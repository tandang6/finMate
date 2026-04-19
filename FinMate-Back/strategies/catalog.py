from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import StrategyDefinition


CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "strategy_catalog.json"


class StrategyCatalogPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    strategies: list[StrategyDefinition]

    @model_validator(mode="after")
    def _validate_uniqueness(self) -> "StrategyCatalogPayload":
        strategy_ids = [strategy.strategy_id for strategy in self.strategies]
        strategy_names = [strategy.name for strategy in self.strategies]
        if len(set(strategy_ids)) != len(strategy_ids):
            raise ValueError("strategy_catalog.json contains duplicate strategy_id values")
        if len(set(strategy_names)) != len(strategy_names):
            raise ValueError("strategy_catalog.json contains duplicate strategy names")
        return self


@lru_cache(maxsize=4)
def load_strategy_catalog(path: Path | None = None) -> StrategyCatalogPayload:
    catalog_path = path or CATALOG_PATH
    with catalog_path.open(encoding="utf-8") as catalog_file:
        raw_payload = json.load(catalog_file)
    return StrategyCatalogPayload.model_validate(raw_payload)


def list_strategy_definitions(path: Path | None = None) -> list[StrategyDefinition]:
    return [strategy.model_copy(deep=True) for strategy in load_strategy_catalog(path).strategies]


def get_strategy_definition(strategy_id: str, path: Path | None = None) -> StrategyDefinition | None:
    for strategy in load_strategy_catalog(path).strategies:
        if strategy.strategy_id == strategy_id:
            return strategy.model_copy(deep=True)
    return None
