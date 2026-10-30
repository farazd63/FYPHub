"""Password and opaque-session security utilities."""

import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

_password_hasher = PasswordHasher(type=Type.ID)

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def password_policy_errors(password: str) -> list[str]:
    """Return safe, user-facing password requirements that are not met."""
    errors: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append("at least 8 characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append("no more than 128 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    if not re.search(r"[0-9]", password):
        errors.append("one number")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("one special character")
    return errors


def validate_password(password: str) -> None:
    """Validate a newly supplied account password before it is hashed."""
    errors = password_policy_errors(password)
    if errors:
        raise ValueError("Password must contain " + ", ".join(errors) + ".")


def hash_password(password: str) -> str:
    """Return an Argon2id hash without modifying the supplied password."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify an unmodified password against an Argon2id hash."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def generate_session_token() -> str:
    """Return an opaque, URL-safe session bearer value; never persist this value."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Return the deterministic database representation of an opaque session token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
