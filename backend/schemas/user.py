"""Pydantic schemas for the User resource.

Response models intentionally exclude password_hash and any internal
storage fields (vision.txt: schemas define exactly what data may LEAVE the API).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    name: str


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    is_active: bool
    created_at: datetime
