from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import AdminUserOut, UserActiveUpdate
from app.services.auth_service import get_current_admin

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[AdminUserOut])
async def list_users(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> list[User]:
    return await UserRepository(session).list_all()


@router.patch("/{user_id}", response_model=AdminUserOut)
async def set_user_active(
    user_id: UUID,
    body: UserActiveUpdate,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Block or unblock an account. A blocked user can't sign in and their existing session stops
    working; everything they contributed is kept.
    """
    if user_id == admin.id and not body.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You can't block your own account"
        )
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await repo.set_active(user, body.is_active)
    await session.commit()
    return user
