import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)
    email: EmailStr | None = None
    display_name: str | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str | None
    display_name: str | None
    is_admin: bool
    is_active: bool
    attribution_opt_in: bool
    # The user's Lightning address; rewards are paid here
    blink_address: str | None
    created_at: datetime


# name@domain.tld. The name part follows LUD-16 (lowercase letters, digits, "-_.+"); upper case is
# accepted and folded, since people type addresses as they appear in their wallet
_LIGHTNING_ADDRESS = re.compile(r"^[a-z0-9._+-]+@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class UserUpdate(BaseModel):
    """PATCH /auth/me. Omitted fields are left unchanged; blink_address null or "" clears it."""

    blink_address: str | None = None
    attribution_opt_in: bool | None = None

    @field_validator("blink_address")
    @classmethod
    def _lightning_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not value:
            return None
        if len(value) > 320 or not _LIGHTNING_ADDRESS.fullmatch(value):
            raise ValueError(
                "A Lightning address looks like an email address: name@domain, e.g. alice@blink.sv"
            )
        return value


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
