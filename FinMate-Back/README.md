# finMate
[FinMate 오픈 API 실행 방법 안내]

1. 개요
- 이 문서는 FinMate 백엔드(FastAPI 기반)를 실행해서
  프론트엔드에서 사용할 오픈 API 서버를 구동하는 방법을 정리한 것입니다.
- 주요 제공 API:
  - POST /api/chat           : AI 금융 멘토 챗봇
  - GET  /api/macro-chart    : 금리 + KOSPI 도미노 차트 데이터
  - GET  /api/market-weather : KOSPI / KOSDAQ / 환율 / 국고채 3년 지표


2. 사전 준비 사항
- Python 3.10 이상 설치
- ECOS API Key (한국은행 경제통계시스템)
- Gemini API Key (Google AI Studio)

※ 윈도우 기준 설명입니다.


3. 프로젝트 폴더 구조 예시
FinMate/
 ├── FinMate-Front/  (React 프론트엔드)
 └── FinMate-Back/   (FastAPI 백엔드)

백엔드 폴더 구성 예시:
- main.py        : FastAPI 엔트리 포인트
- ecos.py        : ECOS API 연동 및 데이터 가공
- bot.py         : Gemini 기반 AI 응답 생성
- test.py        : 테스트용 스크립트
- requirements.txt


4. 가상환경 생성 및 활성화

(1) 가상환경 생성
> python -m venv venv

(2) 가상환경 활성화 (Windows PowerShell 기준)
> venv\Scripts\activate

※ 비활성화할 때는:
> deactivate


5. 패키지 설치 (requirements.txt 사용)

(1) FinMate-Back 폴더로 이동
> cd FinMate-Back

(2) 의존성 설치
> pip install -r requirements.txt


6. FastAPI 서버 실행 방법

(1) FinMate-Back 폴더에서 다음 명령 실행
> uvicorn main:app --reload --port 8000

(2) 서버가 정상적으로 실행되면:
- 기본 주소: http://localhost:8000

(3) 브라우저에서 테스트:
- http://localhost:8000/       → 기본 상태 메시지 확인
- http://localhost:8000/docs   → Swagger UI에서 API 테스트 가능
- http://localhost:8000/redoc  → Redoc 문서


7. 주요 오픈 API 설명

(1) AI 금융 멘토 API
- URL: POST /api/chat
- Request Body(JSON 예시):

{
  "mode": "easy",
  "message": "금리가 오르면 주식은 왜 떨어져?",
  "history": [
    { "role": "user", "text": "이전 대화 내용" },
    { "role": "ai",   "text": "AI 응답" }
  ]
}

- Response(JSON 예시):

{
  "reply": "금리가 오르면 기업의 자금조달 비용이 올라가고..."
}

------------------------------------------------------------

(2) 도미노 차트 데이터 API
- URL: GET /api/macro-chart
- 설명: 최근 6개 기간에 대해 기준금리(rate)와 KOSPI 평균(stock)을 함께 반환

- Response(JSON 예시):

[
  {
    "date": "2025.01",
    "rate": 3.50,
    "stock": 2500.12
  },
  ...
]

------------------------------------------------------------

(3) 시장 날씨 지표 API
- URL: GET /api/market-weather
- 설명: KOSPI, KOSDAQ, USD/KRW, 국고채 3년 등
        주요 자산들의 "최근 값"과 "전일 대비 변화율"을 반환

- Response(JSON 예시):

{
  "indices": [
    {
      "name": "KOSPI",
      "value": "2,750.41",
      "change": 1.2
    },
    {
      "name": "KOSDAQ",
      "value": "890.12",
      "change": 0.8
    },
    {
      "name": "USD/KRW",
      "value": "1,320.50",
      "change": -0.5
    },
    {
      "name": "국고채 3년",
      "value": "3.45%",
      "change": -0.02
    }
  ]
}


8. 프론트엔드(React)와 연동 시 주의사항

- 프론트에서 API를 호출할 때 기본 URL은 다음을 사용:

fetch("http://localhost:8000/api/macro-chart")
fetch("http://localhost:8000/api/market-weather")
fetch("http://localhost:8000/api/chat")

- CORS 설정
  main.py 에서 다음이 설정되어 있어야 함:

  origins = [
      "http://localhost:3000"
  ]

  app.add_middleware(
      CORSMiddleware,
      allow_origins=origins,
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )


9. 자주 발생하는 문제와 해결 방법

- 문제: "ECOS 데이터 조회 오류"
  → ECOS_API_KEY가 올바른지 확인

- 문제: "Gemini 호출 오류"
  → GEMINI_API_KEY가 올바른지 확인

- 문제: CORS 에러
  → allow_origins에 프론트 URL 추가

- 문제: uvicorn 실행 시 모듈을 못 찾음
  → 현재 위치가 main.py가 있는 폴더인지 확인
  → 가상환경 활성화 여부 확인


[끝]
