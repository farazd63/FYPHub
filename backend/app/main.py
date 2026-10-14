from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import engine, get_db
from .models import Team, TeamMember, User, UserRole
from .models import AcademicCycle, AcademicGroupPolicy
from .schemas.academic import CycleOut, PolicyOut
from .schemas.auth import RegistrationRequest, RegistrationResponse
from .schemas.team_registration import TeamMemberInput, TeamRegistrationRequest, TeamRegistrationResponse
from .security import hash_password

app = FastAPI(title="FYPHub API")


@app.exception_handler(RequestValidationError)
async def request_validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    """Expose consistent, field-addressable request validation failures."""
    fields = []
    for item in error.errors():
        location = item.get("loc", ())
        path = ".".join(str(part) for part in location if part != "body")
        fields.append({"path": path, "code": item["type"]})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": {
                "code": "invalid_request",
                "message": "Request validation failed.",
                "fields": fields,
            }
        },
    )


def registration_error(
    status_code: int, code: str, message: str, field: str | None = None
) -> HTTPException:
    """Return a public, structured error without database implementation details."""
    detail: dict[str, str] = {"code": code, "message": message}
    if field is not None:
        detail["field"] = field
    return HTTPException(status_code=status_code, detail=detail)


def normalize_team_member(member: TeamMemberInput, path: str) -> dict[str, str]:
    """Apply the established identifier conventions and field-length rules."""
    full_name = member.full_name.strip()
    registration_number = member.registration_number.strip().upper()
    university_email = str(member.university_email).strip().lower()

    if not full_name or len(full_name) > 255:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_full_name",
            "Full name must be between 1 and 255 non-whitespace characters.",
            f"{path}.full_name",
        )
    if not registration_number or len(registration_number) > 100:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_registration_number",
            "Registration number must be between 1 and 100 non-whitespace characters.",
            f"{path}.registration_number",
        )
    if len(university_email) > 320:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_university_email",
            "University email must not exceed 320 characters.",
            f"{path}.university_email",
        )
    return {
        "full_name": full_name,
        "registration_number": registration_number,
        "university_email": university_email,
    }

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


@app.post(
    "/api/v1/team-registration",
    status_code=status.HTTP_201_CREATED,
    response_model=TeamRegistrationResponse,
)
def register_team(
    registration: TeamRegistrationRequest, session: Session = Depends(get_db)
) -> dict[str, object]:
    """Atomically create one shared student account, team, and member contacts."""
    creator = normalize_team_member(registration.creator, "creator")
    members = [
        normalize_team_member(member, f"members.{index}")
        for index, member in enumerate(registration.members)
    ]
    all_members = [creator, *members]
    shared_login_email = str(registration.shared_login_email).strip().lower()

    if len(shared_login_email) > 320:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_shared_login_email",
            "Shared login email must not exceed 320 characters.",
            "shared_login_email",
        )
    if not 8 <= len(registration.password) <= 128:
        raise registration_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_password_length",
            "Password must be between 8 and 128 characters.",
            "password",
        )

    registration_paths: dict[str, str] = {}
    email_paths: dict[str, str] = {}
    for index, member in enumerate(all_members):
        prefix = "creator" if index == 0 else f"members.{index - 1}"
        registration_number = member["registration_number"]
        university_email = member["university_email"]
        if registration_number in registration_paths:
            raise registration_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "duplicate_request_registration_number",
                "Registration numbers must be unique within the team.",
                f"{prefix}.registration_number",
            )
        if university_email in email_paths:
            raise registration_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "duplicate_request_university_email",
                "University emails must be unique within the team.",
                f"{prefix}.university_email",
            )
        registration_paths[registration_number] = prefix
        email_paths[university_email] = prefix

    try:
        cycle = session.execute(
            select(AcademicCycle)
            .where(AcademicCycle.id == registration.academic_cycle_id)
            .with_for_update()
        ).scalar_one_or_none()
        if cycle is None:
            raise registration_error(
                status.HTTP_404_NOT_FOUND,
                "academic_cycle_not_found",
                "Academic cycle was not found.",
                "academic_cycle_id",
            )
        if not cycle.registration_open:
            raise registration_error(
                status.HTTP_409_CONFLICT,
                "academic_cycle_closed",
                "Registration is not open for this academic cycle.",
                "academic_cycle_id",
            )

        policy = session.execute(
            select(AcademicGroupPolicy)
            .where(AcademicGroupPolicy.academic_cycle_id == cycle.id)
            .with_for_update()
        ).scalar_one_or_none()
        if policy is None:
            raise registration_error(
                status.HTTP_409_CONFLICT,
                "academic_group_policy_missing",
                "Academic group policy is not configured for this cycle.",
                "academic_cycle_id",
            )
        if len(all_members) > policy.max_group_size:
            raise registration_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "group_size_exceeded",
                "Team size exceeds the configured maximum.",
                "members",
            )

        existing_user = session.execute(
            select(User.email, User.registration_number).where(
                or_(
                    User.email == shared_login_email,
                    User.registration_number == creator["registration_number"],
                )
            )
        ).all()
        for email, registration_number in existing_user:
            if email == shared_login_email:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "shared_login_email_exists",
                    "An account with that shared login email already exists.",
                    "shared_login_email",
                )
            if registration_number == creator["registration_number"]:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "creator_registration_exists",
                    "An account with that creator registration number already exists.",
                    "creator.registration_number",
                )

        existing_member = session.execute(
            select(TeamMember.registration_number, TeamMember.university_email).where(
                TeamMember.academic_cycle_id == cycle.id,
                TeamMember.is_active.is_(True),
                or_(
                    TeamMember.registration_number.in_(registration_paths),
                    TeamMember.university_email.in_(email_paths),
                ),
            )
        ).all()
        for registration_number, university_email in existing_member:
            if registration_number in registration_paths:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "member_registration_exists",
                    "An active member with that registration number already exists in this cycle.",
                    f"{registration_paths[registration_number]}.registration_number",
                )
            if university_email in email_paths:
                raise registration_error(
                    status.HTTP_409_CONFLICT,
                    "member_university_email_exists",
                    "An active member with that university email already exists in this cycle.",
                    f"{email_paths[university_email]}.university_email",
                )

        user = User(
            full_name=creator["full_name"],
            email=shared_login_email,
            registration_number=creator["registration_number"],
            password_hash=hash_password(registration.password),
            role=UserRole.STUDENT,
        )
        session.add(user)
        session.flush()

        team = Team(academic_cycle_id=cycle.id, shared_user_id=user.id)
        session.add(team)
        session.flush()

        created_members = [
            TeamMember(
                team_id=team.id,
                academic_cycle_id=cycle.id,
                is_creator=index == 0,
                **member,
            )
            for index, member in enumerate(all_members)
        ]
        session.add_all(created_members)
        session.commit()
        for record in (user, team, *created_members):
            session.refresh(record)
    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as error:
        session.rollback()
        raise registration_error(
            status.HTTP_409_CONFLICT,
            "duplicate_conflict",
            "A conflicting account or active team member already exists.",
        ) from error
    except SQLAlchemyError as error:
        session.rollback()
        raise registration_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "team_registration_failed",
            "Team registration could not be completed.",
        ) from error

    return {
        "account": user,
        "team": team,
        "cycle": cycle,
        "members": created_members,
    }
