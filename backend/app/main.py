from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .database import engine, Base
from .api import endpoints
from .limiter import limiter
import os
import logging
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from pathlib import Path

load_dotenv()

# A5: Centralized logging — level from LOG_LEVEL env var, defaults to INFO
_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Schema lifecycle managed by Alembic
# Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the NLP grading model synchronously at startup so it's instantly ready."""
    # Loading sentence-transformer weights can take several minutes the first
    # time. Keep the local web app responsive and load it only when grading is
    # requested (set PRELOAD_NLP_MODEL=true to restore eager loading).
    if os.getenv("PRELOAD_NLP_MODEL", "false").lower() != "true":
        yield
        return

    try:
        from .nlp_grading_service import get_grading_model, is_nlp_model_available
        if is_nlp_model_available():
            logger.info("Pre-loading NLP Grading Model at startup (synchronous)...")
            get_grading_model()
            logger.info("NLP Grading Model pre-loaded successfully!")
        else:
            logger.warning("NLP model files not found on disk — skipping pre-load.")
    except Exception as e:
        logger.error(f"Failed to pre-load NLP model: {e}")

    yield
    # Shutdown logic if any can go here

app = FastAPI(title="AI-Paper Checking System", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# H3: Read allowed origins from env (comma-separated), restrict methods/headers.
# The frontend authenticates with a Basic Authorization header and sends
# credentials:'omit', so cookie credentials are not needed → allow_credentials=False.
_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:3000")
origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

API_PREFIX = os.getenv("API_PREFIX", "/api")

# --- Authentication ---
# C3: No hardcoded password defaults. App refuses to start if ADMIN_PASSWORD is unset.
security = HTTPBasic()
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError(
        "ADMIN_PASSWORD environment variable is not set. "
        "Add it to backend/.env, e.g.: ADMIN_PASSWORD=your_secure_password_here"
    )

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

# Apply the dependency to all endpoints
app.include_router(endpoints.router, prefix=API_PREFIX, dependencies=[Depends(verify_credentials)])

# H8 — root endpoint now behind auth too
@app.get("/")
def read_root():
    index_file = Path(__file__).resolve().parents[2] / "frontend" / "build" / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"message": "AI-Paper Checking System API is running"}

# Serve static assets when they exist and otherwise return React's entry point.
# This is essential for BrowserRouter: refreshing /dashboard or /keys must load
# the app rather than producing a backend 404 response.
_frontend_build = Path(__file__).resolve().parents[2] / "frontend" / "build"

@app.get("/{frontend_path:path}", include_in_schema=False)
def serve_frontend(frontend_path: str):
    if not _frontend_build.is_dir():
        return {"message": "AI-Paper Checking System API is running"}

    requested_file = (_frontend_build / frontend_path).resolve()
    if requested_file.is_file() and _frontend_build.resolve() in requested_file.parents:
        return FileResponse(requested_file)
    return FileResponse(_frontend_build / "index.html")
