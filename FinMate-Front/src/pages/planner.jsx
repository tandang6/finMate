import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  CheckSquare,
  ChevronLeft,
  ClipboardList,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  XCircle,
} from "lucide-react";


const API_BASE = "http://localhost:8000/api/planner";
const USER_ID_KEY = "finmate-user-id";
const DRAFT_KEY = "finmate-planner-draft";
const HOLDING_PERIOD_OPTIONS = ["1주", "2주", "1개월", "3개월", "6개월", "1년", "기타"];
const DISCLAIMER_TEXT =
  "* 본 서비스에서 제공하는 전략 및 정보는 투자 권유가 아니며, 일반적인 교육 목적의 참고 자료입니다. 모든 투자 판단과 그에 따른 손익의 책임은 이용자 본인에게 있습니다. 예시 전략은 미래 성과를 보장하지 않습니다.";

const DEMO_STOCKS = [
  { name: "삼성전자", code: "005930", sector: "반도체", price: "82,400원" },
  { name: "SK하이닉스", code: "000660", sector: "반도체", price: "198,500원" },
  { name: "NAVER", code: "035420", sector: "플랫폼", price: "191,700원" },
  { name: "카카오", code: "035720", sector: "플랫폼", price: "42,800원" },
  { name: "현대차", code: "005380", sector: "자동차", price: "241,000원" },
  { name: "LG에너지솔루션", code: "373220", sector: "배터리", price: "356,000원" },
];

const STEP_LABELS = [
  "종목 선택",
  "전략 탐색",
  "전략 상세",
  "계획 입력",
  "저장 완료",
];

const STYLE_MAP = {
  technical: {
    label: "기술적",
    badge: "bg-indigo-50 text-indigo-700 border-indigo-100",
    accent: "text-indigo-600",
  },
  fundamental: {
    label: "펀더멘털",
    badge: "bg-emerald-50 text-emerald-700 border-emerald-100",
    accent: "text-emerald-600",
  },
  hybrid: {
    label: "하이브리드",
    badge: "bg-amber-50 text-amber-700 border-amber-100",
    accent: "text-amber-600",
  },
};

const STYLE_FILTERS = [
  { id: "all", label: "전체" },
  { id: "beginner", label: "초보 우선" },
  { id: "technical", label: "기술적" },
  { id: "fundamental", label: "펀더멘털" },
  { id: "hybrid", label: "하이브리드" },
];

const INITIAL_FORM = {
  entry_price: "",
  stop_loss_price: "",
  target_price: "",
  position_size_pct: "",
  holding_period: HOLDING_PERIOD_OPTIONS[2],
  one_line_reason: "",
  note: "",
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


function getHeaders() {
  return {
    "Content-Type": "application/json",
    "X-User-Id": getPlannerUserId(),
  };
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


function parseNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}


function calcRiskReward(entryPrice, stopLossPrice, targetPrice) {
  if (!entryPrice || !stopLossPrice || !targetPrice || entryPrice <= 0) {
    return null;
  }
  if (!(stopLossPrice < entryPrice && entryPrice < targetPrice)) {
    return null;
  }

  const riskPct = ((entryPrice - stopLossPrice) / entryPrice) * 100;
  const rewardPct = ((targetPrice - entryPrice) / entryPrice) * 100;
  const ratio = riskPct > 0 ? rewardPct / riskPct : null;

  return { riskPct, rewardPct, ratio };
}


function filterAndSortTemplates(templates, styleFilter) {
  let filtered = templates;
  if (styleFilter === "beginner") {
    filtered = [...templates].sort(
      (a, b) => (a.beginner_priority ?? 99) - (b.beginner_priority ?? 99)
    );
  } else if (styleFilter !== "all") {
    filtered = templates.filter((t) => t.style === styleFilter);
  }
  return filtered;
}


function PlannerHeader({ step }) {
  return (
    <div className="flex flex-col gap-6 mb-8">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-xs font-semibold text-indigo-700 mb-3">
            <ClipboardList className="w-4 h-4" />
            첫 매수 플래너
          </div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2">전략 카드 기반 첫 매수 플랜</h1>
          <p className="text-sm md:text-base text-gray-500 max-w-3xl">
            종목과 전략을 먼저 정한 뒤, 내 기준의 손절가와 목표가, 비중, 보유 기간을 구체적인 계획으로 남겨보세요.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-2 self-stretch lg:self-auto">
          <Link
            to="/my-plans"
            className="inline-flex items-center justify-center gap-1 whitespace-nowrap text-sm font-medium text-indigo-600 hover:text-indigo-700 px-3 py-2 rounded-full bg-white border border-indigo-100 shadow-sm"
          >
            <ClipboardList className="w-4 h-4" />
            내 계획 보기
          </Link>
          <Link
            to="/"
            className="inline-flex items-center justify-center gap-1 whitespace-nowrap text-sm font-medium text-gray-500 hover:text-indigo-600 px-3 py-2 rounded-full hover:bg-white border border-transparent hover:border-indigo-100 shadow-sm"
          >
            <ChevronLeft className="w-4 h-4" />
            대시보드로 돌아가기
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {STEP_LABELS.map((label, index) => {
          const current = index + 1;
          const isActive = current === step;
          const isDone = current < step;
          return (
            <div
              key={label}
              className={`rounded-2xl border px-4 py-3 transition ${
                isActive
                  ? "bg-indigo-600 text-white border-indigo-600 shadow-lg shadow-indigo-100"
                  : isDone
                    ? "bg-indigo-50 text-indigo-700 border-indigo-100"
                    : "bg-white text-gray-400 border-gray-100"
              }`}
            >
              <div className="text-xs font-semibold mb-1">STEP {current}</div>
              <div className="text-sm font-bold">{label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


function StyleFilterTabs({ activeFilter, onChange, templateCounts }) {
  return (
    <div className="flex flex-wrap gap-2">
      {STYLE_FILTERS.map((filter) => {
        const count = filter.id === "all"
          ? templateCounts.total
          : filter.id === "beginner"
            ? templateCounts.total
            : templateCounts[filter.id] ?? 0;
        return (
          <button
            key={filter.id}
            type="button"
            onClick={() => onChange(filter.id)}
            className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-semibold transition ${
              activeFilter === filter.id
                ? "bg-indigo-600 text-white shadow-md shadow-indigo-100"
                : "bg-white text-gray-500 border border-gray-200 hover:text-indigo-600"
            }`}
          >
            {filter.id === "beginner" && <Filter className="w-3.5 h-3.5" />}
            {filter.label}
            <span className={`text-xs ${activeFilter === filter.id ? "text-indigo-200" : "text-gray-400"}`}>
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}


function StrategyCardCompact({ template, onClick }) {
  const style = STYLE_MAP[template.style] ?? STYLE_MAP.technical;
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-left bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-5 hover:-translate-y-1 hover:shadow-md transition flex flex-col"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${style.badge}`}>
          {style.label}
        </span>
        {template.beginner_priority != null && template.beginner_priority <= 3 && (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-yellow-50 text-yellow-700 border border-yellow-100">
            초보 추천
          </span>
        )}
      </div>
      <div className="text-base font-bold text-gray-900 mb-1.5">{template.name}</div>
      <div className="text-sm text-gray-600 leading-relaxed mb-3 line-clamp-3">
        {template.one_line_summary || template.summary}
      </div>
      {template.when_it_fits_beginner && (
        <div className="flex items-start gap-1.5 text-xs text-emerald-700 bg-emerald-50 rounded-lg px-2.5 py-1.5 mb-2">
          <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span className="line-clamp-2">{template.when_it_fits_beginner}</span>
        </div>
      )}
      {template.when_it_does_not_fit_beginner && (
        <div className="flex items-start gap-1.5 text-xs text-red-600 bg-red-50 rounded-lg px-2.5 py-1.5 mb-2">
          <XCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span className="line-clamp-2">{template.when_it_does_not_fit_beginner}</span>
        </div>
      )}
      <div className="mt-auto pt-3 flex items-center justify-between">
        <span className="text-xs text-gray-400">{template.holding_period}</span>
        <span className={`text-sm font-semibold ${style.accent}`}>자세히 보기 →</span>
      </div>
    </button>
  );
}


export default function FirstPurchasePlanner() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStock, setSelectedStock] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templatesError, setTemplatesError] = useState("");
  const [templatesLoadedOnce, setTemplatesLoadedOnce] = useState(false);
  const [styleFilter, setStyleFilter] = useState("beginner");
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [strategyDetail, setStrategyDetail] = useState(null);
  const [strategyLoading, setStrategyLoading] = useState(false);
  const [strategyError, setStrategyError] = useState("");
  const [form, setForm] = useState(INITIAL_FORM);
  const [draftRestoredFor, setDraftRestoredFor] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveLoading, setSaveLoading] = useState(false);
  const [savedPlan, setSavedPlan] = useState(null);

  const filteredStocks = useMemo(() => {
    const keyword = searchQuery.trim().toLowerCase();
    if (!keyword) {
      return DEMO_STOCKS;
    }
    return DEMO_STOCKS.filter((stock) =>
      [stock.name, stock.code, stock.sector].some((value) => value.toLowerCase().includes(keyword))
    );
  }, [searchQuery]);

  const templateCounts = useMemo(() => {
    const counts = { total: templates.length, technical: 0, fundamental: 0, hybrid: 0 };
    for (const t of templates) {
      if (counts[t.style] !== undefined) {
        counts[t.style]++;
      }
    }
    return counts;
  }, [templates]);

  const displayedTemplates = useMemo(
    () => filterAndSortTemplates(templates, styleFilter),
    [templates, styleFilter]
  );

  const normalizedDraftKey = selectedStock && selectedStrategy
    ? `${selectedStock.name}::${selectedStrategy.id}`
    : "";

  const riskReward = useMemo(() => {
    const entryPrice = parseNumber(form.entry_price);
    const stopLossPrice = parseNumber(form.stop_loss_price);
    const targetPrice = parseNumber(form.target_price);
    return calcRiskReward(entryPrice, stopLossPrice, targetPrice);
  }, [form.entry_price, form.stop_loss_price, form.target_price]);

  const validation = useMemo(() => {
    const messages = [];
    const warnings = [];
    const hints = [];
    const entryPrice = parseNumber(form.entry_price);
    const stopLossPrice = parseNumber(form.stop_loss_price);
    const targetPrice = parseNumber(form.target_price);
    const positionSize = parseNumber(form.position_size_pct);

    if (entryPrice && stopLossPrice && targetPrice && !(stopLossPrice < entryPrice && entryPrice < targetPrice)) {
      messages.push("손절가는 매수 희망가보다 낮아야 하고, 목표가는 매수 희망가보다 높아야 해요.");
    }

    if (positionSize && positionSize > 30) {
      warnings.push("한 종목에 이 비중은 위험할 수 있어요.");
    }

    if (form.one_line_reason.trim() && form.one_line_reason.trim().length < 10) {
      hints.push("매수 이유를 조금 더 구체적으로 적어보세요.");
    }

    if (riskReward?.ratio !== null && riskReward?.ratio <= 1) {
      warnings.push("손익비가 낮습니다. 목표가와 손절가를 다시 확인해보세요.");
    }

    return { messages, warnings, hints };
  }, [form, riskReward]);

  useEffect(() => {
    if (step < 1 || templates.length > 0 || templatesLoadedOnce) {
      return;
    }

    let cancelled = false;
    setTemplatesLoading(true);
    setTemplatesError("");

    const loadTemplates = async () => {
      try {
        const data = await fetchJson(`${API_BASE}/templates`);
        if (!cancelled) {
          setTemplates(data);
          setTemplatesLoadedOnce(true);
        }
      } catch (error) {
        if (!cancelled) {
          setTemplatesError(error.message);
          setTemplatesLoadedOnce(true);
        }
      } finally {
        if (!cancelled) {
          setTemplatesLoading(false);
        }
      }
    };

    loadTemplates();
    return () => {
      cancelled = true;
    };
  }, [step, templates.length, templatesLoadedOnce]);

  useEffect(() => {
    if (step !== 4 || !normalizedDraftKey || draftRestoredFor === normalizedDraftKey) {
      return;
    }

    const raw = window.sessionStorage.getItem(DRAFT_KEY);
    if (!raw) {
      setDraftRestoredFor(normalizedDraftKey);
      return;
    }

    try {
      const draft = JSON.parse(raw);
      if (draft.stockName === selectedStock.name && draft.strategyId === selectedStrategy.id) {
        setForm((current) => ({ ...current, ...draft.form }));
      }
    } catch (error) {
      window.sessionStorage.removeItem(DRAFT_KEY);
    } finally {
      setDraftRestoredFor(normalizedDraftKey);
    }
  }, [draftRestoredFor, normalizedDraftKey, selectedStock, selectedStrategy, step]);

  useEffect(() => {
    if (step !== 4 || !normalizedDraftKey) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      const payload = {
        stockName: selectedStock.name,
        strategyId: selectedStrategy.id,
        form,
      };
      window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(payload));
    }, 1000);

    return () => window.clearTimeout(timeoutId);
  }, [form, normalizedDraftKey, selectedStock, selectedStrategy, step]);

  const handleSelectStock = (stock) => {
    setSelectedStock(stock);
    setStep(2);
    setSelectedStrategy(null);
    setStrategyDetail(null);
    setForm(INITIAL_FORM);
    setShowConfirm(false);
    setSaveError("");
    setSavedPlan(null);
    setDraftRestoredFor("");
  };

  const handleCustomStockSubmit = () => {
    const customName = searchQuery.trim();
    if (!customName) {
      return;
    }

    handleSelectStock({
      name: customName,
      code: "custom",
      sector: "직접 입력",
      price: "-",
    });
  };

  const loadStrategyDetail = async (templateId) => {
    try {
      setStrategyLoading(true);
      setStrategyError("");
      const detail = await fetchJson(`${API_BASE}/templates/${templateId}`);
      setStrategyDetail(detail);
      setSelectedStrategy(detail);
      setStep(3);
    } catch (error) {
      setStrategyError(error.message);
    } finally {
      setStrategyLoading(false);
    }
  };

  const handleFormChange = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const validateBeforeSubmit = () => {
    const requiredFields = [
      "entry_price",
      "stop_loss_price",
      "target_price",
      "position_size_pct",
      "holding_period",
      "one_line_reason",
    ];

    for (const field of requiredFields) {
      if (!String(form[field] ?? "").trim()) {
        setSaveError("필수 항목을 모두 입력해 주세요.");
        return false;
      }
    }

    if (validation.messages.length > 0) {
      setSaveError(validation.messages[0]);
      return false;
    }

    setSaveError("");
    return true;
  };

  const submitPlan = async (status) => {
    if (!validateBeforeSubmit()) {
      return;
    }

    try {
      setSaveLoading(true);
      setSaveError("");

      const payload = {
        symbol: selectedStock.name,
        strategy_template_id: selectedStrategy.id,
        entry_price: Number(form.entry_price),
        stop_loss_price: Number(form.stop_loss_price),
        target_price: Number(form.target_price),
        position_size_pct: Number(form.position_size_pct),
        holding_period: form.holding_period,
        one_line_reason: form.one_line_reason.trim(),
        note: form.note.trim(),
        status,
      };

      const data = await fetchJson(`${API_BASE}/plans`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify(payload),
      });

      setSavedPlan(data);
      setStep(5);
      setShowConfirm(false);
      window.sessionStorage.removeItem(DRAFT_KEY);
    } catch (error) {
      setSaveError(error.message);
    } finally {
      setSaveLoading(false);
    }
  };

  const handleResetPlanner = () => {
    setStep(1);
    setSearchQuery("");
    setSelectedStock(null);
    setSelectedStrategy(null);
    setStrategyDetail(null);
    setForm(INITIAL_FORM);
    setShowConfirm(false);
    setSaveError("");
    setSavedPlan(null);
    setDraftRestoredFor("");
    window.sessionStorage.removeItem(DRAFT_KEY);
  };

  const isFundamental = selectedStrategy?.style === "fundamental";

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#F8F9FD]">
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <PlannerHeader step={step} />

        {/* ===== STEP 1: Stock Selection ===== */}
        {step === 1 && (
          <section className="space-y-6">
            <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-6 md:p-8">
              <div className="max-w-3xl">
                <h2 className="text-xl font-bold text-gray-900 mb-2">어떤 종목을 매수하고 싶으신가요?</h2>
                <p className="text-sm text-gray-500 mb-6">
                  종목명을 직접 입력하거나, 자주 보는 인기 종목 카드에서 시작할 수 있어요.
                </p>
              </div>

              <div className="bg-gray-50 border border-gray-100 rounded-[1.5rem] p-4 md:p-5 mb-6">
                <div className="flex flex-col md:flex-row gap-3">
                  <div className="flex-1 flex items-center gap-3 bg-white border border-gray-200 rounded-xl px-4 py-3">
                    <Search className="w-4 h-4 text-gray-400" />
                    <input
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      placeholder="종목명을 직접 입력하세요 (예: 삼성전자)"
                      className="w-full bg-transparent outline-none text-sm text-gray-700 placeholder:text-gray-400"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleCustomStockSubmit}
                    className="px-4 py-3 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 transition"
                  >
                    입력한 종목으로 시작
                  </button>
                </div>

                {searchQuery.trim() && filteredStocks.length === 0 && (
                  <div className="mt-3 text-sm text-gray-500">
                    검색 결과가 없어도 <span className="font-semibold text-gray-700">{searchQuery.trim()}</span> 이름으로 직접 계획을 만들 수 있어요.
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-gray-700">인기 종목 카드</h3>
                {searchQuery.trim() && (
                  <span className="text-xs text-gray-400">
                    {filteredStocks.length}개의 결과
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredStocks.map((stock) => (
                  <button
                    key={stock.code}
                    type="button"
                    onClick={() => handleSelectStock(stock)}
                    className="text-left bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-5 hover:-translate-y-1 hover:shadow-md transition"
                  >
                    <div className="flex items-start justify-between gap-3 mb-4">
                      <div>
                        <div className="text-lg font-bold text-gray-900">{stock.name}</div>
                        <div className="text-sm text-gray-400">{stock.code}</div>
                      </div>
                      <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700">
                        {stock.sector}
                      </span>
                    </div>
                    <div className="text-sm text-gray-500 mb-4">참고 가격 {stock.price}</div>
                    <div className="text-sm font-semibold text-indigo-600">이 종목으로 전략 보기</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Strategy preview (browsable even before stock selection) */}
            <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-6 md:p-8">
              <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3 mb-6">
                <div>
                  <h3 className="text-xl font-bold text-gray-900 mb-2">전략 라이브러리 미리 보기</h3>
                  <p className="text-sm text-gray-500">
                    10개의 전략 카드 중 내 상황에 맞는 카드를 탐색해 보세요. 종목을 선택하면 다음 단계에서 바로 비교할 수 있어요.
                  </p>
                </div>
                <div className="text-xs text-gray-400 whitespace-nowrap">
                  {templates.length}개의 전략 카드
                </div>
              </div>

              {templatesLoading && (
                <div className="rounded-[1.5rem] border border-gray-100 bg-gray-50 p-10 flex items-center justify-center text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin mr-3" />
                  전략 카드를 불러오는 중입니다.
                </div>
              )}

              {templatesError && (
                <div className="rounded-[1.5rem] border border-red-100 bg-red-50/40 p-5">
                  <div className="text-sm text-red-600 mb-3">{templatesError}</div>
                  <button
                    type="button"
                    onClick={() => {
                      setTemplates([]);
                      setTemplatesLoadedOnce(false);
                      setTemplatesError("");
                    }}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-900 text-white text-sm font-semibold"
                  >
                    <RefreshCw className="w-4 h-4" />
                    다시 불러오기
                  </button>
                </div>
              )}

              {!templatesLoading && !templatesError && templates.length > 0 && (
                <>
                  <div className="mb-5">
                    <StyleFilterTabs
                      activeFilter={styleFilter}
                      onChange={setStyleFilter}
                      templateCounts={templateCounts}
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {displayedTemplates.map((template) => {
                      const style = STYLE_MAP[template.style] ?? STYLE_MAP.technical;
                      return (
                        <div
                          key={template.id}
                          className="bg-gray-50 rounded-[1.5rem] border border-gray-100 p-5"
                        >
                          <div className="flex items-start justify-between gap-3 mb-3">
                            <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${style.badge}`}>
                              {style.label}
                            </span>
                            {template.beginner_priority != null && template.beginner_priority <= 3 && (
                              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-yellow-50 text-yellow-700 border border-yellow-100">
                                초보 추천
                              </span>
                            )}
                          </div>
                          <div className="text-base font-bold text-gray-900 mb-1.5">{template.name}</div>
                          <div className="text-sm text-gray-600 leading-relaxed mb-2 line-clamp-3">
                            {template.one_line_summary || template.summary}
                          </div>
                          <div className="text-xs text-gray-400">{template.holding_period}</div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          </section>
        )}

        {/* ===== STEP 2: Strategy Browse & Select ===== */}
        {step === 2 && (
          <section className="space-y-6">
            <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="text-xs font-semibold text-gray-400 mb-1">종목 선택 &gt; 전략 탐색</div>
                <div className="text-lg font-bold text-gray-900">{selectedStock?.name}</div>
                <div className="text-sm text-gray-500">
                  {selectedStock?.sector} · 참고 가격 {selectedStock?.price}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setStep(1)}
                className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-indigo-600"
              >
                <ChevronLeft className="w-4 h-4" />
                종목 다시 고르기
              </button>
            </div>

            {templatesLoading && (
              <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-10 flex items-center justify-center text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-3" />
                전략 카드를 불러오는 중입니다.
              </div>
            )}

            {templatesError && (
              <div className="bg-white rounded-[1.5rem] border border-red-100 shadow-sm p-6">
                <div className="text-sm text-red-600 mb-3">{templatesError}</div>
                <button
                  type="button"
                  onClick={() => {
                    setTemplates([]);
                    setTemplatesLoadedOnce(false);
                    setTemplatesError("");
                    setStep(1);
                    setStep(2);
                  }}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-900 text-white text-sm font-semibold"
                >
                  <RefreshCw className="w-4 h-4" />
                  다시 시도
                </button>
              </div>
            )}

            {!templatesLoading && !templatesError && (
              <>
                <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm px-5 py-4">
                  <StyleFilterTabs
                    activeFilter={styleFilter}
                    onChange={setStyleFilter}
                    templateCounts={templateCounts}
                  />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                  {displayedTemplates.map((template) => (
                    <StrategyCardCompact
                      key={template.id}
                      template={template}
                      onClick={() => loadStrategyDetail(template.id)}
                    />
                  ))}
                </div>
                {displayedTemplates.length === 0 && (
                  <div className="text-center text-sm text-gray-400 py-8">
                    이 필터에 해당하는 전략 카드가 없습니다.
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {/* ===== STEP 3: Strategy Detail ===== */}
        {step === 3 && (
          <section className="space-y-6">
            <div className="flex items-center justify-between gap-4">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-indigo-600"
              >
                <ChevronLeft className="w-4 h-4" />
                전략 목록으로 돌아가기
              </button>
              {selectedStock && (
                <div className="text-sm text-gray-500">{selectedStock.name} 기준 전략 검토 중</div>
              )}
            </div>

            {strategyLoading && (
              <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-10 flex items-center justify-center text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin mr-3" />
                전략 상세를 불러오는 중입니다.
              </div>
            )}

            {strategyError && (
              <div className="bg-white rounded-[1.5rem] border border-red-100 shadow-sm p-6 text-red-600">
                {strategyError}
              </div>
            )}

            {!strategyLoading && strategyDetail && (
              <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-6 md:p-8">
                {/* Header */}
                <div className="mb-6">
                  <div className="flex items-center gap-3 mb-4">
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${STYLE_MAP[strategyDetail.style]?.badge ?? STYLE_MAP.technical.badge}`}>
                      {STYLE_MAP[strategyDetail.style]?.label ?? "전략"}
                    </span>
                    {strategyDetail.evidence_quality && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 border border-gray-200">
                        근거 수준: {strategyDetail.evidence_quality}
                      </span>
                    )}
                  </div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">{strategyDetail.name}</h2>
                  <p className="text-gray-600 leading-relaxed max-w-3xl">
                    {strategyDetail.one_line_summary || strategyDetail.summary}
                  </p>
                </div>

                {/* When it fits / doesn't fit */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                  {(strategyDetail.when_it_fits_beginner || strategyDetail.when_it_fits) && (
                    <div className="bg-emerald-50 border border-emerald-100 rounded-[1.25rem] p-5">
                      <div className="flex items-center gap-2 text-sm font-bold text-emerald-800 mb-2">
                        <CheckCircle2 className="w-4 h-4" />
                        이런 상황에 적합해요
                      </div>
                      <div className="text-sm text-emerald-700 leading-relaxed">
                        {strategyDetail.when_it_fits_beginner || strategyDetail.when_it_fits}
                      </div>
                    </div>
                  )}
                  {(strategyDetail.when_it_does_not_fit_beginner || strategyDetail.when_it_does_not_fit) && (
                    <div className="bg-red-50 border border-red-100 rounded-[1.25rem] p-5">
                      <div className="flex items-center gap-2 text-sm font-bold text-red-800 mb-2">
                        <XCircle className="w-4 h-4" />
                        이런 상황에는 맞지 않아요
                      </div>
                      <div className="text-sm text-red-700 leading-relaxed">
                        {strategyDetail.when_it_does_not_fit_beginner || strategyDetail.when_it_does_not_fit}
                      </div>
                    </div>
                  )}
                </div>

                {/* General explanation + why people use it */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                  {(strategyDetail.general_explanation || strategyDetail.description) && (
                    <div className="bg-gray-50 rounded-[1.25rem] border border-gray-100 p-5">
                      <div className="text-sm font-bold text-gray-900 mb-2">전략 개요</div>
                      <div className="text-sm text-gray-600 leading-relaxed">
                        {strategyDetail.general_explanation || strategyDetail.description}
                      </div>
                    </div>
                  )}
                  {(strategyDetail.why_people_use_it || strategyDetail.core_rationale) && (
                    <div className="bg-gray-50 rounded-[1.25rem] border border-gray-100 p-5">
                      <div className="text-sm font-bold text-gray-900 mb-2">왜 사람들이 쓰는가</div>
                      <div className="text-sm text-gray-600 leading-relaxed">
                        {strategyDetail.why_people_use_it || strategyDetail.core_rationale}
                      </div>
                    </div>
                  )}
                </div>

                {/* Entry / Stop / Target / Position / Holding */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                  <div className="bg-gray-50 rounded-[1.25rem] border border-gray-100 p-5">
                    <div className="text-sm font-bold text-gray-900 mb-2">진입 힌트</div>
                    <div className="text-sm text-gray-600 leading-relaxed">{strategyDetail.entry_hint}</div>
                  </div>
                  <div className="bg-gray-50 rounded-[1.25rem] border border-gray-100 p-5">
                    <div className="text-sm font-bold text-gray-900 mb-2">보유 기간</div>
                    <div className="text-sm text-gray-600 leading-relaxed">{strategyDetail.holding_period}</div>
                  </div>
                  <div className="bg-gray-50 rounded-[1.25rem] border border-gray-100 p-5">
                    <div className="text-sm font-bold text-gray-900 mb-2">손절 규칙</div>
                    <div className="text-sm text-gray-600 leading-relaxed">{strategyDetail.stop_rule}</div>
                  </div>
                  <div className="bg-gray-50 rounded-[1.25rem] border border-gray-100 p-5">
                    <div className="text-sm font-bold text-gray-900 mb-2">목표가 규칙</div>
                    <div className="text-sm text-gray-600 leading-relaxed">{strategyDetail.target_rule}</div>
                  </div>
                  <div className="bg-gray-50 rounded-[1.25rem] border border-gray-100 p-5 md:col-span-2">
                    <div className="text-sm font-bold text-gray-900 mb-2">포지션 규칙</div>
                    <div className="text-sm text-gray-600 leading-relaxed">{strategyDetail.position_rule}</div>
                  </div>
                </div>

                {/* Invalidation condition */}
                {strategyDetail.invalidation_condition && (
                  <div className="bg-rose-50 border border-rose-100 rounded-[1.25rem] p-5 mb-6">
                    <div className="flex items-center gap-2 text-sm font-bold text-rose-800 mb-2">
                      <ShieldAlert className="w-4 h-4" />
                      이 전략이 무효화되는 조건
                    </div>
                    <div className="text-sm text-rose-700 leading-relaxed">{strategyDetail.invalidation_condition}</div>
                  </div>
                )}

                {/* Caution + Limitations */}
                <div className="bg-amber-50 border border-amber-100 rounded-[1.25rem] p-5 mb-6">
                  <div className="text-sm font-bold text-amber-800 mb-2">주의사항</div>
                  <div className="text-sm text-amber-700 leading-relaxed mb-3">{strategyDetail.caution}</div>
                  {strategyDetail.limitations && (
                    <>
                      <div className="text-sm font-bold text-amber-800 mb-2">한계</div>
                      <div className="text-sm text-amber-700 leading-relaxed">{strategyDetail.limitations}</div>
                    </>
                  )}
                </div>

                {/* Unsupported claims */}
                {strategyDetail.unsupported_or_weak_claims && strategyDetail.unsupported_or_weak_claims.length > 0 && (
                  <div className="bg-gray-50 border border-gray-200 rounded-[1.25rem] p-5 mb-6">
                    <div className="text-sm font-bold text-gray-700 mb-2">약한 근거 / 주의해서 볼 주장</div>
                    <ul className="space-y-1.5">
                      {strategyDetail.unsupported_or_weak_claims.map((claim) => (
                        <li key={claim} className="flex items-start gap-2 text-sm text-gray-500">
                          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-gray-400" />
                          {claim}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Checklist */}
                {strategyDetail.checklist_items && strategyDetail.checklist_items.length > 0 && (
                  <div className="bg-indigo-50 border border-indigo-100 rounded-[1.25rem] p-5 mb-6">
                    <div className="flex items-center gap-2 text-sm font-bold text-indigo-800 mb-3">
                      <CheckSquare className="w-4 h-4" />
                      진입 전 체크리스트
                    </div>
                    <ul className="space-y-2">
                      {strategyDetail.checklist_items.map((item) => (
                        <li key={item} className="flex items-start gap-2 text-sm text-indigo-700">
                          <span className="mt-1 w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Sources + evidence */}
                <div className="bg-gray-50 rounded-[1.25rem] border border-gray-100 p-5 mb-8">
                  <div className="text-sm font-bold text-gray-900 mb-2">출처</div>
                  <ul className="space-y-2 text-sm text-gray-600">
                    {(strategyDetail.source_note || strategyDetail.source || []).map((sourceItem) => (
                      <li key={sourceItem}>{sourceItem}</li>
                    ))}
                  </ul>
                  {strategyDetail.evidence_quality && (
                    <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500 leading-relaxed">
                      근거 수준: {strategyDetail.evidence_quality}
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setStep(4);
                    setShowConfirm(false);
                    setSaveError("");
                  }}
                  className="w-full bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition py-4 font-bold"
                >
                  이 전략으로 계획 세우기
                </button>
              </div>
            )}
          </section>
        )}

        {/* ===== STEP 4: Plan Input ===== */}
        {step === 4 && selectedStrategy && (
          <section className="space-y-6">
            <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="text-xs font-semibold text-gray-400 mb-1">계획 입력</div>
                <div className="text-lg font-bold text-gray-900">
                  {selectedStock?.name} · {selectedStrategy.name}
                </div>
                <div className="text-sm text-gray-500">
                  전략 힌트를 참고해 내 기준의 첫 매수 계획을 적어보세요.
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setStep(3);
                  setShowConfirm(false);
                }}
                className="inline-flex items-center gap-2 text-sm font-medium text-gray-500 hover:text-indigo-600"
              >
                <ChevronLeft className="w-4 h-4" />
                전략 상세로 돌아가기
              </button>
            </div>

            {/* Fundamental thesis invalidation banner */}
            {isFundamental && selectedStrategy.invalidation_condition && (
              <div className="bg-rose-50 border border-rose-100 rounded-[1.5rem] p-5">
                <div className="flex items-center gap-2 text-sm font-bold text-rose-800 mb-2">
                  <ShieldAlert className="w-4 h-4" />
                  Thesis 무효화 조건 (가격보다 중요)
                </div>
                <div className="text-sm text-rose-700 leading-relaxed">{selectedStrategy.invalidation_condition}</div>
                <div className="mt-3 text-xs text-rose-500">
                  펀더멘털 전략에서는 가격 손절보다 thesis 훼손 여부가 더 중요합니다. 메모에 다음 공시 점검 포인트를 함께 적어두세요.
                </div>
              </div>
            )}

            {/* Technical/hybrid invalidation reminder */}
            {!isFundamental && selectedStrategy.invalidation_condition && (
              <div className="bg-rose-50/60 border border-rose-100 rounded-[1.5rem] p-4">
                <div className="flex items-center gap-2 text-sm font-bold text-rose-700 mb-1">
                  <ShieldAlert className="w-4 h-4" />
                  무효화 조건
                </div>
                <div className="text-sm text-rose-600">{selectedStrategy.invalidation_condition}</div>
              </div>
            )}

            <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] gap-6">
              <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-6 md:p-8">
                <div className="space-y-5">
                  <div>
                    <label className="block text-sm font-bold text-gray-700 mb-2">매수 희망가</label>
                    <input
                      type="number"
                      min="0"
                      value={form.entry_price}
                      onChange={(event) => handleFormChange("entry_price", event.target.value)}
                      className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none"
                      placeholder="예: 100000"
                    />
                    <div className="mt-2 text-xs text-gray-400">{selectedStrategy.entry_hint}</div>
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-gray-700 mb-2">손절가</label>
                    <input
                      type="number"
                      min="0"
                      value={form.stop_loss_price}
                      onChange={(event) => handleFormChange("stop_loss_price", event.target.value)}
                      className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none"
                      placeholder="예: 95000"
                    />
                    <div className="mt-2 text-xs text-gray-400">{selectedStrategy.stop_rule}</div>
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-gray-700 mb-2">목표가</label>
                    <input
                      type="number"
                      min="0"
                      value={form.target_price}
                      onChange={(event) => handleFormChange("target_price", event.target.value)}
                      className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none"
                      placeholder="예: 115000"
                    />
                    <div className="mt-2 text-xs text-gray-400">{selectedStrategy.target_rule}</div>
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-gray-700 mb-2">비중 (%)</label>
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={form.position_size_pct}
                      onChange={(event) => handleFormChange("position_size_pct", event.target.value)}
                      className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none"
                      placeholder="예: 15"
                    />
                    <div className="mt-2 text-xs text-gray-400">{selectedStrategy.position_rule}</div>
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-gray-700 mb-2">보유 기간</label>
                    <select
                      value={form.holding_period}
                      onChange={(event) => handleFormChange("holding_period", event.target.value)}
                      className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none bg-white"
                    >
                      {HOLDING_PERIOD_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-gray-700 mb-2">매수 이유 한 줄</label>
                    <input
                      type="text"
                      maxLength={100}
                      value={form.one_line_reason}
                      onChange={(event) => handleFormChange("one_line_reason", event.target.value)}
                      className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none"
                      placeholder="왜 지금 이 전략과 종목을 선택했는지 적어보세요."
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-gray-700 mb-2">
                      메모
                      {isFundamental && (
                        <span className="ml-2 text-xs font-normal text-rose-500">
                          (다음 공시 점검 포인트를 여기에 적어두세요)
                        </span>
                      )}
                    </label>
                    <textarea
                      rows={4}
                      value={form.note}
                      onChange={(event) => handleFormChange("note", event.target.value)}
                      className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
                      placeholder={
                        isFundamental
                          ? "체크할 리스크, 다음 공시 확인 포인트, thesis 재검토 기준을 적어두세요."
                          : "체크할 리스크나 관찰 포인트를 적어두세요."
                      }
                    />
                  </div>
                </div>
              </div>

              <aside className="space-y-4">
                <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-5">
                  <div className="text-sm font-bold text-gray-900 mb-4">리스크 / 리워드</div>
                  {riskReward ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500">손실 위험</span>
                        <span className="font-bold text-red-500">-{riskReward.riskPct.toFixed(1)}%</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500">기대 수익</span>
                        <span className="font-bold text-emerald-500">+{riskReward.rewardPct.toFixed(1)}%</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-500">손익비</span>
                        <span className={`font-bold ${riskReward.ratio <= 1 ? "text-amber-600" : "text-gray-900"}`}>
                          1 : {riskReward.ratio ? riskReward.ratio.toFixed(2) : "-"}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm text-gray-400 leading-relaxed">
                      매수 희망가, 손절가, 목표가를 입력하면 예상 손익비가 계산됩니다.
                    </div>
                  )}
                </div>

                {(validation.messages.length > 0 || validation.warnings.length > 0 || validation.hints.length > 0 || saveError) && (
                  <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-5 space-y-3">
                    {saveError && (
                      <div className="flex items-start gap-2 text-sm text-red-600">
                        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                        <span>{saveError}</span>
                      </div>
                    )}
                    {validation.messages.map((message) => (
                      <div key={message} className="flex items-start gap-2 text-sm text-red-600">
                        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                        <span>{message}</span>
                      </div>
                    ))}
                    {validation.warnings.map((warning) => (
                      <div key={warning} className="flex items-start gap-2 text-sm text-amber-600">
                        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                        <span>{warning}</span>
                      </div>
                    ))}
                    {validation.hints.map((hint) => (
                      <div key={hint} className="text-sm text-gray-500">{hint}</div>
                    ))}
                  </div>
                )}

                {showConfirm && (
                  <div className="bg-white rounded-[1.5rem] border border-indigo-100 shadow-sm p-5">
                    <div className="text-sm font-bold text-gray-900 mb-4">저장 전 확인</div>
                    <div className="space-y-2 text-sm text-gray-600">
                      <div><span className="font-semibold text-gray-900">종목</span> {selectedStock.name}</div>
                      <div><span className="font-semibold text-gray-900">전략</span> {selectedStrategy.name}</div>
                      <div><span className="font-semibold text-gray-900">매수 희망가</span> {form.entry_price}</div>
                      <div><span className="font-semibold text-gray-900">손절가</span> {form.stop_loss_price}</div>
                      <div><span className="font-semibold text-gray-900">목표가</span> {form.target_price}</div>
                      <div><span className="font-semibold text-gray-900">비중</span> {form.position_size_pct}%</div>
                      <div><span className="font-semibold text-gray-900">보유 기간</span> {form.holding_period}</div>
                      <div><span className="font-semibold text-gray-900">매수 이유</span> {form.one_line_reason}</div>
                      {riskReward && (
                        <div><span className="font-semibold text-gray-900">손익비</span> 1 : {riskReward.ratio?.toFixed(2)}</div>
                      )}
                    </div>
                    <div className="flex flex-col sm:flex-row gap-3 mt-5">
                      <button
                        type="button"
                        onClick={() => setShowConfirm(false)}
                        className="flex-1 px-4 py-3 rounded-xl border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                      >
                        수정하기
                      </button>
                      <button
                        type="button"
                        onClick={() => submitPlan("saved")}
                        disabled={saveLoading}
                        className="flex-1 px-4 py-3 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 disabled:opacity-60"
                      >
                        {saveLoading ? "저장 중..." : "확인 후 저장"}
                      </button>
                    </div>
                  </div>
                )}

                <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-5 space-y-3">
                  <button
                    type="button"
                    onClick={() => submitPlan("draft")}
                    disabled={saveLoading}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-60"
                  >
                    {saveLoading ? "저장 중..." : "임시 저장"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (validateBeforeSubmit()) {
                        setShowConfirm(true);
                      }
                    }}
                    disabled={saveLoading}
                    className="w-full px-4 py-3 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 disabled:opacity-60"
                  >
                    저장하기
                  </button>
                </div>
              </aside>
            </div>
          </section>
        )}

        {/* ===== STEP 5: Saved ===== */}
        {step === 5 && savedPlan && (
          <section className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-8 md:p-10 text-center">
            <div className="w-16 h-16 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-5">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">매수 계획이 저장되었습니다!</h2>
            <p className="text-gray-500 mb-8">
              이제 내 계획 목록에서 저장한 전략을 다시 보고, 필요하면 수정하거나 삭제할 수 있어요.
            </p>

            <div className="max-w-xl mx-auto bg-gray-50 border border-gray-100 rounded-[1.5rem] p-6 text-left mb-8">
              <div className="text-sm font-bold text-gray-900 mb-4">저장 요약</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-gray-600">
                <div><span className="font-semibold text-gray-900">종목</span> {savedPlan.symbol}</div>
                <div><span className="font-semibold text-gray-900">전략</span> {savedPlan.strategy_snapshot.name}</div>
                <div><span className="font-semibold text-gray-900">손절가</span> {savedPlan.stop_loss_price}</div>
                <div><span className="font-semibold text-gray-900">목표가</span> {savedPlan.target_price}</div>
                <div><span className="font-semibold text-gray-900">비중</span> {savedPlan.position_size_pct}%</div>
                <div><span className="font-semibold text-gray-900">상태</span> {savedPlan.status === "draft" ? "임시저장" : "저장됨"}</div>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row justify-center gap-3">
              <button
                type="button"
                onClick={() => navigate("/my-plans")}
                className="px-5 py-3 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700"
              >
                내 계획 목록 보기
              </button>
              <button
                type="button"
                onClick={handleResetPlanner}
                className="px-5 py-3 rounded-xl border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50"
              >
                새 계획 만들기
              </button>
            </div>
          </section>
        )}

        <div className="mt-8 text-[11px] text-gray-400 border-t border-gray-100 pt-4">
          {DISCLAIMER_TEXT}
        </div>
      </main>
    </div>
  );
}
