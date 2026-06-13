from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from config import settings
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
    consensus: CalendarPostResultSection


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
    consensus = _build_consensus_section()
    commentary = _build_commentary_section(event, earnings, price_move, consensus)

    return CalendarPostResultResponse(
        eventId=_event_id(event),
        status=_combine_response_status(earnings, price_move),
        sourceNote=_build_source_note(price_move),
        earnings=earnings,
        priceMove=price_move,
        commentary=commentary,
        consensus=consensus,
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
            CalendarPostResultItem(k="매출", v="XX조원 (YoY +X%, 시연용)"),
            CalendarPostResultItem(k="영업이익", v="X.X조원 (YoY +X%, 시연용)"),
            CalendarPostResultItem(k="컨센서스 대비", v="매출 상회 / 이익 상회 (시연용)"),
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
    consensus = _build_consensus_section(status="available")
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
        consensus=consensus,
    )


def _build_earnings_section(event: CalendarPostResultRequest) -> CalendarPostResultSection:
    rcept_no = _rcept_no(event)
    items = [
        CalendarPostResultItem(k="공시 제목", v=event.title),
        CalendarPostResultItem(k="회사", v=event.company_name or "-"),
        CalendarPostResultItem(k="종목코드", v=event.stock_code or "-"),
    ]
    if rcept_no:
        items.append(CalendarPostResultItem(k="DART 접수번호", v=rcept_no))

    items.extend(
        [
            CalendarPostResultItem(
                k="실적 수치",
                v="OpenDART 공시 원문/재무정보 재조회 후 표 파싱이 필요합니다.",
            ),
            CalendarPostResultItem(
                k="컨센서스 대비",
                v="무료 공식 API 범위에서는 일반적으로 제공되지 않습니다.",
            ),
        ]
    )

    return CalendarPostResultSection(
        title="실적 발표 결과",
        status="manual_required" if rcept_no else "not_available",
        source="OpenDART 공시 목록 기반",
        items=items,
    )


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
        source=f"{series.source.provider_name} ({series.source.dataset})",
        items=items,
    )


def _build_consensus_section(status: PostResultStatus = "not_available") -> CalendarPostResultSection:
    return CalendarPostResultSection(
        title="예상치/컨센서스 대비",
        status=status,
        source="공식 무료 API 미제공",
        items=[
            CalendarPostResultItem(
                k="상태",
                v="FnGuide, Bloomberg, Refinitiv, Quantiwise 등 별도 데이터 소스가 필요합니다.",
            )
        ],
    )


def _build_commentary_section(
    event: CalendarPostResultRequest,
    earnings: CalendarPostResultSection,
    price_move: CalendarPostResultSection,
    consensus: CalendarPostResultSection,
) -> CalendarPostResultSection:
    bullets: list[str] = []
    if earnings.status == "manual_required":
        bullets.append("실적 수치는 DART 접수번호로 원문을 다시 조회한 뒤 표 구조를 파싱해야 확정됩니다.")
    elif earnings.status == "not_available":
        bullets.append("이 일정에는 발표 후 실적 수치를 연결할 수 있는 공시 식별자가 아직 없습니다.")

    if price_move.status in {"available", "partial"}:
        bullets.append("주가 반응은 발표일 종가와 다음 거래일 종가를 기준으로 계산합니다.")
    else:
        bullets.append("주가 반응은 종목코드와 일봉 데이터가 모두 있을 때만 계산됩니다.")

    if consensus.status == "not_available":
        bullets.append("컨센서스 대비는 공식 무료 API만으로 자동 산출하기 어려워 별도 데이터 소스가 필요합니다.")

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


def _build_source_note(price_move: CalendarPostResultSection) -> str:
    if price_move.status in {"available", "partial"}:
        return "실적 원문 파싱은 단계적으로 확장하고, 주가 반응은 현재 연결된 일봉 데이터로 계산합니다."
    return "실적 원문/컨센서스/주가 데이터가 모두 한 API에서 제공되지는 않아 데이터 종류별로 연결합니다."


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
