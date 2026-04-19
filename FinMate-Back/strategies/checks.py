from __future__ import annotations

from market_data.types import DailyBarSeries, MarketDataStatus

from .contracts import StrategyCheck, StrategyCheckStatus
from .daily import DailySeriesView


def combine_data_status(*statuses: MarketDataStatus) -> MarketDataStatus:
    if MarketDataStatus.UNAVAILABLE in statuses:
        return MarketDataStatus.UNAVAILABLE
    if MarketDataStatus.PARTIAL in statuses:
        return MarketDataStatus.PARTIAL
    if MarketDataStatus.STALE in statuses:
        return MarketDataStatus.STALE
    return MarketDataStatus.FRESH


def data_freshness_guardrail(
    stock_series: DailyBarSeries,
    benchmark_series: DailyBarSeries,
) -> StrategyCheck:
    combined_status = combine_data_status(stock_series.data_status, benchmark_series.data_status)
    if combined_status == MarketDataStatus.FRESH:
        return StrategyCheck(
            check_id="data_freshness",
            label="Data Freshness",
            status=StrategyCheckStatus.MET,
            detail="Stock and benchmark daily bars are fresh.",
            value="fresh",
        )

    return StrategyCheck(
        check_id="data_freshness",
        label="Data Freshness",
        status=StrategyCheckStatus.BLOCKED,
        detail="Fresh daily data is required before numeric zones can be produced.",
        value=combined_status.value,
    )


def market_regime_guardrail(benchmark_view: DailySeriesView) -> StrategyCheck:
    sma50 = benchmark_view.sma(50)
    sma200 = benchmark_view.sma(200)
    if sma50 is None or sma200 is None:
        return StrategyCheck(
            check_id="market_regime",
            label="Market Regime",
            status=StrategyCheckStatus.BLOCKED,
            detail="Benchmark history is insufficient for market-regime checks.",
        )

    if benchmark_view.latest_close > sma50 and sma50 > sma200:
        return StrategyCheck(
            check_id="market_regime",
            label="Market Regime",
            status=StrategyCheckStatus.MET,
            detail="Benchmark trend remains constructive on the daily timeframe.",
            value=f"close>{sma50:.2f}>{sma200:.2f}",
        )

    return StrategyCheck(
        check_id="market_regime",
        label="Market Regime",
        status=StrategyCheckStatus.NOT_MET,
        detail="Benchmark trend is not constructive enough for the shared market-regime guardrail.",
        value=f"close={benchmark_view.latest_close:.2f}, sma50={sma50:.2f}, sma200={sma200:.2f}",
    )


def trend_regime_filter(stock_view: DailySeriesView) -> StrategyCheck:
    sma50 = stock_view.sma(50)
    sma200 = stock_view.sma(200)
    if sma50 is None or sma200 is None:
        return StrategyCheck(
            check_id="trend_regime",
            label="Trend Regime",
            status=StrategyCheckStatus.BLOCKED,
            detail="Stock history is insufficient for the shared trend-regime filter.",
        )

    if stock_view.latest_close > sma50 and sma50 > sma200:
        return StrategyCheck(
            check_id="trend_regime",
            label="Trend Regime",
            status=StrategyCheckStatus.MET,
            detail="Price remains above rising medium- and long-term daily averages.",
            value=f"close={stock_view.latest_close:.2f}, sma50={sma50:.2f}, sma200={sma200:.2f}",
        )

    return StrategyCheck(
        check_id="trend_regime",
        label="Trend Regime",
        status=StrategyCheckStatus.NOT_MET,
        detail="The shared trend-regime filter is not satisfied on the daily timeframe.",
        value=f"close={stock_view.latest_close:.2f}, sma50={sma50:.2f}, sma200={sma200:.2f}",
    )


def volume_confirmation_filter(stock_view: DailySeriesView, *, min_ratio: float = 1.2) -> StrategyCheck:
    ratio = stock_view.volume_ratio(20)
    if ratio is None:
        return StrategyCheck(
            check_id="volume_confirmation",
            label="Volume Confirmation",
            status=StrategyCheckStatus.BLOCKED,
            detail="Volume history is insufficient for the shared breakout filter.",
        )

    if ratio >= min_ratio:
        return StrategyCheck(
            check_id="volume_confirmation",
            label="Volume Confirmation",
            status=StrategyCheckStatus.MET,
            detail="Latest daily volume is stronger than the recent baseline.",
            value=f"{ratio:.2f}x",
        )

    return StrategyCheck(
        check_id="volume_confirmation",
        label="Volume Confirmation",
        status=StrategyCheckStatus.NOT_MET,
        detail="Latest daily volume is not strong enough for the shared breakout filter.",
        value=f"{ratio:.2f}x",
    )


def all_checks_met(checks: list[StrategyCheck]) -> bool:
    return all(check.status == StrategyCheckStatus.MET for check in checks)


def any_check_blocked(checks: list[StrategyCheck]) -> bool:
    return any(check.status == StrategyCheckStatus.BLOCKED for check in checks)
