from pydantic import BaseModel
import datetime

class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    owner_id: int
    room_id: int

class Message(MessageBase):
    id: int
    owner_id: int
    room_id: int
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
    email: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    experience_points: int
    level: int
    character_state: str
    messages: list[Message] = []

    class Config:
        from_attributes = True

class ChatMessageRequest(BaseModel):
    user_id: int
    message: str

class ChatMessageResponse(BaseModel):
    user_id: int
    character_state: str
    experience_points: int
    is_harmful: bool
    quiz: dict | None = None # 유해 단어가 있을 경우 퀴즈 데이터