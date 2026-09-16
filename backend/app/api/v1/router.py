from fastapi import APIRouter
from app.api.v1.projects import router as projects_router
from app.api.v1.quiz import router as quiz_router
from app.api.v1.mastery import router as mastery_router
from app.api.v1.assignment import router as assignment_router

api_router = APIRouter()

api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(quiz_router, prefix="/projects", tags=["quizzes"])
api_router.include_router(mastery_router, prefix="/projects", tags=["mastery"])
api_router.include_router(assignment_router, prefix="/projects", tags=["assignments"])
