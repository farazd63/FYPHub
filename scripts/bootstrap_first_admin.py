r"""Interactively create the first FYPHub administrator, once only.

Run from the repository root:
    & '.\backend\.venv\Scripts\python.exe' .\scripts\bootstrap_first_admin.py
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

from sqlalchemy import select, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import InstitutionMembership, User, UserRole  # noqa: E402
from app.schemas.email import normalize_szabist_email  # noqa: E402
from app.security import hash_password, validate_full_name, validate_password  # noqa: E402
from app.tenant import primary_institution_id, utc_now  # noqa: E402

EXPECTED_DATABASE = "fyphub_p1"


def main() -> None:
    """Prompt locally for a new first-admin account without exposing credentials."""
    full_name = input("Administrator full name: ").strip()
    email = input("Administrator email: ")
    password = getpass.getpass("Administrator password: ")
    confirmation = getpass.getpass("Confirm administrator password: ")

    try:
        full_name = validate_full_name(full_name)
        email = str(normalize_szabist_email(email))
        validate_password(password)
    except ValueError as error:
        raise RuntimeError(str(error)) from error
    if password != confirmation:
        raise RuntimeError("Passwords do not match.")

    with SessionLocal.begin() as session:
        database_name = session.execute(text("SELECT current_database()")).scalar_one()
        if database_name != EXPECTED_DATABASE:
            raise RuntimeError(
                f"Refusing to modify {database_name!r}; expected {EXPECTED_DATABASE!r}."
            )
        if session.execute(select(User.id).where(User.role == UserRole.ADMIN)).first() is not None:
            raise RuntimeError("An administrator account already exists; no account was changed.")
        if session.execute(select(User.id).where(User.email == email)).first() is not None:
            raise RuntimeError("That email already belongs to an account; no account was changed.")

        institution_id = primary_institution_id(session)
        if institution_id is None:
            raise RuntimeError("The primary SZABIST institution is not configured.")
        now = utc_now()
        user = User(
            full_name=full_name,
            email=email,
            registration_number=None,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            institution_id=institution_id,
            is_active=True,
            email_verified_at=now,
            access_approved_at=now,
        )
        session.add(user)
        session.flush()
        session.add(
            InstitutionMembership(
                institution_id=institution_id,
                user_id=user.id,
                membership_role="INSTITUTION_ADMIN",
                status="ACTIVE",
                approved_by_id=user.id,
                approved_at=now,
            )
        )

    print("First administrator account created. No credential values were displayed.")


if __name__ == "__main__":
    main()
