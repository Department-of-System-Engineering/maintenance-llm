# maintenance-llm

Karbantartási asszisztens LLM-mel: a karbantartó kérdéseire a gépkönyvek / munkautasítások (RAG)
és a CMMS munkalap-adatbázis (Text-to-SQL) alapján válaszol, magyarul.

> **Demóadatok:** a repóban lévő dokumentumok (`pdfs/`) és a munkalap-adatbázis tartalma
> **szintetikus**, a `scripts/generate_synthetic_data.py` állítja elő. Nem valós üzemi adatok.

## Felépítés

| Rész | Hol |
|---|---|
| Chat felület (Chainlit) | `app.py` |
| REST API (FastAPI) | `main.py`, `api/` |
| Orchestrator (RAG + Text-to-SQL összefésülése) | `services/orchestrator_service.py` |
| Dokumentumkeresés (Chroma + BM25 hibrid) | `services/rag_service.py`, `data/raw/vector_store.py` |
| Text-to-SQL (élő sémával, csak SELECT) | `services/text_to_sql_service.py`, `services/schema_inspector.py` |
| Dokumentum-betöltés, darabolás, vektorizálás | `src/utils/`, `src/db/` |
| Demóadat-generálás, modell-összehasonlítás | `scripts/` |

Az adatfolyam: dokumentumok (`pdfs/`) → darabolás + embedding → SQL Server (`LLM_DEV.LlmKnowledgeBase`)
→ szinkron a helyi ChromaDB-be → keresés a kérdéskor.

## Előfeltételek

- Python 3.12
- [Ollama](https://ollama.com), letöltött modellekkel:
  ```
  ollama pull llama3.1:8b
  ollama pull snowflake-arctic-embed2
  ```
- Microsoft SQL Server (pl. 2022 Developer) és ODBC Driver 18 for SQL Server

## Telepítés

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # majd töltsd ki az MSSQL_URI_* sorokat
```

> Windowson a `uvloop` nem telepíthető; ha a `pip install` emiatt elakad, töröld a sort a `requirements.txt`-ből.

## Demóadatok előállítása

```powershell
python -m scripts.generate_synthetic_data
python -c "from src.utils.document_processor import ingest_all_documents; ingest_all_documents('pdfs')"
```

Az első létrehozza az `ICMMS_INT_DEV` (800 munkalap) és `LLM_DEV` adatbázist, valamint a `pdfs/`
dokumentumait; a második vektorizálja a dokumentumokat az `LLM_DEV`-be.

## Futtatás

```powershell
.venv\Scripts\Activate.ps1
chainlit run app.py                         # chat: http://localhost:8000
uvicorn main:app --reload --port 8001       # API:  http://localhost:8001/docs
```

API végpontok:
- `POST /api/ask` — `{"query": "...", "debug": true}` — dokumentum + adatbázis együtt
- `POST /api/chat/ask` — `{"query": "..."}` — csak dokumentum (RAG)

## Modell-összehasonlítás

```powershell
python -m scripts.evaluate_models llm --models llama3.1:8b
python -m scripts.evaluate_models embed --models snowflake-arctic-embed2
```

Eredmények: `outputs/reports/`. Embedding modell cseréje után a `data/chroma_db` mappát törölni
és a dokumentumokat újra betölteni kell (más a vektorok mérete).
