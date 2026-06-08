# dart.py
# 금융감독원 전자공시시스템(DART) API 연동 모듈
# - 기업설명회(IR) / 실적발표 공시 목록을 가져와 캘린더 이벤트 형식으로 변환합니다.

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from config import settings

# ==============================================================================
# 1. DART API 설정
# ==============================================================================

DART_API_KEY = settings.DART_API_KEY
DART_BASE_URL = "https://opendart.fss.or.kr/api"

# 공시 유형 코드
# I = 거래소공시 (기업설명회(IR)개최 포함)
# B = 주요사항보고 (영업(잠정)실적 포함)
PBLNTF_TYPES = [
    ("I", ["기업설명회"]),               # 거래소공시 → 기업설명회(IR)개최 필터
    ("B", ["잠정실적", "영업실적"]),      # 주요사항보고 → 잠정실적 필터
]

# 대형주 목록 (very_high 중요도 부여)
LARGE_CAP_NAMES = [
    "삼성전자", "SK하이닉스", "LG에너지솔루션", "삼성바이오로직스",
    "현대차", "기아", "POSCO", "포스코", "삼성SDI", "LG화학",
    "NAVER", "카카오", "현대모비스", "삼성물산", "셀트리온",
    "KB금융", "신한지주", "하나금융", "우리금융", "삼성생명",
]


# ==============================================================================
# 2. DART 공시 목록 조회
# ==============================================================================

def _fetch_dart_list(
    bgn_de: str,
    end_de: str,
    pblntf_ty: Optional[str] = None,
    page_no: int = 1,
    page_count: int = 100,
) -> Optional[List[Dict]]:
    """
    DART 공시 목록 API 호출.

    Args:
        bgn_de:     조회 시작일 (YYYYMMDD)
        end_de:     조회 종료일 (YYYYMMDD)
        pblntf_ty:  공시 유형 코드 (E=기타공시, B=주요사항보고, None=전체)
        page_no:    페이지 번호 (1부터)
        page_count: 페이지당 최대 건수 (최대 100)

    Returns:
        공시 항목 리스트. 오류 시 None, 정상 조회 결과 없음 시 빈 리스트.
    """
    if not DART_API_KEY:
        return []

    params: Dict[str, Any] = {
        "crtfc_key": DART_API_KEY,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "sort": "date",
        "sort_mth": "asc",
        "page_no": page_no,
        "page_count": page_count,
    }
    if pblntf_ty:
        params["pblntf_ty"] = pblntf_ty

    try:
        res = requests.get(f"{DART_BASE_URL}/list.json", params=params, timeout=20)
        if res.status_code != 200:
            return None

        data = res.json()
        # "000" = 정상, "013" = 조회 결과 없음
        status = data.get("status")
        if status == "013":
            return []
        if status != "000":
            return None

        return data.get("list") or []

    except Exception:
        return None


# ==============================================================================
# 3. 이벤트 변환 및 중요도 판정
# ==============================================================================

def _get_importance(corp_name: str) -> str:
    if any(name in corp_name for name in LARGE_CAP_NAMES):
        return "very_high"
    return "high"


def _to_calendar_event(item: Dict) -> Dict:
    """
    DART 공시 항목 → 프론트엔드 캘린더 이벤트 형식 변환.

    DART 원본 필드:
        rcept_dt   : 접수일자 (YYYYMMDD) — 이벤트 당일 또는 직전에 공시됨
        rcept_no   : 접수번호
        corp_name  : 회사명
        stock_code : 종목코드 (상장사만 존재)
        report_nm  : 보고서명
    """
    rcept_dt   = item.get("rcept_dt", "")
    rcept_no   = item.get("rcept_no", "")
    corp_name  = (item.get("corp_name", "") or "").strip()
    stock_code = (item.get("stock_code") or "").strip()
    report_nm  = (item.get("report_nm", "") or "").strip()

    # "20260601" → "2026-06-01T09:00:00"
    try:
        iso_dt = datetime.strptime(rcept_dt, "%Y%m%d").strftime("%Y-%m-%dT09:00:00")
    except ValueError:
        iso_dt = ""

    title = f"{corp_name} {report_nm}"

    return {
        "id":          f"dart-{rcept_no}",
        "title":       title,
        "datetime":    iso_dt,
        "country":     "KR",
        "type":        "EARNINGS",
        "importance":  _get_importance(corp_name),
        "description": title,
        "asset":       "all",
        "stockCode":   stock_code,
        "companyName": corp_name,
        "location":    "-",
    }


# ==============================================================================
# 4. 캐시 (24시간 TTL 인메모리 캐시)
# ==============================================================================

_cache: Dict[str, Any] = {}
_CACHE_TTL_SECONDS = 86400  # 24시간

def _cache_get(key: str) -> Optional[Dict]:
    entry = _cache.get(key)
    if not entry:
        return None
    if (datetime.now() - entry["ts"]).total_seconds() > _CACHE_TTL_SECONDS:
        del _cache[key]
        return None
    return entry["data"]

def _cache_set(key: str, data: Dict) -> None:
    _cache[key] = {"ts": datetime.now(), "data": data}


# ==============================================================================
# 5. 메인 함수: 캘린더용 실적·IR 일정 조회
# ==============================================================================

def get_dart_calendar(days_back: int = 30, days_ahead: int = 30) -> Dict[str, Any]:
    """
    DART API에서 기업설명회·잠정실적 공시를 가져와 캘린더 이벤트로 반환합니다.

    전략:
    - I타입(거래소공시):   "기업설명회" 키워드 → 기업설명회(IR)개최 포착
    - B타입(주요사항보고): "잠정실적/영업실적" 키워드 → 실적 발표 포착
    - 병렬 페이지 요청으로 속도 개선 (최대 7페이지 × 2타입)
    - 24시간 인메모리 캐시 적용
    """
    if not DART_API_KEY:
        return {
            "events":     [],
            "source":     "none",
            "fetched_at": datetime.now().isoformat(),
            "total":      0,
            "error":      "DART_API_KEY가 설정되지 않았습니다.",
        }

    today  = datetime.today()
    bgn_de = (today - timedelta(days=days_back)).strftime("%Y%m%d")
    end_de = (today + timedelta(days=days_ahead)).strftime("%Y%m%d")
    cache_key = f"dart_{bgn_de}_{end_de}"

    cached = _cache_get(cache_key)
    if cached:
        return cached

    MAX_PAGES = 7  # 7페이지 × 100건 = 700건/타입, 병렬로 ~5-8초

    def _extract_events(items: List[Dict], keywords: List[str]) -> List[Dict]:
        """items 리스트에서 키워드 매칭 항목만 이벤트로 변환해 반환 (순수 함수)."""
        result = []
        for item in items:
            if not any(kw in item.get("report_nm", "") for kw in keywords):
                continue
            ev = _to_calendar_event(item)
            if ev["datetime"]:
                result.append(ev)
        return result

    seen_ids: set = set()
    events:   List[Dict] = []
    had_fetch_error = False

    for pblntf_ty, keywords in PBLNTF_TYPES:
        first_page = _fetch_dart_list(bgn_de, end_de, pblntf_ty=pblntf_ty,
                                      page_no=1, page_count=100)
        if first_page is None:
            had_fetch_error = True
            continue
        if not first_page:
            continue

        # 첫 페이지 처리 (직렬)
        for ev in _extract_events(first_page, keywords):
            if ev["id"] not in seen_ids:
                seen_ids.add(ev["id"])
                events.append(ev)

        if len(first_page) < 100:
            continue  # 1페이지로 끝

        # 2~MAX_PAGES 를 병렬로 요청
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_map = {
                executor.submit(
                    _fetch_dart_list, bgn_de, end_de, pblntf_ty, p, 100
                ): p
                for p in range(2, MAX_PAGES + 1)
            }
            for future in as_completed(future_map):
                page_items = future.result()
                if page_items is None:
                    had_fetch_error = True
                    continue
                for ev in _extract_events(page_items, keywords):
                    if ev["id"] not in seen_ids:
                        seen_ids.add(ev["id"])
                        events.append(ev)

    events.sort(key=lambda e: e["datetime"])

    if had_fetch_error and not events:
        return {
            "events":     [],
            "source":     "dart_unavailable",
            "fetched_at": datetime.now().isoformat(),
            "total":      0,
            "error":      "DART API 응답을 가져오지 못했습니다.",
        }

    result = {
        "events":     events,
        "source":     "dart_partial" if had_fetch_error else "dart",
        "fetched_at": datetime.now().isoformat(),
        "total":      len(events),
    }
    _cache_set(cache_key, result)
    return result


# ==============================================================================
# 5. 디버그용: 원본 DART 응답 확인
# ==============================================================================

def get_dart_raw_sample(days_back: int = 7, pblntf_ty: str = "I") -> Dict[str, Any]:
    """
    디버그용. DART 원본 응답 최대 10건 반환.
    /api/calendar/dart-debug 엔드포인트에서 사용합니다.
    """
    today  = datetime.today()
    bgn_de = (today - timedelta(days=days_back)).strftime("%Y%m%d")
    end_de = today.strftime("%Y%m%d")

    items = _fetch_dart_list(bgn_de, end_de, pblntf_ty=pblntf_ty,
                             page_no=1, page_count=10)
    return {
        "pblntf_ty": pblntf_ty,
        "bgn_de":    bgn_de,
        "end_de":    end_de,
        "count":     len(items),
        "items":     items,
    }
