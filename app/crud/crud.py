
from sqlalchemy.orm import Session
import models
import schemas

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate):
    fake_hashed_password = user.password + "notreallyhashed"
    db_user = models.User(email=user.email, hashed_password=fake_hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_rooms(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Room).offset(skip).limit(limit).all()

def create_room(db: Session, room: schemas.RoomCreate):
    db_room = models.Room(name=room.name)
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room

def get_messages(db: Session, room_id: int, offset: int = 0, limit: int = 100):
    return db.query(models.Message).filter(models.Message.room_id == room_id).offset(offset).limit(limit).all()

def create_message(db: Session, message: schemas.MessageCreate):
    db_message = models.Message(**message.dict())
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

def update_user_status(db: Session, user_id: int, xp: int, state: str):
    db_user = get_user(db, user_id)
    if db_user:
        db_user.experience_points = xp
        db_user.character_state = state
        # 레벨업 로직은 필요하다면 여기에 추가
        db.commit()
        db.refresh(db_user)
    return db_user
