from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.mark_scheme import MarkSchemeRecord
from app.repositories.scheme_repo import MarkSchemeRepository
from app.services.grading.schemes import MarkScheme, load_all_schemes, parse_scheme


def load_repo_schemes() -> dict[str, MarkScheme]:
    return load_all_schemes(Path(get_settings().MARK_SCHEMES_DIR))


def can_view(record: MarkSchemeRecord, viewer_id: UUID | None) -> bool:
    return record.is_public or (viewer_id is not None and record.owner_id == viewer_id)


async def get_visible_record(
    db: AsyncSession, scheme_version: str, viewer_id: UUID | None
) -> MarkSchemeRecord | None:
    record = await MarkSchemeRepository(db).get_by_version(scheme_version)
    if record is None or not can_view(record, viewer_id):
        return None
    return record


async def resolve_scheme(
    db: AsyncSession, scheme_version: str, viewer_id: UUID
) -> MarkScheme | None:
    """Find a scheme by "name@version": repo files first, then uploaded schemes the viewer can see."""
    scheme = load_repo_schemes().get(scheme_version)
    if scheme is not None:
        return scheme
    record = await get_visible_record(db, scheme_version, viewer_id)
    if record is None:
        return None
    # Validated on upload, so this only fails if validation rules have since tightened
    return parse_scheme(record.yaml_content)
