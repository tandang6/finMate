from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Callable
from urllib.parse import unquote

import requests

from config import settings

from .provider import MarketDataProvider
from .types import (
    BenchmarkDefinition,
    DailyBar,
    DailyBarSeries,
    MarketDataSourceInfo,
    MarketDataStatus,
    MarketInstrumentType,
    SupportedTicker,
)


DEFAULT_LOOKBACK = 260
REQUEST_LOOKBACK_DAYS = 540
MIN_FULL_HISTORY_BARS = 220
FRESH_MAX_CALENDAR_DAYS = 7
KST = timezone(timedelta(hours=9))
DATA_GO_KR_REFRESH_HOUR_KST = 13
DATA_GO_KR_REFRESH_GRACE_MINUTES = 10


SUPPORTED_TICKERS: tuple[SupportedTicker, ...] = (
    SupportedTicker(
        symbol_code="005930",
        symbol_name="삼성전자",
        market="KRX",
        aliases=["Samsung Electronics", "Samsung", "005930.KS", "KRX:005930"],
        primary_benchmark_id="kospi",
    ),
    SupportedTicker(
        symbol_code="000660",
        symbol_name="SK하이닉스",
        market="KRX",
        aliases=["SK Hynix", "000660.KS", "KRX:000660"],
        primary_benchmark_id="kospi",
    ),
    SupportedTicker(
        symbol_code="035420",
        symbol_name="NAVER",
        market="KRX",
        aliases=["Naver", "035420.KS", "KRX:035420"],
        primary_benchmark_id="kospi",
    ),
    SupportedTicker(
        symbol_code="035720",
        symbol_name="카카오",
        market="KRX",
        aliases=["Kakao", "035720.KS", "KRX:035720"],
        primary_benchmark_id="kospi",
    ),
    SupportedTicker(
        symbol_code="005380",
        symbol_name="현대차",
        market="KRX",
        aliases=["Hyundai Motor", "005380.KS", "KRX:005380"],
        primary_benchmark_id="kospi",
    ),
    SupportedTicker(
        symbol_code="373220",
        symbol_name="LG에너지솔루션",
        market="KRX",
        aliases=["LG Energy Solution", "LGES", "373220.KS", "KRX:373220"],
        primary_benchmark_id="kospi",
    ),
)


SUPPORTED_BENCHMARKS: tuple[BenchmarkDefinition, ...] = (
    BenchmarkDefinition(
        benchmark_id="kospi",
        benchmark_code="KOSPI",
        benchmark_name="KOSPI",
        market="KRX",
        aliases=["코스피", "Korea Composite Stock Price Index"],
    ),
    BenchmarkDefinition(
        benchmark_id="kosdaq",
        benchmark_code="KOSDAQ",
        benchmark_name="KOSDAQ",
        market="KRX",
        aliases=["코스닥"],
    ),
)


BENCHMARK_ECOS_ITEMS: dict[str, tuple[str, str]] = {
    "kospi": ("802Y001", "0001000"),
    "kosdaq": ("802Y001", "0089000"),
}


class PublicDataMarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        *,
        service_key: str | None = None,
        stock_price_url: str | None = None,
        session: requests.Session | None = None,
        cache_ttl_seconds: int | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._service_key = _normalize_service_key(service_key if service_key is not None else settings.DATA_GO_KR_SERVICE_KEY)
        self._stock_price_url = stock_price_url or settings.DATA_GO_KR_STOCK_PRICE_URL
        self._session = session or requests.Session()
        self._fixed_cache_ttl_seconds = _normalize_cache_ttl(
            cache_ttl_seconds if cache_ttl_seconds is not None else settings.DATA_GO_KR_CACHE_TTL_SECONDS
        )
        self._clock = clock or _now_kst
        self._stock_rows_cache: dict[tuple[Any, ...], tuple[datetime, list[dict[str, Any]]]] = {}
        self._benchmark_bars_cache: dict[tuple[Any, ...], tuple[datetime, list[DailyBar]]] = {}
        self._source_info = MarketDataSourceInfo(
            provider_id="data_go_kr_stock_price",
            provider_name="공공데이터포털 금융위원회 주식시세정보 + ECOS 벤치마크",
            dataset="kr_daily_ohlcv",
            provenance="public_api",
        )
        self._tickers_by_code = {ticker.symbol_code: ticker for ticker in SUPPORTED_TICKERS}
        self._benchmarks_by_id = {benchmark.benchmark_id: benchmark for benchmark in SUPPORTED_BENCHMARKS}
        self._ticker_lookup: dict[str, SupportedTicker] = {}
        self._build_lookup_tables()

    @property
    def source_info(self) -> MarketDataSourceInfo:
        return self._source_info.model_copy(deep=True)

    def list_supported_tickers(self) -> list[SupportedTicker]:
        return [ticker.model_copy(deep=True) for ticker in SUPPORTED_TICKERS]

    def list_supported_benchmarks(self) -> list[BenchmarkDefinition]:
        return [benchmark.model_copy(deep=True) for benchmark in SUPPORTED_BENCHMARKS]

    def normalize_ticker(self, ticker: str) -> SupportedTicker | None:
        normalized_key = self._normalize_query(ticker)
        if not normalized_key:
            return None
        match = self._ticker_lookup.get(normalized_key)
        return match.model_copy(deep=True) if match else None

    def get_stock_daily_bars(self, ticker: str, *, lookback: int | None = None) -> DailyBarSeries:
        symbol = self._resolve_symbol(ticker) or self._dynamic_krx_symbol(ticker)
        requested_lookback = lookback or DEFAULT_LOOKBACK
        if symbol is None:
            normalized_query = self._normalize_query(ticker) or ticker.strip() or "unknown"
            return self._unavailable_series(
                instrument_type=MarketInstrumentType.EQUITY,
                instrument_code=normalized_query,
                requested_lookback=requested_lookback,
                status_reason="지원 종목 목록에 없는 코드입니다.",
            )

        if not self._service_key:
            return self._unavailable_series(
                instrument_type=MarketInstrumentType.EQUITY,
                instrument_code=symbol.symbol_code,
                instrument_name=symbol.symbol_name,
                requested_lookback=requested_lookback,
                benchmark_id=symbol.primary_benchmark_id,
                status_reason="DATA_GO_KR_SERVICE_KEY가 설정되지 않았습니다.",
            )

        try:
            rows = self._fetch_stock_rows(symbol.symbol_code, requested_lookback=requested_lookback)
            bars = _rows_to_bars(rows)
        except Exception as exc:
            return self._unavailable_series(
                instrument_type=MarketInstrumentType.EQUITY,
                instrument_code=symbol.symbol_code,
                instrument_name=symbol.symbol_name,
                requested_lookback=requested_lookback,
                benchmark_id=symbol.primary_benchmark_id,
                status_reason=f"공공데이터포털 주식시세 조회 실패: {exc}",
            )

        bars = _dedupe_and_sort_bars(bars)
        if not bars:
            return self._unavailable_series(
                instrument_type=MarketInstrumentType.EQUITY,
                instrument_code=symbol.symbol_code,
                instrument_name=symbol.symbol_name,
                requested_lookback=requested_lookback,
                benchmark_id=symbol.primary_benchmark_id,
                status_reason="공공데이터포털 응답에 일봉 데이터가 없습니다.",
            )

        bars = bars[-requested_lookback:]
        instrument_name = _stock_name_from_rows(rows) or symbol.symbol_name
        return DailyBarSeries(
            instrument_type=MarketInstrumentType.EQUITY,
            instrument_code=symbol.symbol_code,
            instrument_name=instrument_name,
            market=symbol.market,
            data_status=_classify_data_status(bars),
            source=self.source_info,
            bars=bars,
            benchmark_id=symbol.primary_benchmark_id,
            requested_lookback=requested_lookback,
            status_reason=_status_reason(bars, provider_name="공공데이터포털"),
        )

    def get_primary_benchmark(self, ticker: str) -> BenchmarkDefinition | None:
        symbol = self._resolve_symbol(ticker)
        if symbol is None:
            return None
        benchmark = self._benchmarks_by_id.get(symbol.primary_benchmark_id)
        return benchmark.model_copy(deep=True) if benchmark else None

    def get_benchmark_daily_bars(self, ticker: str, *, lookback: int | None = None) -> DailyBarSeries:
        symbol = self._resolve_symbol(ticker)
        requested_lookback = lookback or DEFAULT_LOOKBACK
        if symbol is None:
            normalized_query = self._normalize_query(ticker) or ticker.strip() or "unknown"
            return self._unavailable_series(
                instrument_type=MarketInstrumentType.BENCHMARK,
                instrument_code=normalized_query,
                requested_lookback=requested_lookback,
                status_reason="지원 종목 목록에 없는 코드라 벤치마크를 찾을 수 없습니다.",
            )

        benchmark = self._benchmarks_by_id.get(symbol.primary_benchmark_id)
        if benchmark is None:
            return self._unavailable_series(
                instrument_type=MarketInstrumentType.BENCHMARK,
                instrument_code=symbol.primary_benchmark_id,
                requested_lookback=requested_lookback,
                benchmark_id=symbol.primary_benchmark_id,
                status_reason="지원 벤치마크 정의가 없습니다.",
            )

        try:
            bars = self._fetch_benchmark_bars(benchmark, requested_lookback=requested_lookback)
        except Exception as exc:
            return self._unavailable_series(
                instrument_type=MarketInstrumentType.BENCHMARK,
                instrument_code=benchmark.benchmark_code,
                instrument_name=benchmark.benchmark_name,
                requested_lookback=requested_lookback,
                benchmark_id=benchmark.benchmark_id,
                status_reason=f"ECOS 벤치마크 조회 실패: {exc}",
            )

        bars = _dedupe_and_sort_bars(bars)[-requested_lookback:]
        if not bars:
            return self._unavailable_series(
                instrument_type=MarketInstrumentType.BENCHMARK,
                instrument_code=benchmark.benchmark_code,
                instrument_name=benchmark.benchmark_name,
                requested_lookback=requested_lookback,
                benchmark_id=benchmark.benchmark_id,
                status_reason="ECOS 응답에 벤치마크 데이터가 없습니다.",
            )

        return DailyBarSeries(
            instrument_type=MarketInstrumentType.BENCHMARK,
            instrument_code=benchmark.benchmark_code,
            instrument_name=benchmark.benchmark_name,
            market=benchmark.market,
            data_status=_classify_data_status(bars),
            source=MarketDataSourceInfo(
                provider_id="ecos_benchmark",
                provider_name="한국은행 ECOS",
                dataset="kr_benchmark_daily_close",
                provenance="public_api",
            ),
            bars=bars,
            benchmark_id=benchmark.benchmark_id,
            requested_lookback=requested_lookback,
            status_reason=_status_reason(bars, provider_name="ECOS"),
        )

    def _fetch_stock_rows(self, symbol_code: str, *, requested_lookback: int) -> list[dict[str, Any]]:
        today = self._today()
        start = today - timedelta(days=REQUEST_LOOKBACK_DAYS)
        row_limit = max(requested_lookback + 80, 360)
        cache_key = (
            "stock",
            symbol_code,
            row_limit,
        )
        cached_rows = self._get_cached_stock_rows(cache_key)
        if cached_rows is not None:
            return cached_rows

        params = {
            "serviceKey": self._service_key,
            "pageNo": 1,
            "numOfRows": row_limit,
            "resultType": "json",
            "likeSrtnCd": symbol_code,
            "beginBasDt": start.strftime("%Y%m%d"),
            "endBasDt": today.strftime("%Y%m%d"),
        }
        rows = self._request_rows(params)
        if rows:
            self._set_cached_stock_rows(cache_key, rows)
            return rows

        fallback_cache_key = ("stock_latest", symbol_code, row_limit)
        cached_fallback_rows = self._get_cached_stock_rows(fallback_cache_key)
        if cached_fallback_rows is not None:
            return cached_fallback_rows

        fallback_params = {
            "serviceKey": self._service_key,
            "pageNo": 1,
            "numOfRows": row_limit,
            "resultType": "json",
            "likeSrtnCd": symbol_code,
        }
        fallback_rows = self._request_rows(fallback_params)
        if fallback_rows:
            self._set_cached_stock_rows(fallback_cache_key, fallback_rows)
            self._set_cached_stock_rows(cache_key, fallback_rows)
        return fallback_rows

    def _request_rows(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        response = self._session.get(self._stock_price_url, params=params, timeout=20)
        if response.status_code != 200:
            raise ValueError(f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValueError("JSON 응답이 아닙니다.") from exc

        response_payload = payload.get("response", {})
        header = response_payload.get("header", {})
        result_code = str(header.get("resultCode", ""))
        if result_code and result_code not in {"00", "INFO-000"}:
            raise ValueError(header.get("resultMsg") or f"resultCode={result_code}")

        items = response_payload.get("body", {}).get("items", {})
        if isinstance(items, dict):
            item_payload = items.get("item", [])
        else:
            item_payload = items
        if isinstance(item_payload, dict):
            return [item_payload]
        if isinstance(item_payload, list):
            return [item for item in item_payload if isinstance(item, dict)]
        return []

    def _fetch_benchmark_bars(
        self,
        benchmark: BenchmarkDefinition,
        *,
        requested_lookback: int,
    ) -> list[DailyBar]:
        from ecos import get_ecos_statistic

        ecos_args = BENCHMARK_ECOS_ITEMS.get(benchmark.benchmark_id)
        if ecos_args is None:
            return []

        today = self._today()
        start = today - timedelta(days=REQUEST_LOOKBACK_DAYS)
        stat_code, item_code = ecos_args
        cache_key = (
            "benchmark",
            benchmark.benchmark_id,
            requested_lookback,
        )
        cached_bars = self._get_cached_benchmark_bars(cache_key)
        if cached_bars is not None:
            return cached_bars

        rows = get_ecos_statistic(
            stat_code,
            "D",
            start.strftime("%Y%m%d"),
            today.strftime("%Y%m%d"),
            item_code,
        )
        if isinstance(rows, dict) and "error" in rows:
            raise ValueError(rows["error"])

        bars: list[DailyBar] = []
        for row in rows:
            try:
                row_date = datetime.strptime(str(row["TIME"]), "%Y%m%d").date()
                close = float(row["DATA_VALUE"])
            except (KeyError, TypeError, ValueError):
                continue
            bars.append(
                DailyBar(
                    date=row_date,
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=0,
                )
            )
        bars = bars[-requested_lookback:]
        self._set_cached_benchmark_bars(cache_key, bars)
        return bars

    def _get_cached_stock_rows(self, key: tuple[Any, ...]) -> list[dict[str, Any]] | None:
        entry = self._get_cache_entry(self._stock_rows_cache, key)
        if entry is None:
            return None
        return _copy_stock_rows(entry)

    def _set_cached_stock_rows(self, key: tuple[Any, ...], rows: list[dict[str, Any]]) -> None:
        self._set_cache_entry(self._stock_rows_cache, key, _copy_stock_rows(rows))

    def _get_cached_benchmark_bars(self, key: tuple[Any, ...]) -> list[DailyBar] | None:
        entry = self._get_cache_entry(self._benchmark_bars_cache, key)
        if entry is None:
            return None
        return _copy_daily_bars(entry)

    def _set_cached_benchmark_bars(self, key: tuple[Any, ...], bars: list[DailyBar]) -> None:
        self._set_cache_entry(self._benchmark_bars_cache, key, _copy_daily_bars(bars))

    def _get_cache_entry(
        self,
        cache: dict[tuple[Any, ...], tuple[datetime, Any]],
        key: tuple[Any, ...],
    ) -> Any | None:
        if self._cache_disabled():
            return None
        entry = cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if self._now() >= expires_at:
            del cache[key]
            return None
        return value

    def _set_cache_entry(
        self,
        cache: dict[tuple[Any, ...], tuple[datetime, Any]],
        key: tuple[Any, ...],
        value: Any,
    ) -> None:
        if self._cache_disabled():
            return
        cache[key] = (self._cache_expires_at(), value)

    def _cache_disabled(self) -> bool:
        return self._fixed_cache_ttl_seconds == 0

    def _cache_expires_at(self) -> datetime:
        now = self._now()
        scheduled_expiry = _next_public_data_cache_expiry(now)
        if self._fixed_cache_ttl_seconds is None:
            return scheduled_expiry
        fixed_expiry = now + timedelta(seconds=self._fixed_cache_ttl_seconds)
        return min(scheduled_expiry, fixed_expiry)

    def _now(self) -> datetime:
        return _to_kst(self._clock())

    def _today(self) -> date:
        return self._now().date()

    def _build_lookup_tables(self) -> None:
        for symbol in SUPPORTED_TICKERS:
            lookup_keys = {
                symbol.symbol_code,
                self._normalize_query(symbol.symbol_code),
                self._normalize_query(symbol.symbol_name),
            }
            lookup_keys.update(self._normalize_query(alias) for alias in symbol.aliases)
            for key in lookup_keys:
                if key:
                    self._ticker_lookup[key] = symbol

    def _resolve_symbol(self, ticker: str) -> SupportedTicker | None:
        normalized_key = self._normalize_query(ticker)
        if not normalized_key:
            return None
        return self._ticker_lookup.get(normalized_key)

    def _dynamic_krx_symbol(self, ticker: str) -> SupportedTicker | None:
        normalized_key = self._normalize_query(ticker)
        if not normalized_key or not normalized_key.isdigit() or len(normalized_key) != 6:
            return None
        return SupportedTicker(
            symbol_code=normalized_key,
            symbol_name=normalized_key,
            market="KRX",
            aliases=[],
            primary_benchmark_id="kospi",
        )

    def _unavailable_series(
        self,
        *,
        instrument_type: MarketInstrumentType,
        instrument_code: str,
        requested_lookback: int,
        status_reason: str,
        instrument_name: str | None = None,
        benchmark_id: str | None = None,
    ) -> DailyBarSeries:
        return DailyBarSeries(
            instrument_type=instrument_type,
            instrument_code=instrument_code,
            instrument_name=instrument_name,
            data_status=MarketDataStatus.UNAVAILABLE,
            source=self.source_info,
            bars=[],
            benchmark_id=benchmark_id,
            requested_lookback=requested_lookback,
            status_reason=status_reason,
        )

    @staticmethod
    def _normalize_query(value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""

        normalized = cleaned.upper().replace(" ", "")
        for prefix in ("KRX:", "KR:"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
        for suffix in (".KS", ".KQ", ".KR"):
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
        if normalized.startswith("A") and normalized[1:].isdigit():
            normalized = normalized[1:]
        if normalized.isdigit() and len(normalized) <= 6:
            normalized = normalized.zfill(6)
        return normalized


@lru_cache(maxsize=1)
def get_public_data_market_data_provider() -> PublicDataMarketDataProvider:
    return PublicDataMarketDataProvider()


def _normalize_service_key(value: str) -> str:
    return unquote((value or "").strip())


def _normalize_cache_ttl(value: int | None) -> int | None:
    if value is None or value < 0:
        return None
    return value


def _now_kst() -> datetime:
    return datetime.now(KST)


def _today_kst() -> date:
    return _now_kst().date()


def _to_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _next_public_data_cache_expiry(now: datetime | None = None) -> datetime:
    current = _to_kst(now or _now_kst())
    candidate_date = current.date()
    refresh_at = _refresh_window_at(candidate_date)

    if _is_weekend(candidate_date) or current >= refresh_at:
        candidate_date += timedelta(days=1)

    candidate_date = _next_weekday(candidate_date)
    return _refresh_window_at(candidate_date)


def _refresh_window_at(value: date) -> datetime:
    return datetime(
        value.year,
        value.month,
        value.day,
        DATA_GO_KR_REFRESH_HOUR_KST,
        DATA_GO_KR_REFRESH_GRACE_MINUTES,
        tzinfo=KST,
    )


def _next_weekday(value: date) -> date:
    current = value
    while _is_weekend(current):
        current += timedelta(days=1)
    return current


def _is_weekend(value: date) -> bool:
    return value.weekday() >= 5


def _copy_stock_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row.copy() for row in rows]


def _copy_daily_bars(bars: list[DailyBar]) -> list[DailyBar]:
    return [bar.model_copy(deep=True) for bar in bars]


def _stock_name_from_rows(rows: list[dict[str, Any]]) -> str | None:
    for row in rows:
        name = str(row.get("itmsNm") or "").strip()
        if name:
            return name
    return None


def _rows_to_bars(rows: list[dict[str, Any]]) -> list[DailyBar]:
    bars: list[DailyBar] = []
    for row in rows:
        try:
            row_date = datetime.strptime(str(row["basDt"]), "%Y%m%d").date()
            open_price = _to_float(row.get("mkp"))
            high_price = _to_float(row.get("hipr"))
            low_price = _to_float(row.get("lopr"))
            close_price = _to_float(row.get("clpr"))
            volume = int(_to_float(row.get("trqu")))
        except (KeyError, TypeError, ValueError):
            continue
        if min(open_price, high_price, low_price, close_price) <= 0:
            continue
        bars.append(
            DailyBar(
                date=row_date,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=max(volume, 0),
            )
        )
    return bars


def _to_float(value: Any) -> float:
    if value is None:
        raise ValueError("missing numeric value")
    return float(str(value).replace(",", "").strip())


def _dedupe_and_sort_bars(bars: list[DailyBar]) -> list[DailyBar]:
    by_date = {bar.date: bar for bar in bars}
    return [by_date[bar_date] for bar_date in sorted(by_date)]


def _classify_data_status(bars: list[DailyBar]) -> MarketDataStatus:
    if not bars:
        return MarketDataStatus.UNAVAILABLE
    latest = bars[-1].date
    age_days = (_today_kst() - latest).days
    if len(bars) < MIN_FULL_HISTORY_BARS:
        return MarketDataStatus.PARTIAL
    if age_days > FRESH_MAX_CALENDAR_DAYS:
        return MarketDataStatus.STALE
    return MarketDataStatus.FRESH


def _status_reason(bars: list[DailyBar], *, provider_name: str) -> str:
    latest = bars[-1].date if bars else None
    if latest is None:
        return f"{provider_name} 응답에 데이터가 없습니다."
    status = _classify_data_status(bars)
    if status == MarketDataStatus.FRESH:
        return f"{provider_name} 최신 가용 일봉 데이터입니다. as_of={latest.isoformat()}"
    if status == MarketDataStatus.PARTIAL:
        return f"{provider_name} 일봉 히스토리가 전략 평가에 필요한 길이보다 짧습니다. as_of={latest.isoformat()}"
    return f"{provider_name} 최신 데이터 기준일이 오래되었습니다. as_of={latest.isoformat()}"
