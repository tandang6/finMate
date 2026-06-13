import React, { useState, useEffect, useRef } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, ComposedChart 
} from 'recharts';
import { 
  Sun, TrendingUp, Bell, Search, User, 
  ArrowRight, Brain, Calendar, ShieldAlert, Zap, LogOut, ChevronRight, CheckCircle, ClipboardList
} from 'lucide-react';
import { Routes, Route, Link } from 'react-router-dom';
import EconomicCalendarPage from './pages/calendar';
import FirstPurchasePlanner from './pages/planner';
import MyPlansPage from './pages/my-plans';
import StrategiesPage from './pages/strategies';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000";

// --- [DATA] 목업 데이터 (백엔드 없이 작동하기 위한 가짜 데이터) ---

const MOCK_WEATHER = {
  weather: "Sunny",
  headline: "금리 인하 기대감에\n시장에 훈풍이 불어요! 🍃",
  summary: "미국 CPI가 예상보다 낮게 발표되면서 시장의 공포 심리가 크게 줄어들었습니다. 특히 성장주 위주의 포트폴리오를 가진 투자자에게 유리한 환경입니다.",
  indices: [
    { name: "KOSPI", value: "2,750.45", change: 1.2 },
    { name: "KOSDAQ", value: "890.12", change: 0.8 },
    { name: "USD/KRW", value: "1,320.50", change: -0.5 },
    { name: "국고채 3년", value: "3.45%", change: -0.02 }
  ]
};

const MOCK_MACRO_CHART = [
  { date: "1월", rate: 3.50, stock: 2500, comment: "동결 기대감" },
  { date: "2월", rate: 3.50, stock: 2650, comment: "외인 매수" },
  { date: "3월", rate: 3.75, stock: 2480, comment: "긴축 공포" },
  { date: "4월", rate: 3.75, stock: 2520, comment: "저가 매수" },
  { date: "5월", rate: 3.75, stock: 2600, comment: "반도체 반등" },
  { date: "6월", rate: 3.50, stock: 2750, comment: "피벗 기대" },
];

const MOCK_NEWS = [
  {
    id: 1, tag: "거시경제", title: "미 연준 파월 의장, '연내 금리 인하' 시사", 
    summary: "FOMC 기자회견에서 인플레이션 둔화세가 뚜렷하다며 연내 피벗 가능성을 언급했습니다.",
    impact: "Positive", aiContext: "금리 인하는 기업의 이자 부담을 줄여주기 때문에 주식 시장에는 강력한 호재입니다."
  },
  {
    id: 2, tag: "반도체", title: "삼성전자, 차세대 HBM 공급 계약 체결", 
    summary: "글로벌 AI 빅테크 기업과 대규모 메모리 반도체 공급 계약을 논의 중이라는 소식입니다.",
    impact: "Positive", aiContext: "AI 산업 성장의 직접적인 수혜를 입어 반도체 섹터 전반의 상승이 예상됩니다."
  },
  {
    id: 3, tag: "환율", title: "달러 강세 주춤, 환율 1320원대 안착", 
    summary: "안전자산 선호 심리가 완화되며 원화 가치가 소폭 상승했습니다.",
    impact: "Neutral", aiContext: "환율 안정은 외국인 수급에 긍정적이지만, 수출 기업의 이익에는 변수가 될 수 있습니다."
  }
];

// --- [COMPONENT] 1. 로그인 화면 ---
const LoginScreen = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsLoading(true);
    // 로그인 시뮬레이션 (1초 딜레이)
    setTimeout(() => {
      setIsLoading(false);
      onLogin({ name: "김핀트", email: email || "user@finmate.com" });
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8 font-sans animate-in fade-in duration-700">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="bg-indigo-600 w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg mx-auto mb-6 transform transition hover:scale-105 hover:rotate-3">
          <TrendingUp className="text-white w-10 h-10" />
        </div>
        <h2 className="text-3xl font-extrabold text-gray-900 tracking-tight">Fin-Mate</h2>
        <p className="mt-2 text-base text-gray-600">
          데이터 기반의 똑똑한 금융 친구
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-10 shadow-xl rounded-2xl border border-gray-100">
          <form className="space-y-6" onSubmit={handleSubmit}>
            <div>
              <label className="block text-sm font-bold text-gray-700 mb-1">이메일</label>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition" placeholder="example@finmate.com" />
            </div>
            <div>
              <label className="block text-sm font-bold text-gray-700 mb-1">비밀번호</label>
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition" placeholder="••••••••" />
            </div>
            <button type="submit" disabled={isLoading} className="w-full flex justify-center py-3 px-4 border border-transparent rounded-xl shadow-sm text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-all transform hover:-translate-y-0.5 disabled:opacity-70 disabled:cursor-not-allowed">
              {isLoading ? "로그인 중..." : "시작하기"}
            </button>
          </form>
          <div className="mt-6 text-center text-xs text-gray-400">
            * 데모 버전입니다. 아무 이메일이나 입력하세요.
          </div>
        </div>
      </div>
    </div>
  );
};

// --- [COMPONENT] 2. 헤더 ---
const Header = ({ user, onLogout }) => {
  const [showMenu, setShowMenu] = useState(false);
  return (
    <header className="bg-white/80 backdrop-blur-md border-b border-gray-100 sticky top-0 z-50 px-6 py-3 flex items-center justify-between shadow-sm">
      <Link to="/" className="flex items-center gap-2 cursor-pointer group">
        <div className="bg-indigo-600 w-9 h-9 rounded-xl flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform">
          <TrendingUp className="text-white w-5 h-5" />
        </div>
        <span className="text-xl font-bold text-gray-800 tracking-tight group-hover:text-indigo-600 transition-colors">Fin-Mate</span>
      </Link>
      
      <div className="hidden md:flex items-center bg-gray-100/80 rounded-full px-5 py-2.5 w-96 focus-within:bg-white focus-within:ring-2 focus-within:ring-indigo-100 transition-all border border-transparent focus-within:border-indigo-200">
        <Search className="w-4 h-4 text-gray-400 mr-2" />
        <input type="text" placeholder="종목, 뉴스, 경제 용어 검색..." className="bg-transparent border-none outline-none text-sm w-full placeholder-gray-400" />
      </div>

      <div className="flex items-center gap-4">
		<Link
          to="/calendar"
          className="hidden md:inline-flex items-center text-sm font-medium 
                     text-gray-600 hover:text-indigo-600 transition-colors"
        >
          <Calendar className="w-4 h-4 mr-1" />
          주요 경제 일정
        </Link>
        <Link
          to="/strategies"
          className="hidden md:inline-flex items-center text-sm font-medium
                     text-gray-600 hover:text-indigo-600 transition-colors"
        >
          <Zap className="w-4 h-4 mr-1" />
          전략 탐색
        </Link>
        <Link
          to="/my-plans"
          className="hidden md:inline-flex items-center text-sm font-medium
                     text-gray-600 hover:text-indigo-600 transition-colors"
        >
          <ClipboardList className="w-4 h-4 mr-1" />
          내 계획
        </Link>
        <button className="relative p-2 hover:bg-gray-100 rounded-full transition-colors group">
          <Bell className="w-5 h-5 text-gray-600 group-hover:text-indigo-600 transition-colors" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border border-white"></span>
        </button>
        
        <div className="relative">
          <button onClick={() => setShowMenu(!showMenu)} className="flex items-center gap-2 hover:bg-gray-50 p-1.5 rounded-full transition-colors border border-transparent hover:border-gray-200">
            <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-700 font-bold border border-indigo-200">
              {user?.name?.[0]}
            </div>
            <span className="text-sm font-bold text-gray-700 hidden md:block">{user?.name}</span>
          </button>
          
          {showMenu && (
            <div className="absolute right-0 mt-2 w-56 bg-white rounded-2xl shadow-xl border border-gray-100 py-2 animate-in fade-in slide-in-from-top-2 z-50">
              <div className="px-4 py-3 border-b border-gray-50">
                <p className="text-xs text-gray-400 mb-1">접속 계정</p>
                <p className="text-sm font-bold text-gray-800 truncate">{user?.email}</p>
              </div>
              <Link
                to="/strategies"
                onClick={() => setShowMenu(false)}
                className="w-full text-left px-4 py-3 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2 transition-colors"
              >
                <Zap className="w-4 h-4" /> 전략 탐색
              </Link>
              <Link
                to="/my-plans"
                onClick={() => setShowMenu(false)}
                className="w-full text-left px-4 py-3 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2 transition-colors"
              >
                <ClipboardList className="w-4 h-4" /> 내 계획 보기
              </Link>
              <button onClick={onLogout} className="w-full text-left px-4 py-3 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors">
                <LogOut className="w-4 h-4" /> 로그아웃
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

// --- [COMPONENT] 3. 시장 날씨 ---
const MarketWeather = ({ data }) => {
  return (
    <div className="bg-gradient-to-br from-indigo-600 to-blue-500 rounded-[2rem] p-8 text-white mb-8 shadow-xl shadow-indigo-200/50 relative overflow-hidden group hover:shadow-2xl transition-shadow duration-300">
      <div className="relative z-10">
        <div className="flex items-center gap-2 mb-4 bg-white/20 w-fit px-4 py-1.5 rounded-full text-xs font-bold backdrop-blur-sm border border-white/10 shadow-inner">
          <Sun className="w-3.5 h-3.5" />
          <span>오늘의 시장 날씨: {data.weather}</span>
        </div>
        <h2 className="text-3xl md:text-4xl font-extrabold mb-4 leading-tight whitespace-pre-line tracking-tight">{data.headline}</h2>
        <p className="text-indigo-100 mb-10 max-w-2xl text-sm md:text-base opacity-90 leading-relaxed font-medium">{data.summary}</p>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {data.indices.map((item, idx) => (
            <div key={idx} className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/10 hover:bg-white/20 transition cursor-pointer group/card">
              <p className="text-xs text-indigo-200 mb-1 font-medium">{item.name}</p>
              <div className="flex items-end justify-between">
                <span className="text-xl font-bold tracking-tight">{item.value}</span>
                <span className={`text-xs font-bold px-2 py-1 rounded-lg flex items-center gap-1 ${
                  item.change > 0 ? 'bg-red-500/20 text-red-100' : 'bg-blue-500/20 text-blue-100'
                }`}>
                  {item.change > 0 ? '▲' : '▼'} {Math.abs(item.change)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
      {/* 배경 장식 */}
      <div className="absolute -top-20 -right-20 text-[20rem] opacity-5 rotate-12 select-none pointer-events-none transition-transform duration-700 group-hover:rotate-[20deg]">☀️</div>
      <div className="absolute bottom-0 left-0 w-full h-1/2 bg-gradient-to-t from-black/10 to-transparent pointer-events-none"></div>
    </div>
  );
};

// --- [COMPONENT] 4. AI 멘토 채팅 (프론트엔드 + 백엔드 연동 버전) ---
const AIMentorChat = () => {
  const [mode, setMode] = useState('easy');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const suggestions = mode === 'easy' 
    ? ["금리가 오르면 왜 주식이 떨어져?", "지금 삼성전자 사도 돼?", "환율이랑 주식은 무슨 관계야?"]
    : ["반도체 섹터 밸류에이션 분석", "FOMC 피벗 시점 전망", "스태그플레이션 리스크 진단"];


  // 모드 변경 시 초기 메시지
  useEffect(() => {
    const initialMsg = mode === 'easy' 
      ? "안녕하세요! 저는 주린이님을 위한 AI 멘토예요. 어려운 금융 용어가 있다면 언제든 물어봐 주세요! 😊"
      : "안녕하십니까. 데이터 기반 시장 분석 모드입니다. 분석이 필요한 거시 지표나 종목에 대해 질의하십시오.";
    setMessages([{ role: 'ai', text: initialMsg }]);
  }, [mode]);

  // 🔗 백엔드(FastAPI) /api/chat 호출 함수
  const callChatAPI = async (mode, message, historyMessages) => {
    // 최근 9개만 잘라서 history로 보냄 (백엔드도 한 번 더 방어적으로 자르지만 여기서도 슬라이스)
    const history = historyMessages.slice(-9);

    const res = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode,          // "easy" | "pro"
        message,       // 현재 질문
        history,       // [{ role: "user" | "ai", text: "..." }, ...]
      }),
    });

    if (!res.ok) {
      throw new Error("Chat API error");
    }

    const data = await res.json();
    return data.reply;  // main.py에서 ChatResponse(reply="...")로 보내는 값
  };

  const handleSendMessage = async (text = input) => {
  const messageText = typeof text === 'string' ? text : input;
  if (!messageText.trim()) return;

  const userMsg = { role: 'user', text: messageText };

  // 🔹 백엔드로 보낼 history: 이전 메시지들만
  const historyForAPI = [...messages].slice(-9);

  // 화면에는 유저 메시지 먼저 추가
  setMessages(prev => [...prev, userMsg]);
  setInput('');
  setIsLoading(true);

  try {
    const responseText = await callChatAPI(mode, messageText, historyForAPI);

    setMessages(prev => [
      ...prev,
      { role: 'ai', text: responseText },
    ]);
  } catch (err) {
    console.error(err);
    setMessages(prev => [
      ...prev,
      { role: 'ai', text: "백엔드 응답 중 오류가 발생했어요 😢" },
    ]);
  } finally {
    setIsLoading(false);
  }
};


  return (
    <div className="bg-white rounded-[1.5rem] border border-gray-100 shadow-xl shadow-gray-200/50 flex flex-col h-[600px] relative overflow-hidden transition-all hover:shadow-2xl">
      {/* 헤더 */}
      <div className="p-5 border-b border-gray-100 bg-white/50 backdrop-blur flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-50 p-2 rounded-xl border border-indigo-100">
            <Brain className="w-5 h-5 text-indigo-600" />
          </div>
          <div>
            <h3 className="font-bold text-gray-800 text-sm">AI 금융 멘토</h3>
            <p className="text-[10px] text-gray-400 font-medium">
              Online • FinMate AI
            </p>
          </div>
        </div>
        <div className="flex bg-gray-100 p-1 rounded-xl cursor-pointer text-xs font-bold select-none relative">
          <div
            onClick={() => setMode('easy')}
            className={`px-4 py-2 rounded-lg transition-all z-10 ${
              mode === 'easy'
                ? 'bg-white text-indigo-600 shadow-sm text-shadow'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            초보
          </div>
          <div
            onClick={() => setMode('pro')}
            className={`px-4 py-2 rounded-lg transition-all z-10 ${
              mode === 'pro'
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            전문가
          </div>
        </div>
      </div>

      {/* 메시지 영역 */}
      <div className="flex-1 p-5 overflow-y-auto space-y-5 bg-gray-50/50 scroll-smooth">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex gap-3 ${
              msg.role === 'user' ? 'flex-row-reverse' : ''
            } animate-in fade-in slide-in-from-bottom-4 duration-500`}
          >
            <div
              className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm border ${
                msg.role === 'ai'
                  ? 'bg-white border-indigo-100 text-indigo-600'
                  : 'bg-indigo-600 border-indigo-600 text-white'
              }`}
            >
              {msg.role === 'ai' ? <Brain size={18} /> : <User size={18} />}
            </div>
            <div
              className={`p-4 rounded-2xl text-sm max-w-[80%] leading-relaxed shadow-sm whitespace-pre-wrap ${
                msg.role === 'ai'
                  ? 'bg-white text-gray-700 rounded-tl-none border border-gray-100'
                  : 'bg-indigo-600 text-white rounded-tr-none'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3 animate-in fade-in">
            <div className="w-9 h-9 rounded-full bg-white border border-indigo-100 flex items-center justify-center flex-shrink-0 text-indigo-600 shadow-sm">
              <Brain size={18} />
            </div>
            <div className="bg-white px-4 py-3 rounded-2xl rounded-tl-none border border-gray-100 flex items-center gap-1.5 shadow-sm">
              <div
                className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"
                style={{ animationDelay: '0s' }}
              ></div>
              <div
                className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"
                style={{ animationDelay: '0.1s' }}
              ></div>
              <div
                className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"
                style={{ animationDelay: '0.2s' }}
              ></div>
            </div>
          </div>
        )}

        {/* 추천 질문 칩 */}
        {!isLoading &&
          messages.length > 0 &&
          messages[messages.length - 1].role === 'ai' && (
            <div className="flex flex-wrap gap-2 pl-12 pt-1 animate-in fade-in slide-in-from-bottom-2">
              {suggestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleSendMessage(q)}
                  className="text-xs bg-white border border-indigo-100 text-indigo-600 px-3 py-1.5 rounded-full hover:bg-indigo-50 hover:border-indigo-200 transition shadow-sm hover:shadow-md font-medium"
                >
                  {q}
                </button>
              ))}
            </div>
          )}
      </div>

      {/* 입력창 */}
      <div className="p-4 bg-white border-t border-gray-100">
        <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 px-4 py-2.5 rounded-full focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-100 transition-all shadow-inner">
          <input
            className="bg-transparent outline-none w-full text-sm placeholder-gray-400"
            placeholder={mode === 'easy' ? "궁금한 내용을 입력하세요..." : "분석 요청..."}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !isLoading && handleSendMessage()}
            disabled={isLoading}
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={isLoading || !input.trim()}
            className="bg-indigo-600 w-8 h-8 rounded-full flex items-center justify-center text-white hover:bg-indigo-700 transition transform active:scale-95 disabled:bg-gray-300 disabled:cursor-not-allowed shadow-md"
          >
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
};

// --- [PAGE] 대시보드 페이지 ---
const DashboardPage = ({ marketWeatherData, macroData, macroInsight, newsWeather, calendarEvents, logicAlerts }) => {
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);

  const upcomingEvents = (calendarEvents || [])
    .filter((ev) => ev?.datetime && new Date(ev.datetime) >= todayStart)
    .sort((a, b) => new Date(a.datetime) - new Date(b.datetime))
    .slice(0, 3);
  return (
    <main className="max-w-7xl mx-auto px-4 lg:px-6 py-8 animate-in fade-in duration-500">
        {/* 상단 날씨 섹션 */}
        <MarketWeather data={marketWeatherData} />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* [LEFT] 차트 & 뉴스 (8칸) */}
          <div className="lg:col-span-8 space-y-8">
            {/* 1. 도미노 차트 */}
            <section className="bg-white p-6 md:p-8 rounded-[1.5rem] border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                <div>
                  <h3 className="font-bold text-xl flex items-center gap-2 text-gray-900">
                    <TrendingUp className="text-indigo-600" /> 거시경제 도미노 효과
                  </h3>
                  <p className="text-sm text-gray-500 mt-1">금리와 주가의 상관관계를 AI가 분석합니다.</p>
                </div>
                <div className="flex gap-2 text-xs font-bold bg-gray-50 p-1 rounded-lg">
                  <span className="flex items-center gap-1.5 px-3 py-1.5 bg-white rounded-md shadow-sm border border-gray-100 text-gray-700"><div className="w-2.5 h-2.5 rounded-full bg-red-400"></div>KOSPI</span>
                  <span className="flex items-center gap-1.5 px-3 py-1.5 text-gray-500"><div className="w-2.5 h-2.5 rounded-full bg-indigo-500"></div>기준금리</span>
                </div>
              </div>
              
              <div className="h-[350px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={macroData} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorStock" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#F87171" stopOpacity={0.15}/>
                        <stop offset="95%" stopColor="#F87171" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F3F4F6" />
                    <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{fontSize:12, fill:'#9CA3AF', dy: 10}} />
                    <YAxis yAxisId="left" orientation="left" domain={[2000, 3000]} axisLine={false} tickLine={false} tick={{fontSize:12, fill:'#9CA3AF'}} />
                    <YAxis yAxisId="right" orientation="right" domain={[0, 5]} axisLine={false} tickLine={false} tick={{fontSize:12, fill:'#9CA3AF'}} />
                    <Tooltip 
                      contentStyle={{borderRadius:'16px', border:'none', boxShadow:'0 10px 25px -5px rgba(0,0,0,0.1)', padding:'12px'}} 
                      itemStyle={{fontSize:'12px', fontWeight:'bold'}}
                    />
                    <Area yAxisId="left" type="monotone" dataKey="stock" name="KOSPI" fill="url(#colorStock)" stroke="#F87171" strokeWidth={3} />
                    <Line yAxisId="right" type="monotone" dataKey="rate" name="금리(%)" stroke="#6366F1" strokeWidth={3} dot={{r:4, strokeWidth:2, fill:'#fff'}} activeDot={{r: 6}} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              
              <div className="mt-6 bg-indigo-50/50 p-4 rounded-2xl border border-indigo-100 flex gap-4 items-start">
                <div className="bg-white p-2 rounded-xl shadow-sm border border-indigo-50"><Brain className="text-indigo-600 w-5 h-5" /></div>
                <div>
                  <p className="text-sm text-indigo-900 leading-relaxed">
                    <strong>AI Analyst 분석:</strong>{" "}
                    {macroInsight
                      ? macroInsight
                      : "최근 금리와 KOSPI 흐름을 바탕으로 시장을 요약하고 있습니다."}
                  </p>
                </div>
              </div>
            </section>

            {/* 2. 뉴스 피드 */}
            <section>
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-bold text-xl flex items-center gap-2 text-gray-900">
                  <Zap className="text-yellow-500 fill-yellow-500" /> 오늘의 핵심 이슈
                </h3>
                <button className="text-sm text-indigo-600 font-bold hover:bg-indigo-50 px-3 py-1.5 rounded-full transition">전체보기 <ChevronRight className="inline w-4 h-4" /></button>
              </div>
              <div className="grid md:grid-cols-2 gap-5">
                {newsWeather?.cards?.map((card, idx) => (
                  <div
                    key={idx}
                    className="bg-white p-6 rounded-[1.5rem] border border-gray-100 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all cursor-pointer group flex flex-col h-full"
                  >
                    <div className="flex justify-between mb-4">
                      {/* 카테고리 태그 */}
                      <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-lg border border-indigo-100">
                        {card.category}
                      </span>

                      {/* 임팩트 배지 대신 'AI 분석' 라벨 */}
                      <span className="text-[10px] font-bold px-2.5 py-1 rounded-full bg-gray-100 text-gray-600 border border-gray-200">
                        AI 분석
                      </span>
                    </div>

                    {/* 뉴스 제목 */}
                    <h4 className="font-bold text-lg text-gray-800 mb-2 group-hover:text-indigo-600 transition leading-snug">
                      {card.title}
                    </h4>

                    {/* 한 줄 요약 */}
                    <p className="text-sm text-gray-500 mb-2 line-clamp-2 leading-relaxed">
                      {card.summary}
                    </p>

                    <a
                      href={card.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-indigo-500 underline inline-block mb-3"   // ← 여기!
                    >
                      뉴스 원문 보기 →
                    </a>


                    {/* 하단 AI 인사이트 + 링크 */}
                    <div className="mt-auto bg-gray-50 p-4 rounded-2xl border border-gray-100 relative">
                      <div className="absolute -top-3 left-4 bg-white border border-gray-200 text-[10px] px-2 py-0.5 rounded-full flex gap-1 shadow-sm font-bold text-gray-600 items-center">
                        <Brain size={10} /> AI 해석
                      </div>
                      <p className="text-xs text-gray-700 mt-1 font-medium leading-relaxed">
                        {card.insight}
                      </p>

                      
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>

          {/* [RIGHT] 사이드바 (4칸) */}
          <div className="lg:col-span-4 space-y-8">
            {/* 3. 로직 알림 */}
            <section className="bg-white p-6 rounded-[1.5rem] border border-gray-100 shadow-sm hover:shadow-md transition">
              <div className="flex justify-between items-center mb-5">
                <h3 className="font-bold text-gray-800 flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-indigo-600" /> 내 로직 알림
                </h3>
                <button className="text-xs font-bold bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-full hover:bg-indigo-100 transition">+ 추가</button>
              </div>
              <div className="space-y-4">
                {logicAlerts.length === 0 && (
                  <div className="p-4 bg-gray-50 border border-gray-100 rounded-2xl text-sm font-medium text-gray-500">
                    로직 알림 데이터를 불러오는 중입니다.
                  </div>
                )}
                {logicAlerts.map((alert) => {
                  const isUnavailable = alert.status === "unavailable";
                  const cardClass = alert.triggered
                    ? "bg-red-50/80 border-red-100 shadow-sm"
                    : "bg-white border-gray-100 opacity-80 hover:opacity-100";
                  const messageClass = alert.triggered
                    ? "text-red-700 font-bold"
                    : isUnavailable
                      ? "text-gray-500 font-medium"
                      : "text-gray-500 font-medium";
                  return (
                    <div
                      key={alert.id}
                      className={`p-4 border rounded-2xl flex gap-3 items-start transition ${cardClass}`}
                    >
                      {alert.triggered ? (
                        <div className="w-2.5 h-2.5 mt-1.5 bg-red-500 rounded-full flex-shrink-0 shadow-[0_0_8px_rgba(239,68,68,0.6)]"></div>
                      ) : (
                        <CheckCircle className={`w-4 h-4 mt-0.5 ${isUnavailable ? "text-gray-300" : "text-green-500"}`} />
                      )}
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[10px] font-bold text-gray-500 bg-white border border-gray-200 px-1.5 py-0.5 rounded">
                            {alert.condition_label}
                          </span>
                        </div>
                        <p className={`text-sm leading-tight ${messageClass}`}>
                          {alert.message}
                        </p>
                        {alert.as_of_date && (
                          <p className="text-[10px] text-gray-400 mt-1">
                            기준일 {alert.as_of_date}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
            
            {/* 4. AI 챗봇 */}
            <AIMentorChat />
            
            {/* 5. 경제 캘린더 */}
            <section className="bg-white p-6 rounded-[1.5rem] border border-gray-100 shadow-sm">
              <div className="flex items-center justify-between mb-5">
                <h3 className="font-bold flex gap-2 items-center text-gray-800">
                  <Calendar className="w-5 h-5 text-indigo-600"/> 주요 경제 일정
                </h3>
                <Link to="/calendar" className="text-xs font-bold text-indigo-600 hover:bg-indigo-50 px-3 py-1.5 rounded-full transition">
                  전체보기 <ChevronRight className="inline w-3 h-3" />
                </Link>
              </div>
              <div className="space-y-3">
                {upcomingEvents.length === 0 && (
                  <p className="text-xs text-gray-400 text-center py-4">예정된 일정이 없습니다.</p>
                )}
                {upcomingEvents.map((ev) => {
                  const d = new Date(ev.datetime);
                  const todayMidnight = new Date();
                  todayMidnight.setHours(0, 0, 0, 0);
                  const tomorrowMidnight = new Date(todayMidnight);
                  tomorrowMidnight.setDate(tomorrowMidnight.getDate() + 1);
                  const isToday = d >= todayMidnight && d < tomorrowMidnight;
                  const dayNum = d.getDate();
                  const importanceStyle =
                    ev.importance === "very_high"
                      ? "bg-red-50 text-red-600 border-red-100"
                      : "bg-orange-50 text-orange-600 border-orange-100";
                  const importanceText =
                    ev.importance === "very_high" ? "매우중요" : "중요";
                  return (
                    <Link
                      key={ev.id}
                      to="/calendar"
                      className="flex items-center justify-between group cursor-pointer hover:bg-gray-50 rounded-2xl p-1 -mx-1 transition"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`flex flex-col items-center px-3 py-2 rounded-xl border transition ${isToday ? "bg-gray-900 border-gray-900 text-white" : "bg-gray-50 border-gray-100 group-hover:bg-indigo-50 group-hover:border-indigo-100"}`}>
                          <span className={`text-[10px] font-bold ${isToday ? "text-gray-300" : "text-gray-400 group-hover:text-indigo-400"}`}>
                            {isToday ? "TODAY" : `${d.getMonth() + 1}월`}
                          </span>
                          <span className={`text-lg font-bold ${isToday ? "text-white" : "text-gray-800 group-hover:text-indigo-700"}`}>
                            {dayNum}
                          </span>
                        </div>
                        <div>
                          <p className="font-bold text-sm text-gray-800 line-clamp-1">{ev.companyName}</p>
                          <p className="text-xs text-gray-400 line-clamp-1">{ev.title}</p>
                        </div>
                      </div>
                      <span className={`border text-[10px] font-bold px-2 py-1 rounded-lg ${importanceStyle}`}>
                        {importanceText}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </section>
          </div>

        </div>
      </main>
  );
};

const FinMateApp = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState(null);

  const handleLogin = (userInfo) => { setIsLoggedIn(true); setUser(userInfo); };
  const handleLogout = () => { setIsLoggedIn(false); setUser(null); };

  const [calendarEvents, setCalendarEvents] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/calendar/earnings-demo`)
      .then((r) => r.ok ? r.json() : [])
      .then((data) => setCalendarEvents(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, []);

   // ✅ 도미노 차트 데이터 상태
  const [macroData, setMacroData] = useState(MOCK_MACRO_CHART);
  
  useEffect(() => {
    const fetchMacroData = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/macro-chart`);
        if (!res.ok) {
          throw new Error("macro-chart api error");
        }

        const data = await res.json();
        // data = [{ date: "2024.01", rate: 3.5, stock: 2500.2 }, ...]
        setMacroData(data);
      } catch (e) {
        console.error("매크로 차트 데이터 불러오기 실패:", e);
        // 실패해도 macroData는 기존 MOCK_MACRO_CHART 유지
      }
    };
    
    fetchMacroData();
  }, []);

const [macroInsight, setMacroInsight] = useState("");

  useEffect(() => {
    const fetchMacroInsight = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/macro-insight`);
        if (!res.ok) {
          throw new Error("macro-insight api error");
        }
        const data = await res.json();
        setMacroInsight(data.insight || "");
      } catch (e) {
        console.error("매크로 인사이트 불러오기 실패:", e);
        setMacroInsight("");
      }
    };
    fetchMacroInsight();
  }, []);


    // ✅ 시장 날씨(상단 4개 카드) 데이터 상태
  const [weatherData, setWeatherData] = useState(MOCK_WEATHER);

  // ✅ 뉴스 + 시장 날씨(LLM 결과) 상태
  const [newsWeather, setNewsWeather] = useState(null);

  useEffect(() => {
    const fetchWeather = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/market-weather`);
        if (!res.ok) {
          throw new Error("market-weather api error");
        }

        const data = await res.json();
        // data = { indices: [ { name, value, change }, ... ] }

        setWeatherData(prev => ({
          ...prev,                 // 기존 weather/headline/summary는 그대로
          indices: data.indices ?? prev.indices,  // indices만 실데이터로 교체
        }));
      } catch (e) {
        console.error("시장 날씨 데이터 불러오기 실패:", e);
        // 실패하면 MOCK_WEATHER 유지
      }
    };

    fetchWeather();
  }, []);


  // ✅ 뉴스 + LLM 시장 날씨 가져오기
  useEffect(() => {
    const fetchNewsWeather = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/news-weather`);
        if (!res.ok) {
          throw new Error("news-weather api error");
        }

        const data = await res.json();
        // data = { weather: { line1, line2, line3 }, cards: [...] }
        setNewsWeather(data);
      } catch (e) {
        console.error("뉴스/날씨 데이터 불러오기 실패:", e);
      }
    };

    fetchNewsWeather();
  }, []);

  const [logicAlerts, setLogicAlerts] = useState([]);

  useEffect(() => {
    const fetchLogicAlerts = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/logic-alerts`);
        if (!res.ok) {
          throw new Error("logic-alerts api error");
        }
        const data = await res.json();
        setLogicAlerts(Array.isArray(data) ? data : []);
      } catch (e) {
        console.error("로직 알림 데이터 불러오기 실패:", e);
        setLogicAlerts([
          {
            id: "logic-alerts-unavailable",
            status: "unavailable",
            triggered: false,
            condition_label: "로직 알림",
            message: "실제 시장 데이터를 불러오지 못했습니다.",
          },
        ]);
      }
    };

    fetchLogicAlerts();
  }, []);

  if (!isLoggedIn) return <LoginScreen onLogin={handleLogin} />;


// ✅ 상단 MarketWeather 컴포넌트에 넘길 데이터 합치기
  const marketWeatherData = {
    weather: newsWeather
      ? (newsWeather.weather.line1 || "").replace("오늘 날씨는 : ", "")
      : weatherData.weather,
    headline: newsWeather ? newsWeather.weather.line2 : weatherData.headline,
    summary: newsWeather ? newsWeather.weather.line3 : weatherData.summary,
    // 지수 데이터는 기존 /api/market-weather 결과 사용
    indices: weatherData.indices,
  };

  return (
    <div className="min-h-screen bg-[#F8F9FD] font-sans text-gray-800 pb-20 selection:bg-indigo-100 selection:text-indigo-700">
      <Header user={user} onLogout={handleLogout} />
	  
      <Routes>
        <Route
          path="/"
          element={
            <DashboardPage
              marketWeatherData={marketWeatherData}
              macroData={macroData}
              macroInsight={macroInsight}
              newsWeather={newsWeather}
              calendarEvents={calendarEvents}
              logicAlerts={logicAlerts}
            />
          }
        />
        <Route path="/calendar" element={<EconomicCalendarPage />} />
        <Route path="/strategies" element={<StrategiesPage />} />
        <Route path="/planner" element={<FirstPurchasePlanner />} />
        <Route path="/my-plans" element={<MyPlansPage />} />
      </Routes>
    </div>
  );
};

export default FinMateApp;
