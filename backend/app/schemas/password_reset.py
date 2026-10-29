"""Public schemas for password recovery without exposing account existence."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from ..security import validate_password


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: str | None = Field(default=None, min_length=1, max_length=320)
    email: str | None = Field(default=None, min_length=1, max_length=320)
    registration_number: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> "ForgotPasswordRequest":
        values = [value for value in (self.identifier, self.email, self.registration_number) if value is not None]
        if len(values) != 1 or not values[0].strip():
            raise ValueError("Provide one email or registration identifier.")
        return self

    def normalized_identifier(self) -> tuple[str, str]:
        value = (self.identifier or self.email or self.registration_number or "").strip()
        if "@" in value:
            return "email", value.lower()
        return "registration_number", value.upper()


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=256)
    password: str = Field(validation_alias=AliasChoices("password", "new_password"))

    @field_validator("password")
    @classmethod
    def valid_password(cls, value: str) -> str:
        try:
            validate_password(value)
        except ValueError as error:
            raise ValueError(str(error)) from error
        return value


class PasswordResetMessage(BaseModel):
    message: str
