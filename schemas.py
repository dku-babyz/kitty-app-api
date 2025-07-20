
from pydantic import BaseModel, Field
import datetime
from typing import Optional, List, Dict, Any

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
    character_state: str
    harmful_chat_count: int
    messages: list[Message] = []

    class Config:
        from_attributes = True

class RiskScoreRequest(BaseModel):
    risk_score: int

class StoryGenerationResponse(BaseModel):
    final_story: str
    final_image_path: str

# New schemas for Quiz and Report AI Server
class ProcessChatDataRequest(BaseModel):
    user_id: int
    original_text: str
    processed_text: str

class QuizResult(BaseModel):
    bad_word: str
    reason: str
    quiz: str

class ReportResult(BaseModel):
    summary: str
    advice: str

class ProcessChatDataResponse(BaseModel):
    message: str
    quiz_results: List[QuizResult] = Field(default_factory=list)
    report_results: Optional[ReportResult] = None
