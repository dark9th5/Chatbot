from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional


BASE_URL = "http://127.0.0.1:8000"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass
class Case:
    name: str
    payload: dict
    expect_status: int
    check: Optional[Callable[[dict], tuple[bool, str]]] = None


@dataclass
class GetCase:
    name: str
    path: str
    expect_status: int
    check: Optional[Callable[[dict | str], tuple[bool, str]]] = None


def _post_json(path: str, payload: dict) -> tuple[int, dict, float]:
    started = time.time()
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body, time.time() - started
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        return exc.code, body, time.time() - started


def _get(path: str) -> tuple[int, dict | str, float]:
    started = time.time()
    request = urllib.request.Request(f"{BASE_URL}{path}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
            body: dict | str = json.loads(raw) if "application/json" in content_type else raw
            return response.status, body, time.time() - started
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
        return exc.code, body, time.time() - started


def _all_news_sources(body: dict) -> tuple[bool, str]:
    sources = body.get("sources", [])
    ok = bool(sources) and all(
        source.get("article_source") != "Upload"
        and not str(source.get("article_link", "")).startswith("upload://")
        for source in sources
    )
    return ok, f"sources={[(s.get('article_title'), s.get('article_source')) for s in sources]}"


def _all_document_sources(body: dict) -> tuple[bool, str]:
    sources = body.get("sources", [])
    ok = bool(sources) and all(
        source.get("article_source") == "Upload"
        and str(source.get("article_link", "")).startswith("upload://")
        for source in sources
    )
    return ok, f"sources={[(s.get('article_title'), s.get('article_source')) for s in sources]}"


def _clarifies(body: dict) -> tuple[bool, str]:
    return bool(body.get("needs_clarification")), body.get("answer", "")


def _does_not_say_today(body: dict) -> tuple[bool, str]:
    answer = body.get("answer", "")
    return "hôm nay" not in answer.casefold(), answer


def _news_cross_source_is_clean(body: dict) -> tuple[bool, str]:
    sources = body.get("sources", [])
    sources_ok = all(
        source.get("article_source") != "Upload"
        and not str(source.get("article_link", "")).startswith("upload://")
        for source in sources
    )
    details = f"sources={[(s.get('article_title'), s.get('article_source')) for s in sources]}"
    no_upload_title = all(
        "Nguyễn Chí Lực" not in source.get("article_title", "")
        for source in sources
    )
    return sources_ok and no_upload_title, details


def _documents_do_not_answer_news(body: dict) -> tuple[bool, str]:
    sources = body.get("sources", [])
    no_news_source = all(source.get("article_source") == "Upload" for source in sources)
    answer = body.get("answer", "")
    no_news_claim = "18 km đường trên cao" not in answer
    return no_news_source and no_news_claim, f"answer={answer}; sources={sources}"


def _doc_answer_mentions_android_stack(body: dict) -> tuple[bool, str]:
    answer = body.get("answer", "")
    answer_ok = any(term in answer for term in ("Jetpack Compose", "Kotlin", "MVVM", "Dagger Hilt"))
    sources_ok, source_details = _all_document_sources(body)
    return answer_ok and sources_ok, f"answer={answer}; {source_details}"


def _doc_summary_mentions_candidate(body: dict) -> tuple[bool, str]:
    answer = body.get("answer", "")
    sources_ok, source_details = _all_document_sources(body)
    return "Nguyễn Chí Lực" in answer and sources_ok, f"answer={answer}; {source_details}"


def _doc_school_answer(body: dict) -> tuple[bool, str]:
    answer = body.get("answer", "")
    sources_ok, source_details = _all_document_sources(body)
    answer_ok = any(
        term in answer
        for term in ("Academy of Cryptography Techniques", "Học viện Kỹ thuật Mật mã")
    )
    return answer_ok and sources_ok, f"answer={answer}; {source_details}"


def _unknown_document_answer(body: dict) -> tuple[bool, str]:
    sources_ok, source_details = _all_document_sources(body)
    answer = body.get("answer", "")
    answer_ok = "không tìm thấy" in answer.casefold()
    return sources_ok and answer_ok, f"answer={answer}; {source_details}"


def _followup_no_more_location_prompt(body: dict) -> tuple[bool, str]:
    answer = body.get("answer", "")
    ok = not body.get("needs_clarification") and "khu vực nào" not in answer.casefold()
    return ok, answer


def _healthy_json(body: dict | str) -> tuple[bool, str]:
    if not isinstance(body, dict):
        return False, str(body)[:120]
    return body.get("status") == "healthy", json.dumps(body, ensure_ascii=False)


def _categories_exclude_documents(body: dict | str) -> tuple[bool, str]:
    if not isinstance(body, dict):
        return False, str(body)[:120]
    categories = body.get("categories", [])
    return "Tài liệu" not in categories, f"categories={categories}"


def _html_contains(marker: str) -> Callable[[dict | str], tuple[bool, str]]:
    def _check(body: dict | str) -> tuple[bool, str]:
        text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
        return marker in text, f"contains={marker!r}"

    return _check


CASES = [
    Case(
        name="news_known_article",
        payload={
            "question": "TP HCM đang nghiên cứu xây gì dọc đại lộ Nguyễn Văn Linh?",
            "data_source": "news",
            "top_k": 3,
        },
        expect_status=200,
        check=_all_news_sources,
    ),
    Case(
        name="news_explicit_date_no_today",
        payload={
            "question": "Nhiệt độ tại Hà Nội ngày 16/5 là bao nhiêu?",
            "data_source": "news",
            "top_k": 3,
        },
        expect_status=200,
        check=_does_not_say_today,
    ),
    Case(
        name="news_today_tp_hcm",
        payload={
            "question": "Tin mới ở TP HCM hôm nay?",
            "data_source": "news",
            "top_k": 3,
        },
        expect_status=200,
        check=_all_news_sources,
    ),
    Case(
        name="news_underspecified",
        payload={
            "question": "Đang tăng mạnh không?",
            "data_source": "news",
            "top_k": 3,
        },
        expect_status=200,
        check=_clarifies,
    ),
    Case(
        name="news_weather_missing_location",
        payload={
            "question": "Ngày mai có nóng không?",
            "data_source": "news",
            "top_k": 3,
        },
        expect_status=200,
        check=_clarifies,
    ),
    Case(
        name="news_cross_source",
        payload={
            "question": "Nguyễn Chí Lực có dùng Jetpack Compose không?",
            "data_source": "news",
            "top_k": 3,
        },
        expect_status=200,
        check=_news_cross_source_is_clean,
    ),
    Case(
        name="documents_android_skills",
        payload={
            "question": "Nguyễn Chí Lực có những kỹ năng Android nào?",
            "data_source": "documents",
            "top_k": 3,
        },
        expect_status=200,
        check=_doc_answer_mentions_android_stack,
    ),
    Case(
        name="documents_summary",
        payload={
            "question": "Tóm tắt tài liệu này",
            "data_source": "documents",
            "top_k": 3,
        },
        expect_status=200,
        check=_doc_summary_mentions_candidate,
    ),
    Case(
        name="documents_date_phrase_does_not_filter_upload_day",
        payload={
            "question": "Trong tài liệu ngày 16/5, Nguyễn Chí Lực học trường nào?",
            "data_source": "documents",
            "top_k": 3,
        },
        expect_status=200,
        check=_doc_school_answer,
    ),
    Case(
        name="documents_unknown_fact",
        payload={
            "question": "Tài liệu nói gì về bằng lái xe?",
            "data_source": "documents",
            "top_k": 3,
        },
        expect_status=200,
        check=_unknown_document_answer,
    ),
    Case(
        name="documents_cross_source",
        payload={
            "question": "TP HCM đang nghiên cứu xây gì dọc đại lộ Nguyễn Văn Linh?",
            "data_source": "documents",
            "top_k": 3,
        },
        expect_status=200,
        check=_documents_do_not_answer_news,
    ),
    Case(
        name="news_followup_with_context",
        payload={
            "question": "ở Hà Nội",
            "data_source": "news",
            "conversation_context": "Ngày mai có nóng không?",
            "top_k": 3,
        },
        expect_status=200,
        check=_followup_no_more_location_prompt,
    ),
    Case(
        name="invalid_source_schema",
        payload={
            "question": "Xin chào",
            "data_source": "all",
            "top_k": 3,
        },
        expect_status=422,
    ),
    Case(
        name="too_short_question_schema",
        payload={
            "question": "?",
            "data_source": "news",
            "top_k": 3,
        },
        expect_status=422,
    ),
]


GET_CASES = [
    GetCase("root_health", "/health", 200, _healthy_json),
    GetCase("chatbot_health", "/api/health", 200, _healthy_json),
    GetCase("public_config", "/api/public-config", 200),
    GetCase("categories_no_documents", "/api/categories", 200, _categories_exclude_documents),
    GetCase("dashboard_page", "/", 200, _html_contains("Dashboard")),
    GetCase("news_page", "/news", 200, _html_contains("Danh sách tin tức")),
    GetCase("upload_page", "/upload", 200, _html_contains("Upload")),
    GetCase("documents_page", "/documents", 200, _html_contains("Documents")),
]


def main() -> int:
    failures = 0
    for case in GET_CASES:
        status, body, elapsed = _get(case.path)
        ok = status == case.expect_status
        detail = ""

        if ok and case.check is not None:
            ok, detail = case.check(body)
        elif status != case.expect_status:
            detail = json.dumps(body, ensure_ascii=False) if isinstance(body, dict) else body[:200]

        print(f"[{'PASS' if ok else 'FAIL'}] {case.name} ({elapsed:.2f}s, HTTP {status})")
        if detail:
            print(f"  {detail}")

        if not ok:
            failures += 1

    for case in CASES:
        status, body, elapsed = _post_json("/api/chat", case.payload)
        ok = status == case.expect_status
        detail = ""

        if ok and case.check is not None:
            ok, detail = case.check(body)
        elif status != case.expect_status:
            detail = json.dumps(body, ensure_ascii=False)

        print(f"[{'PASS' if ok else 'FAIL'}] {case.name} ({elapsed:.2f}s, HTTP {status})")
        if detail:
            print(f"  {detail}")
        elif body.get("answer"):
            print(f"  {body['answer']}")

        if not ok:
            failures += 1

    total = len(GET_CASES) + len(CASES)
    print(f"\nSummary: {total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
