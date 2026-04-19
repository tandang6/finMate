from __future__ import annotations

from abc import ABC, abstractmethod

from .types import BenchmarkDefinition, DailyBarSeries, MarketDataSourceInfo, SupportedTicker


class MarketDataProvider(ABC):
    @property
    @abstractmethod
    def source_info(self) -> MarketDataSourceInfo:
        """Return provider-level metadata without exposing vendor-specific details."""

    @abstractmethod
    def list_supported_tickers(self) -> list[SupportedTicker]:
        """Return the curated ticker universe available to this provider."""

    @abstractmethod
    def list_supported_benchmarks(self) -> list[BenchmarkDefinition]:
        """Return the benchmark universe available to this provider."""

    @abstractmethod
    def normalize_ticker(self, ticker: str) -> SupportedTicker | None:
        """Resolve a user or upstream ticker input into a canonical supported ticker."""

    @abstractmethod
    def get_stock_daily_bars(self, ticker: str, *, lookback: int | None = None) -> DailyBarSeries:
        """Return normalized daily OHLCV for an equity symbol."""

    @abstractmethod
    def get_primary_benchmark(self, ticker: str) -> BenchmarkDefinition | None:
        """Resolve the canonical benchmark associated with a supported symbol."""

    @abstractmethod
    def get_benchmark_daily_bars(self, ticker: str, *, lookback: int | None = None) -> DailyBarSeries:
        """Return normalized daily OHLCV for the benchmark associated with a symbol."""
