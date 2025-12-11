import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Clock,
  Flag,
  Info,
} from "lucide-react";

// -----------------------------
// 더미 데이터 (데모용 경제 일정)
// -----------------------------

const EVENTS = [
  {
    id: "2025-12-cpi-us-headline",
    title: "미국 CPI 발표 (헤드라인)",
    datetime: "2025-12-15T22:30:00",
    country: "US",
    type: "CPI",
    importance: "high",
    description: "전체 항목을 기준으로 한 소비자물가지수(헤드라인 CPI) 발표",
    asset: "all",
    extraContext: {
      isBeforeFomc: true,
    },
  },
  {
    id: "2025-12-cpi-us-core",
    title: "미국 근원 CPI 발표",
    datetime: "2025-12-15T22:30:00",
    country: "US",
    type: "CPI",
    importance: "very_high",
    description:
      "에너지·식품을 제외한 근원 CPI 발표. 연준이 특히 주목하는 물가 지표",
    asset: "all",
    extraContext: {
      isBeforeFomc: true,
    },
  },
  {
    id: "2025-12-fomc-rate",
    title: "FOMC 기준금리 결정 및 성명서",
    datetime: "2025-12-19T04:00:00",
    country: "US",
    type: "FOMC",
    importance: "very_high",
    description:
      "연방공개시장위원회(FOMC)의 기준금리 결정 및 통화정책 성명 발표",
    asset: "all",
    extraContext: {
      hasPressConference: true,
    },
  },
  {
    id: "2025-12-fomc-press",
    title: "파월 의장 기자회견",
    datetime: "2025-12-19T04:30:00",
    country: "US",
    type: "FOMC",
    importance: "very_high",
    description:
      "금리 결정 이후 파월 의장이 향후 통화정책 방향에 대해 설명하는 기자회견",
    asset: "all",
    extraContext: {
      hasPressConference: true,
    },
  },
  {
    id: "2025-12-us-nfp",
    title: "미국 비농업 고용지수 (NFP)",
    datetime: "2025-12-06T22:30:00",
    country: "US",
    type: "JOBS",
    importance: "high",
    description:
      "미국 고용 시장의 강도를 보여주는 핵심 지표. 임금 상승률 함께 발표",
    asset: "all",
  },
  {
    id: "2025-12-kr-gdp",
    title: "한국 3분기 GDP(속보치)",
    datetime: "2025-12-10T08:00:00",
    country: "KR",
    type: "GDP",
    importance: "medium",
    description: "한국 경제 성장률(3분기, 전년 대비/전분기 대비) 속보치 발표",
    asset: "all",
  },
  {
    id: "2025-12-10-samsung-earnings",
    title: "삼성전자 실적 발표",
    datetime: "2025-12-10T09:00:00",
    country: "KR",
    type: "GDP",
    importance: "high",
    description: "삼성전자 분기 실적 및 반도체 업황 코멘트",
    asset: "samsung",
  },
  {
    id: "2025-12-10-sk-earnings",
    title: "SK하이닉스 실적 발표",
    datetime: "2025-12-10T09:00:00",
    country: "KR",
    type: "GDP",
    importance: "high",
    description: "SK하이닉스 분기 실적 및 메모리 업황 코멘트",
    asset: "skhynix",
  },
];

// -----------------------------
// 자산 필터 옵션
// -----------------------------

const ASSETS = [
  { id: "all", label: "전체" },
  { id: "samsung", label: "삼성전자" },
  { id: "skhynix", label: "SK하이닉스" },
];

// -----------------------------
// 타입별 설명 템플릿
// -----------------------------

const EVENT_TEMPLATES = {
  CPI: {
    sectionWhat:
      "CPI(소비자물가지수)는 소비자가 실제로 체감하는 물가 상승률을 측정하는 대표적인 인플레이션 지표입니다.",
    sectionWhy:
      "인플레이션이 예상보다 높게 나오면 긴축(금리 인상) 우려가 커지고, 낮게 나오면 완화(금리 인하) 기대가 높아져서 주식·코인 등 위험자산에 큰 영향을 줍니다.",
    sectionRemind: [
      "숫자(전년 대비 %) 자체보다 '시장 예상치 대비 높았는지/낮았는지'가 더 중요합니다.",
      "헤드라인 vs 근원(Core) CPI 중, 최근에는 근원 지표에 시장이 더 민감하게 반응하는 구간이 자주 나타납니다.",
    ],
    sectionPrinciple: [
      "중요 인플레이션 발표 직전에는 단기 변동성이 커질 수 있어, 과도한 레버리지는 피하는 편이 일반적입니다.",
      "장기 투자자는 단 한 번의 CPI보다 인플레이션이 피크아웃했는지, 다시 올라가는지라는 '방향성'에 주목합니다.",
    ],
  },
  FOMC: {
    sectionWhat:
      "FOMC는 미국 중앙은행(연준)의 통화정책 회의로, 기준금리 결정과 향후 금리 경로에 대한 메시지를 발표하는 일정입니다.",
    sectionWhy:
      "달러 금리는 전 세계 금융시장의 기준 금리 역할을 하기 때문에, FOMC 결과는 주식·채권·코인 등 거의 모든 자산 가격에 파급 효과를 줄 수 있습니다.",
    sectionRemind: [
      "실제 금리 결정(동결/인상/인하)뿐 아니라, 점도표와 기자회견 발언 톤(매파/비둘기)이 함께 중요합니다.",
      "발표 전까지는 '기대감'이, 발표 직후에는 '현실과의 차이'가 가격을 움직입니다.",
    ],
    sectionPrinciple: [
      "단기 트레이딩 관점에서는 발표 직후 5~30분 구간의 급격한 변동성에 유의해야 합니다.",
      "중장기 투자자는 FOMC 한 번보다는 정책 기조가 완화/긴축 중 어디에 가까워지는지 흐름을 보는 것이 중요합니다.",
    ],
  },
  JOBS: {
    sectionWhat:
      "비농업 고용지수(NFP)는 미국의 일자리 증가 수를 보여주는 지표로, 고용 시장의 강도를 가늠하는 데 사용됩니다.",
    sectionWhy:
      "고용이 너무 강하면 임금·인플레이션 압력이 커질 수 있고, 너무 약하면 경기 침체 우려가 커지기 때문에, 연준의 정책 방향과 위험자산 선호도에 모두 영향을 줍니다.",
    sectionRemind: [
      "실제 수치뿐 아니라 실업률, 평균 시급 상승률까지 함께 발표되므로 종합적으로 보는 것이 좋습니다.",
      "발표 직후에는 첫 반응과 그 이후 재해석 구간에서 움직임이 다를 수 있습니다.",
    ],
    sectionPrinciple: [
      "단기 레버리지 포지션은 발표 직후 급격한 스파이크에 휩쓸릴 수 있어, 진입·청산 타이밍을 더 보수적으로 잡는 경우가 많습니다.",
      "중장기 투자자에게는 '고용이 둔화→연준 완화 기조'로 이어지는 흐름이 있는지 여부가 핵심입니다.",
    ],
  },
  GDP: {
    sectionWhat:
      "GDP(국내총생산)는 일정 기간 동안 한 나라에서 생산된 최종 재화와 서비스의 총합으로, 경제 성장률을 보여주는 지표입니다.",
    sectionWhy:
      "성장률이 너무 낮으면 경기 침체 리스크가, 너무 높으면 인플레이션과 긴축 리스크가 부각되며 자산시장 전반의 위험 선호에 영향을 줍니다.",
    sectionRemind: [
      "속보치는 이후 수정될 수 있어, 단기적으로 시장 반응이 과할 수 있습니다.",
      "전 분기 대비/전년 대비, 실질/명목 구분 등 세부 구성을 함께 보는 것이 좋습니다.",
    ],
    sectionPrinciple: [
      "장기 자산 배분 관점에서는 성장률이 구조적으로 둔화되는지 여부가 중요합니다.",
      "단기 트레이더는 GDP 발표보다, 발표 이후 금리·환율·주가지수의 반응을 함께 보는 경우가 많습니다.",
    ],
  },
};

// -----------------------------
// 유틸 함수들
// -----------------------------

function buildExtraSentences(event) {
  const extras = [];
  const ctx = event.extraContext || {};

  if (ctx.isBeforeFomc) {
    extras.push(
      "이번 지표는 FOMC 회의 직전에 발표되기 때문에, 연준이 어떤 스탠스를 취할지에 대한 시장의 기대를 더 크게 움직일 수 있습니다."
    );
  }

  if (ctx.hasPressConference) {
    extras.push(
      "발표 직후 이어지는 기자회견에서의 한 마디 한 마디가 시장 방향성을 바꾸는 경우가 많아, 텍스트 요약이나 주요 발언 정리를 함께 보는 것이 좋습니다."
    );
  }

  return extras;
}

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

function getDateKey(iso) {
  const d = new Date(iso);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// 🔹 달력 셀 생성
function buildCalendarCells(year, monthIndex) {
  const firstDay = new Date(year, monthIndex, 1);
  const firstWeekday = firstDay.getDay(); // 0=일요일
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();

  const cells = [];
  for (let i = 0; i < firstWeekday; i++) {
    cells.push({ day: null, dateKey: null });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const dateKey = `${year}-${String(monthIndex + 1).padStart(
      2,
      "0"
    )}-${String(d).padStart(2, "0")}`;
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

function buildExplanation(event) {
  const base = EVENT_TEMPLATES[event.type];
  if (!base) return null;

  return {
    title: event.title,
    datetime: event.datetime,
    sectionWhat: base.sectionWhat,
    sectionWhy: base.sectionWhy,
    sectionRemind: base.sectionRemind,
    sectionPrinciple: base.sectionPrinciple,
    sectionExtra: buildExtraSentences(event),
  };
}

// -----------------------------
// 페이지 컴포넌트
// -----------------------------

const EconomicCalendarPage = () => {
  // 오늘
  const today = new Date();
  const todayKey = getDateKey(today.toISOString());

  const [selectedAsset, setSelectedAsset] = useState("all");

  // 달력 연/월
  const [year, setYear] = useState(today.getFullYear());
  const [monthIndex, setMonthIndex] = useState(today.getMonth());

  // 날짜별 이벤트 그룹
  const eventsByDate = useMemo(() => {
    const map = {};
    EVENTS.forEach((ev) => {
      const key = getDateKey(ev.datetime);
      if (!map[key]) map[key] = [];
      map[key].push(ev);
    });

    Object.keys(map).forEach((k) => {
      map[k].sort((a, b) => {
        const order = { very_high: 3, high: 2, medium: 1, low: 0 };
        return order[b.importance] - order[a.importance];
      });
    });
    return map;
  }, []);

  const sortedDateKeys = useMemo(
    () => Object.keys(eventsByDate).sort(),
    [eventsByDate]
  );

  // 초기 선택 날짜: 오늘 일정 있으면 오늘, 없으면 첫 날짜
  const initialSelectedDateKey =
    sortedDateKeys.find((k) => k === todayKey) ?? sortedDateKeys[0] ?? null;

  const [selectedDateKey, setSelectedDateKey] = useState(
    initialSelectedDateKey
  );

  const [selectedEventId, setSelectedEventId] = useState(() => {
    if (!initialSelectedDateKey) return null;
    const all = eventsByDate[initialSelectedDateKey] || [];
    return all[0]?.id ?? null;
  });

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

  const selectedEvent =
    filteredEventsForSelectedDate.find((ev) => ev.id === selectedEventId) ||
    filteredEventsForSelectedDate[0] ||
    null;

  const explanation = selectedEvent ? buildExplanation(selectedEvent) : null;

  const handleSelectDate = (dateKey) => {
    setSelectedDateKey(dateKey);
    const events = eventsByDate[dateKey] || [];
    const filtered =
      selectedAsset === "all"
        ? events
        : events.filter((ev) => ev.asset === selectedAsset);
    setSelectedEventId(filtered[0]?.id || null);
  };

  const handleAssetChange = (assetId) => {
    setSelectedAsset(assetId);
    if (!selectedDateKey) return;
    const events = eventsByDate[selectedDateKey] || [];
    const filtered =
      assetId === "all"
        ? events
        : events.filter((ev) => ev.asset === assetId);
    setSelectedEventId(filtered[0]?.id || null);
  };

  const handleDayClick = (cell) => {
    if (!cell.dateKey) return;
    handleSelectDate(cell.dateKey);
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

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#F8F9FD]">
      <main className="max-w-7xl mx-auto px-4 lg:px-6 py-8">
        {/* 상단 헤더 */}
        <div className="flex items-start justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-xs font-semibold text-indigo-700 mb-3">
              <CalendarIcon className="w-4 h-4" />
              주요 경제 일정
            </div>
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2">
              시장을 흔드는 경제 이벤트 한 눈에 보기
            </h1>
            <p className="text-sm md:text-base text-gray-500 max-w-2xl">
              금리, 물가, 고용, 성장률 등 핵심 거시 지표 발표 일정을
              삼성전자·SK하이닉스 등 관심 자산 기준으로 정리해 보여줍니다.
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

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* LEFT: 달력 카드 */}
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

            {/* 요일 헤더 */}
            <div className="grid grid-cols-7 text-center text-[11px] text-gray-400 mb-2">
              {weekdays.map((w) => (
                <div key={w} className="py-1">
                  {w}
                </div>
              ))}
            </div>

            {/* 달력 셀 */}
            <div className="grid grid-cols-7 gap-1">
              {calendarCells.map((cell, idx) => {
                if (!cell.day) {
                  return (
                    <div key={idx} className="aspect-square rounded-xl" />
                  );
                }

                const eventsForDay =
                  (cell.dateKey && eventsByDate[cell.dateKey]) || [];
                const hasEvent = eventsForDay.length > 0;
                const isSelected = cell.dateKey === selectedDateKey;
                const isToday = cell.dateKey === todayKey;

                let baseClass =
                  "aspect-square rounded-xl border text-left text-[11px] px-1.5 py-1 flex flex-col justify-between transition-all";
                let stateClass = "bg-white border-gray-200 text-gray-700";

                if (hasEvent) {
                  stateClass =
                    "bg-indigo-50/40 border-indigo-200 text-gray-900";
                }
                if (isToday) {
                  stateClass =
                    "bg-gray-900 text-white border-gray-900 shadow-sm";
                }
                if (isSelected) {
                  stateClass =
                    "bg-indigo-100 text-indigo-900 border-indigo-500 shadow-sm ring-1 ring-indigo-300";
                }

                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleDayClick(cell)}
                    className={`${baseClass} ${stateClass} relative`}
                  >
                    {/* 날짜 숫자 */}
                    <div className="flex items-center justify-start">
                      <span className="font-semibold text-[11px]">
                        {cell.day}
                      </span>
                    </div>

                    {/* 일정 있는 날: 파란 점 */}
                    {hasEvent && (
					  <span
						className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-indigo-600"
					  />
					)}
                  </button>
                );
              })}
            </div>
          </section>

          {/* RIGHT: 이벤트 리스트 + 상세 설명 */}
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

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* 이벤트 리스트 */}
              <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-4 flex flex-col">
                <h3 className="text-sm font-semibold text-gray-800 mb-3">
                  선택한 날짜의 경제 일정
                </h3>

                {(!filteredEventsForSelectedDate ||
                  filteredEventsForSelectedDate.length === 0) && (
                  <div className="flex-1 flex items-center justify-center text-xs text-gray-400 text-center px-4">
                    선택한 날짜에는 현재 선택한 자산 기준으로 등록된 일정이
                    없습니다.
                    <br />
                    자산을{" "}
                    <span className="font-semibold text-gray-500">"전체"</span>
                    로 바꿔 전체 시장 일정을 확인해보세요.
                  </div>
                )}

                {filteredEventsForSelectedDate.length > 0 && (
                  <ul className="space-y-2 overflow-y-auto max-h-[420px] pr-1">
                    {filteredEventsForSelectedDate.map((event) => {
                      const { time } = formatDateTime(event.datetime);
                      const isActive = selectedEventId === event.id;

                      return (
                        <li key={event.id}>
                          <button
                            onClick={() => setSelectedEventId(event.id)}
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

              {/* 상세 설명 패널 */}
              <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-sm p-4 flex flex-col">
                <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-1.5">
                  <Info className="w-4 h-4 text-indigo-600" />
                  AI 스타일 해설
                </h3>

                {!selectedEvent || !explanation ? (
                  <div className="flex-1 flex items-center justify-center text-xs text-gray-400 text-center px-4">
                    왼쪽 캘린더에서 날짜를 선택하고,
                    <br />
                    보고 싶은 일정을 클릭하면 왜 중요한 일정인지, 어떤 점을
                    체크해야 하는지 요약해서 보여드립니다.
                  </div>
                ) : (
                  <div className="space-y-3 overflow-y-auto max-h-[420px] pr-1 text-sm">
                    <div>
                      <div className="text-xs text-gray-400 mb-1">
                        {formatDateTime(selectedEvent.datetime).date} ·{" "}
                        {formatDateTime(selectedEvent.datetime).time} ·{" "}
                        {selectedEvent.country}
                      </div>
                      <div className="font-semibold text-gray-900 mb-1">
                        {selectedEvent.title}
                      </div>
                    </div>

                    <div className="bg-indigo-50/60 border border-indigo-100 rounded-xl p-3 text-xs text-indigo-900 leading-relaxed">
                      <p className="font-semibold mb-1">
                        1. 이 일정, 무엇을 의미하나요?
                      </p>
                      <p>{explanation.sectionWhat}</p>
                    </div>

                    <div className="bg-amber-50/60 border border-amber-100 rounded-xl p-3 text-xs text-amber-900 leading-relaxed">
                      <p className="font-semibold mb-1">
                        2. 시장에 왜 중요한가요?
                      </p>
                      <p>{explanation.sectionWhy}</p>
                    </div>

                    <div className="bg-gray-50 border border-gray-100 rounded-xl p-3 text-xs text-gray-800 leading-relaxed">
                      <p className="font-semibold mb-1">
                        3. 체크 포인트 (발표 전후)
                      </p>
                      <ul className="list-disc list-inside space-y-0.5">
                        {explanation.sectionRemind.map((line, idx) => (
                          <li key={idx}>{line}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="bg-white border border-gray-100 rounded-xl p-3 text-xs text-gray-800 leading-relaxed">
                      <p className="font-semibold mb-1">
                        4. 투자 원칙 / 유의사항
                      </p>
                      <ul className="list-disc list-inside space-y-0.5">
                        {explanation.sectionPrinciple.map((line, idx) => (
                          <li key={idx}>{line}</li>
                        ))}
                      </ul>
                    </div>

                    {explanation.sectionExtra &&
                      explanation.sectionExtra.length > 0 && (
                        <div className="bg-sky-50 border border-sky-100 rounded-xl p-3 text-xs text-sky-900 leading-relaxed">
                          <p className="font-semibold mb-1">
                            + 추가로 참고하면 좋은 포인트
                          </p>
                          <ul className="list-disc list-inside space-y-0.5">
                            {explanation.sectionExtra.map((line, idx) => (
                              <li key={idx}>{line}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                    <div className="mt-2 text-[11px] text-gray-400 border-t border-gray-100 pt-2">
                      * 본 내용은 투자 권유가 아니라, 경제 일정을 이해하기 위한
                      일반적인 설명입니다.
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};

export default EconomicCalendarPage;
