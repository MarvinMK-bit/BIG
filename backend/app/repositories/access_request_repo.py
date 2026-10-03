from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access_request import AccessRequest, AccessRequestStatus


class AccessRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_username(self, username: str) -> AccessRequest | None:
        result = await self.session.execute(
            select(AccessRequest).where(AccessRequest.username == username.lower())
        )
        return result.scalar_one_or_none()

    async def get_for_update(self, request_id: UUID) -> AccessRequest | None:
        """Locked, so two admins can't both approve the same request."""
        result = await self.session.execute(
            select(AccessRequest).where(AccessRequest.id == request_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[AccessRequest]:
        """Pending requests first, then the rest; newest first within each. For admins only."""
        pending_first = case((AccessRequest.status == AccessRequestStatus.PENDING, 0), else_=1)
        result = await self.session.execute(
            select(AccessRequest).order_by(pending_first, AccessRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        username: str,
        password_hash: str,
        about: str,
        email: str | None = None,
        phone: str | None = None,
        display_name: str | None = None,
    ) -> AccessRequest:
        request = AccessRequest(
            username=username.lower(),
            password_hash=password_hash,
            about=about,
            email=email.lower() if email is not None else None,
            phone=phone,
            display_name=display_name,
        )
        self.session.add(request)
        await self.session.flush()
        return request

    async def set_review(
        self,
        request: AccessRequest,
        status: AccessRequestStatus,
        reviewer_id: UUID,
        note: str | None,
    ) -> AccessRequest:
        if status == AccessRequestStatus.PENDING:
            raise ValueError("An access request can't be reviewed back to pending.")
        request.status = status
        request.reviewed_by_id = reviewer_id
        request.reviewed_at = datetime.now(UTC)
        request.review_note = note
        await self.session.flush()
        return request
