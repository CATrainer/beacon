"""Auth request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str

    model_config = {"from_attributes": True}
