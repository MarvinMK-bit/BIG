from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marking_guide import GuideStatus, MarkingGuide


class MarkingGuideRepository:
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
        title: str | None = None,
    ) -> MarkingGuide:
        guide = MarkingGuide(
            owner_id=owner_id,
            original_filename=original_filename,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            storage_key=storage_key,
            subject=subject,
            title=title,
        )
        self.session.add(guide)
        await self.session.flush()
        return guide

    async def get_by_id(self, guide_id: UUID) -> MarkingGuide | None:
        result = await self.session.execute(select(MarkingGuide).where(MarkingGuide.id == guide_id))
        return result.scalar_one_or_none()

    async def get_for_owner(self, guide_id: UUID, owner_id: UUID) -> MarkingGuide | None:
        result = await self.session.execute(
            select(MarkingGuide).where(MarkingGuide.id == guide_id, MarkingGuide.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def list_for_owner(
        self, owner_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[MarkingGuide]:
        result = await self.session.execute(
            select(MarkingGuide)
            .where(MarkingGuide.owner_id == owner_id)
            .order_by(MarkingGuide.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def mark_processing(self, g: MarkingGuide) -> MarkingGuide:
        g.status = GuideStatus.PROCESSING
        await self.session.flush()
        return g

    async def mark_extracted(
        self,
        g: MarkingGuide,
        *,
        ocr_engine: str,
        ocr_markdown: str,
        ocr_confidence: float | None,
    ) -> MarkingGuide:
        g.status = GuideStatus.EXTRACTED
        g.ocr_engine = ocr_engine
        g.ocr_markdown = ocr_markdown
        g.ocr_confidence = ocr_confidence
        g.extracted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return g

    async def mark_failed(self, g: MarkingGuide, *, error_message: str) -> MarkingGuide:
        g.status = GuideStatus.FAILED
        g.error_message = error_message
        await self.session.flush()
        return g
