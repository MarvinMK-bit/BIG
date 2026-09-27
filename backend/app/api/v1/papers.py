import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.question_paper import PaperStatus, QuestionPaper
from app.models.user import User
from app.repositories.paper_repo import QuestionPaperRepository
from app.schemas.papers import QuestionPaperOut
from app.services.auth_service import get_current_user
from app.services.file_type import detect_paper_mime_type
from app.services.papers import run_paper_extraction
from app.services.storage import get_backend

# Any signed-in user; each paper is visible to its owner, and admins may also read and delete it.
router = APIRouter(prefix="/papers", tags=["papers"])
logger = logging.getLogger(__name__)

UNSUPPORTED_PAPER_MESSAGE = (
    "This file isn't a question paper BIG can read. Please upload a JPEG, PNG, WebP, PDF or "
    "Word (.docx) file."
)
MAX_TITLE_LENGTH = 200


def _blank_to_none(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


async def _get_paper(db: AsyncSession, paper_id: UUID, user: User, *, admin_ok: bool) -> QuestionPaper:
    """The paper if the user owns it (or is an admin, where admin_ok); anything else is a 404."""
    paper = await QuestionPaperRepository(db).get_by_id(paper_id)
    if paper is None or not (paper.owner_id == user.id or (admin_ok and user.is_admin)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question paper not found")
    return paper


@router.post("", response_model=QuestionPaperOut, status_code=status.HTTP_201_CREATED)
async def upload_paper(
    file: UploadFile = File(...),
    title: str = Form(...),
    subject: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuestionPaper:
    clean_title = title.strip()
    if not clean_title or len(clean_title) > MAX_TITLE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Give the paper a title of 1 to {MAX_TITLE_LENGTH} characters.",
        )

    settings = get_settings()
    file_bytes = await file.read()

    # Trust the bytes, not the declared content type
    mime_type = detect_paper_mime_type(file_bytes)
    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=UNSUPPORTED_PAPER_MESSAGE
        )

    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds maximum upload size",
        )

    stored = await get_backend(settings.STORAGE_BACKEND).save(
        file_bytes, filename=file.filename or "upload", mime_type=mime_type
    )
    paper = await QuestionPaperRepository(db).create(
        owner_id=user.id,
        title=clean_title,
        original_filename=file.filename or "upload",
        mime_type=mime_type,
        file_size_bytes=stored.size_bytes,
        storage_key=stored.key,
        subject=_blank_to_none(subject),
    )
    await db.commit()
    return paper


@router.get("", response_model=list[QuestionPaperOut])
async def list_papers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QuestionPaper]:
    """The caller's own papers, newest first."""
    return await QuestionPaperRepository(db).list_for_owner(user.id)


@router.get("/{paper_id}", response_model=QuestionPaperOut)
async def get_paper(
    paper_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuestionPaper:
    return await _get_paper(db, paper_id, user, admin_ok=True)


@router.post("/{paper_id}/extract", response_model=QuestionPaperOut)
async def extract_paper(
    paper_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuestionPaper:
    paper = await _get_paper(db, paper_id, user, admin_ok=False)
    if paper.status != PaperStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Question paper is {paper.status.value}; only pending papers can be extracted",
        )

    # A failure comes back as a FAILED paper with error_message set
    storage = get_backend(get_settings().STORAGE_BACKEND)
    return await run_paper_extraction(paper.id, db, storage)


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper(
    paper_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Owner or admin. Sessions that used the paper keep their results and lose the attachment."""
    paper = await _get_paper(db, paper_id, user, admin_ok=True)
    storage_key = paper.storage_key
    await QuestionPaperRepository(db).delete(paper)
    await db.commit()
    # After the commit, so a row never points at a missing file. The paper is already gone, so a
    # failure here only leaves an orphaned file and must not fail the request.
    try:
        await get_backend(get_settings().STORAGE_BACKEND).delete(storage_key)
    except Exception:
        logger.exception("Deleted question paper %s but not its file %s", paper_id, storage_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
