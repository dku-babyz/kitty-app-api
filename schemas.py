
from pydantic import BaseModel
import datetime
from typing import Optional

class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    owner_id: int
    room_id: int
    character_state: str
    experience_points: int
    is_harmful: bool

class Message(MessageBase):
    id: int
    owner_id: int
    room_id: int
    character_state: str
    experience_points: int
    is_harmful: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class RoomBase(BaseModel):
    name: str

class RoomCreate(RoomBase):
    pass

class Room(RoomBase):
    id: int
    messages: list[Message] = []

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str
    phone_number: str
    email: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    experience_points: int
    level: int
    messages: list[Message] = []

    class Config:
        from_attributes = True
