# tests/test_orchestrator.py
"""
Az orchestrator rétegenkénti tesztje.

Futtatás a projekt gyökeréből:
    python test_orchestrator.py

Három szint, alulról fölfelé:
    1. SZINT — csak a router dönt (nem futtat semmit). Ez a legfontosabb: jól sorol-e?
    2. SZINT — a teljes ask() minden ágon, a route mezővel együtt.
    3. SZINT — kifejezetten a MINDKETTO ág (a drága, összefésülős út).

A debug=True miatt látod a 'route' mezőt — eleinte EZ a legfontosabb.
Ha a router rosszul sorol, a ROUTER_SYSTEM_PROMPT-ot kell hangolni, nem a kódot.
"""

from services.orchestrator_service import orchestrator_service


# ==========================================================================
# Tesztkérdések és a várt útvonal (DOKUMENTUM / ADATBAZIS / MINDKETTO)
# ==========================================================================
TEST_CASES = [
    # (kérdés, várt útvonal)
    ("Megmunkálási ciklus közben a marógép megáll kerékfelfekvési hibával.-	Mi okozhatja a kerékfelfekvési hibaüzenetet?", "ADATBAZIS"),
    ("Megállt az eszterga ciklus közben főorsó forgás hibával.-	Mi okozhatja a főorsóforgás hibát?", "ADATBAZIS"),
    ("Letiltott az eszterg alacsony a főorsó kenés nyomás hibával.-	Mitől alakulhat ki az alacsony nyomás a főorsó kenésnél?", "ADATBAZIS"),
    ("Megállt a robotos cella megmunkálás közben vészkör hibával.-	Mit kell ellenőrizni a vészkör hiba megszűntetéséhez?", "DOKUMENTUM"),
]


def _line():
    print("=" * 72)


def test_level_1_router():
    """Csak a besorolást teszteli — gyors, olcsó, nem futtat RAG-ot vagy SQL-t."""
    _line()
    print("1. SZINT — ROUTER DÖNTÉS (csak besorolás)")
    _line()

    talalat = 0
    for question, expected in TEST_CASES:
        route = orchestrator_service.classify(question)
        ok = "OK " if route == expected else "!! "
        if route == expected:
            talalat += 1
        print(f"  {ok} [{route:<11}] (várt: {expected:<11}) {question}")

    print(f"\n  Találat: {talalat}/{len(TEST_CASES)} kérdés a várt ágra került.")
    print("  (A cél nem feltétlen a 100% — nézd meg, a tévesztések értelmesek-e.)\n")


def test_level_2_full():
    """A teljes ask() minden kérdésre, a route mezővel és a válasszal."""
    _line()
    print("2. SZINT — TELJES ask() MINDEN KÉRDÉSRE")
    _line()

    for question, expected in TEST_CASES:
        print(f"\nKÉRDÉS: {question}")
        print(f"  (várt útvonal: {expected})")
        result = orchestrator_service.ask(question, return_debug=True)
        print(f"  TÉNYLEGES ÚTVONAL: {result.get('route')}")
        if result.get("sql"):
            print(f"  Generált SQL: {result.get('sql')}")
        print(f"  VÁLASZ:\n    {result['answer']}")


def test_level_3_mindketto():
    """Kifejezetten a MINDKETTO ág — a drága, összefésülős út."""
    _line()
    print("3. SZINT — MINDKETTO ÁG (összefésülés)")
    _line()

    # Egy olyan kérdés, ami tényleg mindkét forrást érinti:
    question = "A szabályzat szerinti gyakorisághoz képest hány karbantartás volt idén?"
    print(f"\nKÉRDÉS: {question}\n")

    result = orchestrator_service.ask(question, return_debug=True)
    print(f"  ÚTVONAL: {result.get('route')}")
    print(f"  Generált SQL: {result.get('sql')}")
    print(f"  SQL sorok száma: {result.get('sql_row_count')}")
    print(f"\n  DOKUMENTUM-KONTEXTUS (első 500 karakter):")
    print(f"    {result.get('rag_context_preview')}")
    print(f"\n  ÖSSZEFÉSÜLT VÁLASZ:\n    {result['answer']}")


if __name__ == "__main__":
    test_level_1_router()

    # 2. és 3. szint (lassabb, teljes LLM + DB futás):
    # test_level_2_full()
    # test_level_3_mindketto()