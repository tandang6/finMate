import socket
import threading
import time
import unittest

import requests
import uvicorn
from fastapi import FastAPI

from market_data.mock_provider import MockMarketDataProvider
from market_data.types import (
    DailyBarSeries,
    MarketDataStatus,
    MarketInstrumentType,
)
from strategy_routes import get_market_data_provider, router as strategy_router
from strategies.registry import list_live_strategy_ids


def collect_keys(value):
    if isinstance(value, dict):
        keys = set(value.keys())
        for nested in value.values():
            keys.update(collect_keys(nested))
        return keys
    if isinstance(value, list):
        keys = set()
        for nested in value:
            keys.update(collect_keys(nested))
        return keys
    return set()


def reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def build_strategy_test_app(provider: MockMarketDataProvider) -> FastAPI:
    app = FastAPI()
    app.include_router(strategy_router, prefix="/api/strategies")
    app.dependency_overrides[get_market_data_provider] = lambda: provider
    return app


class SupportedUnavailableProvider(MockMarketDataProvider):
    def get_stock_daily_bars(self, ticker: str, *, lookback: int | None = None) -> DailyBarSeries:
        normalized = self.normalize_ticker(ticker)
        if normalized is not None and normalized.symbol_code == "005930":
            return DailyBarSeries(
                instrument_type=MarketInstrumentType.EQUITY,
                instrument_code=normalized.symbol_code,
                instrument_name=normalized.symbol_name,
                market=normalized.market,
                data_status=MarketDataStatus.UNAVAILABLE,
                source=self.source_info,
                bars=[],
                benchmark_id=normalized.primary_benchmark_id,
                requested_lookback=lookback,
                status_reason="Stock daily bars are unavailable in this route-level test provider.",
            )
        return super().get_stock_daily_bars(ticker, lookback=lookback)

    def get_benchmark_daily_bars(self, ticker: str, *, lookback: int | None = None) -> DailyBarSeries:
        normalized = self.normalize_ticker(ticker)
        if normalized is not None and normalized.symbol_code == "005930":
            benchmark = self.get_primary_benchmark(normalized.symbol_code)
            benchmark_code = benchmark.benchmark_code if benchmark is not None else "KOSPI"
            benchmark_id = benchmark.benchmark_id if benchmark is not None else "kospi"
            benchmark_name = benchmark.benchmark_name if benchmark is not None else "KOSPI"
            return DailyBarSeries(
                instrument_type=MarketInstrumentType.BENCHMARK,
                instrument_code=benchmark_code,
                instrument_name=benchmark_name,
                market=normalized.market,
                data_status=MarketDataStatus.UNAVAILABLE,
                source=self.source_info,
                bars=[],
                benchmark_id=benchmark_id,
                requested_lookback=lookback,
                status_reason="Benchmark daily bars are unavailable in this route-level test provider.",
            )
        return super().get_benchmark_daily_bars(ticker, lookback=lookback)


class StrategyApiServer:
    def __init__(self, provider: MockMarketDataProvider) -> None:
        self.provider = provider
        self.app = build_strategy_test_app(provider)
        self.port = reserve_local_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.server = uvicorn.Server(
            uvicorn.Config(
                self.app,
                host="127.0.0.1",
                port=self.port,
                log_level="error",
            )
        )
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> "StrategyApiServer":
        self.thread.start()
        deadline = time.time() + 5
        last_error = None
        while time.time() < deadline:
            try:
                response = requests.get(
                    f"{self.base_url}/api/strategies/catalog",
                    timeout=0.25,
                )
                if response.status_code == 200:
                    return self
            except requests.RequestException as exc:
                last_error = exc
            time.sleep(0.05)

        self.server.should_exit = True
        self.thread.join(timeout=5)
        raise RuntimeError(f"strategy test server did not start: {last_error}")

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)
        self.app.dependency_overrides.clear()


class StrategyRoutesTest(unittest.TestCase):
    def test_catalog_route_returns_full_catalog_with_activation_states(self) -> None:
        with StrategyApiServer(MockMarketDataProvider()) as server:
            response = requests.get(f"{server.base_url}/api/strategies/catalog", timeout=2)

        self.assertEqual(response.status_code, 200)
        catalog = response.json()
        self.assertTrue(catalog["version"])
        self.assertGreaterEqual(len(catalog["strategies"]), 10)

        activation_states = {strategy["activation_state"] for strategy in catalog["strategies"]}
        self.assertEqual(
            activation_states,
            {"live", "education_only", "blocked_by_data", "deferred"},
        )

        live_names = {
            strategy["name"]
            for strategy in catalog["strategies"]
            if strategy["activation_state"] == "live"
        }
        self.assertEqual(
            live_names,
            {
                "MA Support Retest",
                "Resistance Breakout Retest",
                "Pullback",
                "Darvas/Range Breakout",
                "MA Reclaim",
            },
        )

    def test_symbols_route_returns_latest_close_and_price_basis(self) -> None:
        with StrategyApiServer(MockMarketDataProvider()) as server:
            response = requests.get(f"{server.base_url}/api/strategies/symbols", timeout=2)

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["source"]["provider_id"], "mock_market_data")
        self.assertEqual(
            payload["price_basis"],
            "공공데이터포털 금융위원회_주식시세정보 최신 일봉 종가 기준",
        )

        samsung = next(
            symbol for symbol in payload["symbols"] if symbol["symbol_code"] == "005930"
        )
        self.assertEqual(samsung["symbol_name"], "삼성전자")
        self.assertEqual(samsung["currency"], "KRW")
        self.assertEqual(samsung["data_status"], "fresh")
        self.assertGreater(samsung["latest_close"], 0)
        self.assertRegex(samsung["as_of_date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_evaluate_route_returns_grouped_live_results_for_supported_symbol(self) -> None:
        with StrategyApiServer(MockMarketDataProvider()) as server:
            response = requests.post(
                f"{server.base_url}/api/strategies/evaluate",
                json={"symbol": "005930.KS"},
                timeout=2,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["symbol"]["symbol_code"], "005930")
        self.assertEqual(payload["symbol"]["symbol_name"], "삼성전자")
        self.assertEqual(payload["timeframe"], "1d")
        self.assertEqual(payload["data_status"], "fresh")
        self.assertEqual(payload["source"]["provider_id"], "mock_market_data")
        self.assertTrue(payload["catalog_version"])

        groups = payload["live_evaluation_groups"]
        self.assertEqual(
            [group["bucket_id"] for group in groups],
            ["applicable", "conditions_insufficient", "data_unavailable"],
        )
        self.assertEqual(
            [group["bucket_label"] for group in groups],
            ["적용 가능", "지금은 조건 부족", "데이터 부족"],
        )

        evaluations = [evaluation for group in groups for evaluation in group["evaluations"]]
        self.assertEqual(len(evaluations), 5)
        self.assertEqual(
            {evaluation["strategy_id"] for evaluation in evaluations},
            set(list_live_strategy_ids()),
        )
        self.assertTrue(all(evaluation["activation_state"] == "live" for evaluation in evaluations))
        self.assertTrue(all(evaluation["symbol"]["symbol_code"] == "005930" for evaluation in evaluations))
        self.assertTrue(all(evaluation["buy_zone"]["label"] for evaluation in evaluations))
        self.assertTrue(all(evaluation["stop_invalidation_rule"]["rule_text"] for evaluation in evaluations))
        self.assertTrue(all(evaluation["why_this_plan"] for evaluation in evaluations))

        applicable_ids = {evaluation["strategy_id"] for evaluation in groups[0]["evaluations"]}
        conditions_ids = {evaluation["strategy_id"] for evaluation in groups[1]["evaluations"]}
        self.assertEqual(applicable_ids, {"ma_reclaim"})
        self.assertEqual(
            conditions_ids,
            {
                "darvas_range_breakout",
                "ma_support_retest",
                "pullback",
                "resistance_breakout_retest",
            },
        )

        non_live_groups = payload["non_live_catalog_groups"]
        self.assertEqual(
            [group["activation_state"] for group in non_live_groups],
            ["education_only", "blocked_by_data", "deferred"],
        )
        self.assertTrue(
            all(
                strategy["activation_state"] != "live"
                for group in non_live_groups
                for strategy in group["strategies"]
            )
        )

    def test_evaluate_route_returns_partial_data_bucket(self) -> None:
        with StrategyApiServer(MockMarketDataProvider()) as server:
            response = requests.post(
                f"{server.base_url}/api/strategies/evaluate",
                json={"symbol": "035720"},
                timeout=2,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"]["symbol_code"], "035720")
        self.assertEqual(payload["data_status"], "partial")

        groups = payload["live_evaluation_groups"]
        self.assertEqual(len(groups[0]["evaluations"]), 0)
        self.assertEqual(len(groups[1]["evaluations"]), 0)
        self.assertEqual(len(groups[2]["evaluations"]), 5)

    def test_evaluate_route_returns_stale_data_bucket(self) -> None:
        with StrategyApiServer(MockMarketDataProvider()) as server:
            response = requests.post(
                f"{server.base_url}/api/strategies/evaluate",
                json={"symbol": "035420"},
                timeout=2,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"]["symbol_code"], "035420")
        self.assertEqual(payload["data_status"], "stale")

        groups = payload["live_evaluation_groups"]
        self.assertEqual(len(groups[0]["evaluations"]), 0)
        self.assertEqual(len(groups[1]["evaluations"]), 0)
        self.assertEqual(len(groups[2]["evaluations"]), 5)

    def test_evaluate_route_returns_unavailable_data_bucket_for_supported_symbol(self) -> None:
        with StrategyApiServer(SupportedUnavailableProvider()) as server:
            response = requests.post(
                f"{server.base_url}/api/strategies/evaluate",
                json={"symbol": "005930"},
                timeout=2,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"]["symbol_code"], "005930")
        self.assertEqual(payload["data_status"], "unavailable")

        groups = payload["live_evaluation_groups"]
        self.assertEqual(len(groups[0]["evaluations"]), 0)
        self.assertEqual(len(groups[1]["evaluations"]), 0)
        self.assertEqual(len(groups[2]["evaluations"]), 5)
        self.assertTrue(
            all(
                evaluation["buy_zone"]["lower_price"] is None
                and evaluation["target_review_zone"]["lower_price"] is None
                and "unavailable" in evaluation["why_this_plan"].lower()
                for evaluation in groups[2]["evaluations"]
            )
        )

    def test_evaluate_route_rejects_unsupported_symbol(self) -> None:
        with StrategyApiServer(MockMarketDataProvider()) as server:
            response = requests.post(
                f"{server.base_url}/api/strategies/evaluate",
                json={"symbol": "999999"},
                timeout=2,
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Unsupported symbol", response.json()["detail"])

    def test_evaluate_route_response_has_no_ranking_or_recommendation_keys(self) -> None:
        with StrategyApiServer(MockMarketDataProvider()) as server:
            response = requests.post(
                f"{server.base_url}/api/strategies/evaluate",
                json={"symbol": "005930"},
                timeout=2,
            )

        self.assertEqual(response.status_code, 200)
        keys = collect_keys(response.json())
        self.assertTrue(
            {
                "rank",
                "ranking",
                "score",
                "recommendation",
                "recommended",
                "best_strategy",
                "top_pick",
            }.isdisjoint(keys)
        )


if __name__ == "__main__":
    unittest.main()
