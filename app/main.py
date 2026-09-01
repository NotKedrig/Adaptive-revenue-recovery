"""
app/main.py — FastAPI application entry point (Phase 1).

Phase 1 exposes the /health endpoint and initializes the core infrastructure
for the AI Revenue Recovery System, including the database schemas,
LangGraph checkpointer, and the local scheduler.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import setup_logging
from app.graph.workflow import build_graph
from app.db.state.db import get_session, create_tables
from app.scheduler.notifier import start_scheduler

# ---------------------------------------------------------------------------
# Logging — initialise before any other code runs
# ---------------------------------------------------------------------------
setup_logging(log_dir=settings.log_dir, log_level=settings.log_level)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ---- startup ----
    logger.info(
        "Application startup",
        extra={
            "llm_provider": settings.llm_provider,
            "llm_model_name": settings.llm_model_name,
            "llm_temperature": settings.llm_temperature,
            "embedding_model_name": settings.embedding_model_name,
            "database_url": settings.database_url.split("@")[-1],  # hide credentials
            "chroma_persist_dir": settings.chroma_persist_dir,
            "log_dir": settings.log_dir,
        },
    )
    
    # Initialize the database schemas
    create_tables()
    
    # Start the local scheduler
    start_scheduler()
    
    yield
    # ---- shutdown ----
    logger.info("Application shutdown")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Revenue Recovery System Local POC",
    description=(
        "Multi-agent AI system for managing and recovering failed payments. "
        "Fully local proof-of-concept."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the long-lived singleton LangGraph compiled workflow
compiled_graph = build_graph()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    summary="Health check",
    description="Returns HTTP 200 with a JSON body confirming the service is running.",
    tags=["meta"],
)
async def health() -> JSONResponse:
    """Liveness probe — always returns 200 when the process is running."""
    logger.debug("Health check requested")
    return JSONResponse(
        content={
            "status": "ok",
            "service": "revenue-recovery",
            "version": "0.1.0",
        }
    )

@app.get("/api/health/status")
async def health_status():
    db_ok = True
    try:
        from sqlalchemy import text
        with get_session() as db:
            db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        db_ok = False
        
    kb_ok = True
    try:
        from app.rag.retriever import _get_chroma_client
        chroma = _get_chroma_client(settings.chroma_persist_dir)
        kb_ok = len(chroma.list_collections()) > 0
    except Exception as e:
        logger.error(f"KB health check failed: {e}")
        kb_ok = False
        
    scheduler_ok = True
    try:
        from app.scheduler.notifier import scheduler
        scheduler_ok = scheduler.running
    except Exception as e:
        logger.error(f"Scheduler health check failed: {e}")
        scheduler_ok = False
        
    gemini_ok = True
    try:
        from app.llm.provider import get_provider
        provider = get_provider()
        if not provider:
            gemini_ok = False
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        gemini_ok = False
        
    return {
        "database": db_ok,
        "knowledge_base": kb_ok,
        "scheduler": scheduler_ok,
        "gemini": gemini_ok
    }
