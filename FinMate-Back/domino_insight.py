# domino_insight.py

from typing import List, Dict, Any

# ------------------------------------------------------------------------------
# [모듈 임포트]
# 1. bot: 이미 생성된 Gemini 클라이언트 인스턴스를 가져와 재사용합니다. (연결 효율성)
# 2. ecos: 한국은행 API에서 금리와 주가 데이터를 가져오는 함수들을 임포트합니다.
# 3. config: 모델명 등 환경 설정을 가져옵니다.
# ------------------------------------------------------------------------------
from bot import client
from ecos import get_policy_rate_last_n, get_kospi_last_n
from config import settings

# 도미노 분석에 사용할 Gemini 모델 (예: gemini-2.0-flash)
GEMINI_MODEL_FOR_DOMINO = settings.GEMINI_MODEL_DEFAULT


# ==============================================================================
# 1. 데이터 포맷팅 헬퍼 함수
# ==============================================================================

def _build_macro_series_text(rate_rows: List[Dict[str, Any]],
                             kospi_rows: List[Dict[str, Any]]) -> str:
    """
    ECOS API에서 가져온 '기준금리'와 'KOSPI' 데이터를 
    LLM(Gemini)이 이해하기 쉬운 텍스트 문장 형태로 변환합니다.

    [작동 방식]
    1. 두 개의 리스트(금리, 주가)를 날짜(TIME) 기준으로 매칭(Join)합니다.
    2. "날짜: 금리 X%, KOSPI Y" 형태의 문자열 리스트를 만듭니다.
    3. 이를 줄바꿈(\n)으로 합쳐 하나의 긴 텍스트로 만듭니다.
    """
    
    # 1) KOSPI 데이터를 검색하기 쉽도록 { "202401": 2500.50, ... } 형태의 맵(딕셔너리)으로 변환
    kospi_map: Dict[str, float] = {}
    for r in kospi_rows:
        time_key = r.get("TIME")
        value_str = r.get("DATA_VALUE")
        try:
            kospi_map[time_key] = float(value_str)
        except (TypeError, ValueError):
            continue

    lines = []
    
    # 2) 기준금리 데이터를 순회하며 같은 날짜의 KOSPI 데이터를 찾아서 매칭
    for r in rate_rows:
        time = r.get("TIME", "")          # 예: "202501"
        value_str = r.get("DATA_VALUE")   # 기준금리 값

        # 날짜 포맷팅: "202501" -> "2025.01" (가독성을 위해)
        if len(time) == 6:
            date_str = f"{time[:4]}.{time[4:]}"
        else:
            date_str = time

        try:
            rate = float(value_str)
        except (TypeError, ValueError):
            rate = 0.0

        # 해당 날짜의 KOSPI 값이 있는지 확인
        kospi = kospi_map.get(time)

        # 3) 결과 문자열 생성
        if kospi is not None:
            lines.append(f"- {date_str}: 기준금리 {rate:.2f}%, KOSPI {kospi:.2f}")
        else:
            lines.append(f"- {date_str}: 기준금리 {rate:.2f}%, KOSPI 데이터 없음")

    return "\n".join(lines)


# ==============================================================================
# 2. 도미노 인사이트 생성 메인 함수
# ==============================================================================

def get_domino_insight(n: int = 6) -> Dict[str, Any]:
    """
    최근 N개월간의 '기준금리'와 'KOSPI' 추이를 분석하여,
    Gemini가 '거시경제 도미노 효과(상관관계)'를 설명하는 한 줄 평을 생성합니다.

    Returns:
        성공 시: { "insight": "금리 인하 기대감으로 주가가 상승세입니다." }
        실패 시: { "error": "에러 메시지" }
    """

    # -----------------------------------------------------------
    # STEP 1: ECOS 데이터 가져오기
    # -----------------------------------------------------------
    try:
        rate_rows = get_policy_rate_last_n(n)  # 최근 N개월 기준금리
        kospi_rows = get_kospi_last_n(n)       # 최근 N개월 KOSPI 월평균
    except Exception as e:
        return {"error": f"ECOS 데이터 조회 오류: {e}"}

    # ECOS 모듈에서 에러가 발생하여 dict 형태의 에러 메시지를 반환한 경우 처리
    if isinstance(rate_rows, dict) and "error" in rate_rows:
        return {"error": f"기준금리 오류: {rate_rows['error']}"}
    if isinstance(kospi_rows, dict) and "error" in kospi_rows:
        return {"error": f"KOSPI 오류: {kospi_rows['error']}"}

    if not rate_rows or not kospi_rows:
        return {"error": "도미노 분석에 사용할 데이터가 부족합니다."}

    # LLM에게 넘겨줄 텍스트 데이터 생성
    series_text = _build_macro_series_text(rate_rows, kospi_rows)


    # -----------------------------------------------------------
    # STEP 2: 프롬프트 엔지니어링
    # 데이터의 관계를 설명하도록 페르소나와 제약 조건을 설정합니다.
    # -----------------------------------------------------------
    prompt = f"""
너는 개인 투자자들을 위한 금융 대시보드 'FinMate'의
'거시경제 도미노 효과' 섹션을 설명하는 AI Analyst야.

[역할]
- 기준금리와 KOSPI 지수의 최근 흐름을 보고,
  두 지표의 관계를 1~2문장으로 쉽고 차분하게 설명해줘.
- 과장된 멘트는 피하고, 데이터에 기반한 톤을 유지해.
- 특정 종목의 매수/매도 조언은 하지 마.

[입력 데이터]
{series_text}

[출력 형식]
- 한국어 한 문장 또는 두 문장.
- 각 문장은 40자 이내, 전체 80자 이내.
- "AI Analyst 분석:" 같은 접두사는 붙이지 말고
  바로 내용만 출력해.
"""


    # -----------------------------------------------------------
    # STEP 3: Gemini API 호출 및 결과 반환
    # -----------------------------------------------------------
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL_FOR_DOMINO,
            contents=prompt,
        )
        
        insight = (response.text or "").strip()
        
        # 빈 응답이 올 경우에 대한 방어 코드
        if not insight:
            return {"error": "Gemini로부터 유효한 응답을 받지 못했습니다."}

        return {"insight": insight}

    except Exception as e:
        return {"error": f"Gemini 분석 오류: {e}"}