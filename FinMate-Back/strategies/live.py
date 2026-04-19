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
            label="Support Band Alignment",
            status=StrategyCheckStatus.MET if near_support else StrategyCheckStatus.NOT_MET,
            detail="Latest close remains close enough to the 50-day average to count as a support retest.",
            value=f"sma50={sma50:.2f}" if sma50 is not None else None,
        ),
        StrategyCheck(
            check_id="support_defense",
            label="Support Defense",
            status=StrategyCheckStatus.MET if defended_support else StrategyCheckStatus.NOT_MET,
            detail="Latest daily range tests the 50-day average without closing below it.",
            value=f"low={stock_view.latest_low:.2f}, close={stock_view.latest_close:.2f}",
        ),
        StrategyCheck(
            check_id="recent_room_to_resistance",
            label="Room To Resistance",
            status=(
                StrategyCheckStatus.MET
                if recent_high is not None and recent_high >= stock_view.latest_close * 1.03
                else StrategyCheckStatus.NOT_MET
            ),
            detail="Recent daily highs leave enough room above the current support retest area.",
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
            label="Prior Resistance Anchor",
            status=StrategyCheckStatus.MET if anchor is not None else StrategyCheckStatus.BLOCKED,
            detail="A prior resistance anchor is available from recent daily highs.",
            value=f"{anchor.resistance:.2f}" if anchor is not None else None,
        ),
        StrategyCheck(
            check_id="breakout_extension",
            label="Breakout Extension",
            status=StrategyCheckStatus.MET if breakout_confirmed else StrategyCheckStatus.NOT_MET,
            detail="Recent daily highs extend clearly above the prior resistance anchor.",
            value=(
                f"anchor={anchor.resistance:.2f}, peak={breakout_peak:.2f}"
                if anchor is not None and breakout_peak is not None
                else None
            ),
        ),
        StrategyCheck(
            check_id="retest_hold",
            label="Retest Hold",
            status=StrategyCheckStatus.MET if retest_hold else StrategyCheckStatus.NOT_MET,
            detail="Latest daily bar revisits the prior resistance area and still closes above it.",
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
            label="Pullback Zone",
            status=StrategyCheckStatus.MET if pullback_zone else StrategyCheckStatus.NOT_MET,
            detail="Latest close sits near the short-term daily pullback area.",
            value=f"sma20={sma20:.2f}" if sma20 is not None else None,
        ),
        StrategyCheck(
            check_id="higher_low_structure",
            label="Higher-Low Structure",
            status=StrategyCheckStatus.MET if higher_low_structure else StrategyCheckStatus.NOT_MET,
            detail="The latest close remains above medium-term support during the pullback.",
            value=f"sma50={sma50:.2f}" if sma50 is not None else None,
        ),
        StrategyCheck(
            check_id="recovery_room",
            label="Recovery Room",
            status=(
                StrategyCheckStatus.MET
                if recent_high is not None and recent_high >= stock_view.latest_close * 1.04
                else StrategyCheckStatus.NOT_MET
            ),
            detail="Recent highs still leave room above the current pullback area.",
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
            label="Range Box Detected",
            status=StrategyCheckStatus.MET if box is not None else StrategyCheckStatus.BLOCKED,
            detail="A recent daily range box is available for breakout measurement.",
            value=(f"high={box.high:.2f}, low={box.low:.2f}" if box is not None else None),
        ),
        StrategyCheck(
            check_id="tight_box",
            label="Tight Box",
            status=StrategyCheckStatus.MET if box_is_tight else StrategyCheckStatus.NOT_MET,
            detail="The recent daily range is narrow enough to behave like a simple box setup.",
            value=f"{box.width_ratio:.3f}" if box is not None else None,
        ),
        StrategyCheck(
            check_id="breakout_close",
            label="Breakout Close",
            status=StrategyCheckStatus.MET if breakout_close else StrategyCheckStatus.NOT_MET,
            detail="Latest close is above the top of the recent daily box.",
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
            label="MA Reclaimed",
            status=StrategyCheckStatus.MET if reclaimed else StrategyCheckStatus.NOT_MET,
            detail="Latest close is back above the 50-day average by a meaningful margin.",
            value=f"sma50={sma50:.2f}" if sma50 is not None else None,
        ),
        StrategyCheck(
            check_id="recent_undertrade",
            label="Recent Undertrade",
            status=StrategyCheckStatus.MET if recent_undertrade else StrategyCheckStatus.NOT_MET,
            detail="Price traded below the same average recently enough for the move to count as a reclaim.",
        ),
        StrategyCheck(
            check_id="reclaim_follow_through",
            label="Reclaim Follow-Through",
            status=StrategyCheckStatus.MET if follow_through else StrategyCheckStatus.NOT_MET,
            detail="Recent closes stay above the reclaimed average instead of immediately failing back below it.",
        ),
    ]


def _ma_support_retest_bundle(stock_view: DailySeriesView) -> tuple[PriceZone, StrategyRule, PriceZone]:
    sma50 = stock_view.sma(50) or stock_view.latest_close
    recent_high = stock_view.rolling_high(20) or stock_view.latest_high
    return (
        PriceZone(
            label="50-Day Support Zone",
            description="Use the daily support retest area around the 50-day average as the planning zone.",
            lower_price=round(sma50 * 0.99, 2),
            upper_price=round(sma50 * 1.01, 2),
        ),
        StrategyRule(
            label="50-Day Support Failure",
            rule_text=f"Invalidate the setup if a daily close loses the 50-day support area near {sma50 * 0.99:.2f}.",
        ),
        PriceZone(
            label="Recent High Review Zone",
            description="Review the plan as price approaches the recent daily resistance area.",
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
            label="Retest Zone",
            description="Use the prior breakout anchor as the planning zone while it still acts like support.",
            lower_price=round(resistance * 0.995, 2),
            upper_price=round(resistance * 1.01, 2),
        ),
        StrategyRule(
            label="Breakout Failure",
            rule_text=f"Invalidate the setup if a daily close falls back below the prior breakout area near {resistance * 0.995:.2f}.",
        ),
        PriceZone(
            label="Breakout Follow-Through Review Zone",
            description="Review the plan toward the recent breakout extension area.",
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
            label="Pullback Demand Zone",
            description="Use the short-term daily pullback area around the 20-day average as the planning zone.",
            lower_price=round(sma20 * 0.99, 2),
            upper_price=round(sma20 * 1.01, 2),
        ),
        StrategyRule(
            label="Pullback Failure",
            rule_text=f"Invalidate the setup if price closes below the recent pullback support area near {recent_low * 0.99:.2f}.",
        ),
        PriceZone(
            label="Prior Swing High Review Zone",
            description="Review the plan as price approaches the recent swing-high area.",
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
            label="Range Breakout Zone",
            description="Use the top of the recent daily box as the breakout planning zone.",
            lower_price=round(box_high, 2),
            upper_price=round(box_high * 1.02, 2),
        ),
        StrategyRule(
            label="Box Failure",
            rule_text=f"Invalidate the setup if price closes back below the range top near {box_high * 0.995:.2f}.",
        ),
        PriceZone(
            label="Measured-Move Review Zone",
            description="Review the plan near a simple range-height extension above the box.",
            lower_price=round(box_high + box_height * 0.8, 2),
            upper_price=round(box_high + box_height * 1.2, 2),
        ),
    )


def _ma_reclaim_bundle(stock_view: DailySeriesView) -> tuple[PriceZone, StrategyRule, PriceZone]:
    sma50 = stock_view.sma(50) or stock_view.latest_close
    recent_high = stock_view.rolling_high(30) or stock_view.latest_high
    return (
        PriceZone(
            label="MA Reclaim Zone",
            description="Use the reclaimed 50-day average as the planning zone while price holds above it.",
            lower_price=round(sma50, 2),
            upper_price=round(sma50 * 1.02, 2),
        ),
        StrategyRule(
            label="Reclaim Failure",
            rule_text=f"Invalidate the setup if price closes back below the reclaimed average near {sma50 * 0.995:.2f}.",
        ),
        PriceZone(
            label="Reclaim Follow-Through Review Zone",
            description="Review the plan as price approaches the recent daily resistance area after the reclaim.",
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
            first_position_rule="Use a smaller first position and wait for the daily setup to continue confirming before expanding exposure.",
            holding_profile=context.strategy.holding_profile,
            why_this_plan=f"{context.strategy.name} daily conditions are met, so the plan includes zone-based levels derived from the current structure.",
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
            label="Data-Blocked Buy Zone",
            description="Fresh daily data is required before a numeric buy zone can be produced.",
        ),
        stop_invalidation_rule=StrategyRule(
            label="Data-Blocked Invalidation Rule",
            rule_text="Fresh daily data is required before a numeric invalidation rule can be produced.",
        ),
        target_review_zone=PriceZone(
            label="Data-Blocked Target Review Zone",
            description="Fresh daily data is required before a numeric target review zone can be produced.",
        ),
        first_position_rule="Do not form a numeric first-position plan while daily evaluation is blocked by data freshness.",
        holding_profile=context.strategy.holding_profile,
        why_this_plan=f"{context.strategy.name} daily evaluation is blocked by data freshness, so numeric zones are withheld.",
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
            label="Setup Data Availability",
            status=StrategyCheckStatus.BLOCKED,
            detail="Required daily bars are unavailable, so setup-specific checks are not evaluated.",
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
            label="Data-Unavailable Buy Zone",
            description="Required daily data is unavailable, so a numeric buy zone cannot be produced.",
        ),
        stop_invalidation_rule=StrategyRule(
            label="Data-Unavailable Invalidation Rule",
            rule_text="Required daily data is unavailable, so a numeric invalidation rule cannot be produced.",
        ),
        target_review_zone=PriceZone(
            label="Data-Unavailable Target Review Zone",
            description="Required daily data is unavailable, so a numeric target review zone cannot be produced.",
        ),
        first_position_rule="Do not form a numeric first-position plan while required daily data is unavailable.",
        holding_profile=context.strategy.holding_profile,
        why_this_plan=f"{context.strategy.name} daily evaluation is blocked because required daily data is unavailable.",
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
            label="Conditions-Insufficient Buy Zone",
            description="Current daily conditions are incomplete, so the buy zone remains descriptive only.",
        ),
        stop_invalidation_rule=StrategyRule(
            label="Conditions-Insufficient Invalidation Rule",
            rule_text="Current daily conditions are incomplete, so the invalidation rule remains descriptive only.",
        ),
        target_review_zone=PriceZone(
            label="Conditions-Insufficient Target Review Zone",
            description="Current daily conditions are incomplete, so the target review zone remains descriptive only.",
        ),
        first_position_rule="Keep the first-position plan descriptive only until the daily setup and shared checks align.",
        holding_profile=context.strategy.holding_profile,
        why_this_plan=f"{context.strategy.name} daily conditions are incomplete, so numeric zones are not produced yet.",
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
