from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from market_data.types import MarketDataStatus


class StrategyActivationState(str, Enum):
    LIVE = "live"
    EDUCATION_ONLY = "education_only"
    BLOCKED_BY_DATA = "blocked_by_data"
    DEFERRED = "deferred"


class StrategyKind(str, Enum):
    TRIGGER = "trigger"
    FILTER = "filter"
    GUARDRAIL = "guardrail"


class StrategyDataRequirement(str, Enum):
    DAILY_BARS = "daily_bars"
    DAILY_VOLUME = "daily_volume"
    BENCHMARK_DAILY_BARS = "benchmark_daily_bars"
    FUNDAMENTALS = "fundamentals"
    RELATIVE_STRENGTH = "relative_strength"
    SECTOR_DATA = "sector_data"
    EARNINGS_EVENTS = "earnings_events"
    VOLATILITY_INDICATORS = "volatility_indicators"


class StrategyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1)
    activation_state: StrategyActivationState
    activation_reason: str = Field(min_length=1)
    kind: StrategyKind = StrategyKind.TRIGGER
    supported_timeframes: list[Literal["1d"]] = Field(default_factory=lambda: ["1d"])
    summary: str = Field(min_length=1)
    when_to_use: str = Field(min_length=1)
    when_not_to_use: str = Field(min_length=1)
    holding_profile: str = Field(min_length=1)
    required_data: list[StrategyDataRequirement] = Field(default_factory=list)
    evaluator_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    disclaimer: str = Field(min_length=1)

    @field_validator("supported_timeframes")
    @classmethod
    def _validate_timeframes(cls, value: list[str]) -> list[str]:
        if value != ["1d"]:
            raise ValueError("Slice 1 foundation supports only the 1d timeframe")
        return value

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for tag in value:
            normalized = tag.strip()
            if not normalized or normalized in seen:
                continue
            cleaned.append(normalized)
            seen.add(normalized)
        return cleaned

    @model_validator(mode="after")
    def _validate_activation_rules(self) -> "StrategyDefinition":
        if self.activation_state == StrategyActivationState.LIVE and not self.evaluator_id:
            raise ValueError("live strategies must declare an evaluator_id")
        return self


class StrategySymbol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol_code: str = Field(pattern=r"^\d{6}$")
    symbol_name: str = Field(min_length=1)
    market: str = Field(default="KRX", min_length=1)


class StrategyCheckStatus(str, Enum):
    MET = "met"
    NOT_MET = "not_met"
    BLOCKED = "blocked"
    NOT_EVALUATED = "not_evaluated"


class StrategyCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    status: StrategyCheckStatus
    detail: str = Field(min_length=1)
    value: str | None = None


class PriceZone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    lower_price: float | None = Field(default=None, gt=0)
    upper_price: float | None = Field(default=None, gt=0)
    unit: Literal["KRW"] = "KRW"

    @model_validator(mode="after")
    def _validate_bounds(self) -> "PriceZone":
        if self.lower_price is not None and self.upper_price is not None and self.lower_price > self.upper_price:
            raise ValueError("lower_price must be less than or equal to upper_price")
        return self


class StrategyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1)
    rule_text: str = Field(min_length=1)


class StrategyEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str = Field(min_length=1)
    strategy_name: str = Field(min_length=1)
    activation_state: StrategyActivationState
    symbol: StrategySymbol
    timeframe: Literal["1d"] = "1d"
    evaluated_at: datetime
    data_status: MarketDataStatus
    conditions: list[StrategyCheck] = Field(default_factory=list)
    filters: list[StrategyCheck] = Field(default_factory=list)
    guardrails: list[StrategyCheck] = Field(default_factory=list)
    buy_zone: PriceZone
    stop_invalidation_rule: StrategyRule
    target_review_zone: PriceZone
    first_position_rule: str = Field(min_length=1)
    holding_profile: str = Field(min_length=1)
    why_this_plan: str = Field(min_length=1)

    @field_validator("evaluated_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value
