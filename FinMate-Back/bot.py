# finmate_ai.py
from typing import Literal, List, Mapping
from google import genai
from google.genai import types
import os

# =========================
# 1. Gemini 클라이언트 설정
# =========================


API_KEY = "AIzaSyAslb8OSQhuBq2-q-bMPeOZzA1otlr3evY"
# 테스트용이여서 모델 별로 하루 20개씩 밖에 안됩니다
# api key 직접 발급하셔도 됩니다
# 제일 밑 모델에서 gemini-2.5-flash-lite / gemini-2.5-flash 각각 20개씩 테스트 가능합니다
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

client = genai.Client(api_key=API_KEY)

# 시스템 페르소나
system_persona = (
    "당신은 투자자들에게 현실적인 조언을 해주는 친절하고 전문적인 금융 컨설턴트. "
    "답변은 항상 핵심적이고 명료하게 작성 "
    "최신 정보가 필요한 질문(예: 주가, 뉴스)에는 반드시 검색 도구를 사용하여 답변."
    "답변은 3줄 이내"
)

# Google 검색 도구
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# 모델 설정
config = types.GenerateContentConfig(
    tools=[grounding_tool],
    system_instruction=system_persona,
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
)

# =========================
# 2. 실제 답변 생성 함수
# =========================

def generate_finmate_reply(
    mode: Literal["easy", "pro"],
    message: str,
    history: List[Mapping[str, str]],
) -> str:
    """
    FinMate용 Gemini 답변 생성 함수.
    - mode: "easy" | "pro"
    - message: 사용자의 이번 질문
    - history: [{ "role": "user" | "ai", "text": "..." }, ...]
      → 여기서 최근 9개만 사용 (이번 질문까지 총 10개 맥락)
    """

    # 1) 모드에 따른 말투 프리픽스
    if mode == "easy":
        mode_prefix = "[모드: 주린이에게 쉽게, 친절하게 설명해줘]\n"
    else:
        mode_prefix = "[모드: 전문가에게 심층 분석하듯 답변해줘]\n"

    # 2) 히스토리에서 최근 9개만 사용
    trimmed_history = history[-9:]

    # 3) 히스토리를 텍스트로 합치기
    history_lines = []
    for msg in trimmed_history:
        role = msg.get("role", "user")
        text = msg.get("text", "")
        speaker = "사용자" if role == "user" else "컨설턴트"
        history_lines.append(f"{speaker}: {text}")

    history_text = "\n".join(history_lines) if history_lines else "이전 대화 없음"

    # 4) 최종 프롬프트 구성
    user_prompt = (
        mode_prefix
        + "다음은 지금까지의 대화 기록입니다.\n"
        + history_text
        + "\n\n"
        + "위 대화를 충분히 참고해서, 다음 사용자의 질문에 답변해 주세요.\n"
        + f"사용자 질문: {message}"
    )

    # 5) Gemini 호출
    chat_session = client.chats.create(
        model="gemini-2.5-flash-lite",
        config=config,
    )

    response = chat_session.send_message(user_prompt)
    return response.text
