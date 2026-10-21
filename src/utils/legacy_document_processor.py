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
from utils.document_loaders import (
    convert_legacy_doc_to_docx,
    load_pdfs,
    load_word_files,
    load_excel_tables,
    load_powerpoints,
    load_rtf_files,
)


def ingest_all_pdfs_more_chunks(directory_path: str):
    # 1. Load PDFs from the folder
    pdf_loader = PyPDFDirectoryLoader(directory_path)
    pdf_documents = pdf_loader.load()

    # Load docx from the folder
    docx_loader = DirectoryLoader(
        directory_path, glob="**/*.docx", loader_cls=Docx2txtLoader
    )
    docx_documents = docx_loader.load()

    # Load doc from the folder
    doc_documents = []
    print("Régi .doc fájlok feldolgozása az antiword segítségével...")

    doc_files = glob.glob(os.path.join(directory_path, "**/*.doc"), recursive=True)

    for file_path in doc_files:
        try:
            # Calling Antiword directly on linux
            result = subprocess.run(
                ["antiword", file_path], capture_output=True, text=True, check=True
            )
            text_content = result.stdout

            # Only if ut has text
            if len(text_content.strip()) > 10:
                doc = Document(
                    page_content=text_content, metadata={"source": file_path}
                )
                doc_documents.append(doc)
        except Exception as e:
            print(f"Hiba a {file_path} olvasásakor: {e}")

    # Load xlsx from the folder
    xlsx_documents = []
    CHUNK_SIZE_ROWS = 20  # How many rows a chunk should contain

    # Find all .xlsx files in the folder and its subfolders
    for file_path in glob.glob(
        os.path.join(directory_path, "**/*.xlsx"), recursive=True
    ):

        # Open the Excel file
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)

            if df.empty:
                continue

            # Split the table into 20-row "Markdown" chunks (Both Nomic and Qwen understand this!)
            for i in range(0, len(df), CHUNK_SIZE_ROWS):
                chunk_df = df.iloc[i : i + CHUNK_SIZE_ROWS]
                markdown_table = chunk_df.to_markdown(index=False)

                text_content = (
                    f"--- EXCEL FÁJL: {os.path.basename(file_path)} | MUNKALAP: {sheet_name} "
                    f"| SOROK: {i+1} - {min(i + CHUNK_SIZE_ROWS, len(df))} ---\n\n"
                    f"{markdown_table}"
                )

                # ADD LABEL: "type": "table_chunk"
                doc = Document(
                    page_content=text_content,
                    metadata={
                        "source": file_path,
                        "sheet": sheet_name,
                        "type": "table_chunk",
                    },
                )
                xlsx_documents.append(doc)

    documents = pdf_documents + docx_documents + doc_documents + xlsx_documents

    docs_by_source = {}
    for doc in documents:
        src = doc.metadata.get("source", "Ismeretlen fájl")
        if src not in docs_by_source:
            docs_by_source[src] = []
        docs_by_source[src].append(doc)

    final_db_documents = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)

    for source, docs in docs_by_source.items():
        print(f"Feldolgozás és összefoglalás: {source}...")

        # 2. Concatenate the full text of the file
        full_text = "\n".join([d.page_content for d in docs])

        # 3. GENERATE SUMMARY (PARENT) WITH THE LLM
        # Important: Truncate the first 12000 characters to fit the LLM's 4096 token window!
        summary_prompt = (
            "Te egy dokumentációs szakértő vagy. Készíts egy nagyon tömör, vázlatpontos "
            "tartalomjegyzéket a következő dokumentumból. Sorold fel tételesen, hogy milyen "
            "alkatrészek, gépek, folyamatok vagy főbb témák szerepelnek benne. Ne írj hosszú mondatokat!\n\n"
            f"--- DOKUMENTUM ELEJE ---\n{full_text[:12000]}"
        )

        try:
            from services.llm_service import llm_service

            # Call the LLM to write the index
            summary_text = llm_service.generate_chat_response(
                prompt=summary_prompt, pdf_context=""
            )

            # Create the Parent document with the "summary" label
            summary_doc = Document(
                page_content=f"DOKUMENTUM ÖSSZEFOGLALÓ ÉS TARTALOMJEGYZÉK ({source}):\n{summary_text}",
                metadata={"source": source, "type": "summary"},
            )
            final_db_documents.append(summary_doc)
            print("Összefoglaló kész!")

        except Exception as e:
            print(f"Hiba az összefoglaló generálásakor: {e}")

        # 4. CREATE CHILD (DETAILED) CHUNKS
        # Now split the full text in the traditional way
        chunks = text_splitter.split_text(full_text)
        for chunk_text in chunks:
            chunk_doc = Document(
                page_content=chunk_text,
                metadata={
                    "source": source,
                    "type": "chunk",
                },  # They get the "chunk" label!
            )
            final_db_documents.append(chunk_doc)

        # 2. Splitting (to fit into the context)
        """
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=400)
        chunks = text_splitter.split_documents(documents)
        """

        # 3. Upload to the vector database
        # vector_client.db.add_documents(chunks)
        # return len(chunks)
    vector_client.db.add_documents(final_db_documents)
    return len(final_db_documents)


def ingest_all_pdfs_without_summary(directory_path: str):
    documents = []

    # 1. PDFs
    for file_path in glob.glob(
        os.path.join(directory_path, "**/*.pdf"), recursive=True
    ):
        try:
            loader = PyPDFLoader(
                file_path
            )  # Itt fájlonként töltünk, hogy biztos meglegyen a path
            for doc in loader.load():
                doc.metadata["source"] = file_path
                documents.append(doc)
        except Exception as e:
            print(f"Hiba a PDF olvasásakor {file_path}: {e}")

    # 2. DOCX
    for file_path in glob.glob(
        os.path.join(directory_path, "**/*.docx"), recursive=True
    ):
        try:
            loader = Docx2txtLoader(file_path)
            for doc in loader.load():
                doc.metadata["source"] = file_path
                documents.append(doc)
        except Exception as e:
            print(f"Hiba a DOCX olvasásakor {file_path}: {e}")

    # 4. XLSX
    for file_path in glob.glob(
        os.path.join(directory_path, "**/*.xlsx"), recursive=True
    ):
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            if not df.empty:
                doc = Document(
                    page_content=f"--- EXCEL: {os.path.basename(file_path)} | MUNKALAP: {sheet_name} ---\n\n{df.to_markdown(index=False)}",
                    metadata={"source": file_path, "sheet": sheet_name},
                )
                documents.append(doc)

    # 5. Grouping
    docs_by_source = {}
    for doc in documents:
        src = doc.metadata.get("source", "Ismeretlen fájl")
        if src not in docs_by_source:
            docs_by_source[src] = []
        docs_by_source[src].append(doc)

    # 6. Chunk and upload
    final_db_documents = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)

    for source, docs in docs_by_source.items():
        # Itt összefűzzük a tartalmát, de csak chunkoljuk, nem AI-zzuk
        full_text = "\n".join([d.page_content for d in docs])
        chunks = text_splitter.split_text(full_text)

        for chunk_text in chunks:
            final_db_documents.append(
                Document(
                    page_content=chunk_text,
                    metadata={"source": source},  # Itt az eredeti forrás
                )
            )

    vector_client.db.add_documents(final_db_documents)
    return len(final_db_documents)


def ingest_all_pdfs(directory_path: str):
    # 1. Load PDFs from the folder
    pdf_loader = PyPDFDirectoryLoader(directory_path)
    pdf_documents = pdf_loader.load()

    # Load doc from the folder
    doc_files = glob.glob(os.path.join(directory_path, "**/*.doc"), recursive=True)

    for doc_file in doc_files:
        base_name, _ = os.path.splitext(doc_file)
        docx_file = base_name + ".docx"

        # Csak akkor konvertál, ha még nem létezik az új fájl
        if not os.path.exists(docx_file):
            try:
                outdir = os.path.dirname(doc_file)
                subprocess.run(
                    [
                        "libreoffice",
                        "--headless",
                        "--convert-to",
                        "docx",
                        "--outdir",
                        outdir,
                        doc_file,
                    ],
                    capture_output=True,
                    check=True,
                )
            except Exception as e:
                print(f"Error while converting {doc_file}: {e}")

    # Load docx from the folder
    docx_loader = DirectoryLoader(
        directory_path, glob="**/*.docx", loader_cls=Docx2txtLoader
    )
    docx_documents = docx_loader.load()

    # Load docm from the folder
    docm_loader = DirectoryLoader(
        directory_path, glob="**/*.docm", loader_cls=Docx2txtLoader
    )
    docm_documents = docm_loader.load()

    # Load xlsx from the folder
    xlsx_documents = []
    CHUNK_SIZE_ROWS = 20  # How many rows a chunk should contain

    # Find all .xlsx files in the folder and its subfolders
    for file_path in glob.glob(
        os.path.join(directory_path, "**/*.xlsx"), recursive=True
    ):

        # Open the Excel file
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)

            if df.empty:
                continue

            # Split the table into 20-row "Markdown" chunks (Both Nomic and Qwen understand this!)
            for i in range(0, len(df), CHUNK_SIZE_ROWS):
                chunk_df = df.iloc[i : i + CHUNK_SIZE_ROWS]
                markdown_table = chunk_df.to_markdown(index=False)

                text_content = (
                    f"MŰSZAKI TÁBLÁZAT ÉS KARBANTARTÁSI UTASÍTÁSOK:\n"
                    f"Ez a szakasz a(z) {os.path.basename(file_path)} nevű (régi formátumú) Excel fájl '{sheet_name}' munkalapjáról származik. "
                    f"A lenti táblázat kritikus technológiai utasításokat, alkatrész-listákat, gépbeállításokat és karbantartási lépéseket tartalmaz. "
                    f"Keresésnél és válaszadásnál tekintsd ezt hivatalos gépkönyvi forrásnak!\n\n"
                    f"--- TÁBLÁZAT ADATAI (Sorok: {i+1} - {min(i + CHUNK_SIZE_ROWS, len(df))}) ---\n"
                    f"{markdown_table}"
                )

                # ADD LABEL: "type": "table_chunk"
                doc = Document(
                    page_content=text_content,
                    metadata={
                        "source": file_path,
                        "sheet": sheet_name,
                        "type": "table_chunk",
                    },
                )
                xlsx_documents.append(doc)

    # Load xls from the folder
    xls_documents = []

    for file_path in glob.glob(
        os.path.join(directory_path, "**/*.xls"), recursive=True
    ):
        try:
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)

                if df.empty:
                    continue

                for i in range(0, len(df), CHUNK_SIZE_ROWS):
                    chunk_df = df.iloc[i : i + CHUNK_SIZE_ROWS]
                    markdown_table = chunk_df.to_markdown(index=False)

                    text_content = (
                        f"--- RÉGI EXCEL FÁJL: {os.path.basename(file_path)} | MUNKALAP: {sheet_name} "
                        f"| SOROK: {i+1} - {min(i + CHUNK_SIZE_ROWS, len(df))} ---\n\n"
                        f"{markdown_table}"
                    )

                    doc = Document(
                        page_content=text_content,
                        metadata={
                            "source": file_path,
                            "sheet": sheet_name,
                            "type": "table_chunk",
                        },
                    )
                    xls_documents.append(doc)
        except Exception as e:
            print(f"Hiba a régi Excel ({file_path}) olvasásakor: {e}")

    # Load pptx from the folder
    pptx_documents = []

    pptx_files = glob.glob(os.path.join(directory_path, "**/*.pptx"), recursive=True)

    for file_path in pptx_files:
        try:
            prs = Presentation(file_path)
            slide_texts = []

            # Végigmegyünk a prezentáció összes diáján
            for i, slide in enumerate(prs.slides):
                slide_texts.append(f"--- {i+1}. DIA ---")

                # Kiolvassuk a dián lévő összes szövegdobozt, címet, alakzatot
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_texts.append(shape.text.strip())

            text_content = "\n".join(slide_texts)

            # Csak akkor mentjük el, ha valóban van benne értékelhető szöveg
            if len(text_content.strip()) > 10:
                doc = Document(
                    page_content=text_content, metadata={"source": file_path}
                )
                pptx_documents.append(doc)
        except Exception as e:
            print(f"Hiba a {file_path} olvasásakor: {e}")

    # LOad rtf from the folder
    rtf_documents = []

    rtf_files = glob.glob(os.path.join(directory_path, "**/*.rtf"), recursive=True)

    for file_path in rtf_files:
        try:
            # Megnyitjuk a fájlt (az errors='ignore' segít a furcsa karakterkódolásoknál)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_rtf_content = f.read()

            # Átalakítjuk tiszta szöveggé
            text_content = rtf_to_text(raw_rtf_content)

            # Csak akkor mentjük, ha van benne érdemi szöveg
            if len(text_content.strip()) > 10:
                doc = Document(
                    page_content=text_content, metadata={"source": file_path}
                )
                rtf_documents.append(doc)
        except Exception as e:
            print(f"Hiba a {file_path} olvasásakor: {e}")

    documents = (
        pdf_documents
        + docx_documents
        + docm_documents
        + xlsx_documents
        + xls_documents
        + pptx_documents
        + rtf_documents
    )

    docs_by_source = {}
    for doc in documents:
        src = doc.metadata.get("source", "Ismeretlen fájl")
        if src not in docs_by_source:
            docs_by_source[src] = []
        docs_by_source[src].append(doc)

    final_db_documents = []
    MAX_CHARACTER_LIMIT = (
        12000  # Ennél hosszabb dokumentumot darabolunk
    )

    # Behozunk egy standard LangChain text splittert a nagy fájlokhoz
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=4000, chunk_overlap=400, length_function=len
    )

    for source, docs in docs_by_source.items():
        file_name = os.path.basename(source)

        # Excel fájlok: a betöltő már munkalaponként és 20 soronként darabolta őket,
        # ezért változtatás nélkül kerülnek tovább.
        if file_name.endswith((".xlsx", "xls")):
            for excel_doc in docs:
                final_db_documents.append(excel_doc)
            continue

        # --- SZÖVEGES FÁJLOK (PDF, DOC, DOCX) KEZELÉSE ---
        full_text = "\n".join([d.page_content for d in docs])

        if len(full_text.strip()) < 50:
            continue

        # Dúsított tartalom alapértelmezett fejléccel
        enriched_content = f"=== DOKUMENTUM FORRÁS: {file_name} ===\n\n" f"{full_text}"

        # 1. eset: A dokumentum kényelmesen BEFÉR a limit alá -> EGYBEN HAGYJUK
        if len(enriched_content) <= MAX_CHARACTER_LIMIT:
            print(f"Fájl beolvasása EGYBEN (rövid doksi): {file_name}...")
            doc_item = Document(
                page_content=enriched_content,
                metadata={"source": source, "type": "chunk"},
            )
            final_db_documents.append(doc_item)

        # 2. eset: A gépkönyv TÚL NAGY -> FELTÉTELES DARABOLÁS INDUL
        else:
            print(
                f"⚠️ Óriási fájl észlelve ({len(enriched_content)} kar.). Intelligens szeletelés: {file_name}"
            )

            # Kinyerjük a fájl legfontosabb első 600 karakterét (globális kontextus ablak)
            file_context = full_text[:600]

            # Feldaraboljuk a nagyméretű folyószöveget 4000 karakteres részekre
            chunks = splitter.split_text(full_text)

            for i, chunk_text in enumerate(chunks):
                # A legelső chunk megtartja az eredeti elejét, a többi elé odamásoljuk a kontextust
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

                doc_item = Document(
                    page_content=combined_content,
                    metadata={"source": source, "type": "chunk"},
                )
                final_db_documents.append(doc_item)

    # 3. Feltöltés a vektoradatbázisba
    if final_db_documents:
        vector_client.db.add_documents(final_db_documents)
        print(f"Sikeresen feltöltve {len(final_db_documents)} adatbázis elem!")

    return len(final_db_documents)


def ingest_all_documents_without_db(directory_path: str) -> int:
    """Main process: Reading, chunking, and uploading files to the vector database."""

    # 1. Prepare legacy formats
    convert_legacy_doc_to_docx(directory_path)

    # 2. Extract raw data
    documents = []
    documents.extend(load_pdfs(directory_path))
    documents.extend(load_word_files(directory_path))
    documents.extend(load_excel_tables(directory_path, extension="xlsx"))
    documents.extend(load_excel_tables(directory_path, extension="xls"))
    documents.extend(load_powerpoints(directory_path))
    documents.extend(load_rtf_files(directory_path))

    # 3. Intelligent chunking and contextual enrichment
    final_db_documents = split_and_enrich_documents(documents)

    # 4. Upload to database
    inserted_count = upload_to_vector_db(final_db_documents)

    return inserted_count
