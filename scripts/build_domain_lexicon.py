#!/usr/bin/env python3
"""
Script: build_domain_lexicon.py
- Extracts frequent unigrams/bigrams/trigrams per category from data/news_full.json
- Normalizes and filters candidate phrases
- Merges top candidates into data/ner_lexicons_news_domain.json under TOPIC

Usage:
    python scripts/build_domain_lexicon.py

"""
from pathlib import Path
import json
import re
from collections import Counter, defaultdict

from etl.ner_extractor import _normalize_for_match, NERExtractor

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / 'data' / 'news_full.json'
LEXICON_FILE = ROOT / 'data' / 'ner_lexicons_news_domain.json'
BACKUP_FILE = ROOT / 'data' / 'ner_lexicons_news_domain.json.bak'

# Config
TOP_K_PER_CATEGORY = 80
MIN_TOKEN_LEN = 3
MAX_NGRAM = 3


def load_articles(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    text = path.read_text(encoding='utf-8')
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # try newline-delimited JSON
        payload = [json.loads(line) for line in text.splitlines() if line.strip()]
    return payload


def normalize_text(s: str) -> str:
    s = s or ''
    s = s.lower()
    # remove URLs and non word characters (retain Vietnamese chars)
    s = re.sub(r'https?://\S+', ' ', s)
    s = re.sub(r"[^\w\sáàảãạâấầẩẫậắằẳẵặéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộớờởỡợúùủũụưứừửữựýỳỷỹỵđ-]", ' ', s, flags=re.UNICODE)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def tokens_from_text(s: str):
    s = normalize_text(s)
    return s.split()


def extract_ngrams(tokens, n):
    return [' '.join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]


def build_candidates(articles):
    ner = NERExtractor()
    stopwords = set(ner.QUERY_STOPWORDS)
    categories = defaultdict(Counter)

    for art in articles:
        cat = art.get('category') or 'unknown'
        title = art.get('title') or ''
        summary = art.get('summary') or ''
        content = art.get('content') or ''
        text = ' '.join([title, summary, content])
        tokens = tokens_from_text(text)
        # filter tokens
        tokens = [t for t in tokens if len(t) >= MIN_TOKEN_LEN and not t.isdigit() and t not in stopwords]
        for n in range(1, MAX_NGRAM+1):
            for ng in extract_ngrams(tokens, n):
                # skip ngrams that contain mostly stopwords or too short
                ng_norm = _normalize_for_match(ng)
                if len(ng_norm) < 4:
                    continue
                categories[cat][ng_norm] += 1
    return categories


def merge_into_lexicon(lexicon_path: Path, candidates: dict):
    if not lexicon_path.exists():
        base = {}
    else:
        base = json.loads(lexicon_path.read_text(encoding='utf-8'))

    existing_topics = set(_normalize_for_match(t) for t in base.get('TOPIC', []))

    additions = set()
    # Flatten top candidates across important categories
    for cat, counter in candidates.items():
        for phrase, cnt in counter.most_common(TOP_K_PER_CATEGORY):
            if phrase in existing_topics:
                continue
            # heuristics: include phrases with at least one non-generic token
            if any(len(tok) >= MIN_TOKEN_LEN for tok in phrase.split()):
                additions.add(phrase)

    if additions:
        merged = list(existing_topics.union(additions))
        base['TOPIC'] = sorted(merged)
        # backup
        lexicon_path.with_suffix('.bak.json').write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding='utf-8')
        lexicon_path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding='utf-8')
    return additions


def main():
    print('Loading articles...')
    articles = load_articles(DATA_FILE)
    print(f'Loaded {len(articles)} articles')
    print('Building candidates per category...')
    candidates = build_candidates(articles)
    print(f'Found {len(candidates)} categories with content.')
    print('Merging into lexicon...')
    additions = merge_into_lexicon(LEXICON_FILE, candidates)
    print(f'Added {len(additions)} new topical phrases to {LEXICON_FILE.name}')


if __name__ == '__main__':
    main()
