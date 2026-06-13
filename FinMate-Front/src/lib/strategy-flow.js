const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000";

export const STRATEGY_API_BASE = `${API_BASE_URL}/api/strategies`;
export const PLANNER_API_BASE = `${API_BASE_URL}/api/planner`;
export const USER_ID_KEY = "finmate-user-id";
export const PLANNER_SELECTION_KEY = "finmate-selected-strategy-plan";

export const SUPPORTED_SYMBOLS = [
  { symbol_code: "005930", symbol_name: "삼성전자", sector: "반도체" },
  { symbol_code: "000660", symbol_name: "SK하이닉스", sector: "반도체" },
  { symbol_code: "035420", symbol_name: "NAVER", sector: "플랫폼" },
  { symbol_code: "035720", symbol_name: "카카오", sector: "플랫폼" },
  { symbol_code: "005380", symbol_name: "현대차", sector: "자동차" },
  { symbol_code: "373220", symbol_name: "LG에너지솔루션", sector: "배터리" },
];

export const ACTIVATION_STATE_LABELS = {
  live: "평가 가능",
  education_only: "교육용",
  blocked_by_data: "데이터 대기",
  deferred: "보류",
};

export const DATA_STATUS_LABELS = {
  fresh: "정상 데이터",
  stale: "지연 데이터",
  partial: "부분 데이터",
  unavailable: "데이터 없음",
};

export const CHECK_STATUS_LABELS = {
  met: "충족",
  not_met: "미충족",
  blocked: "보류",
  not_evaluated: "미평가",
};

export const STRATEGY_DISPLAY_NAMES = {
  ma_support_retest: "이동평균 지지 재테스트",
  resistance_breakout_retest: "저항선 돌파 후 재테스트",
  pullback: "눌림목",
  darvas_range_breakout: "다르바스/레인지 돌파",
  ma_reclaim: "이동평균 탈환",
  value_quality: "가치/퀄리티",
  pead: "PEAD (실적 발표 후 드리프트)",
  sector_rotation: "섹터 로테이션",
  vcp: "VCP (변동성 수축 패턴)",
  gap_and_go: "갭 앤 고",
  rsi_oversold_rebound: "RSI 과매도 반등",
  bb_squeeze: "볼린저 스퀴즈",
  relative_strength_leader: "상대 강도 리더",
};

export function getStrategyDisplayName(strategy) {
  return STRATEGY_DISPLAY_NAMES[strategy?.strategy_id] ?? strategy?.name ?? "";
}

export function getPlannerUserId() {
  const existing = window.localStorage.getItem(USER_ID_KEY);
  if (existing) {
    return existing;
  }

  const generated =
    window.crypto?.randomUUID?.() ??
    `finmate-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  window.localStorage.setItem(USER_ID_KEY, generated);
  return generated;
}

export function getPlannerHeaders() {
  return {
    "Content-Type": "application/json",
    "X-User-Id": getPlannerUserId(),
  };
}

export async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = "요청을 처리하지 못했어요.";
    try {
      const data = await response.json();
      if (typeof data.detail === "string") {
        message = data.detail;
      }
    } catch (error) {
      message = "요청을 처리하지 못했어요.";
    }
    throw new Error(message);
  }
  return response.json();
}

export function savePlannerSelection(selection) {
  window.sessionStorage.setItem(PLANNER_SELECTION_KEY, JSON.stringify(selection));
}

export function loadPlannerSelection() {
  const raw = window.sessionStorage.getItem(PLANNER_SELECTION_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    window.sessionStorage.removeItem(PLANNER_SELECTION_KEY);
    return null;
  }
}

export function clearPlannerSelection() {
  window.sessionStorage.removeItem(PLANNER_SELECTION_KEY);
}

export function formatPrice(value) {
  if (!Number.isFinite(value)) {
    return "가격 구역 없음";
  }
  return `${new Intl.NumberFormat("ko-KR").format(Math.round(value))}원`;
}

export function formatPriceZone(zone) {
  if (!zone) {
    return "평가 정보가 없어요.";
  }
  if (Number.isFinite(zone.lower_price) && Number.isFinite(zone.upper_price)) {
    if (zone.lower_price === zone.upper_price) {
      return formatPrice(zone.lower_price);
    }
    return `${formatPrice(zone.lower_price)} ~ ${formatPrice(zone.upper_price)}`;
  }
  return zone.description;
}

export function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function parseOptionalNumber(value) {
  if (value == null || `${value}`.trim() === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}
