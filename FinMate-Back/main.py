# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bot import generate_finmate_reply # 기존 Gemini AI 모듈
from ecos import search_ecos_glossary_term 
from ecos import get_policy_rate_last_n # ECOS 금리 데이터
from ecos import get_kospi_last_n # ECOS KOSPI 월평균 데이터 추가
from ecos import get_last_one  # 

from typing import Literal, List, Optional, Dict, Any, Union # Dict와 Optional 등 추가

# =========================
# 1. FastAPI 설정
# =========================

app = FastAPI()

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# 2. 요청/응답 타입
# =========================

class HistoryMessage(BaseModel):
    role: Literal["user", "ai"]
    text: str

class ChatRequest(BaseModel):
    mode: Literal["easy", "pro"]
    message: str
    history: List[HistoryMessage] = []

class ChatResponse(BaseModel):
    reply: str


class MacroPoint(BaseModel):
    date: str       # 예: "2024.01"
    rate: float     # 기준금리
    stock: Optional[float] = None # float | None 대신 Optional 사용

# =========================
# 3. /api/chat
# =========================

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):

    # 히스토리 변환
    history_dicts = [
        {"role": h.role, "text": h.text}
        for h in req.history
    ]

    user_msg = req.message.strip()


    # --------------------------------------
    # STEP 1️: ECOS 용어 검색 먼저 시도
    # --------------------------------------
    ecos_result = search_ecos_glossary_term(user_msg)

    # "용어"와 "용어설명"이 존재하는 경우 → ECOS 정의를 그대로 반환
    if isinstance(ecos_result, dict) and ecos_result.get("용어설명"):
        term = ecos_result["용어"]
        desc = ecos_result["용어설명"]

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
    # STEP 2️: ECOS에 없으면 → 평소처럼 Gemini 사용
    # --------------------------------------
    try:
        reply_text = generate_finmate_reply(
            mode=req.mode,
            message=req.message,
            history=history_dicts,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini 호출 오류: {e}")

    return ChatResponse(reply=reply_text)

#-------------------- 도미노 그래프

@app.get("/api/macro-chart", response_model=List[MacroPoint])
def get_macro_chart():
    """
    도미노 그래프에 쓸 기준금리 및 KOSPI 월평균 데이터 반환
    """
    N = 6

    # --- 1. 데이터 조회 (기준금리 및 KOSPI 모두 호출) ---
    try:
        rate_rows = get_policy_rate_last_n(N)  # 최근 6개 기준금리
        kospi_rows = get_kospi_last_n(N)       # 최근 6개 KOSPI 월평균
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ECOS 데이터 조회 오류: {e}")

    # ECOS 함수에서 오류 딕셔너리를 반환한 경우 처리
    if isinstance(rate_rows, dict) and "error" in rate_rows:
        raise HTTPException(status_code=500, detail=f"기준금리 오류: {rate_rows['error']}")
    if isinstance(kospi_rows, dict) and "error" in kospi_rows:
        raise HTTPException(status_code=500, detail=f"KOSPI 오류: {kospi_rows['error']}")

    # --- 2. KOSPI 데이터를 매칭을 위한 딕셔너리로 변환 ---
    kospi_map: Dict[str, float] = {}
    for r in kospi_rows:
        time_key = r.get("TIME")
        value_str = r.get("DATA_VALUE")
        try:
            # DATA_VALUE를 실수(float)로 변환하여 딕셔너리에 저장
            kospi_map[time_key] = float(value_str)
        except (TypeError, ValueError):
            pass

    # --- 3. 기준금리 데이터를 순회하며 매칭 및 MacroPoint 생성 ---
    points: List[MacroPoint] = []

    for r in rate_rows:
        time = r.get("TIME", "")      # 예: "202401"
        value_str = r.get("DATA_VALUE", "0")

        # 기준금리 (rate) 변환
        try:
            rate = float(value_str)
        except ValueError:
            rate = 0.0

        # 날짜 형식 변환: "202401" → "2024.01"
        if len(time) == 6:
            formatted_date = f"{time[:4]}.{time[4:]}"
        else:
            formatted_date = time

        # 🔥 KOSPI 값 매칭 🔥
        kospi_value = kospi_map.get(time) # time_key와 일치하는 KOSPI 값 조회

        points.append(
            MacroPoint(
                date=formatted_date,
                rate=rate,
                stock=kospi_value,  # 매칭된 KOSPI 월평균 값 할당
            )
        )

    return points

# =========================
# 3-b. 시장 날씨 (KOSPI/KOSDAQ/환율/국고채) API
# =========================

@app.get("/api/market-weather")
def market_weather():
    """
    KOSPI / KOSDAQ / 환율 / 국고채 3년
    - 최근 값 + 전일 대비 변화율 반환
    프론트의 상단 '시장 날씨' 카드 4개에서 사용
    """
    data = get_last_one()  # ecos.py에 있는 함수

    # get_last_one에서 에러 형식으로 리턴한 경우
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])

    return data  # { "indices": [ {name, value, change}, ... ] }

# =========================
# 4. 기본 엔드포인트
# =========================

@app.get("/")
def root():
    return {"message": "FinMate Backend + ECOS Ready!"}

