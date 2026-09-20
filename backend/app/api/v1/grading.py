import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.grading_session import GradingSession, GradingStatus
from app.models.question_result import QuestionResult
from app.models.user import User
from app.repositories.grading_repo import GradingSessionRepository
from app.repositories.result_repo import QuestionResultRepository
from app.schemas.grading import (
    GraderAccuracyOut,
    GradingRunOut,
    GradingSessionOut,
    QuestionResultOut,
    RunComparisonOut,
    SchemeGradeRequest,
    SchemeGradeResponse,
    VerdictRequest,
)
from app.services.auth_service import get_current_admin, get_current_user
from app.services.grading import grade_with_llm, grade_with_scheme, run_ocr
from app.services.grading.accuracy import measure_accuracy
from app.services.grading.comparison import RunNotFoundError, compare_runs
from app.services.grading.schemes import load_all_schemes
from app.services.storage import get_backend

router = APIRouter(prefix="/grading", tags=["grading"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


@router.post("/upload", response_model=GradingSessionOut, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    subject: str | None = Form(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GradingSession:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type {file.content_type!r}",
        )

    settings = get_settings()
    file_bytes = await file.read()

    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds maximum upload size",
        )

    backend = get_backend(settings.STORAGE_BACKEND)
    stored = await backend.save(
        file_bytes, filename=file.filename or "upload", mime_type=file.content_type
    )

    repo = GradingSessionRepository(session)
    grading_session = await repo.create(
        owner_id=user.id,
        original_filename=file.filename or "upload",
        mime_type=file.content_type,
        file_size_bytes=stored.size_bytes,
        storage_key=stored.key,
        subject=subject,
    )
    await session.commit()

    return grading_session


@router.get("/sessions", response_model=list[GradingSessionOut])
async def list_sessions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[GradingSession]:
    repo = GradingSessionRepository(session)
    return await repo.list_for_owner(user.id)


@router.get("/sessions/{session_id}", response_model=GradingSessionOut)
async def get_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GradingSession:
    repo = GradingSessionRepository(session)
    grading_session = await repo.get_for_owner(session_id, user.id)

    if grading_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading session not found")

    return grading_session


@router.post("/sessions/{session_id}/extract", response_model=GradingSessionOut)
async def extract(
    session_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GradingSession:
    repo = GradingSessionRepository(session)
    grading_session = await repo.get_for_owner(session_id, user.id)

    if grading_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading session not found")

    if grading_session.status != GradingStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Grading session is {grading_session.status.value}; only pending sessions can be extracted",
        )

    storage = get_backend(get_settings().STORAGE_BACKEND)
    return await run_ocr(session_id, session, storage)


@router.post("/sessions/{session_id}/grade/scheme", response_model=SchemeGradeResponse)
async def grade_scheme(
    session_id: UUID,
    body: SchemeGradeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SchemeGradeResponse:
    repo = GradingSessionRepository(session)
    grading_session = await repo.get_for_owner(session_id, user.id)

    if grading_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading session not found")

    if grading_session.status != GradingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Grading session is {grading_session.status.value}; OCR must be completed before grading",
        )

    schemes = load_all_schemes(Path(get_settings().MARK_SCHEMES_DIR))
    scheme = schemes.get(body.scheme_version)
    if scheme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mark scheme {body.scheme_version!r} not found",
        )

    grading_run_id = uuid.uuid4()
    results = await grade_with_scheme(grading_session, scheme, session, grading_run_id)
    await session.commit()

    return SchemeGradeResponse(
        grading_run_id=grading_run_id,
        results=[QuestionResultOut.model_validate(r) for r in results],
    )


@router.post("/sessions/{session_id}/grade/llm", response_model=SchemeGradeResponse)
async def grade_llm(
    session_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SchemeGradeResponse:
    repo = GradingSessionRepository(session)
    grading_session = await repo.get_for_owner(session_id, user.id)

    if grading_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading session not found")

    if grading_session.status != GradingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Grading session is {grading_session.status.value}; OCR must be completed before grading",
        )

    if not get_settings().ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM grading is unavailable: ANTHROPIC_API_KEY is not configured on the server",
        )

    grading_run_id = uuid.uuid4()
    results = await grade_with_llm(grading_session, session, grading_run_id)
    await session.commit()

    return SchemeGradeResponse(
        grading_run_id=grading_run_id,
        results=[QuestionResultOut.model_validate(r) for r in results],
    )


@router.get("/sessions/{session_id}/comparison", response_model=RunComparisonOut)
async def get_comparison(
    session_id: UUID,
    llm_run_id: UUID | None = None,
    scheme_run_id: UUID | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> RunComparisonOut:
    grading_session = await GradingSessionRepository(session).get_for_owner(session_id, user.id)
    if grading_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading session not found")

    try:
        comparison = await compare_runs(
            session_id, user.id, session, llm_run_id=llm_run_id, scheme_run_id=scheme_run_id
        )
    except RunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return RunComparisonOut.model_validate(comparison)


@router.get("/sessions/{session_id}/runs", response_model=list[GradingRunOut])
async def list_runs(
    session_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[GradingRunOut]:
    grading_session = await GradingSessionRepository(session).get_for_owner(session_id, user.id)
    if grading_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading session not found")

    runs = await QuestionResultRepository(session).list_runs_for_session(session_id, user.id)
    return [
        GradingRunOut(
            grading_run_id=run_id,
            grader_type=grader_type,
            mark_scheme_version=scheme_version,
            created_at=created_at,
        )
        for run_id, grader_type, scheme_version, created_at in runs
    ]


@router.patch("/results/{result_id}/verdict", response_model=QuestionResultOut)
async def set_verdict(
    result_id: UUID,
    body: VerdictRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> QuestionResult:
    result = await QuestionResultRepository(session).set_human_verdict(
        result_id, user.id, body.is_correct
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")

    await session.commit()
    return result


@router.get("/accuracy", response_model=list[GraderAccuracyOut])
async def get_accuracy(
    subject: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[GraderAccuracyOut]:
    accuracy = await measure_accuracy(session, owner_id=user.id, subject=subject)
    return [GraderAccuracyOut.model_validate(a) for a in accuracy]


@router.get("/accuracy/global", response_model=list[GraderAccuracyOut])
async def get_global_accuracy(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> list[GraderAccuracyOut]:
    accuracy = await measure_accuracy(session)
    return [GraderAccuracyOut.model_validate(a) for a in accuracy]
