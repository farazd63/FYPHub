from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import engine, get_db
from .models import User, UserRole
from .models import AcademicCycle, AcademicGroupPolicy
from .schemas.academic import CycleOut, PolicyOut
from .schemas.auth import RegistrationRequest, RegistrationResponse
from .security import hash_password

app = FastAPI(title="FYPHub API")

@app.get("/api/v1/academic-cycles",response_model=list[CycleOut])
def list_cycles(session:Session=Depends(get_db))->list[AcademicCycle]:
 return list(session.query(AcademicCycle).order_by(AcademicCycle.id).all())

@app.get("/api/v1/academic-cycles/{cycle_id}/group-policy",response_model=PolicyOut)
def get_group_policy(cycle_id:int,session:Session=Depends(get_db))->AcademicGroupPolicy:
 cycle=session.get(AcademicCycle,cycle_id)
 if cycle is None: raise HTTPException(status_code=404,detail="Academic cycle not found.")
 if cycle.group_policy is None: raise HTTPException(status_code=404,detail="Academic group policy not configured.")
 return cycle.group_policy


@app.get("/health")
def health() -> dict[str, str]:
    """Report application liveness only; this does not check database connectivity."""
    return {"status": "ok", "service": "fyphub-p1-api"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    """Report readiness only when the database and vector extension are available."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            vector_version = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unavailable", "service": "fyphub-p1-api"},
        ) from error

    if vector_version is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unavailable", "service": "fyphub-p1-api"},
        )

    return {"status": "ready", "service": "fyphub-p1-api"}


@app.post(
    "/api/v1/auth/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegistrationResponse,
)
def register_student(
    registration: RegistrationRequest, session: Session = Depends(get_db)
) -> User:
    """Create a student account without accepting public role assignment."""
    full_name = registration.full_name.strip()
    registration_number = registration.registration_number.strip().upper()
    email = str(registration.email).strip().lower()

    if not full_name or len(full_name) > 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="full_name must be between 1 and 255 non-whitespace characters.",
        )
    if not registration_number or len(registration_number) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="registration_number must be between 1 and 100 non-whitespace characters.",
        )
    if len(email) > 320:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="email must not exceed 320 characters.",
        )
    if not 8 <= len(registration.password) <= 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="password must be between 8 and 128 characters.",
        )

    user = User(
        full_name=full_name,
        email=email,
        registration_number=registration_number,
        password_hash=hash_password(registration.password),
        role=UserRole.STUDENT,
    )
    session.add(user)
    try:
        session.commit()
        session.refresh(user)
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email or registration number already exists.",
        ) from error

    return user
