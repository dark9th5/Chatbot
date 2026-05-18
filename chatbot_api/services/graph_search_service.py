"""
Graph Search Service - hybrid retrieval over graph signals + article text.

Thiết kế mới:
1. Ưu tiên thực thể/chủ đề mạnh từ knowledge graph.
2. Bổ sung ACTION/TREND/STATE để câu hỏi không có tên riêng vẫn có tín hiệu.
3. Dùng full-text LIKE fallback khi graph chưa được rebuild hoặc câu hỏi chứa từ ngoài lexicon.
4. Nhận ra câu quá thiếu chủ thể kiểu "đang tăng mạnh không?" để tầng chatbot hỏi lại,
   thay vì cố đoán bừa một bài báo.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

import pymysql

from etl.ner_extractor import NERExtractor
from pipeline.config import MYSQL_CONFIG


class GraphSearchService:
    def __init__(self):
        self.ner = NERExtractor()
        self._conn = None
        self.last_query_analysis: Dict[str, Any] = {}

    @property
    def conn(self):
        if self._conn is None or not self._conn.open:
            self._conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        return self._conn

    @staticmethod
    def _dedupe(values: Iterable[str]) -> List[str]:
        ordered: List[str] = []
        seen = set()
        for value in values:
            normalized = value.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

    @staticmethod
    def _date_keyword_aliases(date_entities: Iterable[str]) -> List[str]:
        """
        Sinh các biến thể ngày giữ nguyên dấu phân cách để keyword fallback bắt
        được tiêu đề kiểu `16/5` hoặc `16.5`; bản chuẩn hóa của NER (`ngày 16 5`)
        không khớp trực tiếp với văn bản gốc trong DB.
        """
        aliases: List[str] = []
        for value in date_entities:
            match = re.search(
                r"(?P<day>\d{1,2})[/. -](?P<month>\d{1,2})(?:[/. -](?P<year>\d{2,4}))?",
                value,
            )
            if not match:
                continue
            day = int(match.group("day"))
            month = int(match.group("month"))
            aliases.extend(
                [
                    f"{day}/{month}",
                    f"{day:02d}/{month:02d}",
                    f"{day}.{month}",
                    f"{day:02d}.{month:02d}",
                ]
            )
        return GraphSearchService._dedupe(aliases)

    @staticmethod
    def _explicit_date_variants(target_date: date) -> List[str]:
        return GraphSearchService._dedupe(
            [
                f"{target_date.day}/{target_date.month}",
                f"{target_date.day:02d}/{target_date.month:02d}",
                f"{target_date.day}.{target_date.month}",
                f"{target_date.day:02d}.{target_date.month:02d}",
                f"{target_date.day}-{target_date.month}",
                f"{target_date.day:02d}-{target_date.month:02d}",
            ]
        )

    def _search_graph(
        self,
        terms: List[str],
        term_weights: Dict[str, float],
        limit: int,
        data_source: str,
        category: Optional[str],
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        if not terms:
            return []

        cursor = self.conn.cursor()
        format_strings = ",".join(["%s"] * len(terms))
        filter_sql, filter_params = self._build_article_filters(
            data_source=data_source,
            category=category,
            from_date=from_date,
            to_date=to_date,
        )
        sql = f"""
            SELECT
                a.id,
                a.title,
                a.content,
                a.source,
                a.link,
                a.published_date,
                GROUP_CONCAT(DISTINCT LOWER(ge.name) SEPARATOR '|') AS matched_terms,
                COUNT(DISTINCT ag.entity_id) AS match_count
            FROM articles a
            JOIN article_graph ag ON a.id = ag.article_id
            JOIN graph_entities ge ON ag.entity_id = ge.id
            WHERE LOWER(ge.name) IN ({format_strings})
            {filter_sql}
            GROUP BY a.id
            ORDER BY match_count DESC, a.published_date DESC
            LIMIT %s
        """
        cursor.execute(sql, tuple(terms) + tuple(filter_params) + (limit,))
        rows = cursor.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            matched_terms = self._dedupe((row.get("matched_terms") or "").split("|"))
            graph_score = sum(term_weights.get(term, 1.0) for term in matched_terms)
            results.append(
                {
                    "id": row["id"],
                    "content": row["content"],
                    "graph_score": float(graph_score),
                    "keyword_score": 0.0,
                    "score": float(graph_score),
                    "match_terms": matched_terms,
                    "metadata": {
                        "title": row["title"],
                        "source": row["source"],
                        "link": row["link"],
                        "published_date": row["published_date"],
                        "data_source": data_source,
                    },
                }
            )
        return results

    def _search_keyword_fallback(
        self,
        terms: List[str],
        term_weights: Dict[str, float],
        limit: int,
        data_source: str,
        required_primary_terms: Optional[List[str]],
        category: Optional[str],
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        if not terms:
            return []

        # Giữ truy vấn SQL gọn vừa đủ; cụm dài/chủ đề mạnh đi trước theo analysis.
        terms = terms[:10]
        score_parts: List[str] = []
        where_parts: List[str] = []
        score_params: List[Any] = []
        where_params: List[Any] = []
        required_parts: List[str] = []
        required_params: List[Any] = []

        for term in terms:
            like_term = f"%{term}%"
            weight = term_weights.get(term, 1.0)
            score_parts.append(
                "(CASE WHEN LOWER(a.title) LIKE %s THEN %s ELSE 0 END "
                "+ CASE WHEN LOWER(a.content) LIKE %s THEN %s ELSE 0 END)"
            )
            score_params.extend([like_term, weight * 2.0, like_term, weight])
            where_parts.extend(
                [
                    "LOWER(a.title) LIKE %s",
                    "LOWER(a.content) LIKE %s",
                ]
            )
            where_params.extend([like_term, like_term])

        for term in (required_primary_terms or [])[:6]:
            like_term = f"%{term}%"
            required_parts.extend(
                [
                    "LOWER(a.title) LIKE %s",
                    "LOWER(a.content) LIKE %s",
                ]
            )
            required_params.extend([like_term, like_term])

        filter_sql, filter_params = self._build_article_filters(
            data_source=data_source,
            category=category,
            from_date=from_date,
            to_date=to_date,
        )
        sql = f"""
            SELECT
                a.id,
                a.title,
                a.content,
                a.source,
                a.link,
                a.published_date,
                ({" + ".join(score_parts)}) AS keyword_score
            FROM articles a
            WHERE ({" OR ".join(where_parts)})
            {"AND (" + " OR ".join(required_parts) + ")" if required_parts else ""}
            {filter_sql}
            ORDER BY keyword_score DESC, a.published_date DESC
            LIMIT %s
        """
        cursor = self.conn.cursor()
        cursor.execute(
            sql,
            tuple(score_params + where_params + required_params + filter_params + [limit]),
        )
        rows = cursor.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            keyword_score = float(row.get("keyword_score") or 0.0)
            if keyword_score <= 0:
                continue
            results.append(
                {
                    "id": row["id"],
                    "content": row["content"],
                    "graph_score": 0.0,
                    "keyword_score": keyword_score,
                    "score": keyword_score * 0.75,
                    "match_terms": [],
                    "metadata": {
                        "title": row["title"],
                        "source": row["source"],
                        "link": row["link"],
                        "published_date": row["published_date"],
                        "data_source": data_source,
                    },
                }
            )
        return results

    def search_explicit_date_mentions(
        self,
        query: str,
        explicit_date: date,
        limit: int = 10,
        data_source: str = "news",
    ) -> List[Dict[str, Any]]:
        """
        Tìm riêng các bài thật sự nhắc tới ngày người dùng hỏi.

        Một số bài dự báo cho 16/5 được đăng tối 15/5, nên không thể chỉ dựa vào
        `published_date`. Luồng này yêu cầu đồng thời có ngày trong văn bản và có
        ít nhất một thực thể chính của câu hỏi để tránh kéo nhầm bài.
        """
        analysis = self.ner.analyze_query(query)
        required_primary_terms = self._dedupe(
            term
            for entity_type, values in (analysis.get("entities", {}) or {}).items()
            if entity_type in self.ner.PRIMARY_ANCHOR_TYPES
            for term in values
        )
        if not required_primary_terms:
            return []

        query_lower = query.casefold()
        secondary_terms = self._dedupe(
            [
                phrase
                for phrase in ("nhiệt độ", "thời tiết", "mưa dông", "nắng nóng")
                if phrase in query_lower
            ]
            + [
                term
                for term in (analysis.get("residual_keywords", []) or [])
                if len(term) >= 4
            ]
        )

        date_variants = self._explicit_date_variants(explicit_date)
        if not date_variants:
            return []

        date_parts: List[str] = []
        date_params: List[Any] = []
        for variant in date_variants:
            like_term = f"%{variant}%"
            date_parts.extend(
                [
                    "LOWER(a.title) LIKE %s",
                    "LOWER(a.content) LIKE %s",
                ]
            )
            date_params.extend([like_term, like_term])

        primary_parts: List[str] = []
        primary_params: List[Any] = []
        for term in required_primary_terms[:6]:
            like_term = f"%{term}%"
            primary_parts.extend(
                [
                    "LOWER(a.title) LIKE %s",
                    "LOWER(a.content) LIKE %s",
                ]
            )
            primary_params.extend([like_term, like_term])

        secondary_parts: List[str] = []
        secondary_params: List[Any] = []
        for term in secondary_terms[:6]:
            like_term = f"%{term}%"
            secondary_parts.extend(
                [
                    "LOWER(a.title) LIKE %s",
                    "LOWER(a.content) LIKE %s",
                ]
            )
            secondary_params.extend([like_term, like_term])

        filter_sql, filter_params = self._build_article_filters(
            data_source=data_source,
            category=None,
            from_date=None,
            to_date=None,
        )
        sql = f"""
            SELECT
                a.id,
                a.title,
                a.content,
                a.source,
                a.link,
                a.published_date,
                CHAR_LENGTH(a.content) AS content_length
            FROM articles a
            WHERE ({" OR ".join(date_parts)})
              AND ({" OR ".join(primary_parts)})
              {"AND (" + " OR ".join(secondary_parts) + ")" if secondary_parts else ""}
              {filter_sql}
            ORDER BY CHAR_LENGTH(a.content) DESC, a.published_date DESC
            LIMIT %s
        """
        cursor = self.conn.cursor()
        cursor.execute(
            sql,
            tuple(date_params + primary_params + secondary_params + filter_params + [limit]),
        )

        results: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            content_length = int(row.get("content_length") or 0)
            # Ưu tiên cứng cho bài nhắc đúng ngày; độ dài nội dung chỉ là tie-break
            # để chọn nguồn đủ chất liệu cho LLM thay vì các snippet tiêu đề.
            exact_date_score = 50.0 + min(content_length / 1000.0, 5.0)
            results.append(
                {
                    "id": row["id"],
                    "content": row["content"],
                    "graph_score": exact_date_score,
                    "keyword_score": 0.0,
                    "score": exact_date_score,
                    "match_terms": [],
                    "metadata": {
                        "title": row["title"],
                        "source": row["source"],
                        "link": row["link"],
                        "published_date": row["published_date"],
                        "data_source": data_source,
                    },
                }
            )
        return results

    @staticmethod
    def _build_article_filters(
        data_source: str,
        category: Optional[str],
        from_date: Optional[date],
        to_date: Optional[date],
    ) -> tuple[str, List[Any]]:
        clauses: List[str] = []
        params: List[Any] = []

        if data_source == "documents":
            clauses.append("a.link LIKE %s")
        else:
            clauses.append("a.link NOT LIKE %s")
        params.append("upload://%")
        if category and category.strip():
            clauses.append("a.category = %s")
            params.append(category.strip())
        if from_date is not None:
            clauses.append("a.published_date >= %s")
            params.append(from_date)
        if to_date is not None:
            # `published_date` là DATETIME trong MySQL. So sánh `<= 2026-05-18`
            # sẽ vô tình chỉ giữ tới đúng 00:00:00 của ngày đó. Dùng cận trên mở
            # của ngày kế tiếp để bao trọn cả ngày người dùng hỏi.
            clauses.append("a.published_date < %s")
            params.append(to_date + timedelta(days=1))

        if not clauses:
            return "", params
        return " AND " + " AND ".join(clauses), params

    @staticmethod
    def _merge_results(*batches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[Any, Dict[str, Any]] = {}
        for batch in batches:
            for item in batch:
                article_id = item["id"]
                if article_id not in merged:
                    merged[article_id] = item.copy()
                    merged[article_id]["match_terms"] = list(item.get("match_terms", []))
                    continue

                current = merged[article_id]
                current["graph_score"] = max(
                    float(current.get("graph_score", 0.0)),
                    float(item.get("graph_score", 0.0)),
                )
                current["keyword_score"] = max(
                    float(current.get("keyword_score", 0.0)),
                    float(item.get("keyword_score", 0.0)),
                )
                current["score"] = current["graph_score"] + current["keyword_score"] * 0.75
                current["match_terms"] = GraphSearchService._dedupe(
                    list(current.get("match_terms", [])) + list(item.get("match_terms", []))
                )

        return sorted(
            merged.values(),
            key=lambda item: (
                float(item.get("score", 0.0)),
                float(item.get("graph_score", 0.0)),
                float(item.get("keyword_score", 0.0)),
            ),
            reverse=True,
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        data_source: str = "news",
        category: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm lai:
        - Graph score cho thực thể/chủ đề đã index.
        - Keyword fallback cho semantic signal và từ ngoài lexicon.
        - Nếu câu không có mỏ neo ngữ nghĩa, để tầng trên hỏi lại thay vì đoán.
        """
        analysis = self.ner.analyze_query(query)
        self.last_query_analysis = analysis

        # If analysis suggests clarification, do not short-circuit the whole
        # search. Allow keyword fallback to run so short/ambiguous queries can
        # still return results when possible. The caller can still inspect
        # `last_query_analysis` to decide whether to ask for clarification.

        date_aliases = self._date_keyword_aliases(
            (analysis.get("entities", {}) or {}).get("DATE", [])
        )
        search_terms = self._dedupe(list(analysis["search_terms"]) + date_aliases)
        term_weights = dict(analysis["term_weights"])
        term_weights.update(
            {
                alias: max(float(term_weights.get(alias, 0.0)), 2.5)
                for alias in date_aliases
            }
        )
        required_primary_terms = self._dedupe(
            term
            for entity_type, values in (analysis.get("entities", {}) or {}).items()
            if entity_type in self.ner.PRIMARY_ANCHOR_TYPES
            for term in values
        )
        graph_results = self._search_graph(
            search_terms,
            term_weights,
            limit=max(limit * 4, limit),
            data_source=data_source,
            category=category,
            from_date=from_date,
            to_date=to_date,
        )
        keyword_results = self._search_keyword_fallback(
            search_terms,
            term_weights,
            limit=max(limit * 4, limit),
            data_source=data_source,
            required_primary_terms=required_primary_terms,
            category=category,
            from_date=from_date,
            to_date=to_date,
        )

        return self._merge_results(graph_results, keyword_results)[:limit]

    def close(self):
        if self._conn:
            self._conn.close()
