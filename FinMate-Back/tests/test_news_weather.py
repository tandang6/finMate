import os
import unittest
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GEMINI_MODEL_DEFAULT", "gemini-test")

import news_weather


SAMPLE_NEWS = [
    {
        "title": "코스피 상승 출발, 반도체 대형주 강세",
        "description": "국내 증시가 반도체 업종 강세에 힘입어 상승 출발했습니다.",
        "link": "https://example.com/news/1",
        "originallink": "",
    },
    {
        "title": "환율 하락에 외국인 수급 개선 기대",
        "description": "원달러 환율이 하락하며 위험자산 선호가 일부 회복됐습니다.",
        "link": "https://example.com/news/2",
        "originallink": "",
    },
]


class NewsWeatherFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        news_weather._cached_result = None
        news_weather._cached_at = 0

    def tearDown(self) -> None:
        news_weather._cached_result = None
        news_weather._cached_at = 0

    def test_get_news_weather_returns_news_cards_when_gemini_fails(self) -> None:
        with patch.object(news_weather, "collect_market_news", return_value=SAMPLE_NEWS), patch.object(
            news_weather,
            "generate_weather_and_cards_with_gemini",
            side_effect=RuntimeError("quota exceeded"),
        ):
            result = news_weather.get_news_weather()

        self.assertEqual(result["weather"]["line1"], "오늘 날씨는 : CLOUDY")
        self.assertEqual(len(result["cards"]), 2)
        self.assertEqual(result["cards"][0]["category"], "증시")
        self.assertEqual(result["cards"][0]["url"], "https://example.com/news/1")
        self.assertIn("AI 분석 한도", result["cards"][0]["insight"])

    def test_get_news_weather_skips_gemini_when_no_news_was_collected(self) -> None:
        with patch.object(news_weather, "collect_market_news", return_value=[]), patch.object(
            news_weather,
            "generate_weather_and_cards_with_gemini",
        ) as generate:
            result = news_weather.get_news_weather()

        generate.assert_not_called()
        self.assertEqual(result["weather"]["line1"], "오늘 날씨는 : CLOUDY")
        self.assertEqual(result["cards"], [])


if __name__ == "__main__":
    unittest.main()
