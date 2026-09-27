from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_paper import PaperStatus, QuestionPaper


class QuestionPaperRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        owner_id: UUID,
        title: str,
        original_filename: str,
        mime_type: str,
        file_size_bytes: int,
        storage_key: str,
        subject: str | None = None,
    ) -> QuestionPaper:
        paper = QuestionPaper(
            owner_id=owner_id,
            title=title,
            original_filename=original_filename,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            storage_key=storage_key,
            subject=subject,
        )
        self.session.add(paper)
        await self.session.flush()
        return paper

    async def get_by_id(self, paper_id: UUID) -> QuestionPaper | None:
        result = await self.session.execute(select(QuestionPaper).where(QuestionPaper.id == paper_id))
        return result.scalar_one_or_none()

    async def get_for_owner(self, paper_id: UUID, owner_id: UUID) -> QuestionPaper | None:
        result = await self.session.execute(
            select(QuestionPaper).where(QuestionPaper.id == paper_id, QuestionPaper.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def list_for_owner(
        self, owner_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[QuestionPaper]:
        result = await self.session.execute(
            select(QuestionPaper)
            .where(QuestionPaper.owner_id == owner_id)
            .order_by(QuestionPaper.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def mark_processing(self, paper: QuestionPaper) -> QuestionPaper:
        paper.status = PaperStatus.PROCESSING
        await self.session.flush()
        return paper

    async def mark_extracted(
        self,
        paper: QuestionPaper,
        *,
        ocr_engine: str,
        ocr_markdown: str,
        ocr_confidence: float | None,
    ) -> QuestionPaper:
        paper.status = PaperStatus.EXTRACTED
        paper.ocr_engine = ocr_engine
        paper.ocr_markdown = ocr_markdown
        paper.ocr_confidence = ocr_confidence
        paper.extracted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return paper

    async def mark_failed(self, paper: QuestionPaper, *, error_message: str) -> QuestionPaper:
        paper.status = PaperStatus.FAILED
        paper.error_message = error_message
        await self.session.flush()
        return paper

    async def delete(self, paper: QuestionPaper) -> None:
        """Delete the paper; the database detaches it from any sessions (ON DELETE SET NULL).

        Ownership is the caller's check.
        """
        await self.session.delete(paper)
        await self.session.flush()
