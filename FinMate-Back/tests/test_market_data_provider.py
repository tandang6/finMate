import unittest

from market_data.mock_provider import FIXTURE_PATH, MockMarketDataProvider
from market_data.provider import MarketDataProvider
from market_data.types import MarketDataStatus, MarketInstrumentType


class MockMarketDataProviderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.provider = MockMarketDataProvider()

    def test_provider_contract_returns_vendor_agnostic_models(self) -> None:
        self.assertIsInstance(self.provider, MarketDataProvider)

        source = self.provider.source_info
        self.assertEqual(source.provider_id, "mock_market_data")
        self.assertEqual(source.dataset, "kr_daily_ohlcv")

        series = self.provider.get_stock_daily_bars("005930", lookback=30)
        self.assertEqual(series.instrument_type, MarketInstrumentType.EQUITY)
        self.assertEqual(series.instrument_code, "005930")
        self.assertEqual(series.instrument_name, "삼성전자")
        self.assertEqual(series.timeframe, "1d")
        self.assertEqual(series.data_status, MarketDataStatus.FRESH)
        self.assertEqual(series.available_bar_count, 30)
        self.assertEqual(series.benchmark_id, "kospi")

    def test_fixture_loading_uses_curated_supported_universe(self) -> None:
        self.assertTrue(FIXTURE_PATH.exists())

        supported = self.provider.list_supported_tickers()
        supported_codes = {ticker.symbol_code for ticker in supported}
        self.assertEqual(
            supported_codes,
            {"005930", "000660", "035420", "035720", "005380", "373220"},
        )

        for code in supported_codes:
            series = self.provider.get_stock_daily_bars(code)
            self.assertGreaterEqual(len(series.bars), 250)

        benchmarks = self.provider.list_supported_benchmarks()
        benchmark_codes = {benchmark.benchmark_code for benchmark in benchmarks}
        self.assertEqual(benchmark_codes, {"KOSPI", "KOSDAQ"})

    def test_ticker_normalization_accepts_codes_names_and_vendorish_formats(self) -> None:
        normalization_cases = {
            "5930": ("005930", "삼성전자"),
            "005930.KS": ("005930", "삼성전자"),
            "krx:000660": ("000660", "SK하이닉스"),
            " NAVER ": ("035420", "NAVER"),
            "카카오": ("035720", "카카오"),
            "lges": ("373220", "LG에너지솔루션"),
        }

        for query, expected in normalization_cases.items():
            with self.subTest(query=query):
                normalized = self.provider.normalize_ticker(query)
                self.assertIsNotNone(normalized)
                self.assertEqual((normalized.symbol_code, normalized.symbol_name), expected)

        self.assertIsNone(self.provider.normalize_ticker("999999"))

    def test_benchmark_lookup_is_hidden_behind_provider_interface(self) -> None:
        benchmark = self.provider.get_primary_benchmark("삼성전자")
        self.assertIsNotNone(benchmark)
        self.assertEqual(benchmark.benchmark_id, "kospi")
        self.assertEqual(benchmark.benchmark_code, "KOSPI")

        benchmark_series = self.provider.get_benchmark_daily_bars("KRX:005930", lookback=20)
        self.assertEqual(benchmark_series.instrument_type, MarketInstrumentType.BENCHMARK)
        self.assertEqual(benchmark_series.instrument_code, "KOSPI")
        self.assertEqual(benchmark_series.available_bar_count, 20)
        self.assertEqual(benchmark_series.data_status, MarketDataStatus.FRESH)

    def test_data_statuses_cover_fresh_stale_partial_and_unavailable(self) -> None:
        self.assertEqual(
            self.provider.get_stock_daily_bars("005930").data_status,
            MarketDataStatus.FRESH,
        )
        self.assertEqual(
            self.provider.get_stock_daily_bars("035420").data_status,
            MarketDataStatus.STALE,
        )
        self.assertEqual(
            self.provider.get_stock_daily_bars("035720").data_status,
            MarketDataStatus.PARTIAL,
        )
        unavailable = self.provider.get_stock_daily_bars("999999")
        self.assertEqual(unavailable.data_status, MarketDataStatus.UNAVAILABLE)
        self.assertEqual(unavailable.bars, [])


if __name__ == "__main__":
    unittest.main()
