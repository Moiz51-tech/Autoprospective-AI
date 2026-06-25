from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os

from api.routes import campaigns, leads
from utils.logger import get_logger

log = get_logger("main")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("logs", exist_ok=True)
    log.info("🤖 AutoProspect AI starting up...")
    yield
    log.info("AutoProspect AI shutting down.")


app = FastAPI(
    title="AutoProspect AI",
    description="AI-powered B2B lead generation & outreach automation",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — lock down in production to your actual frontend domain
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# Global error handler — never expose raw tracebacks to clients
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check logs."},
    )


# Register routers
app.include_router(campaigns.router, prefix="/api")
app.include_router(leads.router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "AutoProspect AI",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check for Railway / load balancers."""
    try:
        from tools.supabase_client import supabase
        # Quick DB connectivity check
        supabase.table("campaigns").select("id").limit(1).execute()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"

    return {
        "status": "ok",
        "database": db_status,
    }
