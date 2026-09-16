from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from loguru import logger

from app.db.session import get_db
from app.db.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut
from app.api.deps import get_current_user, get_owned_space, get_owned_project
from app.db.models.user import User
from app.db.models.space import Space

router = APIRouter()

@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    space_id: UUID,
    project_in: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Verify ownership via get_owned_space logic inline to avoid duplicate Depends parsing for POST /
    space = db.query(Space).filter(Space.id == space_id).first()
    if not space:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Space not found")
    if space.user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized")
    logger.info(f"User {current_user.id} creating project {project_in.name} in space {space_id}")
    project = Project(
        space_id=space_id,
        name=project_in.name,
        description=project_in.description,
        learning_goal=project_in.learning_goal,
        overall_progress=0.0,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.success(f"Project {project.id} created in space {space_id}")
    return project

@router.get("/", response_model=List[ProjectOut])
def list_projects(
    space_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    space = db.query(Space).filter(Space.id == space_id).first()
    if not space:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Space not found")
    if space.user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized")
    projects = db.query(Project).filter(Project.space_id == space_id).order_by(Project.created_at.desc()).all()
    return projects

@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project: Project = Depends(get_owned_project),
):
    return project

@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_in: ProjectUpdate,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    update_data = project_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    logger.info(f"Project {project.id} updated")
    return project

@router.patch("/{project_id}", response_model=ProjectOut)
def patch_project(
    project_in: ProjectUpdate,
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    return update_project(project_in, project, db)

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project: Project = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    logger.warning(f"Deleting project {project.id}")
    db.delete(project)
    db.commit()
    return None
