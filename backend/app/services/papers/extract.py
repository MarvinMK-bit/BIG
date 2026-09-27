from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.question_paper import PaperStatus, QuestionPaper
from app.repositories.paper_repo import QuestionPaperRepository
from app.services.file_type import DOCX_MIME_TYPE
from app.services.grading.ocr_runner import MAX_ERROR_MESSAGE_LENGTH, PAGE_SEPARATOR
from app.services.ocr import get_engine
from app.services.papers.docx_text import docx_to_markdown
from app.services.storage import StorageBackend

# Recorded as the paper's ocr_engine when its text came from the document itself
DOCX_TEXT_ENGINE = "docx-text"


async def run_paper_extraction(
    paper_id: UUID,
    db: AsyncSession,
    storage: StorageBackend,
    engine_name: str | None = None,
) -> QuestionPaper:
    """Extract a pending paper's text: read directly from a DOCX, OCR for images and PDFs.

    On failure the paper is marked FAILED and returned, not raised.
    """
    repo = QuestionPaperRepository(db)

    paper = await repo.get_by_id(paper_id)
    if paper is None:
        raise ValueError(f"Question paper {paper_id} does not exist")
    if paper.status != PaperStatus.PENDING:
        raise ValueError(f"Question paper {paper_id} is {paper.status.value}, expected pending")

    await repo.mark_processing(paper)
    await db.commit()

    try:
        file_bytes = await storage.load(paper.storage_key)
        if paper.mime_type == DOCX_MIME_TYPE:
            # The text already exists; OCR would only add errors
            await repo.mark_extracted(
                paper,
                ocr_engine=DOCX_TEXT_ENGINE,
                ocr_markdown=docx_to_markdown(file_bytes),
                ocr_confidence=None,
            )
        else:
            engine = get_engine(engine_name or get_settings().OCR_ENGINE)
            result = await engine.extract(file_bytes, paper.mime_type)
            scores = [page.confidence for page in result.pages if page.confidence is not None]
            await repo.mark_extracted(
                paper,
                ocr_engine=result.engine_name,
                ocr_markdown=PAGE_SEPARATOR.join(page.markdown for page in result.pages),
                ocr_confidence=sum(scores) / len(scores) if scores else None,
            )
    except Exception as exc:
        await repo.mark_failed(paper, error_message=str(exc)[:MAX_ERROR_MESSAGE_LENGTH])
    await db.commit()
    return paper
