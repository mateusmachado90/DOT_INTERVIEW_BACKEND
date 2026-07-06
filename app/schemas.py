import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import TutorSourceType, TutorStatus


class TutorBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: TutorStatus = TutorStatus.ACTIVE
    system_prompt: str = Field(min_length=1)


class TutorCreate(TutorBase):
    pass


class TutorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: TutorStatus | None = None
    system_prompt: str | None = Field(default=None, min_length=1)


class TutorSourceRead(BaseModel):
    id: uuid.UUID
    name: str
    type: TutorSourceType
    location: str
    enabled: bool
    last_sync_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TutorRead(TutorBase):
    id: uuid.UUID
    sources: list[TutorSourceRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
