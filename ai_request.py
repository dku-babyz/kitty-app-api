import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

def process_text_with_ai(text: str) -> dict:
    """
    AI 서버에 텍스트를 보내 유해성 판단 및 순화된 텍스트를 요청합니다.
    """
    try:
        ai_server_url = f"{os.getenv("AI_SERVER_URL")}/process_text"
        payload = {"text": text}
        response = requests.post(ai_server_url, json=payload, timeout=10)
        response.raise_for_status()

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
            "raw_processed_text_from_ai_server": processed_text, # Add this line
            "quiz_results": ai_response.get("quiz_results", []),
            "report_results": ai_response.get("report_results", {})
        }

    except requests.exceptions.RequestException as e:
        print(f"AI server connection error: {e}")
        return {
            "is_harmful": False,
            "purified_text": text,
            "harmful_words": [],
            "quiz_results": [],
            "report_results": {}
        }
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {
            "is_harmful": False,
            "purified_text": text,
            "harmful_words": [],
            "quiz_results": [],
            "report_results": {}
        }