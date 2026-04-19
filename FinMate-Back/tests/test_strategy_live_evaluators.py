import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from market_data.mock_provider import MockMarketDataProvider
from strategies import StrategyActivationState, StrategyCheckStatus, StrategyEvaluation
from strategies.registry import evaluate_live_strategy, get_live_strategy_evaluator, list_live_strategy_ids


def business_days(end_date: date, count: int) -> list[date]:
    days: list[date] = []
    cursor = end_date
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))


def linear_series(start: float, end: float, count: int) -> list[float]:
    if count == 1:
        return [round(start, 2)]
    step = (end - start) / (count - 1)
    return [round(start + step * index, 2) for index in range(count)]


def bars_from_closes(
    closes: list[float],
    *,
    volumes: list[int] | None = None,
    end_date: date = date(2026, 4, 17),
) -> list[dict]:
    if volumes is None:
        volumes = [1000] * len(closes)

    bars: list[dict] = []
    previous_close = closes[0]
    for day, close, volume in zip(business_days(end_date, len(closes)), closes, volumes):
        open_price = round(previous_close, 2)
        high_price = round(max(open_price, close) * 1.01, 2)
        low_price = round(min(open_price, close) * 0.99, 2)
        bars.append(
            {
                "date": day.isoformat(),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": round(close, 2),
                "volume": volume,
            }
        )
        previous_close = close
    return bars


def build_test_fixture() -> dict:
    benchmark_closes = linear_series(100.0, 220.0, 260)
    weak_benchmark_closes = linear_series(220.0, 100.0, 260)
    conditions_insufficient_closes = linear_series(240.0, 120.0, 260)
    ma_support_closes = linear_series(100.0, 206.0, 240) + [
        208.0,
        210.0,
        211.0,
        210.0,
        209.0,
        208.0,
        207.0,
        206.0,
        205.0,
        204.0,
        203.0,
        202.0,
        201.0,
        200.0,
        201.0,
        202.0,
        203.0,
        204.0,
        203.0,
        202.0,
    ]
    breakout_retest_closes = linear_series(100.0, 150.0, 224) + (
        [154.0, 156.0, 158.0, 160.0, 159.0, 158.0] * 5
    ) + [164.0, 167.0, 169.0, 166.0, 162.0, 161.0]
    pullback_closes = linear_series(100.0, 180.0, 220) + linear_series(182.0, 228.0, 20) + [
        228.0,
        226.0,
        224.0,
        223.0,
        222.0,
        221.0,
        220.0,
        219.0,
        218.0,
        217.0,
        216.0,
        217.0,
        218.0,
        219.0,
        220.0,
        219.0,
        218.0,
        217.0,
        218.0,
        219.0,
    ]
    darvas_closes = linear_series(100.0, 190.0, 239) + [
        200.0,
        202.0,
        204.0,
        206.0,
        208.0,
        210.0,
        209.0,
        208.0,
        207.0,
        206.0,
        205.0,
        204.0,
        203.0,
        202.0,
        201.0,
        202.0,
        203.0,
        204.0,
        205.0,
        206.0,
        217.0,
    ]
    ma_reclaim_closes = linear_series(100.0, 210.0, 230) + [
        208.0,
        205.0,
        202.0,
        199.0,
        196.0,
        194.0,
        192.0,
        191.0,
        192.0,
        194.0,
        196.0,
        198.0,
        200.0,
        202.0,
        204.0,
        206.0,
        207.0,
        208.0,
        209.0,
        210.0,
        211.0,
        212.0,
        213.0,
        214.0,
        215.0,
        216.0,
        217.0,
        218.0,
        219.0,
        220.0,
    ]

    default_volumes = [1000] * 260
    breakout_volumes = [1000] * 254 + [1600, 1700, 1800, 1750, 1600, 1900]
    darvas_volumes = [1000] * 259 + [2200]

    return {
        "symbols": [
            {
                "symbol_code": "101001",
                "symbol_name": "MA Support Fixture",
                "market": "KRX",
                "aliases": ["MA_SUPPORT"],
                "primary_benchmark_id": "kospi",
                "data_status": "fresh",
                "status_reason": "Fresh fixture for MA support retest evaluator tests.",
                "bars": bars_from_closes(ma_support_closes),
            },
            {
                "symbol_code": "101002",
                "symbol_name": "Breakout Retest Fixture",
                "market": "KRX",
                "aliases": ["BREAKOUT_RETEST"],
                "primary_benchmark_id": "kospi",
                "data_status": "fresh",
                "status_reason": "Fresh fixture for resistance breakout retest evaluator tests.",
                "bars": bars_from_closes(breakout_retest_closes, volumes=breakout_volumes),
            },
            {
                "symbol_code": "101003",
                "symbol_name": "Pullback Fixture",
                "market": "KRX",
                "aliases": ["PULLBACK"],
                "primary_benchmark_id": "kospi",
                "data_status": "fresh",
                "status_reason": "Fresh fixture for pullback evaluator tests.",
                "bars": bars_from_closes(pullback_closes),
            },
            {
                "symbol_code": "101004",
                "symbol_name": "Darvas Fixture",
                "market": "KRX",
                "aliases": ["DARVAS"],
                "primary_benchmark_id": "kospi",
                "data_status": "fresh",
                "status_reason": "Fresh fixture for Darvas/range breakout evaluator tests.",
                "bars": bars_from_closes(darvas_closes, volumes=darvas_volumes),
            },
            {
                "symbol_code": "101005",
                "symbol_name": "MA Reclaim Fixture",
                "market": "KRX",
                "aliases": ["MA_RECLAIM"],
                "primary_benchmark_id": "kospi",
                "data_status": "fresh",
                "status_reason": "Fresh fixture for MA reclaim evaluator tests.",
                "bars": bars_from_closes(ma_reclaim_closes),
            },
            {
                "symbol_code": "101006",
                "symbol_name": "Conditions Insufficient Fixture",
                "market": "KRX",
                "aliases": ["CONDITIONS_INSUFFICIENT"],
                "primary_benchmark_id": "kospi",
                "data_status": "fresh",
                "status_reason": "Fresh fixture that intentionally fails live-strategy conditions.",
                "bars": bars_from_closes(conditions_insufficient_closes, volumes=default_volumes),
            },
            {
                "symbol_code": "101007",
                "symbol_name": "Stale Fixture",
                "market": "KRX",
                "aliases": ["STALE_FIXTURE"],
                "primary_benchmark_id": "kospi",
                "data_status": "stale",
                "status_reason": "Stale fixture for blocked-by-data evaluator tests.",
                "bars": bars_from_closes(ma_support_closes),
            },
            {
                "symbol_code": "101008",
                "symbol_name": "Partial Fixture",
                "market": "KRX",
                "aliases": ["PARTIAL_FIXTURE"],
                "primary_benchmark_id": "kospi",
                "data_status": "partial",
                "status_reason": "Partial fixture for blocked-by-data evaluator tests.",
                "bars": bars_from_closes(ma_support_closes),
            },
            {
                "symbol_code": "101009",
                "symbol_name": "Weak Market Fixture",
                "market": "KRX",
                "aliases": ["WEAK_MARKET"],
                "primary_benchmark_id": "weak_benchmark",
                "data_status": "fresh",
                "status_reason": "Fresh fixture that relies on a weak benchmark regime.",
                "bars": bars_from_closes(ma_support_closes),
            },
            {
                "symbol_code": "101010",
                "symbol_name": "Low Volume Breakout Fixture",
                "market": "KRX",
                "aliases": ["LOW_VOLUME_BREAKOUT"],
                "primary_benchmark_id": "kospi",
                "data_status": "fresh",
                "status_reason": "Fresh breakout-style fixture with weak volume confirmation.",
                "bars": bars_from_closes(breakout_retest_closes, volumes=default_volumes),
            },
        ],
        "benchmarks": [
            {
                "benchmark_id": "kospi",
                "benchmark_code": "KOSPI",
                "benchmark_name": "KOSPI",
                "market": "KRX",
                "aliases": ["KS11"],
                "data_status": "fresh",
                "status_reason": "Fresh positive-regime benchmark for evaluator tests.",
                "bars": bars_from_closes(benchmark_closes, volumes=[1_000_000] * 260),
            },
            {
                "benchmark_id": "weak_benchmark",
                "benchmark_code": "WEAK_BENCHMARK",
                "benchmark_name": "Weak Benchmark",
                "market": "KRX",
                "aliases": ["WEAK"],
                "data_status": "fresh",
                "status_reason": "Fresh benchmark fixture with a non-constructive daily regime.",
                "bars": bars_from_closes(weak_benchmark_closes, volumes=[1_000_000] * 260),
            }
        ],
    }


class LiveStrategyEvaluatorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        cls._temp_dir = temp_dir
        fixture_path = Path(temp_dir.name) / "evaluator_fixture.json"
        fixture_path.write_text(json.dumps(build_test_fixture(), ensure_ascii=False), encoding="utf-8")
        cls.provider = MockMarketDataProvider(fixture_path=fixture_path)
        cls.evaluated_at = datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc)
        cls.applicable_symbols = {
            "ma_support_retest": "101001",
            "resistance_breakout_retest": "101002",
            "pullback": "101003",
            "darvas_range_breakout": "101004",
            "ma_reclaim": "101005",
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp_dir.cleanup()

    def test_live_registry_binds_exactly_the_five_approved_live_strategies(self) -> None:
        self.assertEqual(
            list_live_strategy_ids(),
            [
                "darvas_range_breakout",
                "ma_reclaim",
                "ma_support_retest",
                "pullback",
                "resistance_breakout_retest",
            ],
        )
        self.assertIsNone(get_live_strategy_evaluator("value_quality"))
        self.assertIsNone(get_live_strategy_evaluator("pead"))

    def test_each_live_evaluator_returns_applicable_contract_shape(self) -> None:
        for strategy_id, ticker in self.applicable_symbols.items():
            with self.subTest(strategy_id=strategy_id):
                evaluation = evaluate_live_strategy(
                    self.provider,
                    strategy_id=strategy_id,
                    ticker=ticker,
                    evaluated_at=self.evaluated_at,
                )
                self.assertIsInstance(evaluation, StrategyEvaluation)
                self.assertEqual(evaluation.strategy_id, strategy_id)
                self.assertEqual(evaluation.activation_state, StrategyActivationState.LIVE)
                self.assertEqual(evaluation.timeframe, "1d")
                self.assertEqual(evaluation.data_status.value, "fresh")
                self.assertEqual(evaluation.evaluated_at, self.evaluated_at)
                self.assertEqual(evaluation.symbol.symbol_code, ticker)
                self.assertTrue(evaluation.why_this_plan)
                self.assertTrue(evaluation.first_position_rule)
                self.assertTrue(evaluation.holding_profile)
                self.assertTrue(evaluation.stop_invalidation_rule.rule_text)
                self.assertIsNotNone(evaluation.buy_zone.lower_price)
                self.assertIsNotNone(evaluation.buy_zone.upper_price)
                self.assertIsNotNone(evaluation.target_review_zone.lower_price)
                self.assertIsNotNone(evaluation.target_review_zone.upper_price)
                self.assertTrue(all(check.status == StrategyCheckStatus.MET for check in evaluation.conditions))
                self.assertTrue(all(check.status == StrategyCheckStatus.MET for check in evaluation.guardrails))

    def test_each_live_evaluator_returns_conditions_insufficient_when_setup_is_not_ready(self) -> None:
        for strategy_id in self.applicable_symbols:
            with self.subTest(strategy_id=strategy_id):
                evaluation = evaluate_live_strategy(
                    self.provider,
                    strategy_id=strategy_id,
                    ticker="101006",
                    evaluated_at=self.evaluated_at,
                )
                self.assertEqual(evaluation.activation_state, StrategyActivationState.LIVE)
                self.assertEqual(evaluation.data_status.value, "fresh")
                self.assertIsNone(evaluation.buy_zone.lower_price)
                self.assertIsNone(evaluation.buy_zone.upper_price)
                self.assertIsNone(evaluation.target_review_zone.lower_price)
                self.assertIsNone(evaluation.target_review_zone.upper_price)
                self.assertIn("incomplete", evaluation.why_this_plan)
                self.assertTrue(
                    any(check.status == StrategyCheckStatus.NOT_MET for check in evaluation.conditions + evaluation.filters + evaluation.guardrails)
                )
                freshness = next(check for check in evaluation.guardrails if check.check_id == "data_freshness")
                self.assertEqual(freshness.status, StrategyCheckStatus.MET)

    def test_each_live_evaluator_returns_blocked_by_data_when_freshness_fails(self) -> None:
        for strategy_id in self.applicable_symbols:
            with self.subTest(strategy_id=strategy_id):
                evaluation = evaluate_live_strategy(
                    self.provider,
                    strategy_id=strategy_id,
                    ticker="101007",
                    evaluated_at=self.evaluated_at,
                )
                self.assertEqual(evaluation.activation_state, StrategyActivationState.LIVE)
                self.assertEqual(evaluation.data_status.value, "stale")
                self.assertIsNone(evaluation.buy_zone.lower_price)
                self.assertIsNone(evaluation.buy_zone.upper_price)
                self.assertIsNone(evaluation.target_review_zone.lower_price)
                self.assertIsNone(evaluation.target_review_zone.upper_price)
                self.assertIn("blocked", evaluation.why_this_plan)
                freshness = next(check for check in evaluation.guardrails if check.check_id == "data_freshness")
                self.assertEqual(freshness.status, StrategyCheckStatus.BLOCKED)

    def test_each_live_evaluator_returns_blocked_by_data_when_data_is_partial(self) -> None:
        for strategy_id in self.applicable_symbols:
            with self.subTest(strategy_id=strategy_id):
                evaluation = evaluate_live_strategy(
                    self.provider,
                    strategy_id=strategy_id,
                    ticker="101008",
                    evaluated_at=self.evaluated_at,
                )
                self.assertEqual(evaluation.activation_state, StrategyActivationState.LIVE)
                self.assertEqual(evaluation.data_status.value, "partial")
                self.assertIsNone(evaluation.buy_zone.lower_price)
                self.assertIsNone(evaluation.buy_zone.upper_price)
                self.assertIn("blocked", evaluation.why_this_plan)
                freshness = next(check for check in evaluation.guardrails if check.check_id == "data_freshness")
                self.assertEqual(freshness.status, StrategyCheckStatus.BLOCKED)
                self.assertEqual(freshness.value, "partial")

    def test_evaluator_boundary_rejects_unsupported_ticker(self) -> None:
        with self.assertRaisesRegex(ValueError, "not supported"):
            evaluate_live_strategy(
                self.provider,
                strategy_id="ma_support_retest",
                ticker="999999",
                evaluated_at=self.evaluated_at,
            )

    def test_market_regime_not_met_returns_conditions_insufficient(self) -> None:
        evaluation = evaluate_live_strategy(
            self.provider,
            strategy_id="ma_support_retest",
            ticker="101009",
            evaluated_at=self.evaluated_at,
        )

        self.assertEqual(evaluation.activation_state, StrategyActivationState.LIVE)
        self.assertEqual(evaluation.data_status.value, "fresh")
        self.assertIsNone(evaluation.buy_zone.lower_price)
        self.assertIsNone(evaluation.buy_zone.upper_price)
        self.assertIn("incomplete", evaluation.why_this_plan)

        market_regime = next(check for check in evaluation.guardrails if check.check_id == "market_regime")
        self.assertEqual(market_regime.status, StrategyCheckStatus.NOT_MET)

    def test_breakout_volume_confirmation_not_met_returns_conditions_insufficient(self) -> None:
        evaluation = evaluate_live_strategy(
            self.provider,
            strategy_id="resistance_breakout_retest",
            ticker="101010",
            evaluated_at=self.evaluated_at,
        )

        self.assertEqual(evaluation.activation_state, StrategyActivationState.LIVE)
        self.assertEqual(evaluation.data_status.value, "fresh")
        self.assertIsNone(evaluation.buy_zone.lower_price)
        self.assertIsNone(evaluation.buy_zone.upper_price)
        self.assertIn("incomplete", evaluation.why_this_plan)

        volume_confirmation = next(check for check in evaluation.filters if check.check_id == "volume_confirmation")
        self.assertEqual(volume_confirmation.status, StrategyCheckStatus.NOT_MET)

    def test_non_live_strategies_cannot_be_evaluated(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_live_strategy(
                self.provider,
                strategy_id="value_quality",
                ticker="101001",
                evaluated_at=self.evaluated_at,
            )


if __name__ == "__main__":
    unittest.main()
