# ecos.py

# ==============================================================================
# [필수 라이브러리 및 모듈 임포트]
# ==============================================================================
import requests
import urllib.parse
from collections import defaultdict
from typing import List, Dict, Any, Union
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar

from config import settings  # 환경 설정 (ECOS API Key 등)

# ==============================================================================
# 1. 한국은행 ECOS API 설정
# ==============================================================================

ECOS_AUTH_KEY = settings.ECOS_AUTH_KEY
ECOS_BASE_URL = "http://ecos.bok.or.kr/api"


# ==============================================================================
# 2. 공통 유틸리티 함수 (API 호출 래퍼)
# ==============================================================================

def get_ecos_statistic(stat_code: str, cycle: str, start: str, end: str, item_code: str = "") -> Union[List[Dict], Dict]:
    """
    한국은행 ECOS 통계 조회 API를 호출하는 범용 함수입니다.
    
    Args:
        stat_code (str): 통계표 코드 (예: '722Y001' 기준금리)
        cycle (str): 주기 (D:일, M:월, Q:분기, Y:년)
        start (str): 검색 시작일자 (YYYYMMDD or YYYYMM)
        end (str): 검색 종료일자 (YYYYMMDD or YYYYMM)
        item_code (str): 통계 항목 코드 (선택값)

    Returns:
        List[Dict]: 성공 시 데이터 리스트 반환
        Dict: 실패 시 에러 메시지 딕셔너리 반환
    """
    
    # API 키 누락 확인
    if not ECOS_AUTH_KEY:
        return {"error": "ECOS_AUTH_KEY가 설정되지 않았습니다."}

    # URL 조립 (요청 인자 순서: 인증키/요청타입/언어/요청시작건수/요청종료건수/통계코드/주기/시작일/종료일/항목코드)
    url = (
        f"{ECOS_BASE_URL}/StatisticSearch/"
        f"{ECOS_AUTH_KEY}/json/kr/1/500/"
        f"{stat_code}/{cycle}/{start}/{end}/{item_code}"
    )

    try:
        res = requests.get(url, timeout=10)
        
        # HTTP 통신 에러 체크
        if res.status_code != 200:
            return {"error": f"HTTP 오류: {res.status_code}", "detail": res.text[:100]}

        data = res.json()
        
        # 1) 정상 데이터가 있는 경우 ('StatisticSearch' 키 존재)
        if "StatisticSearch" in data:
            return data["StatisticSearch"].get("row", [])
        
        # 2) API 결과 메시지 확인 ('RESULT' 키)
        if "RESULT" in data:
            # INFO-200: 데이터가 없다는 뜻 (에러 아님, 빈 리스트 반환)
            if data["RESULT"].get("CODE") == "INFO-200": 
                return [] 
            # 그 외는 실제 API 오류
            return {"error": data["RESULT"].get("MESSAGE"), "code": data["RESULT"].get("CODE")}

        # 3) 예상치 못한 응답 구조
        return {"error": f"예상치 못한 응답 구조: {str(data)[:100]}"}

    except Exception as e:
        return {"error": f"API 호출 오류: {str(e)}"}


def search_ecos_glossary_term(term: str) -> Dict[str, str]:
    """
    경제 용어 사전(Glossary) 검색 함수
    사용자가 입력한 용어에 대한 한국은행 공식 설명을 찾아줍니다.
    """
    if not ECOS_AUTH_KEY:
        return {"error": "ECOS_AUTH_KEY가 필요합니다."}

    # URL 인코딩 (한글 검색어 처리)
    encoded_term = urllib.parse.quote(term, encoding='utf-8')
    url_path = f"StatisticWord/{ECOS_AUTH_KEY}/json/kr/1/10/{encoded_term}"
    request_url = f"{ECOS_BASE_URL}/{url_path}"
    
    try:
        response = requests.get(request_url, timeout=10)
        if response.status_code != 200:
            return {"error": f"HTTP 오류: {response.status_code}"}
            
        data = response.json()
        
        # 검색 결과가 하나 이상 있을 때 첫 번째 결과를 반환
        if 'StatisticWord' in data and data['StatisticWord']['list_total_count'] > 0:
            row = data['StatisticWord']['row'][0]
            return {"용어": row.get('WORD'), "용어설명": row.get('CONTENT')}
        
        return {"message": f"'{term}' 검색 결과 없음"}

    except Exception as e:
        return {"error": f"오류: {str(e)}"}


# ==============================================================================
# 3. 월별 히스토리 데이터 조회 함수 (도미노 차트용)
# ==============================================================================

def get_policy_rate_last_n(n: int = 6) -> Union[List[Dict], Dict]:
    """
    한국은행 기준금리 추이 조회 (최근 N개월)
    
    [조회 로직]
    - 현재 달(진행 중) 데이터는 제외하고, '지난달'을 기준으로 과거 N개월을 조회합니다.
    - 예: 현재 12월이면 -> 6월 ~ 11월 데이터 반환 (확정된 월 데이터 사용)
    """
    today = datetime.today()
    
    # 1. 기준점 설정: 지난달 (1개월 전)
    last_month_date = today - relativedelta(months=1)
    
    # 2. 종료월 문자열 (YYYYMM)
    end_str = last_month_date.strftime("%Y%m")
    
    # 3. 시작월 설정
    # N개월 데이터를 얻기 위해 넉넉하게 N+2개월 전부터 조회 후 나중에 자릅니다.
    # (공휴일 등으로 데이터가 비는 경우 대비)
    start_dt = last_month_date - relativedelta(months=n+2)
    start_str = start_dt.strftime("%Y%m")

    # API 호출 (코드: 722Y001=금리, 주기: M, 항목: 0101000=한국은행 기준금리)
    rows = get_ecos_statistic("722Y001", "M", start_str, end_str, "0101000")

    if isinstance(rows, dict) and "error" in rows:
        return rows

    # 시간순 정렬 (과거 -> 최신)
    rows_sorted = sorted(rows, key=lambda r: r["TIME"])
    
    # 데이터가 N개보다 많으면, 가장 최근(지난달)이 포함되도록 뒤에서 N개만 슬라이싱
    return rows_sorted[-n:] if len(rows_sorted) > n else rows_sorted


def get_kospi_last_n(n: int = 6) -> Union[List[Dict], Dict]:
    """
    KOSPI 월평균 지수 조회 (최근 N개월)
    ECOS는 KOSPI '월평균' 데이터를 바로 주지 않는 경우가 있어, '일별' 데이터를 가져와 직접 평균을 냅니다.
    """
    today = datetime.today()
    
    # 1. 기준점: 지난달
    last_month_date = today - relativedelta(months=1)
    
    # 2. 종료일 계산: 지난달의 마지막 날짜 (예: 11월 -> 11월 30일)
    last_day = calendar.monthrange(last_month_date.year, last_month_date.month)[1]
    
    end_dt = last_month_date.replace(day=last_day)
    end_str = end_dt.strftime("%Y%m%d")
    
    # 3. 시작일 계산: 넉넉하게 잡음
    start_dt = last_month_date - relativedelta(months=n+2)
    start_str = start_dt.strftime("%Y%m%d")

    # API 호출 (코드: 802Y001=주식시장, 주기: D=일별, 항목: 0001000=KOSPI)
    rows = get_ecos_statistic("802Y001", "D", start_str, end_str, "0001000")

    if isinstance(rows, dict) and "error" in rows:
        return rows

    # [데이터 가공] 일별 데이터 -> 월별 평균 계산
    monthly_data = defaultdict(lambda: {"total": 0.0, "count": 0})
    for row in rows:
        time_str = row["TIME"]
        month_key = time_str[:6] # YYYYMM 추출
        try:
            value = float(row["DATA_VALUE"])
            monthly_data[month_key]["total"] += value
            monthly_data[month_key]["count"] += 1
        except (ValueError, TypeError):
            continue

    result_list = []
    for month_key, data in monthly_data.items():
        if data["count"] > 0:
            avg_value = data["total"] / data["count"]
            result_list.append({
                "TIME": month_key,
                "DATA_VALUE": f"{avg_value:.2f}",
                "UNIT_NAME": "월평균 KOSPI 지수"
            })
    
    # 시간순 정렬 (과거 -> 최신)
    result_sorted = sorted(result_list, key=lambda r: r["TIME"])
    
    # 뒤에서 N개 자르기 (가장 최근 월이 마지막에 오도록)
    return result_sorted[-n:] if len(result_sorted) > n else result_sorted


# ==============================================================================
# 4. 실시간(일별) 시장 지수 조회 (상단 배너용)
# ==============================================================================

def get_last_one() -> Dict[str, Any]:
    """
    대시보드 상단 '시장 날씨' 배너에 표시할 주요 4대 지표의 최신 데이터를 가져옵니다.
    (KOSPI, KOSDAQ, 환율, 국고채)
    
    Returns:
        { "indices": [ {name, value, change}, ... ] }
    """
    today = datetime.today()
    # 최근 데이터를 찾기 위해 2주 전부터 조회 (공휴일, 주말 고려)
    start_dt = today - timedelta(days=14) 
    
    start_str = start_dt.strftime("%Y%m%d")
    end_str = today.strftime("%Y%m%d")

    # 조회할 자산 목록 매핑 (Key: API 코드)
    assets = {
        "kospi":  ("802Y001", "0001000"),    # KOSPI
        "kosdaq": ("802Y001", "0089000"),    # KOSDAQ
        "fx":     ("731Y001", "0000001"),    # 원/달러 환율 (종가)
        "bond":   ("817Y002", "010200000")   # 국고채 3년 금리
    }
    
    results = {}
    for key, (code, item) in assets.items():
        rows = get_ecos_statistic(code, "D", start_str, end_str, item)
        if isinstance(rows, dict) and "error" in rows:
            return {"error": f"{key} 오류: {rows['error']}"}
        results[key] = rows

    # [내부 함수] 데이터 리스트에서 가장 최신 값(오늘/전일)과 그 전날 값을 추출
    def process_asset_data(rows: List[Dict]) -> Dict[str, Any]:
        if not rows: return {"val": None, "prev": None}
        sorted_rows = sorted(rows, key=lambda x: x["TIME"])
        
        last_row = sorted_rows[-1]                                    # 가장 최신 데이터
        prev_row = sorted_rows[-2] if len(sorted_rows) >= 2 else None # 바로 이전 데이터
        
        val = float(last_row["DATA_VALUE"]) if last_row else None
        prev = float(prev_row["DATA_VALUE"]) if prev_row else None
        return {"val": val, "prev": prev}

    # [내부 함수] 등락률 계산 (%)
    def calc_change(curr, prev):
        if curr is None or prev in (None, 0): return 0.0
        return (curr / prev - 1.0) * 100.0

    # 각 자산별 데이터 처리
    data_map = {k: process_asset_data(v) for k, v in results.items()}
    
    # 프론트엔드 포맷에 맞춰 리스트 생성
    return {
        "indices": [
            {
                "name": "KOSPI",
                "value": f"{data_map['kospi']['val']:,.2f}" if data_map['kospi']['val'] else "-",
                "change": round(calc_change(data_map['kospi']['val'], data_map['kospi']['prev']), 1),
            },
            {
                "name": "KOSDAQ",
                "value": f"{data_map['kosdaq']['val']:,.2f}" if data_map['kosdaq']['val'] else "-",
                "change": round(calc_change(data_map['kosdaq']['val'], data_map['kosdaq']['prev']), 1),
            },
            {
                "name": "USD/KRW",
                "value": f"{data_map['fx']['val']:,.2f}" if data_map['fx']['val'] else "-",
                "change": round(calc_change(data_map['fx']['val'], data_map['fx']['prev']), 1),
            },
            {
                "name": "국고채 3년",
                "value": f"{data_map['bond']['val']:.2f}%" if data_map['bond']['val'] else "-",
                "change": round(calc_change(data_map['bond']['val'], data_map['bond']['prev']), 2),
            },
        ]
    }


# ==============================================================================
# 5. 차트/그래프용 데이터 최종 가공
# ==============================================================================

def get_macro_points(n: int = 6) -> Any:
    """
    도미노 차트(꺾은선 그래프)에 들어갈 데이터 포인트 리스트를 생성합니다.
    - 구조: [{date: "2024.01", rate: 3.5, stock: 2500}, ...]
    - 기준금리(월)와 KOSPI(월평균) 데이터를 날짜 기준으로 합칩니다.
    """
    try:
        # 위에서 정의한 함수들을 호출하여 데이터를 가져옵니다.
        rate_rows = get_policy_rate_last_n(n)
        kospi_rows = get_kospi_last_n(n)
    except Exception as e:
        return {"error": f"데이터 조회 오류: {e}"}

    # 에러 체크
    if isinstance(rate_rows, dict) and "error" in rate_rows: return rate_rows
    if isinstance(kospi_rows, dict) and "error" in kospi_rows: return kospi_rows

    # 매핑을 위해 KOSPI 데이터를 {날짜: 값} 형태의 딕셔너리로 변환
    kospi_map = {r["TIME"]: float(r["DATA_VALUE"]) for r in kospi_rows if "DATA_VALUE" in r}

    points = []
    # 기준금리 데이터를 기준으로 순회하며 KOSPI 값을 매칭
    for r in rate_rows:
        time_key = r.get("TIME", "")
        if not time_key: continue
            
        # "202401" -> "2024.01" 포맷 변경
        formatted_date = f"{time_key[:4]}.{time_key[4:]}" if len(time_key) == 6 else time_key
        
        try:
            rate_val = float(r.get("DATA_VALUE", 0))
        except:
            rate_val = 0.0

        points.append({
            "date": formatted_date,         # X축 라벨
            "rate": rate_val,               # Y1축 (금리)
            "stock": kospi_map.get(time_key)# Y2축 (주가)
        })
    
    # 반환 순서: 과거(왼쪽) -> 최신(오른쪽)
    return points