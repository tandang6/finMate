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
            label="데이터 신선도",
            status=StrategyCheckStatus.MET,
            detail="종목 및 벤치마크 일봉 데이터가 최신 상태입니다.",
            value="fresh",
        )

    return StrategyCheck(
        check_id="data_freshness",
        label="데이터 신선도",
        status=StrategyCheckStatus.BLOCKED,
        detail="수치 구역을 생성하기 전 최신 일봉 데이터가 필요합니다.",
        value=combined_status.value,
    )


def market_regime_guardrail(benchmark_view: DailySeriesView) -> StrategyCheck:
    sma50 = benchmark_view.sma(50)
    sma200 = benchmark_view.sma(200)
    if sma50 is None or sma200 is None:
        return StrategyCheck(
            check_id="market_regime",
            label="시장 환경",
            status=StrategyCheckStatus.BLOCKED,
            detail="시장 환경 확인을 위한 벤치마크 히스토리가 부족합니다.",
        )

    if benchmark_view.latest_close > sma50 and sma50 > sma200:
        return StrategyCheck(
            check_id="market_regime",
            label="시장 환경",
            status=StrategyCheckStatus.MET,
            detail="벤치마크 추세가 일봉 기준 건설적으로 유지됩니다.",
            value=f"close>{sma50:.2f}>{sma200:.2f}",
        )

    return StrategyCheck(
        check_id="market_regime",
        label="시장 환경",
        status=StrategyCheckStatus.NOT_MET,
        detail="공유 시장 환경 가드레일에 맞는 충분한 벤치마크 추세가 아닙니다.",
        value=f"close={benchmark_view.latest_close:.2f}, sma50={sma50:.2f}, sma200={sma200:.2f}",
    )


def trend_regime_filter(stock_view: DailySeriesView) -> StrategyCheck:
    sma50 = stock_view.sma(50)
    sma200 = stock_view.sma(200)
    if sma50 is None or sma200 is None:
        return StrategyCheck(
            check_id="trend_regime",
            label="추세 환경",
            status=StrategyCheckStatus.BLOCKED,
            detail="공유 추세 환경 필터에 대한 종목 히스토리가 부족합니다.",
        )

    if stock_view.latest_close > sma50 and sma50 > sma200:
        return StrategyCheck(
            check_id="trend_regime",
            label="추세 환경",
            status=StrategyCheckStatus.MET,
            detail="가격이 상승하는 중·장기 일봉 평균선 위를 유지합니다.",
            value=f"close={stock_view.latest_close:.2f}, sma50={sma50:.2f}, sma200={sma200:.2f}",
        )

    return StrategyCheck(
        check_id="trend_regime",
        label="추세 환경",
        status=StrategyCheckStatus.NOT_MET,
        detail="공유 추세 환경 필터가 일봉 기준 충족되지 않습니다.",
        value=f"close={stock_view.latest_close:.2f}, sma50={sma50:.2f}, sma200={sma200:.2f}",
    )


def volume_confirmation_filter(stock_view: DailySeriesView, *, min_ratio: float = 1.2) -> StrategyCheck:
    ratio = stock_view.volume_ratio(20)
    if ratio is None:
        return StrategyCheck(
            check_id="volume_confirmation",
            label="거래량 확인",
            status=StrategyCheckStatus.BLOCKED,
            detail="공유 돌파 필터에 대한 거래량 히스토리가 부족합니다.",
        )

    if ratio >= min_ratio:
        return StrategyCheck(
            check_id="volume_confirmation",
            label="거래량 확인",
            status=StrategyCheckStatus.MET,
            detail="최근 일봉 거래량이 최근 기준선보다 강합니다.",
            value=f"{ratio:.2f}x",
        )

    return StrategyCheck(
        check_id="volume_confirmation",
        label="거래량 확인",
        status=StrategyCheckStatus.NOT_MET,
        detail="최근 일봉 거래량이 공유 돌파 필터 기준에 충분하지 않습니다.",
        value=f"{ratio:.2f}x",
    )


def all_checks_met(checks: list[StrategyCheck]) -> bool:
    return all(check.status == StrategyCheckStatus.MET for check in checks)


def any_check_blocked(checks: list[StrategyCheck]) -> bool:
    return any(check.status == StrategyCheckStatus.BLOCKED for check in checks)
