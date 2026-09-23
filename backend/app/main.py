from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.auth import router as auth_router
from app.api.v1.grading import router as grading_router
from app.api.v1.guides import router as guides_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="Backend API", debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Same shape as FastAPI's default 422, minus "input" so submitted values are never echoed.
    errors = [{k: v for k, v in error.items() if k != "input"} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


app.include_router(auth_router, prefix="/api/v1")
app.include_router(grading_router, prefix="/api/v1")
app.include_router(guides_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
