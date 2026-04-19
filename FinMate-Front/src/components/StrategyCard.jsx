import React from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Compass,
  Flag,
  Layers3,
  ShieldAlert,
  Target,
} from "lucide-react";

import {
  ACTIVATION_STATE_LABELS,
  CHECK_STATUS_LABELS,
  DATA_STATUS_LABELS,
  formatPriceZone,
} from "../lib/strategy-flow";


const CHECK_STATUS_CLASS_MAP = {
  met: "bg-emerald-50 text-emerald-700 border-emerald-100",
  not_met: "bg-amber-50 text-amber-700 border-amber-100",
  blocked: "bg-red-50 text-red-700 border-red-100",
  not_evaluated: "bg-gray-50 text-gray-600 border-gray-200",
};

const ACTIVATION_CLASS_MAP = {
  live: "bg-indigo-50 text-indigo-700 border-indigo-100",
  education_only: "bg-sky-50 text-sky-700 border-sky-100",
  blocked_by_data: "bg-amber-50 text-amber-700 border-amber-100",
  deferred: "bg-gray-50 text-gray-700 border-gray-200",
};

function CheckGroup({ title, items }) {
  if (!items || items.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-bold uppercase tracking-[0.18em] text-gray-400">{title}</div>
      <div className="space-y-2">
        {items.map((check) => (
          <div key={check.check_id} className="rounded-2xl border border-gray-100 bg-white px-3 py-3">
            <div className="flex flex-wrap items-center gap-2 mb-1.5">
              <span className="text-sm font-semibold text-gray-900">{check.label}</span>
              <span
                className={`text-[11px] font-bold px-2 py-1 rounded-full border ${
                  CHECK_STATUS_CLASS_MAP[check.status] ?? CHECK_STATUS_CLASS_MAP.not_evaluated
                }`}
              >
                {CHECK_STATUS_LABELS[check.status] ?? check.status}
              </span>
            </div>
            <div className="text-sm text-gray-600 leading-relaxed">{check.detail}</div>
            {check.value && <div className="text-xs text-gray-400 mt-1.5">기준값: {check.value}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function InfoPanel({ icon: Icon, title, body, subtle }) {
  return (
    <div className={`rounded-[1.25rem] border p-4 ${subtle ? "bg-white border-gray-100" : "bg-gray-50 border-gray-100"}`}>
      <div className="flex items-center gap-2 text-sm font-bold text-gray-900 mb-2">
        <Icon className="w-4 h-4 text-indigo-600" />
        {title}
      </div>
      <div className="text-sm text-gray-600 leading-relaxed whitespace-pre-line">{body}</div>
    </div>
  );
}

export default function StrategyCard({ definition, evaluation, onCreatePlan }) {
  const checkGroups = evaluation
    ? [
        { title: "조건", items: evaluation.conditions },
        { title: "필터", items: evaluation.filters },
        { title: "가드레일", items: evaluation.guardrails },
      ]
    : [];

  const activationState = evaluation?.activation_state ?? definition.activation_state;
  const activationLabel = ACTIVATION_STATE_LABELS[activationState] ?? activationState;
  const activationClass = ACTIVATION_CLASS_MAP[activationState] ?? ACTIVATION_CLASS_MAP.deferred;
  const dataStatusLabel = evaluation ? DATA_STATUS_LABELS[evaluation.data_status] ?? evaluation.data_status : null;
  const statusReason = evaluation ? evaluation.why_this_plan : definition.activation_reason;

  return (
    <article className="bg-white rounded-[1.75rem] border border-gray-100 shadow-sm hover:shadow-md transition overflow-hidden">
      <div className="p-6 md:p-7 space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${activationClass}`}>
                {activationLabel}
              </span>
              {dataStatusLabel && (
                <span className="text-xs font-bold px-2.5 py-1 rounded-full border bg-gray-50 text-gray-600 border-gray-200">
                  {dataStatusLabel}
                </span>
              )}
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-900">{definition.name}</h3>
              <p className="text-sm text-gray-500 mt-2 leading-relaxed">{definition.summary}</p>
            </div>
          </div>

          {evaluation && (
            <div className="rounded-[1.25rem] border border-indigo-100 bg-indigo-50 px-4 py-3 min-w-[220px]">
              <div className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-500 mb-1">
                평가 기준
              </div>
              <div className="text-sm font-semibold text-indigo-900">{evaluation.symbol.symbol_name}</div>
              <div className="text-xs text-indigo-700 mt-1">
                {evaluation.symbol.symbol_code} · {evaluation.timeframe}
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="rounded-[1.25rem] border border-emerald-100 bg-emerald-50 px-4 py-4">
            <div className="text-sm font-bold text-emerald-900 mb-2">이럴 때 살펴봐요</div>
            <div className="text-sm text-emerald-800 leading-relaxed">{definition.when_to_use}</div>
          </div>
          <div className="rounded-[1.25rem] border border-red-100 bg-red-50 px-4 py-4">
            <div className="text-sm font-bold text-red-900 mb-2">이럴 때는 보수적으로 봐요</div>
            <div className="text-sm text-red-800 leading-relaxed">{definition.when_not_to_use}</div>
          </div>
        </div>

        <section className="space-y-4">
          <div className="flex items-center gap-2 text-base font-bold text-gray-900">
            <Layers3 className="w-4 h-4 text-indigo-600" />
            현재 조건 확인
          </div>
          {evaluation ? (
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              {checkGroups.map((group) => (
                <CheckGroup key={group.title} title={group.title} items={group.items} />
              ))}
            </div>
          ) : (
            <div className="rounded-[1.25rem] border border-dashed border-gray-200 bg-gray-50 px-4 py-4 text-sm text-gray-600 leading-relaxed">
              이 카드는 현재 V1 일봉 평가 대상이 아니에요. 활성화 상태와 준비 사유만 안내합니다.
            </div>
          )}
        </section>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <InfoPanel
            icon={Target}
            title="매수 구역"
            body={evaluation ? formatPriceZone(evaluation.buy_zone) : "현재 V1에서는 숫자 매수 구역을 제공하지 않습니다."}
          />
          <InfoPanel
            icon={ShieldAlert}
            title="무효화 규칙"
            body={evaluation ? evaluation.stop_invalidation_rule.rule_text : "현재 V1에서는 무효화 규칙을 평가하지 않습니다."}
          />
          <InfoPanel
            icon={Flag}
            title="목표 재검토 구역"
            body={evaluation ? formatPriceZone(evaluation.target_review_zone) : "현재 V1에서는 목표 재검토 구역을 제공하지 않습니다."}
          />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <InfoPanel
            icon={Compass}
            title="첫 비중 가이드"
            body={evaluation ? evaluation.first_position_rule : "현재 V1에서는 첫 비중 가이드를 제공하지 않습니다."}
            subtle
          />
          <InfoPanel
            icon={CheckCircle2}
            title="보유 프로필"
            body={evaluation ? evaluation.holding_profile : definition.holding_profile}
            subtle
          />
          <InfoPanel
            icon={AlertTriangle}
            title={evaluation ? "현재 판단 근거" : "현재 상태"}
            body={statusReason}
            subtle
          />
        </div>

        <div className="rounded-[1.25rem] border border-gray-100 bg-gray-50 px-4 py-4">
          <div className="text-xs font-bold uppercase tracking-[0.18em] text-gray-400 mb-2">안내 문구</div>
          <div className="text-sm text-gray-600 leading-relaxed">{definition.disclaimer}</div>
        </div>
      </div>

      {evaluation && onCreatePlan && (
        <div className="border-t border-gray-100 bg-white px-6 py-4">
          <button
            type="button"
            onClick={onCreatePlan}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700 transition"
          >
            이 전략으로 계획 만들기
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </article>
  );
}
