import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Tutor
from app.schemas import TutorCreate, TutorRead, TutorUpdate
from app.security import require_api_token


router = APIRouter(
    prefix="/tutors",
    tags=["tutors"],
    dependencies=[Depends(require_api_token)],
)


DbSession = Annotated[Session, Depends(get_db)]


def get_tutor_or_404(db: Session, tutor_id: uuid.UUID) -> Tutor:
    tutor = db.scalar(
        select(Tutor).options(selectinload(Tutor.sources)).where(Tutor.id == tutor_id)
    )
    if tutor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found")
    return tutor


@router.post("", response_model=TutorRead, status_code=status.HTTP_201_CREATED)
def create_tutor(tutor_in: TutorCreate, db: DbSession) -> Tutor:
    tutor = Tutor(**tutor_in.model_dump())
    db.add(tutor)
    db.commit()
    db.refresh(tutor)
    return tutor


@router.get("", response_model=list[TutorRead])
def list_tutors(
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Tutor]:
    statement = (
        select(Tutor)
        .options(selectinload(Tutor.sources))
        .order_by(Tutor.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


@router.get("/{tutor_id}", response_model=TutorRead)
def get_tutor(tutor_id: uuid.UUID, db: DbSession) -> Tutor:
    return get_tutor_or_404(db, tutor_id)


@router.patch("/{tutor_id}", response_model=TutorRead)
def update_tutor(tutor_id: uuid.UUID, tutor_in: TutorUpdate, db: DbSession) -> Tutor:
    tutor = get_tutor_or_404(db, tutor_id)
    for field, value in tutor_in.model_dump(exclude_unset=True).items():
        setattr(tutor, field, value)

    db.commit()
    db.refresh(tutor)
    return tutor


@router.put("/{tutor_id}", response_model=TutorRead)
def replace_tutor(tutor_id: uuid.UUID, tutor_in: TutorCreate, db: DbSession) -> Tutor:
    tutor = get_tutor_or_404(db, tutor_id)
    for field, value in tutor_in.model_dump().items():
        setattr(tutor, field, value)

    db.commit()
    db.refresh(tutor)
    return tutor


@router.delete("/{tutor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tutor(tutor_id: uuid.UUID, db: DbSession) -> Response:
    tutor = get_tutor_or_404(db, tutor_id)
    db.delete(tutor)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
