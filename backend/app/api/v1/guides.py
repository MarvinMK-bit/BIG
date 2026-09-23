import re
from pathlib import PurePath
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.grading import UNSUPPORTED_FILE_MESSAGE
from app.core.config import get_settings
from app.core.database import get_db
from app.models.marking_guide import GuideStatus, MarkingGuide
from app.models.user import User
from app.repositories.guide_repo import MarkingGuideRepository
from app.schemas.guides import GuideYamlOut, MarkingGuideOut
from app.services.auth_service import get_current_admin
from app.services.file_type import detect_mime_type
from app.services.guides import (
    build_guide_docx,
    build_scheme_yaml,
    extract_questions_from_guide,
    parse_guide_docx,
    run_guide_ocr,
)
from app.services.storage import get_backend

# Admin only: every route depends on get_current_admin, and guides are scoped to their owner.
router = APIRouter(prefix="/guides", tags=["guides"])

DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_DOCX_BYTES = 5 * 1024 * 1024
_ZIP_MAGIC = b"PK\x03\x04"


def _blank_to_none(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


async def _get_guide(db: AsyncSession, guide_id: UUID, admin: User) -> MarkingGuide:
    guide = await MarkingGuideRepository(db).get_for_owner(guide_id, admin.id)
    if guide is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marking guide not found")
    return guide


def _guide_title(guide: MarkingGuide) -> str:
    return guide.title or PurePath(guide.original_filename).stem or "Marking guide"


def _download_headers(title: str) -> dict[str, str]:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-.") or "marking-guide"
    filename = f"{stem}.docx"
    # Plain filename for old clients, RFC 5987 filename* so non-ASCII titles survive
    return {
        "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(title)}.docx"
    }


@router.post("", response_model=MarkingGuideOut, status_code=status.HTTP_201_CREATED)
async def upload_guide(
    file: UploadFile = File(...),
    subject: str | None = Form(None),
    title: str | None = Form(None),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> MarkingGuide:
    settings = get_settings()
    file_bytes = await file.read()

    # Same validation as script uploads: trust the bytes, not the declared content type
    mime_type = detect_mime_type(file_bytes)
    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=UNSUPPORTED_FILE_MESSAGE
        )

    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds maximum upload size",
        )

    stored = await get_backend(settings.STORAGE_BACKEND).save(
        file_bytes, filename=file.filename or "upload", mime_type=mime_type
    )
    guide = await MarkingGuideRepository(db).create(
        owner_id=admin.id,
        original_filename=file.filename or "upload",
        mime_type=mime_type,
        file_size_bytes=stored.size_bytes,
        storage_key=stored.key,
        subject=_blank_to_none(subject),
        title=_blank_to_none(title),
    )
    await db.commit()
    return guide


@router.get("", response_model=list[MarkingGuideOut])
async def list_guides(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[MarkingGuide]:
    return await MarkingGuideRepository(db).list_for_owner(admin.id)


@router.get("/{guide_id}", response_model=MarkingGuideOut)
async def get_guide(
    guide_id: UUID,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> MarkingGuide:
    return await _get_guide(db, guide_id, admin)


@router.post("/{guide_id}/extract", response_model=MarkingGuideOut)
async def extract_guide(
    guide_id: UUID,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> MarkingGuide:
    guide = await _get_guide(db, guide_id, admin)
    if guide.status != GuideStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Marking guide is {guide.status.value}; only pending guides can be extracted",
        )

    # An OCR failure comes back as a FAILED guide with error_message set
    storage = get_backend(get_settings().STORAGE_BACKEND)
    return await run_guide_ocr(guide.id, db, storage)


@router.get("/{guide_id}/docx")
async def download_guide_docx(
    guide_id: UUID,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    guide = await _get_guide(db, guide_id, admin)
    if guide.status != GuideStatus.EXTRACTED or guide.ocr_markdown is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Marking guide is {guide.status.value}; extract it before downloading the DOCX",
        )

    rows = extract_questions_from_guide(guide.ocr_markdown)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No questions or answers were found in this guide's extracted text.",
        )

    title = _guide_title(guide)
    return Response(
        content=build_guide_docx(title, guide.subject, rows),
        media_type=DOCX_MIME_TYPE,
        headers=_download_headers(title),
    )


@router.post("/{guide_id}/to-yaml", response_model=GuideYamlOut)
async def guide_to_yaml(
    guide_id: UUID,
    file: UploadFile = File(...),
    name: str = Form(...),
    version: str = Form(...),
    subject: str | None = Form(None),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> GuideYamlOut:
    """Convert the reviewed DOCX to scheme YAML. Nothing is saved; the admin uploads it via /schemes."""
    guide = await _get_guide(db, guide_id, admin)

    raw = await file.read(MAX_DOCX_BYTES + 1)
    if len(raw) > MAX_DOCX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"The reviewed guide must be at most {MAX_DOCX_BYTES // (1024 * 1024)}MB.",
        )
    if not raw.startswith(_ZIP_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload the reviewed guide as a Word document (.docx).",
        )

    scheme_subject = _blank_to_none(subject) or guide.subject
    if scheme_subject is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This guide has no subject. Send a subject field with the reviewed DOCX.",
        )

    try:
        rows = parse_guide_docx(raw)
        text, _ = build_scheme_yaml(
            rows,
            name=name.strip(),
            version=version.strip(),
            subject=scheme_subject,
            description=f"Generated from marking guide {_guide_title(guide)!r}.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    return GuideYamlOut(yaml=text)
