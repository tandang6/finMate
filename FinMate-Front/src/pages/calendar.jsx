import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Clock,
  Flag,
  Info,
  Loader2,
  X,
  TrendingUp,
  TrendingDown,
  CheckCircle,
} from "lucide-react";

// -----------------------------
// 자산 필터 옵션
// -----------------------------
const ASSETS = [
  { id: "all", label: "전체" },
  { id: "samsung", label: "삼성전자" },
  { id: "skhynix", label: "SK하이닉스" },
];

// -----------------------------
// 유틸 함수들
// -----------------------------
function formatDateTime(iso) {
  const d = new Date(iso);
  const date = d.toLocaleDateString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
  });
  const time = d.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return { date, time };
}

function getDateKey(input) {
  const d = input instanceof Date ? input : new Date(input);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function buildCalendarCells(year, monthIndex) {
  const firstDay = new Date(year, monthIndex, 1);
  const firstWeekday = firstDay.getDay(); // 0=일요일
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();

  const cells = [];
  for (let i = 0; i < firstWeekday; i++) cells.push({ day: null, dateKey: null });
  for (let d = 1; d <= daysInMonth; d++) {
    const dateKey = `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(
      d
    ).padStart(2, "0")}`;
    cells.push({ day: d, dateKey });
  }
  return cells;
}

function importanceLabel(level) {
  switch (level) {
    case "very_high":
      return "매우 중요";
    case "high":
      return "중요";
    case "medium":
      return "보통";
    case "low":
    default:
      return "낮음";
  }
}

function importanceChipClass(level) {
  switch (level) {
    case "very_high":
      return "bg-red-50 text-red-600 border-red-100";
    case "high":
      return "bg-orange-50 text-orange-600 border-orange-100";
    case "medium":
      return "bg-amber-50 text-amber-600 border-amber-100";
    case "low":
    default:
      return "bg-gray-50 text-gray-500 border-gray-200";
  }
}

function parseInsightSections(text) {
  const clean = (text || "").trim();
  if (!clean) return null;

  // 섹션 헤더 기준 분리
  const headerRegex = /(🔴\s*상승 요인.*|🔵\s*하락 요인.*|🟢\s*시장 체크 포인트.*)/g;

  const parts = clean.split(headerRegex).filter(Boolean);

  const result = {
    long: [],
    short: [],
    checkpoints: [],
  };

  let current = null;

  for (let i = 0; i < parts.length; i++) {
    const chunk = parts[i].trim();

    if (chunk.startsWith("🔴")) current = "long";
    else if (chunk.startsWith("🔵")) current = "short";
    else if (chunk.startsWith("🟢")) current = "checkpoints";
    else if (current) {
      // content chunk
      if (current === "checkpoints") {
        // "- ..." 라인만 모으기
        const lines = chunk
          .split("\n")
          .map((l) => l.trim())
          .filter(Boolean);

        result.checkpoints = lines
          .filter((l) => l.startsWith("-"))
          .map((l) => l.replace(/^-+\s*/, ""));
      } else {
        // "1) 제목" + "- bullet" 구조 파싱
        const blocks = chunk
          .split(/\n(?=\d+\)\s)/) // "1) ..." 시작 기준
          .map((b) => b.trim())
          .filter(Boolean);

        const parsed = blocks.map((b) => {
          const lines = b.split("\n").map((l) => l.trim()).filter(Boolean);
          const titleLine = lines[0] || "";
          const title = titleLine.replace(/^\d+\)\s*/, "").trim();

          const bullets = lines
            .slice(1)
            .filter((l) => l.startsWith("-"))
            .map((l) => l.replace(/^-+\s*/, ""));

          // bullet이 하나도 없으면 그냥 나머지 라인들 텍스트로라도 표시
          const fallback = lines.slice(1).filter((l) => !l.startsWith("-"));
          const finalBullets = bullets.length ? bullets : fallback;

          return { title, bullets: finalBullets };
        });

        result[current] = parsed;
      }
    }
  }

  return result;
}

// -----------------------------
// 발표 후 더미데이터
// -----------------------------
const POST_EVENT_DUMMY = {
  "kr-earnings-37": {
    status: "available",
    sourceNote: "이 이벤트는 촬영/시연을 위해 보존된 고정 데이터입니다.",
    earnings: {
      title: "2025년 3분기 실적",
      status: "available",
      source: "시연용 고정 데이터",
      items: [
        { k: "매출", v: "79조 1,400억원 (시연용)" },
        { k: "영업이익", v: "12조 1,600억원 (시연용)" },
        { k: "순이익", v: "9조 8,800억원 (시연용)" },
        { k: "포인트", v: "메모리 가격 반등 + AI 수요 기대감(가정)" },
      ],
    },
    priceMove: {
      title: "발표 직후 주가 반응",
      status: "available",
      source: "시연용 고정 데이터",
      items: [
        { k: "당일", v: "+3.2% (가정)" },
        { k: "장중 변동", v: "초반 급등 → 일부 차익실현(가정)" },
        { k: "거래량", v: "평균 대비 증가(가정)" },
      ],
    },
    commentary: {
      title: "해설",
      status: "available",
      source: "시연용 고정 데이터",
      bullets: [
        "결과가 ‘기대 대비 상회’면 단기적으로 매수세가 유입되기 쉬움",
        "하지만 가이던스/업황 코멘트가 약하면 ‘사실매도’가 나올 수 있음",
        "발표 후 1~3일은 수급(기관/외국인)과 기술적 저항 구간 확인이 핵심",
      ],
    },
  },
};


function buildEventCacheKey(event) {
  if (!event) return "";
  return event.id || `${event.stockCode || event.stock_code || ""}-${event.datetime || ""}-${event.title || ""}`;
}

function getPostEventFallback(event) {
  if (!event) return null;
  const stockCode = event.stockCode || event.stock_code || "";
  const dateKey = event.datetime ? getDateKey(event.datetime) : "";
  return POST_EVENT_DUMMY[event.id] || (stockCode === "005930" && dateKey === "2025-10-30"
    ? POST_EVENT_DUMMY["kr-earnings-37"]
    : null);
}

function buildPostResultPayload(event) {
  return {
    ...event,
    companyName: event.companyName || event.company_name || "",
    stockCode: event.stockCode || event.stock_code || "",
    rceptNo: event.rceptNo || event.rcept_no || "",
  };
}


// -----------------------------
// 페이지 컴포넌트
// -----------------------------
const EconomicCalendarPage = () => {
  const today = new Date();
  const todayKey = getDateKey(today);

  const [selectedAsset, setSelectedAsset] = useState("all");

  // 달력 연/월
  const [year, setYear] = useState(today.getFullYear());
  const [monthIndex, setMonthIndex] = useState(today.getMonth());

  // API로 받아오는 이벤트 상태
  const [events, setEvents] = useState([]);
  const [isLoadingEvents, setIsLoadingEvents] = useState(true);
  const [eventsError, setEventsError] = useState(null);

  // 선택된 날짜/이벤트 (이벤트는 자동 선택 X)
  const [selectedDateKey, setSelectedDateKey] = useState(todayKey);
  const [selectedEventId, setSelectedEventId] = useState(null);

  // 해설 패널 열림 상태
  const [isInsightOpen, setIsInsightOpen] = useState(false);
  
  // 해설 패널 발표 전 후 상태
  const [insightTab, setInsightTab] = useState("pre"); // "pre" | "post"

  // AI 해설 상태
  const [aiInsight, setAiInsight] = useState("");
  const [isLoadingInsight, setIsLoadingInsight] = useState(false);
  const [insightError, setInsightError] = useState(null);

  // AI 해설 캐시 (이벤트별 인사이트 저장)
  const [insightCache, setInsightCache] = useState({});

  // 발표 후 결과 상태/캐시
  const [postResultCache, setPostResultCache] = useState({});
  const [isLoadingPostResult, setIsLoadingPostResult] = useState(false);
  const [postResultError, setPostResultError] = useState(null);

  // 헤더 높이(상단바 높이). 필요하면 숫자만 수정.
  const HEADER_H = 64;
  
  const insightParsed = useMemo(() => parseInsightSections(aiInsight), [aiInsight]);
  
  
  // -----------------------------
  // Events Fetch
  // -----------------------------
  useEffect(() => {
    const fetchEvents = async () => {
      try {
        setIsLoadingEvents(true);
        setEventsError(null);

        const res = await fetch("http://localhost:8000/api/calendar/earnings-demo");
        if (!res.ok) throw new Error("calendar events api error");

        const data = await res.json();
        const normalized = Array.isArray(data) ? data.filter((e) => e && e.datetime) : [];
        setEvents(normalized);
      } catch (e) {
        console.error("캘린더 이벤트 불러오기 실패:", e);
        setEventsError(e);
        setEvents([]);
      } finally {
        setIsLoadingEvents(false);
      }
    };

    fetchEvents();
  }, []);

  // 날짜별 이벤트 그룹
  const eventsByDate = useMemo(() => {
    const map = {};
    events.forEach((ev) => {
      const key = getDateKey(ev.datetime);
      if (!map[key]) map[key] = [];
      map[key].push(ev);
    });

    Object.keys(map).forEach((k) => {
      map[k].sort((a, b) => {
        const order = { very_high: 3, high: 2, medium: 1, low: 0 };
        return (order[b.importance] ?? 0) - (order[a.importance] ?? 0);
      });
    });

    return map;
  }, [events]);

  // 달력 셀
  const calendarCells = useMemo(
    () => buildCalendarCells(year, monthIndex),
    [year, monthIndex]
  );
  const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
  const monthLabel = `${year}년 ${monthIndex + 1}월`;

  // 선택된 날짜 + 자산 기준 이벤트
  const filteredEventsForSelectedDate = useMemo(() => {
    if (!selectedDateKey) return [];
    const all = eventsByDate[selectedDateKey] || [];
    if (selectedAsset === "all") return all;
    return all.filter((ev) => ev.asset === selectedAsset);
  }, [eventsByDate, selectedDateKey, selectedAsset]);

  // 선택 이벤트 (현재 선택된 날짜/자산 범위 안에서만)
  const selectedEvent = useMemo(() => {
    if (!selectedEventId) return null;
    return filteredEventsForSelectedDate.find((ev) => ev.id === selectedEventId) || null;
  }, [filteredEventsForSelectedDate, selectedEventId]);

  const selectedEventCacheKey = useMemo(() => buildEventCacheKey(selectedEvent), [selectedEvent]);
  const postFallback = useMemo(() => getPostEventFallback(selectedEvent), [selectedEvent]);
  const postResult = selectedEventCacheKey ? postResultCache[selectedEventCacheKey] || null : null;
  const postDisplay = postResult || postFallback;

  const postSections = useMemo(() => {
    if (!postDisplay) return [];
    return [
      { key: "earnings", label: "실적 발표 결과", data: postDisplay.earnings },
      { key: "priceMove", label: "주가 변동", data: postDisplay.priceMove },
    ].filter((section) => section.data);
  }, [postDisplay]);

  // -----------------------------
  // Post Result Fetch (패널 열림 + 발표 후 탭 + 이벤트 선택 시)
  // -----------------------------
  useEffect(() => {
    const fetchPostResult = async () => {
      if (!isInsightOpen || !selectedEvent || insightTab !== "post") return;

      const cacheKey = buildEventCacheKey(selectedEvent);
      if (postResultCache[cacheKey]) {
        setPostResultError(null);
        setIsLoadingPostResult(false);
        return;
      }

      try {
        setIsLoadingPostResult(true);
        setPostResultError(null);

        const res = await fetch("http://localhost:8000/api/calendar/post-result", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildPostResultPayload(selectedEvent)),
        });

        if (!res.ok) throw new Error("post result api error");

        const data = await res.json();
        setPostResultCache((prev) => ({ ...prev, [cacheKey]: data }));
      } catch (e) {
        console.error("발표 후 결과 불러오기 실패:", e);
        setPostResultError(e);
      } finally {
        setIsLoadingPostResult(false);
      }
    };

    fetchPostResult();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInsightOpen, selectedEventId, insightTab]);

  // -----------------------------
  // Insight Fetch (패널 열림 + 이벤트 선택 시)
  // -----------------------------
  useEffect(() => {
    const fetchInsight = async () => {
      if (!isInsightOpen || !selectedEvent || insightTab !== "pre") return;

      const cacheKey =
        selectedEvent.id ||
        `${selectedEvent.stockCode || ""}-${selectedEvent.datetime || ""}-${selectedEvent.title || ""}`;

      // 캐시 hit
      if (insightCache[cacheKey]) {
        setAiInsight(insightCache[cacheKey]);
        setInsightError(null);
        setIsLoadingInsight(false);
        return;
      }

      try {
        setIsLoadingInsight(true);
        setInsightError(null);

		// 백엔드 Pydantic 모델에 맞춰 key 이름 맞추기
        const payload = {
          title: selectedEvent.title,
          companyName: selectedEvent.companyName || selectedEvent.company_name || "",
          stockCode: selectedEvent.stockCode || selectedEvent.stock_code || "",
          datetime: selectedEvent.datetime,
		  // 있으면 type도 같이 보내면 나중에 프롬프트 고도화에 도움
          type: selectedEvent.type || "",
        };

        const res = await fetch("http://localhost:8000/api/calendar/insight", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) throw new Error("insight api error");

        const data = await res.json();
        const insightText = data?.insight || "";

        setAiInsight(insightText);
        setInsightCache((prev) => ({ ...prev, [cacheKey]: insightText }));
      } catch (e) {
        console.error("AI 해설 불러오기 실패:", e);
        setInsightError(e);
        setAiInsight("");
      } finally {
        setIsLoadingInsight(false);
      }
    };

    fetchInsight();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInsightOpen, selectedEventId, insightTab]); // 클릭/열림 시만

  // -----------------------------
  // Handlers
  // -----------------------------
  const handleSelectDate = (dateKey) => {
    setSelectedDateKey(dateKey);
    setSelectedEventId(null);
    setAiInsight("");
    setInsightError(null);
    setPostResultError(null);
    setIsLoadingPostResult(false);
    // 날짜 바꾸면 패널 닫고 싶으면 아래 주석 해제
    // setIsInsightOpen(false);
  };

  const handleAssetChange = (assetId) => {
    setSelectedAsset(assetId);
    setSelectedEventId(null);
    setIsInsightOpen(false);
    setAiInsight("");
    setInsightError(null);
    setPostResultError(null);
    setIsLoadingPostResult(false);
  };

  const handlePrevMonth = () => {
    setMonthIndex((prev) => {
      if (prev === 0) {
        setYear((y) => y - 1);
        return 11;
      }
      return prev - 1;
    });
  };

  const handleNextMonth = () => {
    setMonthIndex((prev) => {
      if (prev === 11) {
        setYear((y) => y + 1);
        return 0;
      }
      return prev + 1;
    });
  };

  const isPastEvent = (ev) => {
	if (!ev?.datetime) return false;
	return new Date(ev.datetime).getTime() < Date.now();
  };

  const handleClickEvent = (event) => {
    setSelectedEventId(event.id);
    setIsInsightOpen(true);
	
	// 과거 이벤트면 '발표 후' 기본
    const defaultTab = isPastEvent(event) ? "post" : "pre";
    setInsightTab(defaultTab);
	
    setInsightError(null);
    setPostResultError(null);

    // 캐시 있으면 즉시 표시
    const cacheKey =
      event.id || `${event.stockCode || ""}-${event.datetime || ""}-${event.title || ""}`;
    if (insightCache[cacheKey]) {
      setAiInsight(insightCache[cacheKey]);
      setIsLoadingInsight(false);
    } else {
      setAiInsight("");
    }
  };

  // 패널 열리면: main을 풀폭으로 해서 “좌측 여백이 줄어드는 느낌”
  const mainClass = isInsightOpen
    ? "w-full px-4 lg:px-6 py-8"
    : "max-w-7xl mx-auto px-4 lg:px-6 py-8";

  // 패널이 fixed라서 겹치지 않도록 오른쪽 padding으로 공간 확보(왼쪽이 밀리는 느낌)
  const leftWrapClass = "transition-all duration-300 ease-out " + (isInsightOpen ? "lg:pr-[34%]" : "pr-0");

  // 패널 top/h는 inline style로 처리(템플릿 문자열 실수 방지)
  const panelStyle = {
    top: HEADER_H,
    height: `calc(100vh - ${HEADER_H}px)`,
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#F8F9FD]">
      <main className={mainClass}>
        {/* 상단 헤더 */}
        <div className="flex items-start justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-xs font-semibold text-indigo-700 mb-3">
              <CalendarIcon className="w-4 h-4" />
              주요 경제 일정
            </div>
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2">
              경제 이벤트 캘린더
            </h1>
            <p className="text-sm md:text-base text-gray-500 max-w-2xl">
              국내 기업의 실적 발표 일정 및 금리, 물가, 고용, 성장률 등 핵심 거시 지표 발표 일정을
              삼성전자·SK하이닉스 등 보유/관심 자산 기준으로 정리해 보여줍니다.
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

        {/* ✅ 왼쪽 영역(캘린더+목록): 패널 열리면 오른쪽 padding으로 밀림 */}
        <div className="relative">
          <div className={leftWrapClass}>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* 캘린더 */}
              <section className="lg:col-span-4 bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-5 flex flex-col">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold text-gray-800 flex items-center gap-2">
                    <CalendarIcon className="w-4 h-4 text-indigo-600" />
                    일정 캘린더
                  </h2>
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <button
                      type="button"
                      onClick={handlePrevMonth}
                      className="p-1 rounded-full hover:bg-gray-100 border border-gray-200"
                    >
                      <ChevronLeft className="w-3 h-3" />
                    </button>
                    <span className="font-medium text-gray-800">{monthLabel}</span>
                    <button
                      type="button"
                      onClick={handleNextMonth}
                      className="p-1 rounded-full hover:bg-gray-100 border border-gray-200"
                    >
                      <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>

                {isLoadingEvents && (
                  <div className="text-xs text-gray-400 mb-3">일정을 불러오는 중...</div>
                )}
                {eventsError && (
                  <div className="text-xs text-red-500 mb-3">
                    일정 데이터를 불러오지 못했어요. (백엔드 실행/포트 확인)
                  </div>
                )}

                <div className="grid grid-cols-7 text-center text-[11px] text-gray-400 mb-2">
                  {weekdays.map((w) => (
                    <div key={w} className="py-1">
                      {w}
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-7 gap-1">
                  {calendarCells.map((cell, idx) => {
                    if (!cell.day) return <div key={idx} className="aspect-square rounded-xl" />;

                    const eventsForDayAll = (cell.dateKey && eventsByDate[cell.dateKey]) || [];
                    const eventsForDayFiltered =
					  selectedAsset === "all"
						? eventsForDayAll
						: eventsForDayAll.filter((ev) => ev.asset === selectedAsset);

					const hasEvent = eventsForDayFiltered.length > 0;
                    const isSelected = cell.dateKey === selectedDateKey;
                    const isToday = cell.dateKey === todayKey;

                    let baseClass =
                      "aspect-square rounded-xl border text-left text-[11px] px-1.5 py-1 flex flex-col justify-between transition-all";
                    let stateClass = "bg-white border-gray-200 text-gray-700";

                    if (hasEvent) stateClass = "bg-indigo-50/40 border-indigo-200 text-gray-900";
                    if (isToday) stateClass = "bg-gray-900 text-white border-gray-900 shadow-sm";
                    if (isSelected)
                      stateClass =
                        "bg-indigo-100 text-indigo-900 border-indigo-500 shadow-sm ring-1 ring-indigo-300";

                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleSelectDate(cell.dateKey)}
                        className={`${baseClass} ${stateClass} relative`}
                      >
                        <div className="flex items-center justify-start">
                          <span className="font-semibold text-[11px]">{cell.day}</span>
                        </div>
                        {hasEvent && (
                          <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-indigo-600" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </section>

              {/* 일정 리스트 */}
              <section className="lg:col-span-8 space-y-4">
			    {/* 자산 필터 */}
                <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <Flag className="w-3 h-3 text-indigo-500" />
                    <span>관심 자산 기준으로 일정 필터링</span>
                  </div>
                  <div className="inline-flex items-center rounded-full bg-gray-50 p-1 border border-gray-100">
                    {ASSETS.map((asset) => (
                      <button
                        key={asset.id}
                        onClick={() => handleAssetChange(asset.id)}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                          selectedAsset === asset.id
                            ? "bg-white text-indigo-600 shadow-sm border border-indigo-100"
                            : "text-gray-500 hover:text-gray-700"
                        }`}
                      >
                        {asset.label}
                      </button>
                    ))}
                  </div>
                </div>

				{/* 이벤트 리스트 카드 */}
                <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-4 flex flex-col">
                  <h3 className="text-sm font-semibold text-gray-800 mb-3">
                    선택한 날짜의 경제 일정
                  </h3>

                  {filteredEventsForSelectedDate.length === 0 && (
                    <div className="flex-1 flex items-center justify-center text-xs text-gray-400 text-center px-4">
                      선택한 날짜에는 현재 선택한 자산 기준으로 등록된 일정이 없습니다.
                      <br />
                      자산을 <span className="font-semibold text-gray-500">"전체"</span>로 바꿔 확인해보세요.
                    </div>
                  )}

                  {filteredEventsForSelectedDate.length > 0 && (
                    <ul className="space-y-2 overflow-y-auto max-h-[520px] pr-1">
                      {filteredEventsForSelectedDate.map((event) => {
                        const { time } = formatDateTime(event.datetime);
                        const isActive = selectedEventId === event.id;

                        return (
                          <li key={event.id}>
                            <button
                              onClick={() => handleClickEvent(event)}
                              className={`w-full text-left px-3 py-3 rounded-2xl border flex flex-col gap-1 transition-all ${
                                isActive
                                  ? "bg-indigo-50 border-indigo-200 shadow-sm"
                                  : "bg-white border-gray-200 hover:bg-gray-50"
                              }`}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-xs font-medium text-gray-900 line-clamp-1">
                                  {event.title}
                                </span>
                                <span
                                  className={
                                    "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border " +
                                    importanceChipClass(event.importance)
                                  }
                                >
                                  {importanceLabel(event.importance)}
                                </span>
                              </div>
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-[11px] text-gray-500 line-clamp-2">
                                  {event.description}
                                </span>
                                <span className="inline-flex items-center gap-1 text-[11px] text-gray-400 whitespace-nowrap">
                                  <Clock className="w-3 h-3" />
                                  {time}
                                </span>
                              </div>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </section>
            </div>
          </div>

          {/* RIGHT: 인사이트 패널 */}
          {isInsightOpen && (
            <aside
              className="hidden lg:flex fixed right-0 bg-white border-l border-gray-100 shadow-sm flex-col w-[34%]"
              style={panelStyle}
            >
              <div className="h-full flex flex-col p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Info className="w-4 h-4 text-indigo-600" />
                    <h3 className="text-sm font-semibold text-gray-800">일정 해설</h3>
                  </div>

                  <button
					type="button"
					onClick={() => setIsInsightOpen(false)}
					aria-label="해설 패널 닫기"
					className="text-gray-700 hover:text-gray-400">
					<X className="w-6 h-6" />
				  </button>
                </div>

                {!selectedEvent && (
                  <div className="flex-1 flex items-center justify-center text-sm text-gray-400 text-center px-6">
                    왼쪽에서 일정을 클릭하면 발표 전/후 해설이 열립니다.
                  </div>
                )}

                {!!selectedEvent && (
                  <>
                    <div className="mb-4">
                      <div className="text-xs text-gray-400 mb-1">
                        {formatDateTime(selectedEvent.datetime).date} ·{" "}
                        {formatDateTime(selectedEvent.datetime).time}
                      </div>
                      <div className="text-base font-semibold text-gray-900">
                        {selectedEvent.title}
                      </div>
					  {/* 기업명 및 주식코드
                      <div className="text-xs text-gray-500 mt-1">
                        {selectedEvent.companyName || selectedEvent.company_name || ""}{" "}
                        {selectedEvent.stockCode || selectedEvent.stock_code
                          ? `(${selectedEvent.stockCode || selectedEvent.stock_code})`
                          : ""}
                      </div>
					  */}
                    </div>

					{/* 탭 (발표 전 / 발표 후) */}
					<div className="mt-0.5">
					  <div className="flex items-end border-b border-gray-200">
						<button
						  type="button"
						  onClick={() => setInsightTab("post")}
						  className={[
							"relative -mb-px px-4 py-2 text-xs font-semibold transition",
							"rounded-t-xl border border-b-0",
							insightTab === "post"
							  ? "bg-white text-gray-900 border-gray-200 shadow-sm"
							  : "bg-transparent text-gray-500 border-transparent hover:text-gray-700 hover:bg-gray-50",
						  ].join(" ")}
						>
						  발표 후
						  {insightTab === "post" && (
							<span className="absolute left-0 right-0 -bottom-[1px] h-[2px] bg-white" />
						  )}
						</button>

						<button
						  type="button"
						  onClick={() => setInsightTab("pre")}
						  className={[
							"relative -mb-px ml-1 px-4 py-2 text-xs font-semibold transition",
							"rounded-t-xl border border-b-0",
							insightTab === "pre"
							  ? "bg-white text-gray-900 border-gray-200 shadow-sm"
							  : "bg-transparent text-gray-500 border-transparent hover:text-gray-700 hover:bg-gray-50",
						  ].join(" ")}
						>
						  발표 전
						  {insightTab === "pre" && (
							<span className="absolute left-0 right-0 -bottom-[1px] h-[2px] bg-white" />
						  )}
						</button>
					  </div>
					</div>

					{/* 본문 */}
                    <div className="flex-1 overflow-y-auto">
                      {/* (A) 발표 후 탭 */}
                      {insightTab === "post" && (
					  <div className="space-y-4 mt-3">
						{isLoadingPostResult && !postDisplay && (
						  <div className="text-sm text-gray-500 inline-flex items-center gap-2">
							<Loader2 className="w-4 h-4 animate-spin" />
							발표 후 데이터를 확인하는 중...
						  </div>
						)}

						{postResultError && (
						  <div className="text-sm text-amber-700 bg-amber-50 border border-amber-100 rounded-xl p-3">
							발표 후 API를 불러오지 못했어요. 사용 가능한 로컬/시연 데이터가 있으면 대신 표시합니다.
						  </div>
						)}

						{postDisplay?.sourceNote && (
						  <div className="text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-xl p-3">
							{postDisplay.sourceNote}
						  </div>
						)}

						{!isLoadingPostResult && !postDisplay ? (
						  <div className="text-sm text-gray-500 bg-gray-50 border border-gray-200 rounded-xl p-3">
							발표 후 결과를 만들 수 있는 종목코드, 공시번호, 일봉 데이터가 아직 연결되지 않았습니다.
						  </div>
						) : (
						  <>
								{postSections.map((section) => (
								  <div key={section.key} className="rounded-2xl border border-gray-200 bg-white p-4">
									<div className="mb-2">
									  <div className="text-sm font-semibold text-gray-900">{section.label}</div>
									</div>
									<div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
								  <div className="flex items-start justify-between gap-2 mb-2">
									<div className="text-xs font-semibold text-gray-900">
									  {section.data.title}
									</div>
									{section.data.source && (
									  <div className="text-[10px] text-gray-400 text-right">
										{section.data.source}
									  </div>
									)}
								  </div>
								  <ul className="space-y-1 text-xs text-gray-800">
									{(section.data.items || []).map((it, i) => (
									  <li key={i} className="flex gap-2">
										<span className="w-24 shrink-0 text-gray-500">{it.k}</span>
										<span className="font-medium">
										  {it.v}
										  {it.note && (
											<span className="block text-[10px] font-normal text-gray-400">
											  {it.note}
											</span>
										  )}
										</span>
									  </li>
									))}
								  </ul>
									</div>
								  </div>
								))}
							  </>
							)}
					  </div>
					)}

                      {/* (B) 발표 전 탭 */}
                      {insightTab === "pre" && (
                        <>
                          {isLoadingInsight && (
                            <div className="text-sm text-gray-500 inline-flex items-center gap-2 mt-2">
                              <Loader2 className="w-4 h-4 animate-spin" />
                              해설 생성 중...
                            </div>
                          )}

                          {insightError && (
                            <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl p-3 mt-2">
                              해설을 불러오지 못했어요. (/api/calendar/insight 확인)
                            </div>
                          )}

                          {!isLoadingInsight && !aiInsight && !insightError && (
                            <div className="text-sm text-gray-400 mt-2">해설 데이터가 없습니다.</div>
                          )}

                          {!!aiInsight && !isLoadingInsight && !insightError && (
                            <div className="space-y-4 mt-2">
                              {/* 상승 */}
                              <div className="rounded-2xl border border-red-100 bg-red-50/60 p-4">
                                <div className="flex items-center gap-2 mb-2">
                                  <div className="w-7 h-7 rounded-full bg-red-100 flex items-center justify-center">
                                    <TrendingUp className="w-4 h-4 text-red-600" />
                                  </div>
                                  <div className="text-sm font-semibold text-red-700">상승 요인</div>
                                </div>

                                {!insightParsed?.long?.length ? (
                                  <div className="text-xs text-red-700/70">표시할 항목이 없습니다.</div>
                                ) : (
                                  <div className="space-y-3">
                                    {insightParsed.long.map((blk, idx) => (
                                      <div
                                        key={idx}
                                        className="bg-white/70 border border-red-100 rounded-xl p-3"
                                      >
                                        <div className="text-xs font-semibold text-gray-900 mb-1">
                                          {idx + 1}) {blk.title}
                                        </div>
                                        <ul className="list-disc list-inside space-y-1 text-xs text-gray-800 leading-relaxed">
                                          {blk.bullets.map((b, i) => (
                                            <li key={i}>{b}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>

                              {/* 하락 */}
                              <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-4">
                                <div className="flex items-center gap-2 mb-2">
                                  <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center">
                                    <TrendingDown className="w-4 h-4 text-blue-600" />
                                  </div>
                                  <div className="text-sm font-semibold text-blue-700">하락 요인</div>
                                </div>

                                {!insightParsed?.short?.length ? (
                                  <div className="text-xs text-blue-700/70">표시할 항목이 없습니다.</div>
                                ) : (
                                  <div className="space-y-3">
                                    {insightParsed.short.map((blk, idx) => (
                                      <div
                                        key={idx}
                                        className="bg-white/70 border border-blue-100 rounded-xl p-3"
                                      >
                                        <div className="text-xs font-semibold text-gray-900 mb-1">
                                          {idx + 1}) {blk.title}
                                        </div>
                                        <ul className="list-disc list-inside space-y-1 text-xs text-gray-800 leading-relaxed">
                                          {blk.bullets.map((b, i) => (
                                            <li key={i}>{b}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>

                              {/* 체크포인트 */}
                              <div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-4">
                                <div className="flex items-center gap-2 mb-2">
                                  <div className="w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center">
                                    <CheckCircle className="w-4 h-4 text-emerald-600" />
                                  </div>
                                  <div className="text-sm font-semibold text-emerald-700">시장 체크 포인트</div>
                                </div>

                                {!insightParsed?.checkpoints?.length ? (
                                  <div className="text-xs text-emerald-700/70">표시할 항목이 없습니다.</div>
                                ) : (
                                  <ul className="list-disc list-inside space-y-1 text-xs text-gray-800 leading-relaxed bg-white/70 border border-emerald-100 rounded-xl p-3">
                                    {insightParsed.checkpoints.map((c, i) => (
                                      <li key={i}>{c}</li>
                                    ))}
                                  </ul>
                                )}
                              </div>

                              {!insightParsed && (
                                <pre className="whitespace-pre-wrap text-xs leading-relaxed text-gray-800">
                                  {aiInsight}
                                </pre>
                              )}
                            </div>
                          )}
                        </>
                      )}
					  
					  <div className="mt-4 text-[11px] text-gray-400 border-t border-gray-100 pt-2">
                        * 본 내용은 투자 권유가 아니라, 경제 일정을 이해하기 위한 일반적인 설명입니다.
                      </div>
					</div>
				  </>
				)}
              </div>
            </aside>
          )}
        </div>
      </main>
    </div>
  );
};

export default EconomicCalendarPage;
