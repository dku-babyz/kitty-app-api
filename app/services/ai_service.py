import requests
import json
from ..core.config import settings

def process_text_with_ai(text: str) -> dict:
    """
    AI 서버에 텍스트를 보내 유해성 판단 및 순화된 텍스트를 요청합니다.
    """
    try:
        ai_server_url = f"{settings.AI_SERVER_URL}/process_text"
        payload = {"text": text}
        response = requests.post(ai_server_url, json=payload, timeout=10)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생

        ai_response = response.json()
        original_text = ai_response.get("original_text", "")
        processed_text = ai_response.get("processed_text", "")

        is_harmful = original_text != processed_text
        purified_text = original_text
        harmful_words = []
        quiz_data = None

        if is_harmful:
            try:
                # processed_text가 JSON 문자열일 경우 파싱
                parsed_processed_text = json.loads(processed_text)
                purified_text = parsed_processed_text.get("대체 문장", original_text)
                harmful_words = parsed_processed_text.get("문장중 유해한 단어들", [])
            except json.JSONDecodeError:
                # processed_text가 단순 문자열일 경우 (순화된 문장 자체)
                purified_text = processed_text

        return {
            "is_harmful": is_harmful,
            "purified_text": purified_text,
            "harmful_words": harmful_words,
            "quiz": quiz_data # 현재 AI 서버에서 제공하지 않으므로 None
        }

    except requests.exceptions.RequestException as e:
        print(f"AI server connection error: {e}")
        # AI 서버 연결 실패 또는 타임아웃 시 기본 응답
        return {
            "is_harmful": False,
            "purified_text": text,
            "harmful_words": [],
            "quiz": None
        }
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {
            "is_harmful": False,
            "purified_text": text,
            "harmful_words": [],
            "quiz": None
        }