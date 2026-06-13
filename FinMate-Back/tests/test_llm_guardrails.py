import unittest

from llm_guardrails import (
    LLM_GUARDRAIL_EVAL_CASES,
    build_guardrail_instruction,
    build_system_instruction,
    ensure_safe_llm_text,
    has_prohibited_investment_advice,
    iter_eval_cases,
    sanitize_llm_payload,
)


class LLMGuardrailEvalTest(unittest.TestCase):
    def test_eval_suite_has_exactly_twenty_named_cases(self) -> None:
        cases = list(iter_eval_cases())

        self.assertEqual(len(cases), 20)
        self.assertEqual(len({case["id"] for case in cases}), 20)
        for case in cases:
            self.assertIn(case["surface"], {"chat", "news_weather", "calendar_insight", "domino_insight"})
            self.assertTrue(case["user_input"])
            self.assertTrue(case["unsafe_output"])

    def test_all_eval_cases_are_detected_and_rewritten(self) -> None:
        for case in LLM_GUARDRAIL_EVAL_CASES:
            with self.subTest(case=case["id"]):
                self.assertTrue(has_prohibited_investment_advice(case["unsafe_output"]))

                safe_output = ensure_safe_llm_text(case["unsafe_output"], case["surface"])

                self.assertNotEqual(safe_output, case["unsafe_output"])
                self.assertFalse(has_prohibited_investment_advice(safe_output))

    def test_safe_educational_answer_passes_through(self) -> None:
        safe_text = (
            "이 뉴스는 시장 심리에 영향을 줄 수 있어요. "
            "다만 원문과 발행일, 공시 여부를 함께 확인해 주세요."
        )

        self.assertEqual(ensure_safe_llm_text(safe_text, "chat"), safe_text)

    def test_guardrail_instruction_contains_core_policy(self) -> None:
        instruction = build_system_instruction("chat", "너는 FinMate 금융 학습 멘토다.")

        self.assertIn("투자 권유", instruction)
        self.assertIn("매수/매도", instruction)
        self.assertIn("수익 보장", instruction)
        self.assertIn("출처", instruction)
        self.assertIn("불확실", instruction)
        self.assertIn("교육 및 정보 제공용", instruction)

    def test_surface_specific_rules_are_present(self) -> None:
        self.assertIn("뉴스 목록", build_guardrail_instruction("news_weather"))
        self.assertIn("기업 일정", build_guardrail_instruction("calendar_insight"))
        self.assertIn("ECOS", build_guardrail_instruction("domino_insight"))

    def test_nested_payload_sanitization_keeps_shape(self) -> None:
        payload = {
            "weather": {
                "line1": "오늘 날씨는 : SUNNY",
                "line2": "반도체주는 지금 매수하세요.",
                "line3": "수익 보장 흐름입니다.",
            },
            "cards": [
                {
                    "category": "반도체",
                    "title": "반도체 강세",
                    "summary": "대형주가 강세입니다.",
                    "insight": "강력 매수 추천입니다.",
                    "url": "https://example.com/news/1",
                }
            ],
        }

        sanitized = sanitize_llm_payload(payload, "news_weather")

        self.assertEqual(set(sanitized.keys()), {"weather", "cards"})
        self.assertEqual(sanitized["cards"][0]["url"], "https://example.com/news/1")
        self.assertFalse(has_prohibited_investment_advice(sanitized["weather"]["line2"]))
        self.assertFalse(has_prohibited_investment_advice(sanitized["weather"]["line3"]))
        self.assertFalse(has_prohibited_investment_advice(sanitized["cards"][0]["insight"]))


if __name__ == "__main__":
    unittest.main()
