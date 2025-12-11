# [FinMate 오픈 API 실행 및 연동 가이드]

## 1\. 개요

  - 이 문서는 FinMate 백엔드(FastAPI 기반)를 로컬 환경에서 구동하고, 프론트엔드와 연동하기 위한 절차를 설명합니다.
  - **주요 제공 API 목록:**
    1.  `POST /api/chat`           : AI 금융 멘토 챗봇 (ECOS 용어 사전 + Gemini)
    2.  `GET  /api/market-weather` : 시장 날씨 지표 (KOSPI/환율 등 실시간 데이터)
    3.  `GET  /api/news-weather`   : **(NEW)** 뉴스 기반 AI 시장 날씨 요약 및 뉴스 카드
    4.  `GET  /api/macro-chart`    : 금리 + KOSPI 도미노 차트 데이터
    5.  `GET  /api/macro-insight`  : **(NEW)** 차트 데이터 기반 AI 한 줄 분석

## 2\. 사전 준비 사항

  - **Python 3.9 이상** 설치
  - **API Key 준비:**
      - ECOS API Key (한국은행 경제통계시스템)
      - Gemini API Key (Google AI Studio)
      - **(NEW)** Naver Developers API Key (검색 API - Client ID/Secret)
  - **운영체제:** Windows 기준 설명 (Mac/Linux 명령어는 별도 표기)

## 3\. 프로젝트 폴더 구조

```text
FinMate/
 ├── FinMate-Front/   (React 프론트엔드)
 └── FinMate-Back/    (FastAPI 백엔드)
      ├── main.py            # FastAPI 앱 진입점
      ├── ecos.py            # 한국은행 데이터 크롤링
      ├── bot.py             # AI 챗봇 로직
      ├── news_weather.py    # (NEW) 네이버 뉴스 + AI 요약
      ├── domino_insight.py  # (NEW) 거시경제 AI 분석
      ├── config.py          # 환경변수 관리 설정
      ├── .env               # (필수) API Key 저장 파일
      └── requirements.txt   # 라이브러리 목록
```

## 4\. 환경 설정 및 실행 (순서대로 진행)

### (1) 가상환경 생성 및 활성화

```powershell
# FinMate-Back 폴더로 이동 후
python -m venv venv

# Windows 활성화
venv\Scripts\activate

# (참고) Mac/Linux 활성화
# source venv/bin/activate
```

### (2) 패키지 설치

```powershell
pip install -r requirements.txt
```

### (3) 환경 변수 파일(.env) 생성 **(중요)**

`FinMate-Back` 폴더 바로 아래에 `.env` 파일을 만들고 키를 입력하세요.

```properties
# .env 파일 내용 예시
GEMINI_API_KEY=AIzaSy...
MODEL_NAME=gemini-2.0-flash

NAVER_CLIENT_ID=네이버_클라이언트_아이디
NAVER_CLIENT_SECRET=네이버_시크릿

ECOS_AUTH_KEY=한국은행_인증키
```

### (4) 서버 실행

```powershell
uvicorn main:app --reload --port 8000
```

  - **정상 실행 확인:** 브라우저에서 `http://localhost:8000/docs` 접속 시 Swagger UI가 뜨면 성공입니다.

## 5\. 주요 오픈 API 상세 명세

### (1) 🤖 AI 금융 멘토 (`POST /api/chat`)

  - **설명:** 사용자의 질문에 대해 경제 용어 사전 검색 후, 없으면 AI가 답변합니다.
  - **Request:**

<!-- end list -->

```json
{
  "mode": "easy",
  "message": "환율이 오르면 어떻게 돼?",
  "history": []
}
```

  - **Response:**

<!-- end list -->

```json
{ "reply": "환율이 오르면 수출 기업에는 좋지만, 수입 물가가 올라요! 💸" }
```

-----

### (2) 🌤️ 뉴스 시장 날씨 (`GET /api/news-weather`) **(NEW)**

  - **설명:** 네이버 뉴스를 분석해 시장 분위기(Sunny/Cloudy 등)와 뉴스 카드 4개를 반환합니다. (50분 캐시 적용)
  - **Response:**

<!-- end list -->

```json
{
  "weather": {
    "line1": "오늘 날씨는 : SUNNY",
    "line2": "금리 인하 기대감에 훈풍이 불어요! 🌿",
    "line3": "물가 안정 신호로 투자 심리가 회복되고 있습니다."
  },
  "cards": [
    {
      "category": "증시",
      "title": "코스피 2700선 돌파",
      "summary": "외국인 매수세 유입으로 상승했습니다.",
      "insight": "반도체 업황 개선 기대가 큽니다.",
      "url": "https://n.news.naver.com/..."
    }
  ]
}
```

-----

### (3) 📊 도미노 차트 데이터 (`GET /api/macro-chart`)

  - **설명:** 최근 6개월 기준금리와 KOSPI 지수를 반환합니다.
  - **Response:**

<!-- end list -->

```json
[
  { "date": "2024.08", "rate": 3.50, "stock": 2650.10 },
  { "date": "2024.09", "rate": 3.50, "stock": 2590.50 }
]
```

-----

### (4) 💡 도미노 AI 인사이트 (`GET /api/macro-insight`) **(NEW)**

  - **설명:** 위 차트 데이터를 보고 AI가 분석한 한 줄 코멘트를 반환합니다.
  - **Response:**

<!-- end list -->

```json
{ "insight": "금리가 동결되는 동안 주가는 박스권에 머무는 모습입니다." }
```

-----

### (5) 📈 시장 지표 (`GET /api/market-weather`)

  - **설명:** KOSPI, KOSDAQ, 환율, 국고채의 현재가와 등락률을 반환합니다.
  - **Response:**

<!-- end list -->

```json
{
  "indices": [
    { "name": "KOSPI", "value": "2,750.41", "change": 1.2 },
    { "name": "USD/KRW", "value": "1,320.50", "change": -0.5 }
  ]
}
```

## 6\. 프론트엔드 연동 시 주의사항

1.  **CORS 설정:**

      - `main.py`의 `origins` 리스트에 프론트엔드 주소(`http://localhost:3000`)가 정확히 등록되어 있어야 합니다.

2.  **API 호출 주소:**

    ```javascript
    // 예시 (Axios or Fetch)
    const response = await fetch("http://localhost:8000/api/news-weather");
    ```

3.  **로딩 처리:**

      - `news-weather`나 `chat` API는 AI가 생성하는 시간이 필요하므로(약 1\~3초), 프론트엔드에서 **스피너(Loading Spinner)** 처리가 필수입니다.

## 7\. 트러블슈팅 (자주 묻는 질문)

  - **Q. "RuntimeError: GEMINI\_API\_KEY..." 에러가 떠요.**

      - A. `.env` 파일이 없거나, 키 값이 비어있는지 확인하세요. 파일명은 반드시 `.env`여야 합니다.

  - **Q. 뉴스 날씨 API가 너무 느려요.**

      - A. 최초 실행 시 뉴스를 크롤링하고 AI가 요약하느라 약 3\~5초 소요될 수 있습니다. 이후 50분간은 캐시(저장된 값)를 반환하므로 빠릅니다.

  - **Q. ECOS 데이터가 비어있어요.**

      - A. 한국은행 API는 하루 호출 제한(약 2만 회)이 있거나, 인증키가 만료되었을 수 있습니다. 로그를 확인해 주세요.

-----

**[끝]**
