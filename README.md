# FinMate

FinMate는 금융 초보자가 뉴스, 거시경제 지표, 경제 일정처럼 흩어진 정보를 한 화면에서 이해하고 스스로 판단 근거를 정리할 수 있도록 돕는 금융 의사결정 지원 서비스입니다. React 프론트엔드와 FastAPI 백엔드로 구성되어 있으며, AI 금융 멘토, 시장 날씨, 거시경제 도미노 차트, 경제 일정 해설 기능을 제공합니다.

기존의 "시장 이해" 기능 위에 한국 주식 입문자를 위한 **전략 기반 투자 계획 플래너**를 추가했습니다. 이 기능은 특정 종목이나 전략을 추천하지 않고, 사용자가 선택한 종목의 일봉 조건을 전략별로 점검한 뒤 계획을 검토하고 저장하도록 돕는 규칙 기반 프로토타입입니다.

## 데모 영상

<video src="./assets/strategy-planner-demo.mp4" controls width="100%"></video>

[FinMate 전략 플래너 데모 영상 보기](./assets/strategy-planner-demo.mp4)

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

## 기술 구현

### Frontend

- React 기반 SPA
- `react-router-dom`으로 `/strategies`, `/planner`, `/my-plans` 화면 연결
- 전략 선택은 sessionStorage에 임시 저장한 뒤 planner로 전달
- 계획 저장/조회/수정/삭제는 FastAPI planner API와 연동

### Backend

- FastAPI 기반 API 서버
- `MarketDataProvider` 추상화로 OHLCV 데이터 공급자를 교체 가능하게 구성
- 현재 데모는 mock daily OHLCV fixture로 동작
- 데이터 freshness 상태를 `fresh`, `stale`, `partial`, `unavailable`로 분리
- SQLite `user_plans` 테이블에 스냅샷 기반 계획 저장

### 주요 API

| Method | Endpoint | 설명 |
| --- | --- | --- |
| `GET` | `/api/strategies/catalog` | 전략 카탈로그와 activation state를 반환합니다. |
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

Windows에서는 가상환경 활성화 명령만 `venv\Scripts\activate`를 사용하면 됩니다. AI 챗봇, 뉴스, 경제지표 기능까지 함께 실행하려면 `FinMate-Back/.env`에 `GEMINI_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `ECOS_AUTH_KEY`를 설정해야 합니다.

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

```bash
cd FinMate-Front
npm test -- --watchAll=false
```

## 프로젝트 구조

```text
FinMate-Back/
  main.py                    # FastAPI 앱 진입점
  strategy_routes.py          # 전략 카탈로그/평가 API
  plan_routes.py              # 플래너 저장/조회/수정/삭제 API
  plan_db.py                  # SQLite user_plans 저장소
  market_data/                # MarketDataProvider와 daily bar 타입
  strategies/                 # 전략 계약, 평가 로직, 공통 체크
  data/strategy_catalog.json  # 전략 카탈로그

FinMate-Front/
  src/pages/strategies.jsx    # 전략 탐색 화면
  src/pages/planner.jsx       # 평가 스냅샷 검토/저장 화면
  src/pages/my-plans.jsx      # 저장된 계획 화면
  src/components/StrategyCard.jsx
  src/lib/strategy-flow.js
```

## 안내

FinMate의 전략 플래너는 교육 및 계획 정리를 돕기 위한 프로토타입입니다. 제공되는 전략 카드, 구역, 규칙은 투자 권유나 수익 보장을 의미하지 않으며, 모든 투자 판단과 책임은 사용자 본인에게 있습니다.
