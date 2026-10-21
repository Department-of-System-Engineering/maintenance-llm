# scripts/evaluate_models.py
"""
Modell-összehasonlítás a szintetikus demóadatokon.

Két mérés:
    embed  — embedding modellek: a kérdéshez a helyes dokumentumot találja-e meg
             (csak memóriában fut, az SQL- és a Chroma-adatbázist NEM módosítja).
    llm    — chat modellek: Text-to-SQL helyesség (előre kiszámolt helyes válaszhoz mérve)
             és RAG-válasz (kötelező tények szerepelnek-e), futásidővel együtt.
             A projekt saját szolgáltatásain keresztül fut; a modellt az OLLAMA_MODEL
             környezeti változó választja ki (felülírja a .env-et).

Futtatás a projekt gyökeréből:
    python -m scripts.evaluate_models embed --models nomic-embed-text embeddinggemma
    python -m scripts.evaluate_models llm --models llama3.1:8b gemma3:12b

Az eredmények az outputs/reports/ mappába kerülnek (JSON), az összesítés a konzolra.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = PROJECT_ROOT / "outputs" / "reports"

# ==========================================================================
# Embedding kérdések: (kérdés, a helyes forrásfájl nevének eleje)
# Szándékosan átfogalmazva, hogy ne a dokumentumcím szavaira lehessen rákeresni.
# ==========================================================================
EMBED_QUESTIONS = [
    ("Miért nincs elég olajnyomás az eszterga orsójának kenésénél?", "MWI-90101"),
    ("Riaszt a gép, hogy kevés a kenőolaj nyomása, mit nézzek meg először?", "MWI-90101"),
    ("Hogyan kell kicserélni a sorjázó gép szűrő-szabályzó-olajozó egységét?", "MWI-90102"),
    ("Víz jön a pneumatikus hengereknél a sorjázón, mi a teendő?", "MWI-90102"),
    ("Hány liter olaj megy a 160 tonnás présbe, és milyen típusú?", "MWI-90103"),
    ("Túlmelegszik a prés hidraulikaolaja, mi lehet az oka?", "MWI-90103"),
    ("Leállt a légsűrítő magas hőmérséklet miatt, mit csináljak?", "MWI-90104"),
    ("Milyen gyakran kell olajleválasztó betétet cserélni a kompresszorban?", "MWI-90104"),
    ("Habzik és rossz szagú az emulzió a forgácsoló gépen.", "MWI-90105"),
    ("Hogyan mérjem a hűtőfolyadék töménységét refraktométerrel?", "MWI-90105"),
    ("Hogyan kell lakatolni a gépet karbantartás előtt?", "BIZ-001"),
    ("Többen dolgozunk egy gépen, hogyan biztosítjuk, hogy senki ne kapcsolja vissza?", "BIZ-001"),
    ("A megmunkáló központ nem engedi el a szerszámot az orsóból.", "MWI-90106"),
    ("Elakadt a szerszámtár, hogyan veszem fel újra a referenciát?", "MWI-90106"),
    ("Nekiment a robot a készüléknek, hogyan indítsam újra?", "MWI-90107"),
    ("Ki felel a kompresszorolaj szintjének napi ellenőrzéséért és milyen olaj kell bele?", "KP-2026"),
]

# ==========================================================================
# Text-to-SQL kérdések: (kérdés, helyes SQL, numerikus tűrés vagy None)
# Helyes, ha a helyes válasz értéke megjelenik a modell lekérdezésének eredményében.
# ==========================================================================
SQL_QUESTIONS = [
    ("Melyik gépen volt a legtöbb hibaelhárítás 2026-ban?",
     "SELECT TOP 1 eq_short_code FROM dbo.t_cmms_wo WHERE is_bd = 1 AND YEAR(rec_date) = 2026 "
     "GROUP BY eq_short_code ORDER BY COUNT(*) DESC", None),
    ("Hány hibaelhárítási munkalap volt 2025-ben összesen?",
     "SELECT COUNT(*) FROM dbo.t_cmms_wo WHERE is_bd = 1 AND YEAR(rec_date) = 2025", 0),
    ("Melyik karbantartó zárta le a legtöbb munkalapot?",
     "SELECT TOP 1 resp_name FROM dbo.t_cmms_wo WHERE wo_is_done = 1 GROUP BY resp_name ORDER BY COUNT(*) DESC", None),
    ("Hány percig tartott átlagosan egy javítás a #400-as gépen?",
     "SELECT AVG(CAST(wo_duration_minutes AS FLOAT)) FROM dbo.t_cmms_wo WHERE eq_short_code = N'#400'", 1.0),
    ("Hány munkalap van még nyitott állapotban?",
     "SELECT COUNT(*) FROM dbo.t_cmms_wo WHERE wo_is_done = 0", 0),
]

# ==========================================================================
# RAG kérdések: (kérdés, kötelező tények — mindnek szerepelnie kell a válaszban)
# ==========================================================================
RAG_QUESTIONS = [
    ("Mekkora a JR20/20 eszterga főorsó kenési üzemi nyomása, és milyen nyomás alatt riaszt?",
     ["2,5", "3,5", "1,8"]),
    ("Milyen cikkszámú levegőelőkészítő egység kell az SG-40 sorjázóhoz, és milyen nyomásra kell beállítani?",
     ["FRL-12-5-SG", "6"]),
    ("Mit kell tenni, ha a KS-55 kompresszor E04 hibával leáll?",
     ["tartalék", "15 perc", "hűtő"]),
    ("Milyen koncentrációjú legyen a hűtő-kenő emulzió, és milyen gyakran kell mérni?",
     ["6", "8", "műszak"]),
]


# ==========================================================================
# Embedding mérés
# ==========================================================================
def _load_chunks():
    """Ugyanaz a betöltés és darabolás, mint az ingest_all_documents-ben (DB nélkül)."""
    from src.utils.document_loaders import (
        load_excel_tables, load_pdfs, load_powerpoints, load_rtf_files, load_word_files,
    )
    from src.utils.document_processor import split_and_enrich_documents

    docs_dir = str(PROJECT_ROOT / "pdfs")
    documents = []
    for loader in (load_pdfs, load_word_files, load_excel_tables, load_powerpoints, load_rtf_files):
        documents.extend(loader(docs_dir))
    return split_and_enrich_documents(documents)


def _cosine_rank(query_vec, doc_vecs):
    import numpy as np

    q = np.asarray(query_vec, dtype=np.float32)
    d = np.asarray(doc_vecs, dtype=np.float32)
    sims = d @ q / (np.linalg.norm(d, axis=1) * np.linalg.norm(q) + 1e-9)
    return list(np.argsort(-sims))


def run_embed(models: list[str]) -> dict:
    from ollama import Client
    from config.settings import settings

    client = Client(host=settings.ollama_host)
    chunks = _load_chunks()
    sources = [Path(c.metadata["source"]).name for c in chunks]
    texts = [c.page_content for c in chunks]
    print(f"{len(chunks)} chunk, {len(EMBED_QUESTIONS)} kérdés\n")

    results = {}
    for model in models:
        t0 = time.time()
        doc_vecs = client.embed(model=model, input=texts, truncate=True)["embeddings"]
        hits1 = hits3 = 0
        rr_sum = 0.0
        details = []
        for question, expected in EMBED_QUESTIONS:
            q_vec = client.embed(model=model, input=question)["embeddings"][0]
            ranked = [sources[i] for i in _cosine_rank(q_vec, doc_vecs)]
            # Egy fájlnak több chunkja is lehet (Excel) -> fájlszintű rangsor
            ranked_files = list(dict.fromkeys(ranked))
            rank = next((i + 1 for i, f in enumerate(ranked_files) if f.startswith(expected)), None)
            hits1 += rank == 1
            hits3 += rank is not None and rank <= 3
            rr_sum += 1 / rank if rank else 0
            details.append({"question": question, "expected": expected, "rank": rank, "top1": ranked_files[0]})
        n = len(EMBED_QUESTIONS)
        results[model] = {
            "hit@1": hits1 / n, "hit@3": hits3 / n, "MRR": rr_sum / n,
            "seconds": round(time.time() - t0, 1), "dim": len(doc_vecs[0]), "details": details,
        }
        print(f"{model:<28} hit@1={hits1}/{n}  hit@3={hits3}/{n}  MRR={rr_sum / n:.2f}  "
              f"dim={len(doc_vecs[0])}  {results[model]['seconds']}s")
    return results


# ==========================================================================
# LLM mérés (egy modell, külön folyamatban — a settings importkor olvassa a modellnevet)
# ==========================================================================
def _value_in_rows(expected, rows: list[dict], tolerance) -> bool:
    for row in rows:
        for value in row.values():
            if value is None:
                continue
            if tolerance is not None:
                try:
                    if abs(float(value) - float(expected)) <= tolerance:
                        return True
                except (TypeError, ValueError):
                    continue
            elif str(value).strip().lower() == str(expected).strip().lower():
                return True
    return False


def run_llm_single() -> dict:
    """Az aktuális OLLAMA_MODEL-lel méri a Text-to-SQL-t és a RAG-ot."""
    from sqlalchemy import text

    from services.rag_service import rag_service
    from services.text_to_sql_service import text_to_sql_service as t2s

    model = os.environ["OLLAMA_MODEL"]
    out = {"model": model, "sql": [], "rag": []}

    for question, truth_sql, tolerance in SQL_QUESTIONS:
        with t2s.engine.connect() as conn:
            expected = conn.execute(text(truth_sql)).scalar()
        t0 = time.time()
        entry = {"question": question, "expected": expected}
        try:
            sql = t2s.generate_sql(question)
            entry["sql"] = sql
            df = t2s.execute_sql(sql)
            rows = df.astype(object).where(df.notna(), None).to_dict(orient="records")
            entry["valid"] = True
            entry["correct"] = _value_in_rows(expected, rows, tolerance)
            entry["rows_preview"] = [{k: str(v) for k, v in r.items()} for r in rows[:3]]
        except Exception as e:
            entry.update(valid=False, correct=False, error=str(e)[:300])
        entry["seconds"] = round(time.time() - t0, 1)
        out["sql"].append(entry)
        print(f"[SQL] {'OK ' if entry['correct'] else 'ROSSZ'} {entry['seconds']:>6}s  {question}", flush=True)

    for question, facts in RAG_QUESTIONS:
        rag_service.chat_history = []  # minden kérdés tiszta lappal
        t0 = time.time()
        try:
            answer = rag_service.search_and_chat(question)
        except Exception as e:
            answer = f"HIBA: {e}"
        found = [f for f in facts if f.lower() in answer.lower()]
        entry = {
            "question": question, "facts": facts, "found": found,
            "score": len(found) / len(facts), "seconds": round(time.time() - t0, 1), "answer": answer,
        }
        out["rag"].append(entry)
        print(f"[RAG] {len(found)}/{len(facts)} tény {entry['seconds']:>6}s  {question}", flush=True)

    return out


def run_llm(models: list[str]) -> dict:
    results = {}
    for model in models:
        print(f"\n===== {model} =====", flush=True)
        tmp = REPORT_DIR / f"_llm_{model.replace(':', '_').replace('/', '_')}.json"
        env = {**os.environ, "OLLAMA_MODEL": model, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.evaluate_models", "_llm_single", "--out", str(tmp)],
            cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
        )
        for line in proc.stdout.splitlines():
            if line.startswith(("[SQL]", "[RAG]")):
                print(line, flush=True)
        if proc.returncode != 0 or not tmp.exists():
            print(f"HIBA a(z) {model} futásában:\n{proc.stderr[-1500:]}")
            results[model] = {"error": proc.stderr[-1500:]}
            continue
        results[model] = json.loads(tmp.read_text(encoding="utf-8"))
        tmp.unlink()
        # Modell kiürítése a memóriából, hogy a következő elférjen
        subprocess.run(["ollama", "stop", model], capture_output=True)

    print("\n===== ÖSSZESÍTÉS =====")
    print(f"{'modell':<16} {'SQL érvényes':>12} {'SQL helyes':>10} {'RAG tények':>10} {'átl. idő/kérdés':>16}")
    for model, r in results.items():
        if "error" in r:
            print(f"{model:<16} HIBA")
            continue
        n_sql, n_rag = len(r["sql"]), len(r["rag"])
        valid = sum(e["valid"] for e in r["sql"])
        correct = sum(e["correct"] for e in r["sql"])
        rag_score = sum(e["score"] for e in r["rag"]) / n_rag
        avg_t = sum(e["seconds"] for e in r["sql"] + r["rag"]) / (n_sql + n_rag)
        print(f"{model:<16} {valid:>9}/{n_sql} {correct:>7}/{n_sql} {rag_score:>9.0%} {avg_t:>14.1f}s")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Modell-összehasonlítás")
    parser.add_argument("mode", choices=["embed", "llm", "_llm_single"])
    parser.add_argument("--models", nargs="+")
    parser.add_argument("--out", help="(belső) kimeneti fájl a _llm_single módhoz")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if args.mode == "_llm_single":
        Path(args.out).write_text(json.dumps(run_llm_single(), ensure_ascii=False, indent=2, default=str),
                                  encoding="utf-8")
        return

    results = run_embed(args.models) if args.mode == "embed" else run_llm(args.models)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"model_eval_{args.mode}_{stamp}.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nRészletes eredmények: {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
