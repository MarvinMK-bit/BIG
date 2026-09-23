import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.grading_session import GradingSession, GradingStatus
from app.models.question_result import QuestionResult
from app.models.user import User
from app.repositories.grading_repo import GradingSessionRepository
from app.repositories.result_repo import QuestionResultRepository
from app.repositories.scheme_repo import MarkSchemeRepository
from app.schemas.grading import (
    GraderAccuracyOut,
    GradingRunOut,
    GradingSessionOut,
    QuestionResultOut,
    RunComparisonOut,
    SchemeGradeRequest,
    SchemeGradeResponse,
    SchemeOut,
    VerdictRequest,
)
from app.services.auth_service import get_current_admin, get_current_user
from app.services.file_type import detect_mime_type
from app.services.grading import (
    NoQuestionMarkersError,
    grade_with_llm,
    grade_with_scheme,
    run_ocr,
)
from app.services.grading.accuracy import measure_accuracy
from app.services.grading.comparison import RunNotFoundError, compare_runs
from app.services.grading.scheme_store import (
    can_view,
    get_visible_record,
    load_repo_schemes,
    resolve_scheme,
)
from app.services.grading.schemes import parse_scheme
from app.services.storage import get_backend

router = APIRouter(prefix="/grading", tags=["grading"])

UNSUPPORTED_FILE_MESSAGE = (
    "This file isn't a photo or PDF of a script. Please upload a JPEG, PNG, WebP or PDF."
)

MAX_SCHEME_BYTES = 256 * 1024
_SCHEME_SUFFIXES = (".yaml", ".yml")


@router.post("/upload", response_model=GradingSessionOut, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    subject: str | None = Form(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> GradingSession:
    settings = get_settings()
    file_bytes = await file.read()

    # The client-declared content type is untrusted; identify the file from its own bytes.
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

    backend = get_backend(settings.STORAGE_BACKEND)
    stored = await backend.save(
        file_bytes, filename=file.filename or "upload", mime_type=mime_type
    )

    repo = GradingSessionRepository(session)
    grading_session = await repo.create(
        owner_id=user.id,
        original_filename=file.filename or "upload",
        mime_type=mime_type,
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


@router.get("/schemes", response_model=list[SchemeOut])
async def list_schemes(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[SchemeOut]:
    repo_schemes = load_repo_schemes()
    out = [
        SchemeOut(
            scheme_version=scheme.scheme_version,
            name=scheme.name,
            subject=scheme.subject,
            description=scheme.description,
            question_count=len(scheme.questions),
            origin="repo",
        )
        for scheme in repo_schemes.values()
    ]
    for record in await MarkSchemeRepository(session).list_all(user.id):
        # Repo files win when resolving, so a shadowed upload isn't offered
        if record.scheme_version in repo_schemes:
            continue
        out.append(
            SchemeOut(
                scheme_version=record.scheme_version,
                name=record.name,
                subject=record.subject,
                description=record.description,
                question_count=record.question_count,
                origin="uploaded",
                owner_username=record.owner.username,
            )
        )
    return out


@router.post("/schemes", response_model=SchemeOut, status_code=status.HTTP_201_CREATED)
async def upload_scheme(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SchemeOut:
    if not (file.filename or "").lower().endswith(_SCHEME_SUFFIXES):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Mark schemes must be uploaded as a .yaml or .yml file.",
        )

    raw = await file.read(MAX_SCHEME_BYTES + 1)
    if len(raw) > MAX_SCHEME_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Mark scheme files must be at most {MAX_SCHEME_BYTES // 1024}KB.",
        )

    try:
        yaml_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mark scheme file must be UTF-8 text.",
        )

    try:
        scheme = parse_scheme(yaml_text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    conflict = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Mark scheme {scheme.scheme_version!r} already exists",
    )
    repo = MarkSchemeRepository(session)
    if scheme.scheme_version in load_repo_schemes() or await repo.get_by_version(scheme.scheme_version):
        raise conflict

    try:
        record = await repo.create(
            owner_id=user.id,
            name=scheme.name,
            version=scheme.version,
            subject=scheme.subject,
            description=scheme.description,
            yaml_content=yaml_text,
            question_count=len(scheme.questions),
        )
        await session.commit()
    except IntegrityError:
        # Lost a race with a concurrent upload of the same name@version
        await session.rollback()
        raise conflict

    return SchemeOut(
        scheme_version=record.scheme_version,
        name=record.name,
        subject=record.subject,
        description=record.description,
        question_count=record.question_count,
        origin="uploaded",
        owner_username=user.username,
    )


# Deliberately unauthenticated: schemes are public and must be readable by anyone.
@router.get("/schemes/{scheme_version}/yaml", response_class=PlainTextResponse)
async def get_scheme_yaml(
    scheme_version: str,
    session: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    repo_scheme = load_repo_schemes().get(scheme_version)
    if repo_scheme is not None and repo_scheme.path is not None:
        return PlainTextResponse(repo_scheme.path.read_text(encoding="utf-8"))

    record = await get_visible_record(session, scheme_version, viewer_id=None)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Mark scheme {scheme_version!r} not found"
        )
    return PlainTextResponse(record.yaml_content)


@router.delete("/schemes/{scheme_version}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheme(
    scheme_version: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    repo = MarkSchemeRepository(session)
    record = await repo.get_by_version(scheme_version)
    if record is None or not (can_view(record, user.id) or user.is_admin):
        if scheme_version in load_repo_schemes():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Mark schemes stored as repo files can't be deleted here",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Mark scheme {scheme_version!r} not found"
        )

    if user.is_admin:
        await repo.delete(record)
    elif not await repo.delete_own(record.id, user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the scheme's owner or an admin can delete it",
        )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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

    scheme = await resolve_scheme(session, body.scheme_version, user.id)
    if scheme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mark scheme {body.scheme_version!r} not found",
        )

    grading_run_id = uuid.uuid4()
    try:
        results = await grade_with_scheme(
            grading_session, scheme, session, grading_run_id, unnumbered_mode=body.unnumbered_mode
        )
    except NoQuestionMarkersError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
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


@router.get("/sessions/{session_id}/runs/{run_id}/results", response_model=list[QuestionResultOut])
async def get_run_results(
    session_id: UUID,
    run_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[QuestionResult]:
    grading_session = await GradingSessionRepository(session).get_for_owner(session_id, user.id)
    if grading_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading session not found")

    rows = await QuestionResultRepository(session).list_for_run(run_id, user.id)
    results = [r for r in rows if r.session_id == session_id]
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grading run not found")

    return results


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
