from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grading_session import GradingSession, GradingStatus


class GradingSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        owner_id: UUID,
        original_filename: str,
        mime_type: str,
        file_size_bytes: int,
        storage_key: str,
        subject: str | None = None,
    ) -> GradingSession:
        grading_session = GradingSession(
            owner_id=owner_id,
            original_filename=original_filename,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            storage_key=storage_key,
            subject=subject,
        )
        self.session.add(grading_session)
        await self.session.flush()
        return grading_session

    async def get_by_id(self, session_id: UUID) -> GradingSession | None:
        result = await self.session.execute(select(GradingSession).where(GradingSession.id == session_id))
        return result.scalar_one_or_none()

    async def get_for_owner(self, session_id: UUID, owner_id: UUID) -> GradingSession | None:
        result = await self.session.execute(
            select(GradingSession).where(
                GradingSession.id == session_id, GradingSession.owner_id == owner_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_owner(
        self, owner_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[GradingSession]:
        result = await self.session.execute(
            select(GradingSession)
            .where(GradingSession.owner_id == owner_id)
            .order_by(GradingSession.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def mark_processing(self, s: GradingSession) -> GradingSession:
        s.status = GradingStatus.PROCESSING
        await self.session.flush()
        return s

    async def mark_completed(
        self,
        s: GradingSession,
        *,
        ocr_engine: str,
        ocr_markdown: str,
        ocr_confidence: float | None,
    ) -> GradingSession:
        s.status = GradingStatus.COMPLETED
        s.ocr_engine = ocr_engine
        s.ocr_markdown = ocr_markdown
        s.ocr_confidence = ocr_confidence
        s.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return s

    async def mark_failed(self, s: GradingSession, *, error_message: str) -> GradingSession:
        s.status = GradingStatus.FAILED
        s.error_message = error_message
        await self.session.flush()
        return s
