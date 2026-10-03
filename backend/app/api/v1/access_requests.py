from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.access_request import AccessRequest, AccessRequestStatus
from app.models.user import User
from app.repositories.access_request_repo import AccessRequestRepository
from app.repositories.user_repo import UserRepository
from app.schemas.access_request import AccessRequestOut, AccessRequestReview
from app.services.auth_service import get_current_admin

router = APIRouter(prefix="/access-requests", tags=["access-requests"])


@router.get("", response_model=list[AccessRequestOut])
async def list_access_requests(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> list[AccessRequest]:
    """Every request, pending first, newest first within each status."""
    return await AccessRequestRepository(session).list_all()


@router.patch("/{request_id}", response_model=AccessRequestOut)
async def review_access_request(
    request_id: UUID,
    body: AccessRequestReview,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> AccessRequest:
    """Approve (creating the account, active, with the password chosen at request time) or decline."""
    repo = AccessRequestRepository(session)
    request = await repo.get_for_update(request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found")
    if request.status != AccessRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This request has already been {request.status.value}",
        )

    if body.status == AccessRequestStatus.APPROVED:
        users = UserRepository(session)
        # Either could have been taken since the request was made, by an account created another way
        if await users.get_by_username(request.username) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A user named {request.username!r} already exists",
            )
        if request.email is not None and await users.get_by_email(request.email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An existing user already has the email address {request.email}",
            )
        await users.create(
            username=request.username,
            password_hash=request.password_hash,
            email=request.email,
            display_name=request.display_name,
        )

    await repo.set_review(request, body.status, admin.id, body.note or None)
    await session.commit()
    return request
