"""Centralized, reversible policy for public registration behavior."""

import os
from enum import StrEnum


class RegistrationMode(StrEnum):
    DEMO = "demo"
    RESTRICTED = "restricted"


REGISTRATION_MODE_ENV = "REGISTRATION_MODE"
DEMO_MODE_WARNING = "Demo registration mode is active."


def get_registration_mode(value: str | None = None) -> RegistrationMode:
    """Return the configured mode, failing closed for missing/invalid values."""
    candidate = value if value is not None else os.getenv(REGISTRATION_MODE_ENV)
    return RegistrationMode.DEMO if (candidate or "").strip().lower() == RegistrationMode.DEMO else RegistrationMode.RESTRICTED


def registration_mode() -> RegistrationMode:
    """Read the current process configuration without exposing it publicly."""
    return get_registration_mode()

