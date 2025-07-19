from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import schemas
from ..crud import crud
from ..db import database
from ..services import ai_service

router = APIRouter()

@router.post("/chat", response_model=schemas.ChatMessageResponse)
def handle_chat_message(
    request: schemas.ChatMessageRequest,
    db: Session = Depends(database.get_db)
):
    # 1. AI 서버로 채팅 메시지 보내서 분석 요청
    ai_result = ai_service.process_text_with_ai(request.message)
    is_harmful = ai_result.get("is_harmful", False)
    purified_text = ai_result.get("purified_text", request.message)
    harmful_words = ai_result.get("harmful_words", [])
    quiz_data = ai_result.get("quiz")

    # 2. 사용자 정보 가져오기
    user = crud.get_user(db, user_id=request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 3. 결과에 따라 경험치 및 캐릭터 상태 업데이트
    if is_harmful:
        new_xp = user.experience_points - 10  # 유해 시 경험치 하락
        new_state = "crying"  # 유해 시 캐릭터 울음
    else:
        new_xp = user.experience_points + 5   # 유해하지 않을 시 경험치 상승
        new_state = "smiling" # 유해하지 않을 시 캐릭터 웃음

    # 경험치는 0 미만으로 내려가지 않도록 방지
    if new_xp < 0:
        new_xp = 0

    # DB에 업데이트
    updated_user = crud.update_user_status(
        db, user_id=user.id, xp=new_xp, state=new_state
    )

    if not updated_user:
        raise HTTPException(status_code=500, detail="Failed to update user status")

    # 4. 클라이언트에 응답 반환
    return schemas.ChatMessageResponse(
        user_id=updated_user.id,
        character_state=updated_user.character_state,
        experience_points=updated_user.experience_points,
        is_harmful=is_harmful,
        quiz=quiz_data
    )