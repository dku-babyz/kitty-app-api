
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True)
    phone_number = Column(String(255), unique=True, index=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    experience_points = Column(Integer, default=0)
    level = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    character_state = Column(String(255), default="smiling")
    harmful_chat_count = Column(Integer, default=0)

    messages = relationship("Message", back_populates="owner")

class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)

    messages = relationship("Message", back_populates="room")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String(255))
    character_state = Column(String(255), default="smiling")
    experience_points = Column(Integer, default=0)
    is_harmful = Column(Integer, default=1)
    owner_id = Column(Integer, ForeignKey("users.id"))
    room_id = Column(Integer, ForeignKey("rooms.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="messages")
    room = relationship("Room", back_populates="messages")
