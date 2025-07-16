
from fastapi import FastAPI, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
import asyncio
import json

import crud
import models
import schemas
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.get("/users/", response_model=list[schemas.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@app.get("/users/{user_id}", response_model=schemas.User)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@app.post("/rooms/", response_model=schemas.Room)
def create_room(room: schemas.RoomCreate, db: Session = Depends(get_db)):
    return crud.create_room(db=db, room=room)

@app.get("/rooms/", response_model=list[schemas.Room])
def read_rooms(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    rooms = crud.get_rooms(db, skip=skip, limit=limit)
    return rooms

@app.post("/messages/", response_model=schemas.Message)
def create_message(message: schemas.MessageCreate, db: Session = Depends(get_db)):
    return crud.create_message(db=db, message=message)

@app.get("/messages/{room_id}", response_model=list[schemas.Message])
def read_messages(room_id: int, db: Session = Depends(get_db)):
    messages = crud.get_messages(db, room_id=room_id)
    return messages

@app.get("/stream/{room_id}")
async def message_stream(request: Request, room_id: int, db: Session = Depends(get_db)):
    async def event_generator():
        last_message_id = 0
        while True:
            if await request.is_disconnected():
                break
            messages = crud.get_messages(db, room_id=room_id, offset=last_message_id)
            if messages:
                for message in messages:
                    yield json.dumps(schemas.Message.from_orm(message).dict())
                    last_message_id = message.id
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator(), media_type="text/event-stream")
