import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class MarkSchemeSource(str, enum.Enum):
    MANUAL = "manual"
    GENERATED = "generated"
    FEEDBACK_DERIVED = "feedback-derived"


class SchemeReviewStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class MarkSchemeRecord(Base):
    """A mark scheme uploaded through the app, as opposed to a file in the repository.

    review_status records an admin's decision on whether the scheme enters BIG's public
    corpus, i.e. is exported to the repository's mark_schemes directory. It does not gate
    use: a pending (or declined) scheme remains fully usable for grading by anyone who can
    see it, exactly as before it was reviewed.
    """

    __tablename__ = "mark_schemes"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_mark_schemes_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[MarkSchemeSource] = mapped_column(
        Enum(MarkSchemeSource, name="mark_scheme_source"),
        nullable=False,
        default=MarkSchemeSource.MANUAL,
    )

    # The scheme exactly as uploaded; re-parsed with parse_scheme when used for grading
    yaml_content: Mapped[str] = mapped_column(Text, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Schemes are public by default (section 3.7). Nothing sets this false yet.
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    review_status: Mapped[SchemeReviewStatus] = mapped_column(
        Enum(SchemeReviewStatus, name="scheme_review_status"),
        nullable=False,
        default=SchemeReviewStatus.PENDING,
        server_default=SchemeReviewStatus.PENDING.name,
        index=True,
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set by scripts.export_schemes when the scheme is written to the repository's scheme directory
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User"] = relationship(
        "User", back_populates="mark_schemes", foreign_keys=[owner_id]
    )
    reviewed_by: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by_id])

    @property
    def scheme_version(self) -> str:
        return f"{self.name}@{self.version}"
