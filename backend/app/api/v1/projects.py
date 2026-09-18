from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from loguru import logger

from app.db.session import get_db
from app.db.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut
from app.api.deps import get_current_user, get_owned_space, get_owned_project
from app.db.models.user import User
from app.db.models.space import Space
from app.services.event_service import emit_event, PROJECT_CREATED
from app.utils.pagination import MAX_PAGE_SIZE, PageOut, paginate_query, page_envelope

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
    emit_event(db, type=PROJECT_CREATED, user_id=current_user.id, project_id=project.id,
               text=f"Project '{project.name}' created",
               event_key=f"project:{project.id}")
    logger.success(f"Project {project.id} created in space {space_id}")
    return project

@router.get("/", response_model=PageOut)
def list_projects(
    space_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE, description="Rows per page"),
):
    space = db.query(Space).filter(Space.id == space_id).first()
    if not space:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Space not found")
    if space.user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized")
    projects, total, page, page_size = paginate_query(
        db.query(Project).filter(Project.space_id == space_id).order_by(Project.created_at.desc()),
        page, page_size,
    )
    return page_envelope([ProjectOut.model_validate(p) for p in projects], total, page, page_size)

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
