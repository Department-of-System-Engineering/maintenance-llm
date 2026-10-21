from ollama import Client
from services.llm_service import llm_service
from services.rag_service import rag_service
from data.raw.vector_store import vector_client
from fastapi import FastAPI
from api.chat_router import router as chat_router
from src.utils.document_processor import print_stored_chunks
from api.unified_router import router as unified_router

app = FastAPI(title="Saját RAG Backend")
app.include_router(unified_router)

# Hozzácsatoljuk a chat végpontokat az alkalmazáshoz
app.include_router(chat_router)


@app.get("/")
async def root():
    return {"message": "The server is running!"}


def main() -> None:

    '''
    # DATABASE CHECK
    db_meret = len(vector_client.db.get()["ids"])
    print(f"\n[Rendszer] Az adatbázisban lévő szövegdarabok száma: {db_meret}")
    # print_stored_chunks()

    # Interactive loop: keep answering until Ctrl+C
    while True:
        try:
            user_question = input("\nÍrd be a kérdésed! > ")
            if not user_question.strip():
                continue

            print("Gondolkodom...")

            # Calling rag_service. It will search in ChromaDB
            answer = rag_service.search_and_chat(user_query=user_question)

            print("\nVÁLASZ:")
            print(answer)

        except KeyboardInterrupt:
            print("\nKilépés...")
            break
    '''

if __name__ == "__main__":
    main()
