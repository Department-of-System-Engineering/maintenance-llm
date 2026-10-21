# test_text_to_sql.py  (a projekt gyökerébe:  ~/llm-project/test_text_to_sql.py)
"""
A teljes Text-to-SQL lánc izolált tesztje.

Futtatás a projekt gyökeréből:
    python test_text_to_sql.py

Vagy modulként:
    python -m test_text_to_sql

Mit csinál:
    1. Kiírja az élő sémát (amit az LLM látni fog)
    2. Néhány példakérdésen végigfuttatja a teljes láncot
    3. Minden kérdésnél megmutatja: a GENERÁLT SQL-t, a sorok számát, és a végső választ

A return_debug=True miatt látod a generált SQL-t is — eleinte ez a legfontosabb,
mert így ellenőrizheted, hogy az LLM helyes oszlopneveket használ-e.
"""

from services.text_to_sql_service import text_to_sql_service


# Ide írj a saját tábládhoz illő kérdéseket! Ezek csak kiindulási példák.
TEST_QUESTIONS = [
    "Letiltott az eszterg alacsony a főorsó kenés nyomás hibával.-	Mitől alakulhat ki az alacsony nyomás a főorsó kenésnél?"
    # "Hány karbantartás történt 2025-ben?",   # <- igazítsd a valódi oszlopokhoz
]


def _print_schema():
    print("=" * 70)
    print("ÉLŐ SÉMA (amit az LLM lát):")
    print("=" * 70)
    try:
        print(text_to_sql_service.get_schema())
    except Exception as e:
        print(f"!! Nem sikerült a sémát lekérdezni: {e}")
        raise
    print()


def _ask(question: str):
    print("-" * 70)
    print(f"KÉRDÉS: {question}")
    print("-" * 70)

    result = text_to_sql_service.ask(question, return_debug=True)

    print(f"GENERÁLT SQL:\n  {result.get('sql')}\n")
    if "row_count" in result:
        print(f"SOROK SZÁMA: {result['row_count']}")
    if result.get("error"):
        print(f"HIBA: {result['error']}")
    print(f"\nVÁLASZ:\n  {result['answer']}\n")


if __name__ == "__main__":
    _print_schema()
    for q in TEST_QUESTIONS:
        _ask(q)