"""Pydantic schemas for the Subject catalog."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    semester: int
    created_at: datetime
