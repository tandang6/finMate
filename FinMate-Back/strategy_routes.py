from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from market_data.mock_provider import MockMarketDataProvider
from market_data.provider import MarketDataProvider
from market_data.types import MarketDataSourceInfo, MarketDataStatus
from strategies import (
    StrategyActivationState,
    StrategyCheckStatus,
    StrategyDefinition,
    StrategyEvaluation,
    evaluate_live_strategy,
    list_live_strategy_ids,
    load_strategy_catalog,
)
from strategies.catalog import StrategyCatalogPayload
from strategies.checks import combine_data_status
from strategies.contracts import StrategySymbol


router = APIRouter(tags=["strategies"])


class StrategyEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("symbol must not be blank")
        return cleaned


class StrategyEvaluationGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket_id: Literal["applicable", "conditions_insufficient", "data_unavailable"]
    bucket_label: Literal["적용 가능", "지금은 조건 부족", "데이터 부족"]
    evaluations: list[StrategyEvaluation] = Field(default_factory=list)


class NonLiveCatalogGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_state: StrategyActivationState
    strategies: list[StrategyDefinition] = Field(default_factory=list)


class StrategyEvaluateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: str = Field(min_length=1)
    symbol: StrategySymbol
    timeframe: Literal["1d"] = "1d"
    evaluated_at: datetime
    data_status: MarketDataStatus
    source: MarketDataSourceInfo
    live_evaluation_groups: list[StrategyEvaluationGroup]
    non_live_catalog_groups: list[NonLiveCatalogGroup]


_LIVE_GROUPS: tuple[tuple[str, str], ...] = (
    ("applicable", "적용 가능"),
    ("conditions_insufficient", "지금은 조건 부족"),
    ("data_unavailable", "데이터 부족"),
)

_NON_LIVE_STATES: tuple[StrategyActivationState, ...] = (
    StrategyActivationState.EDUCATION_ONLY,
    StrategyActivationState.BLOCKED_BY_DATA,
    StrategyActivationState.DEFERRED,
)


@lru_cache(maxsize=1)
def get_market_data_provider() -> MarketDataProvider:
    return MockMarketDataProvider()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _build_symbol_or_422(provider: MarketDataProvider, query: str) -> StrategySymbol:
    normalized = provider.normalize_ticker(query)
    if normalized is None:
        raise HTTPException(
            status_code=422,
            detail="Unsupported symbol for the current Korean daily-bar universe.",
        )

    return StrategySymbol(
        symbol_code=normalized.symbol_code,
        symbol_name=normalized.symbol_name,
        market=normalized.market,
    )


def _classify_evaluation_group(
    evaluation: StrategyEvaluation,
) -> Literal["applicable", "conditions_insufficient", "data_unavailable"]:
    if evaluation.data_status != MarketDataStatus.FRESH:
        return "data_unavailable"

    shared_blocked = any(
        check.status == StrategyCheckStatus.BLOCKED
        for check in [*evaluation.filters, *evaluation.guardrails]
    )
    if shared_blocked:
        return "data_unavailable"

    numeric_zone_ready = (
        evaluation.buy_zone.lower_price is not None
        and evaluation.buy_zone.upper_price is not None
        and evaluation.target_review_zone.lower_price is not None
        and evaluation.target_review_zone.upper_price is not None
    )
    if numeric_zone_ready:
        return "applicable"

    return "conditions_insufficient"


def _build_live_evaluation_groups(
    evaluations: list[StrategyEvaluation],
) -> list[StrategyEvaluationGroup]:
    grouped = {group_id: [] for group_id, _ in _LIVE_GROUPS}
    for evaluation in evaluations:
        grouped[_classify_evaluation_group(evaluation)].append(evaluation)

    return [
        StrategyEvaluationGroup(
            bucket_id=group_id,
            bucket_label=group_label,
            evaluations=grouped[group_id],
        )
        for group_id, group_label in _LIVE_GROUPS
    ]


def _build_non_live_catalog_groups() -> list[NonLiveCatalogGroup]:
    definitions = list(load_strategy_catalog().strategies)
    return [
        NonLiveCatalogGroup(
            activation_state=activation_state,
            strategies=[
                strategy
                for strategy in definitions
                if strategy.activation_state == activation_state
            ],
        )
        for activation_state in _NON_LIVE_STATES
    ]


@router.get("/catalog", response_model=StrategyCatalogPayload)
def get_strategy_catalog() -> StrategyCatalogPayload:
    return load_strategy_catalog()


@router.post("/evaluate", response_model=StrategyEvaluateResponse)
def evaluate_strategies(
    payload: StrategyEvaluateRequest,
    provider: MarketDataProvider = Depends(get_market_data_provider),
) -> StrategyEvaluateResponse:
    symbol = _build_symbol_or_422(provider, payload.symbol)
    evaluated_at = _utc_now()

    evaluations = [
        evaluate_live_strategy(
            provider,
            strategy_id=strategy_id,
            ticker=symbol.symbol_code,
            evaluated_at=evaluated_at,
        )
        for strategy_id in list_live_strategy_ids()
    ]

    overall_data_status = combine_data_status(*(evaluation.data_status for evaluation in evaluations))

    return StrategyEvaluateResponse(
        catalog_version=load_strategy_catalog().version,
        symbol=symbol,
        evaluated_at=evaluated_at,
        data_status=overall_data_status,
        source=provider.source_info,
        live_evaluation_groups=_build_live_evaluation_groups(evaluations),
        non_live_catalog_groups=_build_non_live_catalog_groups(),
    )
