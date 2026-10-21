import PyPDF2
import os
import pandas as pd
import glob
import subprocess
from langchain_text_splitters import RecursiveCharacterTextSplitter
from data.raw.vector_store import vector_client
from langchain_community.document_loaders import (
    PyPDFDirectoryLoader,
    DirectoryLoader,
    PyPDFLoader,
    Docx2txtLoader,
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import UnstructuredWordDocumentLoader
from striprtf.striprtf import rtf_to_text
from pptx import Presentation
from src.db.db_connector import upload_vectors_to_sql, setup_vector_table
from langchain_ollama import OllamaEmbeddings
from config.settings import settings
from .document_loaders import (
    convert_legacy_doc_to_docx,
    load_pdfs,
    load_word_files,
    load_excel_tables,
    load_powerpoints,
    load_rtf_files,
)
from sqlalchemy import text


def get_pdf_text(file_paths: list[str]) -> str:
    """
    Reads the provided list of PDF files and returns the full text.
    """
    full_text = ""
    for path in file_paths:
        if not os.path.exists(path):
            print(f"Figyelmeztetés: A fájl nem található - {path}")
            continue

        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    full_text += extracted + "\n"
    return full_text


def ingest_all_documents(directory_path: str) -> int:
    """Main process: Reading, chunking, and uploading files to the vector database."""

    # Define target environment
    TARGET_ENV = "LLM_DEV"
    print(f"Starting ingestion process for directory: {directory_path}")

    # 0. Prepare Database (create the vector table if missing)
    prepare_database(db_env=TARGET_ENV)

    # 1. Prepare legacy formats
    convert_legacy_doc_to_docx(directory_path)

    # 2. Extract raw data
    documents = []
    documents.extend(load_pdfs(directory_path))
    documents.extend(load_word_files(directory_path))
    documents.extend(load_excel_tables(directory_path))
    documents.extend(load_powerpoints(directory_path))
    documents.extend(load_rtf_files(directory_path))

    # 3. Intelligent chunking and contextual enrichment
    final_db_documents = split_and_enrich_documents(documents)

    # 4. Embed and Upload to SQL (The vectorized storage process)
    inserted_count = process_and_store_vectors(
        final_db_documents=final_db_documents, db_env=TARGET_ENV
    )

    print(f"Ingestion process completed. Total chunks uploaded: {inserted_count}")
    return inserted_count


# ==============================================================================
# 3. CHUNKING & ENRICHMENT FUNCTIONS
# ==============================================================================


def split_and_enrich_documents(documents: list) -> list:
    """Groups documents by source, then splits them based on character limit."""
    final_db_documents = []
    MAX_CHARACTER_LIMIT = 12000

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=4000, chunk_overlap=400, length_function=len
    )

    # Group by source file
    docs_by_source = {}
    for doc in documents:
        src = doc.metadata.get("source", "Unknown file")
        if src not in docs_by_source:
            docs_by_source[src] = []
        docs_by_source[src].append(doc)

    for source, docs in docs_by_source.items():
        file_name = os.path.basename(source)

        # Pass Excel tables through without modification
        if file_name.endswith((".xlsx", ".xls")):
            final_db_documents.extend(docs)
            continue

        # Concatenate text files
        full_text = "\n".join([d.page_content for d in docs])
        if len(full_text.strip()) < 50:
            continue

        enriched_content = f"=== DOKUMENTUM FORRÁS: {file_name} ===\n\n{full_text}"

        # Case 1: Short document fits under the limit comfortably
        if len(enriched_content) <= MAX_CHARACTER_LIMIT:
            print(f"Reading file as a WHOLE (short doc): {file_name}...")
            final_db_documents.append(
                Document(
                    page_content=enriched_content,
                    metadata={"source": source, "type": "chunk"},
                )
            )

        # Case 2: Large document, requires intelligent chunking
        else:
            print(
                f" Huge file detected ({len(enriched_content)} chars). Intelligent slicing: {file_name}"
            )
            file_context = full_text[:600]
            chunks = splitter.split_text(full_text)

            for i, chunk_text in enumerate(chunks):
                if i > 0:
                    combined_content = (
                        f"=== DOKUMENTUM FORRÁS: {file_name} ===\n"
                        f"--- GLOBÁLIS FÁJL KONTEXTUS ---\n{file_context}\n\n"
                        f"--- DOKUMENTUM RÉSZLET (Szelet #{i+1}) ---\n{chunk_text}"
                    )
                else:
                    combined_content = (
                        f"=== DOKUMENTUM FORRÁS: {file_name} ===\n\n{chunk_text}"
                    )

                final_db_documents.append(
                    Document(
                        page_content=combined_content,
                        metadata={"source": source, "type": "chunk"},
                    )
                )

    return final_db_documents


# ==============================================================================
# 4. DATABASE UPLOAD FUNCTION
# ==============================================================================


def upload_to_vector_db(final_db_documents: list) -> int:
    """Uploads the processed items to the database."""
    if final_db_documents:
        vector_client.db.add_documents(final_db_documents)
        print(f"Successfully uploaded {len(final_db_documents)} database items!")

    return len(final_db_documents)


def process_and_store_vectors(final_db_documents: list, db_env: str = "LLM_DEV") -> int:
    """Generálja a vektorokat és feltölti az SQL Serverbe a kész chunkokat."""
    if not final_db_documents:
        print("Nincs mit feldolgozni: a dokumentum lista üres.")
        return 0

    # 1. Modell inicializálása a feltöltéshez
    print(f"Ollama modell betöltése a vektorizáláshoz: {settings.search_model}")
    my_embeddings = OllamaEmbeddings(
        model=settings.search_model, base_url=settings.ollama_host, num_ctx=16384
    )

    # 2. Adatbázis tranzakció
    print(f"Indul az SQL feltöltés a {db_env} adatbázisba...")
    inserted_count = upload_vectors_to_sql(
        final_db_documents=final_db_documents,
        embedding_model=my_embeddings,
        sql_filename="insert_vector_chunk.sql",
        db_env=db_env,
    )

    return inserted_count


def prepare_database(db_env: str = "LLM_DEV", wipe_existing: bool = True) -> None:
    """Ellenőrzi, és szükség esetén létrehozza a vektoradatbázis tábláját az SQL Serveren."""
    print(f"Adatbázis tábla ellenőrzése / létrehozása a {db_env} környezetben...")
    setup_vector_table(sql_filename="create_vector_table.sql", db_env=db_env)
    if wipe_existing:
        print(
            "FIGYELEM: A korábbi vektorok törlése (TRUNCATE)... Tiszta lappal indulunk!"
        )

        from src.db.db_connector import setup_database_connection

        engine = setup_database_connection(db_env)

        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE [LlmKnowledgeBase]"))

        print("Adatbázis sikeresen kiürítve!")


def print_stored_chunks(limit=81):
    print(f"Adatbázis tartalmának lekérdezése... (Max {limit} db mutatása)\n")

    # Most local databases (e.g. ChromaDB) support the .get() method,
    # which returns the raw data.
    db_data = vector_client.db.get(limit=limit)

    if not db_data or not db_data.get("documents"):
        print("Az adatbázis jelenleg teljesen üres!")
        return

    for i in range(len(db_data["documents"])):
        szoveg = db_data["documents"][i]
        meta = db_data["metadatas"][i]

        # Extract metadata (if any)
        forras = meta.get("source", "Ismeretlen fájl")
        oldal = meta.get("page", "N/A")

        print(f"--- [ {i+1}. DARAB ] | Fájl: {forras} | Oldal: {oldal} ---")
        print(szoveg)
