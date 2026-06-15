import hashlib
import sys
import time
from pathlib import Path
from typing import Dict, List

import pymysql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from etl.content_cleaner import strip_article_boilerplate
from etl.ner_extractor import NERExtractor
from pipeline.config import MYSQL_CONFIG


class KnowledgeGraphBuilder:
    GRAPH_INDEX_TYPES = {
        "PERSON",
        "ORG",
        "LOC",
        "MONEY",
        "DATE",
        "TIME",
        "EVENT",
        "PRODUCT",
        "LAW",
        "PERCENT",
        "TEMPERATURE",
        "SCORE",
        "FACILITY",
        "VEHICLE",
        "AWARD",
        "DISEASE",
        "SPORT_TEAM",
        "WORK_OF_ART",
        "LANGUAGE",
        "NATIONALITY",
        "CRYPTO",
        "ADDRESS",
        "IDENTIFIER",
        "STOCK_TICKER",
        "INDEX",
        "TOPIC",
    }
    SIGNATURE_VERSION = "knowledge-graph-builder-v5"

    def __init__(self):
        self.ner = NERExtractor()
        self.conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        self._entity_id_cache = {}

    def _to_vi_entity_type(self, entity_type: str) -> str:
        return self.ner.VI_TYPE_MAP.get(entity_type, entity_type)

    def _to_vi_attribute_key(self, attribute_key: str) -> str:
        return self.ner.VI_TYPE_MAP.get(attribute_key, attribute_key)

    def _get_cursor(self):
        if not self.conn.open:
            self.conn.ping(reconnect=True)
        return self.conn.cursor()

    def _table_exists(self, table_name: str) -> bool:
        cursor = self._get_cursor()
        cursor.execute("SHOW TABLES LIKE %s", (table_name,))
        return cursor.fetchone() is not None

    def _check_graph_entities_schema(self):
        try:
            cursor = self._get_cursor()
            cursor.execute(
                """
                SELECT COLUMN_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'graph_entities'
                  AND COLUMN_NAME = 'type'
                """,
                (MYSQL_CONFIG.get("database"),),
            )
            row = cursor.fetchone()
            if row and row.get("COLUMN_TYPE") and "enum" in row["COLUMN_TYPE"].lower():
                print("[Graph] Widening graph_entities.type from ENUM to VARCHAR(100).")
                cursor.execute("ALTER TABLE graph_entities MODIFY COLUMN `type` VARCHAR(100) NOT NULL")
                self.conn.commit()
        except Exception as exc:
            print(f"[Graph] Could not check graph_entities schema: {exc}")

    def _init_graph_tables(self):
        cursor = self._get_cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_entities (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                type VARCHAR(100) NOT NULL,
                UNIQUE KEY uk_entity_name_type (name, type),
                INDEX idx_entity_name (name),
                INDEX idx_entity_type (type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS article_graph (
                id INT AUTO_INCREMENT PRIMARY KEY,
                article_id INT NOT NULL,
                entity_id INT NOT NULL,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                FOREIGN KEY (entity_id) REFERENCES graph_entities(id) ON DELETE CASCADE,
                UNIQUE KEY uk_article_entity (article_id, entity_id),
                INDEX idx_article_graph_article (article_id),
                INDEX idx_article_graph_entity (entity_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS article_graph_index (
                article_id INT PRIMARY KEY,
                extractor_signature CHAR(64) NOT NULL,
                content_hash CHAR(64) NOT NULL,
                entity_count INT NOT NULL DEFAULT 0,
                relation_count INT NOT NULL DEFAULT 0,
                attribute_count INT NOT NULL DEFAULT 0,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                INDEX idx_graph_index_signature (extractor_signature),
                INDEX idx_graph_index_processed_at (processed_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_build_metadata (
                meta_key VARCHAR(100) PRIMARY KEY,
                meta_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        self.conn.commit()

    def _init_relations_table(self):
        cursor = self._get_cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS entity_relations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                subject_id INT NOT NULL,
                relation_type VARCHAR(100) NOT NULL,
                object_id INT NOT NULL,
                article_id INT NOT NULL,
                FOREIGN KEY (subject_id) REFERENCES graph_entities(id) ON DELETE CASCADE,
                FOREIGN KEY (object_id) REFERENCES graph_entities(id) ON DELETE CASCADE,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                UNIQUE KEY uk_relation (subject_id, relation_type, object_id, article_id),
                INDEX idx_entity_relations_article (article_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS entity_attributes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                entity_id INT NOT NULL,
                attribute_key VARCHAR(100) NOT NULL,
                attribute_value VARCHAR(255) NOT NULL,
                article_id INT NOT NULL,
                FOREIGN KEY (entity_id) REFERENCES graph_entities(id) ON DELETE CASCADE,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                UNIQUE KEY uk_attribute (entity_id, attribute_key, attribute_value, article_id),
                INDEX idx_entity_attributes_article (article_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        self.conn.commit()

    def _current_extractor_signature(self) -> str:
        root = Path(__file__).resolve().parents[1]
        tracked_files = [
            root / "etl" / "ner_extractor.py",
            root / "etl" / "content_cleaner.py",
            root / "pipeline" / "knowledge_graph_builder.py",
            root / "data" / "ner_lexicons.json",
            root / "data" / "ner_titlecase_lexicons.json",
            root / "requirements.txt",
        ]

        digest = hashlib.sha256()
        digest.update(self.SIGNATURE_VERSION.encode("utf-8"))
        for path in tracked_files:
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(path.read_bytes() if path.exists() else b"<missing>")
        return digest.hexdigest()

    def _article_content_hash(self, article: Dict) -> str:
        title = article.get("title") or ""
        content = article.get("content") or ""
        return hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()

    def _article_full_text_for_ner(self, article: Dict) -> str:
        title = article.get("title") or ""
        content = strip_article_boilerplate(
            article.get("content") or "",
            article.get("source"),
        )
        return f"{title}. {content}".strip()

    def _get_metadata(self, key: str):
        cursor = self._get_cursor()
        cursor.execute("SELECT meta_value FROM graph_build_metadata WHERE meta_key = %s", (key,))
        row = cursor.fetchone()
        return row["meta_value"] if row else None

    def _set_metadata(self, key: str, value: str):
        cursor = self._get_cursor()
        cursor.execute(
            """
            INSERT INTO graph_build_metadata (meta_key, meta_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE meta_value = VALUES(meta_value)
            """,
            (key, value),
        )
        self.conn.commit()

    def _has_existing_graph_data(self) -> bool:
        cursor = self._get_cursor()
        for table_name in ("article_graph", "entity_relations", "entity_attributes"):
            if not self._table_exists(table_name):
                continue
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM {table_name}")
            if cursor.fetchone()["cnt"] > 0:
                return True
        return False

    def _backfill_existing_index(self, signature: str):
        cursor = self._get_cursor()
        cursor.execute(
            """
            INSERT INTO article_graph_index (
                article_id,
                extractor_signature,
                content_hash,
                entity_count,
                relation_count,
                attribute_count
            )
            SELECT
                a.id,
                %s,
                SHA2(CONCAT(COALESCE(a.title, ''), '\n', COALESCE(a.content, '')), 256),
                COALESCE(ag.entity_count, 0),
                COALESCE(er.relation_count, 0),
                COALESCE(ea.attribute_count, 0)
            FROM articles a
            LEFT JOIN (
                SELECT article_id, COUNT(*) AS entity_count
                FROM article_graph
                GROUP BY article_id
            ) ag ON ag.article_id = a.id
            LEFT JOIN (
                SELECT article_id, COUNT(*) AS relation_count
                FROM entity_relations
                GROUP BY article_id
            ) er ON er.article_id = a.id
            LEFT JOIN (
                SELECT article_id, COUNT(*) AS attribute_count
                FROM entity_attributes
                GROUP BY article_id
            ) ea ON ea.article_id = a.id
            WHERE a.content IS NOT NULL
              AND (
                COALESCE(ag.entity_count, 0) > 0
                OR COALESCE(er.relation_count, 0) > 0
                OR COALESCE(ea.attribute_count, 0) > 0
              )
            ON DUPLICATE KEY UPDATE
                extractor_signature = VALUES(extractor_signature),
                content_hash = VALUES(content_hash),
                entity_count = VALUES(entity_count),
                relation_count = VALUES(relation_count),
                attribute_count = VALUES(attribute_count)
            """,
            (signature,),
        )
        self.conn.commit()
        print(f"[Graph] Backfilled graph index rows: {cursor.rowcount}")

    def reset_graph(self):
        cursor = self._get_cursor()
        print("[Graph] Resetting derived graph data...")
        for table_name in (
            "entity_attributes",
            "entity_relations",
            "article_graph",
            "article_graph_index",
            "graph_entities",
        ):
            if self._table_exists(table_name):
                cursor.execute(f"DELETE FROM {table_name}")
        self.conn.commit()

    def _get_articles_to_process(self, signature: str) -> List[Dict]:
        cursor = self._get_cursor()
        cursor.execute(
            """
            SELECT a.id, a.title, a.content, a.source
            FROM articles a
            LEFT JOIN article_graph_index idx ON idx.article_id = a.id
            WHERE a.content IS NOT NULL
              AND (
                idx.article_id IS NULL
                OR idx.extractor_signature <> %s
                OR idx.content_hash <> SHA2(CONCAT(COALESCE(a.title, ''), '\n', COALESCE(a.content, '')), 256)
              )
            ORDER BY a.id ASC
            """,
            (signature,),
        )
        return cursor.fetchall()

    def _clear_article_graph(self, article_id: int):
        cursor = self._get_cursor()
        cursor.execute("DELETE FROM entity_attributes WHERE article_id = %s", (article_id,))
        cursor.execute("DELETE FROM entity_relations WHERE article_id = %s", (article_id,))
        cursor.execute("DELETE FROM article_graph WHERE article_id = %s", (article_id,))
        cursor.execute("DELETE FROM article_graph_index WHERE article_id = %s", (article_id,))

    def _get_or_create_entity_id(self, cursor, name: str, vi_type: str):
        cache_key = (name, vi_type)
        if cache_key in self._entity_id_cache:
            return self._entity_id_cache[cache_key], False

        cursor.execute(
            "SELECT id FROM graph_entities WHERE name = %s AND type = %s LIMIT 1",
            (name, vi_type),
        )
        row = cursor.fetchone()
        if row:
            self._entity_id_cache[cache_key] = row["id"]
            return row["id"], False

        cursor.execute("INSERT INTO graph_entities (name, type) VALUES (%s, %s)", (name, vi_type))
        self._entity_id_cache[cache_key] = cursor.lastrowid
        return cursor.lastrowid, True

    def _extract_unique_entities(self, entities_dict: Dict[str, List[str]]):
        unique_entities = set()
        for entity_type, names in entities_dict.items():
            if entity_type not in self.GRAPH_INDEX_TYPES:
                continue
            for name in names:
                name_clean = name.strip().lower()
                if len(name_clean) > 2:
                    unique_entities.add(
                        (name_clean, entity_type, self._to_vi_entity_type(entity_type))
                    )
        return unique_entities

    def _process_article(self, article: Dict, signature: str) -> Dict[str, int]:
        cursor = self._get_cursor()
        article_id = article["id"]
        full_text = self._article_full_text_for_ner(article)
        entities_dict = self.ner.extract_entities(full_text)
        self._clear_article_graph(article_id)

        counts = {"entities": 0, "relations": 0, "attributes": 0}
        new_type_counts = {}
        article_entity_ids = {}

        for name, _entity_type, vi_type in self._extract_unique_entities(entities_dict):
            entity_id, inserted = self._get_or_create_entity_id(cursor, name, vi_type)
            article_entity_ids[(name, vi_type)] = entity_id
            if inserted:
                new_type_counts[vi_type] = new_type_counts.get(vi_type, 0) + 1

            cursor.execute(
                "INSERT IGNORE INTO article_graph (article_id, entity_id) VALUES (%s, %s)",
                (article_id, entity_id),
            )
            if cursor.rowcount > 0:
                counts["entities"] += 1

        for rel in self.ner.extract_relations(full_text, entities_dict=entities_dict):
            if rel["subject_type"] not in self.GRAPH_INDEX_TYPES or rel["object_type"] not in self.GRAPH_INDEX_TYPES:
                continue
            subject_key = (rel["subject"].lower(), self._to_vi_entity_type(rel["subject_type"]))
            object_key = (rel["object"].lower(), self._to_vi_entity_type(rel["object_type"]))
            subject_id = article_entity_ids.get(subject_key)
            object_id = article_entity_ids.get(object_key)
            if not subject_id:
                subject_id, _ = self._get_or_create_entity_id(cursor, *subject_key)
                article_entity_ids[subject_key] = subject_id
            if not object_id:
                object_id, _ = self._get_or_create_entity_id(cursor, *object_key)
                article_entity_ids[object_key] = object_id

            cursor.execute(
                """
                INSERT IGNORE INTO entity_relations
                    (subject_id, relation_type, object_id, article_id)
                VALUES (%s, %s, %s, %s)
                """,
                (subject_id, rel["relation"], object_id, article_id),
            )
            if cursor.rowcount > 0:
                counts["relations"] += 1

        for attr in self.ner.extract_attributes(full_text, entities_dict=entities_dict):
            if attr["entity_type"] not in self.GRAPH_INDEX_TYPES:
                continue
            entity_key = (attr["entity"].lower(), self._to_vi_entity_type(attr["entity_type"]))
            entity_id = article_entity_ids.get(entity_key)
            if not entity_id:
                entity_id, _ = self._get_or_create_entity_id(cursor, *entity_key)
                article_entity_ids[entity_key] = entity_id

            cursor.execute(
                """
                INSERT IGNORE INTO entity_attributes
                    (entity_id, attribute_key, attribute_value, article_id)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    entity_id,
                    self._to_vi_attribute_key(attr["attribute_key"]),
                    attr["attribute_value"],
                    article_id,
                ),
            )
            if cursor.rowcount > 0:
                counts["attributes"] += 1

        cursor.execute(
            """
            INSERT INTO article_graph_index (
                article_id,
                extractor_signature,
                content_hash,
                entity_count,
                relation_count,
                attribute_count
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                extractor_signature = VALUES(extractor_signature),
                content_hash = VALUES(content_hash),
                entity_count = VALUES(entity_count),
                relation_count = VALUES(relation_count),
                attribute_count = VALUES(attribute_count)
            """,
            (
                article_id,
                signature,
                self._article_content_hash(article),
                counts["entities"],
                counts["relations"],
                counts["attributes"],
            ),
        )

        counts["new_type_counts"] = new_type_counts
        return counts

    def build_graph(self, full_rebuild: bool = False):
        print("\n[Graph] START KNOWLEDGE GRAPH BUILD")
        print("=" * 60)

        self._init_graph_tables()
        self._check_graph_entities_schema()
        self._init_relations_table()

        signature = self._current_extractor_signature()
        stored_signature = self._get_metadata("extractor_signature")

        if full_rebuild:
            print("[Graph] Full rebuild requested.")
            self.reset_graph()
        elif stored_signature and stored_signature != signature:
            print("[Graph] Extractor/rules signature changed. Rebuilding graph from scratch.")
            self.reset_graph()
        elif not stored_signature and self._has_existing_graph_data():
            print("[Graph] Existing graph detected. Initializing incremental index.")
            self._backfill_existing_index(signature)
            self._set_metadata("extractor_signature", signature)

        articles = self._get_articles_to_process(signature)
        print(f"[Info] Articles queued for graph processing: {len(articles)}")

        if not articles:
            self._set_metadata("extractor_signature", signature)
            print("[Graph] No new or changed articles to process.")
            return

        totals = {"entities": 0, "relations": 0, "attributes": 0}
        inserted_type_counts = {}
        start_time = time.time()

        for idx, article in enumerate(articles, 1):
            counts = self._process_article(article, signature)
            totals["entities"] += counts["entities"]
            totals["relations"] += counts["relations"]
            totals["attributes"] += counts["attributes"]

            for entity_type, count in counts["new_type_counts"].items():
                inserted_type_counts[entity_type] = inserted_type_counts.get(entity_type, 0) + count

            if idx % 50 == 0:
                print(f"  [OK] Processed {idx}/{len(articles)} queued articles...")
                self.conn.commit()

        self.conn.commit()
        self._set_metadata("extractor_signature", signature)
        duration = time.time() - start_time

        print("\n" + "=" * 60)
        print("--- KNOWLEDGE GRAPH BUILD RESULT ---")
        print(f"  Articles processed: {len(articles)}")
        print(f"  Entity links:        {totals['entities']}")
        print(f"  Relations:           {totals['relations']}")
        print(f"  Attributes:          {totals['attributes']}")
        if inserted_type_counts:
            print("  New entity type distribution:")
            for entity_type, count in sorted(inserted_type_counts.items(), key=lambda item: -item[1]):
                print(f"    {entity_type}: {count}")
        print(f"  Duration:            {duration:.2f}s")
        print("=" * 60)

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    full_rebuild = "--full-rebuild" in sys.argv or "--full" in sys.argv
    builder = KnowledgeGraphBuilder()
    try:
        builder.build_graph(full_rebuild=full_rebuild)
    finally:
        builder.close()
