# calendar_insight.py
from typing import Optional
from google import genai
from google.genai import types
from config import settings


# ==============================================================================
# Gemini client (insight 전용)
# - bot.py의 system_persona는 "3줄 이내" 제한이 있어서 인사이트용으론 별도 config 사용
# - 최신 데이터 생성/검색 금지 (무료 플랜 절약 + 환각 방지)
# ==============================================================================

API_KEY = settings.GEMINI_API_KEY
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

client = genai.Client(api_key=API_KEY)

INSIGHT_SYSTEM_PERSONA = """
너는 한국 주식/거시경제 이벤트를 설명하는 금융 멘토다.
반드시 '구조화된 섹션'으로만 답하고, 서론/잡담/인삿말/요약문/주의문을 절대 넣지 마라.
실제 수치/실적/뉴스/전망 등 '검증 불가한 최신 사실'은 만들지 말고, 일반 원리와 체크포인트로 설명해라.
각 항목은 짧은 bullet로 써라. (한 줄 25자~60자 정도)
""".strip()

# 검색 도구를 아예 빼서(=tools 없음) 비용/할당량 절약 + 환각 방지
INSIGHT_CONFIG = types.GenerateContentConfig(
    system_instruction=INSIGHT_SYSTEM_PERSONA,
    temperature=0.4,
)


def build_insight_prompt(
    title: str,
    company_name: str,
    stock_code: str,
    datetime: str,
    event_type: Optional[str] = None,
) -> str:
    # ✅ 핵심: "첫 문장 금지" + "정해진 헤더로 바로 시작" + "UI가 섹션으로 묶기 쉬운 포맷"
    return f"""
[이벤트 정보]
- 기업명: {company_name}
- 종목코드: {stock_code}
- 일정: {datetime}
- 이벤트 제목: {title}
- 타입: {event_type or "UNKNOWN"}

[출력 규칙]
- 반드시 아래 3개 섹션만 출력한다. (다른 문장/서론/결론 금지)
- 각 섹션은 '헤더' 다음에 항목을 번호로 나눈다.
- 각 번호 아래는 2~3개의 bullet로 쓴다.
- '실제 수치/실적 결과/속보/루머' 같은 최신 사실을 절대 만들어내지 말고, 일반 원리 기반으로만 작성한다.

[출력 형식(그대로)]
🔴 상승 요인 (롱 근거)
1) 기본적(펀더멘탈) 분석
- ...
- ...
2) 기술적 분석
- ...
- ...
3) 매크로 분석
- ...
- ...
4) 심리/이벤트 기반 분석
- ...
- ...

🔵 하락 요인 (숏 근거)
1) 기본적(펀더멘탈) 분석
- ...
- ...
2) 기술적 분석
- ...
- ...
3) 매크로 분석
- ...
- ...
4) 심리/이벤트 기반 분석
- ...
- ...

🟢 시장 체크 포인트
- ...
- ...
- ...
""".strip()


def generate_calendar_insight(
    title: str,
    company_name: str,
    stock_code: str,
    datetime: str,
    event_type: Optional[str] = None,
) -> str:
    prompt = build_insight_prompt(
        title=title,
        company_name=company_name,
        stock_code=stock_code,
        datetime=datetime,
        event_type=event_type,
    )

    res = client.models.generate_content(
        model=settings.GEMINI_MODEL_DEFAULT,
        contents=prompt,
        config=INSIGHT_CONFIG,
    )
    
    return (res.text or "").strip()
