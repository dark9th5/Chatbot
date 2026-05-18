from etl.ner_extractor import NERExtractor
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'uploads' / 'sample_cv.txt'
text = p.read_text(encoding='utf-8')
print('=== CV TEXT ===')
print(text)
print('\n=== NER.extract_entities ===')
ner = NERExtractor()
entities = ner.extract_entities(text)
for k, v in entities.items():
    if v:
        print(f"{k}: {v}")

print('\n=== NER.analyze_query (as if user asked about the CV owner) ===')
analysis = ner.analyze_query(text)
for k in ('anchor_terms','search_terms','question_intents','requires_clarification'):
    print(f"{k}: {analysis.get(k)}")
