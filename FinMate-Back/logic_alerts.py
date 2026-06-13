from __future__ import annotations

from typing import Any

from config import settings
from ecos import get_last_one
from market_data.public_data_provider import get_public_data_market_data_provider
from market_data.types import MarketDataStatus


SAMSUNG_RULE_PRICE = 70_000.0
USDKRW_RULE_PRICE = 1_350.0


def get_logic_alerts() -> list[dict[str, Any]]:
    return [_build_samsung_price_alert(), _build_usdkrw_alert()]


def _build_samsung_price_alert() -> dict[str, Any]:
    base_alert = {
        "id": "samsung-under-70000",
        "kind": "stock_price",
        "title": "삼성전자",
        "condition_label": "삼성전자 < 70,000원",
        "threshold": SAMSUNG_RULE_PRICE,
        "unit": "KRW",
        "source": "공공데이터포털 금융위원회_주식시세정보",
    }
    if not settings.DATA_GO_KR_SERVICE_KEY:
        return {
            **base_alert,
            "status": "unavailable",
            "triggered": False,
            "current_value": None,
            "current_value_label": "-",
            "message": "DATA_GO_KR_SERVICE_KEY가 필요합니다.",
        }

    provider = get_public_data_market_data_provider()
    series = provider.get_stock_daily_bars("005930", lookback=2)
    if series.data_status == MarketDataStatus.UNAVAILABLE or not series.bars:
        return {
            **base_alert,
            "status": "unavailable",
            "triggered": False,
            "current_value": None,
            "current_value_label": "-",
            "message": series.status_reason or "현재가를 불러오지 못했습니다.",
        }

    latest = series.bars[-1]
    current_value = latest.close
    triggered = current_value < SAMSUNG_RULE_PRICE
    return {
        **base_alert,
        "status": series.data_status.value,
        "triggered": triggered,
        "current_value": current_value,
        "current_value_label": f"{current_value:,.0f}원",
        "as_of_date": latest.date.isoformat(),
        "message": (
            f"현재가 {current_value:,.0f}원, 매수 구간에 도달했습니다."
            if triggered
            else f"현재가 {current_value:,.0f}원으로 조건 미충족"
        ),
    }


def _build_usdkrw_alert() -> dict[str, Any]:
    base_alert = {
        "id": "usdkrw-over-1350",
        "kind": "fx",
        "title": "원/달러 환율",
        "condition_label": "환율 > 1,350원",
        "threshold": USDKRW_RULE_PRICE,
        "unit": "KRW",
        "source": "한국은행 ECOS",
    }
    try:
        market_weather = get_last_one()
        if isinstance(market_weather, dict) and "error" in market_weather:
            raise ValueError(market_weather["error"])
        fx_item = next(
            item for item in market_weather.get("indices", [])
            if item.get("name") == "USD/KRW"
        )
        current_value = float(str(fx_item.get("value", "")).replace(",", ""))
    except Exception as exc:
        return {
            **base_alert,
            "status": "unavailable",
            "triggered": False,
            "current_value": None,
            "current_value_label": "-",
            "message": f"환율 데이터를 불러오지 못했습니다: {exc}",
        }

    triggered = current_value > USDKRW_RULE_PRICE
    return {
        **base_alert,
        "status": "fresh",
        "triggered": triggered,
        "current_value": current_value,
        "current_value_label": f"{current_value:,.2f}원",
        "message": (
            f"현재 {current_value:,.2f}원, 환율 조건에 도달했습니다."
            if triggered
            else f"현재 {current_value:,.2f}원으로 조건 미충족"
        ),
    }
