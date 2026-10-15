"""Interactively create the first FYPHub administrator, once only.

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
from app.models import User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402

EXPECTED_DATABASE = "fyphub_p1"


def main() -> None:
    """Prompt locally for a new first-admin account without exposing credentials."""
    full_name = input("Administrator full name: ").strip()
    email = input("Administrator email: ").strip().lower()
    password = getpass.getpass("Administrator password: ")
    confirmation = getpass.getpass("Confirm administrator password: ")

    if not full_name or len(full_name) > 255:
        raise RuntimeError("Full name must be between 1 and 255 non-whitespace characters.")
    if not email or len(email) > 320 or "@" not in email:
        raise RuntimeError("Enter a valid administrator email address.")
    if not 8 <= len(password) <= 128:
        raise RuntimeError("Password must be between 8 and 128 characters.")
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

        session.add(
            User(
                full_name=full_name,
                email=email,
                registration_number=None,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
        )

    print("First administrator account created. No credential values were displayed.")


if __name__ == "__main__":
    main()
