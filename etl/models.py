from datetime import datetime
from dataclasses import dataclass
from typing import Optional

@dataclass
class Article:
    """Class đại diện cho một bài báo (Standardized Data Model)"""
    title: str
    link: str
    summary: str
    content: str
    published_date: Optional[str]  # Format: YYYY-MM-DD HH:MM:SS
    source: str
    category: str

    def to_dict(self):
        return {
            "title": self.title,
            "link": self.link,
            "summary": self.summary,
            "content": self.content,
            "published_date": self.published_date,
            "source": self.source,
            "category": self.category
        }
