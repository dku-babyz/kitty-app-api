import json

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from websockets import InvalidParameterName

import ai_request
import crud
import models
import schemas
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: int):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: int):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)

    async def broadcast(self, message: str, room_id: int):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_text(message)

manager = ConnectionManager()

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

@app.get("/messages/{room_id}", response_model=list[schemas.Message])
def read_messages(room_id: int, db: Session = Depends(get_db)):
    messages = crud.get_messages(db, room_id=room_id)
    return messages

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int):
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            parsed = json.loads(data)

            if parsed.get("type") == "join_room":
                continue

            db: Session = SessionLocal()

            content = parsed["content"]
            sender_id = parsed["sender_id"]

            ai_result = ai_request.process_text_with_ai(content)
            is_harmful = ai_result.get("is_harmful", False)
            purified_text = ai_result.get("purified_text", content)
            harmful_words = ai_result.get("harmful_words", [])
            quiz_data = ai_result.get("quiz")

            user = crud.get_user(db, user_id=sender_id)
            if not user:
                raise InvalidParameterName("User not found")

            # 3. 결과에 따라 경험치 및 캐릭터 상태 업데이트
            if is_harmful:
                new_xp = user.experience_points - 10
                new_state = "crying"
            else:
                new_xp = user.experience_points + 5
                new_state = "smiling"

            # 경험치는 0 미만으로 내려가지 않도록 방지
            if new_xp < 0:
                new_xp = 0

            updated_user = crud.update_user_status(
                db, user_id=user.id, xp=new_xp,
            )

            try:
                message_create = schemas.MessageCreate(
                    room_id=room_id,
                    content=purified_text,
                    owner_id=sender_id,
                    character_state=new_state,
                    experience_points=new_xp,
                    is_harmful=is_harmful,
                )
                db_message = crud.create_message(db, message_create)
                schema_data = schemas.Message.from_orm(db_message)
                from fastapi.encoders import jsonable_encoder

                await manager.broadcast(
                    json.dumps({"type": "new_message", "message": jsonable_encoder(schema_data)}),
                    room_id=room_id
                )
            except Exception as e:
                print("Error:", e)
            finally:
                db.close()

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)