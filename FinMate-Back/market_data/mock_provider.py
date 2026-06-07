from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

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


FIXTURE_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_market_data.json"


class _FixtureBenchmark(BenchmarkDefinition):
    data_status: MarketDataStatus
    status_reason: str | None = None
    bars: list[DailyBar] = Field(default_factory=list)


class _FixtureSymbol(SupportedTicker):
    data_status: MarketDataStatus
    status_reason: str | None = None
    bars: list[DailyBar] = Field(default_factory=list)


class _FixturePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: list[_FixtureSymbol]
    benchmarks: list[_FixtureBenchmark]


@lru_cache(maxsize=4)
def _load_fixture(path: str) -> _FixturePayload:
    with Path(path).open(encoding="utf-8") as fixture_file:
        raw_payload = json.load(fixture_file)
    return _FixturePayload.model_validate(raw_payload)


class MockMarketDataProvider(MarketDataProvider):
    def __init__(self, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path or FIXTURE_PATH
        payload = _load_fixture(str(self.fixture_path))
        self._source_info = MarketDataSourceInfo(
            provider_id="mock_market_data",
            provider_name="Mock Market Data Provider",
            dataset="kr_daily_ohlcv",
            provenance="fixture",
        )
        self._supported_tickers = sorted(payload.symbols, key=lambda symbol: symbol.symbol_code)
        self._supported_benchmarks = sorted(payload.benchmarks, key=lambda benchmark: benchmark.benchmark_id)
        self._tickers_by_code = {symbol.symbol_code: symbol for symbol in self._supported_tickers}
        self._benchmarks_by_id = {benchmark.benchmark_id: benchmark for benchmark in self._supported_benchmarks}
        self._ticker_lookup: dict[str, _FixtureSymbol] = {}
        self._build_lookup_tables()

    @property
    def source_info(self) -> MarketDataSourceInfo:
        return self._source_info.model_copy(deep=True)

    def list_supported_tickers(self) -> list[SupportedTicker]:
        return [self._to_supported_ticker(symbol) for symbol in self._supported_tickers]

    def list_supported_benchmarks(self) -> list[BenchmarkDefinition]:
        return [self._to_benchmark_definition(benchmark) for benchmark in self._supported_benchmarks]

    def normalize_ticker(self, ticker: str) -> SupportedTicker | None:
        normalized_key = self._normalize_query(ticker)
        if not normalized_key:
            return None
        match = self._ticker_lookup.get(normalized_key)
        return self._to_supported_ticker(match) if match else None

    def get_stock_daily_bars(self, ticker: str, *, lookback: int | None = None) -> DailyBarSeries:
        symbol = self._resolve_symbol(ticker)
        if symbol is None:
            normalized_query = self._normalize_query(ticker) or ticker.strip() or "unknown"
            return DailyBarSeries(
                instrument_type=MarketInstrumentType.EQUITY,
                instrument_code=normalized_query,
                instrument_name=None,
                data_status=MarketDataStatus.UNAVAILABLE,
                source=self.source_info,
                bars=[],
                requested_lookback=lookback,
                status_reason="Ticker is not supported by the current provider fixture universe.",
            )
        return self._build_series_from_symbol(symbol, lookback=lookback)

    def get_primary_benchmark(self, ticker: str) -> BenchmarkDefinition | None:
        symbol = self._resolve_symbol(ticker)
        if symbol is None:
            return None
        benchmark = self._benchmarks_by_id.get(symbol.primary_benchmark_id)
        return self._to_benchmark_definition(benchmark) if benchmark else None

    def get_benchmark_daily_bars(self, ticker: str, *, lookback: int | None = None) -> DailyBarSeries:
        symbol = self._resolve_symbol(ticker)
        if symbol is None:
            normalized_query = self._normalize_query(ticker) or ticker.strip() or "unknown"
            return DailyBarSeries(
                instrument_type=MarketInstrumentType.BENCHMARK,
                instrument_code=normalized_query,
                instrument_name=None,
                data_status=MarketDataStatus.UNAVAILABLE,
                source=self.source_info,
                bars=[],
                requested_lookback=lookback,
                status_reason="Benchmark lookup failed because the ticker is unsupported.",
            )

        benchmark = self._benchmarks_by_id.get(symbol.primary_benchmark_id)
        if benchmark is None:
            return DailyBarSeries(
                instrument_type=MarketInstrumentType.BENCHMARK,
                instrument_code=symbol.primary_benchmark_id,
                instrument_name=None,
                data_status=MarketDataStatus.UNAVAILABLE,
                source=self.source_info,
                bars=[],
                benchmark_id=symbol.primary_benchmark_id,
                requested_lookback=lookback,
                status_reason="No benchmark fixture is configured for the requested ticker.",
            )

        return self._build_series_from_benchmark(benchmark, lookback=lookback)

    def _build_lookup_tables(self) -> None:
        for symbol in self._supported_tickers:
            lookup_keys = {
                symbol.symbol_code,
                self._normalize_query(symbol.symbol_code),
                self._normalize_query(symbol.symbol_name),
            }
            lookup_keys.update(self._normalize_query(alias) for alias in symbol.aliases)
            for key in lookup_keys:
                if key:
                    self._ticker_lookup[key] = symbol

    @staticmethod
    def _to_supported_ticker(symbol: _FixtureSymbol) -> SupportedTicker:
        return SupportedTicker.model_validate(
            {
                "symbol_code": symbol.symbol_code,
                "symbol_name": symbol.symbol_name,
                "market": symbol.market,
                "aliases": symbol.aliases,
                "primary_benchmark_id": symbol.primary_benchmark_id,
            }
        )

    @staticmethod
    def _to_benchmark_definition(benchmark: _FixtureBenchmark) -> BenchmarkDefinition:
        return BenchmarkDefinition.model_validate(
            {
                "benchmark_id": benchmark.benchmark_id,
                "benchmark_code": benchmark.benchmark_code,
                "benchmark_name": benchmark.benchmark_name,
                "market": benchmark.market,
                "aliases": benchmark.aliases,
            }
        )

    def _resolve_symbol(self, ticker: str) -> _FixtureSymbol | None:
        normalized_key = self._normalize_query(ticker)
        if not normalized_key:
            return None
        return self._ticker_lookup.get(normalized_key)

    def _build_series_from_symbol(self, symbol: _FixtureSymbol, *, lookback: int | None) -> DailyBarSeries:
        bars = self._slice_bars(symbol.bars, lookback=lookback)
        return DailyBarSeries(
            instrument_type=MarketInstrumentType.EQUITY,
            instrument_code=symbol.symbol_code,
            instrument_name=symbol.symbol_name,
            market=symbol.market,
            data_status=symbol.data_status,
            source=self.source_info,
            bars=bars,
            benchmark_id=symbol.primary_benchmark_id,
            requested_lookback=lookback,
            status_reason=symbol.status_reason,
        )

    def _build_series_from_benchmark(
        self,
        benchmark: _FixtureBenchmark,
        *,
        lookback: int | None,
    ) -> DailyBarSeries:
        bars = self._slice_bars(benchmark.bars, lookback=lookback)
        return DailyBarSeries(
            instrument_type=MarketInstrumentType.BENCHMARK,
            instrument_code=benchmark.benchmark_code,
            instrument_name=benchmark.benchmark_name,
            market=benchmark.market,
            data_status=benchmark.data_status,
            source=self.source_info,
            bars=bars,
            benchmark_id=benchmark.benchmark_id,
            requested_lookback=lookback,
            status_reason=benchmark.status_reason,
        )

    @staticmethod
    def _slice_bars(bars: list[DailyBar], *, lookback: int | None) -> list[DailyBar]:
        if lookback is None or lookback >= len(bars):
            return [bar.model_copy(deep=True) for bar in bars]
        return [bar.model_copy(deep=True) for bar in bars[-lookback:]]

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
