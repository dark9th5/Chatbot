# DoAn_CT060122

Project chatbot tin tuc tieng Viet theo mo hinh RAG (ETL + Vector Search + LLM + Android client).

## Cau truc thu muc

- `apps/android/`: ung dung Android (Kotlin/Compose)
- `chatbot_api/`: API chatbot (FastAPI)
- `web_admin/`: web admin + upload tai lieu
- `etl/`: thu thap va xu ly du lieu RSS
- `pipeline/`: NLP/chunking/vectorization modules
- `scripts/`: cac entrypoint script
- `data/`: du lieu runtime (JSON, Qdrant local)
- `docs/`: tai lieu huong dan

## Chay nhanh

1. Cai dependencies Python

```bash
pip install -r requirements.txt
```

2. Chay backend (web admin + API)

```bash
uvicorn web_admin.main:app --host 0.0.0.0 --port 8000 --reload
```

3. Chay ETL de nap du lieu

```bash
python scripts/main_etl.py
```

4. Build Android app

```bash
cd apps/android
./gradlew assembleDebug
```

- Cac file compatibility shim (nhu `main_etl.py`, `nlp_processor.py`...) da duoc di chuyen vao thu muc `legacy/` de lam gon thu muc goc.
- Tai lieu tong quan: [docs/HUONG_DAN_HIEU_PROJECT_DOAN_CT060122.md](file:///d:/App%20Android/DoAn_CT060122/docs/HUONG_DAN_HIEU_PROJECT_DOAN_CT060122.md).
