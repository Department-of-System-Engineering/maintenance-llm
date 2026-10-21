from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.llm_service import LLMService
from services.rag_service import RAGService
from src.utils.document_processor import ingest_all_pdfs
from data.raw.vector_store import vector_client

router = APIRouter(prefix="/api/doc", tags=["Dokumentum Kezelés"])


@router.post("/ingest-all")
async def trigger_pdf_ingestion():
    try:
        ingest_all_pdfs()
        return {
            "status": "success",
            "message": "A pdfs mappában található összes dokumentum feldolgozása sikeres.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Hiba a feldolgozás során: {str(e)}"
        )


@router.get("/chunks")
async def get_stored_chunks(limit: int = 5):
    """
    Returns the text chunks stored in the vector database.
    The limit parameter controls how many items are shown at once (to prevent the browser from freezing).
    """
    try:
        # The .get() function of LangChain's ChromaDB wrapper retrieves the raw data
        db_data = vector_client.db.get(limit=limit)

        formatted_chunks = []

        # Chroma returns a dictionary for the .get() call with 'documents', 'metadatas', and 'ids' keys
        if "documents" in db_data and "metadatas" in db_data:
            for i in range(len(db_data["documents"])):
                formatted_chunks.append(
                    {
                        "id": db_data["ids"][i] if "ids" in db_data else "Unknown ID",
                        "source": db_data["metadatas"][i].get(
                            "source", "Unknown source"
                        ),
                        "page": db_data["metadatas"][i].get("page", "N/A"),
                        "text": db_data["documents"][i],
                    }
                )

        return {
            "status": "success",
            "returned_chunks_count": len(formatted_chunks),
            "data": formatted_chunks,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error when querying the database: {str(e)}"
        )
