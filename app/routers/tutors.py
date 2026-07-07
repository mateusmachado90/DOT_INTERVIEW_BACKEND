import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.conversation_agent import (
    ConversationAgentError,
    ConversationAgentProviderError,
    ConversationAgentTimeoutError,
    run_tutor_conversation,
)
from app.db import get_db
from app.models import ChatMessage, ChatMessageRole, ChatSession, Tutor
from app.schemas import TutorChatRequest, TutorChatResponse, TutorCreate, TutorRead, TutorUpdate
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


@router.post("/{tutor_id}/chat", response_model=TutorChatResponse)
def chat_with_tutor(
    tutor_id: uuid.UUID,
    chat_in: TutorChatRequest,
    db: DbSession,
) -> TutorChatResponse:
    tutor = get_tutor_or_404(db, tutor_id)
    chat_session = get_or_create_chat_session(db, tutor, chat_in.session_token)
    history = list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at.asc())
        )
    )

    try:
        answer = run_tutor_conversation(
            tutor=tutor,
            history=history,
            user_message=chat_in.message,
        )
    except ConversationAgentTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=exc.user_message,
        ) from exc
    except ConversationAgentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=exc.user_message,
        ) from exc
    except ConversationAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.user_message,
        ) from exc

    db.add_all(
        [
            ChatMessage(
                session=chat_session,
                role=ChatMessageRole.USER,
                content=chat_in.message,
            ),
            ChatMessage(
                session=chat_session,
                role=ChatMessageRole.ASSISTANT,
                content=answer,
            ),
        ]
    )
    db.commit()

    return TutorChatResponse(
        session_id=chat_session.id,
        session_token=chat_session.session_token,
        answer=answer,
    )


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


def get_or_create_chat_session(
    db: Session,
    tutor: Tutor,
    session_token: str | None,
) -> ChatSession:
    if session_token:
        chat_session = db.scalar(
            select(ChatSession).where(ChatSession.session_token == session_token)
        )
        if chat_session is None or chat_session.tutor_id != tutor.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found for tutor",
            )
        return chat_session

    # Token opaco de 32 caracteres hexadecimais minusculos, sem hifens, facil de trafegar em JSON.
    chat_session = ChatSession(tutor=tutor, session_token=uuid.uuid4().hex)
    db.add(chat_session)
    db.flush()
    return chat_session
