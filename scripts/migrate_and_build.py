#!/usr/bin/env python
"""
Apply ALTER TABLE to widen `graph_entities.type` if needed, then run
KnowledgeGraphBuilder to rebuild the knowledge graph.
"""
import sys
import traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import MYSQL_CONFIG
import pymysql

def apply_migration():
    print("[migrate] Connecting to MySQL...")
    conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COLUMN_TYPE, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'graph_entities' AND COLUMN_NAME = 'type'", (MYSQL_CONFIG.get('database'),))
        row = cursor.fetchone()
        if row:
            coltype = str(row.get('COLUMN_TYPE') or '').lower()
            print(f"[migrate] Found column type: {coltype}")
            if 'enum' in coltype:
                print("[migrate] ENUM detected — executing ALTER TABLE to widen the column...")
                cursor.execute("ALTER TABLE graph_entities MODIFY COLUMN `type` VARCHAR(50) NOT NULL")
                conn.commit()
                print("[migrate] ALTER TABLE completed.")
            else:
                print("[migrate] Column is not ENUM — no migration needed.")
        else:
            print("[migrate] Could not find graph_entities.type column metadata — skipping migration.")
    finally:
        conn.close()


def run_builder():
    print("[builder] Starting KnowledgeGraphBuilder...")
    try:
        from pipeline.knowledge_graph_builder import KnowledgeGraphBuilder
        builder = KnowledgeGraphBuilder()
        try:
            builder.build_graph()
        finally:
            builder.close()
        print("[builder] KnowledgeGraphBuilder finished.")
    except Exception:
        print("[builder] Builder failed:")
        traceback.print_exc()
        raise

if __name__ == '__main__':
    try:
        apply_migration()
        run_builder()
    except Exception as e:
        print(f"[error] {e}")
        sys.exit(2)
    print("[done] Migration + build complete.")
