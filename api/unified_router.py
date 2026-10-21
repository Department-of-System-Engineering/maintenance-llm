# api/unified_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.orchestrator_service import orchestrator_service

router = APIRouter(prefix="/api/ask", tags=["Unified"])


class UnifiedQuestionRequest(BaseModel):
    query: str
    debug: bool = False  # ha True, a válasz tartalmazza a generált SQL-t és a nyers részleteket


@router.post("")
async def unified_ask(request: UnifiedQuestionRequest):
    """
    Egyetlen közös belépési pont. Az orchestrator minden kérdésre lefuttatja
    a dokumentumkeresést (RAG) és a Text-to-SQL-t is, majd egy válasszá fésüli őket.

    Példa:
        { "query": "Hány karbantartás történt tavaly?", "debug": true }
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Üres kérdés.")

    try:
        result = orchestrator_service.ask(
            user_question=request.query,
            return_debug=request.debug,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestrator hiba: {str(e)}")

    return {"question": request.query, **result}