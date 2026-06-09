from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from market_data.provider import MarketDataProvider
from market_data.types import MarketDataStatus

from .catalog import get_strategy_definition
from .checks import (
    all_checks_met,
    any_check_blocked,
    combine_data_status,
    data_freshness_guardrail,
    market_regime_guardrail,
    trend_regime_filter,
    volume_confirmation_filter,
)
from .contracts import (
    PriceZone,
    StrategyActivationState,
    StrategyCheck,
    StrategyCheckStatus,
    StrategyDefinition,
    StrategyEvaluation,
    StrategyRule,
    StrategySymbol,
)
from .daily import DailySeriesView


@dataclass(frozen=True)
class EvaluationContext:
    strategy: StrategyDefinition
    symbol: StrategySymbol
    stock_view: DailySeriesView
    benchmark_view: DailySeriesView
    data_status: MarketDataStatus
    evaluated_at: datetime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_evaluation_context(
    provider: MarketDataProvider,
    strategy: StrategyDefinition,
    ticker: str,
    *,
    evaluated_at: datetime | None = None,
) -> EvaluationContext:
    normalized = provider.normalize_ticker(ticker)
    if normalized is None:
        raise ValueError("Ticker is not supported by the current provider.")

    stock_series = provider.get_stock_daily_bars(normalized.symbol_code)
    benchmark_series = provider.get_benchmark_daily_bars(normalized.symbol_code)

    return EvaluationContext(
        strategy=strategy,
        symbol=StrategySymbol(
            symbol_code=normalized.symbol_code,
            symbol_name=normalized.symbol_name,
            market=normalized.market,
        ),
        stock_view=DailySeriesView.from_series(stock_series),
        benchmark_view=DailySeriesView.from_series(benchmark_series),
        data_status=combine_data_status(stock_series.data_status, benchmark_series.data_status),
        evaluated_at=evaluated_at or _utc_now(),
    )


def evaluate_ma_support_retest(context: EvaluationContext) -> StrategyEvaluation:
    conditions = _ma_support_retest_conditions(context.stock_view)
    filters = [trend_regime_filter(context.stock_view)]
    guardrails = [
        data_freshness_guardrail(context.stock_view.series, context.benchmark_view.series),
        market_regime_guardrail(context.benchmark_view),
    ]
    return _finalize_evaluation(
        context=context,
        conditions=conditions,
        filters=filters,
        guardrails=guardrails,
        applicable_bundle=_ma_support_retest_bundle(context.stock_view),
    )


def evaluate_resistance_breakout_retest(context: EvaluationContext) -> StrategyEvaluation:
    conditions = _resistance_breakout_retest_conditions(context.stock_view)
    filters = [
        trend_regime_filter(context.stock_view),
        volume_confirmation_filter(context.stock_view),
    ]
    guardrails = [
        data_freshness_guardrail(context.stock_view.series, context.benchmark_view.series),
        market_regime_guardrail(context.benchmark_view),
    ]
    return _finalize_evaluation(
        context=context,
        conditions=conditions,
        filters=filters,
        guardrails=guardrails,
        applicable_bundle=_resistance_breakout_retest_bundle(context.stock_view),
    )


def evaluate_pullback(context: EvaluationContext) -> StrategyEvaluation:
    conditions = _pullback_conditions(context.stock_view)
    filters = [trend_regime_filter(context.stock_view)]
    guardrails = [
        data_freshness_guardrail(context.stock_view.series, context.benchmark_view.series),
        market_regime_guardrail(context.benchmark_view),
    ]
    return _finalize_evaluation(
        context=context,
        conditions=conditions,
        filters=filters,
        guardrails=guardrails,
        applicable_bundle=_pullback_bundle(context.stock_view),
    )


def evaluate_darvas_range_breakout(context: EvaluationContext) -> StrategyEvaluation:
    conditions = _darvas_range_breakout_conditions(context.stock_view)
    filters = [
        trend_regime_filter(context.stock_view),
        volume_confirmation_filter(context.stock_view),
    ]
    guardrails = [
        data_freshness_guardrail(context.stock_view.series, context.benchmark_view.series),
        market_regime_guardrail(context.benchmark_view),
    ]
    return _finalize_evaluation(
        context=context,
        conditions=conditions,
        filters=filters,
        guardrails=guardrails,
        applicable_bundle=_darvas_range_breakout_bundle(context.stock_view),
    )


def evaluate_ma_reclaim(context: EvaluationContext) -> StrategyEvaluation:
    conditions = _ma_reclaim_conditions(context.stock_view)
    filters = [trend_regime_filter(context.stock_view)]
    guardrails = [
        data_freshness_guardrail(context.stock_view.series, context.benchmark_view.series),
        market_regime_guardrail(context.benchmark_view),
    ]
    return _finalize_evaluation(
        context=context,
        conditions=conditions,
        filters=filters,
        guardrails=guardrails,
        applicable_bundle=_ma_reclaim_bundle(context.stock_view),
    )


def _ma_support_retest_conditions(stock_view: DailySeriesView) -> list[StrategyCheck]:
    sma50 = stock_view.sma(50)
    recent_high = stock_view.rolling_high(20)
    near_support = False
    defended_support = False
    if sma50 is not None:
        near_support = sma50 <= stock_view.latest_close <= sma50 * 1.025
        defended_support = stock_view.latest_low <= sma50 * 1.01 and stock_view.latest_close >= sma50

    return [
        StrategyCheck(
            check_id="support_band_alignment",
            label="지지 밴드 정렬",
            status=StrategyCheckStatus.MET if near_support else StrategyCheckStatus.NOT_MET,
            detail="지지 재테스트로 인정받기 위해 최근 종가가 50일 평균선에 충분히 가깝습니다.",
            value=f"sma50={sma50:.2f}" if sma50 is not None else None,
        ),
        StrategyCheck(
            check_id="support_defense",
            label="지지선 방어",
            status=StrategyCheckStatus.MET if defended_support else StrategyCheckStatus.NOT_MET,
            detail="최근 일봉 범위가 50일 평균선을 테스트하되 그 아래에서 종가를 형성하지 않습니다.",
            value=f"low={stock_view.latest_low:.2f}, close={stock_view.latest_close:.2f}",
        ),
        StrategyCheck(
            check_id="recent_room_to_resistance",
            label="저항선까지 여유 공간",
            status=(
                StrategyCheckStatus.MET
                if recent_high is not None and recent_high >= stock_view.latest_close * 1.03
                else StrategyCheckStatus.NOT_MET
            ),
            detail="최근 일봉 고점이 현재 지지 재테스트 구역 위에 충분한 여유를 남겨줍니다.",
            value=f"high20={recent_high:.2f}" if recent_high is not None else None,
        ),
    ]


def _resistance_breakout_retest_conditions(stock_view: DailySeriesView) -> list[StrategyCheck]:
    anchor = stock_view.breakout_anchor(30, exclude_recent=6)
    breakout_peak = stock_view.rolling_high(5, exclude_recent=1)
    breakout_confirmed = (
        anchor is not None
        and breakout_peak is not None
        and breakout_peak > anchor.resistance * 1.02
    )
    retest_hold = (
        anchor is not None
        and breakout_peak is not None
        and stock_view.latest_low <= anchor.resistance * 1.01
        and stock_view.latest_close >= anchor.resistance * 0.995
        and stock_view.latest_close <= breakout_peak * 0.99
    )
    return [
        StrategyCheck(
            check_id="prior_resistance_anchor",
            label="이전 저항 앵커",
            status=StrategyCheckStatus.MET if anchor is not None else StrategyCheckStatus.BLOCKED,
            detail="최근 일봉 고점에서 이전 저항 앵커를 확인할 수 있습니다.",
            value=f"{anchor.resistance:.2f}" if anchor is not None else None,
        ),
        StrategyCheck(
            check_id="breakout_extension",
            label="돌파 확장",
            status=StrategyCheckStatus.MET if breakout_confirmed else StrategyCheckStatus.NOT_MET,
            detail="최근 일봉 고점이 이전 저항 앵커를 명확히 상회합니다.",
            value=(
                f"anchor={anchor.resistance:.2f}, peak={breakout_peak:.2f}"
                if anchor is not None and breakout_peak is not None
                else None
            ),
        ),
        StrategyCheck(
            check_id="retest_hold",
            label="재테스트 유지",
            status=StrategyCheckStatus.MET if retest_hold else StrategyCheckStatus.NOT_MET,
            detail="최근 일봉 바가 이전 저항 구역을 재방문하되 여전히 그 위에서 종가를 형성합니다.",
            value=f"low={stock_view.latest_low:.2f}, close={stock_view.latest_close:.2f}",
        ),
    ]


def _pullback_conditions(stock_view: DailySeriesView) -> list[StrategyCheck]:
    sma20 = stock_view.sma(20)
    sma50 = stock_view.sma(50)
    recent_high = stock_view.rolling_high(20)
    pullback_zone = False
    higher_low_structure = False
    if sma20 is not None and sma50 is not None:
        pullback_zone = sma20 * 0.99 <= stock_view.latest_close <= sma20 * 1.02
        higher_low_structure = stock_view.latest_close > sma50

    return [
        StrategyCheck(
            check_id="pullback_zone",
            label="눌림목 구역",
            status=StrategyCheckStatus.MET if pullback_zone else StrategyCheckStatus.NOT_MET,
            detail="최근 종가가 단기 일봉 눌림목 구역 근처에 위치합니다.",
            value=f"sma20={sma20:.2f}" if sma20 is not None else None,
        ),
        StrategyCheck(
            check_id="higher_low_structure",
            label="고점 상승 구조",
            status=StrategyCheckStatus.MET if higher_low_structure else StrategyCheckStatus.NOT_MET,
            detail="눌림목 중에도 최근 종가가 중기 지지선 위를 유지합니다.",
            value=f"sma50={sma50:.2f}" if sma50 is not None else None,
        ),
        StrategyCheck(
            check_id="recovery_room",
            label="회복 여유 공간",
            status=(
                StrategyCheckStatus.MET
                if recent_high is not None and recent_high >= stock_view.latest_close * 1.04
                else StrategyCheckStatus.NOT_MET
            ),
            detail="최근 고점이 현재 눌림목 구역 위에 여유 공간을 남겨줍니다.",
            value=f"high20={recent_high:.2f}" if recent_high is not None else None,
        ),
    ]


def _darvas_range_breakout_conditions(stock_view: DailySeriesView) -> list[StrategyCheck]:
    box = stock_view.range_box(20, exclude_recent=1)
    box_is_tight = box is not None and box.width_ratio <= 0.12
    breakout_close = box is not None and stock_view.latest_close > box.high * 1.01
    return [
        StrategyCheck(
            check_id="range_box_detected",
            label="레인지 박스 감지",
            status=StrategyCheckStatus.MET if box is not None else StrategyCheckStatus.BLOCKED,
            detail="돌파 측정을 위한 최근 일봉 레인지 박스가 확인됩니다.",
            value=(f"high={box.high:.2f}, low={box.low:.2f}" if box is not None else None),
        ),
        StrategyCheck(
            check_id="tight_box",
            label="타이트 박스",
            status=StrategyCheckStatus.MET if box_is_tight else StrategyCheckStatus.NOT_MET,
            detail="최근 일봉 레인지가 단순 박스 셋업으로 작동하기에 충분히 좁습니다.",
            value=f"{box.width_ratio:.3f}" if box is not None else None,
        ),
        StrategyCheck(
            check_id="breakout_close",
            label="돌파 종가",
            status=StrategyCheckStatus.MET if breakout_close else StrategyCheckStatus.NOT_MET,
            detail="최근 종가가 최근 일봉 박스 상단 위에 있습니다.",
            value=f"close={stock_view.latest_close:.2f}" + (f", box_high={box.high:.2f}" if box is not None else ""),
        ),
    ]


def _ma_reclaim_conditions(stock_view: DailySeriesView) -> list[StrategyCheck]:
    sma50 = stock_view.sma(50)
    reclaimed = sma50 is not None and stock_view.latest_close > sma50 * 1.005
    recent_undertrade = sma50 is not None and stock_view.any_close_below(sma50 * 0.995, window=20, exclude_recent=2)
    follow_through = sma50 is not None and stock_view.last_n_closes_above(sma50, window=2)
    return [
        StrategyCheck(
            check_id="ma_reclaimed",
            label="이동평균 탈환",
            status=StrategyCheckStatus.MET if reclaimed else StrategyCheckStatus.NOT_MET,
            detail="최근 종가가 50일 평균선 위로 의미 있게 회복됐습니다.",
            value=f"sma50={sma50:.2f}" if sma50 is not None else None,
        ),
        StrategyCheck(
            check_id="recent_undertrade",
            label="최근 이탈 경험",
            status=StrategyCheckStatus.MET if recent_undertrade else StrategyCheckStatus.NOT_MET,
            detail="탈환으로 인정받기 위해 같은 평균선 아래에서 최근에 거래된 기록이 있습니다.",
        ),
        StrategyCheck(
            check_id="reclaim_follow_through",
            label="탈환 추가 확인",
            status=StrategyCheckStatus.MET if follow_through else StrategyCheckStatus.NOT_MET,
            detail="최근 종가들이 탈환된 평균선 위에서 유지되며 즉시 다시 무너지지 않습니다.",
        ),
    ]


def _ma_support_retest_bundle(stock_view: DailySeriesView) -> tuple[PriceZone, StrategyRule, PriceZone]:
    sma50 = stock_view.sma(50) or stock_view.latest_close
    recent_high = stock_view.rolling_high(20) or stock_view.latest_high
    return (
        PriceZone(
            label="50일 지지 구역",
            description="50일 평균선 근처 일봉 지지 재테스트 구역을 계획 구역으로 사용하세요.",
            lower_price=round(sma50 * 0.99, 2),
            upper_price=round(sma50 * 1.01, 2),
        ),
        StrategyRule(
            label="50일 지지선 이탈",
            rule_text=f"50일 지지 구역인 {sma50 * 0.99:.2f} 근처에서 일봉이 마감되면 셋업을 무효화합니다.",
        ),
        PriceZone(
            label="최근 고점 재검토 구역",
            description="가격이 최근 일봉 저항 구역에 접근할 때 계획을 재검토하세요.",
            lower_price=round(recent_high * 0.98, 2),
            upper_price=round(recent_high * 1.01, 2),
        ),
    )


def _resistance_breakout_retest_bundle(stock_view: DailySeriesView) -> tuple[PriceZone, StrategyRule, PriceZone]:
    anchor = stock_view.breakout_anchor(30, exclude_recent=6)
    breakout_peak = stock_view.rolling_high(5, exclude_recent=1) or stock_view.latest_high
    resistance = anchor.resistance if anchor is not None else stock_view.latest_close
    support = anchor.support if anchor is not None else stock_view.latest_low
    return (
        PriceZone(
            label="재테스트 구역",
            description="이전 돌파 앵커가 지지선 역할을 하는 동안 계획 구역으로 사용하세요.",
            lower_price=round(resistance * 0.995, 2),
            upper_price=round(resistance * 1.01, 2),
        ),
        StrategyRule(
            label="돌파 실패",
            rule_text=f"일봉 종가가 이전 돌파 구역인 {resistance * 0.995:.2f} 근처 아래로 내려오면 셋업을 무효화합니다.",
        ),
        PriceZone(
            label="돌파 후속 상승 재검토 구역",
            description="최근 돌파 확장 구역 방향으로 계획을 재검토하세요.",
            lower_price=round(breakout_peak * 0.99, 2),
            upper_price=round((breakout_peak + (resistance - support)) * 1.01, 2),
        ),
    )


def _pullback_bundle(stock_view: DailySeriesView) -> tuple[PriceZone, StrategyRule, PriceZone]:
    sma20 = stock_view.sma(20) or stock_view.latest_close
    recent_low = stock_view.rolling_low(10) or stock_view.latest_low
    recent_high = stock_view.rolling_high(20) or stock_view.latest_high
    return (
        PriceZone(
            label="눌림목 수요 구역",
            description="20일 평균선 근처 단기 일봉 눌림목 구역을 계획 구역으로 사용하세요.",
            lower_price=round(sma20 * 0.99, 2),
            upper_price=round(sma20 * 1.01, 2),
        ),
        StrategyRule(
            label="눌림목 실패",
            rule_text=f"가격이 최근 눌림목 지지 구역인 {recent_low * 0.99:.2f} 근처 아래에서 종가를 형성하면 셋업을 무효화합니다.",
        ),
        PriceZone(
            label="이전 스윙 고점 재검토 구역",
            description="가격이 최근 스윙 고점 구역에 접근할 때 계획을 재검토하세요.",
            lower_price=round(recent_high * 0.98, 2),
            upper_price=round(recent_high * 1.01, 2),
        ),
    )


def _darvas_range_breakout_bundle(stock_view: DailySeriesView) -> tuple[PriceZone, StrategyRule, PriceZone]:
    box = stock_view.range_box(20, exclude_recent=1)
    if box is None:
        box_high = stock_view.latest_close
        box_low = stock_view.latest_low
    else:
        box_high = box.high
        box_low = box.low
    box_height = max(box_high - box_low, 0.01)
    return (
        PriceZone(
            label="레인지 돌파 구역",
            description="최근 일봉 박스 상단을 돌파 계획 구역으로 사용하세요.",
            lower_price=round(box_high, 2),
            upper_price=round(box_high * 1.02, 2),
        ),
        StrategyRule(
            label="박스 이탈",
            rule_text=f"가격이 레인지 상단인 {box_high * 0.995:.2f} 근처 아래로 되돌아와 마감되면 셋업을 무효화합니다.",
        ),
        PriceZone(
            label="측정 이동 재검토 구역",
            description="박스 위의 단순 레인지 높이 연장 근처에서 계획을 재검토하세요.",
            lower_price=round(box_high + box_height * 0.8, 2),
            upper_price=round(box_high + box_height * 1.2, 2),
        ),
    )


def _ma_reclaim_bundle(stock_view: DailySeriesView) -> tuple[PriceZone, StrategyRule, PriceZone]:
    sma50 = stock_view.sma(50) or stock_view.latest_close
    recent_high = stock_view.rolling_high(30) or stock_view.latest_high
    return (
        PriceZone(
            label="이동평균 탈환 구역",
            description="가격이 그 위에서 유지되는 동안 탈환된 50일 평균선을 계획 구역으로 사용하세요.",
            lower_price=round(sma50, 2),
            upper_price=round(sma50 * 1.02, 2),
        ),
        StrategyRule(
            label="탈환 실패",
            rule_text=f"가격이 탈환된 평균선인 {sma50 * 0.995:.2f} 근처 아래로 되돌아와 마감되면 셋업을 무효화합니다.",
        ),
        PriceZone(
            label="탈환 후속 상승 재검토 구역",
            description="탈환 후 가격이 최근 일봉 저항 구역에 접근할 때 계획을 재검토하세요.",
            lower_price=round(recent_high * 0.98, 2),
            upper_price=round(recent_high * 1.01, 2),
        ),
    )


def _finalize_evaluation(
    *,
    context: EvaluationContext,
    conditions: list[StrategyCheck],
    filters: list[StrategyCheck],
    guardrails: list[StrategyCheck],
    applicable_bundle: tuple[PriceZone, StrategyRule, PriceZone],
) -> StrategyEvaluation:
    if any_check_blocked(guardrails):
        return _blocked_evaluation(context, conditions, filters, guardrails)

    if all_checks_met(conditions + filters + guardrails):
        buy_zone, stop_rule, target_zone = applicable_bundle
        return StrategyEvaluation(
            strategy_id=context.strategy.strategy_id,
            strategy_name=context.strategy.name,
            activation_state=StrategyActivationState.LIVE,
            symbol=context.symbol,
            evaluated_at=context.evaluated_at,
            data_status=context.data_status,
            conditions=conditions,
            filters=filters,
            guardrails=guardrails,
            buy_zone=buy_zone,
            stop_invalidation_rule=stop_rule,
            target_review_zone=target_zone,
            first_position_rule="첫 비중은 작게 유지하고, 추가 비중을 늘리기 전에 일봉 셋업이 계속 확인되길 기다리세요.",
            holding_profile=context.strategy.holding_profile,
            why_this_plan=f"{context.strategy.name} 일봉 조건이 충족되어 현재 구조에서 파생된 구역 기반 레벨을 계획에 포함합니다.",
        )

    return _conditions_insufficient_evaluation(context, conditions, filters, guardrails)


def _blocked_evaluation(
    context: EvaluationContext,
    conditions: list[StrategyCheck],
    filters: list[StrategyCheck],
    guardrails: list[StrategyCheck],
) -> StrategyEvaluation:
    return StrategyEvaluation(
        strategy_id=context.strategy.strategy_id,
        strategy_name=context.strategy.name,
        activation_state=StrategyActivationState.LIVE,
        symbol=context.symbol,
        evaluated_at=context.evaluated_at,
        data_status=context.data_status,
        conditions=conditions,
        filters=filters,
        guardrails=guardrails,
        buy_zone=PriceZone(
            label="데이터 차단 매수 구역",
            description="수치 매수 구역을 생성하기 전 최신 일봉 데이터가 필요합니다.",
        ),
        stop_invalidation_rule=StrategyRule(
            label="데이터 차단 무효화 규칙",
            rule_text="수치 무효화 규칙을 생성하기 전 최신 일봉 데이터가 필요합니다.",
        ),
        target_review_zone=PriceZone(
            label="데이터 차단 목표 재검토 구역",
            description="수치 목표 재검토 구역을 생성하기 전 최신 일봉 데이터가 필요합니다.",
        ),
        first_position_rule="데이터 신선도로 인해 일봉 평가가 차단된 상태에서는 수치 첫 비중 계획을 세우지 마세요.",
        holding_profile=context.strategy.holding_profile,
        why_this_plan=f"blocked: {context.strategy.name} 일봉 평가가 데이터 신선도 문제로 차단되어 수치 구역을 제공하지 않습니다.",
    )


def _data_unavailable_evaluation(context: EvaluationContext) -> StrategyEvaluation:
    filters = [trend_regime_filter(context.stock_view)]
    if context.strategy.strategy_id in {"resistance_breakout_retest", "darvas_range_breakout"}:
        filters.append(volume_confirmation_filter(context.stock_view))

    guardrails = [
        data_freshness_guardrail(context.stock_view.series, context.benchmark_view.series),
        market_regime_guardrail(context.benchmark_view),
    ]
    conditions = [
        StrategyCheck(
            check_id="setup_data_availability",
            label="셋업 데이터 가용성",
            status=StrategyCheckStatus.BLOCKED,
            detail="필요한 일봉 데이터를 사용할 수 없어 셋업별 확인을 평가하지 않습니다.",
            value=context.data_status.value,
        )
    ]

    return StrategyEvaluation(
        strategy_id=context.strategy.strategy_id,
        strategy_name=context.strategy.name,
        activation_state=StrategyActivationState.LIVE,
        symbol=context.symbol,
        evaluated_at=context.evaluated_at,
        data_status=context.data_status,
        conditions=conditions,
        filters=filters,
        guardrails=guardrails,
        buy_zone=PriceZone(
            label="데이터 없음 매수 구역",
            description="필요한 일봉 데이터를 사용할 수 없어 수치 매수 구역을 생성할 수 없습니다.",
        ),
        stop_invalidation_rule=StrategyRule(
            label="데이터 없음 무효화 규칙",
            rule_text="필요한 일봉 데이터를 사용할 수 없어 수치 무효화 규칙을 생성할 수 없습니다.",
        ),
        target_review_zone=PriceZone(
            label="데이터 없음 목표 재검토 구역",
            description="필요한 일봉 데이터를 사용할 수 없어 수치 목표 재검토 구역을 생성할 수 없습니다.",
        ),
        first_position_rule="필요한 일봉 데이터를 사용할 수 없는 상태에서는 수치 첫 비중 계획을 세우지 마세요.",
        holding_profile=context.strategy.holding_profile,
        why_this_plan=f"unavailable: {context.strategy.name} 필요한 일봉 데이터를 사용할 수 없어 일봉 평가가 차단됩니다.",
    )


def _conditions_insufficient_evaluation(
    context: EvaluationContext,
    conditions: list[StrategyCheck],
    filters: list[StrategyCheck],
    guardrails: list[StrategyCheck],
) -> StrategyEvaluation:
    return StrategyEvaluation(
        strategy_id=context.strategy.strategy_id,
        strategy_name=context.strategy.name,
        activation_state=StrategyActivationState.LIVE,
        symbol=context.symbol,
        evaluated_at=context.evaluated_at,
        data_status=context.data_status,
        conditions=conditions,
        filters=filters,
        guardrails=guardrails,
        buy_zone=PriceZone(
            label="조건 부족 매수 구역",
            description="현재 일봉 조건이 불완전하여 매수 구역은 설명적 표현에 그칩니다.",
        ),
        stop_invalidation_rule=StrategyRule(
            label="조건 부족 무효화 규칙",
            rule_text="현재 일봉 조건이 불완전하여 무효화 규칙은 설명적 표현에 그칩니다.",
        ),
        target_review_zone=PriceZone(
            label="조건 부족 목표 재검토 구역",
            description="현재 일봉 조건이 불완전하여 목표 재검토 구역은 설명적 표현에 그칩니다.",
        ),
        first_position_rule="일봉 셋업과 공유 확인이 모두 정렬될 때까지 첫 비중 계획은 설명적 표현에 그칩니다.",
        holding_profile=context.strategy.holding_profile,
        why_this_plan=f"incomplete: {context.strategy.name} 일봉 조건이 불완전하여 아직 수치 구역을 생성하지 않습니다.",
    )


LiveEvaluator = callable


LIVE_STRATEGY_EVALUATORS = {
    "ma_support_retest": evaluate_ma_support_retest,
    "resistance_breakout_retest": evaluate_resistance_breakout_retest,
    "pullback": evaluate_pullback,
    "darvas_range_breakout": evaluate_darvas_range_breakout,
    "ma_reclaim": evaluate_ma_reclaim,
}


def get_live_strategy_evaluator(strategy_id: str):
    return LIVE_STRATEGY_EVALUATORS.get(strategy_id)


def list_live_strategy_ids() -> list[str]:
    return sorted(LIVE_STRATEGY_EVALUATORS.keys())


def evaluate_live_strategy(
    provider: MarketDataProvider,
    *,
    strategy_id: str,
    ticker: str,
    evaluated_at: datetime | None = None,
) -> StrategyEvaluation:
    strategy = get_strategy_definition(strategy_id)
    if strategy is None:
        raise ValueError(f"Unknown strategy_id: {strategy_id}")
    if strategy.activation_state != StrategyActivationState.LIVE:
        raise ValueError(f"Strategy '{strategy_id}' is not live and cannot be evaluated.")

    evaluator = get_live_strategy_evaluator(strategy_id)
    if evaluator is None:
        raise ValueError(f"No live evaluator is bound for strategy '{strategy_id}'.")

    context = build_evaluation_context(
        provider,
        strategy,
        ticker,
        evaluated_at=evaluated_at,
    )
    if (
        context.data_status == MarketDataStatus.UNAVAILABLE
        or not context.stock_view.closes
        or not context.stock_view.highs
        or not context.stock_view.lows
        or not context.stock_view.volumes
        or not context.benchmark_view.closes
        or not context.benchmark_view.highs
        or not context.benchmark_view.lows
        or not context.benchmark_view.volumes
    ):
        return _data_unavailable_evaluation(context)
    return evaluator(context)
