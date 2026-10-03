import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AccessRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"


class AccessRequest(Base):
    """A request for an account, reviewed by hand. Approving it creates the User; nothing else does
    while ALLOW_REGISTRATION is false.
    """

    __tablename__ = "access_requests"
    __table_args__ = (
        CheckConstraint("email IS NOT NULL OR phone IS NOT NULL", name="ck_access_requests_contact"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Lower-cased, like users.username. Unique across all requests, decided ones included
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Who they are and why they want access, in their own words
    about: Mapped[str] = mapped_column(Text, nullable=False)

    # Hashed when the request is made; copied to the User on approval. The password is never stored
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[AccessRequestStatus] = mapped_column(
        Enum(AccessRequestStatus, name="access_request_status"),
        nullable=False,
        default=AccessRequestStatus.PENDING,
        index=True,
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reviewed_by: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by_id])
