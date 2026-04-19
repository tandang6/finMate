from __future__ import annotations

from dataclasses import dataclass

from market_data.types import DailyBarSeries


@dataclass(frozen=True)
class RangeBox:
    high: float
    low: float
    width_ratio: float


@dataclass(frozen=True)
class BreakoutAnchor:
    resistance: float
    support: float


@dataclass(frozen=True)
class DailySeriesView:
    series: DailyBarSeries
    closes: tuple[float, ...]
    highs: tuple[float, ...]
    lows: tuple[float, ...]
    volumes: tuple[int, ...]

    @classmethod
    def from_series(cls, series: DailyBarSeries) -> "DailySeriesView":
        return cls(
            series=series,
            closes=tuple(bar.close for bar in series.bars),
            highs=tuple(bar.high for bar in series.bars),
            lows=tuple(bar.low for bar in series.bars),
            volumes=tuple(bar.volume for bar in series.bars),
        )

    @property
    def latest_close(self) -> float:
        return self.closes[-1]

    @property
    def latest_high(self) -> float:
        return self.highs[-1]

    @property
    def latest_low(self) -> float:
        return self.lows[-1]

    @property
    def latest_volume(self) -> int:
        return self.volumes[-1]

    def sma(self, window: int, *, offset: int = 0) -> float | None:
        values = self._window_slice(self.closes, window, exclude_recent=offset)
        if values is None:
            return None
        return sum(values) / len(values)

    def average_volume(self, window: int, *, offset: int = 0) -> float | None:
        values = self._window_slice(self.volumes, window, exclude_recent=offset)
        if values is None:
            return None
        return sum(values) / len(values)

    def volume_ratio(self, window: int, *, offset: int = 0) -> float | None:
        average_volume = self.average_volume(window, offset=offset)
        if average_volume in (None, 0):
            return None
        target_index = len(self.volumes) - 1 - offset
        if target_index < 0:
            return None
        return self.volumes[target_index] / average_volume

    def rolling_high(self, window: int, *, exclude_recent: int = 0) -> float | None:
        values = self._window_slice(self.highs, window, exclude_recent=exclude_recent)
        return max(values) if values is not None else None

    def rolling_low(self, window: int, *, exclude_recent: int = 0) -> float | None:
        values = self._window_slice(self.lows, window, exclude_recent=exclude_recent)
        return min(values) if values is not None else None

    def rolling_close_high(self, window: int, *, exclude_recent: int = 0) -> float | None:
        values = self._window_slice(self.closes, window, exclude_recent=exclude_recent)
        return max(values) if values is not None else None

    def rolling_close_low(self, window: int, *, exclude_recent: int = 0) -> float | None:
        values = self._window_slice(self.closes, window, exclude_recent=exclude_recent)
        return min(values) if values is not None else None

    def range_box(self, window: int, *, exclude_recent: int = 0) -> RangeBox | None:
        high = self.rolling_high(window, exclude_recent=exclude_recent)
        low = self.rolling_low(window, exclude_recent=exclude_recent)
        if high is None or low is None or high <= 0:
            return None
        return RangeBox(high=high, low=low, width_ratio=(high - low) / high)

    def breakout_anchor(self, window: int, *, exclude_recent: int = 0) -> BreakoutAnchor | None:
        resistance = self.rolling_high(window, exclude_recent=exclude_recent)
        support = self.rolling_low(window, exclude_recent=exclude_recent)
        if resistance is None or support is None:
            return None
        return BreakoutAnchor(resistance=resistance, support=support)

    def any_close_below(self, level: float, *, window: int, exclude_recent: int = 0) -> bool:
        values = self._window_slice(self.closes, window, exclude_recent=exclude_recent)
        return any(value < level for value in values or ())

    def last_n_closes_above(self, level: float, *, window: int) -> bool:
        values = self._window_slice(self.closes, window, exclude_recent=0)
        if values is None:
            return False
        return all(value > level for value in values)

    def _window_slice(
        self,
        values: tuple[float, ...] | tuple[int, ...],
        window: int,
        *,
        exclude_recent: int = 0,
    ) -> tuple[float, ...] | tuple[int, ...] | None:
        if window <= 0 or exclude_recent < 0:
            return None

        end = len(values) - exclude_recent
        start = end - window
        if start < 0 or end <= 0:
            return None
        return values[start:end]
