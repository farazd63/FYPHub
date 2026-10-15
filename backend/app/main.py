from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import engine, get_db
from .models import AdminAuditEvent, AuthSession, Team, TeamMember, User, UserRole
from .models import AcademicCycle, AcademicGroupPolicy
from .schemas.academic import CycleOut, PolicyOut
from .schemas.auth import CurrentUserResponse, LoginRequest, RegistrationRequest, RegistrationResponse
from .schemas.admin_users import AdminUserCreate, AdminUserPage, AdminUserResponse, AdminUserRoleChange, AdminUserStatusChange
from .schemas.team_registration import TeamMemberInput, TeamRegistrationRequest, TeamRegistrationResponse
from .security import generate_session_token, hash_password, hash_session_token, verify_password
from .auth import (
    ALLOWED_BROWSER_ORIGIN,
    SESSION_COOKIE_NAME,
    SESSION_LIFETIME_HOURS,
    clear_session_cookie,
    get_current_user,
    require_roles,
    set_session_cookie,
    utc_now,
    validate_mutating_origin,
)

app = FastAPI(title="FYPHub API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)

_DUMMY_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$FkrCX/M1V29q1Jj4yMHSiw$rONBAdg5KlI9DhIbVoDaHB3lM5HJXojJYVeAaLlbGwI"


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


@app.post("/api/v1/auth/login", response_model=CurrentUserResponse)
def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
) -> User:
    """Authenticate an active account and issue a new opaque cookie session."""
    validate_mutating_origin(request)
    if credentials.email is not None:
        user = session.execute(
            select(User).where(User.email == str(credentials.email).strip().lower())
        ).scalar_one_or_none()
    else:
        user = session.execute(
            select(User).where(User.registration_number == credentials.registration_number)
        ).scalar_one_or_none()
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(credentials.password, password_hash)
    if (
        user is None
        or not password_valid
        or not user.is_active
        or (credentials.requested_role is not None and user.role != credentials.requested_role)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    now = utc_now()
    presented_token = request.cookies.get(SESSION_COOKIE_NAME)
    if presented_token:
        existing = session.execute(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(presented_token))
        ).scalar_one_or_none()
        if existing is not None and existing.revoked_at is None:
            existing.revoked_at = now

    raw_token = generate_session_token()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            expires_at=now + timedelta(hours=SESSION_LIFETIME_HOURS),
        )
    )
    session.commit()
    set_session_cookie(request, response, raw_token)
    return user


@app.get("/api/v1/auth/me", response_model=CurrentUserResponse)
def current_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated active account's safe fields."""
    return current_user


@app.get("/api/v1/admin/me", response_model=CurrentUserResponse)
def admin_current_user(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    """Return the current account only when its persisted role is ADMIN."""
    return current_user


def admin_user_error(status_code: int, code: str, message: str) -> HTTPException:
    """Return a safe management failure without leaking persistence details."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def add_admin_audit_event(
    session: Session, *, actor_id: int, affected_user_id: int, action: str, changed_values: dict[str, object]
) -> None:
    """Append only non-sensitive account metadata; never credentials or sessions."""
    session.add(
        AdminAuditEvent(
            actor_id=actor_id,
            affected_user_id=affected_user_id,
            action=action,
            changed_values=changed_values,
        )
    )


def shared_team_account(session: Session, user_id: int) -> bool:
    return session.execute(select(Team.id).where(Team.shared_user_id == user_id)).scalar_one_or_none() is not None


def lock_and_protect_last_active_admin(session: Session, user: User, *, will_remain_active_admin: bool) -> None:
    """Serialize changes that could remove the final active ADMIN account."""
    if user.role != UserRole.ADMIN or will_remain_active_admin:
        return
    # PostgreSQL transaction advisory lock closes the count-then-change race across requests.
    session.execute(text("SELECT pg_advisory_xact_lock(98137241)"))
    active_admins = session.execute(
        select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
    ).scalar_one()
    if user.is_active and active_admins <= 1:
        raise admin_user_error(
            status.HTTP_409_CONFLICT,
            "last_active_admin",
            "At least one active ADMIN account must remain.",
        )


def revoke_user_sessions(session: Session, user_id: int) -> None:
    session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


@app.get("/api/v1/admin/users", response_model=AdminUserPage)
def list_admin_users(
    search: str | None = Query(default=None, max_length=320),
    role: UserRole | None = None,
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    statement = select(User)
    count_statement = select(func.count(User.id))
    filters = []
    if search and search.strip():
        needle = f"%{search.strip()}%"
        filters.append(or_(User.full_name.ilike(needle), User.email.ilike(needle), User.registration_number.ilike(needle)))
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))
    if filters:
        statement = statement.where(*filters)
        count_statement = count_statement.where(*filters)
    total = session.execute(count_statement).scalar_one()
    users = session.execute(
        statement.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {"items": users, "page": page, "page_size": page_size, "total": total}


@app.post("/api/v1/admin/users", status_code=status.HTTP_201_CREATED, response_model=AdminUserResponse)
def create_admin_user(
    payload: AdminUserCreate,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> User:
    validate_mutating_origin(request)
    user = User(
        full_name=payload.full_name,
        email=str(payload.email).strip().lower(),
        registration_number=payload.registration_number,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    session.add(user)
    try:
        session.flush()
        add_admin_audit_event(
            session,
            actor_id=actor.id,
            affected_user_id=user.id,
            action="account_created",
            changed_values={"email": user.email, "role": user.role.value, "is_active": True},
        )
        session.commit()
        session.refresh(user)
    except IntegrityError as error:
        session.rollback()
        raise admin_user_error(status.HTTP_409_CONFLICT, "duplicate_account", "An account with that email or registration number already exists.") from error
    return user


@app.patch("/api/v1/admin/users/{user_id}/status", response_model=AdminUserResponse)
def change_admin_user_status(
    user_id: int,
    payload: AdminUserStatusChange,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> User:
    validate_mutating_origin(request)
    user = session.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if user is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "account_not_found", "Account was not found.")
    if user.is_active == payload.is_active:
        return user
    if not payload.is_active and shared_team_account(session, user.id):
        raise admin_user_error(status.HTTP_409_CONFLICT, "shared_team_account", "Shared team accounts cannot be deactivated here.")
    lock_and_protect_last_active_admin(
        session, user, will_remain_active_admin=payload.is_active and user.role == UserRole.ADMIN
    )
    previous = user.is_active
    user.is_active = payload.is_active
    if not payload.is_active:
        revoke_user_sessions(session, user.id)
    add_admin_audit_event(
        session, actor_id=actor.id, affected_user_id=user.id, action="account_status_changed",
        changed_values={"is_active": payload.is_active, "previous_is_active": previous},
    )
    try:
        session.commit()
        session.refresh(user)
    except SQLAlchemyError:
        session.rollback()
        raise
    return user


@app.patch("/api/v1/admin/users/{user_id}/role", response_model=AdminUserResponse)
def change_admin_user_role(
    user_id: int,
    payload: AdminUserRoleChange,
    request: Request,
    actor: User = Depends(require_roles(UserRole.ADMIN)),
    session: Session = Depends(get_db),
) -> User:
    validate_mutating_origin(request)
    user = session.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if user is None:
        raise admin_user_error(status.HTTP_404_NOT_FOUND, "account_not_found", "Account was not found.")
    if user.role == payload.role:
        return user
    if shared_team_account(session, user.id):
        raise admin_user_error(status.HTTP_409_CONFLICT, "shared_team_account", "Shared team account roles cannot be changed here.")
    if payload.role == UserRole.STUDENT and user.registration_number is None:
        raise admin_user_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "student_registration_required", "A STUDENT account requires a registration number.")
    lock_and_protect_last_active_admin(
        session, user, will_remain_active_admin=user.is_active and payload.role == UserRole.ADMIN
    )
    previous = user.role
    user.role = payload.role
    revoke_user_sessions(session, user.id)
    add_admin_audit_event(
        session, actor_id=actor.id, affected_user_id=user.id, action="account_role_changed",
        changed_values={"role": payload.role.value, "previous_role": previous.value},
    )
    try:
        session.commit()
        session.refresh(user)
    except SQLAlchemyError:
        session.rollback()
        raise
    return user


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
) -> Response:
    """Revoke the presented session when present and always clear its browser cookie."""
    validate_mutating_origin(request)
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        record = session.execute(
            select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        ).scalar_one_or_none()
        if record is not None and record.revoked_at is None:
            record.revoked_at = utc_now()
            session.commit()
    clear_session_cookie(request, response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


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
