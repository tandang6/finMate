import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ChevronLeft,
  ClipboardList,
  Loader2,
  PencilLine,
  Save,
  ShieldCheck,
} from "lucide-react";

import StrategyCard from "../components/StrategyCard";
import {
  PLANNER_API_BASE,
  STRATEGY_API_BASE,
  clearPlannerSelection,
  fetchJson,
  formatDateTime,
  formatPriceZone,
  getPlannerHeaders,
  loadPlannerSelection,
  parseOptionalNumber,
  savePlannerSelection,
} from "../lib/strategy-flow";


const EMPTY_FORM = {
  entry_price_override: "",
  stop_loss_price_override: "",
  target_price_override: "",
  position_size_override_pct: "",
  holding_period: "",
  one_line_reason: "",
  note: "",
};

function buildInitialForm(selection, definition) {
  return {
    ...EMPTY_FORM,
    holding_period: definition?.holding_profile ?? selection?.evaluation_snapshot?.holding_profile ?? "",
  };
}

function Field({ label, hint, children }) {
  return (
    <label className="block">
      <div className="text-sm font-bold text-gray-800 mb-2">{label}</div>
      {children}
      {hint && <div className="text-xs text-gray-400 mt-2">{hint}</div>}
    </label>
  );
}

function TextInput(props) {
  return (
    <input
      {...props}
      className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
    />
  );
}

function TextArea(props) {
  return (
    <textarea
      {...props}
      className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
    />
  );
}

export default function PlannerReviewPage() {
  const location = useLocation();
  const [plannerSelection, setPlannerSelection] = useState(() => {
    const fromRoute = location.state?.plannerSelection;
    return fromRoute?.evaluation_snapshot ? fromRoute : loadPlannerSelection();
  });
  const [catalog, setCatalog] = useState(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [saveError, setSaveError] = useState("");
  const [saveLoading, setSaveLoading] = useState("");
  const [savedPlan, setSavedPlan] = useState(null);

  useEffect(() => {
    const incoming = location.state?.plannerSelection;
    if (incoming?.evaluation_snapshot) {
      savePlannerSelection(incoming);
      setPlannerSelection(incoming);
    }
  }, [location.state]);

  useEffect(() => {
    if (!plannerSelection?.evaluation_snapshot) {
      setCatalogLoading(false);
      setCatalogError("");
      return undefined;
    }

    let cancelled = false;

    async function loadCatalog() {
      try {
        setCatalogLoading(true);
        setCatalogError("");
        const data = await fetchJson(`${STRATEGY_API_BASE}/catalog`);
        if (!cancelled) {
          setCatalog(data);
        }
      } catch (error) {
        if (!cancelled) {
          setCatalogError(error.message);
        }
      } finally {
        if (!cancelled) {
          setCatalogLoading(false);
        }
      }
    }

    loadCatalog();
    return () => {
      cancelled = true;
    };
  }, [plannerSelection]);

  const definition = useMemo(() => {
    if (!plannerSelection?.evaluation_snapshot || !catalog?.strategies) {
      return null;
    }
    return (
      catalog.strategies.find(
        (strategy) => strategy.strategy_id === plannerSelection.evaluation_snapshot.strategy_id
      ) ?? null
    );
  }, [catalog, plannerSelection]);

  useEffect(() => {
    if (!plannerSelection?.evaluation_snapshot) {
      setForm(EMPTY_FORM);
      return;
    }
    setForm(buildInitialForm(plannerSelection, definition));
    setSavedPlan(null);
    setSaveError("");
  }, [definition, plannerSelection]);

  const evaluation = plannerSelection?.evaluation_snapshot ?? null;

  const handleFormChange = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const validateForm = () => {
    if (!evaluation) {
      return "선택된 전략 평가가 없습니다.";
    }
    if (!form.holding_period.trim()) {
      return "보유 계획은 비워둘 수 없어요.";
    }
    if (!form.one_line_reason.trim()) {
      return "한 줄 이유를 입력해 주세요.";
    }

    const numericFields = [
      "entry_price_override",
      "stop_loss_price_override",
      "target_price_override",
      "position_size_override_pct",
    ];

    for (const field of numericFields) {
      const parsed = parseOptionalNumber(form[field]);
      if (Number.isNaN(parsed)) {
        return "선택 입력한 숫자 필드는 올바른 값만 넣어 주세요.";
      }
    }

    return "";
  };

  const submitPlan = async (status) => {
    const validationError = validateForm();
    if (validationError) {
      setSaveError(validationError);
      return;
    }

    try {
      setSaveLoading(status);
      setSaveError("");

      const payload = {
        strategy_template_id: evaluation.strategy_id,
        evaluation_snapshot: evaluation,
        holding_period: form.holding_period.trim(),
        one_line_reason: form.one_line_reason.trim(),
        note: form.note.trim(),
        status,
      };

      const entryPriceOverride = parseOptionalNumber(form.entry_price_override);
      const stopLossPriceOverride = parseOptionalNumber(form.stop_loss_price_override);
      const targetPriceOverride = parseOptionalNumber(form.target_price_override);
      const positionSizeOverridePct = parseOptionalNumber(form.position_size_override_pct);

      if (entryPriceOverride !== null) {
        payload.entry_price_override = entryPriceOverride;
      }
      if (stopLossPriceOverride !== null) {
        payload.stop_loss_price_override = stopLossPriceOverride;
      }
      if (targetPriceOverride !== null) {
        payload.target_price_override = targetPriceOverride;
      }
      if (positionSizeOverridePct !== null) {
        payload.position_size_override_pct = positionSizeOverridePct;
      }

      const saved = await fetchJson(`${PLANNER_API_BASE}/plans`, {
        method: "POST",
        headers: getPlannerHeaders(),
        body: JSON.stringify(payload),
      });

      setSavedPlan(saved);
      savePlannerSelection({ evaluation_snapshot: saved.evaluation_snapshot ?? evaluation });
    } catch (error) {
      setSaveError(error.message);
    } finally {
      setSaveLoading("");
    }
  };

  if (!evaluation) {
    return (
      <div className="min-h-[calc(100vh-4rem)] bg-[#F8F9FD]">
        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="bg-white rounded-[2rem] border border-gray-100 shadow-sm px-6 py-8 md:px-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-xs font-semibold text-indigo-700 mb-4">
              <ClipboardList className="w-4 h-4" />
              스냅샷 검토 / 저장
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-3">검토할 전략 스냅샷이 아직 없어요</h1>
            <p className="text-sm md:text-base text-gray-500 leading-relaxed mb-6">
              이제 `/planner`는 단독 탐색 화면이 아니라, `/strategies`에서 선택한 규칙 기반 평가 스냅샷을 검토하고 저장하는 화면입니다.
            </p>
            <Link
              to="/strategies"
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700"
            >
              <ChevronLeft className="w-4 h-4" />
              /strategies로 돌아가기
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#F8F9FD]">
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <section className="bg-white rounded-[2rem] border border-gray-100 shadow-sm px-6 py-7 md:px-8">
          <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-6">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-xs font-semibold text-indigo-700 mb-4">
                <PencilLine className="w-4 h-4" />
                스냅샷 검토 / 저장
              </div>
              <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-3">선택한 평가 스냅샷을 검토하고 계획으로 저장해요</h1>
              <p className="text-sm md:text-base text-gray-500 leading-relaxed">
                이 화면은 전략을 다시 추천하지 않는 review 단계입니다. `/strategies`에서 고른 규칙 기반 평가 결과를 그대로 보여주고,
                필요한 경우에만 숫자 오버라이드를 덧붙여 저장합니다.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/strategies"
                className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm font-semibold text-gray-600 hover:text-indigo-600"
              >
                <ChevronLeft className="w-4 h-4" />
                전략 다시 보기
              </Link>
              <button
                type="button"
                onClick={() => {
                  clearPlannerSelection();
                  setPlannerSelection(null);
                }}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm font-semibold text-gray-600 hover:text-indigo-600"
              >
                스냅샷 비우기
              </button>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div className="rounded-[1.5rem] border border-gray-100 bg-white px-5 py-5 shadow-sm">
            <div className="text-xs font-bold uppercase tracking-[0.18em] text-gray-400 mb-2">선택 종목</div>
            <div className="text-lg font-bold text-gray-900">{evaluation.symbol.symbol_name}</div>
            <div className="text-sm text-gray-500 mt-1">{evaluation.symbol.symbol_code} · {evaluation.symbol.market}</div>
          </div>
          <div className="rounded-[1.5rem] border border-gray-100 bg-white px-5 py-5 shadow-sm">
            <div className="text-xs font-bold uppercase tracking-[0.18em] text-gray-400 mb-2">평가 시각</div>
            <div className="text-lg font-bold text-gray-900">{formatDateTime(evaluation.evaluated_at)}</div>
            <div className="text-sm text-gray-500 mt-1">{evaluation.timeframe} 기준</div>
          </div>
          <div className="rounded-[1.5rem] border border-gray-100 bg-white px-5 py-5 shadow-sm">
            <div className="text-xs font-bold uppercase tracking-[0.18em] text-gray-400 mb-2">오버라이드 안내</div>
            <div className="text-sm text-gray-600 leading-relaxed">
              숫자 입력은 선택 사항입니다. 비워두면 저장된 계획은 평가 스냅샷의 구역과 규칙을 그대로 기준으로 삼고,
              정확한 매수/손절 숫자를 강제하지 않습니다.
            </div>
          </div>
        </section>

        {catalogLoading && (
          <div className="bg-white rounded-[1.75rem] border border-gray-100 shadow-sm px-6 py-10 flex items-center justify-center text-gray-500">
            <Loader2 className="w-5 h-5 animate-spin mr-3" />
            전략 정의를 불러오는 중입니다.
          </div>
        )}

        {catalogError && (
          <div className="bg-white rounded-[1.75rem] border border-red-100 shadow-sm px-6 py-6 text-red-600">
            {catalogError}
          </div>
        )}

        {!catalogLoading && definition && (
          <StrategyCard definition={definition} evaluation={evaluation} />
        )}

        <section className="bg-white rounded-[1.75rem] border border-gray-100 shadow-sm px-6 py-6 md:px-7 md:py-7">
          <div className="flex items-center gap-2 text-lg font-bold text-gray-900 mb-5">
            <ShieldCheck className="w-5 h-5 text-indigo-600" />
            저장할 계획 정리
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <Field
              label="보유 계획"
              hint="전략 카드의 보유 프로필을 기준으로 내 표현으로 정리해도 좋습니다."
            >
              <TextInput
                value={form.holding_period}
                onChange={(event) => handleFormChange("holding_period", event.target.value)}
                placeholder="예: 2주 동안 일봉 종가 기준으로 추적"
              />
            </Field>

            <Field
              label="한 줄 이유"
              hint="저장 시 필수입니다. 나중에 계획을 다시 볼 때 바로 이해되는 문장으로 적어 주세요."
            >
              <TextInput
                value={form.one_line_reason}
                onChange={(event) => handleFormChange("one_line_reason", event.target.value)}
                maxLength={100}
                placeholder="예: 20일선 재돌파 뒤 50일선 위에서 지지 확인"
              />
            </Field>

            <Field
              label="매수 가격 오버라이드"
              hint={`현재 buy zone: ${formatPriceZone(evaluation.buy_zone)}`}
            >
              <TextInput
                value={form.entry_price_override}
                onChange={(event) => handleFormChange("entry_price_override", event.target.value)}
                inputMode="decimal"
                placeholder="비워두면 스냅샷 구역을 그대로 사용"
              />
            </Field>

            <Field
              label="손절 가격 오버라이드"
              hint={evaluation.stop_invalidation_rule.rule_text}
            >
              <TextInput
                value={form.stop_loss_price_override}
                onChange={(event) => handleFormChange("stop_loss_price_override", event.target.value)}
                inputMode="decimal"
                placeholder="선택 입력"
              />
            </Field>

            <Field
              label="목표 재검토 가격 오버라이드"
              hint={`현재 target review zone: ${formatPriceZone(evaluation.target_review_zone)}`}
            >
              <TextInput
                value={form.target_price_override}
                onChange={(event) => handleFormChange("target_price_override", event.target.value)}
                inputMode="decimal"
                placeholder="선택 입력"
              />
            </Field>

            <Field
              label="첫 비중 오버라이드(%)"
              hint={evaluation.first_position_rule}
            >
              <TextInput
                value={form.position_size_override_pct}
                onChange={(event) => handleFormChange("position_size_override_pct", event.target.value)}
                inputMode="decimal"
                placeholder="예: 15"
              />
            </Field>
          </div>

          <div className="mt-5">
            <Field label="메모" hint="선택 입력입니다. 내 관찰 포인트나 경고 문구를 남길 수 있어요.">
              <TextArea
                rows={4}
                value={form.note}
                onChange={(event) => handleFormChange("note", event.target.value)}
                placeholder="예: 데이터 부족 카드면 재평가 후 다시 확인"
              />
            </Field>
          </div>

          {saveError && (
            <div className="mt-5 rounded-[1.25rem] border border-red-100 bg-red-50 px-4 py-4 text-sm text-red-600">
              {saveError}
            </div>
          )}

          {savedPlan && (
            <div className="mt-5 rounded-[1.25rem] border border-emerald-100 bg-emerald-50 px-4 py-4">
              <div className="text-sm font-bold text-emerald-900 mb-1">계획이 저장되었어요</div>
              <div className="text-sm text-emerald-800 leading-relaxed">
                {savedPlan.symbol} · {savedPlan.strategy_snapshot?.name ?? evaluation.strategy_name}
              </div>
              <div className="text-xs text-emerald-700 mt-2">
                저장 시각 {formatDateTime(savedPlan.created_at)}
              </div>
              <Link
                to="/my-plans"
                className="inline-flex items-center gap-2 mt-4 rounded-xl border border-emerald-200 bg-white px-4 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-100"
              >
                저장된 계획 보기
              </Link>
            </div>
          )}

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => submitPlan("saved")}
              disabled={Boolean(saveLoading)}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700 disabled:opacity-70"
            >
              {saveLoading === "saved" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              저장하기
            </button>
            <button
              type="button"
              onClick={() => submitPlan("draft")}
              disabled={Boolean(saveLoading)}
              className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm font-semibold text-gray-700 hover:text-indigo-600 disabled:opacity-70"
            >
              {saveLoading === "draft" ? <Loader2 className="w-4 h-4 animate-spin" /> : <ClipboardList className="w-4 h-4" />}
              임시저장
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
