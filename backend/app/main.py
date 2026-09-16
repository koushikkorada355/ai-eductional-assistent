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
    yield
    logger.info("Shutting down backend...")

# 3. Initialize FastAPI
app = FastAPI(title="AI Study Companion Backend", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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

@app.get("/health")
async def health_check():
    return {"status": "healthy"}