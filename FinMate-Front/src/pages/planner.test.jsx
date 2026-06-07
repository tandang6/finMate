import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import PlannerReviewPage from "./planner";


const evaluationSnapshot = {
  strategy_id: "ma_reclaim",
  strategy_name: "MA Reclaim",
  activation_state: "live",
  symbol: {
    symbol_code: "005930",
    symbol_name: "삼성전자",
    market: "KRX",
  },
  timeframe: "1d",
  evaluated_at: "2026-04-19T00:00:00Z",
  data_status: "fresh",
  conditions: [
    {
      check_id: "reclaim",
      label: "MA reclaim",
      status: "met",
      detail: "Price reclaimed the moving average.",
      value: "20MA",
    },
  ],
  filters: [],
  guardrails: [],
  buy_zone: {
    label: "Buy zone",
    description: "Around the reclaimed average.",
    lower_price: 80000,
    upper_price: 82000,
    unit: "KRW",
  },
  stop_invalidation_rule: {
    label: "Invalidation",
    rule_text: "Exit if price loses the reclaimed average on a closing basis.",
  },
  target_review_zone: {
    label: "Target review",
    description: "Prior swing high area.",
    lower_price: 86000,
    upper_price: 88000,
    unit: "KRW",
  },
  first_position_rule: "Start with a partial position.",
  holding_profile: "Days to weeks.",
  why_this_plan: "Reclaim held and the setup is actionable.",
};

const catalogPayload = {
  version: "slice-1a",
  strategies: [
    {
      strategy_id: "ma_reclaim",
      name: "MA Reclaim",
      activation_state: "live",
      activation_reason: "Approved live strategy",
      kind: "trigger",
      supported_timeframes: ["1d"],
      summary: "Price reclaims a key moving average.",
      when_to_use: "Use after a constructive reclaim.",
      when_not_to_use: "Avoid in weak structure.",
      holding_profile: "Days to weeks.",
      required_data: ["daily_bars"],
      evaluator_id: "ma_reclaim_v1",
      tags: ["daily"],
      disclaimer: "Educational only.",
    },
  ],
};

const savedPlanPayload = {
  plan_id: "plan-1",
  symbol: "삼성전자",
  strategy_template_id: "ma_reclaim",
  strategy_snapshot: {
    strategy_id: "ma_reclaim",
    name: "MA Reclaim",
  },
  evaluation_snapshot: evaluationSnapshot,
  entry_price_override: null,
  stop_loss_price_override: null,
  target_price_override: null,
  position_size_override_pct: null,
  holding_period: "Days to weeks.",
  one_line_reason: "Reclaim setup review",
  note: "",
  status: "saved",
  created_at: "2026-04-19T00:00:00Z",
  updated_at: "2026-04-19T00:00:00Z",
};

function okJson(data) {
  return Promise.resolve({
    ok: true,
    json: async () => data,
  });
}

function renderPlanner(initialEntries) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/planner" element={<PlannerReviewPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("PlannerReviewPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    global.fetch = jest.fn((url) => {
      if (url.includes("/api/strategies/catalog")) {
        return okJson(catalogPayload);
      }
      return Promise.reject(new Error(`Unexpected url ${url}`));
    });
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  test("shows an empty state when opened without a selected evaluation snapshot", () => {
    renderPlanner(["/planner"]);

    expect(screen.getByText("검토할 전략 스냅샷이 아직 없어요")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /\/strategies로 돌아가기/i })).toBeInTheDocument();
  });

  test("saves a snapshot-first plan without sending a caller supplied symbol", async () => {
    global.fetch = jest.fn((url, options) => {
      if (url.includes("/api/strategies/catalog")) {
        return okJson(catalogPayload);
      }
      if (url.includes("/api/planner/plans")) {
        return okJson(savedPlanPayload);
      }
      return Promise.reject(new Error(`Unexpected url ${url}`));
    });

    renderPlanner([
      {
        pathname: "/planner",
        state: {
          plannerSelection: {
            evaluation_snapshot: evaluationSnapshot,
          },
        },
      },
    ]);

    expect(await screen.findByText("선택한 평가 스냅샷을 검토하고 계획으로 저장해요")).toBeInTheDocument();
    expect(await screen.findByText("MA Reclaim")).toBeInTheDocument();
    expect(await screen.findByText("저장할 계획 정리")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("예: 2주 동안 일봉 종가 기준으로 추적"), {
      target: { value: "2주 동안 종가 기준 추적" },
    });
    fireEvent.change(screen.getByPlaceholderText("예: 20일선 재돌파 뒤 50일선 위에서 지지 확인"), {
      target: { value: "Reclaim setup review" },
    });

    fireEvent.click(screen.getByRole("button", { name: "저장하기" }));

    await waitFor(() => {
      const saveCall = global.fetch.mock.calls.find(([url]) => url.includes("/api/planner/plans"));
      expect(saveCall).toBeTruthy();
      const payload = JSON.parse(saveCall[1].body);
      expect(payload.symbol).toBeUndefined();
      expect(payload.strategy_template_id).toBe("ma_reclaim");
      expect(payload.evaluation_snapshot.symbol.symbol_name).toBe("삼성전자");
      expect(payload.one_line_reason).toBe("Reclaim setup review");
    });

    expect(await screen.findByText("계획이 저장되었어요")).toBeInTheDocument();
  });
});
