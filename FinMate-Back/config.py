# config.py
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

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
    GEMINI_MODEL_DEFAULT = os.getenv("MODEL_NAME", "")
settings = Settings()