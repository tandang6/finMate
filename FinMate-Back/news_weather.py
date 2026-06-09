# news_weather.py

# ==============================================================================
# [필수 라이브러리 및 모듈 임포트]
# ==============================================================================
import requests
import urllib.parse
from datetime import datetime
import email.utils as eut
import json
import time

from config import settings  # 환경 설정 (API Key 등)
from bot import client       # bot.py에서 이미 초기화된 Gemini Client 재사용 (리소스 절약)


# ==============================================================================
# [전역 캐시 설정]
# 외부 API(네이버, Gemini) 호출 횟수를 줄이고 응답 속도를 높이기 위한 간단한 인메모리 캐시입니다.
# ==============================================================================
_cached_result = None   # 가장 최근에 생성된 분석 결과(JSON) 저장
_cached_at = 0          # 마지막으로 데이터를 갱신한 시간 (Epoch time)
CACHE_TTL = 3000        # 캐시 유효 시간 (초 단위, 3000초 = 50분)


# ==============================================================================
# 1. 네이버 뉴스 검색 API 설정
# ==============================================================================

NAVER_CLIENT_ID = settings.NAVER_CLIENT_ID
NAVER_CLIENT_SECRET = settings.NAVER_CLIENT_SECRET
GEMINI_API_KEY = settings.GEMINI_API_KEY
MODEL_NAME = settings.GEMINI_MODEL_DEFAULT
NAVER_BASE_URL = "https://openapi.naver.com/v1/search/news.json"


def search_naver_news(query: str, display: int = 10, start: int = 1, sort: str = "date"):
    """
    네이버 뉴스 검색 API를 호출하여 원본 데이터를 가져옵니다.
    - query: 검색어
    - sort: 'date'(최신순) 또는 'sim'(정확도순)
    """
    enc_query = urllib.parse.quote(query)
    url = f"{NAVER_BASE_URL}?query={enc_query}&display={display}&start={start}&sort={sort}"

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }

    resp = requests.get(url, headers=headers, timeout=10)
    
    # 통신 실패 시 None 반환 후 로그 출력
    if resp.status_code != 200:
        print(f"❌ '{query}' 검색 실패:", resp.status_code, resp.text)
        return None

    return resp.json()


def clean_html_tags(text: str) -> str:
    """
    네이버 API 응답에 포함된 HTML 태그(&quot;, <b> 등)를 제거하여 순수 텍스트로 변환합니다.
    """
    if not text:
        return ""
    return (
        text.replace("<b>", "")
        .replace("</b>", "")
        .replace("&quot;", "\"")
        .replace("&apos;", "'")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )


def parse_pubdate(pub_date_str: str):
    """
    뉴스 기사 발행일 문자열(RFC 2822 형식)을 Python datetime 객체로 변환합니다.
    """
    try:
        return eut.parsedate_to_datetime(pub_date_str)
    except Exception:
        return None


def extract_news_list(data: dict):
    """
    API 원본 응답(JSON)에서 필요한 필드만 추출하여 리스트로 정리합니다.
    """
    if data is None:
        return []

    items = data.get("items", [])
    result = []

    for item in items:
        title = clean_html_tags(item.get("title", ""))
        desc = clean_html_tags(item.get("description", ""))
        link = item.get("link", "")
        originallink = item.get("originallink", "")
        pub_date_str = item.get("pubDate", "")
        pub_dt = parse_pubdate(pub_date_str)

        result.append(
            {
                "title": title,
                "description": desc,
                "link": link,
                "originallink": originallink,
                "pubDate": pub_date_str,
                "pubDate_dt": pub_dt,
            }
        )

    return result


def collect_market_news(queries, per_query: int = 5, sort: str = "date", top_n: int = 10):
    """
    여러 키워드(queries)로 뉴스를 검색한 뒤, 중요도와 최신성을 기준으로 상위 N개를 선정합니다.
    
    [알고리즘]
    1. 여러 키워드로 검색된 뉴스들을 하나로 합칩니다.
    2. 중복 제거: URL이나 제목이 같으면 동일 뉴스로 간주합니다.
    3. 점수(Score) 계산: 여러 키워드에서 동시에 검색된 뉴스일수록 점수를 높게 부여합니다.
    4. 정렬: 점수가 높고, 날짜가 최신인 순서로 정렬하여 상위 top_n개를 반환합니다.
    """
    merged = {}

    for q in queries:
        # 각 키워드별로 뉴스 검색
        raw = search_naver_news(q, display=per_query, sort=sort)
        articles = extract_news_list(raw)

        for art in articles:
            # 중복 식별 키 (링크 우선, 없으면 제목)
            key = art["link"] or art["originallink"] or art["title"]

            if key not in merged:
                merged[key] = art
                merged[key]["keywords"] = set()
                merged[key]["score"] = 0

            # 해당 뉴스가 발견된 키워드 추가 및 점수 증가
            merged[key]["keywords"].add(q)
            merged[key]["score"] += 1

    # 딕셔너리를 리스트로 변환
    articles = list(merged.values())
    for art in articles:
        art["keywords"] = list(art["keywords"])

    # 정렬 기준: 1순위(언급 빈도 점수), 2순위(최신 날짜)
    def sort_key(a):
        dt = a.get("pubDate_dt") or datetime.min
        return (a["score"], dt)

    articles.sort(key=sort_key, reverse=True)
    
    # 상위 N개만 잘라서 반환
    return articles[:top_n]


def build_context_from_top_news(top_news):
    """
    Gemini에게 넘겨줄 프롬프트용 텍스트를 생성합니다.
    (뉴스 제목, 요약, 링크를 보기 좋게 나열)
    """
    lines = []
    for i, n in enumerate(top_news, 1):
        title = n["title"]
        desc = n["description"]
        url = n["link"] or n["originallink"]
        lines.append(
            f"[뉴스 {i}]\n"
            f"제목: {title}\n"
            f"요약: {desc}\n"
            f"링크: {url}\n"
        )
    return "\n".join(lines)


def shorten_text(text: str, max_length: int) -> str:
    """
    화면 카드에 들어갈 fallback 문구를 짧게 정리합니다.
    """
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "…"


def infer_news_category(article: dict) -> str:
    """
    AI 요약이 실패했을 때 제목/설명 기반으로 간단한 카드 카테고리를 고릅니다.
    """
    text = f"{article.get('title', '')} {article.get('description', '')}"
    category_keywords = [
        ("금리", "금리"),
        ("환율", "환율"),
        ("달러", "환율"),
        ("코스피", "증시"),
        ("코스닥", "증시"),
        ("증시", "증시"),
        ("반도체", "반도체"),
        ("이차전지", "산업"),
        ("AI", "산업"),
        ("기업", "기업"),
    ]

    for keyword, category in category_keywords:
        if keyword in text:
            return category

    return "뉴스"


def build_news_weather_fallback(top_news):
    """
    Gemini quota/모델 오류가 나도 프론트가 뉴스 데이터를 표시할 수 있게 합니다.
    """
    cards = []
    for article in top_news[:4]:
        title = article.get("title", "")
        description = article.get("description", "")
        url = article.get("link") or article.get("originallink") or ""
        summary_source = description or title

        cards.append(
            {
                "category": infer_news_category(article),
                "title": shorten_text(title, 28) or "시장 뉴스",
                "summary": shorten_text(summary_source, 42) or "원문 기준 주요 뉴스입니다.",
                "insight": "AI 분석 한도 문제로 원문 뉴스를 표시합니다.",
                "url": url,
            }
        )

    return {
        "weather": {
            "line1": "오늘 날씨는 : CLOUDY",
            "line2": "뉴스는 불러왔고 AI 요약은 대기 중이에요",
            "line3": "Gemini 한도 문제로 원문 뉴스 카드만 표시합니다.",
        },
        "cards": cards,
    }


# ==============================================================================
# 2. Gemini AI를 활용한 시장 날씨 및 뉴스 카드 생성
# ==============================================================================


def generate_weather_and_cards_with_gemini(top_news):
    """
    수집된 뉴스 목록을 바탕으로 AI에게 '시장 날씨(요약)'와 '뉴스 카드' 생성을 요청합니다.
    결과는 반드시 JSON 형식으로 받아옵니다.
    """
    context_text = build_context_from_top_news(top_news)

    # [프롬프트 설계]
    # 1. 페르소나: 친절한 마켓 캐스터
    # 2. 임무: 뉴스들을 분석하여 시장 분위기(SUNNY/CLOUDY/STORMY) 판단 및 핵심 뉴스 카드 작성
    # 3. 제약조건: 반드시 지정된 JSON 포맷만 출력 (파싱을 위해)
    prompt = f"""
너는 개인 투자자들을 위한 금융 대시보드 'FinMate'의
'오늘의 시장 날씨'를 전달하는 마켓 캐스터야.

[너의 페르소나]
- 한국 개인 투자자에게 매일 아침 시장 분위기를 친절하게 설명해주는 캐스터.
- 과장된 멘트 대신, 차분하고 근거 있는 톤을 사용.
- 투자 조언(매수/매도, 특정 종목 추천)은 하지마.
- 시장을 '날씨'에 비유해서 감정적으로 이해하기 쉽게 설명하는 역할.

weather 의미:
- SUNNY : 전반적으로 상승, 훈풍, 낙관적인 분위기
- CLOUDY : 혼조, 관망, 방향성이 명확하지 않은 상태
- STORMY : 하락, 변동성 확대, 공포·우려가 큰 상태

[출력 형식 예시(JSON)]
아래는 형식을 설명하기 위한 예시이다. 값은 예시일 뿐이다.

{{
  "weather": {{
    "line1": "오늘 날씨는 : SUNNY",
    "line2": "금리 인하 기대감에 시장에 훈풍이 불어요! 🌿",
    "line3": "물가 둔화로 투자 심리가 회복되는 모습입니다. 하지만 일부 투자자는 관망하는 분위기예요."
  }},
  "cards": [
    {{
      "category": "거시경제",
      "title": "파월 의장, 연내 금리 인하 시사",
      "summary": "금리 인하 기대가 시장에 반영되었습니다.",
      "insight": "완화 기대가 투자 심리를 개선하고 있습니다.",
      "url": "https://news.example.com"
    }}
  ]
}}

[실제 출력 규칙]
- 반드시 위 JSON 형태 그대로만 출력.
- weather.line1 → "오늘 날씨는 : SUNNY/CLOUDY/STORMY"
- weather.line2 → 쉬운 표현, 25자 이내, 이모지 0~1개
- weather.line3 → 이유 설명 1~2문장, 각 40자 이내
- cards:
  - 최대 4개
  - category 2~4글자 (예: "거시경제", "환율", "반도체" 등)
  - title 20자 내외
  - summary 40자 이내
  - insight 40자 이내
  - url은 반드시 [뉴스 목록] 안에 등장하는 링크 중 하나 사용
- JSON 외 다른 말 절대 출력하지 마라.

[뉴스 목록]
{context_text}
"""

    # Gemini API 호출 (bot.py의 client 사용)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )

    raw = response.text.strip()

    # AI가 응답을 마크다운 코드 블록(```json ... ```)으로 감쌀 경우 제거
    if raw.startswith("```"):
        lines = raw.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        raw = "\n".join(lines).strip()

    # 문자열을 Python 딕셔너리로 변환
    data = json.loads(raw)
    return data


# ==============================================================================
# 3. 외부에서 호출하는 메인 함수 (캐시 적용)
# ==============================================================================

def get_news_weather():
    """
    API 엔드포인트에서 호출하는 함수입니다.
    
    [로직]
    1. 메모리 캐시를 확인합니다. 유효 기간(50분) 내의 데이터가 있으면 바로 반환합니다.
    2. 캐시가 없거나 만료되었으면:
       a. 네이버 뉴스 API로 주요 키워드(증시, 금리 등) 검색
       b. 검색 결과를 AI에게 전달하여 요약 및 분석 요청
       c. 결과를 캐시에 저장하고 반환
    """
    global _cached_result, _cached_at

    now = time.time()

    # 1. 캐시 히트 (Cache Hit): 유효한 데이터가 있으면 즉시 반환
    if _cached_result is not None and (now - _cached_at) < CACHE_TTL:
        return _cached_result

    # 2. 캐시 미스 (Cache Miss): 데이터를 새로 생성
    queries = [
        "코스피",
        "증시",
        "금리 인하",
        "금리 인상",
        "CPI",
        "물가 상승",
        "환율",
        "미국 증시",
        "이차전지",
        "기업",
        "AI"
    ]

    # 뉴스 수집 및 선별
    top_news = collect_market_news(
        queries=queries,
        per_query=5,
        sort="date",
        top_n=10,
    )

    # AI 분석 수행. Gemini quota/모델 오류가 나도 뉴스 원문 카드는 반환합니다.
    if top_news:
        try:
            result = generate_weather_and_cards_with_gemini(top_news)
        except Exception as exc:
            print(f"⚠️ Gemini 뉴스 요약 실패, fallback 반환: {exc}")
            result = build_news_weather_fallback(top_news)
    else:
        result = build_news_weather_fallback(top_news)

    # 3. 결과 캐싱 (Cache Update)
    _cached_result = result
    _cached_at = now

    return result
