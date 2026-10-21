from fastapi import APIRouter
from pydantic import BaseModel
from services.llm_service import LLMService
from services.rag_service import RAGService

router = APIRouter(prefix="/api/chat", tags=["Chat"])

llm_service = LLMService()
rag_service = RAGService()


class ChatRequest(BaseModel):
    query: str


# returns an answer
@router.post("/ask")
async def ask_question(request: ChatRequest):
    answer = rag_service.search_and_chat(request.query)
    return {"question": request.query, "answer": answer}
