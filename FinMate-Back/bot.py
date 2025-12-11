# finmate_ai.py

from typing import Literal, List, Mapping
from google import genai
from google.genai import types
import os
from config import settings  # 환경변수 및 설정값 관리 모듈

# ==============================================================================
# 1. Google Gemini API 클라이언트 설정
# ==============================================================================

# settings에서 API 키를 가져옵니다. (.env 파일 등에 정의된 값)
API_KEY = settings.GEMINI_API_KEY

# [주의] Google AI Studio의 Free Tier(무료) 사용 시 제한 사항
# - 모델별로 하루 요청 횟수나 분당 요청 횟수(RPM) 제한이 있습니다.
# - 예: gemini-2.0-flash 등의 모델은 테스트 시 하루 약 50~1500회(정책에 따라 다름) 무료 호출 가능
# - 상용 배포 시에는 유료 플랜(Pay-as-you-go) 검토가 필요합니다.
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

# Gemini 클라이언트 인스턴스 생성
client = genai.Client(api_key=API_KEY)

# [시스템 페르소나 설정]
# AI에게 부여할 역할(Role)과 성격(Tone)을 정의합니다.
# 이 지침은 모든 대화의 기본 규칙으로 작동합니다.
system_persona = (
    "당신은 투자자들에게 현실적인 조언을 해주는 친절하고 전문적인 금융 컨설턴트. "
    "답변은 항상 핵심적이고 명료하게 작성 "
    "최신 정보가 필요한 질문(예: 주가, 뉴스)에는 반드시 검색 도구를 사용하여 답변."
    "답변은 3줄 이내"
)

# [Google 검색 도구(Grounding) 설정]
# AI가 학습 데이터에 없는 최신 정보(실시간 주가, 오늘 뉴스 등)를
# Google 검색을 통해 찾아보고 답변할 수 있도록 기능을 활성화합니다.
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# [모델 생성 설정 (Config)]
# - tools: 사용할 도구 목록 (여기선 검색 기능)
# - system_instruction: 위에서 정의한 페르소나
# - automatic_function_calling: 도구 사용이 필요할 때 AI가 자동으로 판단하여 호출
config = types.GenerateContentConfig(
    tools=[grounding_tool],
    system_instruction=system_persona,
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
)


# ==============================================================================
# 2. 챗봇 답변 생성 함수 (Core Logic)
# ==============================================================================

def generate_finmate_reply(
    mode: Literal["easy", "pro"],
    message: str,
    history: List[Mapping[str, str]],
) -> str:
    """
    FinMate용 Gemini 답변 생성 함수.
    
    Args:
        mode (str): "easy"(초보자용) 또는 "pro"(전문가용) 모드 선택
        message (str): 사용자가 현재 입력한 질문
        history (List): 이전 대화 기록 목록 [{ "role": "user/ai", "text": "..." }]
        
    Returns:
        str: AI가 생성한 답변 텍스트
    """

    # -----------------------------------------------------------
    # 1) 모드(Mode)에 따른 '말투 가이드' 프리픽스 설정
    # 프롬프트의 가장 앞단에 붙여서 답변 스타일을 즉석에서 조정합니다.
    # -----------------------------------------------------------
    if mode == "easy":
        mode_prefix = "[모드: 주린이에게 쉽게, 친절하게 설명해줘]\n"
    else:
        mode_prefix = "[모드: 전문가에게 심층 분석하듯 답변해줘]\n"

    # -----------------------------------------------------------
    # 2) 대화 문맥(Context) 관리
    # API 비용 절감 및 토큰 제한을 고려하여, 최근 대화 9개까지만 잘라서 사용합니다.
    # (이번 질문 1개 + 이전 기록 9개 = 총 10개 턴의 맥락 유지)
    # -----------------------------------------------------------
    trimmed_history = history[-9:]

    # -----------------------------------------------------------
    # 3) 히스토리 데이터 포맷팅
    # AI가 '누가 말했는지' 구분할 수 있도록 텍스트 형태로 변환합니다.
    # 예: "사용자: 안녕\n컨설턴트: 안녕하세요"
    # -----------------------------------------------------------
    history_lines = []
    for msg in trimmed_history:
        role = msg.get("role", "user")
        text = msg.get("text", "")
        speaker = "사용자" if role == "user" else "컨설턴트"
        history_lines.append(f"{speaker}: {text}")

    history_text = "\n".join(history_lines) if history_lines else "이전 대화 없음"

    # -----------------------------------------------------------
    # 4) 최종 프롬프트(Prompt) 조립
    # [모드 지시사항] + [이전 대화 기록] + [현재 질문] 순서로 합칩니다.
    # -----------------------------------------------------------
    user_prompt = (
        mode_prefix
        + "다음은 지금까지의 대화 기록입니다.\n"
        + history_text
        + "\n\n"
        + "위 대화를 충분히 참고해서, 다음 사용자의 질문에 답변해 주세요.\n"
        + f"사용자 질문: {message}"
    )

    # -----------------------------------------------------------
    # 5) Gemini API 호출 및 응답 반환
    # 설정된 모델과 설정을 사용하여 최종 텍스트를 생성합니다.
    # -----------------------------------------------------------
    chat_session = client.chats.create(
        model=settings.MODEL_NAME,  # config.py에서 지정한 모델명 (예: gemini-2.0-flash)
        config=config,
    )

    response = chat_session.send_message(user_prompt)
    
    return response.text