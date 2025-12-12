# main.py

# ==============================================================================
# [필수 라이브러리 및 모듈 임포트]
# ==============================================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal, List, Optional, Dict, Any, Union

# ------------------------------------------------------------------------------
# [커스텀 모듈 임포트]
# 프로젝트 내 다른 파일에서 정의된 핵심 기능들을 가져옵니다.
# ------------------------------------------------------------------------------
from bot import generate_finmate_reply          # Google Gemini AI를 통해 챗봇 답변 생성
from ecos import search_ecos_glossary_term      # 한국은행 ECOS 용어 사전 검색 기능
from ecos import get_policy_rate_last_n         # 기준금리 데이터 조회
from ecos import get_kospi_last_n               # KOSPI 월평균 데이터 조회
from ecos import get_last_one                   # 주요 시장 지수(KOSPI, 환율 등) 최신값 조회
from ecos import get_macro_points               # 도미노 그래프용 데이터(금리+주가) 가공

from news_weather import get_news_weather       # 네이버 뉴스 크롤링 + AI 요약("시장 날씨") 생성

from domino_insight import get_domino_insight   # 거시경제 데이터 기반 AI 인사이트 생성


# ==============================================================================
# 1. FastAPI 앱 초기화 및 설정
# ==============================================================================

app = FastAPI()

# [CORS 설정]
# 프론트엔드(React/Next.js 등)가 http://localhost:3000 에서 실행될 때,
# 이 백엔드 API에 정상적으로 요청을 보낼 수 있도록 허용합니다.
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # 허용할 출처 목록
    allow_credentials=True,     # 쿠키/인증 정보 포함 허용
    allow_methods=["*"],        # 모든 HTTP 메서드(GET, POST 등) 허용
    allow_headers=["*"],        # 모든 헤더 허용
)


# ==============================================================================
# 2. 데이터 모델 정의 (Pydantic)
# 요청(Request)과 응답(Response) 데이터의 형식을 정의하여 유효성을 검증합니다.
# ==============================================================================

# [채팅 관련 모델]
class HistoryMessage(BaseModel):
    """이전 대화 기록 (User와 AI의 턴)"""
    role: Literal["user", "ai"]
    text: str

class ChatRequest(BaseModel):
    """클라이언트가 보내는 채팅 요청 구조"""
    mode: Literal["easy", "pro"]        # 답변 스타일 (쉬운 모드 / 전문가 모드)
    message: str                        # 사용자의 현재 질문
    history: List[HistoryMessage] = []  # 대화 맥락 유지를 위한 히스토리

class ChatResponse(BaseModel):
    """클라이언트에게 보낼 채팅 응답 구조"""
    reply: str

# [거시경제 그래프 관련 모델]
class MacroPoint(BaseModel):
    """도미노 그래프의 한 점(Point) 데이터"""
    date: str                       # 날짜 (예: "2024.01")
    rate: float                     # 한국은행 기준금리
    stock: Optional[float] = None   # KOSPI 지수 (데이터가 없을 경우 None 허용)

# [뉴스 및 시장 날씨 관련 모델]
class NewsWeather(BaseModel):
    """AI가 요약한 오늘의 시장 날씨 3줄 평"""
    line1: str
    line2: str
    line3: str

class NewsCard(BaseModel):
    """개별 뉴스 카드 데이터"""
    category: str   # 뉴스 카테고리 (예: 증시, 부동산)
    title: str      # 기사 제목
    summary: str    # 3줄 요약
    insight: str    # AI의 분석/인사이트
    url: str        # 원문 링크

class NewsWeatherResponse(BaseModel):
    """뉴스 날씨 API 최종 응답 구조"""
    weather: NewsWeather
    cards: List[NewsCard]


# ==============================================================================
# 3. API 엔드포인트 정의
# ==============================================================================

# ------------------------------------------------------------------------------
# [3-a] 메인 채팅 API (/api/chat)
# 사용자의 질문을 받아 1차로 경제 용어 사전을 검색하고, 없으면 AI에게 질문합니다.
# ------------------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):

    # 1. Pydantic 모델을 딕셔너리 형태로 변환 (Gemini 모듈 호환성 위해)
    history_dicts = [
        {"role": h.role, "text": h.text}
        for h in req.history
    ]

    user_msg = req.message.strip()

    # --------------------------------------
    # STEP 1: ECOS 용어 사전 우선 검색
    # 사용자가 경제 용어를 물어봤을 경우, 정확한 정의를 먼저 제공합니다.
    # --------------------------------------
    ecos_result = search_ecos_glossary_term(user_msg)

    # 검색 결과가 있고 "용어설명"이 존재하는 경우 -> 사전 정의 반환
    if isinstance(ecos_result, dict) and ecos_result.get("용어설명"):
        term = ecos_result["용어"]
        desc = ecos_result["용어설명"]

        # 모드에 따라 말투를 다르게 포장
        if req.mode == "easy":
            answer = (
                f"📘 **[{term}] 용어 설명 (쉬운 버전)**\n\n"
                f"{desc}\n\n"
                f"👉 한국은행 ECOS 공식 용어사전 데이터를 기반으로 한 설명이에요!"
            )
        else:
            answer = (
                f"📊 **[{term}] ECOS 공식 정의**\n\n"
                f"{desc}\n\n"
                f"(출처: 한국은행 ECOS)"
            )

        return ChatResponse(reply=answer)

    # --------------------------------------
    # STEP 2: 사전에 없으면 Gemini AI 호출
    # 일반적인 질문이나 복합적인 대화는 LLM이 처리합니다.
    # --------------------------------------
    try:
        reply_text = generate_finmate_reply(
            mode=req.mode,
            message=req.message,
            history=history_dicts,
        )
    except Exception as e:
        # AI 호출 중 에러 발생 시 500 에러 반환
        raise HTTPException(status_code=500, detail=f"Gemini 호출 오류: {e}")

    return ChatResponse(reply=reply_text)


# ------------------------------------------------------------------------------
# [3-b] 도미노 그래프 데이터 API (/api/macro-chart)
# 기준금리와 KOSPI 지수의 상관관계를 보여주는 그래프용 데이터를 반환합니다.
# ------------------------------------------------------------------------------
@app.get("/api/macro-chart", response_model=List[MacroPoint])
def get_macro_chart():
    """
    도미노 그래프에 사용할 데이터 반환
    - 범위: 최근 N개월 (여기서는 6개월)
    - 내용: 기준금리(Rate) vs 주가(Stock)
    """
    N = 6
    data = get_macro_points(N)

    # 데이터 가져오기 실패 시 에러 처리
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])

    # 리스트 내부의 딕셔너리를 Pydantic 모델로 변환하여 반환
    return [MacroPoint(**p) for p in data]


# ------------------------------------------------------------------------------
# [3-c] 실시간 시장 지수 API (/api/market-weather)
# 프론트엔드 상단 배너에 표시될 KOSPI, 환율 등의 최신 수치를 반환합니다.
# ------------------------------------------------------------------------------
@app.get("/api/market-weather")
def market_weather():
    """
    주요 4대 시장 지표 조회
    1. KOSPI
    2. KOSDAQ
    3. 원/달러 환율
    4. 국고채 3년물 금리
    -> 각각의 '현재가'와 '전일 대비 등락률'을 반환
    """
    data = get_last_one()  # ecos.py 내부 함수 호출

    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])

    return data  # 구조: { "indices": [ {name, value, change}, ... ] }


# ------------------------------------------------------------------------------
# [3-d] 뉴스 기반 시장 날씨 API (/api/news-weather)
# 최신 뉴스를 크롤링하고 AI가 이를 분석하여 '오늘의 시장 분위기'와 '뉴스 카드'를 생성합니다.
# ------------------------------------------------------------------------------
@app.get("/api/news-weather", response_model=NewsWeatherResponse)
def news_weather_endpoint():
    """
    1. 네이버 금융 뉴스 크롤링
    2. AI를 통한 뉴스 요약 및 인사이트 도출
    3. '맑음/흐림' 등의 시장 날씨 멘트 생성
    """
    try:
        data = get_news_weather()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"뉴스/LLM 처리 오류: {e}")

    # 원본 딕셔너리 데이터 추출
    weather_dict = data.get("weather", {})
    cards_list = data.get("cards", [])

    # Pydantic 모델에 맞춰 데이터 매핑
    weather = NewsWeather(
        line1=weather_dict.get("line1", ""),
        line2=weather_dict.get("line2", ""),
        line3=weather_dict.get("line3", ""),
    )

    cards = [
        NewsCard(
            category=c.get("category", ""),
            title=c.get("title", ""),
            summary=c.get("summary", ""),
            insight=c.get("insight", ""),
            url=c.get("url", ""),
        )
        for c in cards_list
    ]

    return NewsWeatherResponse(weather=weather, cards=cards)


# ------------------------------------------------------------------------------
# [3-e] 도미노 인사이트 API (/api/macro-insight)
# 거시경제 데이터(도미노 그래프 데이터)를 AI가 분석하여 텍스트 코멘트를 제공합니다.
# ------------------------------------------------------------------------------
@app.get("/api/macro-insight")
def macro_insight():
    data = get_domino_insight()

    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])

    return data


# ==============================================================================
# 4. 서버 헬스 체크용 기본 엔드포인트
# ==============================================================================
@app.get("/")
def root():
    return {"message": "FinMate Backend + ECOS Ready!"}