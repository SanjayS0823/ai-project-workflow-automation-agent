"""FastAPI application entrypoint for the AI Project & Workflow Automation Agent."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .api.projects import router as projects_router
from .api.tasks import router as tasks_router
from .database import init_db

from dotenv import load_dotenv

load_dotenv()
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database when the application starts."""
    init_db()
    yield


def _validation_field(errors) -> str:
    """Extract the field name from the first validation error."""
    for error in errors:
        parts = [
            str(part)
            for part in error.get("loc", ())
            if part not in ("body", "query", "path", "header")
        ]
        if parts:
            return ".".join(parts)
    return ""


def _friendly_validation_detail(errors) -> str:
    """Turn pydantic validation errors into one human-readable message."""
    if not errors:
        return "Invalid request."
    first = errors[0]
    error_type = first.get("type", "")
    msg = first.get("msg", "")
    field = _validation_field(errors)

    if error_type == "missing":
        text = f"{field or 'A required field'} is required."
    elif error_type in {"string_too_short", "too_short"}:
        text = f"{field or 'This field'} is too short."
    elif error_type in {"string_too_long", "too_long"}:
        text = f"{field or 'This field'} is too long."
    elif error_type == "json_invalid":
        text = "The request body is not valid JSON."
    elif error_type in {"enum", "literal_error"}:
        text = f"{field}: {msg}" if field else msg
    elif error_type in {"string_type", "int_type", "bool_type"}:
        text = f"{field or 'This field'} has an invalid type."
    else:
        clean = msg.replace("Value error, ", "").strip()
        text = f"{field}: {clean}" if field and clean else clean or "Invalid request."
    return text


app = FastAPI(
    title="AI Project & Workflow Automation Agent API",
    description="Internal project planning and workflow automation for Zenera Labs.",
    version="0.9.0",
    lifespan=lifespan,
)

app.include_router(projects_router)
app.include_router(tasks_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return friendly 422 messages instead of raw pydantic error lists."""
    return JSONResponse(
        status_code=422, content={"detail": _friendly_validation_detail(exc.errors())}
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Never expose database internals to users."""
    return JSONResponse(
        status_code=503, content={"detail": "Database error. Please try again."}
    )

# Allow the Vite dev server to call this API during development.
# No database, AI, or business logic is implemented yet (Phase 1).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    """Root endpoint with service metadata."""
    return {
        "message": "AI Project & Workflow Automation Agent API",
        "status": "running",
    }


@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}
