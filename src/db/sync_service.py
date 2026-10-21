import json
import numpy as np
from sqlalchemy import text
from sqlalchemy.engine import Engine
from src.db.fetch_definitions import fetch_chromadb_data
from services.rag_service import vector_client


def sync_sql_to_chroma() -> None:
    """
    Letölti a kész vektorokat az SQL Serverről a fetchers segítségével,
    szinkronizálja a ChromaDB-vel, majd frissíti a hibrid kereső memóriáját.
    """
    print("Vektorok letöltése az SQL szerverről...")

    # 1. Adatok lekérése (a fetch_definitions-ben definiált partial függvénnyel).
    # A JSON metaadatot és a VARBINARY vektort a függvény alakítja át.
    chroma_data = fetch_chromadb_data()

    if not chroma_data["ids"]:
        print("Az SQL tábla üres, nincs mit szinkronizálni.")
        return

    chunk_count = len(chroma_data["ids"])
    print(f"{chunk_count} chunk letöltve. Betöltés a ChromaDB memóriába...")

    # 2. Upsert a ChromaDB-be
    # Ha a fájl már bent van, frissíti, ha nincs, beteszi.
    vector_client.db._collection.upsert(
        ids=chroma_data["ids"],
        documents=chroma_data["documents"],
        metadatas=chroma_data["metadatas"],
        embeddings=chroma_data["embeddings"],
    )

    # 3. BM25 index újraépítése, különben a kulcsszavas keresés nem látná az új chunkokat
    print("Új adatok észlelve a ChromaDB-ben! BM25 index frissítése...")
    vector_client._init_bm25()

    print(f"ChromaDB szinkronizáció és indexelés sikeres! {chunk_count} elem aktív.")
