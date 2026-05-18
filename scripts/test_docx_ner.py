import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from etl.ner_extractor import NERExtractor

DOCX_PATH = Path(__file__).resolve().parents[1] / 'uploads' / 'Ban_Tin_Tong_Hop_Da_Chieu.docx'

def extract_text_from_docx(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    text_parts = []
    with zipfile.ZipFile(path, 'r') as z:
        if 'word/document.xml' not in z.namelist():
            return ''
        xml_bytes = z.read('word/document.xml')
        root = ET.fromstring(xml_bytes)
        # Word XML uses namespace; find all paragraph texts
        namespaces = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        for para in root.findall('.//w:p', namespaces):
            texts = [t.text for t in para.findall('.//w:t', namespaces) if t.text]
            if texts:
                text_parts.append(''.join(texts))
    return '\n'.join(text_parts)


def main():
    print('Reading:', DOCX_PATH)
    text = extract_text_from_docx(DOCX_PATH)
    if not text:
        print('No text extracted or file missing.')
        return
    print('--- Document text (first 800 chars) ---')
    print(text[:800])
    print('\n--- Running NER ---')
    ner = NERExtractor()
    entities = ner.extract_entities(text)
    for k, v in entities.items():
        if v:
            print(f"{k}: {v}")
    print('\n--- Analysis (search anchors, requires_clarification) ---')
    analysis = ner.analyze_query(text)
    print('anchor_terms:', analysis.get('anchor_terms'))
    print('requires_clarification:', analysis.get('requires_clarification'))

if __name__ == '__main__':
    main()
