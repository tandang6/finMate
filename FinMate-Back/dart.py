# dart.py
# 금융감독원 전자공시시스템(DART) API 연동 모듈
# - 실적·잠정실적 공시와 실적 관련 IR 일정을 캘린더 이벤트 형식으로 변환합니다.

import html
import io
import re
import requests
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from config import settings

# ==============================================================================
# 1. DART API 설정
# ==============================================================================

DART_API_KEY = settings.DART_API_KEY
DART_BASE_URL = "https://opendart.fss.or.kr/api"

# 공시 유형 코드
# I = 거래소공시. 영업(잠정)실적(공정공시)와 기업설명회(IR)가 모두 섞여 들어옵니다.
EARNINGS_REPORT_KEYWORDS = [
    "영업(잠정)실적",
    "영업실적",
    "잠정실적",
    "실적발표",
    "경영실적 발표",
    "경영실적발표",
    "분기실적",
]

IR_REPORT_KEYWORDS = ["기업설명회"]

PBLNTF_TYPES = [
    (
        "I",
        EARNINGS_REPORT_KEYWORDS + IR_REPORT_KEYWORDS,
    ),
]

# 대형주 목록 (very_high 중요도 부여)
LARGE_CAP_NAMES = [
    "삼성전자", "SK하이닉스", "LG에너지솔루션", "삼성바이오로직스",
    "현대차", "기아", "POSCO", "포스코", "삼성SDI", "LG화학",
    "NAVER", "카카오", "현대모비스", "삼성물산", "셀트리온",
    "KB금융", "신한지주", "하나금융", "우리금융", "삼성생명",
]

# Toss 증시캘린더처럼 국내 주요 기업의 실적발표 일정을 우선 노출하기 위한 범위입니다.
# DART 기업설명회 원문 조회는 비용이 있으므로 이 목록에 해당하는 회사만 상세 확인합니다.
EARNINGS_CALENDAR_COMPANY_NAMES = tuple(
    dict.fromkeys(
        LARGE_CAP_NAMES
        + [
            "현대자동차",
            "LG전자",
            "LG이노텍",
            "LG",
            "SK",
            "SK텔레콤",
            "SK스퀘어",
            "SK이노베이션",
            "SKC",
            "삼성전기",
            "삼성에스디에스",
            "삼성SDS",
            "삼성화재",
            "삼성카드",
            "HD현대",
            "HD현대일렉트릭",
            "HD현대중공업",
            "HD한국조선해양",
            "HD현대미포",
            "두산에너빌리티",
            "한화에어로스페이스",
            "한화솔루션",
            "현대건설",
            "현대글로비스",
            "현대제철",
            "대한항공",
            "크래프톤",
            "엔씨소프트",
            "아모레퍼시픽",
            "KT",
            "KT&G",
            "카카오뱅크",
            "카카오페이",
        ]
    )
)

EARNINGS_IR_TEXT_KEYWORDS = [
    "실적",
    "경영실적",
    "분기실적",
    "결산실적",
    "실적발표",
    "어닝콜",
    "earnings",
    "quarterly results",
]

IR_EVENT_DATE_LABELS = [
    "개최일시",
    "행사일시",
    "설명회일시",
    "IR일정",
    "일시",
]

MAX_IR_DETAIL_FETCHES = 80

_DATE_TIME_RE = re.compile(
    r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?"
    r"(?:\s*(\d{1,2})\s*(?::|시)\s*(\d{2})?)?",
    re.IGNORECASE,
)


# ==============================================================================
# 2. DART 공시 목록 조회
# ==============================================================================

def _fetch_dart_list(
    bgn_de: str,
    end_de: str,
    pblntf_ty: Optional[str] = None,
    page_no: int = 1,
    page_count: int = 100,
) -> List[Dict]:
    """
    DART 공시 목록 API 호출.

    Args:
        bgn_de:     조회 시작일 (YYYYMMDD)
        end_de:     조회 종료일 (YYYYMMDD)
        pblntf_ty:  공시 유형 코드 (E=기타공시, B=주요사항보고, None=전체)
        page_no:    페이지 번호 (1부터)
        page_count: 페이지당 최대 건수 (최대 100)

    Returns:
        공시 항목 리스트. 오류/결과 없음 시 빈 리스트.
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
            return []

        data = res.json()
        # "000" = 정상, "013" = 조회 결과 없음
        if data.get("status") not in ("000", "013"):
            return []

        return data.get("list") or []

    except Exception:
        return []


def _fetch_dart_document_text(rcept_no: str) -> str:
    """
    DART 공시 원문(document.xml)을 텍스트로 변환합니다.

    기업설명회(IR) 목록 제목만으로는 실적발표 일정인지 구분하기 어렵기 때문에,
    원문에 "경영실적", "실적발표", "어닝콜" 같은 문구가 있는지 확인합니다.
    """
    if not DART_API_KEY or not rcept_no:
        return ""

    params = {
        "crtfc_key": DART_API_KEY,
        "rcept_no": rcept_no,
    }

    try:
        res = requests.get(f"{DART_BASE_URL}/document.xml", params=params, timeout=20)
        if res.status_code != 200:
            return ""

        payload = io.BytesIO(res.content)
        if zipfile.is_zipfile(payload):
            payload.seek(0)
            chunks: List[str] = []
            with zipfile.ZipFile(payload) as archive:
                for name in archive.namelist():
                    if name.endswith("/"):
                        continue
                    chunks.append(_strip_markup(_decode_bytes(archive.read(name))))
            return " ".join(chunk for chunk in chunks if chunk)

        return _strip_markup(_decode_bytes(res.content))

    except Exception:
        return ""


def _decode_bytes(raw: bytes) -> str:
    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _strip_markup(text: str) -> str:
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# ==============================================================================
# 3. 이벤트 변환 및 중요도 판정
# ==============================================================================

def _get_importance(corp_name: str) -> str:
    if any(name in corp_name for name in LARGE_CAP_NAMES):
        return "very_high"
    return "high"


def _normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _contains_keyword(value: str, keywords: List[str]) -> bool:
    normalized_value = _normalize_for_match(value).lower()
    return any(_normalize_for_match(keyword).lower() in normalized_value for keyword in keywords)


def _is_direct_earnings_report(report_name: str) -> bool:
    return _contains_keyword(report_name, EARNINGS_REPORT_KEYWORDS) and not _contains_keyword(
        report_name,
        IR_REPORT_KEYWORDS,
    )


def _is_ir_report(report_name: str) -> bool:
    return _contains_keyword(report_name, IR_REPORT_KEYWORDS)


def _is_calendar_company(corp_name: str) -> bool:
    normalized_corp = _normalize_for_match(corp_name)
    for name in EARNINGS_CALENDAR_COMPANY_NAMES:
        normalized_name = _normalize_for_match(name)
        if len(normalized_name) <= 2:
            if normalized_corp == normalized_name:
                return True
            continue
        if normalized_name in normalized_corp:
            return True
    return False


def _is_earnings_ir_text(text: str) -> bool:
    return _contains_keyword(text, EARNINGS_IR_TEXT_KEYWORDS)


def _format_rcept_datetime(rcept_dt: str) -> str:
    try:
        return datetime.strptime(rcept_dt, "%Y%m%d").strftime("%Y-%m-%dT09:00:00")
    except ValueError:
        return ""


def _parse_datetime_match(match: re.Match) -> Optional[str]:
    year, month, day, hour, minute = match.groups()
    try:
        parsed = datetime(
            int(year),
            int(month),
            int(day),
            int(hour or 9),
            int(minute or 0),
        )
    except ValueError:
        return None
    return parsed.strftime("%Y-%m-%dT%H:%M:00")


def _extract_event_datetime_from_text(text: str) -> Optional[str]:
    normalized = re.sub(r"\s+", " ", text or "")
    if not normalized:
        return None

    for corpus in (normalized, _normalize_for_match(normalized)):
        for label in IR_EVENT_DATE_LABELS:
            search_label = _normalize_for_match(label) if corpus != normalized else label
            search_from = 0
            while True:
                idx = corpus.find(search_label, search_from)
                if idx == -1:
                    break
                window = corpus[idx : idx + 140]
                match = _DATE_TIME_RE.search(window)
                if match:
                    parsed = _parse_datetime_match(match)
                    if parsed:
                        return parsed
                search_from = idx + len(search_label)

    return None


def _to_calendar_event(item: Dict, *, event_kind: str = "result", document_text: str = "") -> Dict:
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
    corp_name  = item.get("corp_name", "")
    stock_code = item.get("stock_code") or ""
    report_nm  = item.get("report_nm", "")

    iso_dt = _format_rcept_datetime(rcept_dt)
    calendar_category = "earnings_result"
    source_detail = "dart_result"
    title = f"{corp_name} {report_nm}"
    description = title

    if event_kind == "ir_schedule":
        iso_dt = _extract_event_datetime_from_text(document_text) or iso_dt
        calendar_category = "earnings_schedule"
        source_detail = "dart_ir"
        title = f"{corp_name} 실적발표"
        description = f"{corp_name} 실적발표 일정 ({report_nm})"

    return {
        "id":          f"dart-{rcept_no}",
        "title":       title,
        "datetime":    iso_dt,
        "country":     "KR",
        "type":        "EARNINGS",
        "importance":  _get_importance(corp_name),
        "description": description,
        "asset":       "all",
        "stockCode":   stock_code,
        "companyName": corp_name,
        "rceptNo":     rcept_no,
        "source":      "dart",
        "sourceDetail": source_detail,
        "calendarCategory": calendar_category,
        "rawReportName": report_nm,
        "location":    "-",
    }


def _dedupe_company_day_events(events: List[Dict]) -> List[Dict]:
    """
    같은 회사/날짜에 실적 IR 일정과 잠정실적 공시가 같이 잡히면 일정 쪽을 우선합니다.
    """
    priority = {
        "earnings_schedule": 0,
        "earnings_result": 1,
    }
    selected: Dict[Tuple[str, str], Dict] = {}

    for event in events:
        key = (
            event.get("companyName", ""),
            (event.get("datetime") or "")[:10],
        )
        current = selected.get(key)
        if current is None:
            selected[key] = event
            continue

        event_rank = priority.get(event.get("calendarCategory"), 9)
        current_rank = priority.get(current.get("calendarCategory"), 9)
        if event_rank < current_rank:
            selected[key] = event

    return list(selected.values())


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
# 5. 메인 함수: 캘린더용 실적 일정 조회
# ==============================================================================

def get_dart_calendar(days_back: int = 30, days_ahead: int = 30) -> Dict[str, Any]:
    """
    DART API에서 실적 공시와 실적 관련 IR 일정을 가져와 캘린더 이벤트로 반환합니다.

    전략:
    - I타입(거래소공시): "영업(잠정)실적(공정공시)" 계열 포착
    - 기업설명회(IR)는 원문 문서에 실적/경영실적 문구가 있을 때만 일정으로 노출
    - 일반 기업설명회(IR)는 숨김
    - 병렬 페이지 요청으로 속도 개선
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
    ir_detail_fetches = 0

    def _extract_events(items: List[Dict], keywords: List[str]) -> List[Dict]:
        """items 리스트에서 키워드 매칭 항목만 이벤트로 변환해 반환 (순수 함수)."""
        nonlocal ir_detail_fetches
        result = []
        for item in items:
            report_name = item.get("report_nm", "")
            corp_name = item.get("corp_name", "")

            if not _contains_keyword(report_name, keywords):
                continue

            if _is_direct_earnings_report(report_name):
                if not _is_calendar_company(corp_name):
                    continue
                ev = _to_calendar_event(item, event_kind="result")
            elif _is_ir_report(report_name):
                if not _is_calendar_company(corp_name):
                    continue
                if ir_detail_fetches >= MAX_IR_DETAIL_FETCHES:
                    continue
                ir_detail_fetches += 1
                document_text = _fetch_dart_document_text(item.get("rcept_no", ""))
                if not _is_earnings_ir_text(document_text):
                    continue
                ev = _to_calendar_event(
                    item,
                    event_kind="ir_schedule",
                    document_text=document_text,
                )
            else:
                continue

            if ev["datetime"]:
                result.append(ev)
        return result

    seen_ids: set = set()
    events:   List[Dict] = []

    for pblntf_ty, keywords in PBLNTF_TYPES:
        first_page = _fetch_dart_list(bgn_de, end_de, pblntf_ty=pblntf_ty,
                                      page_no=1, page_count=100)
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
                page_items = future.result() or []
                for ev in _extract_events(page_items, keywords):
                    if ev["id"] not in seen_ids:
                        seen_ids.add(ev["id"])
                        events.append(ev)

    events = _dedupe_company_day_events(events)
    events.sort(key=lambda e: e["datetime"])

    result = {
        "events":     events,
        "source":     "dart",
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
