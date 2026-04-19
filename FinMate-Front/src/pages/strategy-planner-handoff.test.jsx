import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import PlannerReviewPage from "./planner";
import StrategiesPage from "./strategies";


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

const evaluationPayload = {
  catalog_version: "slice-1a",
  symbol: {
    symbol_code: "005930",
    symbol_name: "삼성전자",
    market: "KRX",
  },
  timeframe: "1d",
  evaluated_at: "2026-04-19T00:00:00Z",
  data_status: "fresh",
  source: {
    provider_id: "mock",
    provider_name: "Mock Market Data",
    dataset: "fixture",
    provenance: "test",
  },
  live_evaluation_groups: [
    {
      bucket_id: "applicable",
      bucket_label: "적용 가능",
      evaluations: [
        {
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
        },
      ],
    },
    {
      bucket_id: "conditions_insufficient",
      bucket_label: "지금은 조건 부족",
      evaluations: [],
    },
    {
      bucket_id: "data_unavailable",
      bucket_label: "데이터 부족",
      evaluations: [],
    },
  ],
  non_live_catalog_groups: [],
};

function okJson(data) {
  return Promise.resolve({
    ok: true,
    json: async () => data,
  });
}

describe("strategies to planner handoff", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    global.fetch = jest.fn((url) => {
      if (url.includes("/api/strategies/catalog")) {
        return okJson(catalogPayload);
      }
      if (url.includes("/api/strategies/evaluate")) {
        return okJson(evaluationPayload);
      }
      return Promise.reject(new Error(`Unexpected url ${url}`));
    });
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  test("moves a selected evaluation snapshot from /strategies into /planner review", async () => {
    render(
      <MemoryRouter initialEntries={["/strategies"]}>
        <Routes>
          <Route path="/strategies" element={<StrategiesPage />} />
          <Route path="/planner" element={<PlannerReviewPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("지원 종목의 일봉 조건을 전략별로 정리해요")).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: /이 전략으로 계획 만들기/i }));

    expect(await screen.findByText("선택한 평가 스냅샷을 검토하고 계획으로 저장해요")).toBeInTheDocument();
    expect(screen.getByText("삼성전자")).toBeInTheDocument();
    expect(screen.getByText("저장할 계획 정리")).toBeInTheDocument();
  });
});
