import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ChevronLeft,
  ChevronDown,
  ClipboardList,
  Loader2,
  PencilLine,
  Trash2,
} from "lucide-react";


const API_BASE = "http://localhost:8000/api/planner";
const USER_ID_KEY = "finmate-user-id";
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


function getPlannerUserId() {
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


async function fetchJson(url, options = {}) {
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


function formatDate(value) {
  return new Date(value).toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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

  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      "X-User-Id": getPlannerUserId(),
    }),
    []
  );

  const loadPlans = useCallback(async (filter = activeFilter) => {
    try {
      setLoading(true);
      setError("");
      const query = filter === "all" ? "" : `?status=${filter}`;
      const data = await fetchJson(`${API_BASE}/plans${query}`, { headers });
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
      const detail = await fetchJson(`${API_BASE}/plans/${planId}`, { headers });
      setDetailMap((current) => ({ ...current, [planId]: detail }));
    } catch (loadError) {
      setDetailError(loadError.message);
    } finally {
      setDetailLoadingId("");
    }
  };

  const startEditing = (plan) => {
    setEditingId(plan.plan_id);
    setEditForm({
      stop_loss_price: String(plan.stop_loss_price),
      target_price: String(plan.target_price),
      position_size_pct: String(plan.position_size_pct),
      holding_period: plan.holding_period,
      one_line_reason: plan.one_line_reason,
      note: plan.note ?? "",
      status: plan.status,
    });
  };

  const handleEditChange = (field, value) => {
    setEditForm((current) => ({ ...current, [field]: value }));
  };

  const saveEdit = async (planId) => {
    try {
      setSavingId(planId);
      const payload = {
        stop_loss_price: Number(editForm.stop_loss_price),
        target_price: Number(editForm.target_price),
        position_size_pct: Number(editForm.position_size_pct),
        holding_period: editForm.holding_period,
        one_line_reason: editForm.one_line_reason.trim(),
        note: editForm.note.trim(),
        status: editForm.status,
      };

      const updated = await fetchJson(`${API_BASE}/plans/${planId}`, {
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
      await fetchJson(`${API_BASE}/plans/${planId}`, {
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
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2">저장된 첫 매수 플랜</h1>
            <p className="text-sm md:text-base text-gray-500 max-w-2xl">
              저장한 계획을 다시 보고, 상세 내용을 확인한 뒤 필요하면 수정하거나 삭제할 수 있어요.
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
            <p className="text-gray-500 mb-6">종목과 전략을 먼저 고른 뒤, 첫 매수 계획을 하나 만들어보세요.</p>
            <Link
              to="/planner"
              className="inline-flex items-center justify-center px-5 py-3 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700"
            >
              매수 플래너로 가기
            </Link>
          </div>
        )}

        {!loading && !error && plans.length > 0 && (
          <div className="space-y-4">
            {plans.map((plan) => {
              const detail = detailMap[plan.plan_id] ?? plan;
              const strategy = detail.strategy_snapshot ?? {};
              const style = STYLE_MAP[strategy.style] ?? STYLE_MAP.technical;
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
                            {plan.status === "draft" ? "임시저장" : "저장됨"}
                          </span>
                          <span className="text-xs text-gray-400">{formatDate(plan.created_at)}</span>
                        </div>
                        <div>
                          <div className="text-xl font-bold text-gray-900">{plan.symbol}</div>
                          <div className="text-sm text-gray-500">{strategy.name}</div>
                        </div>
                        <div className="text-sm text-gray-600">{plan.one_line_reason}</div>
                      </div>

                      <div className="grid grid-cols-3 gap-3 text-sm min-w-0">
                        <div className="bg-gray-50 rounded-2xl p-4">
                          <div className="text-xs text-gray-400 mb-1">손절가</div>
                          <div className="font-bold text-gray-900">{plan.stop_loss_price}</div>
                        </div>
                        <div className="bg-gray-50 rounded-2xl p-4">
                          <div className="text-xs text-gray-400 mb-1">목표가</div>
                          <div className="font-bold text-gray-900">{plan.target_price}</div>
                        </div>
                        <div className="bg-gray-50 rounded-2xl p-4">
                          <div className="text-xs text-gray-400 mb-1">비중</div>
                          <div className="font-bold text-gray-900">{plan.position_size_pct}%</div>
                        </div>
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
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                            <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
                              <div className="text-xs text-gray-400 mb-1">전략명</div>
                              <div className="font-bold text-gray-900">{strategy.name}</div>
                            </div>
                            <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
                              <div className="text-xs text-gray-400 mb-1">작성일</div>
                              <div className="font-bold text-gray-900">{formatDate(detail.created_at)}</div>
                            </div>
                            <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
                              <div className="text-xs text-gray-400 mb-1">매수 희망가</div>
                              <div className="font-bold text-gray-900">{detail.entry_price}</div>
                            </div>
                            <div className="bg-white rounded-[1.25rem] border border-gray-100 p-4">
                              <div className="text-xs text-gray-400 mb-1">보유 기간</div>
                              <div className="font-bold text-gray-900">{detail.holding_period}</div>
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
                              수정하기
                            </button>
                          </div>
                        </div>
                      )}

                      {isEditing && editForm && (
                        <div className="space-y-4">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <input
                              type="number"
                              value={editForm.stop_loss_price}
                              onChange={(event) => handleEditChange("stop_loss_price", event.target.value)}
                              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none"
                              placeholder="손절가"
                            />
                            <input
                              type="number"
                              value={editForm.target_price}
                              onChange={(event) => handleEditChange("target_price", event.target.value)}
                              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none"
                              placeholder="목표가"
                            />
                            <input
                              type="number"
                              value={editForm.position_size_pct}
                              onChange={(event) => handleEditChange("position_size_pct", event.target.value)}
                              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none"
                              placeholder="비중"
                            />
                            <select
                              value={editForm.holding_period}
                              onChange={(event) => handleEditChange("holding_period", event.target.value)}
                              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none bg-white"
                            >
                              {["1주", "2주", "1개월", "3개월", "6개월", "1년", "기타"].map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                            <select
                              value={editForm.status}
                              onChange={(event) => handleEditChange("status", event.target.value)}
                              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none bg-white"
                            >
                              <option value="saved">저장됨</option>
                              <option value="draft">임시저장</option>
                            </select>
                          </div>

                          <input
                            type="text"
                            value={editForm.one_line_reason}
                            onChange={(event) => handleEditChange("one_line_reason", event.target.value)}
                            className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none"
                            placeholder="매수 이유 한 줄"
                          />

                          <textarea
                            rows={4}
                            value={editForm.note}
                            onChange={(event) => handleEditChange("note", event.target.value)}
                            className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
                            placeholder="메모"
                          />

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
