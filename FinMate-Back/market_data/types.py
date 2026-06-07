from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MarketDataStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class MarketInstrumentType(str, Enum):
    EQUITY = "equity"
    BENCHMARK = "benchmark"


class MarketDataSourceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1)
    provider_name: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    provenance: str = Field(min_length=1)


class BenchmarkDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_id: str = Field(min_length=1)
    benchmark_code: str = Field(min_length=1)
    benchmark_name: str = Field(min_length=1)
    market: str = Field(default="KRX", min_length=1)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("aliases")
    @classmethod
    def _normalize_aliases(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for alias in value:
            normalized = alias.strip()
            if not normalized or normalized in seen:
                continue
            cleaned.append(normalized)
            seen.add(normalized)
        return cleaned


class SupportedTicker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol_code: str = Field(pattern=r"^\d{6}$")
    symbol_name: str = Field(min_length=1)
    market: str = Field(default="KRX", min_length=1)
    aliases: list[str] = Field(default_factory=list)
    primary_benchmark_id: str = Field(min_length=1)

    @field_validator("aliases")
    @classmethod
    def _normalize_aliases(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for alias in value:
            normalized = alias.strip()
            if not normalized or normalized in seen:
                continue
            cleaned.append(normalized)
            seen.add(normalized)
        return cleaned


class DailyBar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_price_range(self) -> "DailyBar":
        if self.low > self.high:
            raise ValueError("low must not be greater than high")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be less than or equal to open and close")
        if self.high < max(self.open, self.close):
            raise ValueError("high must be greater than or equal to open and close")
        return self


class DailyBarSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_type: MarketInstrumentType
    instrument_code: str = Field(min_length=1)
    instrument_name: str | None = None
    market: str = Field(default="KRX", min_length=1)
    timeframe: Literal["1d"] = "1d"
    data_status: MarketDataStatus
    source: MarketDataSourceInfo
    bars: list[DailyBar] = Field(default_factory=list)
    benchmark_id: str | None = None
    status_reason: str | None = None
    requested_lookback: int | None = Field(default=None, ge=1)
    available_bar_count: int = Field(default=0, ge=0)
    as_of_date: date | None = None

    @model_validator(mode="after")
    def _validate_series(self) -> "DailyBarSeries":
        if self.data_status == MarketDataStatus.UNAVAILABLE and self.bars:
            raise ValueError("unavailable series cannot include bars")
        if self.data_status != MarketDataStatus.UNAVAILABLE and not self.bars:
            raise ValueError("available series must include at least one bar")

        if self.bars:
            bar_dates = [bar.date for bar in self.bars]
            if bar_dates != sorted(bar_dates):
                raise ValueError("bars must be sorted by ascending date")
            if len(set(bar_dates)) != len(bar_dates):
                raise ValueError("bars must not contain duplicate dates")
            self.as_of_date = self.as_of_date or bar_dates[-1]
        else:
            self.as_of_date = None

        self.available_bar_count = len(self.bars)
        return self
