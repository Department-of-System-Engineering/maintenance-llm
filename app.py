import chainlit as cl

from services.rag_service import rag_service
from data.raw.vector_store import vector_client
from src.db.sync_service import sync_sql_to_chroma

# Orchestrator: minden kérdésre lefuttatja a RAG-ot és a Text-to-SQL-t, majd összefésüli
from services.orchestrator_service import orchestrator_service


@cl.on_chat_start
async def start():
    """Ez fut le egyszer, amikor megnyitod a chat oldalt a böngészőben."""
    try:
        sync_sql_to_chroma()
        # Lekérjük az adatbázis méretét, ahogy a main.py-ban csináltad
        db_meret = len(vector_client.db.get()["ids"])
        welcome_msg = (
            f"**Karbantartó Chat Demo**\n"
            f"Az adatbázisban jelenleg **{db_meret}** szövegdarab található.\n\n"
            f"Írd be a kérdésed, és válaszolok a források alapján!"
        )
    except Exception:
        welcome_msg = "**RAG Backend Online!**\nÍrd be a kérdésed!"

    await cl.Message(content=welcome_msg).send()


# A háttér-infó (melyik ágra került a kérdés) emberi nyelvre fordítása a lépés-címhez
_ROUTE_LABELS = {
    "DOKUMENTUM": "Dokumentumokban keresek…",
    "ADATBAZIS": "Lekérdezem az adatbázist…",
    "MINDKETTO": "Dokumentum + adatbázis együtt…",
}


@cl.on_message
async def main(message: cl.Message):
    """Ez a függvény kezeli a beérkező üzeneteket, tehermentesítve a főszálat."""
    user_question = message.content

    if not user_question.strip():
        return

    # A feldolgozás egy kinyitható Chainlit-lépésben jelenik meg
    async with cl.Step(name="Kérdés elemzése és válasz generálása…") as step:
        try:
            # Az orchestrator szinkron (blokkoló) hívás — LLM + DB.
            # A cl.make_async külön szálra teszi, hogy a felület ne fagyjon be.
            # return_debug=True -> visszakapjuk a route-ot és a generált SQL-t is.
            async_ask = cl.make_async(orchestrator_service.ask)

            result = await async_ask(user_question=user_question, return_debug=True)

            answer = result["answer"]
            route = result.get("route")

            # A lépés címét a tényleges útvonalra frissítjük (szép visszajelzés)
            if route in _ROUTE_LABELS:
                step.name = _ROUTE_LABELS[route]

            # A háttér-infó a lépés "output" mezőjébe kerül, így a fő választól
            # elkülönül, de a lépés kinyitásával megtekinthető.
            debug_lines = []
            if route:
                debug_lines.append(f"Útvonal: {route}")
            if result.get("sql"):
                debug_lines.append(f"Generált SQL: {result['sql']}")
            if result.get("sql_row_count") is not None:
                debug_lines.append(f"SQL sorok száma: {result['sql_row_count']}")
            if debug_lines:
                step.output = "\n".join(debug_lines)

            step.status = "success"

        except Exception as e:
            answer = f"Hiba történt a generálás során: {str(e)}"
            step.status = "failed"

    # Válasz visszaküldése a felületre
    await cl.Message(content=answer).send()