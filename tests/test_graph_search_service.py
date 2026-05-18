from __future__ import annotations

import unittest
from datetime import date

from chatbot_api.services.graph_search_service import GraphSearchService


class _FakeCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.params = ()

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return []


class _FakeConnection:
    open = True

    def __init__(self) -> None:
        self.cursor_obj = _FakeCursor()

    def cursor(self):
        return self.cursor_obj


class GraphSearchServiceFilterTests(unittest.TestCase):
    def test_news_filter_uses_parameterized_upload_prefix(self) -> None:
        sql, params = GraphSearchService._build_article_filters(
            data_source="news",
            category=None,
            from_date=None,
            to_date=None,
        )

        self.assertEqual(" AND a.link NOT LIKE %s", sql)
        self.assertEqual(["upload://%"], params)



    def test_keyword_fallback_requires_primary_anchor_when_present(self) -> None:
        service = GraphSearchService()
        service._conn = _FakeConnection()

        service._search_keyword_fallback(
            terms=["nguyễn chí lực", "dùng", "jetpack"],
            term_weights={"nguyễn chí lực": 4.0, "dùng": 4.0, "jetpack": 4.0},
            limit=3,
            data_source="news",
            required_primary_terms=["nguyễn chí lực"],
            category=None,
            from_date=None,
            to_date=None,
        )

        sql = service._conn.cursor_obj.sql
        params = service._conn.cursor_obj.params
        self.assertIn("AND (LOWER(a.title) LIKE %s OR LOWER(a.content) LIKE %s)", sql)
        self.assertIn("%nguyễn chí lực%", params)

    def test_date_aliases_keep_original_separators_for_keyword_search(self) -> None:
        aliases = GraphSearchService._date_keyword_aliases(["ngày 16/5"])

        self.assertIn("16/5", aliases)
        self.assertIn("16.5", aliases)


if __name__ == "__main__":
    unittest.main()
