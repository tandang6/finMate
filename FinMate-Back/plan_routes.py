import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from plan_db import create_plan, delete_plan, get_plan, list_plans, update_plan


router = APIRouter(tags=["planner"])

TEMPLATES_PATH = Path(__file__).parent / "data" / "strategy_templates.json"
VALID_STATUSES = {"draft", "saved"}


class StrategyTemplate(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    style: str
    # v1 library fields
    one_line_summary: Optional[str] = None
    general_explanation: Optional[str] = None
    why_people_use_it: Optional[str] = None
    when_it_fits_beginner: Optional[str] = None
    when_it_does_not_fit_beginner: Optional[str] = None
    entry_hint: str
    invalidation_condition: Optional[str] = None
    stop_rule: str
    target_rule: str
    position_rule: str
    holding_period: str
    checklist_items: Optional[List[str]] = None
    caution: str
    limitations: Optional[str] = None
    source_note: Optional[List[str]] = None
    evidence_quality: Optional[str] = None
    unsupported_or_weak_claims: Optional[List[str]] = None
    beginner_priority: Optional[int] = None
    disclaimer: str
    # legacy fields kept for backward compatibility with old snapshots
    summary: Optional[str] = None
    description: Optional[str] = None
    core_rationale: Optional[str] = None
    source: Optional[List[str]] = None
    suitable_situation: Optional[str] = None
    caution_summary: Optional[str] = None


class PlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    strategy_template_id: str = Field(min_length=1)
    entry_price: float = Field(gt=0)
    stop_loss_price: float = Field(gt=0)
    target_price: float = Field(gt=0)
    position_size_pct: float = Field(gt=0, le=100)
    holding_period: str = Field(min_length=1)
    one_line_reason: str = Field(min_length=1, max_length=100)
    note: str = Field(default="")
    status: Literal["draft", "saved"] = "saved"


class PlanUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stop_loss_price: Optional[float] = Field(default=None, gt=0)
    target_price: Optional[float] = Field(default=None, gt=0)
    position_size_pct: Optional[float] = Field(default=None, gt=0, le=100)
    holding_period: Optional[str] = Field(default=None, min_length=1)
    one_line_reason: Optional[str] = Field(default=None, min_length=1, max_length=100)
    note: Optional[str] = None
    status: Optional[Literal["draft", "saved"]] = None


class PlanResponse(BaseModel):
    plan_id: str
    symbol: str
    strategy_template_id: str
    strategy_snapshot: Dict[str, Any]
    entry_price: float
    stop_loss_price: float
    target_price: float
    position_size_pct: float
    holding_period: str
    one_line_reason: str
    note: str
    status: Literal["draft", "saved"]
    created_at: str
    updated_at: str


def _require_user_id(user_id: Optional[str]) -> str:
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="X-User-Id header is required")
    return user_id.strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_price_relationship(entry_price: float, stop_loss_price: float, target_price: float) -> None:
    if not (stop_loss_price < entry_price < target_price):
        raise HTTPException(
            status_code=422,
            detail="stop_loss_price must be lower than entry_price, and entry_price must be lower than target_price",
        )


@lru_cache(maxsize=1)
def _load_templates() -> List[Dict[str, Any]]:
    with TEMPLATES_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def _get_template_or_404(template_id: str) -> Dict[str, Any]:
    for template in _load_templates():
        if template["id"] == template_id:
            return template
    raise HTTPException(status_code=404, detail="Strategy template not found")


@router.get("/templates", response_model=List[StrategyTemplate])
def get_templates() -> List[Dict[str, Any]]:
    return _load_templates()


@router.get("/templates/{template_id}", response_model=StrategyTemplate)
def get_template(template_id: str) -> Dict[str, Any]:
    return _get_template_or_404(template_id)


@router.post("/plans", response_model=PlanResponse)
def create_plan_endpoint(
    payload: PlanCreateRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    user_id = _require_user_id(x_user_id)
    _validate_price_relationship(payload.entry_price, payload.stop_loss_price, payload.target_price)
    template = _get_template_or_404(payload.strategy_template_id)
    now = _utc_now()

    plan = create_plan(
        {
            "plan_id": str(uuid4()),
            "user_id": user_id,
            "symbol": payload.symbol.strip(),
            "strategy_template_id": payload.strategy_template_id,
            "strategy_snapshot": template,
            "entry_price": payload.entry_price,
            "stop_loss_price": payload.stop_loss_price,
            "target_price": payload.target_price,
            "position_size_pct": payload.position_size_pct,
            "holding_period": payload.holding_period.strip(),
            "one_line_reason": payload.one_line_reason.strip(),
            "note": payload.note.strip(),
            "status": payload.status,
            "created_at": now,
            "updated_at": now,
        }
    )

    return plan


@router.get("/plans", response_model=List[PlanResponse])
def list_plans_endpoint(
    status: Optional[str] = Query(default=None),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> List[Dict[str, Any]]:
    user_id = _require_user_id(x_user_id)

    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="status must be one of: draft, saved")

    return list_plans(user_id=user_id, status=status)


@router.get("/plans/{plan_id}", response_model=PlanResponse)
def get_plan_endpoint(
    plan_id: str,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    user_id = _require_user_id(x_user_id)
    plan = get_plan(plan_id, user_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.put("/plans/{plan_id}", response_model=PlanResponse)
def update_plan_endpoint(
    plan_id: str,
    payload: PlanUpdateRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, Any]:
    user_id = _require_user_id(x_user_id)
    existing = get_plan(plan_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="At least one field must be provided")

    next_entry = existing["entry_price"]
    next_stop = updates.get("stop_loss_price", existing["stop_loss_price"])
    next_target = updates.get("target_price", existing["target_price"])
    _validate_price_relationship(next_entry, next_stop, next_target)

    if "holding_period" in updates and updates["holding_period"] is not None:
        updates["holding_period"] = updates["holding_period"].strip()
    if "one_line_reason" in updates and updates["one_line_reason"] is not None:
        updates["one_line_reason"] = updates["one_line_reason"].strip()
    if "note" in updates and updates["note"] is not None:
        updates["note"] = updates["note"].strip()

    updates["updated_at"] = _utc_now()

    plan = update_plan(plan_id, user_id, updates)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.delete("/plans/{plan_id}")
def delete_plan_endpoint(
    plan_id: str,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
) -> Dict[str, bool]:
    user_id = _require_user_id(x_user_id)
    deleted = delete_plan(plan_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"deleted": True}
