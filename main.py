import json
import os
from datetime import timedelta, datetime

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from websockets import InvalidParameterName
from jose import JWTError, jwt

import ai_request
import crud
import models
import schemas
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Kitty App API",
    version="0.1.0",
    description="API for the Kitty App, a chat application with AI-powered content moderation.",
)

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not crud.pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    db_user = crud.get_user_by_phone_number(db, phone_number=user.phone_number)
    if db_user:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    if user.email:
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
            quiz_results = ai_result.get("quiz_results", [])
            report_results = ai_result.get("report_results", {})

            user = crud.get_user(db, user_id=sender_id)
            if not user:
                raise InvalidParameterName("User not found")

            # 3. 결과에 따라 경험치 및 캐릭터 상태 업데이트
            new_harmful_chat_count = user.harmful_chat_count
            if is_harmful:
                new_xp = user.experience_points - 10
                new_state = "crying"
                new_harmful_chat_count += 1
            else:
                new_xp = user.experience_points + 5
                new_state = "smiling"

            # 경험치는 0 미만으로 내려가지 않도록 방지
            if new_xp < 0:
                new_xp = 0

            updated_user = crud.update_user_status(
                db, user_id=user.id, xp=new_xp, character_state=new_state, harmful_chat_count=new_harmful_chat_count
            )

            try:
                message_create = schemas.MessageCreate(
                    room_id=room_id,
                    content=purified_text,
                    owner_id=sender_id,
                    character_state=new_state, # 메시지 자체의 캐릭터 상태
                    experience_points=new_xp, # 메시지 자체의 경험치
                    is_harmful=is_harmful,
                )
                db_message = crud.create_message(db, message_create)
                schema_data = schemas.Message.from_orm(db_message)
                from fastapi.encoders import jsonable_encoder

                # 사용자 정보 업데이트를 포함하여 브로드캐스트
                await manager.broadcast(
                    json.dumps({
                        "type": "new_message",
                        "message": jsonable_encoder(schema_data),
                        "user_update": {
                            "id": updated_user.id,
                            "experience_points": updated_user.experience_points,
                            "character_state": updated_user.character_state,
                            "harmful_chat_count": updated_user.harmful_chat_count
                        },
                        "quiz_results": quiz_results,
                        "report_results": report_results
                    }),
                    room_id=room_id
                )
            except Exception as e:
                print("Error:", e)
            finally:
                db.close()

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)