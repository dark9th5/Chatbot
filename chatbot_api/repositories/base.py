"""
Base Repository — Abstract Data Access Layer
Design Pattern: Repository Pattern + Template Method
"""

import pymysql
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from pipeline.config import MYSQL_CONFIG


class BaseRepository:
    """
    Abstract base repository:
    - Quản lý kết nối MySQL (context manager)
    - Interface chuẩn cho sub-repositories
    """

    def __init__(self):
        """Khởi tạo đối tượng và chuẩn bị các phụ thuộc cần dùng."""
        self._config = MYSQL_CONFIG

    @contextmanager
    def _get_connection(self):
        """Context manager cho MySQL connection."""
        conn = pymysql.connect(
            **self._config,
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            yield conn
        finally:
            conn.close()

    def _fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Xử lý một phần nghiệp vụ của module theo tham số đầu vào."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()

    def _fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """Xử lý một phần nghiệp vụ của module theo tham số đầu vào."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def _execute(self, query: str, params: tuple = ()) -> int:
        """Xử lý một phần nghiệp vụ của module theo tham số đầu vào."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
