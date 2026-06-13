from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from market_data.public_data_provider import PublicDataMarketDataProvider, _next_public_data_cache_expiry
from market_data.types import MarketDataStatus, MarketInstrumentType

KST = timezone(timedelta(hours=9))


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(self.payload)


def stock_payload(rows):
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "items": {
                    "item": rows,
                },
            },
        },
    }


class PublicDataMarketDataProviderTest(unittest.TestCase):
    def test_stock_rows_are_mapped_to_daily_bar_series(self) -> None:
        session = FakeSession(
            stock_payload(
                [
                    {
                        "basDt": "20260610",
                        "srtnCd": "005930",
                        "itmsNm": "삼성전자",
                        "mkp": "70100",
                        "hipr": "71300",
                        "lopr": "69900",
                        "clpr": "71000",
                        "trqu": "12345678",
                    },
                    {
                        "basDt": "20260609",
                        "srtnCd": "005930",
                        "itmsNm": "삼성전자",
                        "mkp": "69500",
                        "hipr": "70400",
                        "lopr": "69000",
                        "clpr": "70100",
                        "trqu": "12000000",
                    },
                ]
            )
        )
        provider = PublicDataMarketDataProvider(
            service_key="encoded%2Bkey%3D",
            stock_price_url="https://example.com/stock",
            session=session,
        )

        series = provider.get_stock_daily_bars("005930", lookback=2)

        self.assertEqual(series.instrument_type, MarketInstrumentType.EQUITY)
        self.assertEqual(series.instrument_code, "005930")
        self.assertEqual(series.instrument_name, "삼성전자")
        self.assertEqual(series.available_bar_count, 2)
        self.assertEqual(series.bars[-1].date.isoformat(), "2026-06-10")
        self.assertEqual(series.bars[-1].close, 71000.0)
        self.assertEqual(series.bars[-1].volume, 12345678)
        self.assertEqual(series.benchmark_id, "kospi")
        self.assertEqual(series.data_status, MarketDataStatus.PARTIAL)
        self.assertEqual(session.calls[0]["params"]["serviceKey"], "encoded+key=")
        self.assertEqual(session.calls[0]["params"]["likeSrtnCd"], "005930")

    def test_missing_key_returns_unavailable_without_api_call(self) -> None:
        session = FakeSession(stock_payload([]))
        provider = PublicDataMarketDataProvider(
            service_key="",
            stock_price_url="https://example.com/stock",
            session=session,
        )

        series = provider.get_stock_daily_bars("005930", lookback=2)

        self.assertEqual(series.data_status, MarketDataStatus.UNAVAILABLE)
        self.assertEqual(series.bars, [])
        self.assertEqual(session.calls, [])

    def test_stock_rows_are_cached_within_ttl(self) -> None:
        session = FakeSession(
            stock_payload(
                [
                    {
                        "basDt": "20260610",
                        "srtnCd": "005930",
                        "itmsNm": "삼성전자",
                        "mkp": "70100",
                        "hipr": "71300",
                        "lopr": "69900",
                        "clpr": "71000",
                        "trqu": "12345678",
                    },
                ]
            )
        )
        provider = PublicDataMarketDataProvider(
            service_key="encoded%2Bkey%3D",
            stock_price_url="https://example.com/stock",
            session=session,
            cache_ttl_seconds=600,
        )

        first = provider.get_stock_daily_bars("005930", lookback=1)
        second = provider.get_stock_daily_bars("005930", lookback=1)

        self.assertEqual(first.bars[-1].close, 71000.0)
        self.assertEqual(second.bars[-1].close, 71000.0)
        self.assertEqual(len(session.calls), 1)

    def test_zero_cache_ttl_disables_stock_row_cache(self) -> None:
        session = FakeSession(
            stock_payload(
                [
                    {
                        "basDt": "20260610",
                        "srtnCd": "005930",
                        "itmsNm": "삼성전자",
                        "mkp": "70100",
                        "hipr": "71300",
                        "lopr": "69900",
                        "clpr": "71000",
                        "trqu": "12345678",
                    },
                ]
            )
        )
        provider = PublicDataMarketDataProvider(
            service_key="encoded%2Bkey%3D",
            stock_price_url="https://example.com/stock",
            session=session,
            cache_ttl_seconds=0,
        )

        provider.get_stock_daily_bars("005930", lookback=1)
        provider.get_stock_daily_bars("005930", lookback=1)

        self.assertEqual(len(session.calls), 2)

    def test_benchmark_rows_are_cached_within_ttl(self) -> None:
        provider = PublicDataMarketDataProvider(
            service_key="encoded%2Bkey%3D",
            stock_price_url="https://example.com/stock",
            session=FakeSession(stock_payload([])),
            cache_ttl_seconds=600,
        )
        ecos_rows = [
            {"TIME": "20260610", "DATA_VALUE": "3000.5"},
            {"TIME": "20260611", "DATA_VALUE": "3010.5"},
        ]

        with patch("ecos.get_ecos_statistic", return_value=ecos_rows) as get_ecos_statistic:
            first = provider.get_benchmark_daily_bars("005930", lookback=2)
            second = provider.get_benchmark_daily_bars("005930", lookback=2)

        self.assertEqual(first.bars[-1].close, 3010.5)
        self.assertEqual(second.bars[-1].close, 3010.5)
        self.assertEqual(get_ecos_statistic.call_count, 1)

    def test_public_data_cache_expiry_uses_kst_refresh_window(self) -> None:
        self.assertEqual(
            _next_public_data_cache_expiry(datetime(2026, 6, 12, 12, 0, tzinfo=KST)),
            datetime(2026, 6, 12, 13, 10, tzinfo=KST),
        )
        self.assertEqual(
            _next_public_data_cache_expiry(datetime(2026, 6, 12, 14, 0, tzinfo=KST)),
            datetime(2026, 6, 15, 13, 10, tzinfo=KST),
        )
        self.assertEqual(
            _next_public_data_cache_expiry(datetime(2026, 6, 13, 9, 0, tzinfo=KST)),
            datetime(2026, 6, 15, 13, 10, tzinfo=KST),
        )

    def test_schedule_based_cache_expires_after_refresh_window(self) -> None:
        current_time = datetime(2026, 6, 12, 12, 0, tzinfo=KST)

        def clock() -> datetime:
            return current_time

        session = FakeSession(
            stock_payload(
                [
                    {
                        "basDt": "20260610",
                        "srtnCd": "005930",
                        "itmsNm": "삼성전자",
                        "mkp": "70100",
                        "hipr": "71300",
                        "lopr": "69900",
                        "clpr": "71000",
                        "trqu": "12345678",
                    },
                ]
            )
        )
        provider = PublicDataMarketDataProvider(
            service_key="encoded%2Bkey%3D",
            stock_price_url="https://example.com/stock",
            session=session,
            cache_ttl_seconds=-1,
            clock=clock,
        )

        provider.get_stock_daily_bars("005930", lookback=1)
        provider.get_stock_daily_bars("005930", lookback=1)
        self.assertEqual(len(session.calls), 1)

        current_time = datetime(2026, 6, 12, 13, 11, tzinfo=KST)
        provider.get_stock_daily_bars("005930", lookback=1)
        self.assertEqual(len(session.calls), 2)

    def test_normalization_accepts_names_and_vendorish_codes(self) -> None:
        provider = PublicDataMarketDataProvider(service_key="")

        self.assertEqual(provider.normalize_ticker("5930").symbol_code, "005930")
        self.assertEqual(provider.normalize_ticker("005930.KS").symbol_name, "삼성전자")
        self.assertEqual(provider.normalize_ticker("lges").symbol_code, "373220")
        self.assertIsNone(provider.normalize_ticker("999999"))


if __name__ == "__main__":
    unittest.main()
