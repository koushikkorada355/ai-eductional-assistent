from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from uuid import UUID
from jose import JWTError, jwt
from app.db.session import get_db
from app.config import settings
from app.db.models.user import User
from app.db.models.space import Space
from app.db.models.project import Project

# HTTP Bearer instead of OAuth2 password flow
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

def get_owned_space(
    space_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Space:
    space = db.query(Space).filter(Space.id == space_id).first()
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    if space.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this space")
    return space

def get_owned_project(
    space_id: UUID,
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    # Verify space ownership first (ensures data isolation)
    space = db.query(Space).filter(Space.id == space_id).first()
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    if space.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this space")
    project = db.query(Project).filter(Project.id == project_id, Project.space_id == space_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found in this space")
    return project

def get_owned_project_by_id(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    # Flat-route ownership check: project -> parent space -> owner (same pattern as above)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    space = db.query(Space).filter(Space.id == project.space_id).first()
    if not space or space.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    return project

def get_owned_quiz(
    quiz_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Flat-route ownership check: quiz -> project -> parent space -> owner
    from app.db.models.assessment import Quiz

    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    project = db.query(Project).filter(Project.id == quiz.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    space = db.query(Space).filter(Space.id == project.space_id).first()
    if not space or space.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this quiz")
    return quiz