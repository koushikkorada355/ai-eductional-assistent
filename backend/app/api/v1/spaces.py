from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
from loguru import logger

from app.db.session import get_db
from app.db.models.space import Space
from app.schemas.space import SpaceCreate, SpaceUpdate, SpaceOut
from app.api.deps import get_current_user, get_owned_space
from app.db.models.user import User
from app.services.event_service import emit_event, SPACE_CREATED
from app.utils.pagination import MAX_PAGE_SIZE, PageOut, paginate_query, page_envelope

router = APIRouter()

@router.post("/", response_model=SpaceOut, status_code=status.HTTP_201_CREATED)
def create_space(
    space_in: SpaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(f"User {current_user.id} creating space: {space_in.name}")
    space = Space(
        user_id=current_user.id,
        name=space_in.name,
        description=space_in.description,
    )
    db.add(space)
    db.commit()
    db.refresh(space)
    emit_event(db, type=SPACE_CREATED, user_id=current_user.id,
               text=f"Space '{space.name}' created",
               event_key=f"space:{space.id}")
    logger.success(f"Space created {space.id} for user {current_user.id}")
    return space

@router.get("/", response_model=PageOut)
def list_spaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=50, ge=1, le=MAX_PAGE_SIZE, description="Rows per page"),
):
    # Data Isolation: only return spaces owned by authenticated user
    query = db.query(Space).filter(Space.user_id == current_user.id).order_by(Space.created_at.desc())
    rows, total, page, page_size = paginate_query(query, page, page_size)
    return page_envelope([SpaceOut.model_validate(s) for s in rows], total, page, page_size)

@router.get("/{space_id}", response_model=SpaceOut)
def get_space(
    space: Space = Depends(get_owned_space),
):
    return space

@router.put("/{space_id}", response_model=SpaceOut)
def update_space(
    space_in: SpaceUpdate,
    space: Space = Depends(get_owned_space),
    db: Session = Depends(get_db),
):
    update_data = space_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(space, field, value)
    db.commit()
    db.refresh(space)
    logger.info(f"Space {space.id} updated")
    return space

@router.patch("/{space_id}", response_model=SpaceOut)
def patch_space(
    space_in: SpaceUpdate,
    space: Space = Depends(get_owned_space),
    db: Session = Depends(get_db),
):
    return update_space(space_in, space, db)

@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_space(
    space: Space = Depends(get_owned_space),
    db: Session = Depends(get_db),
):
    logger.warning(f"Deleting space {space.id} (cascade to projects)")
    db.delete(space)
    db.commit()
    return None
