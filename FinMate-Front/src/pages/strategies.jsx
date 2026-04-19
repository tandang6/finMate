import React, { useDeferredValue, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ClipboardList,
  Database,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
} from "lucide-react";

import StrategyCard from "../components/StrategyCard";
import {
  DATA_STATUS_LABELS,
  STRATEGY_API_BASE,
  SUPPORTED_SYMBOLS,
  fetchJson,
  formatDateTime,
  savePlannerSelection,
} from "../lib/strategy-flow";


function SectionShell({ title, description, children, emptyText }) {
  return (
    <section className="space-y-4">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">{title}</h2>
          <p className="text-sm text-gray-500 mt-1">{description}</p>
        </div>
      </div>
      {children && children.length > 0 ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">{children}</div>
      ) : (
        <div className="rounded-[1.5rem] border border-dashed border-gray-200 bg-white px-5 py-6 text-sm text-gray-500">
          {emptyText}
        </div>
      )}
    </section>
  );
}

export default function StrategiesPage() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [catalogReloadKey, setCatalogReloadKey] = useState(0);
  const [selectedSymbolCode, setSelectedSymbolCode] = useState(SUPPORTED_SYMBOLS[0].symbol_code);
  const [symbolQuery, setSymbolQuery] = useState("");
  const deferredSymbolQuery = useDeferredValue(symbolQuery);
  const [evaluationResponse, setEvaluationResponse] = useState(null);
  const [evaluationLoading, setEvaluationLoading] = useState(true);
  const [evaluationError, setEvaluationError] = useState("");
  const [evaluationReloadKey, setEvaluationReloadKey] = useState(0);

  const visibleSymbols = useMemo(() => {
    const keyword = deferredSymbolQuery.trim().toLowerCase();
    if (!keyword) {
      return SUPPORTED_SYMBOLS;
    }
    return SUPPORTED_SYMBOLS.filter((symbol) =>
      [symbol.symbol_name, symbol.symbol_code, symbol.sector]
        .join(" ")
        .toLowerCase()
        .includes(keyword)
    );
  }, [deferredSymbolQuery]);

  const catalogMap = useMemo(() => {
    if (!catalog) {
      return {};
    }
    return Object.fromEntries(catalog.strategies.map((strategy) => [strategy.strategy_id, strategy]));
  }, [catalog]);

  useEffect(() => {
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
  }, [catalogReloadKey]);

  useEffect(() => {
    let cancelled = false;

    async function evaluateSelectedSymbol() {
      try {
        setEvaluationLoading(true);
        setEvaluationError("");
        const data = await fetchJson(`${STRATEGY_API_BASE}/evaluate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol: selectedSymbolCode }),
        });
        if (!cancelled) {
          setEvaluationResponse(data);
        }
      } catch (error) {
        if (!cancelled) {
          setEvaluationError(error.message);
        }
      } finally {
        if (!cancelled) {
          setEvaluationLoading(false);
        }
      }
    }

    evaluateSelectedSymbol();
    return () => {
      cancelled = true;
    };
  }, [evaluationReloadKey, selectedSymbolCode]);

  const liveSections = useMemo(() => {
    if (!evaluationResponse) {
      return {};
    }

    return Object.fromEntries(
      evaluationResponse.live_evaluation_groups.map((group) => [
        group.bucket_id,
        group.evaluations
          .map((evaluation) => ({
            evaluation,
            definition: catalogMap[evaluation.strategy_id],
          }))
          .filter((card) => Boolean(card.definition)),
      ])
    );
  }, [catalogMap, evaluationResponse]);

  const educationCards = useMemo(() => {
    if (evaluationResponse?.non_live_catalog_groups) {
      const group = evaluationResponse.non_live_catalog_groups.find(
        (item) => item.activation_state === "education_only"
      );
      return group?.strategies ?? [];
    }
    return catalog?.strategies.filter((strategy) => strategy.activation_state === "education_only") ?? [];
  }, [catalog, evaluationResponse]);

  const pendingCards = useMemo(() => {
    if (evaluationResponse?.non_live_catalog_groups) {
      return evaluationResponse.non_live_catalog_groups
        .filter(
          (item) => item.activation_state === "deferred" || item.activation_state === "blocked_by_data"
        )
        .flatMap((item) => item.strategies);
    }
    return (
      catalog?.strategies.filter(
        (strategy) =>
          strategy.activation_state === "deferred" || strategy.activation_state === "blocked_by_data"
      ) ?? []
    );
  }, [catalog, evaluationResponse]);

  const handleCreatePlan = (evaluation) => {
    const plannerSelection = {
      evaluation_snapshot: evaluation,
    };
    savePlannerSelection(plannerSelection);
    navigate("/planner", { state: { plannerSelection } });
  };

  const sourceName = evaluationResponse?.source?.provider_id === "mock"
    ? "Slice 1 데모 데이터"
    : evaluationResponse?.source?.provider_name;

  const sourceMeta = evaluationResponse?.source?.provider_id === "mock"
    ? "고정 fixture · 규칙 테스트용"
    : evaluationResponse?.source
      ? `${evaluationResponse.source.dataset} · ${evaluationResponse.source.provenance}`
      : "";

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#F8F9FD]">
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <section className="bg-white rounded-[2rem] border border-gray-100 shadow-sm px-6 py-7 md:px-8 md:py-8">
          <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-6">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-xs font-semibold text-indigo-700 mb-4">
                <Sparkles className="w-4 h-4" />
                전략 탐색
              </div>
              <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-3">지원 종목의 일봉 조건을 전략별로 정리해요</h1>
              <p className="text-sm md:text-base text-gray-500 leading-relaxed">
                이 화면은 완성형 투자 추천 서비스가 아니라, 지원되는 한국 종목의 일봉 조건을 규칙 기반으로 점검하는 전략 계획 프로토타입입니다.
                추천 순위는 제공하지 않고, 선택한 평가 스냅샷만 계획 검토 화면으로 넘깁니다.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                to="/my-plans"
                className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm font-semibold text-gray-600 hover:text-indigo-600"
              >
                <ClipboardList className="w-4 h-4" />
                저장된 계획 보기
              </Link>
              <button
                type="button"
                onClick={() => setEvaluationReloadKey((current) => current + 1)}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-bold text-white hover:bg-indigo-700"
              >
                <RefreshCw className="w-4 h-4" />
                현재 종목 다시 평가
              </button>
            </div>
          </div>
        </section>

        <section className="bg-white rounded-[1.75rem] border border-gray-100 shadow-sm px-5 py-5 md:px-6 md:py-6">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-5 mb-5">
            <div>
              <h2 className="text-lg font-bold text-gray-900 mb-2">지원 종목 선택</h2>
            </div>
            <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 min-w-[280px]">
              <Search className="w-4 h-4 text-gray-400" />
              <input
                value={symbolQuery}
                onChange={(event) => setSymbolQuery(event.target.value)}
                placeholder="종목명이나 코드로 찾기"
                className="w-full bg-transparent outline-none text-sm text-gray-700 placeholder:text-gray-400"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {visibleSymbols.map((symbol) => {
              const isActive = symbol.symbol_code === selectedSymbolCode;
              return (
                <button
                  key={symbol.symbol_code}
                  type="button"
                  onClick={() => setSelectedSymbolCode(symbol.symbol_code)}
                  className={`text-left rounded-[1.25rem] border px-4 py-4 transition ${
                    isActive
                      ? "border-indigo-600 bg-indigo-600 text-white shadow-md shadow-indigo-100"
                      : "border-gray-100 bg-gray-50 hover:bg-white hover:border-indigo-200 text-gray-700"
                  }`}
                >
                  <div className="text-base font-bold">{symbol.symbol_name}</div>
                  <div className={`text-sm mt-1 ${isActive ? "text-indigo-100" : "text-gray-400"}`}>
                    {symbol.symbol_code} · {symbol.sector}
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        {(catalogLoading || evaluationLoading) && (
          <div className="bg-white rounded-[1.75rem] border border-gray-100 shadow-sm px-6 py-10 flex items-center justify-center text-gray-500">
            <Loader2 className="w-5 h-5 animate-spin mr-3" />
            전략 평가 화면을 준비하는 중입니다.
          </div>
        )}

        {(catalogError || evaluationError) && (
          <div className="bg-white rounded-[1.75rem] border border-red-100 shadow-sm px-6 py-6">
            <div className="text-sm text-red-600 mb-3">{catalogError || evaluationError}</div>
            <button
              type="button"
              onClick={() => {
                setCatalogReloadKey((current) => current + 1);
                setEvaluationReloadKey((current) => current + 1);
              }}
              className="inline-flex items-center gap-2 rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white"
            >
              <RefreshCw className="w-4 h-4" />
              다시 시도
            </button>
          </div>
        )}

        {!catalogLoading && !evaluationLoading && !catalogError && !evaluationError && evaluationResponse && (
          <>
            <section className="bg-white rounded-[1.75rem] border border-gray-100 shadow-sm px-5 py-5 md:px-6 md:py-6">
              <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
                <div className="rounded-[1.25rem] border border-gray-100 bg-gray-50 px-4 py-4">
                  <div className="text-xs font-bold uppercase tracking-[0.18em] text-gray-400 mb-2">기준 종목</div>
                  <div className="text-lg font-bold text-gray-900">{evaluationResponse.symbol.symbol_name}</div>
                  <div className="text-sm text-gray-500 mt-1">{evaluationResponse.symbol.symbol_code} · {evaluationResponse.timeframe}</div>
                </div>
                <div className="rounded-[1.25rem] border border-gray-100 bg-gray-50 px-4 py-4">
                  <div className="text-xs font-bold uppercase tracking-[0.18em] text-gray-400 mb-2">데이터 상태</div>
                  <div className="text-lg font-bold text-gray-900">
                    {DATA_STATUS_LABELS[evaluationResponse.data_status] ?? evaluationResponse.data_status}
                  </div>
                  <div className="text-sm text-gray-500 mt-1">stale / partial / unavailable은 데이터 부족으로 표시돼요.</div>
                </div>
                <div className="rounded-[1.25rem] border border-gray-100 bg-gray-50 px-4 py-4">
                  <div className="text-xs font-bold uppercase tracking-[0.18em] text-gray-400 mb-2">데이터 출처</div>
                  <div className="text-lg font-bold text-gray-900">{sourceName}</div>
                  <div className="text-sm text-gray-500 mt-1">
                    {sourceMeta}
                  </div>
                </div>
                <div className="rounded-[1.25rem] border border-gray-100 bg-gray-50 px-4 py-4">
                  <div className="text-xs font-bold uppercase tracking-[0.18em] text-gray-400 mb-2">평가 시각</div>
                  <div className="text-lg font-bold text-gray-900">{formatDateTime(evaluationResponse.evaluated_at)}</div>
                  <div className="text-sm text-gray-500 mt-1">catalog 버전 {evaluationResponse.catalog_version}</div>
                </div>
              </div>
            </section>

            <div className="space-y-10">
              <SectionShell
                title="적용 가능"
                description="현재 일봉 조건상 규칙과 구역을 바로 검토할 수 있는 카드입니다."
                emptyText="이번 평가에서는 적용 가능 카드가 없어요."
              >
                {(liveSections.applicable ?? []).map(({ definition, evaluation }) => (
                  <StrategyCard
                    key={evaluation.strategy_id}
                    definition={definition}
                    evaluation={evaluation}
                    onCreatePlan={() => handleCreatePlan(evaluation)}
                  />
                ))}
              </SectionShell>

              <SectionShell
                title="지금은 조건 부족"
                description="전략 자체는 live지만, 오늘 기준으로 조건이 아직 덜 갖춰진 카드입니다."
                emptyText="이번 평가에서는 조건 부족 카드가 없어요."
              >
                {(liveSections.conditions_insufficient ?? []).map(({ definition, evaluation }) => (
                  <StrategyCard
                    key={evaluation.strategy_id}
                    definition={definition}
                    evaluation={evaluation}
                    onCreatePlan={() => handleCreatePlan(evaluation)}
                  />
                ))}
              </SectionShell>

              <SectionShell
                title="데이터 부족"
                description="데이터 freshness나 coverage가 충분하지 않아 평가를 보수적으로 막아 둔 카드입니다."
                emptyText="이번 평가에서는 데이터 부족 카드가 없어요."
              >
                {(liveSections.data_unavailable ?? []).map(({ definition, evaluation }) => (
                  <StrategyCard
                    key={evaluation.strategy_id}
                    definition={definition}
                    evaluation={evaluation}
                    onCreatePlan={() => handleCreatePlan(evaluation)}
                  />
                ))}
              </SectionShell>

              <SectionShell
                title="교육용"
                description="전략 개념은 볼 수 있지만, 현재 V1에서는 live 평가를 제공하지 않는 카드입니다."
                emptyText="교육용 전략 카드가 없습니다."
              >
                {educationCards.map((definition) => (
                  <StrategyCard key={definition.strategy_id} definition={definition} />
                ))}
              </SectionShell>

              <SectionShell
                title="보류"
                description="데이터 또는 구현 범위가 아직 준비되지 않아 catalog 수준으로만 제공하는 카드입니다."
                emptyText="보류 전략 카드가 없습니다."
              >
                {pendingCards.map((definition) => (
                  <StrategyCard key={definition.strategy_id} definition={definition} />
                ))}
              </SectionShell>
            </div>
          </>
        )}

        <section className="bg-white rounded-[1.75rem] border border-gray-100 shadow-sm px-5 py-5 md:px-6 md:py-6">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center shrink-0">
              <Database className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <div className="text-base font-bold text-gray-900 mb-2">안내</div>
              <div className="text-sm text-gray-600 leading-relaxed">
                이 화면은 추천 순위나 “지금 가장 좋은 전략”을 제공하지 않습니다. 현재 종목의 일봉 조건을 전략별로 나눠 보여주고,
                사용자가 하나의 평가 스냅샷을 선택해 계획 검토 화면으로 넘기도록 만든 규칙 기반 프로토타입입니다.
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
