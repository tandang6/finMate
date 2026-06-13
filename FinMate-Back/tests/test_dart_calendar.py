import unittest
from unittest.mock import patch

import dart


class DartCalendarTest(unittest.TestCase):
    def setUp(self) -> None:
        dart._cache.clear()

    def test_calendar_keeps_earnings_reports_and_earnings_ir_only(self) -> None:
        sample_items = [
            {
                "rcept_dt": "20260507",
                "rcept_no": "20260507800004",
                "corp_name": "카카오",
                "stock_code": "035720",
                "report_nm": "연결재무제표기준영업(잠정)실적(공정공시)",
            },
            {
                "rcept_dt": "20260507",
                "rcept_no": "20260507800100",
                "corp_name": "카카오",
                "stock_code": "035720",
                "report_nm": "기업설명회(IR)개최(안내공시)",
            },
            {
                "rcept_dt": "20260514",
                "rcept_no": "20260514800111",
                "corp_name": "기아",
                "stock_code": "000270",
                "report_nm": "기업설명회(IR)개최(안내공시)",
            },
        ]

        def fake_document_text(rcept_no: str) -> str:
            if rcept_no == "20260514800111":
                return "개최 일시 2026년 5월 15일 10:00 2026년 1분기 경영실적 발표"
            return "개최일시 2026년 5월 7일 14:00 회사 소개 및 사업 현황 설명"

        with patch.object(dart, "DART_API_KEY", "test-key"), patch.object(
            dart,
            "_fetch_dart_list",
            return_value=sample_items,
        ) as fetch_list, patch.object(
            dart,
            "_fetch_dart_document_text",
            side_effect=fake_document_text,
        ) as fetch_document:
            result = dart.get_dart_calendar(days_back=1, days_ahead=1)

        titles = [event["title"] for event in result["events"]]
        kia_event = next(event for event in result["events"] if event["companyName"] == "기아")

        self.assertEqual(result["source"], "dart")
        self.assertEqual(fetch_list.call_count, 1)
        self.assertEqual(fetch_document.call_count, 2)
        self.assertEqual(len(result["events"]), 2)
        self.assertTrue(any("영업(잠정)실적" in title for title in titles))
        self.assertIn("기아 실적발표", titles)
        self.assertFalse(any("기업설명회" in title for title in titles))
        self.assertEqual(kia_event["datetime"], "2026-05-15T10:00:00")
        self.assertEqual(kia_event["calendarCategory"], "earnings_schedule")


if __name__ == "__main__":
    unittest.main()
