from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.marking_guide import GuideStatus, MarkingGuide
from app.repositories.guide_repo import MarkingGuideRepository
from app.services.grading.ocr_runner import MAX_ERROR_MESSAGE_LENGTH, PAGE_SEPARATOR
from app.services.ocr import get_engine
from app.services.storage import StorageBackend


async def run_guide_ocr(
    guide_id: UUID,
    db: AsyncSession,
    storage: StorageBackend,
    engine_name: str | None = None,
) -> MarkingGuide:
    """OCR a pending guide. On failure the guide is marked FAILED and returned, not raised."""
    repo = MarkingGuideRepository(db)

    guide = await repo.get_by_id(guide_id)
    if guide is None:
        raise ValueError(f"Marking guide {guide_id} does not exist")
    if guide.status != GuideStatus.PENDING:
        raise ValueError(f"Marking guide {guide_id} is {guide.status.value}, expected pending")

    await repo.mark_processing(guide)
    await db.commit()

    try:
        file_bytes = await storage.load(guide.storage_key)
        engine = get_engine(engine_name or get_settings().OCR_ENGINE)
        result = await engine.extract(file_bytes, guide.mime_type)

        scores = [page.confidence for page in result.pages if page.confidence is not None]
        await repo.mark_extracted(
            guide,
            ocr_engine=result.engine_name,
            ocr_markdown=PAGE_SEPARATOR.join(page.markdown for page in result.pages),
            ocr_confidence=sum(scores) / len(scores) if scores else None,
        )
    except Exception as exc:
        await repo.mark_failed(guide, error_message=str(exc)[:MAX_ERROR_MESSAGE_LENGTH])
    await db.commit()
    return guide
