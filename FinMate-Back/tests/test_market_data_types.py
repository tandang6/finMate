import unittest
from datetime import date

from pydantic import ValidationError

from market_data.types import DailyBar, DailyBarSeries, MarketDataSourceInfo, MarketDataStatus, MarketInstrumentType


class MarketDataTypesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = MarketDataSourceInfo(
            provider_id="test_provider",
            provider_name="Test Provider",
            dataset="kr_daily_ohlcv",
            provenance="fixture",
        )

    def _bar(self, day: int = 1) -> DailyBar:
        return DailyBar(
            date=date(2026, 4, day),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000,
        )

    def test_daily_bar_rejects_invalid_ranges(self) -> None:
        invalid_payloads = [
            {
                "date": date(2026, 4, 1),
                "open": 100.0,
                "high": 99.0,
                "low": 95.0,
                "close": 98.0,
                "volume": 1000,
            },
            {
                "date": date(2026, 4, 1),
                "open": 100.0,
                "high": 105.0,
                "low": 101.0,
                "close": 102.0,
                "volume": 1000,
            },
            {
                "date": date(2026, 4, 1),
                "open": 100.0,
                "high": 101.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 1000,
            },
            {
                "date": date(2026, 4, 1),
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": -1,
            },
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    DailyBar(**payload)

    def test_daily_bar_series_rejects_invalid_status_and_ordering(self) -> None:
        valid_bar_one = self._bar(1)
        valid_bar_two = self._bar(2)

        invalid_series_payloads = [
            {
                "instrument_type": MarketInstrumentType.EQUITY,
                "instrument_code": "005930",
                "instrument_name": "삼성전자",
                "data_status": MarketDataStatus.UNAVAILABLE,
                "source": self.source,
                "bars": [valid_bar_one],
            },
            {
                "instrument_type": MarketInstrumentType.EQUITY,
                "instrument_code": "005930",
                "instrument_name": "삼성전자",
                "data_status": MarketDataStatus.FRESH,
                "source": self.source,
                "bars": [],
            },
            {
                "instrument_type": MarketInstrumentType.EQUITY,
                "instrument_code": "005930",
                "instrument_name": "삼성전자",
                "data_status": MarketDataStatus.FRESH,
                "source": self.source,
                "bars": [valid_bar_two, valid_bar_one],
            },
            {
                "instrument_type": MarketInstrumentType.EQUITY,
                "instrument_code": "005930",
                "instrument_name": "삼성전자",
                "data_status": MarketDataStatus.FRESH,
                "source": self.source,
                "bars": [valid_bar_one, valid_bar_one],
            },
        ]

        for payload in invalid_series_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    DailyBarSeries(**payload)


if __name__ == "__main__":
    unittest.main()
