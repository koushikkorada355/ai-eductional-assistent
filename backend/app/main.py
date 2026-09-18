from fastapi import FastAPI
from loguru import logger
import sys
from contextlib import asynccontextmanager

# Notice the 'app.' prefix on all imports!
from app.db.session import Base, engine
import app.db.base  # ensure Space/Project models are registered for create_all
from app.api.v1.auth import router as auth_router
from app.api.v1.spaces import router as spaces_router
from app.api.v1.projects import router as projects_router
from app.api.v1.tutor import router as tutor_router
from app.api.v1.materials import router as materials_router
from app.api.v1.quiz import router as quiz_router
from app.api.v1.quiz_flat import router as quiz_flat_router
from app.api.v1.mastery import router as mastery_router
from app.api.v1.assignment import router as assignment_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.admin import router as admin_router

# 1. Configure Logger
logger.remove()
logger.add(
    sys.stdout, 
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True
)

# 2. Lifespan event
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up AI Study Companion Backend...")
    import time
    from sqlalchemy.exc import OperationalError
    for attempt in range(10):
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
            Base.metadata.create_all(bind=engine)
            # Idempotent migrations for existing deployments (create_all only creates new tables)
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS title VARCHAR DEFAULT 'Untitled Assignment'"))
                conn.execute(text("ALTER TABLE assignment_submissions ADD COLUMN IF NOT EXISTS answers JSONB"))
                conn.execute(text("ALTER TABLE assignment_submissions ADD COLUMN IF NOT EXISTS score FLOAT DEFAULT 0.0"))
                conn.execute(text("ALTER TABLE assignment_submissions ADD COLUMN IF NOT EXISTS total INTEGER DEFAULT 0"))
                # Multi-conversation tutor: title + activity tracking per conversation.
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS title VARCHAR(200) DEFAULT 'New conversation'"))
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                conn.execute(text("UPDATE chat_sessions SET title = 'New conversation' WHERE title IS NULL"))
                conn.execute(text("UPDATE chat_sessions SET updated_at = created_at WHERE updated_at IS NULL"))
                # One project can now own many conversations (drop legacy 1:1 unique).
                # NOTE: the legacy column was declared unique=True AND index=True,
                # so SQLAlchemy created a unique *index* named
                # ix_chat_sessions_project_id (not a table constraint) — drop it
                # by index name. The constraint-name variant is kept for safety
                # across deployments.
                conn.execute(text("ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS chat_sessions_project_id_key"))
                conn.execute(text("DROP INDEX IF EXISTS ix_chat_sessions_project_id"))
                # Concept source attribution: which document a concept was
                # first extracted from (NULL = predates tracking / chat-made).
                conn.execute(text("ALTER TABLE concepts ADD COLUMN IF NOT EXISTS document_id UUID"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_concepts_document_id ON concepts (document_id)"))
                conn.execute(text("DO $$ BEGIN ALTER TABLE concepts ADD CONSTRAINT concepts_document_id_fkey FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL; EXCEPTION WHEN duplicate_object THEN NULL; END $$"))
                # Tutor follow-ups: clickable suggested questions per assistant message.
                conn.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS suggested_questions JSONB"))
                # Auth redesign: display name collected at registration.
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(120)"))
                # AI usage metering: tokens / cost / provider per operation.
                conn.execute(text("ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS provider VARCHAR"))
                conn.execute(text("ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER DEFAULT 0"))
                conn.execute(text("ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS completion_tokens INTEGER DEFAULT 0"))
                conn.execute(text("ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS total_tokens INTEGER DEFAULT 0"))
                conn.execute(text("ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS cost_usd FLOAT DEFAULT 0"))
                conn.execute(text("ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS calls INTEGER DEFAULT 1"))
                conn.commit()
            logger.success("Database connected and tables created.")
            break
        except OperationalError as e:
            logger.warning(f"DB not ready (attempt {attempt+1}/10): {e} - retrying in 2s")
            time.sleep(2)
    else:
        logger.error("Failed to connect to DB after 10 attempts, exiting.")
        sys.exit(1)
    try:
        from app.db.checkpointer import setup_checkpointer
        await setup_checkpointer()
    except Exception:
        pass
    try:
        from app.db.session import SessionLocal
        from app.core.admin_seed import ensure_admin_seed
        db = SessionLocal()
        try:
            ensure_admin_seed(db)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Admin seed skipped: {e}")
    yield
    logger.info("Shutting down backend...")

# 3. Initialize FastAPI
app = FastAPI(title="AI Study Companion Backend", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware

from app.config import settings as _cors_settings

_cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if _cors_settings.FRONTEND_URL:
    # Support single URL or comma-separated list.
    _cors_origins += [
        u.strip().rstrip("/")
        for u in _cors_settings.FRONTEND_URL.split(",")
        if u.strip()
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|172\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Include Routers
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(spaces_router, prefix="/api/v1/spaces", tags=["Spaces"])
app.include_router(projects_router, prefix="/api/v1/spaces/{space_id}/projects", tags=["Projects"])
app.include_router(tutor_router, prefix="/api/v1/spaces/{space_id}/projects", tags=["Tutor"])
app.include_router(materials_router, prefix="/api/v1/spaces/{space_id}/projects", tags=["Materials"])
app.include_router(quiz_router, prefix="/api/v1/spaces/{space_id}/projects", tags=["Quiz"])
app.include_router(quiz_flat_router, prefix="/api/v1", tags=["Quiz"])
app.include_router(mastery_router, prefix="/api/v1", tags=["Mastery"])
app.include_router(assignment_router, prefix="/api/v1/spaces/{space_id}/projects", tags=["Assignments"])
app.include_router(analytics_router, prefix="/api/v1", tags=["Analytics"])
app.include_router(admin_router, prefix="/api/v1", tags=["Admin"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}