import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("FINMATE_PLAN_DB_PATH", DATA_DIR / "plans.db"))

LATEST_SCHEMA_VERSION = 2
LEGACY_PLAN_COLUMNS = (
    "plan_id",
    "user_id",
    "symbol",
    "strategy_template_id",
    "strategy_snapshot",
    "entry_price",
    "stop_loss_price",
    "target_price",
    "position_size_pct",
    "holding_period",
    "one_line_reason",
    "note",
    "status",
    "created_at",
    "updated_at",
)
LATEST_PLAN_COLUMNS = (
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
)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        columns = _get_table_columns(conn, "user_plans")
        if not columns:
            _create_latest_user_plans_table(conn)
        elif _is_legacy_schema(columns):
            _migrate_legacy_user_plans(conn)
        elif not _is_latest_schema(columns):
            raise RuntimeError("user_plans schema is not recognized by the current planner storage layer")

        conn.execute(f"PRAGMA user_version = {LATEST_SCHEMA_VERSION}")
        conn.commit()


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row["name"] for row in rows]


def _is_legacy_schema(columns: list[str]) -> bool:
    return tuple(columns) == LEGACY_PLAN_COLUMNS


def _is_latest_schema(columns: list[str]) -> bool:
    return tuple(columns) == LATEST_PLAN_COLUMNS


def _create_latest_user_plans_table(
    conn: sqlite3.Connection,
    *,
    table_name: str = "user_plans",
) -> None:
    conn.execute(
        f"""
        CREATE TABLE {table_name} (
            plan_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            strategy_template_id TEXT NOT NULL,
            strategy_snapshot TEXT NOT NULL,
            evaluation_snapshot TEXT,
            entry_price_override REAL,
            stop_loss_price_override REAL,
            target_price_override REAL,
            position_size_override_pct REAL,
            holding_period TEXT NOT NULL,
            one_line_reason TEXT NOT NULL,
            note TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'saved',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _migrate_legacy_user_plans(conn: sqlite3.Connection) -> None:
    temp_table = "user_plans__v2"
    conn.execute(f"DROP TABLE IF EXISTS {temp_table}")
    _create_latest_user_plans_table(conn, table_name=temp_table)
    conn.execute(
        f"""
        INSERT INTO {temp_table} (
            plan_id,
            user_id,
            symbol,
            strategy_template_id,
            strategy_snapshot,
            evaluation_snapshot,
            entry_price_override,
            stop_loss_price_override,
            target_price_override,
            position_size_override_pct,
            holding_period,
            one_line_reason,
            note,
            status,
            created_at,
            updated_at
        )
        SELECT
            plan_id,
            user_id,
            symbol,
            strategy_template_id,
            strategy_snapshot,
            NULL,
            entry_price,
            stop_loss_price,
            target_price,
            position_size_pct,
            holding_period,
            one_line_reason,
            COALESCE(note, ''),
            status,
            created_at,
            updated_at
        FROM user_plans
        """
    )
    conn.execute("DROP TABLE user_plans")
    conn.execute(f"ALTER TABLE {temp_table} RENAME TO user_plans")


def _decode_json(value: str | None) -> Dict[str, Any] | None:
    if value is None:
        return None
    return json.loads(value)


def _row_to_plan(row: sqlite3.Row) -> Dict[str, Any]:
    plan = dict(row)
    plan.pop("user_id", None)
    plan["strategy_snapshot"] = _decode_json(plan["strategy_snapshot"])
    plan["evaluation_snapshot"] = _decode_json(plan["evaluation_snapshot"])
    plan["note"] = plan.get("note") or ""
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
                evaluation_snapshot,
                entry_price_override,
                stop_loss_price_override,
                target_price_override,
                position_size_override_pct,
                holding_period,
                one_line_reason,
                note,
                status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan["plan_id"],
                plan["user_id"],
                plan["symbol"],
                plan["strategy_template_id"],
                json.dumps(plan["strategy_snapshot"], ensure_ascii=False),
                json.dumps(plan["evaluation_snapshot"], ensure_ascii=False)
                if plan.get("evaluation_snapshot") is not None
                else None,
                plan.get("entry_price_override"),
                plan.get("stop_loss_price_override"),
                plan.get("target_price_override"),
                plan.get("position_size_override_pct"),
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

    prepared_fields = dict(fields)
    for json_field in ("strategy_snapshot", "evaluation_snapshot"):
        if json_field in prepared_fields:
            value = prepared_fields[json_field]
            prepared_fields[json_field] = (
                json.dumps(value, ensure_ascii=False) if value is not None else None
            )

    assignments = ", ".join(f"{key} = ?" for key in prepared_fields.keys())
    params = list(prepared_fields.values()) + [plan_id, user_id]

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
