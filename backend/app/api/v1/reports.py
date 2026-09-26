from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.performance_report import PerformanceReport
from app.models.user import User
from app.repositories.report_repo import (
    HasDisputesError,
    ReportError,
    ReportRepository,
)
from app.schemas.report import ReportCreate, ReportOut, ReportWithDisputesOut
from app.services.auth_service import get_current_admin, get_current_user
from app.services.grading.scheme_store import get_visible_record, load_repo_schemes

router = APIRouter(prefix="/reports", tags=["reports"])


async def _scheme_visible(session: AsyncSession, scheme_version: str, user: User) -> bool:
    return (
        scheme_version in load_repo_schemes()
        or await get_visible_record(session, scheme_version, user.id) is not None
    )


async def _require_visible_scheme(session: AsyncSession, scheme_version: str, user: User) -> None:
    if not await _scheme_visible(session, scheme_version, user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Mark scheme {scheme_version!r} not found"
        )


def _with_disputes(report: PerformanceReport, disputes: list[PerformanceReport]) -> ReportWithDisputesOut:
    return ReportWithDisputesOut(
        **ReportOut.from_model(report).model_dump(),
        disputed_by=[ReportOut.from_model(d) for d in disputes],
    )


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ReportOut:
    await _require_visible_scheme(session, payload.mark_scheme_version, user)
    try:
        report = await ReportRepository(session).create(
            author=user,
            mark_scheme_version=payload.mark_scheme_version,
            disputes_id=payload.disputes_id,
            scripts_tested=payload.scripts_tested,
            questions_judged=payload.questions_judged,
            correct_decisions=payload.correct_decisions,
            paper_type=payload.paper_type,
            level=payload.level,
            tester_context=payload.tester_context,
            method_notes=payload.method_notes,
        )
    except ReportError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    await session.commit()
    return ReportOut.from_model(report)


@router.get("/scheme/{scheme_version}", response_model=list[ReportWithDisputesOut])
async def list_scheme_reports(
    scheme_version: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ReportWithDisputesOut]:
    """Top-level reports newest first, each with the disputes against it nested, also newest first."""
    await _require_visible_scheme(session, scheme_version, user)
    reports = await ReportRepository(session).list_for_scheme(scheme_version)
    disputes: dict[UUID, list[PerformanceReport]] = {}
    for report in reports:
        if report.disputes_id is not None:
            disputes.setdefault(report.disputes_id, []).append(report)
    return [_with_disputes(r, disputes.get(r.id, [])) for r in reports if r.disputes_id is None]


@router.get("/{public_ref}", response_model=ReportWithDisputesOut)
async def get_report(
    public_ref: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ReportWithDisputesOut:
    repo = ReportRepository(session)
    report = await repo.get_by_public_ref(public_ref)
    if report is None or not await _scheme_visible(session, report.mark_scheme_version, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return _with_disputes(report, await repo.list_disputes_of(report.id))


@router.delete("/{public_ref}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    public_ref: str,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Admins only. Reports aren't moderated; this exists for removing, e.g., identifying data."""
    repo = ReportRepository(session)
    report = await repo.get_by_public_ref(public_ref)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    try:
        await repo.delete(report)
    except HasDisputesError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
