from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_ollama import OllamaEmbeddings
from config.settings import settings

class VectorStoreClient:
    def __init__(self):
        print("Vektoradatbázis és modellek inicializálása...")
        
        # 1. Beágyazó modell
        self.embeddings = OllamaEmbeddings(
            model=settings.search_model,
            base_url=settings.ollama_host,
            num_ctx = 16384
        )
        
        self.persist_directory = "./data/chroma_db"
        self._db = None  # Lusta inicializálás: az első .db hozzáféréskor jön létre
        
        # 2. BM25 felállítása
        self.bm25_retriever = None
        self._init_bm25()


    @property
    def db(self):
        if self._db is None:
            self._db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
        return self._db

    def _init_bm25(self):
        print("BM25 kulcsszavas index betöltése a memóriába...")
        try:
            # A 'self.db' hozzáférés itt hozza létre a Chroma klienst (lásd a db property-t)
            all_data = self.db.get() 
            docs = []
            
            if all_data and all_data.get('documents'):
                for txt, meta in zip(all_data['documents'], all_data['metadatas']):
                    docs.append(Document(page_content=txt, metadata=meta))
                    
            if docs:
                self.bm25_retriever = BM25Retriever.from_documents(docs)
                print(f"BM25 hibrid index sikeresen felállt! ({len(docs)} db fájlból)")
            else:
                print("A ChromaDB üres, így a BM25 index nem épült fel.")
                
        except Exception as e:
            print(f" Hiba a BM25 betöltésekor: {e}")

vector_client = VectorStoreClient()