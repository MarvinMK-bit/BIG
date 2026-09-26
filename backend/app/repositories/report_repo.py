from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.performance_report import PerformanceReport, performance_report_ref_seq
from app.models.user import User
from app.repositories.feedback_repo import ref_number, suffix_letters
from app.repositories.scheme_repo import MarkSchemeRepository
from app.services.grading.scheme_store import load_repo_schemes


class ReportError(ValueError):
    """A request the report rules forbid; the message is safe to show to the user."""


class DisputeTargetError(ReportError):
    pass


class HasDisputesError(ReportError):
    pass


def suffix_index(letters: str) -> int:
    """Inverse of suffix_letters: "a" -> 0, "z" -> 25, "aa" -> 26."""
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("a") + 1)
    return index - 1


def _select() -> Select[tuple[PerformanceReport]]:
    # The disputed report comes along for its public_ref; the author says who made the claim
    return select(PerformanceReport).options(
        selectinload(PerformanceReport.author),
        selectinload(PerformanceReport.disputes),
    )


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def is_scheme_author(self, author: User, mark_scheme_version: str) -> bool:
        """Whether author wrote the scheme. Repo schemes have no owner row; admins stand in for it."""
        if mark_scheme_version in load_repo_schemes():
            return author.is_admin
        record = await MarkSchemeRepository(self.session).get_by_version(mark_scheme_version)
        return record is not None and record.owner_id == author.id

    async def create(
        self,
        *,
        author: User,
        mark_scheme_version: str,
        scripts_tested: int,
        questions_judged: int,
        correct_decisions: int,
        paper_type: str,
        level: str | None = None,
        tester_context: str | None = None,
        method_notes: str | None = None,
        disputes_id: UUID | None = None,
    ) -> PerformanceReport:
        if not 0 <= correct_decisions <= questions_judged:
            raise ReportError("Correct decisions must be between 0 and the number of questions judged.")

        if disputes_id is None:
            number = await self.session.scalar(select(performance_report_ref_seq.next_value()))
            public_ref = f"R{number:04d}a"
        else:
            # Locking the target serialises sibling disputes, so two can't take the same letter
            target = await self.get_by_id(disputes_id, for_update=True)
            if target is None:
                raise DisputeTargetError("The report being disputed does not exist.")
            if target.disputes_id is not None:
                raise DisputeTargetError(
                    f"Report {target.public_ref} is itself a dispute; dispute "
                    f"{ref_number(target.public_ref)}a instead."
                )
            if target.mark_scheme_version != mark_scheme_version:
                raise DisputeTargetError(
                    f"Report {target.public_ref} is about {target.mark_scheme_version}; a dispute "
                    f"must name the same scheme version, not {mark_scheme_version}."
                )
            sibling_refs = await self.session.scalars(
                select(PerformanceReport.public_ref).where(PerformanceReport.disputes_id == target.id)
            )
            # The highest letter in use, not the count, so an admin deletion can't cause a reuse
            last = max(
                (suffix_index(ref.removeprefix(ref_number(ref))) for ref in sibling_refs),
                default=0,
            )
            public_ref = ref_number(target.public_ref) + suffix_letters(last + 1)

        report = PerformanceReport(
            public_ref=public_ref,
            author_id=author.id,
            mark_scheme_version=mark_scheme_version,
            disputes_id=disputes_id,
            scripts_tested=scripts_tested,
            questions_judged=questions_judged,
            correct_decisions=correct_decisions,
            paper_type=paper_type,
            level=level,
            tester_context=tester_context,
            method_notes=method_notes,
            is_author_self_report=await self.is_scheme_author(author, mark_scheme_version),
        )
        self.session.add(report)
        await self.session.flush()
        # Reload so the author and disputes relationships are populated for the caller
        created = await self.get_by_id(report.id)
        assert created is not None
        return created

    async def get_by_id(self, report_id: UUID, *, for_update: bool = False) -> PerformanceReport | None:
        query = _select().where(PerformanceReport.id == report_id).execution_options(populate_existing=True)
        if for_update:
            query = query.with_for_update(of=PerformanceReport)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_public_ref(self, public_ref: str) -> PerformanceReport | None:
        result = await self.session.execute(_select().where(PerformanceReport.public_ref == public_ref))
        return result.scalar_one_or_none()

    async def list_for_scheme(self, mark_scheme_version: str) -> list[PerformanceReport]:
        """Every report on the scheme, top-level and disputes alike, newest first."""
        result = await self.session.execute(
            _select()
            .where(PerformanceReport.mark_scheme_version == mark_scheme_version)
            .order_by(PerformanceReport.created_at.desc(), PerformanceReport.public_ref.desc())
        )
        return list(result.scalars().all())

    async def list_disputes_of(self, report_id: UUID) -> list[PerformanceReport]:
        result = await self.session.execute(
            _select()
            .where(PerformanceReport.disputes_id == report_id)
            .order_by(PerformanceReport.created_at.desc(), PerformanceReport.public_ref.desc())
        )
        return list(result.scalars().all())

    async def delete(self, report: PerformanceReport) -> None:
        """Unconditional delete, for admins. A report others dispute must lose its disputes first,
        so no dispute is left pointing at nothing."""
        has_disputes = await self.session.scalar(
            select(PerformanceReport.id).where(PerformanceReport.disputes_id == report.id).limit(1)
        )
        if has_disputes is not None:
            raise HasDisputesError(
                f"Report {report.public_ref} has disputes; delete those first."
            )
        await self.session.delete(report)
        await self.session.flush()
