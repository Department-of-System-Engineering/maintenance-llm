import os
import pandas as pd
import glob
import subprocess
from langchain_community.document_loaders import (
    PyPDFDirectoryLoader,
    DirectoryLoader,
    Docx2txtLoader,
)
from langchain_core.documents import Document
from striprtf.striprtf import rtf_to_text
from pptx import Presentation
import openpyxl
from langchain_core.documents import Document
import re
import xlrd


def convert_legacy_doc_to_docx(directory_path: str):
    """Finds .doc files and converts them to .docx using LibreOffice."""
    doc_files = glob.glob(os.path.join(directory_path, "**/*.doc"), recursive=True)

    for doc_file in doc_files:
        base_name, _ = os.path.splitext(doc_file)
        docx_file = base_name + ".docx"

        # Convert only if the new file does not exist yet
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


# ==============================================================================
# 2. FILE LOADER FUNCTIONS
# ==============================================================================


def load_pdfs(directory_path: str) -> list:
    pdf_loader = PyPDFDirectoryLoader(directory_path)
    return pdf_loader.load()


def load_word_files(directory_path: str) -> list:
    docs = []
    docx_loader = DirectoryLoader(
        directory_path, glob="**/*.docx", loader_cls=Docx2txtLoader
    )
    docs.extend(docx_loader.load())

    docm_loader = DirectoryLoader(
        directory_path, glob="**/*.docm", loader_cls=Docx2txtLoader
    )
    docs.extend(docm_loader.load())
    return docs


def load_excel_tables_1(directory_path: str, extension: str) -> list:
    """
    Excel fájlokat olvas be, és a tartalmukat CSV formátumú szövegként
    LangChain Document objektumokká alakítja a RAG számára.
    """
    excel_documents = []
    CHUNK_SIZE_ROWS = 20  # Hány sor kerüljön egy RAG dokumentumba

    for file_path in glob.glob(
        os.path.join(directory_path, f"**/*.{extension}"), recursive=True
    ):
        try:
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:

                # Nyers beolvasás (header=None biztosítja, hogy semmit nem vágunk le a tetejéről)
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

                if df.empty:
                    continue

                # Chunkolás és memórián belüli CSV konverzió
                for i in range(0, len(df), CHUNK_SIZE_ROWS):
                    chunk_df = df.iloc[i : i + CHUNK_SIZE_ROWS]

                    # to_csv fájlnév nélkül stringet ad vissza!
                    # sep=';' tartja az Excel kompatibilis magyar elválasztást
                    csv_text = chunk_df.to_csv(index=False, header=False, sep=";")

                    # Ha véletlenül csak üres sorok lennének a chunkban (pl. ;;;;\n;;;;)
                    if not csv_text.replace(";", "").replace("\n", "").strip():
                        continue

                    # Összeállítjuk a szöveget, amit az LLM látni fog
                    text_content = (
                        f"--- FORRÁS FÁJL: {os.path.basename(file_path)} | MUNKALAP: {sheet_name} ---\n"
                        f"ADATOK CSV FORMÁTUMBAN (Sorok: {i+1} - {min(i + CHUNK_SIZE_ROWS, len(df))}):\n"
                        f"{csv_text}"
                    )

                    # Létrehozzuk a LangChain dokumentumot
                    doc = Document(
                        page_content=text_content,
                        metadata={
                            "source": file_path,
                            "sheet": sheet_name,
                            "type": "excel_to_csv_chunk",
                        },
                    )
                    excel_documents.append(doc)

        except Exception as e:
            print(f"Hiba a fájl olvasásakor ({file_path}): {e}")

    return excel_documents


def load_excel_tables_old(directory_path: str, extension: str) -> list:
    """Processes Excel files (xls or xlsx) and creates 20-row Markdown tables."""
    excel_documents = []
    CHUNK_SIZE_ROWS = 20

    for file_path in glob.glob(
        os.path.join(directory_path, f"**/*.{extension}"), recursive=True
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

                    # Formatting text based on file type (Keeping Hungarian context for the LLM)
                    if extension == "xlsx":
                        text_content = (
                            f"MŰSZAKI TÁBLÁZAT ÉS KARBANTARTÁSI UTASÍTÁSOK:\n"
                            f"Ez a szakasz a(z) {os.path.basename(file_path)} nevű (régi formátumú) Excel fájl '{sheet_name}' munkalapjáról származik. "
                            f"A lenti táblázat kritikus technológiai utasításokat, alkatrész-listákat, gépbeállításokat és karbantartási lépéseket tartalmaz. "
                            f"Keresésnél és válaszadásnál tekintsd ezt hivatalos gépkönyvi forrásnak!\n\n"
                            f"--- TÁBLÁZAT ADATAI (Sorok: {i+1} - {min(i + CHUNK_SIZE_ROWS, len(df))}) ---\n"
                            f"{markdown_table}"
                        )
                    else:
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
                    excel_documents.append(doc)
        except Exception as e:
            print(f"Error reading {extension} Excel file ({file_path}): {e}")

    return excel_documents


def load_powerpoints(directory_path: str) -> list:
    pptx_documents = []
    for file_path in glob.glob(
        os.path.join(directory_path, "**/*.pptx"), recursive=True
    ):
        try:
            prs = Presentation(file_path)
            slide_texts = []

            # Iterate through all slides in the presentation
            for i, slide in enumerate(prs.slides):
                slide_texts.append(f"--- {i+1}. DIA ---")

                # Read all text boxes, titles, and shapes on the slide
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_texts.append(shape.text.strip())

            text_content = "\n".join(slide_texts)

            # Save only if there is meaningful text
            if len(text_content.strip()) > 10:
                doc = Document(
                    page_content=text_content, metadata={"source": file_path}
                )
                pptx_documents.append(doc)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    return pptx_documents


def load_rtf_files(directory_path: str) -> list:
    rtf_documents = []
    for file_path in glob.glob(
        os.path.join(directory_path, "**/*.rtf"), recursive=True
    ):
        try:
            # Open the file (errors='ignore' helps with weird character encodings)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_rtf_content = f.read()

            # Convert to plain text (assuming rtf_to_text is defined)
            text_content = rtf_to_text(raw_rtf_content)

            # Save only if there is meaningful text
            if len(text_content.strip()) > 10:
                doc = Document(
                    page_content=text_content, metadata={"source": file_path}
                )
                rtf_documents.append(doc)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    return rtf_documents



# ══════════════════════════════════════════════════════════════════════
# EXCEL LOADER — .xlsx + .xls támogatás
#
# Stratégia: NEM próbáljuk "kitalálni" a fejléc-struktúrát, mert az
# Excel fájlok felépítése nagyon változatos. Ehelyett:
#   1) Hűségesen visszaadjuk a cellák tartalmát pozíció-megőrzéssel
#   2) Cellaformázást (háttérszín) is kinyerjük, mert jelentést hordoz
#   3) Minden chunk elején megismételjük a felső sorokat (metadata kontextus)
#   4) Összefoglaló (summary) chunk a teljes munkalapról
# ══════════════════════════════════════════════════════════════════════
 
CHUNK_SIZE_ROWS = 20          # Hány sor kerüljön egy adat-chunkba
CONTEXT_ROWS = 8              # A felső N sort minden chunk elején ismételjük
SUMMARY_ROWS = 30             # Összefoglaló chunkba ennyi sor kerül
 
 
def load_excel_tables(
    directory_path: str,
    extensions: list[str] | None = None,
    extension: str | None = None,
) -> list[Document]:
    """
    Megkeresi az összes Excel fájlt (.xlsx + .xls) és RAG dokumentumokat ad vissza.
    """
    if extensions is None:
        if extension is not None:
            extensions = [extension]
        else:
            extensions = ["xlsx", "xls"]
 
    all_documents = []
 
    for ext in extensions:
        files = glob.glob(
            os.path.join(directory_path, f"**/*.{ext}"), recursive=True
        )
        print(f"Talált .{ext} fájlok: {len(files)} db")
 
        for file_path in files:
            try:
                docs = _parse_workbook(file_path)
                all_documents.extend(docs)
                print(f"  ✓ {os.path.basename(file_path)}  →  {len(docs)} chunk")
            except Exception as e:
                print(f"  ✗ {os.path.basename(file_path)}: {e}")
 
    print(f"\n✅ Összesen {len(all_documents)} Excel chunk a RAG számára.")
    return all_documents
 
 
# ─── Routing ──────────────────────────────────────────────────────────
 
 
def _parse_workbook(file_path: str) -> list[Document]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".xls":
        return _parse_xls_workbook(file_path)
    return _parse_xlsx_workbook(file_path)
 
 
# ─── .xlsx feldolgozás (openpyxl) ────────────────────────────────────
 
 
def _parse_xlsx_workbook(file_path: str) -> list[Document]:
    documents = []
    wb = openpyxl.load_workbook(file_path, data_only=True)
 
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        docs = _parse_sheet_xlsx(ws, file_path, sheet_name)
        documents.extend(docs)
 
    return documents
 
 
def _parse_sheet_xlsx(ws, file_path: str, sheet_name: str) -> list[Document]:
    """
    Egy .xlsx munkalap hűséges feldolgozása:
      - Merged cellák feloldása
      - Háttérszínek kinyerése
      - Pozíció-megőrző szöveges kimenet
    """
    # 1. Merged cellák feltérképezése
    merged_map = {}
    for mr in ws.merged_cells.ranges:
        anchor_val = ws.cell(mr.min_row, mr.min_col).value
        for r in range(mr.min_row, mr.max_row + 1):
            for c in range(mr.min_col, mr.max_col + 1):
                merged_map[(r, c)] = anchor_val
 
    # 2. Összes sor kiolvasása szöveggel + háttérszínnel
    all_rows = []
    for row in ws.iter_rows():
        cells = []
        for cell in row:
            # Érték: merged → anchor, egyébként saját
            raw_val = merged_map.get((cell.row, cell.column), cell.value)
            text = _clean_cell(raw_val)
 
            # Háttérszín kinyerése
            color_tag = _get_color_tag(cell)
            if color_tag and text:
                text = f"{text} {color_tag}"
            elif color_tag and not text:
                text = color_tag
 
            cells.append(text)
        all_rows.append(cells)
 
    return _build_chunks(all_rows, file_path, sheet_name)
 
 
def _get_color_tag(cell) -> str:
    """
    Cella háttérszínéből olvasható tag-et csinál.
    Pl. sárga háttér → "[SÁRGA]", kék → "[KÉK]"
    Üres vagy fehér/szürke háttérnél üres stringet ad.
    """
    try:
        fill = cell.fill
        if fill is None or fill.patternType is None or fill.patternType == "none":
            return ""
 
        fg = fill.fgColor
        if fg is None or fg.rgb is None:
            return ""
 
        rgb = str(fg.rgb)
 
        # Átlátszó / fehér / szürke → nem jelöljük
        if rgb in ("00000000", "FFFFFFFF", "00FFFFFF") or rgb.startswith("00"):
            return ""
 
        # Theme-index alapú színek (openpyxl néha csak theme-et ad)
        if fg.type == "theme":
            return "[JELÖLT]"
 
        # RGB → szín-név mapping (leggyakoribb Excel-színek)
        hex_color = rgb[-6:].upper()
        color_map = {
            "FFFF00": "[SÁRGA]",
            "FFFF99": "[HALVÁNYSÁRGA]",
            "FFC000": "[NARANCSSÁRGA]",
            "FF0000": "[PIROS]",
            "FF6666": "[HALVÁNYPIROS]",
            "00FF00": "[ZÖLD]",
            "92D050": "[ZÖLD]",
            "00B050": "[ZÖLD]",
            "0000FF": "[KÉK]",
            "0070C0": "[KÉK]",
            "4472C4": "[KÉK]",
            "5B9BD5": "[HALVÁNYKÉK]",
            "BDD7EE": "[HALVÁNYKÉK]",
            "D9E2F3": "[HALVÁNYKÉK]",
        }
 
        for hex_prefix, tag in color_map.items():
            if hex_color == hex_prefix:
                return tag
 
        # Ismeretlen de létező szín → általános jelölés
        return "[JELÖLT]"
 
    except Exception:
        return ""
 
 
# ─── .xls feldolgozás (pandas + xlrd) ────────────────────────────────
 
 
def _parse_xls_workbook(file_path: str) -> list[Document]:
    """
    .xls fájl feldolgozása. Háttérszínt xlrd-vel olvassuk,
    merged cellák korlátozottan támogatottak.
    """
    documents = []
 
    try:
        # xlrd a formázáshoz kell (formatting_info=True)
        rb = xlrd.open_workbook(file_path, formatting_info=True)
    except Exception:
        # Ha nem sikerül formatting_info-val, próbáljuk nélküle
        try:
            rb = xlrd.open_workbook(file_path)
        except Exception as e:
            print(f"    Nem sikerült megnyitni: {e}")
            return []
 
    for sheet_idx in range(rb.nsheets):
        sh = rb.sheet_by_index(sheet_idx)
        sheet_name = sh.name
 
        all_rows = []
        for r in range(sh.nrows):
            cells = []
            for c in range(sh.ncols):
                cell = sh.cell(r, c)
                text = _clean_cell(cell.value if cell.ctype != 0 else None)
 
                # Háttérszín xlrd-vel
                color_tag = _get_xls_color_tag(rb, sh, r, c)
                if color_tag and text:
                    text = f"{text} {color_tag}"
                elif color_tag and not text:
                    text = color_tag
 
                cells.append(text)
            all_rows.append(cells)
 
        docs = _build_chunks(all_rows, file_path, sheet_name)
        documents.extend(docs)
 
    return documents
 
 
def _get_xls_color_tag(workbook, sheet, row, col) -> str:
    """Háttérszín kinyerése .xls fájlból xlrd-vel."""
    try:
        xf_idx = sheet.cell_xf_index(row, col)
        xf = workbook.xf_list[xf_idx]
        bg_color_idx = xf.background.pattern_colour_index
 
        # 0, 64, 65 = fehér/alapértelmezett
        if bg_color_idx in (0, 64, 65):
            return ""
 
        # xlrd color map
        color_map = workbook.colour_map
        if bg_color_idx in color_map and color_map[bg_color_idx]:
            r, g, b = color_map[bg_color_idx]
            # Fehér / szürke kiszűrése
            if r > 240 and g > 240 and b > 240:
                return ""
            if r == g == b:
                return ""
 
            # Szín-felismerés
            if g > 200 and r > 200 and b < 100:
                return "[SÁRGA]"
            if r > 200 and g < 100 and b < 100:
                return "[PIROS]"
            if g > 200 and r < 100:
                return "[ZÖLD]"
            if b > 200 and r < 100 and g < 150:
                return "[KÉK]"
            if r > 200 and g > 150 and b < 100:
                return "[NARANCSSÁRGA]"
            return "[JELÖLT]"
 
        return ""
    except Exception:
        return ""
 
 
# ─── Közös: chunkolás ─────────────────────────────────────────────────
 
 
def _clean_cell(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    # Pandas/xlrd float "45.0" → "45" ha egész
    if re.match(r"^\d+\.0$", text):
        text = text[:-2]
    return text
 
 
def _build_chunks(
    all_rows: list[list[str]], file_path: str, sheet_name: str
) -> list[Document]:
    """
    Nyers sorokból RAG chunkokat épít.
 
    1) Üres oszlopok eltávolítása
    2) Összefoglaló chunk (type="summary") az első SUMMARY_ROWS sorból
    3) Adat chunkok (type="chunk"), mindegyik elején a felső CONTEXT_ROWS
       sor megismételve (gépszám, részleg, fejléc stb.)
    """
    # Üres sorok kiszűrése (de pozíciót NEM változtatunk, a sor-szám megmarad)
    indexed_rows = [
        (i + 1, row) for i, row in enumerate(all_rows)
        if any(v for v in row)
    ]
 
    if not indexed_rows:
        return []
 
    # Üres oszlopok eltávolítása
    max_cols = max(len(row) for _, row in indexed_rows)
    padded = [(idx, row + [""] * (max_cols - len(row))) for idx, row in indexed_rows]
 
    non_empty_cols = [
        c for c in range(max_cols)
        if any(row[c] for _, row in padded)
    ]
    cleaned = [(idx, [row[c] for c in non_empty_cols]) for idx, row in padded]
 
    if not cleaned:
        return []
 
    fname = os.path.basename(file_path)
 
    # ─── Sor → szöveg konverzió ───
    def row_to_text(row_num: int, cells: list[str]) -> str:
        # 1. Jobbról levágja az üres cellákat a tömörség kedvéért (meglévő logika)
        while cells and not cells[-1]:
            cells = cells[:-1]

        # 2. Egymást követő AZONOS értékek összevonása (összevont Excel-cellák!)
        #    Pl. a 17x ismételt címsorból 1 db marad.
        deduped = []
        prev = object()  # olyan kezdőérték, ami semmivel nem egyezik
        for val in cells:
            if val != prev:
                deduped.append(val)
            prev = val

        return f"Sor {row_num}: {' | '.join(deduped)}"
 
    # ─── Kontextus sorok (felső pár sor, ami metaadatokat tartalmaz) ───
    context_lines = []
    for idx, row in cleaned[:CONTEXT_ROWS]:
        context_lines.append(row_to_text(idx, row))
    context_text = "\n".join(context_lines)
 
    documents = []
 
    # ─── 1. Összefoglaló chunk ───
    summary_lines = []
    for idx, row in cleaned[:SUMMARY_ROWS]:
        summary_lines.append(row_to_text(idx, row))
 
    summary_text = (
        f"═══ ÖSSZEFOGLALÓ: {fname} | MUNKALAP: {sheet_name} ═══\n"
        f"TELJES MÉRET: {len(cleaned)} sor, {len(non_empty_cols)} oszlop\n"
        f"{'─' * 60}\n"
        + "\n".join(summary_lines)
    )
 
    documents.append(Document(
        page_content=summary_text,
        metadata={
            "source": file_path,
            "sheet": sheet_name,
            "type": "summary",
        },
    ))
 
    # ─── 2. Adat chunkok (a kontextus-sorok után induló részek) ───
    data_rows = cleaned[CONTEXT_ROWS:]
 
    if not data_rows:
        return documents  # Csak summary van, az is elég
 
    for chunk_start in range(0, len(data_rows), CHUNK_SIZE_ROWS):
        chunk = data_rows[chunk_start : chunk_start + CHUNK_SIZE_ROWS]
 
        chunk_lines = []
        for idx, row in chunk:
            chunk_lines.append(row_to_text(idx, row))
 
        first_row = chunk[0][0]
        last_row = chunk[-1][0]
 
        text_content = (
            f"═══ FORRÁS: {fname} | MUNKALAP: {sheet_name} ═══\n"
            f"FELSŐ SOROK (kontextus):\n{context_text}\n"
            f"{'─' * 60}\n"
            f"ADATOK (sor {first_row} – {last_row}):\n"
            + "\n".join(chunk_lines)
        )
 
        documents.append(Document(
            page_content=text_content,
            metadata={
                "source": file_path,
                "sheet": sheet_name,
                "type": "chunk",
            },
        ))
 
    return documents