# services/orchestrator_service.py
"""
Orchestrator — MINDIG mindkét forrást használja (router nélkül).

Minden kérdésnél lefut a RAG (dokumentum) ÉS a Text-to-SQL (adatbázis) is,
majd egy záró LLM-hívás összefésüli a kettőt egyetlen magyar válasszá.

Miért nincs router? Mert a kérdések besorolása (dokumentum vs adatbázis) a mi
adatainkon megbízhatatlan volt — a diagnosztikai kérdések dokumentumnak tűnnek,
pedig részben az adat is kell hozzájuk. Ezért inkább mindig mindkét forrást
megkérdezzük, és az összefésülő LLM dönti el, melyikből mit használ. Cserébe
minden kérdés a drágább (két forrás + összefésülés) úton fut.

A prompt-instrukciók ANGOLUL vannak (a modell pontosabban követi őket), de a
felhasználónak szánt válasz KIZÁRÓLAG magyar lehet.

A meglévő szolgáltatásokra épül, azokat NEM módosítja:
    - services.rag_service.rag_service   (a belső _retrieve_documents / _build_context metódusait használja)
    - services.text_to_sql_service.text_to_sql_service
    - services.llm_service.llm_service   (az összefésüléshez)
"""

import logging
from typing import Any, Dict

from services.llm_service import llm_service
from services.rag_service import rag_service
from services.text_to_sql_service import text_to_sql_service
from src.logic.decorators import log_step, log_exceptions

logger = logging.getLogger(__name__)


# ==========================================================================
# Merge prompt — INSTRUCTIONS IN ENGLISH, but the answer MUST be in Hungarian.
# ==========================================================================
MERGE_SYSTEM_PROMPT = """You are a helpful assistant. For the user's question you received
information from TWO sources: document excerpts and the result of a database query.
Your task is to merge the two into a SINGLE, coherent, easy-to-understand answer.
Do not repeat the two sources separately; instead, form one unified answer from them.
If one source contains no relevant information, ignore it.

IMPORTANT: You MUST write your answer to the user in HUNGARIAN ONLY, regardless of the
language of the question or the sources. Never answer in English."""


class OrchestratorService:
    def __init__(self):
        self.rag = rag_service
        self.sql = text_to_sql_service

    # ------------------------------------------------------------------
    # RAG nyers kontextus kinyerése a MEGLÉVŐ belső metódusokkal
    # (nem a kész választ kérjük, hanem a nyers dokumentum-kontextust)
    # ------------------------------------------------------------------
    def _get_rag_context(self, user_question: str) -> str:
        # A rag_service már lépésekre van bontva — ezeket hívjuk közvetlenül.
        search_query = self.rag._rewrite_query(user_question)
        summary_docs, chunk_docs = self.rag._retrieve_documents(search_query)
        pdf_context, _used_sources = self.rag._build_context(summary_docs, chunk_docs)
        return pdf_context

    # ------------------------------------------------------------------
    # A teljes folyamat: MINDIG mindkét forrás + összefésülés
    # ------------------------------------------------------------------
    @log_exceptions
    @log_step("orchestrator ask")
    def ask(self, user_question: str, return_debug: bool = False) -> Dict[str, Any]:
        # 1. Nyers dokumentum-kontextus (RAG)
        try:
            rag_context = self._get_rag_context(user_question)
        except Exception as e:
            logger.error(f"RAG kontextus hiba: {e}")
            rag_context = "(nem sikerült dokumentumot lekérni)"

        # 2. Nyers adatbázis-eredmény (Text-to-SQL, debug módban visszaadja a sorokat)
        sql_result = self.sql.ask(user_question, return_debug=True)
        sql_answer = sql_result.get("answer", "")
        sql_rows = sql_result.get("rows")
        sql_data_str = str(sql_rows) if sql_rows else sql_answer

        # 3. Összefésülés egyetlen záró LLM-hívással (a válasz magyar — lásd MERGE_SYSTEM_PROMPT)
        merge_prompt = (
            f"The user's question: {user_question}\n\n"
            f"--- DOCUMENT EXCERPTS ---\n{rag_context}\n\n"
            f"--- DATABASE RESULT ---\n{sql_data_str}\n\n"
            "Merge the two into a single, unified answer. Remember: answer in Hungarian only."
        )
        merged = llm_service.generate_clean_response(
            prompt=merge_prompt,
            system_prompt=MERGE_SYSTEM_PROMPT,
        )

        result: Dict[str, Any] = {"answer": merged.strip()}
        if return_debug:
            result["route"] = "MINDKETTO"  # mindig ez, a felület kompatibilitásáért
            result["rag_context_preview"] = rag_context[:500]
            result["sql"] = sql_result.get("sql")
            result["sql_row_count"] = sql_result.get("row_count")
        return result


# Példányosítás, hogy a router közvetlenül importálhassa
orchestrator_service = OrchestratorService()