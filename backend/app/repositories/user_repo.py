from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username.lower()))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        username: str,
        password_hash: str,
        email: str | None = None,
        display_name: str | None = None,
    ) -> User:
        user = User(
            username=username.lower(),
            password_hash=password_hash,
            email=email.lower() if email is not None else None,
            display_name=display_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def set_blink_address(self, user: User, address: str | None) -> User:
        user.blink_address = address
        await self.session.flush()
        return user

    async def set_attribution_opt_in(self, user: User, opt_in: bool) -> User:
        user.attribution_opt_in = opt_in
        await self.session.flush()
        return user
