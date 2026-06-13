from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from config import settings
from dart import _fetch_dart_document_text, _fetch_dart_list, _is_direct_earnings_report
from market_data.provider import MarketDataProvider
from market_data.public_data_provider import get_public_data_market_data_provider
from market_data.types import DailyBar, MarketDataStatus


PostResultStatus = Literal[
    "available",
    "partial",
    "unavailable",
    "not_available",
    "manual_required",
]


class CalendarPostResultRequest(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str = ""
    title: str
    datetime: str
    type: str = ""
    country: str = ""
    source: str = ""
    company_name: str = Field(default="", alias="companyName")
    stock_code: str = Field(default="", alias="stockCode")
    rcept_no: str = Field(default="", alias="rceptNo")


class CalendarPostResultItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    k: str
    v: str
    note: str | None = None


class CalendarPostResultSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    status: PostResultStatus
    source: str | None = None
    items: list[CalendarPostResultItem] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class CalendarPostResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eventId: str
    status: Literal["available", "partial", "unavailable"]
    sourceNote: str
    earnings: CalendarPostResultSection
    priceMove: CalendarPostResultSection
    commentary: CalendarPostResultSection


@dataclass(frozen=True)
class DartEarningsMetric:
    label: str
    value: str
    note: str | None = None


@dataclass(frozen=True)
class DartEarningsData:
    metrics: list[DartEarningsMetric]
    rcept_no: str
    report_name: str
    unit: str | None = None


EARNINGS_METRIC_ALIASES: list[tuple[str, list[str]]] = [
    ("매출", ["매출액", "영업수익", "수익(매출액)"]),
    ("영업이익", ["영업이익"]),
    ("순이익", ["당기순이익", "분기순이익", "반기순이익", "연결당기순이익"]),
]

CURRENT_PERIOD_MARKERS = [
    "당해실적",
    "당기실적",
    "금기실적",
    "당분기",
    "당반기",
    "당기",
]

_NUMBER_RE = re.compile(
    r"\(?[-−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|\(?[-−]?\d+(?:\.\d+)?\)?"
)
_UNIT_RE = re.compile(r"단위\s*[:：]?\s*([가-힣A-Za-z$]+)")


@lru_cache(maxsize=1)
def get_calendar_post_result_provider() -> MarketDataProvider | None:
    if not settings.DATA_GO_KR_SERVICE_KEY:
        return None
    return get_public_data_market_data_provider()


def build_calendar_post_result(
    event: CalendarPostResultRequest,
    *,
    provider: MarketDataProvider | None = None,
) -> CalendarPostResultResponse:
    fixture = _build_fixture_response(event)
    if fixture is not None:
        return fixture

    earnings = _build_earnings_section(event)
    price_move = _build_price_move_section(event, provider=provider)
    commentary = _build_commentary_section(event, earnings, price_move)

    return CalendarPostResultResponse(
        eventId=_event_id(event),
        status=_combine_response_status(earnings, price_move),
        sourceNote=_build_source_note(earnings, price_move),
        earnings=earnings,
        priceMove=price_move,
        commentary=commentary,
    )


def _build_fixture_response(event: CalendarPostResultRequest) -> CalendarPostResultResponse | None:
    event_date = _parse_event_date(event.datetime)
    is_samsung_demo = (
        event.id == "kr-earnings-37"
        or (event.stock_code == "005930" and event_date == date(2025, 10, 30))
    )
    if not is_samsung_demo:
        return None

    earnings = CalendarPostResultSection(
        title="2025년 3분기 실적",
        status="available",
        source="시연용 고정 데이터",
        items=[
            CalendarPostResultItem(k="매출", v="79조 1,400억원 (시연용)"),
            CalendarPostResultItem(k="영업이익", v="12조 1,600억원 (시연용)"),
            CalendarPostResultItem(k="순이익", v="9조 8,800억원 (시연용)"),
            CalendarPostResultItem(k="포인트", v="메모리 가격 반등 + AI 수요 기대감 (시연용)"),
        ],
    )
    price_move = CalendarPostResultSection(
        title="발표 직후 주가 반응",
        status="available",
        source="시연용 고정 데이터",
        items=[
            CalendarPostResultItem(k="당일", v="+3.2% (시연용)"),
            CalendarPostResultItem(k="장중 변동", v="초반 급등 후 일부 차익실현 (시연용)"),
            CalendarPostResultItem(k="거래량", v="평균 대비 증가 (시연용)"),
        ],
    )
    commentary = CalendarPostResultSection(
        title="해설",
        status="available",
        source="시연용 고정 데이터",
        bullets=[
            "결과가 기대 대비 상회하면 단기적으로 매수세가 유입되기 쉽습니다.",
            "가이던스나 업황 코멘트가 약하면 발표 직후 차익실현이 나올 수 있습니다.",
            "발표 후 1~3거래일은 수급과 기술적 저항 구간 확인이 핵심입니다.",
        ],
    )
    return CalendarPostResultResponse(
        eventId=_event_id(event),
        status="available",
        sourceNote="이 이벤트는 촬영/시연을 위해 보존된 고정 데이터입니다.",
        earnings=earnings,
        priceMove=price_move,
        commentary=commentary,
    )


def _build_earnings_section(event: CalendarPostResultRequest) -> CalendarPostResultSection:
    earnings_data = _load_dart_earnings_data(event)
    if not earnings_data or not earnings_data.metrics:
        items = [
            CalendarPostResultItem(k="공시 제목", v=event.title),
            CalendarPostResultItem(k="회사", v=event.company_name or "-"),
            CalendarPostResultItem(k="종목코드", v=event.stock_code or "-"),
        ]
        rcept_no = _rcept_no(event)
        if rcept_no:
            items.append(CalendarPostResultItem(k="DART 접수번호", v=rcept_no))
        items.append(
            CalendarPostResultItem(
                k="상태",
                v="OpenDART 원문에서 매출/영업이익/순이익 수치를 자동 확인하지 못했습니다.",
            )
        )
        return CalendarPostResultSection(
            title="실적 발표 결과",
            status="unavailable" if rcept_no else "not_available",
            source="OpenDART 공시 원문",
            items=items,
        )

    items = [
        CalendarPostResultItem(k=metric.label, v=metric.value, note=metric.note)
        for metric in earnings_data.metrics
    ]
    items.extend(
        [
            CalendarPostResultItem(k="회사", v=event.company_name or "-"),
            CalendarPostResultItem(k="종목코드", v=event.stock_code or "-"),
            CalendarPostResultItem(k="DART 접수번호", v=earnings_data.rcept_no),
        ]
    )

    status: PostResultStatus = "available" if len(earnings_data.metrics) >= 2 else "partial"
    return CalendarPostResultSection(
        title="실적 발표 결과",
        status=status,
        source="OpenDART 공시 원문",
        items=items,
        bullets=[earnings_data.report_name] if earnings_data.report_name else [],
    )


def _load_dart_earnings_data(event: CalendarPostResultRequest) -> DartEarningsData | None:
    rcept_no = _rcept_no(event)
    if rcept_no:
        data = _parse_dart_earnings_document(
            _fetch_dart_document_text(rcept_no),
            rcept_no=rcept_no,
            report_name=event.title,
        )
        if data and data.metrics:
            return data

    related = _find_related_earnings_filing(event)
    if not related:
        return None

    related_rcept_no = related.get("rcept_no", "")
    return _parse_dart_earnings_document(
        _fetch_dart_document_text(related_rcept_no),
        rcept_no=related_rcept_no,
        report_name=related.get("report_nm", ""),
    )


def _find_related_earnings_filing(event: CalendarPostResultRequest) -> dict | None:
    event_date = _parse_event_date(event.datetime)
    if event_date is None:
        return None

    bgn_de = (event_date - timedelta(days=10)).strftime("%Y%m%d")
    end_de = (event_date + timedelta(days=10)).strftime("%Y%m%d")
    matches: list[dict] = []

    for page_no in range(1, 4):
        items = _fetch_dart_list(
            bgn_de,
            end_de,
            pblntf_ty="I",
            page_no=page_no,
            page_count=100,
        )
        if not items:
            break
        for item in items:
            if not _is_same_company_event(event, item):
                continue
            if not _is_direct_earnings_report(item.get("report_nm", "")):
                continue
            matches.append(item)
        if len(items) < 100:
            break

    if not matches:
        return None

    def sort_key(item: dict) -> tuple[int, str]:
        try:
            filing_date = datetime.strptime(item.get("rcept_dt", ""), "%Y%m%d").date()
            day_gap = abs((filing_date - event_date).days)
        except ValueError:
            day_gap = 999
        return (day_gap, item.get("rcept_dt", ""))

    return sorted(matches, key=sort_key)[0]


def _is_same_company_event(event: CalendarPostResultRequest, item: dict) -> bool:
    event_stock = event.stock_code.strip()
    item_stock = (item.get("stock_code") or "").strip()
    if event_stock and item_stock and event_stock == item_stock:
        return True

    event_name = _normalize_text(event.company_name)
    item_name = _normalize_text(item.get("corp_name", ""))
    if not event_name or not item_name:
        return False
    return event_name == item_name or event_name in item_name or item_name in event_name


def _parse_dart_earnings_document(
    document_text: str,
    *,
    rcept_no: str,
    report_name: str,
) -> DartEarningsData | None:
    normalized = re.sub(r"\s+", " ", document_text or "").strip()
    if not normalized:
        return None

    unit = _extract_dart_unit(normalized)
    metrics: list[DartEarningsMetric] = []
    used_labels: set[str] = set()

    for label, aliases in EARNINGS_METRIC_ALIASES:
        if label in used_labels:
            continue
        parsed_value = _extract_metric_value(normalized, aliases)
        if parsed_value is None:
            continue
        raw_value, display_value = parsed_value
        note = f"원문: {raw_value}{(' ' + unit) if unit else ''}"
        metrics.append(DartEarningsMetric(label=label, value=_format_metric_value(display_value, unit), note=note))
        used_labels.add(label)

    if not metrics:
        return None

    return DartEarningsData(
        metrics=metrics,
        rcept_no=rcept_no,
        report_name=report_name,
        unit=unit,
    )


def _extract_dart_unit(text: str) -> str | None:
    match = _UNIT_RE.search(text)
    if not match:
        return None
    return match.group(1).strip()


def _extract_metric_value(text: str, aliases: list[str]) -> tuple[str, float] | None:
    all_aliases = [alias for _, group in EARNINGS_METRIC_ALIASES for alias in group]
    for alias in aliases:
        start = text.find(alias)
        while start != -1:
            window_start = start + len(alias)
            window_end = _find_next_alias_index(text, window_start, all_aliases) or window_start + 320
            window = text[window_start:window_end]
            number = _extract_current_period_number(window)
            if number is not None:
                return number
            start = text.find(alias, start + len(alias))
    return None


def _find_next_alias_index(text: str, start: int, aliases: list[str]) -> int | None:
    positions = [text.find(alias, start) for alias in aliases]
    positions = [position for position in positions if position != -1]
    return min(positions) if positions else None


def _extract_current_period_number(window: str) -> tuple[str, float] | None:
    marker_positions = [
        window.find(marker)
        for marker in CURRENT_PERIOD_MARKERS
        if window.find(marker) != -1 and window.find(marker) < 120
    ]
    search_windows = []
    if marker_positions:
        marker_pos = min(marker_positions)
        search_windows.append(window[marker_pos : marker_pos + 160])
    search_windows.append(window[:220])

    for candidate_window in search_windows:
        for match in _NUMBER_RE.finditer(candidate_window):
            if _is_percentage_token(candidate_window, match):
                continue
            parsed = _parse_number(match.group(0))
            if parsed is None:
                continue
            return match.group(0), parsed
    return None


def _is_percentage_token(window: str, match: re.Match) -> bool:
    tail = window[match.end() : match.end() + 2]
    return "%" in tail


def _parse_number(value: str) -> float | None:
    cleaned = value.strip().replace(",", "").replace("−", "-")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    if cleaned in {"", "-", "."}:
        return None
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    return -parsed if negative else parsed


def _format_metric_value(value: float, unit: str | None) -> str:
    normalized_unit = (unit or "").replace(" ", "")
    if normalized_unit in {"백만원", "억원", "천원", "원"}:
        multiplier = {
            "백만원": 1_000_000,
            "억원": 100_000_000,
            "천원": 1_000,
            "원": 1,
        }[normalized_unit]
        return _format_krw_amount(value * multiplier)
    return f"{value:,.0f}{(' ' + unit) if unit else ''}"


def _format_krw_amount(amount: float) -> str:
    sign = "-" if amount < 0 else ""
    abs_amount = abs(amount)
    eok = round(abs_amount / 100_000_000)
    jo = eok // 10_000
    rest_eok = eok % 10_000
    if jo and rest_eok:
        return f"{sign}{jo:,.0f}조 {rest_eok:,.0f}억원"
    if jo:
        return f"{sign}{jo:,.0f}조원"
    if rest_eok:
        return f"{sign}{rest_eok:,.0f}억원"
    return f"{sign}{abs_amount:,.0f}원"


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _build_price_move_section(
    event: CalendarPostResultRequest,
    *,
    provider: MarketDataProvider | None,
) -> CalendarPostResultSection:
    stock_code = event.stock_code.strip()
    if not stock_code:
        return _unavailable_price_section("이 일정에 종목코드가 없어 주가 반응을 계산할 수 없습니다.")
    if provider is None:
        return _unavailable_price_section(
            "DATA_GO_KR_SERVICE_KEY가 설정되지 않아 공공데이터포털 일봉을 조회할 수 없습니다."
        )

    event_date = _parse_event_date(event.datetime)
    if event_date is None:
        return _unavailable_price_section("이벤트 날짜를 해석할 수 없어 주가 반응을 계산할 수 없습니다.")

    series = provider.get_stock_daily_bars(stock_code, lookback=90)
    if series.data_status == MarketDataStatus.UNAVAILABLE or not series.bars:
        return _unavailable_price_section(series.status_reason or "일봉 데이터가 없습니다.")

    bars = sorted(series.bars, key=lambda bar: bar.date)
    event_index = _find_event_bar_index(bars, event_date)
    if event_index is None:
        return _unavailable_price_section("발표일 이후의 일봉 데이터가 아직 없습니다.")

    event_bar = bars[event_index]
    next_bar = bars[event_index + 1] if event_index + 1 < len(bars) else None
    prior_bars = bars[max(0, event_index - 20) : event_index]

    day_return = _percent_change(event_bar.close, event_bar.open)
    next_return = _percent_change(next_bar.close, event_bar.close) if next_bar else None
    volume_ratio = _volume_ratio(event_bar, prior_bars)

    items = [
        CalendarPostResultItem(k="발표 기준일", v=event_bar.date.isoformat()),
        CalendarPostResultItem(k="당일 종가", v=f"{event_bar.close:,.0f}원"),
        CalendarPostResultItem(k="당일 등락", v=_format_percent(day_return)),
        CalendarPostResultItem(
            k="D+1 종가 반응",
            v=_format_percent(next_return) if next_return is not None else "다음 거래일 데이터 없음",
        ),
        CalendarPostResultItem(
            k="거래량",
            v=f"20일 평균 대비 {volume_ratio:.0f}%" if volume_ratio is not None else "비교 가능한 20일 평균 부족",
        ),
    ]

    status: PostResultStatus = "available"
    if next_bar is None or series.data_status in {MarketDataStatus.STALE, MarketDataStatus.PARTIAL}:
        status = "partial"

    return CalendarPostResultSection(
        title="발표 직후 주가 반응",
        status=status,
        source=series.source.provider_name,
        items=items,
    )


def _build_commentary_section(
    event: CalendarPostResultRequest,
    earnings: CalendarPostResultSection,
    price_move: CalendarPostResultSection,
) -> CalendarPostResultSection:
    bullets: list[str] = []
    if earnings.status in {"available", "partial"}:
        bullets.append("실적 수치는 OpenDART 공시 원문에서 매출, 영업이익, 순이익 항목을 자동 추출한 값입니다.")
    elif earnings.status == "unavailable":
        bullets.append("OpenDART 원문에서 주요 실적 수치를 자동 확인하지 못했습니다.")
    elif earnings.status == "not_available":
        bullets.append("이 일정에는 발표 후 실적 수치를 연결할 수 있는 공시 식별자가 아직 없습니다.")

    if price_move.status in {"available", "partial"}:
        bullets.append("주가 반응은 발표일 종가와 다음 거래일 종가를 기준으로 계산합니다.")
    else:
        bullets.append("주가 반응은 종목코드와 일봉 데이터가 모두 있을 때만 계산됩니다.")

    if event.type.upper() == "EARNINGS":
        bullets.append("발표 후 1~3거래일은 결과 수치보다 가이던스, 수급, 저항 구간 반응을 함께 확인하는 편이 안전합니다.")

    return CalendarPostResultSection(
        title="해설",
        status="available" if bullets else "not_available",
        source="FinMate rules",
        bullets=bullets,
    )


def _unavailable_price_section(reason: str) -> CalendarPostResultSection:
    return CalendarPostResultSection(
        title="발표 직후 주가 반응",
        status="unavailable",
        source="공공데이터포털 금융위원회 주식시세정보",
        items=[CalendarPostResultItem(k="상태", v=reason)],
    )


def _combine_response_status(*sections: CalendarPostResultSection) -> Literal["available", "partial", "unavailable"]:
    statuses = {section.status for section in sections}
    if "available" in statuses and not statuses.intersection({"partial", "unavailable", "manual_required", "not_available"}):
        return "available"
    if statuses.intersection({"available", "partial", "manual_required"}):
        return "partial"
    return "unavailable"


def _build_source_note(
    earnings: CalendarPostResultSection,
    price_move: CalendarPostResultSection,
) -> str:
    if earnings.status in {"available", "partial"} and price_move.status in {"available", "partial"}:
        return "실적 수치는 OpenDART 원문에서 추출했고, 주가 반응은 연결된 일봉 데이터로 계산했습니다."
    if earnings.status in {"available", "partial"}:
        return "실적 수치는 OpenDART 원문에서 추출했습니다. 주가 반응은 일봉 데이터 연결 상태에 따라 표시됩니다."
    return "실적 수치와 주가 반응은 각각 OpenDART 원문과 일봉 데이터에서 가능한 범위만 표시합니다."


def _event_id(event: CalendarPostResultRequest) -> str:
    if event.id:
        return event.id
    return f"{event.stock_code or 'calendar'}-{event.datetime}"


def _rcept_no(event: CalendarPostResultRequest) -> str:
    if event.rcept_no:
        return event.rcept_no
    if event.id.startswith("dart-"):
        return event.id.removeprefix("dart-")
    return ""


def _parse_event_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _find_event_bar_index(bars: list[DailyBar], event_date: date) -> int | None:
    for index, bar in enumerate(bars):
        if bar.date >= event_date:
            return index
    return None


def _percent_change(current: float, base: float) -> float | None:
    if base <= 0:
        return None
    return (current - base) / base * 100


def _format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}%"


def _volume_ratio(event_bar: DailyBar, prior_bars: list[DailyBar]) -> float | None:
    volumes = [bar.volume for bar in prior_bars if bar.volume > 0]
    if not volumes:
        return None
    avg_volume = sum(volumes) / len(volumes)
    if avg_volume <= 0:
        return None
    return event_bar.volume / avg_volume * 100
