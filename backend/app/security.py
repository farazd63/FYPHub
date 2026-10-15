"""Password and opaque-session security utilities."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

_password_hasher = PasswordHasher(type=Type.ID)


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
