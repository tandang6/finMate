import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ChevronLeft,
  ChevronDown,
  ClipboardList,
  Loader2,
  PencilLine,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import StrategyCard from "../components/StrategyCard";
import {
  PLANNER_API_BASE,
  fetchJson,
  formatDateTime,
  formatPrice,
  formatPriceZone,
  getPlannerHeaders,
  parseOptionalNumber,
} from "../lib/strategy-flow";


const DISCLAIMER_TEXT =
  "* 본 서비스에서 제공하는 전략 및 정보는 투자 권유가 아니며, 일반적인 교육 목적의 참고 자료입니다. 모든 투자 판단과 그에 따른 손익의 책임은 이용자 본인에게 있습니다. 예시 전략은 미래 성과를 보장하지 않습니다.";

const FILTERS = [
  { id: "all", label: "전체" },
  { id: "saved", label: "저장됨" },
  { id: "draft", label: "임시저장" },
];

const STYLE_MAP = {
  technical: {
    label: "기술적",
    badge: "bg-indigo-50 text-indigo-700 border-indigo-100",
  },
  fundamental: {
    label: "펀더멘털",
    badge: "bg-emerald-50 text-emerald-700 border-emerald-100",
  },
  hybrid: {
    label: "하이브리드",
    badge: "bg-amber-50 text-amber-700 border-amber-100",
  },
};

const STATUS_LABELS = {
  saved: "저장됨",
  draft: "임시저장",
};

function getStrategyStyle(plan) {
  return STYLE_MAP[plan?.strategy_snapshot?.style] ?? STYLE_MAP.technical;
}

function isSnapshotBacked(plan) {
  return Boolean(plan?.evaluation_snapshot);
}

function getStrategyName(plan) {
  return (
    plan?.evaluation_snapshot?.strategy_name ??
    plan?.strategy_snapshot?.name ??
    plan?.strategy_snapshot?.strategy_id ??
    plan?.strategy_template_id ??
    "전략 정보 없음"
  );
}

function getDisplaySymbol(plan) {
  return plan?.evaluation_snapshot?.symbol?.symbol_name ?? plan?.symbol ?? "종목 정보 없음";
}

function getDisplaySymbolMeta(plan) {
  if (plan?.evaluation_snapshot?.symbol) {
    const symbol = plan.evaluation_snapshot.symbol;
    return `${symbol.symbol_code} · ${symbol.market}`;
  }
  return "기존 저장 형식";
}

function formatOverridePrice(value) {
  return Number.isFinite(value) ? formatPrice(value) : "미설정";
}

function formatOverridePercent(value) {
  return Number.isFinite(value) ? `${value}%` : "미설정";
}

function hasOverrideValues(plan) {
  return [
    plan?.entry_price_override,
    plan?.stop_loss_price_override,
    plan?.target_price_override,
    plan?.position_size_override_pct,
  ].some((value) => Number.isFinite(value));
}

function buildEditForm(plan) {
  return {
    entry_price_override:
      plan.entry_price_override == null ? "" : String(plan.entry_price_override),
    stop_loss_price_override:
      plan.stop_loss_price_override == null ? "" : String(plan.stop_loss_price_override),
    target_price_override:
      plan.target_price_override == null ? "" : String(plan.target_price_override),
    position_size_override_pct:
      plan.position_size_override_pct == null ? "" : String(plan.position_size_override_pct),
    holding_period: plan.holding_period ?? "",
    one_line_reason: plan.one_line_reason ?? "",
    note: plan.note ?? "",
    status: plan.status ?? "saved",
  };
}

function Field({ label, hint, children }) {
  const control = React.isValidElement(children)
    ? React.cloneElement(children, {
        "aria-label": children.props["aria-label"] ?? label,
      })
    : children;

  return (
    <label className="block">
      <div className="text-sm font-bold text-gray-800 mb-2">{label}</div>
      {control}
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

function OverrideSummary({ plan }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
        <div className="text-xs text-gray-400 mb-1">매수 가격 오버라이드</div>
        <div className="font-bold text-gray-900">{formatOverridePrice(plan.entry_price_override)}</div>
      </div>
      <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
        <div className="text-xs text-gray-400 mb-1">손절 가격 오버라이드</div>
        <div className="font-bold text-gray-900">{formatOverridePrice(plan.stop_loss_price_override)}</div>
      </div>
      <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
        <div className="text-xs text-gray-400 mb-1">목표 재검토 오버라이드</div>
        <div className="font-bold text-gray-900">{formatOverridePrice(plan.target_price_override)}</div>
      </div>
      <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
        <div className="text-xs text-gray-400 mb-1">첫 비중 오버라이드</div>
        <div className="font-bold text-gray-900">{formatOverridePercent(plan.position_size_override_pct)}</div>
      </div>
    </div>
  );
}

function LegacyPlanDetail({ plan }) {
  return (
    <div className="space-y-4">
      <div className="rounded-[1.25rem] border border-amber-100 bg-amber-50 px-4 py-4 text-sm text-amber-800 leading-relaxed">
        평가 스냅샷 이전에 저장된 기존 계획입니다. 현재는 저장된 표시값과 오버라이드 값만 유지하며, 실시간 재평가는 하지 않습니다.
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
          <div className="text-xs text-gray-400 mb-1">전략명</div>
          <div className="font-bold text-gray-900">{getStrategyName(plan)}</div>
        </div>
        <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
          <div className="text-xs text-gray-400 mb-1">표시 종목</div>
          <div className="font-bold text-gray-900">{plan.symbol}</div>
        </div>
        <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
          <div className="text-xs text-gray-400 mb-1">보유 기간</div>
          <div className="font-bold text-gray-900">{plan.holding_period}</div>
        </div>
        <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
          <div className="text-xs text-gray-400 mb-1">작성일</div>
          <div className="font-bold text-gray-900">{formatDateTime(plan.created_at)}</div>
        </div>
      </div>

      <OverrideSummary plan={plan} />
    </div>
  );
}

function SnapshotPlanDetail({ plan }) {
  return (
    <div className="space-y-4">
      <div className="rounded-[1.25rem] border border-indigo-100 bg-indigo-50 px-4 py-4 text-sm text-indigo-800 leading-relaxed">
        이 계획은 저장 당시의 전략 평가 스냅샷을 그대로 보여줍니다. My Plans에서는 조건을 다시 계산하지 않고, 저장된 구역과 규칙만 검토합니다.
      </div>
      <StrategyCard
        definition={plan.strategy_snapshot}
        evaluation={plan.evaluation_snapshot}
      />
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-base font-bold text-gray-900">
          <ShieldCheck className="w-4 h-4 text-indigo-600" />
          저장된 오버라이드
        </div>
        {hasOverrideValues(plan) ? (
          <OverrideSummary plan={plan} />
        ) : (
          <div className="rounded-[1.25rem] border border-dashed border-gray-200 bg-white px-4 py-4 text-sm text-gray-500">
            이 계획에는 추가 숫자 오버라이드가 없습니다. 저장된 buy zone / stop rule / target review zone을 그대로 기준으로 봅니다.
          </div>
        )}
      </div>
    </div>
  );
}

export default function MyPlansPage() {
  const [activeFilter, setActiveFilter] = useState("all");
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState("");
  const [detailMap, setDetailMap] = useState({});
  const [detailLoadingId, setDetailLoadingId] = useState("");
  const [detailError, setDetailError] = useState("");
  const [editingId, setEditingId] = useState("");
  const [editForm, setEditForm] = useState(null);
  const [savingId, setSavingId] = useState("");
  const [deletingId, setDeletingId] = useState("");

  const headers = useMemo(() => getPlannerHeaders(), []);

  const loadPlans = useCallback(async (filter = activeFilter) => {
    try {
      setLoading(true);
      setError("");
      const query = filter === "all" ? "" : `?status=${filter}`;
      const data = await fetchJson(`${PLANNER_API_BASE}/plans${query}`, { headers });
      setPlans(data);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [activeFilter, headers]);

  useEffect(() => {
    loadPlans(activeFilter);
  }, [activeFilter, loadPlans]);

  const handleExpand = async (planId) => {
    if (expandedId === planId) {
      setExpandedId("");
      setEditingId("");
      setDetailError("");
      return;
    }

    setExpandedId(planId);
    setEditingId("");
    setDetailError("");

    if (detailMap[planId]) {
      return;
    }

    try {
      setDetailLoadingId(planId);
      const detail = await fetchJson(`${PLANNER_API_BASE}/plans/${planId}`, { headers });
      setDetailMap((current) => ({ ...current, [planId]: detail }));
    } catch (loadError) {
      setDetailError(loadError.message);
    } finally {
      setDetailLoadingId("");
    }
  };

  const startEditing = (plan) => {
    setDetailError("");
    setEditingId(plan.plan_id);
    setEditForm(buildEditForm(plan));
  };

  const handleEditChange = (field, value) => {
    setEditForm((current) => ({ ...current, [field]: value }));
  };

  const saveEdit = async (planId) => {
    const entryPriceOverride = parseOptionalNumber(editForm.entry_price_override);
    const stopLossPriceOverride = parseOptionalNumber(editForm.stop_loss_price_override);
    const targetPriceOverride = parseOptionalNumber(editForm.target_price_override);
    const positionSizeOverridePct = parseOptionalNumber(editForm.position_size_override_pct);

    if (
      [entryPriceOverride, stopLossPriceOverride, targetPriceOverride, positionSizeOverridePct].some((value) =>
        Number.isNaN(value)
      )
    ) {
      setDetailError("숫자 오버라이드에는 올바른 값만 입력해 주세요.");
      return;
    }
    if (!editForm.holding_period.trim()) {
      setDetailError("보유 기간은 비워둘 수 없어요.");
      return;
    }
    if (!editForm.one_line_reason.trim()) {
      setDetailError("한 줄 이유는 비워둘 수 없어요.");
      return;
    }

    try {
      setSavingId(planId);
      setDetailError("");
      const payload = {
        entry_price_override: entryPriceOverride,
        stop_loss_price_override: stopLossPriceOverride,
        target_price_override: targetPriceOverride,
        position_size_override_pct: positionSizeOverridePct,
        holding_period: editForm.holding_period.trim(),
        one_line_reason: editForm.one_line_reason.trim(),
        note: editForm.note.trim(),
        status: editForm.status,
      };

      const updated = await fetchJson(`${PLANNER_API_BASE}/plans/${planId}`, {
        method: "PUT",
        headers,
        body: JSON.stringify(payload),
      });

      setDetailMap((current) => ({ ...current, [planId]: updated }));
      if (activeFilter === "all" || updated.status === activeFilter) {
        setPlans((current) => current.map((plan) => (plan.plan_id === planId ? updated : plan)));
      } else {
        setPlans((current) => current.filter((plan) => plan.plan_id !== planId));
      }
      setEditingId("");
      setEditForm(null);
    } catch (saveError) {
      setDetailError(saveError.message);
    } finally {
      setSavingId("");
    }
  };

  const removePlan = async (event, planId) => {
    event.stopPropagation();
    if (!window.confirm("이 계획을 삭제할까요?")) {
      return;
    }

    try {
      setDeletingId(planId);
      await fetchJson(`${PLANNER_API_BASE}/plans/${planId}`, {
        method: "DELETE",
        headers,
      });
      setPlans((current) => current.filter((plan) => plan.plan_id !== planId));
      setDetailMap((current) => {
        const next = { ...current };
        delete next[planId];
        return next;
      });
      if (expandedId === planId) {
        setExpandedId("");
        setEditingId("");
      }
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setDeletingId("");
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#F8F9FD]">
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-start justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-xs font-semibold text-indigo-700 mb-3">
              <ClipboardList className="w-4 h-4" />
              내 매수 계획
            </div>
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2">저장된 전략 스냅샷과 매수 계획</h1>
            <p className="text-sm md:text-base text-gray-500 max-w-2xl">
              저장된 평가 스냅샷을 그대로 다시 보고, 필요한 경우 오버라이드 값과 메모만 수정할 수 있어요.
            </p>
          </div>

          <Link
            to="/"
            className="inline-flex items-center gap-1 text-sm font-medium text-gray-500 hover:text-indigo-600 px-3 py-2 rounded-full hover:bg-white border border-transparent hover:border-indigo-100 shadow-sm"
          >
            <ChevronLeft className="w-4 h-4" />
            대시보드로 돌아가기
          </Link>
        </div>

        <div className="flex flex-wrap gap-2 mb-6">
          {FILTERS.map((filter) => (
            <button
              key={filter.id}
              type="button"
              onClick={() => setActiveFilter(filter.id)}
              className={`px-4 py-2 rounded-full text-sm font-semibold transition ${
                activeFilter === filter.id
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-100"
                  : "bg-white text-gray-500 border border-gray-200 hover:text-indigo-600"
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>

        {loading && (
          <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-10 flex items-center justify-center text-gray-500">
            <Loader2 className="w-5 h-5 animate-spin mr-3" />
            저장된 계획을 불러오는 중입니다.
          </div>
        )}

        {error && !loading && (
          <div className="bg-white rounded-[1.5rem] border border-red-100 shadow-sm p-6 text-red-600 mb-6">
            {error}
          </div>
        )}

        {!loading && !error && plans.length === 0 && (
          <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-10 text-center">
            <div className="text-xl font-bold text-gray-900 mb-2">아직 저장된 계획이 없어요</div>
            <p className="text-gray-500 mb-6">먼저 `/strategies`에서 전략을 비교하고, 하나의 평가 스냅샷을 선택해 계획을 만들어 보세요.</p>
            <Link
              to="/strategies"
              className="inline-flex items-center justify-center px-5 py-3 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700"
            >
              전략 보러 가기
            </Link>
          </div>
        )}

        {!loading && !error && plans.length > 0 && (
          <div className="space-y-4">
            {plans.map((plan) => {
              const detail = detailMap[plan.plan_id] ?? plan;
              const snapshotBacked = isSnapshotBacked(detail);
              const style = getStrategyStyle(detail);
              const isExpanded = expandedId === plan.plan_id;
              const isEditing = editingId === plan.plan_id;

              return (
                <div
                  key={plan.plan_id}
                  className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm overflow-hidden"
                >
                  <div className="p-5 md:p-6">
                    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${style.badge}`}>
                            {style.label}
                          </span>
                          <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-gray-100 text-gray-600">
                            {STATUS_LABELS[plan.status] ?? plan.status}
                          </span>
                          <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${
                            snapshotBacked
                              ? "bg-indigo-50 text-indigo-700 border-indigo-100"
                              : "bg-amber-50 text-amber-700 border-amber-100"
                          }`}>
                            {snapshotBacked ? "스냅샷 기반" : "기존 계획"}
                          </span>
                          <span className="text-xs text-gray-400">{formatDateTime(plan.created_at)}</span>
                        </div>
                        <div>
                          <div className="text-xl font-bold text-gray-900">{getDisplaySymbol(detail)}</div>
                          <div className="text-sm text-gray-500">
                            {getStrategyName(detail)} · {getDisplaySymbolMeta(detail)}
                          </div>
                        </div>
                        <div className="text-sm text-gray-600">{plan.one_line_reason}</div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 min-w-0">
                        {snapshotBacked ? (
                          <>
                            <div className="bg-gray-50 rounded-2xl p-4">
                              <div className="text-xs text-gray-400 mb-1">매수 구역</div>
                              <div className="font-bold text-gray-900">{formatPriceZone(detail.evaluation_snapshot.buy_zone)}</div>
                            </div>
                            <div className="bg-gray-50 rounded-2xl p-4">
                              <div className="text-xs text-gray-400 mb-1">목표 재검토</div>
                              <div className="font-bold text-gray-900">{formatPriceZone(detail.evaluation_snapshot.target_review_zone)}</div>
                            </div>
                            <div className="bg-gray-50 rounded-2xl p-4">
                              <div className="text-xs text-gray-400 mb-1">오버라이드</div>
                              <div className="font-bold text-gray-900">{hasOverrideValues(detail) ? "있음" : "없음"}</div>
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="bg-gray-50 rounded-2xl p-4">
                              <div className="text-xs text-gray-400 mb-1">매수 오버라이드</div>
                              <div className="font-bold text-gray-900">{formatOverridePrice(detail.entry_price_override)}</div>
                            </div>
                            <div className="bg-gray-50 rounded-2xl p-4">
                              <div className="text-xs text-gray-400 mb-1">손절 오버라이드</div>
                              <div className="font-bold text-gray-900">{formatOverridePrice(detail.stop_loss_price_override)}</div>
                            </div>
                            <div className="bg-gray-50 rounded-2xl p-4">
                              <div className="text-xs text-gray-400 mb-1">목표 오버라이드</div>
                              <div className="font-bold text-gray-900">{formatOverridePrice(detail.target_price_override)}</div>
                            </div>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center justify-between mt-5 text-sm text-gray-500">
                      <button
                        type="button"
                        onClick={() => handleExpand(plan.plan_id)}
                        className="inline-flex items-center gap-2 hover:text-indigo-600"
                      >
                        <ChevronDown className={`w-4 h-4 transition ${isExpanded ? "rotate-180" : ""}`} />
                        {isExpanded ? "상세 접기" : "상세 보기"}
                      </button>
                      <button
                        type="button"
                        onClick={(event) => removePlan(event, plan.plan_id)}
                        disabled={deletingId === plan.plan_id}
                        className="inline-flex items-center gap-2 text-red-500 hover:text-red-600"
                      >
                        <Trash2 className="w-4 h-4" />
                        {deletingId === plan.plan_id ? "삭제 중..." : "삭제"}
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-gray-100 px-5 md:px-6 py-6 bg-gray-50/60">
                      {detailLoadingId === plan.plan_id && (
                        <div className="flex items-center text-sm text-gray-500 mb-4">
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          상세 내용을 불러오는 중입니다.
                        </div>
                      )}

                      {detailError && (
                        <div className="text-sm text-red-600 mb-4">{detailError}</div>
                      )}

                      {!isEditing && (
                        <div className="space-y-4">
                          {snapshotBacked ? <SnapshotPlanDetail plan={detail} /> : <LegacyPlanDetail plan={detail} />}

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
                              <div className="text-xs text-gray-400 mb-1">보유 기간</div>
                              <div className="font-bold text-gray-900">{detail.holding_period}</div>
                            </div>
                            <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
                              <div className="text-xs text-gray-400 mb-1">상태</div>
                              <div className="font-bold text-gray-900">{STATUS_LABELS[detail.status] ?? detail.status}</div>
                            </div>
                          </div>

                          <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
                            <div className="text-xs text-gray-400 mb-1">매수 이유</div>
                            <div className="text-sm text-gray-700">{detail.one_line_reason}</div>
                          </div>

                          <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
                            <div className="text-xs text-gray-400 mb-1">메모</div>
                            <div className="text-sm text-gray-700 whitespace-pre-wrap">
                              {detail.note || "아직 메모가 없습니다."}
                            </div>
                          </div>

                          <div className="flex flex-col sm:flex-row gap-3">
                            <button
                              type="button"
                              onClick={() => startEditing(detail)}
                              className="inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700"
                            >
                              <PencilLine className="w-4 h-4" />
                              오버라이드 수정
                            </button>
                          </div>
                        </div>
                      )}

                      {isEditing && editForm && (
                        <div className="space-y-5">
                          <div className="text-base font-bold text-gray-900">허용된 필드만 수정</div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <Field
                              label="매수 가격 오버라이드"
                              hint={snapshotBacked ? `저장된 buy zone: ${formatPriceZone(detail.evaluation_snapshot.buy_zone)}` : "기존 계획의 선택 입력 값입니다."}
                            >
                              <TextInput
                                type="number"
                                value={editForm.entry_price_override}
                                onChange={(event) => handleEditChange("entry_price_override", event.target.value)}
                                placeholder="비워두면 미설정"
                              />
                            </Field>

                            <Field
                              label="손절 가격 오버라이드"
                              hint={snapshotBacked ? detail.evaluation_snapshot.stop_invalidation_rule.rule_text : "기존 계획의 선택 입력 값입니다."}
                            >
                              <TextInput
                                type="number"
                                value={editForm.stop_loss_price_override}
                                onChange={(event) => handleEditChange("stop_loss_price_override", event.target.value)}
                                placeholder="비워두면 미설정"
                              />
                            </Field>

                            <Field
                              label="목표 재검토 오버라이드"
                              hint={snapshotBacked ? `저장된 target review zone: ${formatPriceZone(detail.evaluation_snapshot.target_review_zone)}` : "기존 계획의 선택 입력 값입니다."}
                            >
                              <TextInput
                                type="number"
                                value={editForm.target_price_override}
                                onChange={(event) => handleEditChange("target_price_override", event.target.value)}
                                placeholder="비워두면 미설정"
                              />
                            </Field>

                            <Field label="첫 비중 오버라이드(%)" hint="선택 입력입니다.">
                              <TextInput
                                type="number"
                                value={editForm.position_size_override_pct}
                                onChange={(event) => handleEditChange("position_size_override_pct", event.target.value)}
                                placeholder="비워두면 미설정"
                              />
                            </Field>

                            <Field label="보유 기간" hint="수정 가능한 메모성 필드입니다.">
                              <TextInput
                                value={editForm.holding_period}
                                onChange={(event) => handleEditChange("holding_period", event.target.value)}
                                placeholder="예: 2주"
                              />
                            </Field>

                            <Field label="상태" hint="저장됨 또는 임시저장만 선택할 수 있어요.">
                              <select
                                value={editForm.status}
                                onChange={(event) => handleEditChange("status", event.target.value)}
                                className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-700 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
                              >
                                <option value="saved">저장됨</option>
                                <option value="draft">임시저장</option>
                              </select>
                            </Field>
                          </div>

                          <Field label="한 줄 이유" hint="계획의 핵심 이유만 짧게 유지하세요.">
                            <TextInput
                              value={editForm.one_line_reason}
                              onChange={(event) => handleEditChange("one_line_reason", event.target.value)}
                              placeholder="예: 저장된 buy zone 근처에서 다시 검토"
                            />
                          </Field>

                          <Field label="메모" hint="기록용 메모만 수정합니다.">
                            <TextArea
                              rows={4}
                              value={editForm.note}
                              onChange={(event) => handleEditChange("note", event.target.value)}
                              placeholder="메모"
                            />
                          </Field>

                          <div className="flex flex-col sm:flex-row gap-3">
                            <button
                              type="button"
                              onClick={() => saveEdit(plan.plan_id)}
                              disabled={savingId === plan.plan_id}
                              className="px-4 py-3 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 disabled:opacity-60"
                            >
                              {savingId === plan.plan_id ? "저장 중..." : "수정 저장"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingId("");
                                setEditForm(null);
                              }}
                              className="px-4 py-3 rounded-xl border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                            >
                              취소
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="mt-8 text-[11px] text-gray-400 border-t border-gray-100 pt-4">
          {DISCLAIMER_TEXT}
        </div>
      </main>
    </div>
  );
}
