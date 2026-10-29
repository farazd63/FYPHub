"""Shared normalization for Pydantic email fields."""


def normalize_email(value: object) -> object:
    """Trim and case-normalize email input before EmailStr validation."""

    if isinstance(value, str):
        return value.strip().lower()
    return value
