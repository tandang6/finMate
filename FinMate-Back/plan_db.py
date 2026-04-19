import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "plans.db"


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_plans (
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
        )
        conn.commit()


def _row_to_plan(row: sqlite3.Row) -> Dict[str, Any]:
    plan = dict(row)
    plan.pop("user_id", None)
    plan["strategy_snapshot"] = json.loads(plan["strategy_snapshot"])
    return plan


def create_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    with _connect() as conn:
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
                plan["plan_id"],
                plan["user_id"],
                plan["symbol"],
                plan["strategy_template_id"],
                json.dumps(plan["strategy_snapshot"], ensure_ascii=False),
                plan["entry_price"],
                plan["stop_loss_price"],
                plan["target_price"],
                plan["position_size_pct"],
                plan["holding_period"],
                plan["one_line_reason"],
                plan.get("note", ""),
                plan["status"],
                plan["created_at"],
                plan["updated_at"],
            ),
        )
        conn.commit()

    return get_plan(plan["plan_id"], plan["user_id"])


def list_plans(user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM user_plans WHERE user_id = ?"
    params: List[Any] = [user_id]

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC"

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_plan(row) for row in rows]


def get_plan(plan_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM user_plans WHERE plan_id = ? AND user_id = ?",
            (plan_id, user_id),
        ).fetchone()

    return _row_to_plan(row) if row else None


def update_plan(plan_id: str, user_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not fields:
        return get_plan(plan_id, user_id)

    assignments = ", ".join(f"{key} = ?" for key in fields.keys())
    params = list(fields.values()) + [plan_id, user_id]

    with _connect() as conn:
        result = conn.execute(
            f"UPDATE user_plans SET {assignments} WHERE plan_id = ? AND user_id = ?",
            params,
        )
        conn.commit()

    if result.rowcount == 0:
        return None

    return get_plan(plan_id, user_id)


def delete_plan(plan_id: str, user_id: str) -> bool:
    with _connect() as conn:
        result = conn.execute(
            "DELETE FROM user_plans WHERE plan_id = ? AND user_id = ?",
            (plan_id, user_id),
        )
        conn.commit()

    return result.rowcount > 0
