import json
import os
from datetime import timedelta, datetime

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from websockets import InvalidParameterName
from jose import JWTError, jwt

import requests
import ai_request
import crud
import models
import schemas
from database import SessionLocal, engine

AI_AGENT_API_URL = os.getenv("AI_AGENT_API_URL", "http://220.149.244.87:8000")
KITTY_API_KEY = os.getenv("KITTY_API_KEY")
QUIZ_REPORT_AI_API_URL = os.getenv("QUIZ_REPORT_AI_API_URL", "http://220.149.244.87:8000")
QUIZ_REPORT_AI_API_KEY = os.getenv("QUIZ_REPORT_AI_API_KEY")

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

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

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

@app.post("/generate-story", response_model=schemas.StoryGenerationResponse)
async def generate_story(request: schemas.RiskScoreRequest):
    if not KITTY_API_KEY:
        raise HTTPException(status_code=500, detail="KITTY_API_KEY not configured")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": KITTY_API_KEY
    }
    payload = {
        "risk_score": request.risk_score
    }

    try:
        response = requests.post(f"{AI_AGENT_API_URL}/generate-story", headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"AI agent API call failed: {e}")

async def call_quiz_report_ai_server(user_id: int, original_text: str, processed_text: str) -> schemas.ProcessChatDataResponse:
    if not QUIZ_REPORT_AI_API_KEY:
        raise HTTPException(status_code=500, detail="QUIZ_REPORT_AI_API_KEY not configured")

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": QUIZ_REPORT_AI_API_KEY
    }
    payload = {
        "user_id": user_id,
        "original_text": original_text,
        "processed_text": processed_text
    }

    try:
        response = requests.post(f"{QUIZ_REPORT_AI_API_URL}/process_chat_data", headers=headers, json=payload)
        response.raise_for_status()
        return schemas.ProcessChatDataResponse(**response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error calling Quiz/Report AI server: {e}")
        if response is not None:
            print(f"Response status: {response.status_code}, body: {response.text}")
        raise HTTPException(status_code=500, detail=f"Quiz/Report AI server call failed: {e}")

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

@app.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: schemas.User = Depends(get_current_user)):
    return current_user

@app.post("/ai-story", response_model=schemas.DiaryGenerationResponse)
async def generate_ai_story(request: schemas.DiaryEntryRequest):
    # Dummy logic to generate risk_score based on mood
    # In a real scenario, this would involve more sophisticated AI analysis
    risk_score = 50 # Default neutral
    if request.mood == "happy":
        risk_score = 10
    elif request.mood == "sad":
        risk_score = 80
    elif request.mood == "angry":
        risk_score = 95
    # Add more mood mappings as needed

    # Call the existing generate_story logic
    try:
        story_response = await generate_story(schemas.RiskScoreRequest(risk_score=risk_score))
        
        # Transform the response to the format expected by the frontend
        return schemas.DiaryGenerationResponse(
            image_url=story_response.final_image_path,
            story=story_response.final_story
        )
    except HTTPException as e:
        raise e # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate AI story: {e}")

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
            quiz_results_from_ai = []
            report_results_from_ai = {}

            if is_harmful:
                new_xp = user.experience_points - 10
                new_state = "crying"
                new_harmful_chat_count += 1

                # Check if harmful_chat_count reaches 10 or more
                if new_harmful_chat_count >= 10:
                    try:
                        # Call the Quiz/Report AI server
                        ai_response = await call_quiz_report_ai_server(
                            user_id=sender_id,
                            original_text=content,
                            processed_text=ai_result.get("raw_processed_text_from_ai_server", "")
                        )
                        quiz_results_from_ai = ai_response.quiz_results
                        report_results_from_ai = ai_response.report_results
                    except HTTPException as e:
                        print(f"Failed to get quiz/report from AI server: {e.detail}")

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
                        "quiz_results": quiz_results_from_ai,
                        "report_results": report_results_from_ai
                    }),
                    room_id=room_id
                )
            except Exception as e:
                print("Error:", e)
            finally:
                db.close()

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)