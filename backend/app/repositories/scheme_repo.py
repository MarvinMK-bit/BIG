from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mark_scheme import MarkSchemeRecord, MarkSchemeSource


def split_scheme_version(scheme_version: str) -> tuple[str, str] | None:
    """Split "name@version" at the last "@"; None if either side is empty."""
    name, sep, version = scheme_version.rpartition("@")
    if not sep or not name or not version:
        return None
    return name, version


class MarkSchemeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        owner_id: UUID,
        name: str,
        version: str,
        subject: str | None,
        description: str | None,
        yaml_content: str,
        question_count: int,
        source: MarkSchemeSource = MarkSchemeSource.MANUAL,
    ) -> MarkSchemeRecord:
        record = MarkSchemeRecord(
            owner_id=owner_id,
            name=name,
            version=version,
            subject=subject,
            description=description,
            yaml_content=yaml_content,
            question_count=question_count,
            source=source,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_id(self, scheme_id: UUID) -> MarkSchemeRecord | None:
        result = await self.session.execute(
            select(MarkSchemeRecord).where(MarkSchemeRecord.id == scheme_id)
        )
        return result.scalar_one_or_none()

    async def get_by_version(self, scheme_version: str) -> MarkSchemeRecord | None:
        """Look up a scheme by "name@version", regardless of visibility."""
        parts = split_scheme_version(scheme_version)
        if parts is None:
            return None
        name, version = parts
        result = await self.session.execute(
            select(MarkSchemeRecord)
            .options(selectinload(MarkSchemeRecord.owner))
            .where(MarkSchemeRecord.name == name, MarkSchemeRecord.version == version)
        )
        return result.scalar_one_or_none()

    async def list_all(self, viewer_id: UUID) -> list[MarkSchemeRecord]:
        """Public schemes plus the viewer's own, oldest first."""
        result = await self.session.execute(
            select(MarkSchemeRecord)
            .options(selectinload(MarkSchemeRecord.owner))
            .where(or_(MarkSchemeRecord.is_public, MarkSchemeRecord.owner_id == viewer_id))
            .order_by(MarkSchemeRecord.created_at, MarkSchemeRecord.name, MarkSchemeRecord.version)
        )
        return list(result.scalars().all())

    async def list_everything(self) -> list[MarkSchemeRecord]:
        """Every scheme regardless of visibility, oldest first. For admin tooling only."""
        result = await self.session.execute(
            select(MarkSchemeRecord)
            .options(selectinload(MarkSchemeRecord.owner))
            .order_by(MarkSchemeRecord.created_at, MarkSchemeRecord.name, MarkSchemeRecord.version)
        )
        return list(result.scalars().all())

    async def delete_own(self, scheme_id: UUID, owner_id: UUID) -> bool:
        """Delete the scheme if owner_id owns it. Returns whether anything was deleted."""
        record = await self.get_by_id(scheme_id)
        if record is None or record.owner_id != owner_id:
            return False
        await self.delete(record)
        return True

    async def delete(self, record: MarkSchemeRecord) -> None:
        """Unconditional delete, for admins; ownership checks are the caller's job."""
        await self.session.delete(record)
        await self.session.flush()
