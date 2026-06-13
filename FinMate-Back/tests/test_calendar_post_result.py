from __future__ import annotations

import unittest
from datetime import date, timedelta

from calendar_post_result import CalendarPostResultRequest, build_calendar_post_result
from market_data.provider import MarketDataProvider
from market_data.types import (
    BenchmarkDefinition,
    DailyBar,
    DailyBarSeries,
    MarketDataSourceInfo,
    MarketDataStatus,
    MarketInstrumentType,
    SupportedTicker,
)


class FakePostResultProvider(MarketDataProvider):
    def __init__(self, bars: list[DailyBar]) -> None:
        self._bars = bars
        self._source_info = MarketDataSourceInfo(
            provider_id="fake_daily_bars",
            provider_name="Fake Daily Bars",
            dataset="unit_test_daily_ohlcv",
            provenance="fixture",
        )
        self._ticker = SupportedTicker(
            symbol_code="005930",
            symbol_name="삼성전자",
            market="KRX",
            aliases=["005930.KS"],
            primary_benchmark_id="kospi",
        )

    @property
    def source_info(self) -> MarketDataSourceInfo:
        return self._source_info

    def list_supported_tickers(self) -> list[SupportedTicker]:
        return [self._ticker]

    def list_supported_benchmarks(self) -> list[BenchmarkDefinition]:
        return []

    def normalize_ticker(self, ticker: str) -> SupportedTicker | None:
        return self._ticker if ticker in {"005930", "005930.KS"} else None

    def get_stock_daily_bars(self, ticker: str, *, lookback: int | None = None) -> DailyBarSeries:
        return DailyBarSeries(
            instrument_type=MarketInstrumentType.EQUITY,
            instrument_code="005930",
            instrument_name="삼성전자",
            market="KRX",
            data_status=MarketDataStatus.FRESH,
            source=self.source_info,
            bars=self._bars[-lookback:] if lookback else self._bars,
            benchmark_id="kospi",
            requested_lookback=lookback,
            status_reason="unit test fixture",
        )

    def get_primary_benchmark(self, ticker: str) -> BenchmarkDefinition | None:
        return None

    def get_benchmark_daily_bars(self, ticker: str, *, lookback: int | None = None) -> DailyBarSeries:
        return DailyBarSeries(
            instrument_type=MarketInstrumentType.BENCHMARK,
            instrument_code="KOSPI",
            instrument_name="KOSPI",
            data_status=MarketDataStatus.UNAVAILABLE,
            source=self.source_info,
            bars=[],
            requested_lookback=lookback,
            status_reason="not used in calendar post-result tests",
        )


def make_bar(value_date: date, *, open_price: float, close: float, volume: int) -> DailyBar:
    high = max(open_price, close)
    low = min(open_price, close)
    return DailyBar(
        date=value_date,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


class CalendarPostResultTest(unittest.TestCase):
    def test_static_demo_fixture_is_available_without_provider(self) -> None:
        result = build_calendar_post_result(
            CalendarPostResultRequest(
                id="kr-earnings-37",
                title="삼성전자 2025년 3분기 실적발표",
                datetime="2025-10-30T10:00:00",
                type="EARNINGS",
                companyName="삼성전자",
                stockCode="005930",
            ),
            provider=None,
        )

        self.assertEqual(result.status, "available")
        self.assertIn("고정 데이터", result.sourceNote)
        self.assertEqual(result.earnings.status, "available")
        self.assertEqual(result.priceMove.status, "available")

    def test_price_reaction_uses_injected_daily_bar_provider(self) -> None:
        start = date(2026, 5, 14)
        prior_bars = [
            make_bar(start + timedelta(days=offset), open_price=100, close=100, volume=100)
            for offset in range(20)
        ]
        event_bar = make_bar(date(2026, 6, 3), open_price=100, close=105, volume=200)
        next_bar = make_bar(date(2026, 6, 4), open_price=105, close=110, volume=150)
        provider = FakePostResultProvider([*prior_bars, event_bar, next_bar])

        result = build_calendar_post_result(
            CalendarPostResultRequest(
                id="dart-20260603000123",
                title="삼성전자 영업(잠정)실적 공시",
                datetime="2026-06-03T09:00:00",
                type="EARNINGS",
                companyName="삼성전자",
                stockCode="005930",
                rceptNo="20260603000123",
            ),
            provider=provider,
        )

        price_values = {item.k: item.v for item in result.priceMove.items}

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.earnings.status, "manual_required")
        self.assertEqual(result.priceMove.status, "available")
        self.assertEqual(price_values["당일 등락"], "+5.00%")
        self.assertEqual(price_values["D+1 종가 반응"], "+4.76%")
        self.assertEqual(price_values["거래량"], "20일 평균 대비 200%")

    def test_missing_provider_keeps_result_explainable(self) -> None:
        result = build_calendar_post_result(
            CalendarPostResultRequest(
                id="dart-20260603000123",
                title="삼성전자 영업(잠정)실적 공시",
                datetime="2026-06-03T09:00:00",
                type="EARNINGS",
                companyName="삼성전자",
                stockCode="005930",
            ),
            provider=None,
        )

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.earnings.status, "manual_required")
        self.assertEqual(result.priceMove.status, "unavailable")
        self.assertIn("DATA_GO_KR_SERVICE_KEY", result.priceMove.items[0].v)
        self.assertTrue(result.commentary.bullets)


if __name__ == "__main__":
    unittest.main()
