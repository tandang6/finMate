# config.py
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


def _optional_int_env(name: str) -> int | None:
    value = os.getenv(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

class Settings:
    # ECOS
    ECOS_AUTH_KEY = os.getenv("ECOS_AUTH_KEY", "")
    ECOS_BASE_URL = os.getenv("ECOS_BASE_URL", "http://ecos.bok.or.kr/api")
    
    # NAVER
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
    NAVER_BASE_URL = "https://openapi.naver.com/v1/search/news.json"
    
    # GEMINI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    # 모델은 변경 가능합니다
    GEMINI_MODEL_DEFAULT = os.getenv("GEMINI_MODEL_DEFAULT", "")

    # DART
    DART_API_KEY = os.getenv("DART_API_KEY", "")

    # DATA.GO.KR
    DATA_GO_KR_SERVICE_KEY = os.getenv("DATA_GO_KR_SERVICE_KEY", "")
    DATA_GO_KR_STOCK_PRICE_URL = os.getenv(
        "DATA_GO_KR_STOCK_PRICE_URL",
        "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo",
    )
    DATA_GO_KR_CACHE_TTL_SECONDS = _optional_int_env("DATA_GO_KR_CACHE_TTL_SECONDS")

settings = Settings()
