import json
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI

import plan_db
from market_data.mock_provider import MockMarketDataProvider
from plan_db import create_plan as create_plan_record
from plan_db import get_plan as get_plan_record
from plan_db import init_db
from plan_routes import router as planner_router
from strategies.registry import evaluate_live_strategy


LEGACY_SCHEMA_SQL = """
CREATE TABLE user_plans (
    plan_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    strategy_template_id TEXT NOT NULL,
    strategy_snapshot TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss_price REAL NOT NULL,
    target_price REAL NOT NULL,
    position_size_pct REAL NOT NULL,
    holding_period TEXT NOT NULL,
    one_line_reason TEXT NOT NULL,
    note TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'saved',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def build_evaluation_snapshot(strategy_id: str = "ma_reclaim", ticker: str = "005930") -> dict:
    evaluation = evaluate_live_strategy(
        MockMarketDataProvider(),
        strategy_id=strategy_id,
        ticker=ticker,
        evaluated_at=datetime(2026, 4, 19, 0, 0, tzinfo=timezone.utc),
    )
    return evaluation.model_dump(mode="json")


def write_legacy_plan_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(LEGACY_SCHEMA_SQL)
        conn.execute(
            """
            INSERT INTO user_plans (
                plan_id,
                user_id,
                symbol,
                strategy_template_id,
                strategy_snapshot,
                entry_price,
                stop_loss_price,
                target_price,
                position_size_pct,
                holding_period,
                one_line_reason,
                note,
                status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-plan-1",
                "user-1",
                "삼성전자",
                "ma_reclaim",
                json.dumps({"id": "legacy-template", "name": "Legacy Template"}, ensure_ascii=False),
                100.0,
                90.0,
                120.0,
                25.0,
                "2주",
                "legacy row",
                "migrated",
                "saved",
                "2025-01-01T00:00:00Z",
                "2025-01-02T00:00:00Z",
            ),
        )
        conn.commit()


class TemporaryPlannerDb:
    def __enter__(self) -> "TemporaryPlannerDb":
        self._temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._temp_dir.name) / "plans.db"
        self._original_db_path = plan_db.DB_PATH
        plan_db.DB_PATH = self.db_path
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        plan_db.DB_PATH = self._original_db_path
        self._temp_dir.cleanup()


class PlannerApiServer:
    def __init__(self) -> None:
        self.app = FastAPI()
        self.app.include_router(planner_router, prefix="/api/planner")
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

    def __enter__(self) -> "PlannerApiServer":
        init_db()
        self.thread.start()
        deadline = time.time() + 5
        last_error = None
        while time.time() < deadline:
            try:
                response = requests.get(
                    f"{self.base_url}/api/planner/templates",
                    timeout=0.25,
                )
                if response.status_code == 200:
                    return self
            except requests.RequestException as exc:
                last_error = exc
            time.sleep(0.05)

        self.server.should_exit = True
        self.thread.join(timeout=5)
        raise RuntimeError(f"planner test server did not start: {last_error}")

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


class PlanStorageMigrationTest(unittest.TestCase):
    def test_init_db_migrates_legacy_rows_and_preserves_values(self) -> None:
        with TemporaryPlannerDb() as temp_db:
            write_legacy_plan_db(temp_db.db_path)

            init_db()

            with sqlite3.connect(temp_db.db_path) as conn:
                columns = [row[1] for row in conn.execute("PRAGMA table_info(user_plans)").fetchall()]

            self.assertEqual(
                columns,
                [
                    "plan_id",
                    "user_id",
                    "symbol",
                    "strategy_template_id",
                    "strategy_snapshot",
                    "evaluation_snapshot",
                    "entry_price_override",
                    "stop_loss_price_override",
                    "target_price_override",
                    "position_size_override_pct",
                    "holding_period",
                    "one_line_reason",
                    "note",
                    "status",
                    "created_at",
                    "updated_at",
                ],
            )

            legacy_plan = get_plan_record("legacy-plan-1", "user-1")
            self.assertIsNotNone(legacy_plan)
            self.assertIsNone(legacy_plan["evaluation_snapshot"])
            self.assertEqual(legacy_plan["entry_price_override"], 100.0)
            self.assertEqual(legacy_plan["stop_loss_price_override"], 90.0)
            self.assertEqual(legacy_plan["target_price_override"], 120.0)
            self.assertEqual(legacy_plan["position_size_override_pct"], 25.0)
            self.assertEqual(legacy_plan["strategy_snapshot"]["name"], "Legacy Template")


class PlannerRoutesTest(unittest.TestCase):
    def test_create_plan_from_evaluation_snapshot_without_exact_overrides(self) -> None:
        payload = {
            "symbol": "임의 표시 이름",
            "strategy_template_id": "ma_reclaim",
            "evaluation_snapshot": build_evaluation_snapshot("ma_reclaim"),
            "holding_period": "2주",
            "one_line_reason": "snapshot-first create",
            "note": "no overrides",
            "status": "saved",
        }

        with TemporaryPlannerDb() as temp_db, PlannerApiServer() as server:
            response = requests.post(
                f"{server.base_url}/api/planner/plans",
                headers={"X-User-Id": "user-1"},
                json=payload,
                timeout=2,
            )

        self.assertEqual(response.status_code, 200)
        plan = response.json()
        self.assertEqual(plan["strategy_template_id"], "ma_reclaim")
        self.assertEqual(plan["symbol"], "삼성전자")
        self.assertEqual(plan["evaluation_snapshot"]["strategy_id"], "ma_reclaim")
        self.assertEqual(plan["strategy_snapshot"]["strategy_id"], "ma_reclaim")
        self.assertIsNone(plan["entry_price_override"])
        self.assertIsNone(plan["stop_loss_price_override"])
        self.assertIsNone(plan["target_price_override"])
        self.assertIsNone(plan["position_size_override_pct"])

    def test_create_plan_with_optional_overrides(self) -> None:
        snapshot = build_evaluation_snapshot("ma_reclaim")
        payload = {
            "strategy_template_id": "ma_reclaim",
            "evaluation_snapshot": snapshot,
            "entry_price_override": snapshot["buy_zone"]["lower_price"],
            "stop_loss_price_override": round(snapshot["buy_zone"]["lower_price"] * 0.95, 2),
            "target_price_override": snapshot["target_review_zone"]["lower_price"],
            "position_size_override_pct": 20.0,
            "holding_period": "3주",
            "one_line_reason": "with overrides",
            "status": "draft",
        }

        with TemporaryPlannerDb() as temp_db, PlannerApiServer() as server:
            response = requests.post(
                f"{server.base_url}/api/planner/plans",
                headers={"X-User-Id": "user-1"},
                json=payload,
                timeout=2,
            )

        self.assertEqual(response.status_code, 200)
        plan = response.json()
        self.assertEqual(plan["entry_price_override"], payload["entry_price_override"])
        self.assertEqual(plan["stop_loss_price_override"], payload["stop_loss_price_override"])
        self.assertEqual(plan["target_price_override"], payload["target_price_override"])
        self.assertEqual(plan["position_size_override_pct"], 20.0)
        self.assertEqual(plan["status"], "draft")

    def test_update_override_fields_preserves_evaluation_snapshot(self) -> None:
        snapshot = build_evaluation_snapshot("ma_reclaim")
        create_payload = {
            "strategy_template_id": "ma_reclaim",
            "evaluation_snapshot": snapshot,
            "holding_period": "2주",
            "one_line_reason": "before update",
            "status": "saved",
        }

        with TemporaryPlannerDb() as temp_db, PlannerApiServer() as server:
            create_response = requests.post(
                f"{server.base_url}/api/planner/plans",
                headers={"X-User-Id": "user-1"},
                json=create_payload,
                timeout=2,
            )
            self.assertEqual(create_response.status_code, 200)
            plan_id = create_response.json()["plan_id"]

            update_response = requests.put(
                f"{server.base_url}/api/planner/plans/{plan_id}",
                headers={"X-User-Id": "user-1"},
                json={
                    "entry_price_override": snapshot["buy_zone"]["lower_price"],
                    "stop_loss_price_override": round(snapshot["buy_zone"]["lower_price"] * 0.95, 2),
                    "target_price_override": snapshot["target_review_zone"]["lower_price"],
                    "position_size_override_pct": 15.0,
                    "note": "updated",
                },
                timeout=2,
            )

        self.assertEqual(update_response.status_code, 200)
        updated_plan = update_response.json()
        self.assertEqual(updated_plan["evaluation_snapshot"]["strategy_id"], "ma_reclaim")
        self.assertEqual(updated_plan["entry_price_override"], snapshot["buy_zone"]["lower_price"])
        self.assertEqual(updated_plan["position_size_override_pct"], 15.0)
        self.assertEqual(updated_plan["note"], "updated")

    def test_list_reads_legacy_and_snapshot_first_rows_together(self) -> None:
        snapshot = build_evaluation_snapshot("ma_reclaim")

        with TemporaryPlannerDb() as temp_db:
            write_legacy_plan_db(temp_db.db_path)
            init_db()
            create_plan_record(
                {
                    "plan_id": "new-plan-1",
                    "user_id": "user-1",
                    "symbol": "삼성전자",
                    "strategy_template_id": "ma_reclaim",
                    "strategy_snapshot": {"strategy_id": "ma_reclaim", "name": "MA Reclaim"},
                    "evaluation_snapshot": snapshot,
                    "entry_price_override": None,
                    "stop_loss_price_override": None,
                    "target_price_override": None,
                    "position_size_override_pct": None,
                    "holding_period": "2주",
                    "one_line_reason": "new row",
                    "note": "",
                    "status": "saved",
                    "created_at": "2026-04-19T00:00:00Z",
                    "updated_at": "2026-04-19T00:00:00Z",
                }
            )
            with PlannerApiServer() as server:
                response = requests.get(
                    f"{server.base_url}/api/planner/plans",
                    headers={"X-User-Id": "user-1"},
                    timeout=2,
                )

        self.assertEqual(response.status_code, 200)
        plans = response.json()
        self.assertEqual(len(plans), 2)
        plans_by_id = {plan["plan_id"]: plan for plan in plans}
        self.assertIsNone(plans_by_id["legacy-plan-1"]["evaluation_snapshot"])
        self.assertEqual(plans_by_id["legacy-plan-1"]["entry_price_override"], 100.0)
        self.assertEqual(plans_by_id["new-plan-1"]["evaluation_snapshot"]["strategy_id"], "ma_reclaim")
        self.assertIsNone(plans_by_id["new-plan-1"]["entry_price_override"])


if __name__ == "__main__":
    unittest.main()
