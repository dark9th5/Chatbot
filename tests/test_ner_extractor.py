from __future__ import annotations

import unittest

from etl.ner_extractor import NERExtractor


class NERExtractorQueryAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ner = NERExtractor()

    def test_extracts_topic_time_and_trend(self) -> None:
        analysis = self.ner.analyze_query("Giá vàng hôm nay tăng mạnh không?")

        self.assertIn("giá vàng", analysis["entities"]["TOPIC"])
        self.assertIn("hôm nay", analysis["entities"]["DATE"])
        self.assertIn("tăng mạnh", analysis["entities"]["TREND"])
        self.assertFalse(analysis["requires_clarification"])

    def test_marks_verb_only_query_as_underspecified(self) -> None:
        analysis = self.ner.analyze_query("Đang tăng mạnh không?")

        self.assertIn("tăng mạnh", analysis["entities"]["TREND"])
        self.assertTrue(analysis["requires_clarification"])

    def test_topic_plus_action_is_searchable_without_named_entity(self) -> None:
        analysis = self.ner.analyze_query("Mưa lớn còn kéo dài không?")

        self.assertIn("mưa lớn", analysis["entities"]["TOPIC"])
        self.assertIn("kéo dài", analysis["entities"]["ACTION"])
        self.assertEqual(["mưa lớn"], analysis["anchor_terms"])
        self.assertFalse(analysis["requires_clarification"])

    def test_question_intent_is_preserved_for_clarification(self) -> None:
        analysis = self.ner.analyze_query("Bao giờ giảm?")

        self.assertIn("WHEN", analysis["question_intents"])
        self.assertIn("giảm", analysis["entities"]["TREND"])
        self.assertTrue(analysis["requires_clarification"])

    def test_generic_travel_query_is_marked_underspecified(self) -> None:
        analysis = self.ner.analyze_query("Đi đâu chơi đây?")

        self.assertIn("WHERE", analysis["question_intents"])
        self.assertTrue(analysis["requires_clarification"])

    def test_extracts_structured_news_entities(self) -> None:
        entities = self.ner.extract_entities(
            "Công ty Cổ phần FPT công bố tại số 10 đường Nguyễn Huệ lúc 08:30-10:00, "
            "mã cổ phiếu FPT tăng 3,5% sau chuyến bay VN123 và hashtag #AI."
        )

        self.assertIn("công ty cổ phần fpt", entities["ORG"])
        self.assertIn("số 10 đường nguyễn huệ", entities["ADDRESS"])
        self.assertIn("08:30-10:00", entities["TIME"])
        self.assertIn("fpt", entities["STOCK_TICKER"])
        self.assertIn("vn123", entities["IDENTIFIER"])
        self.assertIn("#ai", entities["HASHTAG"])

    def test_aliases_are_expanded_for_retrieval(self) -> None:
        analysis = self.ner.analyze_query("Tin mới ở TP HCM hôm nay?")

        self.assertIn("tp hcm", analysis["anchor_terms"])
        self.assertIn("thành phố hồ chí minh", analysis["alias_terms"])
        self.assertIn("sài gòn", analysis["search_terms"])

    def test_dynamic_products_and_indexes_are_detected(self) -> None:
        entities = self.ner.extract_entities(
            "iPhone 17 Pro Max ra mắt khi VN-Index lập đỉnh và S&P 500 tăng."
        )

        self.assertIn("iphone 17 pro max", entities["PRODUCT"])
        self.assertIn("vn-index", entities["INDEX"])
        self.assertIn("s&p 500", entities["INDEX"])

    def test_money_and_duration_cover_common_news_forms(self) -> None:
        entities = self.ner.extract_entities(
            "Dự án có vốn 3,5 tỷ đồng, hoàn thành sau 18 tháng."
        )

        self.assertIn("3,5 tỷ đồng", entities["MONEY"])
        self.assertIn("18 tháng", entities["DURATION"])

    def test_uppercase_ai_is_detected_as_topic(self) -> None:
        analysis = self.ner.analyze_query("Tình hình AI tại Việt Nam hiện nay như thế nào?")

        self.assertIn("ai", analysis["entities"]["TOPIC"])
        self.assertIn("ai", analysis["anchor_terms"])
        self.assertFalse(analysis["requires_clarification"])

    def test_generic_location_anchor_promotes_focus_keywords(self) -> None:
        analysis = self.ner.analyze_query("Tình hình ngoại giao của Việt Nam hiện nay như nào?")

        self.assertIn("ngoại giao", analysis["anchor_terms"])
        self.assertFalse(analysis["requires_clarification"])

    def test_domain_topic_lexicon_covers_maritime_sovereignty(self) -> None:
        analysis = self.ner.analyze_query("Tình hình chủ quyền biển đảo hiện nay ra sao?")

        self.assertIn("chủ quyền biển đảo", analysis["entities"]["TOPIC"])
        self.assertFalse(analysis["requires_clarification"])

    def test_domain_topic_lexicon_covers_digital_transformation(self) -> None:
        analysis = self.ner.analyze_query("Tiến độ chuyển đổi số quốc gia hiện nay như thế nào?")

        self.assertIn("chuyển đổi số", analysis["entities"]["TOPIC"])
        self.assertIn("chuyển đổi số", analysis["anchor_terms"])

    def test_domain_org_lexicon_covers_meteorology_agency(self) -> None:
        entities = self.ner.extract_entities(
            "Trung tâm Dự báo Khí tượng Thủy văn Quốc gia cảnh báo mưa lớn diện rộng."
        )

        self.assertIn("trung tâm dự báo khí tượng thủy văn quốc gia", entities["ORG"])

    def test_domain_product_lexicon_covers_modern_ai_models(self) -> None:
        entities = self.ner.extract_entities(
            "OpenAI giới thiệu GPT 5 và cập nhật ChatGPT 4o cho người dùng doanh nghiệp."
        )

        self.assertIn("gpt 5", entities["PRODUCT"])
        self.assertIn("chatgpt 4o", entities["PRODUCT"])


if __name__ == "__main__":
    unittest.main()
