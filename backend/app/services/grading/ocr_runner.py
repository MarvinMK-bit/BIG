from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.grading_session import GradingSession, GradingStatus
from app.repositories.grading_repo import GradingSessionRepository
from app.services.ocr import OCRPage, get_engine
from app.services.storage import StorageBackend

PAGE_SEPARATOR = "\n\n---\n\n"
MAX_ERROR_MESSAGE_LENGTH = 1000


def _mean_confidence(pages: list[OCRPage]) -> float | None:
    scores = [page.confidence for page in pages if page.confidence is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)


async def run_ocr(
    session_id: UUID,
    db: AsyncSession,
    storage: StorageBackend,
    engine_name: str | None = None,
) -> GradingSession:
    repo = GradingSessionRepository(db)

    grading_session = await repo.get_by_id(session_id)
    if grading_session is None:
        raise ValueError(f"Grading session {session_id} does not exist")
    if grading_session.status != GradingStatus.PENDING:
        raise ValueError(
            f"Grading session {session_id} is {grading_session.status.value}, expected pending"
        )

    await repo.mark_processing(grading_session)
    await db.commit()

    try:
        file_bytes = await storage.load(grading_session.storage_key)
        engine = get_engine(engine_name or get_settings().OCR_ENGINE)
        result = await engine.extract(file_bytes, grading_session.mime_type)

        await repo.mark_completed(
            grading_session,
            ocr_engine=result.engine_name,
            ocr_markdown=PAGE_SEPARATOR.join(page.markdown for page in result.pages),
            ocr_confidence=_mean_confidence(result.pages),
        )
        await db.commit()
    except Exception as exc:
        await repo.mark_failed(grading_session, error_message=str(exc)[:MAX_ERROR_MESSAGE_LENGTH])
        await db.commit()
        raise

    return grading_session
