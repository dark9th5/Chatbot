from __future__ import annotations

import unittest
from datetime import date, datetime

from chatbot_api.services.chatbot_service import ChatbotService
from etl.ner_extractor import NERExtractor


class _FakeGraphSearchService:
    def __init__(self) -> None:
        self.ner = NERExtractor()
        self.last_query_analysis = {}
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        self.last_query_analysis = self.ner.analyze_query(kwargs["query"])
        query_lower = kwargs["query"].casefold()
        if "hà nội" in query_lower or "nhiệt độ" in query_lower:
            content = "Dự báo ngày 16/5 tại Hà Nội, nhiệt độ phổ biến 35 độ C vào buổi trưa."
            title = "Thời tiết Hà Nội ngày 16/5"
        else:
            content = "Du lịch biển phù hợp cho kỳ nghỉ một tuần với nhiều hoạt động ngoài trời."
            title = "Gợi ý du lịch biển"
        return [
            {
                "id": 1,
                "content": content,
                "score": 2.0,
                "keyword_score": 1.0,
                "metadata": {
                    "title": title,
                    "source": "Test",
                    "link": "",
                },
            }
        ]

    def search_explicit_date_mentions(self, **kwargs):
        return []

    @staticmethod
    def _merge_results(*batches):
        return [item for batch in batches for item in batch]


class _FakeProvider:
    provider_name = "fake"


class _FakeLLMService:
    provider = _FakeProvider()

    def __init__(self) -> None:
        self.questions = []
        self.answers = []

    def generate_answer(
        self,
        context: str,
        question: str,
        source_label: str,
        reference_date: str | None = None,
    ) -> str:
        self.questions.append(question)
        answer = self.answers.pop(0) if self.answers else "Bạn có thể cân nhắc các điểm đến biển phù hợp cho chuyến đi một tuần."
        return answer


class ChatbotServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = _FakeGraphSearchService()
        self.llm = _FakeLLMService()
        self.service = ChatbotService(
            graph_search_service=self.graph,
            article_repository=None,
            llm_service=self.llm,
            query_expansion_service=None,
        )

    def test_generic_travel_query_requests_clarification(self) -> None:
        response = self.service.get_answer(
            question="Đi chơi ở đâu thì tốt?",
            category="Du lịch",
        )

        self.assertTrue(response.needs_clarification)
        self.assertEqual([], self.graph.calls)

    def test_follow_up_reuses_context_and_filters(self) -> None:
        response = self.service.get_answer(
            question="Tôi muốn đi biển, tầm 1 tuần",
            category="Du lịch",
            conversation_context="Đi chơi ở đâu thì tốt?",
        )

        self.assertFalse(response.needs_clarification)
        self.assertEqual("Du lịch", self.graph.calls[0]["category"])
        self.assertIn("Đi chơi ở đâu thì tốt?", self.graph.calls[0]["query"])
        self.assertIn("Tôi muốn đi biển, tầm 1 tuần", self.llm.questions[0])

    def test_explicit_date_query_is_anchored_in_answer(self) -> None:
        self.llm.answers.append("Nhiệt độ Hà Nội hôm nay ở mức 35 độ C.")

        response = self.service.get_answer(
            question="Nhiệt độ tại Hà Nội ngày 16/5 là bao nhiêu?",
        )

        self.assertIn("ngày 16/5/", response.answer)
        self.assertNotIn("hôm nay", response.answer.lower())
        self.assertEqual("news", self.graph.calls[0]["data_source"])
        self.assertIsNone(self.graph.calls[0]["from_date"])
        self.assertIsNone(self.graph.calls[0]["to_date"])
        self.assertGreater(self.graph.calls[0]["limit"], 3)



    def test_source_dates_accept_datetime_strings(self) -> None:
        self.assertEqual(
            date(2026, 5, 16),
            self.service._normalize_source_date("2026-05-16 20:55:43"),
        )
        self.assertEqual(
            date(2026, 5, 16),
            self.service._normalize_source_date(datetime(2026, 5, 16, 20, 55, 43)),
        )



    def test_extract_date_range_understands_tomorrow(self) -> None:
        tomorrow_start, tomorrow_end = self.service._extract_date_range("Ngày mai có nóng không?")
        self.assertEqual(tomorrow_start, tomorrow_end)
        self.assertIsNotNone(tomorrow_start)

    def test_explicit_date_results_prefer_textual_date_mentions(self) -> None:
        results = [
            {
                "id": 1,
                "content": "Bài khác không nhắc đúng ngày.",
                "metadata": {"title": "Tin Hà Nội"},
            },
            {
                "id": 2,
                "content": "Dự báo ngày 16/5 tại Hà Nội nắng nóng.",
                "metadata": {"title": "Dự báo thời tiết"},
            },
        ]

        ordered = self.service._prefer_explicit_date_results(results, date(2026, 5, 16))

        self.assertEqual(2, ordered[0]["id"])





    def test_news_returns_empty_response_when_context_is_irrelevant(self) -> None:
        response = self.service.get_answer(
            question="Tình hình ngoại giao của Việt Nam hiện nay như nào?",
        )

        self.assertEqual([], response.sources)
        self.assertIn("chưa tìm thấy thông tin phù hợp", response.answer.lower())
        self.assertEqual([], self.llm.questions)

    def test_no_info_answer_does_not_include_sources(self) -> None:
        self.llm.answers.append("Tôi không tìm thấy thông tin này trong các bài báo")

        response = self.service.get_answer(
            question="Đi biển ở đâu đẹp cho kỳ nghỉ?",
        )

        self.assertEqual([], response.sources)


if __name__ == "__main__":
    unittest.main()
