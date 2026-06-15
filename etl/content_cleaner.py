from __future__ import annotations

import re
from typing import Iterable, Optional


_CREDIT_LABELS_PATTERN = (
    r"(?:nội dung|noi dung|thiết kế|thiet ke|ảnh|anh|nguồn ảnh|nguon anh|"
    r"video|đồ họa|do hoa|biên tập|bien tap|kỹ thuật|ky thuat|"
    r"tác giả|tac gia|thực hiện|thuc hien)"
)

NEWS_BRAND_TERMS = {
    "vnexpress",
    "dân trí",
    "dantri",
    "vietnamnet",
    "tuổi trẻ",
    "tuoi tre",
    "thanh niên",
    "thanh nien",
    "lao động",
    "lao dong",
    "nhân dân",
    "nhan dan",
    "vov",
    "vtv",
    "vtc",
    "reuters",
    "ap",
    "afp",
    "bbc",
    "cnn",
    "bloomberg",
    "zing",
    "znews",
}

BYLINE_PREFIX_PATTERN = re.compile(
    r"^\s*(?:"
    r"theo|nguồn|source|tác giả|tac gia|biên dịch|bien dich|dịch|dich|"
    r"tổng hợp|tong hop|thực hiện|thuc hien|"
    r"bài(?:\s+và)?\s+ảnh|bai(?:\s+va)?\s+anh|"
    r"ảnh|anh|nguồn ảnh|nguon anh|video|đồ họa|do hoa|infographic"
    r")\s*[:：\-–]?\s+",
    re.IGNORECASE,
)
CREDIT_SEGMENT_PATTERN = re.compile(
    rf"^\s*{_CREDIT_LABELS_PATTERN}\s*[:：\-–]\s*\S",
    re.IGNORECASE,
)
INLINE_CREDIT_BLOCK_PATTERN = re.compile(
    rf"(?is)\s+{_CREDIT_LABELS_PATTERN}\s*[:：\-–]\s*.*?"
    rf"(?:\|\s*{_CREDIT_LABELS_PATTERN}\s*[:：\-–]\s*.*?)+\s*$",
)
AUTHOR_LIKE_PATTERN = re.compile(
    r"^[A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ]"
    r"[\wÀ-ỹ'.-]+(?:\s+[A-ZÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬĐÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ]"
    r"[\wÀ-ỹ'.-]+){0,4}$"
)


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line or "").strip()


def _source_terms(source: Optional[str]) -> set[str]:
    terms = {term.casefold() for term in NEWS_BRAND_TERMS}
    if source:
        source_clean = _normalize_line(source).casefold()
        if source_clean:
            terms.add(source_clean)
            terms.update(part.strip() for part in re.split(r"[,/|;-]+", source_clean) if part.strip())
    return terms


def _contains_source_name(line: str, source: Optional[str]) -> bool:
    lowered = line.casefold()
    return any(term and term in lowered for term in _source_terms(source))


def _is_standalone_source(line: str, source: Optional[str]) -> bool:
    lowered = line.casefold().strip("()[]{} .:-–")
    return lowered in _source_terms(source)


def _looks_like_author_only(line: str) -> bool:
    if len(line) > 48:
        return False
    if re.search(r"[.!?;:]", line):
        return False
    words = line.split()
    if not 1 <= len(words) <= 5:
        return False
    if line.isupper() and len(words) <= 5:
        return True
    return bool(AUTHOR_LIKE_PATTERN.match(line))


def _is_credit_segment(segment: str) -> bool:
    return bool(CREDIT_SEGMENT_PATTERN.match(segment.strip()))


def _is_credit_line(line: str) -> bool:
    stripped = line.strip("()[]{} ")
    if _is_credit_segment(stripped):
        return True

    segments = [part.strip() for part in stripped.split("|") if part.strip()]
    if len(segments) < 2:
        return False

    credit_count = sum(1 for segment in segments if _is_credit_segment(segment))
    if credit_count == len(segments):
        return True

    # News credits often mix "Nội dung: A | Thiết kế: B | VCBS".
    # If most short pipe-separated segments are credits, treat the whole tail as boilerplate.
    return credit_count >= 2 and all(len(segment) <= 80 for segment in segments)


def _is_tail_boilerplate(line: str, source: Optional[str]) -> bool:
    if not line:
        return True
    if len(line) > 180:
        return False

    stripped = line.strip("()[]{} ")
    if _is_credit_line(stripped):
        return True
    if BYLINE_PREFIX_PATTERN.search(stripped):
        return True
    if _is_standalone_source(stripped, source):
        return True
    if stripped.casefold().startswith("theo ") and len(stripped) <= 140:
        return True
    if _contains_source_name(stripped, source) and re.search(r"^(?:theo|nguồn|source)\b", stripped, re.IGNORECASE):
        return True
    if re.search(r"\b(?:theo|nguồn|source)\b", stripped, re.IGNORECASE) and _contains_source_name(stripped, source):
        return True
    if _looks_like_author_only(stripped):
        return True
    return False


def _trim_tail_lines(lines: Iterable[str], source: Optional[str]) -> list[str]:
    cleaned = [_normalize_line(line) for line in lines]
    while cleaned and not cleaned[-1]:
        cleaned.pop()

    scanned = 0
    while cleaned and scanned < 12:
        tail = cleaned[-1]
        if not _is_tail_boilerplate(tail, source):
            break
        cleaned.pop()
        scanned += 1
        while cleaned and not cleaned[-1]:
            cleaned.pop()
    return cleaned


def _strip_inline_credit_tail(text: str) -> str:
    last_match = None
    for match in INLINE_CREDIT_BLOCK_PATTERN.finditer(text):
        last_match = match

    if not last_match:
        return text

    # Restrict this aggressive rule to short final credit blocks so body text
    # that happens to contain "nội dung:" earlier is not cut accidentally.
    if len(text) - last_match.start() > 1200:
        return text

    return text[: last_match.start()].rstrip()


def strip_article_boilerplate(text: str, source: Optional[str] = None) -> str:
    """Remove common source/byline/author boilerplate from the end of news text."""
    if not text:
        return ""

    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return ""
    text = _strip_inline_credit_tail(text)
    if not text:
        return ""

    paragraphs = re.split(r"\n{2,}", text)
    cleaned_paragraphs = _trim_tail_lines(paragraphs, source)
    result = "\n\n".join(cleaned_paragraphs).strip()

    # Some crawlers return every paragraph on a single line. Run a second pass
    # over single newlines, but only when paragraph trimming did not change much.
    single_lines = result.split("\n")
    trimmed_single_lines = _trim_tail_lines(single_lines, source)
    result = "\n".join(trimmed_single_lines).strip()

    return re.sub(r"\n{3,}", "\n\n", result)
