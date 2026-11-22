"""Shared normalization for Pydantic email fields."""

SZABIST_EMAIL_DOMAIN = "szabist-isb.pk"


def normalize_email(value: object) -> object:
    """Trim and case-normalize email input before EmailStr validation."""

    if isinstance(value, str):
        return value.strip().lower()
    return value


def normalize_szabist_email(value: object) -> object:
    """Normalize an email and require the single configured SZABIST domain."""

    normalized = normalize_email(value)
    if isinstance(normalized, str):
        domain = normalized.rsplit("@", 1)[1] if normalized.count("@") == 1 else ""
        if domain != SZABIST_EMAIL_DOMAIN:
            raise ValueError("Only @szabist-isb.pk university emails are accepted.")
    return normalized
