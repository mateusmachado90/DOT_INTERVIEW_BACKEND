import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import TutorStatus


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


class TutorRead(TutorBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
