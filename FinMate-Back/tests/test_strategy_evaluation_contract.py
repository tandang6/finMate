import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from market_data.types import MarketDataStatus
from strategies.contracts import (
    PriceZone,
    StrategyActivationState,
    StrategyCheck,
    StrategyCheckStatus,
    StrategyEvaluation,
    StrategyRule,
    StrategySymbol,
)


class StrategyEvaluationContractTest(unittest.TestCase):
    def _build_valid_payload(self) -> dict:
        return {
            "strategy_id": "ma_support_retest",
            "strategy_name": "MA Support Retest",
            "activation_state": StrategyActivationState.LIVE,
            "symbol": StrategySymbol(symbol_code="005930", symbol_name="삼성전자", market="KRX"),
            "timeframe": "1d",
            "evaluated_at": datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc),
            "data_status": MarketDataStatus.FRESH,
            "conditions": [
                StrategyCheck(
                    check_id="trend_up",
                    label="Trend Regime",
                    status=StrategyCheckStatus.MET,
                    detail="The daily trend remains constructive.",
                    value="50DMA > 200DMA",
                )
            ],
            "filters": [
                StrategyCheck(
                    check_id="volume_confirmation",
                    label="Volume Confirmation",
                    status=StrategyCheckStatus.NOT_EVALUATED,
                    detail="Volume filter is reserved for future evaluator logic.",
                )
            ],
            "guardrails": [
                StrategyCheck(
                    check_id="data_freshness",
                    label="Data Freshness",
                    status=StrategyCheckStatus.MET,
                    detail="The mock provider returned a fresh daily series.",
                )
            ],
            "buy_zone": PriceZone(
                label="Support Zone",
                description="Plan entries only while price holds near the rising support area.",
                lower_price=71500,
                upper_price=73500,
            ),
            "stop_invalidation_rule": StrategyRule(
                label="Support Break",
                rule_text="Exit the setup if price closes clearly below the support zone.",
            ),
            "target_review_zone": PriceZone(
                label="Resistance Review Zone",
                description="Review the plan near the next daily resistance area.",
                lower_price=78500,
                upper_price=80500,
            ),
            "first_position_rule": "Start with a smaller first position and add only if the daily setup confirms.",
            "holding_profile": "Short-to-medium daily swing while the trend structure remains constructive.",
            "why_this_plan": "The daily structure is constructive, data is fresh, and the plan remains zone-based.",
        }

    def test_strategy_evaluation_serializes_and_round_trips(self) -> None:
        evaluation = StrategyEvaluation(**self._build_valid_payload())

        serialized = evaluation.model_dump(mode="json")
        self.assertEqual(serialized["timeframe"], "1d")
        self.assertEqual(serialized["data_status"], "fresh")
        self.assertEqual(serialized["symbol"]["symbol_code"], "005930")

        round_trip = StrategyEvaluation.model_validate_json(evaluation.model_dump_json())
        self.assertEqual(round_trip.strategy_id, "ma_support_retest")
        self.assertEqual(round_trip.buy_zone.lower_price, 71500)

    def test_price_zone_rejects_invalid_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            PriceZone(
                label="Broken Zone",
                description="This should fail validation.",
                lower_price=80000,
                upper_price=79000,
            )

    def test_strategy_evaluation_requires_timezone_aware_timestamp(self) -> None:
        payload = self._build_valid_payload()
        payload["evaluated_at"] = datetime(2026, 4, 19, 9, 0)
        with self.assertRaises(ValidationError):
            StrategyEvaluation(**payload)

    def test_strategy_evaluation_rejects_invalid_timeframe(self) -> None:
        payload = self._build_valid_payload()
        payload["timeframe"] = "4h"
        with self.assertRaises(ValidationError):
            StrategyEvaluation(**payload)

    def test_strategy_evaluation_requires_nested_symbol_shape(self) -> None:
        payload = self._build_valid_payload()
        payload.pop("symbol")
        payload["symbol_code"] = "005930"
        payload["symbol_name"] = "삼성전자"

        with self.assertRaises(ValidationError):
            StrategyEvaluation(**payload)


if __name__ == "__main__":
    unittest.main()
