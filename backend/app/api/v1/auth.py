from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.access_request_repo import AccessRequestRepository
from app.repositories.user_repo import UserRepository
from app.schemas.access_request import AccessRequestAccepted, AccessRequestCreate
from app.schemas.user import Token, UserCreate, UserOut, UserUpdate
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
async def auth_config() -> dict[str, bool]:
    return {"registration_open": get_settings().ALLOW_REGISTRATION}


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: AsyncSession = Depends(get_db)) -> Token:
    if not get_settings().ALLOW_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Registration is closed on this instance. BIG is open source — "
                "see the repository to run your own."
            ),
        )

    repo = UserRepository(session)

    if await repo.get_by_username(payload.username) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    if payload.email is not None and await repo.get_by_email(payload.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already taken")

    user = await repo.create(
        username=payload.username,
        password_hash=hash_password(payload.password),
        email=payload.email,
        display_name=payload.display_name,
    )
    await session.commit()

    return Token(access_token=create_access_token(str(user.id)))


REQUEST_RECEIVED = (
    "Thank you — your request has been received. Requests are reviewed by hand; if yours is "
    "approved, you will be contacted on the email address or phone number you gave, and can then "
    "sign in with the username and password you chose."
)


@router.post(
    "/request-access", response_model=AccessRequestAccepted, status_code=status.HTTP_202_ACCEPTED
)
async def request_access(
    payload: AccessRequestCreate, session: AsyncSession = Depends(get_db)
) -> AccessRequestAccepted:
    """Ask for an account. Public, and the only way in while ALLOW_REGISTRATION is false.

    The response is the same whether or not a request was recorded, so this can't be used to
    discover which usernames exist.
    """
    # Hashed before any lookup, so a taken username takes as long to answer as a free one
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    users = UserRepository(session)
    requests = AccessRequestRepository(session)
    taken = (
        await users.get_by_username(payload.username) is not None
        or await requests.get_by_username(payload.username) is not None
        # users.email is unique, so the account could never be created; they already have one
        or (payload.email is not None and await users.get_by_email(payload.email) is not None)
    )
    if not taken:
        try:
            await requests.create(
                username=payload.username,
                password_hash=password_hash,
                about=payload.about,
                email=payload.email,
                phone=payload.phone,
                display_name=payload.display_name,
            )
            await session.commit()
        except IntegrityError:
            # A simultaneous request for the same username got there first
            await session.rollback()

    return AccessRequestAccepted(message=REQUEST_RECEIVED)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> Token:
    repo = UserRepository(session)
    user = await repo.get_by_username(form_data.username)

    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Only said once the password is right, so it reveals nothing to someone guessing
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account has been blocked."
        )

    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
async def read_current_user(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_current_user(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    repo = UserRepository(session)
    if "blink_address" in payload.model_fields_set:
        await repo.set_blink_address(user, payload.blink_address)
    if "attribution_opt_in" in payload.model_fields_set:
        if payload.attribution_opt_in is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="attribution_opt_in must be true or false",
            )
        await repo.set_attribution_opt_in(user, payload.attribution_opt_in)
    await session.commit()
    return user
