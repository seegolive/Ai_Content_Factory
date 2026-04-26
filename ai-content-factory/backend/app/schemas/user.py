"""User Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class YoutubeAccountOut(BaseModel):
    id: uuid.UUID
    channel_id: str
    channel_name: Optional[str] = None

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    plan: str
    credits_used: int
    is_active: bool
    created_at: datetime
    youtube_accounts: list[YoutubeAccountOut] = []

    model_config = {"from_attributes": True}
