# FinMate

FinMate는 금융 초보자가 뉴스, 거시경제 지표, 경제 일정처럼 흩어진 정보를 한 화면에서 이해하고 스스로 판단 근거를 정리할 수 있도록 돕는 금융 의사결정 지원 서비스입니다. React 프론트엔드와 FastAPI 백엔드로 구성되어 있으며, AI 금융 멘토, 시장 날씨, 거시경제 도미노 차트, 경제 일정 해설 기능을 제공합니다.

멘토링 이후 FinMate는 단순히 금융 정보를 보여주는 서비스가 아니라, 실제 운영 단계에서 발생할 수 있는 외부 API 장애, 호출 비용, 데이터 신뢰성, LLM 응답 안전성을 함께 고려하는 방향으로 보완했습니다. 특히 금융이라는 주제가 졸업작품에서 자주 다루어질 수 있다는 피드백을 반영해, 기능의 독특함보다 서비스가 안정적으로 동작하고 사용자가 AI 답변을 과신하지 않도록 만드는 구조를 기술적 차별점으로 정리했습니다.

기존의 "시장 이해" 기능 위에 한국 주식 입문자를 위한 **전략 기반 투자 계획 플래너**를 추가했습니다. 이 기능은 특정 종목이나 전략을 추천하지 않고, 사용자가 선택한 종목의 일봉 조건을 전략별로 점검한 뒤 계획을 검토하고 저장하도록 돕는 규칙 기반 프로토타입입니다.

## 데모 영상

![FinMate 전략 플래너 데모](./assets/strategy-planner-demo.gif)

[FinMate 전략 플래너 데모 GIF 보기](./assets/strategy-planner-demo.gif)

## 기능: 전략 기반 투자 계획 플래너

신규 기능은 `/strategies` -> `/planner` -> `/my-plans`로 이어지는 계획 작성 흐름입니다.

1. 사용자가 지원 종목을 선택합니다.
2. 서비스가 live 전략들의 조건, 필터, 가드레일을 일봉 데이터 기준으로 평가합니다.
3. 전략 카드를 "적용 가능", "지금은 조건 부족", "데이터 부족", "교육용", "보류" 상태로 나눠 보여줍니다.
4. 사용자가 하나의 평가 스냅샷을 선택하면 계획 검토 화면으로 이동합니다.
5. 사용자는 보유 계획과 한 줄 이유를 직접 입력하고, 필요한 경우에만 매수/손절/목표/비중 오버라이드 값을 추가합니다.
6. 저장된 계획은 My Plans에서 저장 당시의 평가 스냅샷 그대로 다시 확인할 수 있습니다.

이 흐름은 "지금 가장 좋은 전략"을 골라주는 추천 기능이 아니라, 현재 조건이 왜 충족되었거나 부족한지 확인하고 사용자가 자기 판단을 기록하게 만드는 계획 지원 기능입니다.

## 주요 화면

| 화면 | 경로 | 역할 |
| --- | --- | --- |
| 전략 탐색 | `/strategies` | 지원 종목을 선택하고 전략별 평가 상태를 카드로 비교합니다. |
| 계획 검토 및 저장 | `/planner` | 선택한 전략 평가 스냅샷을 검토하고 계획을 저장합니다. |
| 내 계획 | `/my-plans` | 저장된 전략 스냅샷, 오버라이드, 메모를 다시 확인하고 수정합니다. |

## 전략 평가 방식

V1 범위는 한국 주식, 일봉 데이터 기준입니다. 현재 live 평가 대상 전략은 다음 다섯 가지입니다.

| Live 전략 | 설명 |
| --- | --- |
| MA Support Retest | 상승 추세 중 이동평균 지지 재확인 구간을 점검합니다. |
| Resistance Breakout Retest | 기존 저항 돌파 이후 되돌림 지지 여부를 점검합니다. |
| Pullback | 상승 추세 안에서 단기 눌림목 조건을 점검합니다. |
| Darvas/Range Breakout | 박스권 또는 범위 돌파 조건을 점검합니다. |
| MA Reclaim | 주요 이동평균 회복 이후 유지 여부를 점검합니다. |

전략 카드는 다음 정보를 공통 형식으로 보여줍니다.

- 조건, 필터, 가드레일 충족 여부
- 매수 구역
- 손절 무효화 규칙
- 목표 재검토 구역
- 첫 비중 가이드
- 보유 프로필
- 현재 판단 근거와 안내 문구

Value/Quality는 V1에서 `education_only` 상태로 제공하며, PEAD, Sector Rotation, VCP 등은 데이터와 평가 로직이 준비되기 전까지 `deferred` 상태로 보류됩니다.

## 계획 저장 방식

플래너는 평가 결과를 다시 계산하지 않고, `/strategies`에서 선택한 하나의 평가 스냅샷을 그대로 받아 검토합니다.

- `strategy_snapshot`: 저장 당시의 전략 정의 카드
- `evaluation_snapshot`: 조건, 필터, 가드레일, 구역, 데이터 상태, 평가 시각
- 필수 입력: 보유 계획, 한 줄 이유
- 선택 입력: 매수 가격, 손절 가격, 목표 재검토 가격, 첫 비중 오버라이드, 메모

My Plans는 저장된 스냅샷을 다시 보여주는 화면입니다. 시간이 지난 뒤에도 "그때 어떤 조건과 근거로 이 계획을 저장했는지" 확인할 수 있도록, 저장된 계획을 실시간으로 재평가하지 않습니다.

## 멘토링 반영: 운영 안정성과 AI 안전성 보완

기업 멘토링에서는 FinMate가 실제 서비스처럼 운영될 경우 발생할 수 있는 장애, 비용, LLM 환각 문제를 함께 고민해보는 것이 중요하다는 피드백을 받았습니다. 이를 반영해 최종 결과물에서는 외부 API 호출을 줄이는 캐시, API 실패 시 대체 응답, 데이터 상태 표시, LLM 투자 권유 방지 규칙을 기술적 차별점으로 정리했습니다.

멘토링 피드백은 단순 문구 보강이 아니라 실제 백엔드 구조와 테스트 항목에 연결했습니다.

| 멘토링 피드백 | FinMate의 반영 방향 |
| --- | --- |
| 금융 주제는 흔하므로 차별점이 필요함 | 사용자가 추천을 받는 서비스가 아니라, 전략 조건과 데이터 상태를 확인하고 자기 판단 근거를 저장하는 계획 지원 서비스로 정리했습니다. |
| 운영 단계의 장애와 비용을 고려해야 함 | Naver/Gemini/DART/공공데이터 반복 호출을 줄이기 위해 캐시를 두고, API 실패 시에도 화면 흐름이 끊기지 않도록 fallback 응답을 제공합니다. |
| AI가 투자 권유나 검증되지 않은 최신 사실을 만들 수 있음 | `llm_guardrails.py`에 공통 안전 규칙을 분리하고, 챗봇·뉴스·캘린더·도미노 인사이트의 AI 응답을 같은 기준으로 후처리합니다. |
| 데이터가 부족한 상황을 숨기면 안 됨 | 전략 평가와 발표 후 결과에서 `fresh`, `partial`, `stale`, `unavailable` 같은 상태를 노출해 사용자가 데이터 한계를 알 수 있게 했습니다. |
| 반영 내용이 검증되어야 함 | LLM 위험 답변, 뉴스 fallback, DART 일정 필터링, 공공데이터 캐시, 발표 후 결과 상태를 테스트로 확인했습니다. |

| 반영 항목 | 구현 내용 |
| --- | --- |
| 외부 API 호출 비용 관리 | 뉴스 기반 시장 날씨는 50분 인메모리 캐시를 적용했고, DART 일정 조회는 24시간 캐시를 적용했습니다. 공공데이터 일봉 provider도 KST 기준 데이터 갱신 시점에 맞춰 캐시 만료 시간을 계산합니다. |
| 외부 API 장애 대응 | Gemini 뉴스 요약 실패 시 원문 뉴스 기반 fallback 카드를 반환하고, DART API 키가 없거나 조회가 어려운 경우 정적 일정 데이터(`earnings_events.json`)로 캘린더 흐름을 유지합니다. |
| 데이터 신뢰성 관리 | 뉴스는 여러 키워드 검색 결과를 URL/제목 기준으로 중복 제거하고 최신성과 검색 점수로 정렬합니다. 전략 평가는 일봉 데이터 상태를 `fresh`, `partial`, `stale`, `unavailable`로 구분합니다. |
| LLM 응답 안전성 | `llm_guardrails.py`에 공통 안전 규칙을 분리하고, 챗봇·뉴스 날씨·캘린더 인사이트·도미노 인사이트에 매수/매도 추천 금지, 수익 보장 금지, 최신 사실 생성 제한 규칙을 적용했습니다. |
| 안전성 테스트 | 20개 위험 답변 케이스를 통해 투자 권유성 문장이 감지되고 안전 문구로 대체되는지 검증했습니다. 뉴스 요약 실패, DART 일정 필터링, 공공데이터 캐시, 발표 후 결과 상태도 테스트로 확인했습니다. |
| 투자 권유 오해 방지 | 전략 플래너는 특정 종목이나 전략을 추천하지 않고, 조건·필터·가드레일을 확인한 뒤 사용자가 자신의 판단 근거를 저장하도록 구성했습니다. |

## 기술 구현

### Frontend

- React 기반 SPA
- `react-router-dom`으로 `/strategies`, `/planner`, `/my-plans` 화면 연결
- 전략 선택은 sessionStorage에 임시 저장한 뒤 planner로 전달
- 계획 저장/조회/수정/삭제는 FastAPI planner API와 연동

### Backend

- FastAPI 기반 API 서버
- `MarketDataProvider` 추상화로 OHLCV 데이터 공급자를 교체 가능하게 구성
- `DATA_GO_KR_SERVICE_KEY`가 있으면 공공데이터포털 금융위원회 주식시세정보 일봉을 사용하고, 없으면 mock daily OHLCV fixture로 동작
- 데이터 freshness 상태를 `fresh`, `stale`, `partial`, `unavailable`로 분리
- SQLite `user_plans` 테이블에 스냅샷 기반 계획 저장
- `llm_guardrails.py`로 공통 LLM 안전 규칙과 금지 패턴을 분리
- 챗봇, 뉴스 날씨, 캘린더 인사이트, 도미노 인사이트에 공통 가드레일과 안전 fallback 적용
- 뉴스 시장 날씨는 Gemini 실패 시 원문 뉴스 기반 fallback 카드를 반환하고 결과를 50분 캐시
- DART 일정 조회는 실적 공시/실적 관련 IR만 필터링하고 24시간 캐시
- 공공데이터포털 일봉 provider는 데이터 갱신 시점 기반 캐시와 `fresh/partial/stale/unavailable` 상태를 제공
- 캘린더 발표 후 결과 API는 실적 수치, 주가 반응, 해설을 `available/partial/unavailable` 상태로 분리

### 주요 API

| Method | Endpoint | 설명 |
| --- | --- | --- |
| `GET` | `/api/logic-alerts` | 삼성전자 가격, 환율 등 규칙 기반 알림 상태를 반환합니다. |
| `GET` | `/api/calendar/earnings-demo` | OpenDART 기반 국내 기업 실적 발표/실적 관련 IR 일정을 반환합니다. |
| `POST` | `/api/calendar/insight` | 캘린더 이벤트의 발표 전 체크포인트를 Gemini로 생성합니다. |
| `POST` | `/api/calendar/post-result` | 발표 후 실적 수치, 주가 반응, 해설을 OpenDART/일봉 데이터로 구성합니다. |
| `GET` | `/api/calendar/dart-debug` | DART 원본 응답을 확인하는 개발용 엔드포인트입니다. |
| `GET` | `/api/strategies/catalog` | 전략 카탈로그와 activation state를 반환합니다. |
| `GET` | `/api/strategies/symbols` | 지원 종목의 최신 일봉 종가와 데이터 상태를 반환합니다. |
| `POST` | `/api/strategies/evaluate` | 선택 종목의 live 전략 평가 결과를 반환합니다. |
| `GET` | `/api/planner/plans` | 저장된 계획 목록을 조회합니다. |
| `POST` | `/api/planner/plans` | 선택한 평가 스냅샷으로 계획을 저장합니다. |
| `GET` | `/api/planner/plans/{plan_id}` | 계획 상세 정보를 조회합니다. |
| `PUT` | `/api/planner/plans/{plan_id}` | 오버라이드, 메모, 상태 등 허용된 필드를 수정합니다. |
| `DELETE` | `/api/planner/plans/{plan_id}` | 저장된 계획을 삭제합니다. |

## 로컬 실행

### Backend

```bash
cd FinMate-Back
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Windows에서는 가상환경 활성화 명령만 `venv\Scripts\activate`를 사용하면 됩니다. AI 챗봇, 뉴스, 경제지표, DART 캘린더, 공공데이터 일봉 기능까지 함께 실행하려면 `FinMate-Back/.env`에 다음 값을 설정합니다.

```properties
GEMINI_MODEL_DEFAULT=gemini-2.0-flash
GEMINI_API_KEY=your_key
NAVER_CLIENT_ID=your_key
NAVER_CLIENT_SECRET=your_key
ECOS_AUTH_KEY=your_key
DART_API_KEY=your_key
DATA_GO_KR_SERVICE_KEY=your_key
DATA_GO_KR_CACHE_TTL_SECONDS=
```

`DATA_GO_KR_SERVICE_KEY`가 비어 있으면 전략 평가는 mock fixture로 동작하고, 캘린더 발표 후 주가 반응과 일부 로직 알림은 unavailable 상태가 될 수 있습니다.

### Frontend

```bash
cd FinMate-Front
npm install
npm start
```

프론트엔드는 기본적으로 `http://localhost:3000`, 백엔드는 `http://localhost:8000`에서 실행됩니다.

## 테스트

```bash
cd FinMate-Back
python -m unittest discover -s tests -p "test_*.py" -v
```

백엔드 테스트에는 전략 평가뿐 아니라 멘토링 피드백을 반영한 운영/안전성 테스트도 포함되어 있습니다.

| 테스트 파일 | 검증 내용 |
| --- | --- |
| `tests/test_llm_guardrails.py` | 투자 권유, 매수/매도 지시, 수익 보장 등 20개 위험 답변을 감지하고 안전 fallback으로 대체하는지 검증 |
| `tests/test_news_weather.py` | Gemini 뉴스 요약 실패 시에도 원문 뉴스 기반 카드가 반환되는지 검증 |
| `tests/test_dart_calendar.py` | DART 공시 중 실적 발표/실적 관련 IR 일정만 캘린더에 남기는지 검증 |
| `tests/test_public_data_provider.py` | 공공데이터 일봉 매핑, 캐시, 캐시 비활성화, KST 갱신 시점 기반 만료를 검증 |
| `tests/test_calendar_post_result.py` | 실적 공시 수치 파싱, 발표 후 주가 반응, partial/unavailable 상태를 검증 |

```bash
cd FinMate-Front
npm test -- --watchAll=false
```

## 프로젝트 구조

```text
FinMate-Back/
  main.py                    # FastAPI 앱 진입점
  llm_guardrails.py          # 공통 LLM 안전 규칙/금지 패턴/fallback
  dart.py                    # OpenDART 실적/IR 일정 조회
  calendar_post_result.py    # 발표 후 실적 수치/주가 반응 구성
  logic_alerts.py            # 규칙 기반 시장 알림
  strategy_routes.py          # 전략 카탈로그/평가 API
  plan_routes.py              # 플래너 저장/조회/수정/삭제 API
  plan_db.py                  # SQLite user_plans 저장소
  market_data/                # MarketDataProvider와 daily bar 타입
  strategies/                 # 전략 계약, 평가 로직, 공통 체크
  data/strategy_catalog.json  # 전략 카탈로그
  tests/                      # LLM 가드레일, 뉴스 fallback, DART, 공공데이터 테스트

FinMate-Front/
  src/pages/strategies.jsx    # 전략 탐색 화면
  src/pages/planner.jsx       # 평가 스냅샷 검토/저장 화면
  src/pages/my-plans.jsx      # 저장된 계획 화면
  src/components/StrategyCard.jsx
  src/lib/strategy-flow.js
```

## 안내

FinMate의 전략 플래너는 교육 및 계획 정리를 돕기 위한 프로토타입입니다. 제공되는 전략 카드, 구역, 규칙은 투자 권유나 수익 보장을 의미하지 않으며, 모든 투자 판단과 책임은 사용자 본인에게 있습니다.

FinMate의 AI 설명은 금융 정보를 쉽게 이해하도록 돕는 보조 기능입니다. 공통 LLM 가드레일을 통해 매수·매도 지시, 특정 종목 추천, 수익 보장, 검증되지 않은 최신 사실 생성을 제한하며, 위험한 투자 권유성 문장이 감지되면 안전한 안내 문구로 대체합니다.
