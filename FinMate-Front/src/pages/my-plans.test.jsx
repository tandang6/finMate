import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import MyPlansPage from "./my-plans";


const snapshotEvaluation = {
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

const snapshotPlan = {
  plan_id: "plan-snapshot",
  symbol: "임의 표시 이름",
  strategy_template_id: "ma_reclaim",
  strategy_snapshot: {
    strategy_id: "ma_reclaim",
    name: "MA Reclaim",
    style: "technical",
    activation_state: "live",
    activation_reason: "Approved live strategy",
    summary: "Price reclaims a key moving average.",
    when_to_use: "Use after a constructive reclaim.",
    when_not_to_use: "Avoid in weak structure.",
    holding_profile: "Days to weeks.",
    disclaimer: "Educational only.",
  },
  evaluation_snapshot: snapshotEvaluation,
  entry_price_override: 81500,
  stop_loss_price_override: null,
  target_price_override: 87500,
  position_size_override_pct: 25,
  holding_period: "2주",
  one_line_reason: "저장된 buy zone 부근 검토",
  note: "첫 진입은 보수적으로 기록",
  status: "saved",
  created_at: "2026-04-19T00:00:00Z",
  updated_at: "2026-04-19T00:00:00Z",
};

const legacyPlan = {
  plan_id: "plan-legacy",
  symbol: "네이버",
  strategy_template_id: "pullback",
  strategy_snapshot: {
    strategy_id: "pullback",
    name: "Pullback",
    style: "technical",
  },
  evaluation_snapshot: null,
  entry_price_override: 250000,
  stop_loss_price_override: 240000,
  target_price_override: 270000,
  position_size_override_pct: null,
  holding_period: "3주",
  one_line_reason: "기존 수동 계획",
  note: "레거시 메모",
  status: "draft",
  created_at: "2026-04-18T00:00:00Z",
  updated_at: "2026-04-18T00:00:00Z",
};

function okJson(data) {
  return Promise.resolve({
    ok: true,
    json: async () => data,
  });
}

function renderMyPlans() {
  return render(
    <MemoryRouter>
      <MyPlansPage />
    </MemoryRouter>
  );
}

describe("MyPlansPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.confirm = jest.fn(() => true);
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  test("renders snapshot-backed plans from evaluation_snapshot first", async () => {
    global.fetch = jest.fn((url) => {
      if (url.includes("/api/planner/plans/plan-snapshot")) {
        return okJson(snapshotPlan);
      }
      if (url.includes("/api/planner/plans")) {
        return okJson([snapshotPlan]);
      }
      return Promise.reject(new Error(`Unexpected url ${url}`));
    });

    renderMyPlans();

    expect(await screen.findByText("삼성전자")).toBeInTheDocument();
    expect(screen.queryByText("임의 표시 이름")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "상세 보기" }));

    expect(await screen.findByText(/저장 당시의 전략 평가 스냅샷/)).toBeInTheDocument();
    expect(
      screen.getAllByText((_, element) => element?.textContent?.includes("005930 · KRX") ?? false).length
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("매수 구역").length).toBeGreaterThan(0);
    expect(screen.getAllByText("무효화 규칙").length).toBeGreaterThan(0);
    expect(screen.getAllByText("목표 재검토 구역").length).toBeGreaterThan(0);
    expect(screen.getAllByText("첫 비중 가이드").length).toBeGreaterThan(0);
    expect(screen.getAllByText("보유 프로필").length).toBeGreaterThan(0);
    expect(screen.getByText("25%")).toBeInTheDocument();
  });

  test("preserves legacy fallback rendering when evaluation_snapshot is missing", async () => {
    global.fetch = jest.fn((url) => {
      if (url.includes("/api/planner/plans/plan-legacy")) {
        return okJson(legacyPlan);
      }
      if (url.includes("/api/planner/plans")) {
        return okJson([legacyPlan]);
      }
      return Promise.reject(new Error(`Unexpected url ${url}`));
    });

    renderMyPlans();

    expect(await screen.findByText("네이버")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "상세 보기" }));

    expect(await screen.findByText(/평가 스냅샷 이전에 저장된 기존 계획입니다/)).toBeInTheDocument();
    expect(screen.getByText(/기존 저장 형식/)).toBeInTheDocument();
    expect(screen.queryByText("현재 조건 확인")).not.toBeInTheDocument();
    expect(screen.getAllByText("250,000원").length).toBeGreaterThan(0);
    expect(screen.getAllByText("270,000원").length).toBeGreaterThan(0);
  });

  test("allows only override and note fields to be edited", async () => {
    const updatedPlan = {
      ...snapshotPlan,
      entry_price_override: 82000,
      stop_loss_price_override: 79000,
      target_price_override: 89000,
      position_size_override_pct: 30,
      holding_period: "3주",
      one_line_reason: "저장된 구역 안에서만 검토",
      note: "오버라이드 수정 완료",
      status: "draft",
    };

    global.fetch = jest.fn((url, options = {}) => {
      if (url.includes("/api/planner/plans/plan-snapshot") && options.method === "PUT") {
        return okJson(updatedPlan);
      }
      if (url.includes("/api/planner/plans/plan-snapshot")) {
        return okJson(snapshotPlan);
      }
      if (url.includes("/api/planner/plans")) {
        return okJson([snapshotPlan]);
      }
      return Promise.reject(new Error(`Unexpected url ${url}`));
    });

    renderMyPlans();

    fireEvent.click(await screen.findByRole("button", { name: "상세 보기" }));
    fireEvent.click(await screen.findByRole("button", { name: "오버라이드 수정" }));

    fireEvent.change(screen.getByLabelText("매수 가격 오버라이드"), {
      target: { value: "82000" },
    });
    fireEvent.change(screen.getByLabelText("손절 가격 오버라이드"), {
      target: { value: "79000" },
    });
    fireEvent.change(screen.getByLabelText("목표 재검토 오버라이드"), {
      target: { value: "89000" },
    });
    fireEvent.change(screen.getByLabelText("첫 비중 오버라이드(%)"), {
      target: { value: "30" },
    });
    fireEvent.change(screen.getByLabelText("보유 기간"), {
      target: { value: "3주" },
    });
    fireEvent.change(screen.getByLabelText("상태"), {
      target: { value: "draft" },
    });
    fireEvent.change(screen.getByLabelText("한 줄 이유"), {
      target: { value: "저장된 구역 안에서만 검토" },
    });
    fireEvent.change(screen.getByLabelText("메모"), {
      target: { value: "오버라이드 수정 완료" },
    });

    fireEvent.click(screen.getByRole("button", { name: "수정 저장" }));

    await waitFor(() => {
      const saveCall = global.fetch.mock.calls.find(
        ([url, options]) =>
          url.includes("/api/planner/plans/plan-snapshot") && options?.method === "PUT"
      );
      expect(saveCall).toBeTruthy();

      const payload = JSON.parse(saveCall[1].body);
      expect(Object.keys(payload).sort()).toEqual(
        [
          "entry_price_override",
          "holding_period",
          "note",
          "one_line_reason",
          "position_size_override_pct",
          "status",
          "stop_loss_price_override",
          "target_price_override",
        ].sort()
      );
      expect(payload.symbol).toBeUndefined();
      expect(payload.evaluation_snapshot).toBeUndefined();
      expect(payload.strategy_template_id).toBeUndefined();
      expect(payload.entry_price_override).toBe(82000);
      expect(payload.stop_loss_price_override).toBe(79000);
      expect(payload.target_price_override).toBe(89000);
      expect(payload.position_size_override_pct).toBe(30);
      expect(payload.holding_period).toBe("3주");
      expect(payload.one_line_reason).toBe("저장된 구역 안에서만 검토");
      expect(payload.note).toBe("오버라이드 수정 완료");
      expect(payload.status).toBe("draft");
    });
  });

  test("shows a /strategies-first empty state when there are no saved plans", async () => {
    global.fetch = jest.fn((url) => {
      if (url.includes("/api/planner/plans")) {
        return okJson([]);
      }
      return Promise.reject(new Error(`Unexpected url ${url}`));
    });

    renderMyPlans();

    expect(await screen.findByText("아직 저장된 계획이 없어요")).toBeInTheDocument();
    expect(screen.getByText(/먼저 `\/strategies`에서 전략을 비교하고/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "전략 보러 가기" })).toHaveAttribute("href", "/strategies");
    expect(screen.queryByRole("link", { name: /planner/i })).not.toBeInTheDocument();
  });
});
