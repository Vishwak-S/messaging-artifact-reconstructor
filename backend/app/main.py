"""
Messaging App Artifact Reconstructor — FastAPI Backend

A digital-forensics analysis platform for reconstructing chat history
from WhatsApp, Telegram, and Signal SQLite databases.

IMPORTANT: This tool is intended for authorized forensic analysis only.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.database.db import init_db
from app.services.evidence_service import clear_analysis_data_keep_cases
from app.api import cases, evidence, databases, conversations, messages, timeline, search, reports, audit

# ── App initialization ────────────────────────────────────────────────────────

app = FastAPI(
    title="Messaging App Artifact Reconstructor",
    description=(
        "A forensic analysis platform for extracting and reconstructing "
        "chat history from WhatsApp, Telegram, and Signal SQLite databases."
    ),
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database initialization ───────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()
    # Each launch is a fresh analysis session by request.  Cases remain so the
    # user can reuse them, but prior files, databases, conversations, reports,
    # and analysis logs do not accumulate across launches.
    clear_analysis_data_keep_cases()


@app.on_event("shutdown")
def shutdown():
    pass

# ── API routes ────────────────────────────────────────────────────────────────

API_PREFIX = "/api"

app.include_router(cases.router, prefix=API_PREFIX)
app.include_router(evidence.router, prefix=API_PREFIX)
app.include_router(databases.router, prefix=API_PREFIX)
app.include_router(conversations.router, prefix=API_PREFIX)
app.include_router(messages.router, prefix=API_PREFIX)
app.include_router(timeline.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)

# ── Dashboard stats endpoint ──────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    from app.database.db import SessionLocal
    from app.models.models import Case, Evidence, ForensicDatabase, Conversation, Message
    db = SessionLocal()
    try:
        return {
            "total_cases": db.query(Case).count(),
            "total_evidence": db.query(Evidence).count(),
            "total_databases": db.query(ForensicDatabase).count(),
            "total_messages": db.query(Message).count(),
            "total_conversations": db.query(Conversation).count(),
            "total_attachments": db.query(Message).filter(Message.has_attachment == True).count(),
            "applications": {
                "WhatsApp": db.query(Message).filter(Message.application == "WhatsApp").count(),
                "Telegram": db.query(Message).filter(Message.application == "Telegram").count(),
                "Signal": db.query(Message).filter(Message.application == "Signal").count(),
            },
        }
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "version": settings.APP_VERSION}
