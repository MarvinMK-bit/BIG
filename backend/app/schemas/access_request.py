import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from app.models.access_request import AccessRequestStatus

# Digits with the usual separators and an optional leading +; 7 to 15 digits, as E.164 allows
_PHONE = re.compile(r"^\+?[0-9 ()\-.]+$")

# Blank optional fields arrive as "" from a form; strip_whitespace then _blank_to_none makes them None
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
ReviewNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class AccessRequestCreate(BaseModel):
    """POST /auth/request-access. At least one of email or phone is required."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)
    display_name: OptionalText | None = None
    email: EmailStr | None = None
    phone: str | None = None
    about: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("display_name", "email", "phone", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        digits = sum(c.isdigit() for c in value)
        if not _PHONE.fullmatch(value) or not 7 <= digits <= 15:
            raise ValueError("Enter a phone number with its country code, e.g. +44 7700 900123")
        return value

    @model_validator(mode="after")
    def _contact(self) -> "AccessRequestCreate":
        if self.email is None and self.phone is None:
            raise ValueError("Give an email address or a phone number so we can contact you")
        return self


class AccessRequestAccepted(BaseModel):
    # The same whatever happened to the request, so the endpoint reveals nothing about usernames
    message: str


class AccessRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None
    phone: str | None
    display_name: str | None
    about: str
    status: AccessRequestStatus
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime


class AccessRequestReview(BaseModel):
    status: Literal[AccessRequestStatus.APPROVED, AccessRequestStatus.DECLINED]
    note: ReviewNote | None = None
