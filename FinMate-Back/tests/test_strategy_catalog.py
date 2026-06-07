import unittest
import json
import tempfile
from pathlib import Path

from pydantic import ValidationError

from strategies.catalog import get_strategy_definition, list_strategy_definitions, load_strategy_catalog
from strategies.contracts import StrategyActivationState, StrategyDataRequirement


class StrategyCatalogTest(unittest.TestCase):
    def _write_catalog(self, payload: dict) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        catalog_path = Path(temp_dir.name) / "strategy_catalog.json"
        catalog_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return catalog_path

    def test_catalog_contains_required_foundation_lineup(self) -> None:
        catalog = load_strategy_catalog()
        self.assertEqual(catalog.version, "slice-1a")

        strategies = list_strategy_definitions()
        self.assertGreaterEqual(len(strategies), 12)

        by_name = {strategy.name: strategy for strategy in strategies}
        live_names = {
            strategy.name
            for strategy in strategies
            if strategy.activation_state == StrategyActivationState.LIVE
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

        self.assertEqual(
            by_name["Value/Quality"].activation_state,
            StrategyActivationState.EDUCATION_ONLY,
        )
        self.assertIn(
            StrategyDataRequirement.FUNDAMENTALS,
            by_name["Value/Quality"].required_data,
        )

        for deferred_name in {
            "PEAD",
            "Sector Rotation",
            "VCP",
            "Gap-and-Go",
            "RSI Oversold Rebound",
            "BB Squeeze",
        }:
            with self.subTest(strategy=deferred_name):
                self.assertEqual(
                    by_name[deferred_name].activation_state,
                    StrategyActivationState.DEFERRED,
                )

        self.assertEqual(
            by_name["Relative Strength Leader"].activation_state,
            StrategyActivationState.BLOCKED_BY_DATA,
        )

    def test_live_strategies_require_evaluator_bindings_and_daily_timeframe_only(self) -> None:
        strategies = list_strategy_definitions()
        for strategy in strategies:
            with self.subTest(strategy=strategy.strategy_id):
                self.assertEqual(strategy.supported_timeframes, ["1d"])
                if strategy.activation_state == StrategyActivationState.LIVE:
                    self.assertIsNotNone(strategy.evaluator_id)

    def test_strategy_lookup_returns_canonical_definition(self) -> None:
        strategy = get_strategy_definition("ma_support_retest")
        self.assertIsNotNone(strategy)
        self.assertEqual(strategy.name, "MA Support Retest")
        self.assertIsNone(get_strategy_definition("not_real"))

    def test_catalog_rejects_duplicate_strategy_ids(self) -> None:
        catalog_path = self._write_catalog(
            {
                "version": "test",
                "strategies": [
                    {
                        "strategy_id": "duplicate",
                        "name": "First",
                        "activation_state": "education_only",
                        "activation_reason": "Test case",
                        "summary": "Summary",
                        "when_to_use": "Use",
                        "when_not_to_use": "Avoid",
                        "holding_profile": "Profile",
                        "required_data": ["daily_bars"],
                        "disclaimer": "Disclaimer",
                    },
                    {
                        "strategy_id": "duplicate",
                        "name": "Second",
                        "activation_state": "deferred",
                        "activation_reason": "Test case",
                        "summary": "Summary",
                        "when_to_use": "Use",
                        "when_not_to_use": "Avoid",
                        "holding_profile": "Profile",
                        "required_data": ["daily_bars"],
                        "disclaimer": "Disclaimer",
                    },
                ],
            }
        )

        with self.assertRaises(ValidationError):
            load_strategy_catalog(catalog_path)

    def test_catalog_rejects_duplicate_strategy_names(self) -> None:
        catalog_path = self._write_catalog(
            {
                "version": "test",
                "strategies": [
                    {
                        "strategy_id": "first",
                        "name": "Same Name",
                        "activation_state": "education_only",
                        "activation_reason": "Test case",
                        "summary": "Summary",
                        "when_to_use": "Use",
                        "when_not_to_use": "Avoid",
                        "holding_profile": "Profile",
                        "required_data": ["daily_bars"],
                        "disclaimer": "Disclaimer",
                    },
                    {
                        "strategy_id": "second",
                        "name": "Same Name",
                        "activation_state": "deferred",
                        "activation_reason": "Test case",
                        "summary": "Summary",
                        "when_to_use": "Use",
                        "when_not_to_use": "Avoid",
                        "holding_profile": "Profile",
                        "required_data": ["daily_bars"],
                        "disclaimer": "Disclaimer",
                    },
                ],
            }
        )

        with self.assertRaises(ValidationError):
            load_strategy_catalog(catalog_path)

    def test_catalog_rejects_live_strategy_without_evaluator_binding(self) -> None:
        catalog_path = self._write_catalog(
            {
                "version": "test",
                "strategies": [
                    {
                        "strategy_id": "live_without_evaluator",
                        "name": "Live Without Evaluator",
                        "activation_state": "live",
                        "activation_reason": "Test case",
                        "summary": "Summary",
                        "when_to_use": "Use",
                        "when_not_to_use": "Avoid",
                        "holding_profile": "Profile",
                        "required_data": ["daily_bars"],
                        "disclaimer": "Disclaimer",
                    }
                ],
            }
        )

        with self.assertRaises(ValidationError):
            load_strategy_catalog(catalog_path)

    def test_catalog_rejects_invalid_activation_state(self) -> None:
        catalog_path = self._write_catalog(
            {
                "version": "test",
                "strategies": [
                    {
                        "strategy_id": "bad_activation_state",
                        "name": "Bad Activation State",
                        "activation_state": "recommended",
                        "activation_reason": "Test case",
                        "summary": "Summary",
                        "when_to_use": "Use",
                        "when_not_to_use": "Avoid",
                        "holding_profile": "Profile",
                        "required_data": ["daily_bars"],
                        "disclaimer": "Disclaimer",
                    }
                ],
            }
        )

        with self.assertRaises(ValidationError):
            load_strategy_catalog(catalog_path)


if __name__ == "__main__":
    unittest.main()
