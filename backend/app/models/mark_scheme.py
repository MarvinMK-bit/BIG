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


class MarkSchemeRecord(Base):
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

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User"] = relationship("User", back_populates="mark_schemes")

    @property
    def scheme_version(self) -> str:
        return f"{self.name}@{self.version}"
