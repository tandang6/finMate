import requests
import json
import sys

# ⚠️ 여기에 고객님의 한국은행 ECOS API 인증키를 넣어주세요.
ECOS_AUTH_KEY = "3HEAP0CVSRNLAPF7WG38" 
ECOS_BASE_URL = "http://ecos.bok.or.kr/api"

def search_ecos_glossary_term(term: str):
    """
    한국은행 ECOS API의 'StatisticWord' 서비스를 사용하여 특정 통계 용어를 검색합니다.
    """
    if not ECOS_AUTH_KEY or ECOS_AUTH_KEY == "YOUR_ECOS_API_KEY":
        return {"error": "ECOS_AUTH_KEY를 설정해야 합니다."}

    # 명세서에 따른 URL 경로 구성
    # URL 구조: /StatisticWord/인증키/json/kr/1/10/검색_용어
    url_path = (f"StatisticWord/{ECOS_AUTH_KEY}/json/kr/1/10/" 
                f"{term}") # 검색할 용어를 URL에 직접 인코딩
    
    # URL 인코딩 (한글 용어가 URL에 안전하게 들어갈 수 있도록 처리)
    import urllib.parse
    encoded_term_path = urllib.parse.quote(term, encoding='utf-8')
    url_path = (f"StatisticWord/{ECOS_AUTH_KEY}/json/kr/1/10/"
                f"{encoded_term_path}")
    
    request_url = f"{ECOS_BASE_URL}/{url_path}"
    
    print(f"\n[도구 사용] 📚 ECOS 용어 검색 중: '{term}'")
    
    try:
        response = requests.get(request_url, timeout=10)
        
        # ⚠️ JSON 디코딩 전, 서버가 오류 메시지(비 JSON)를 보냈는지 확인합니다.
        # 응답 코드가 200이 아니거나, 내용이 예상되는 JSON 구조가 아니면 오류 처리
        if response.status_code != 200:
            return {"error": f"HTTP 오류 발생: {response.status_code}", "detail": response.text[:50]}
            
        data = response.json()
        
        # 명세서에 따른 응답 구조: StatisticWord
        if 'StatisticWord' in data:
            result = data['StatisticWord']
            if result['list_total_count'] > 0:
                # 용어와 정의를 딕셔너리로 반환
                row = result['row'][0] # 첫 번째 검색 결과
                return {
                    "용어": row.get('WORD'),
                    "용어설명": row.get('CONTENT')
                }
            else:
                return {"message": f"용어 '{term}'에 대한 검색 결과가 없습니다."}
        elif data.get('RESULT', {}).get('CODE') != '000':
            # KIS처럼 오류 코드가 있는 경우 (인증키 오류 등)
            return {"error": data['RESULT']['MESSAGE'], "code": data['RESULT']['CODE']}
        
        return {"error": "API 응답은 받았으나 알 수 없는 형식입니다."}

    except requests.exceptions.JSONDecodeError:
         return {"error": "API 서버에서 JSON 형식이 아닌 데이터(인증키/IP 오류 메시지)를 받았습니다."}
    except Exception as e:
        return {"error": f"네트워크 또는 파싱 오류: {str(e)}"}

    
# =================================================================
# ECOS 통계표 조회 공통 함수 (StatisticSearch)
# =================================================================
def get_ecos_statistic(stat_code: str, cycle: str, start: str, end: str, item_code: str = ""):
    """
    ECOS StatisticSearch 호출용 공통 함수
    예)
      stat_code = "722Y001"   → 기준금리
      cycle = "M"             → 월별
      start = "202301"
      end = "202512"
    """
    if not ECOS_AUTH_KEY:
        return {"error": "ECOS_AUTH_KEY가 없습니다."}

    url = (
        f"{ECOS_BASE_URL}/StatisticSearch/"
        f"{ECOS_AUTH_KEY}/json/kr/1/500/"
        f"{stat_code}/{cycle}/{start}/{end}/{item_code}"
    )

    print(f"\n[ECOS 호출] 통계표 {stat_code} 조회 중...")

    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return {"error": f"HTTP 오류: {res.status_code}", "detail": res.text[:100]}

        data = res.json()

        if "StatisticSearch" not in data:
            return {"error": f"응답 구조가 이상함: {data}"}

        return data["StatisticSearch"].get("row", [])

    except Exception as e:
        return {"error": f"네트워크 오류: {str(e)}"}

import requests
import json
import sys
import datetime
import urllib.parse
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from typing import List, Dict, Any, Union

# =================================================================
# 1) 최근 기준금리 N개 가져오기 (722Y001, 월별) - 날짜 고정
# =================================================================
def get_policy_rate_last_n(n: int = 6):
    """
    최근 기준금리 N개 가져오기 (월별)
    - 통계표 코드: 722Y001
    - ITEM_CODE: 0101000 (한국은행 기준금리)
    """
    # ⚠️ 날짜 고정 요청에 따라 2025년 전체 기간으로 설정
    start_date = "202501"
    end_date = "202512"

    rows = get_ecos_statistic(
        stat_code="722Y001",
        cycle="M",
        start=start_date,
        end=end_date,
        item_code="0101000"
    )

    if isinstance(rows, dict) and "error" in rows:
        return rows  # 오류 그대로 반환

    rows_sorted = sorted(rows, key=lambda r: r["TIME"])
    return rows_sorted[-n:]



# =================================================================
# 2) 최근 KOSPI 지수 N개 가져오기 (802Y001, 일별 조회 후, 월평균 계산) - 날짜 고정
# 금리와 맞추기 위해 마지막 날짜를 한달전으로 설정
# =================================================================
def get_kospi_last_n(n: int = 6):
    """
    최근 KOSPI 지수 N개 조회 (일별 데이터를 조회 후 월평균으로 계산)
    - 통계표 코드: 802Y001 (주식시장-일별)
    """
    # ⚠️ 날짜 고정 요청에 따라 원본과 유사하게 2025년 기간으로 설정
    start_date = "20250101" 
    end_date = "20251131" # 12월 12일 대신 31일로 설정하여 연말까지의 데이터를 포함

    # API를 통해 일별 데이터 조회
    rows = get_ecos_statistic(
        stat_code="802Y001",
        cycle="D", 
        start=start_date, 
        end=end_date,
        item_code="0001000" 
    )

    if isinstance(rows, dict) and "error" in rows:
        return rows  # 오류 그대로 반환

    # --- 1. 일별 데이터를 월별로 그룹화 및 평균 계산 (가공 로직) ---
    monthly_data = defaultdict(lambda: {"total": 0.0, "count": 0})
    
    for row in rows:
        time_str = row["TIME"]
        month_key = time_str[:6] # 'YYYYMM' 형식의 월별 키
        
        try:
            value = float(row["DATA_VALUE"])
            monthly_data[month_key]["total"] += value
            monthly_data[month_key]["count"] += 1
        except ValueError:
            continue

    # --- 2. 최종 월 평균 계산 및 리스트 생성 ---
    result_list = []
    for month_key, data in monthly_data.items():
        if data["count"] > 0:
            avg_value = data["total"] / data["count"]
            result_list.append({
                "TIME": month_key,                 
                "DATA_VALUE": f"{avg_value:.2f}", 
                "UNIT_NAME": "월평균 KOSPI 지수"
            })
    
    # --- 3. TIME 오름차순 정렬 후 최근 N개만 가져오기 ---
    result_sorted = sorted(result_list, key=lambda r: r["TIME"])
    return result_sorted[-n:]



# =================================================================
# 4) KOSPI / KOSDAQ / 환율 / 국고채 3년 - 최근 값 + 전일 대비 변화
# =================================================================
def get_last_one():
    """
    2025-12-09 ~ 2025-12-10 사이의
    KOSPI / KOSDAQ / 원달러 환율 / 국고채 3년 수익률을 조회하고

    - 가장 최근 값 (마지막 일자)
    - 전일 대비 % 변화

    를 계산해서 프론트에서 바로 쓸 수 있는 형태로 반환.
    """

    start_date = "20251208"
    end_date = "20251209"

    # 1) 자산별 ECOS 호출 -----------------------------------------
    kospi_rows = get_ecos_statistic(
        stat_code="802Y001",
        cycle="D",
        start=start_date,
        end=end_date,
        item_code="0001000",   # KOSPI
    )

    kosdaq_rows = get_ecos_statistic(
        stat_code="802Y001",
        cycle="D",
        start=start_date,
        end=end_date,
        item_code="0089000",   # KOSDAQ
    )

    fx_rows = get_ecos_statistic(
        stat_code="731Y001",
        cycle="D",
        start=start_date,
        end=end_date,
        item_code="0000001",   # 원/달러 환율
    )

    bond_rows = get_ecos_statistic(
        stat_code="817Y002",
        cycle="D",
        start=start_date,
        end=end_date,
        item_code="010200000",  # 국고채 3년 수익률
    )

    # 2) 에러 체크 -------------------------------------------------
    for name, rows in [
        ("kospi", kospi_rows),
        ("kosdaq", kosdaq_rows),
        ("fx", fx_rows),
        ("bond", bond_rows),
    ]:
        if isinstance(rows, dict) and "error" in rows:
            # 어디서 에러 났는지 함께 알려주기
            return {"error": f"{name} 조회 실패: {rows['error']}"}

    # 3) 마지막/전날 값 꺼내는 헬퍼 -------------------------------
    def last_two_values(rows):
        """
        rows: ECOS 응답 리스트
        return: (last_value: float | None, prev_value: float | None)
        """
        if not isinstance(rows, list) or len(rows) == 0:
            return None, None

        # 가장 최근 값
        last = rows[-1]
        # 그 전날 값 (없을 수도 있음)
        prev = rows[-2] if len(rows) >= 2 else None

        def to_float(row):
            if row is None:
                return None
            try:
                return float(row.get("DATA_VALUE"))
            except (TypeError, ValueError):
                return None

        return to_float(last), to_float(prev)

    def calc_change_pct(last, prev):
        """
        전일 대비 % 변화 계산 (prev가 없거나 0이면 0으로 처리)
        """
        if last is None or prev in (None, 0):
            return 0.0
        return (last / prev - 1.0) * 100.0

    # 4) 각 자산별 값/변화 계산 -----------------------------------
    kospi_last, kospi_prev = last_two_values(kospi_rows)
    kosdaq_last, kosdaq_prev = last_two_values(kosdaq_rows)
    fx_last, fx_prev = last_two_values(fx_rows)
    bond_last, bond_prev = last_two_values(bond_rows)

    kospi_change = calc_change_pct(kospi_last, kospi_prev)
    kosdaq_change = calc_change_pct(kosdaq_last, kosdaq_prev)
    fx_change = calc_change_pct(fx_last, fx_prev)

    # 국고채는 보통 '퍼센트포인트' 차이를 보기도 하지만,
    # 프론트에서는 그냥 %로 찍으니까 일단 % 변화로 통일
    bond_change = calc_change_pct(bond_last, bond_prev)

    # 5) 프론트에서 바로 쓸 수 있는 형태로 묶어서 반환 ------------
    #  - value는 문자열로 포맷
    #  - change는 소수 1~2자리 정도로 반올림
    return {
        "indices": [
            {
                "name": "KOSPI",
                "value": f"{kospi_last:,.2f}" if kospi_last is not None else "-",
                "change": round(kospi_change, 1),
            },
            {
                "name": "KOSDAQ",
                "value": f"{kosdaq_last:,.2f}" if kosdaq_last is not None else "-",
                "change": round(kosdaq_change, 1),
            },
            {
                "name": "USD/KRW",
                "value": f"{fx_last:,.2f}" if fx_last is not None else "-",
                "change": round(fx_change, 1),
            },
            {
                "name": "국고채 3년",
                "value": f"{bond_last:.2f}%" if bond_last is not None else "-",
                "change": round(bond_change, 2),
            },
        ]
    }




