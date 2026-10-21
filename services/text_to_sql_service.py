# services/text_to_sql_service.py
"""
Text-to-SQL szolgáltatás — ÉLŐ SÉMÁVAL.

A 4 lépéses folyamat:
    1. Séma átadása    -> AZ ÉLŐ DB-BŐL lekérdezve (schema_inspector), nem kézzel!
    2. SQL generálás   -> az LLM (Qwen2.5) legenerálja a T-SQL parancsot
    3. Végrehajtás     -> a MEGLÉVŐ SQLAlchemy engine futtatja le (nem az LLM!)
    4. Válasz          -> az LLM barátságos magyar mondattá alakítja az eredményt

A meglévő infrastruktúrára épül:
    - services.llm_service.llm_service.generate_clean_response()  (temp=0.0 SQL-hez)
    - services.schema_inspector.get_table_schema()                (élő séma az INFORMATION_SCHEMA-ból)
    - src.db.db_connector.setup_database_connection()             (Engine a DB_URIS-ből)
    - src.logic.decorators.log_step / log_exceptions
"""

import re
import logging
from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine, CursorResult

from services.llm_service import llm_service
from services.schema_inspector import get_schema_and_text_columns
from src.db.db_connector import setup_database_connection
from src.logic.decorators import log_step, log_exceptions

logger = logging.getLogger(__name__)


# ==========================================================================
# Prompt sablonok
# ==========================================================================
SQL_GENERATION_SYSTEM_PROMPT = """You are a Microsoft SQL Server (T-SQL) expert.
Your task is to produce a single, valid T-SQL SELECT query from the user's
natural-language question, based on the database schema below.

--- DATABASE SCHEMA ---
{schema}

STRICT RULES:
1. Return ONLY the SELECT query, nothing else (no explanation, no ```sql markup).
2. NEVER write INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, MERGE or EXEC statements.
3. Use only the table and columns present in the schema above. Use exact column names.
4. Use Microsoft SQL Server syntax (e.g. 'SELECT TOP 10', not 'LIMIT 10';
   date functions: YEAR(), MONTH(), GETDATE()).
5. When aggregating, give meaningful column aliases (e.g. AS darab, AS osszeg).
6. TEXT SEARCH: when the user looks for a word, name or free text (rather than an exact
   value in a known column), you MUST search across EVERY column listed here:
       {text_columns}
   Include ALL of these columns in the WHERE clause — do not omit any, even if some seem
   less relevant. Combine every column with OR, e.g.:
       WHERE (LOWER(col_a) LIKE LOWER(N'%term%') OR LOWER(col_b) LIKE LOWER(N'%term%') OR ...)
   Always prefix string literals with N (e.g. N'%term%'), because the columns are NVARCHAR
   (Unicode) — this preserves accented Hungarian characters (á, é, ő, ű, etc.). Wrap both
   sides in LOWER() so the match is case-insensitive. Use '%term%' with wildcards on both
   sides for partial matches. If the user clearly refers to one specific column, search
   only that column instead.
7. If the question cannot be answered from the schema, return: SELECT 'NEM_MEGVALASZOLHATO' AS hiba;
"""

ANSWER_SYSTEM_PROMPT = """Te egy segítőkész asszisztens vagy, aki egy adatbázis-lekérdezés
nyers eredményét foglalja össze a felhasználónak, közérthető magyar mondatban.

FONTOS SZABÁLYOK:
1. KIZÁRÓLAG a megadott nyers adatból dolgozz. Semmit ne találj ki, ne egészíts ki
   általános tudásból. Ha valami nem szerepel az adatban, azt ne állítsd.
2. Minden állításodat KÖSD a konkrét adathoz: melyik mező vagy sor alapján állítod.
   Pl.: "A fail_solution mező szerint 3 esetben szivattyúcsere történt."
3. A válasz két részből álljon:
   - ÖSSZEFOGLALÁS: rövid, közérthető magyar válasz a kérdésre.
   - INDOKLÁS: pontokba szedve, miből következtettél erre (mely mezők, hány sor, milyen értékek).
4. Ne említsd az SQL-t vagy a technikai részleteket (tábla-, oszlopneveket használhatsz).
5. Ha az eredmény üres, közöld udvariasan, hogy nincs a feltételeknek megfelelő adat."""

# ==========================================================================
# Biztonsági réteg — csak olvasó (SELECT) lekérdezés engedélyezett
# ==========================================================================
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|MERGE|EXEC|EXECUTE|"
    r"CREATE|GRANT|REVOKE|SP_|XP_)\b",
    re.IGNORECASE,
)


def _clean_sql(raw_sql: str) -> str:
    """Eltávolítja a Markdown jelölést és a felesleges szöveget az LLM válaszából."""
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", raw_sql, re.DOTALL | re.IGNORECASE)
    if fenced:
        raw_sql = fenced.group(1)

    sql = raw_sql.strip()

    select_match = re.search(r"((?:SELECT|WITH)\b.*)", sql, re.DOTALL | re.IGNORECASE)
    if select_match:
        sql = select_match.group(1).strip()

    if ";" in sql:
        sql = sql.split(";")[0].strip()

    return sql


def _is_safe_select(sql: str) -> bool:
    """True, ha a lekérdezés kizárólag egy olvasó SELECT (semmi módosító művelet)."""
    if not sql:
        return False
    if not sql.lstrip().upper().startswith(("SELECT", "WITH")):
        return False
    if _FORBIDDEN_KEYWORDS.search(sql):
        return False
    if ";" in sql.rstrip(";"):  # stacked query védelem
        return False
    return True


# ==========================================================================
# Fő szolgáltatás
# ==========================================================================
class TextToSQLService:
    def __init__(
        self,
        table_name: str,
        db_env: str = "ICMMS_INT",
        db_schema: str = "dbo",
        max_rows: int = 100,
        cache_schema: bool = True,
    ):
        """
        :param table_name: A lekérdezhető tábla neve.
        :param db_env: A db_connector.DB_URIS egyik kulcsa (alapból 'ICMMS_INT').
        :param db_schema: Az SQL séma neve (MSSQL-ben alapból 'dbo').
        :param max_rows: Biztonsági felső korlát a válaszba beolvasott sorok számára.
        :param cache_schema: Ha True, a séma-lekérdezés csak egyszer fut le, aztán gyorsítótárból jön.
        """
        self.table_name = table_name
        self.db_env = db_env
        self.db_schema = db_schema
        self.max_rows = max_rows
        self.cache_schema = cache_schema

        self._engine: Optional[Engine] = None
        self._schema_cache: Optional[str] = None
        self._text_columns_cache: Optional[list] = None

    @property
    def engine(self) -> Engine:
        """Az SQLAlchemy engine lusta felállítása a meglévő connectorral."""
        if self._engine is None:
            self._engine = setup_database_connection(self.db_env)
        return self._engine

    # ------------------------------------------------------------------
    # 1. lépés: Séma lekérdezése az ÉLŐ adatbázisból
    # ------------------------------------------------------------------
    def get_schema(self) -> str:
        if self.cache_schema and self._schema_cache is not None:
            return self._schema_cache

        schema_text, text_columns = get_schema_and_text_columns(
            table_name=self.table_name,
            db_env=self.db_env,
            schema=self.db_schema,
            engine=self.engine,
        )
        self._text_columns_cache = text_columns
        if self.cache_schema:
            self._schema_cache = schema_text
        return schema_text

    # ------------------------------------------------------------------
    # 2. lépés: SQL generálása
    # ------------------------------------------------------------------
    @log_exceptions
    @log_step("text-to-sql generation")
    def generate_sql(self, user_question: str) -> str:
        schema = self.get_schema()  # ez tölti fel a self._text_columns_cache-t is

        # A szöveges mezők konkrét, vesszős listája a promptba (ha nincs, üres helyőrző)
        text_cols = getattr(self, "_text_columns_cache", None) or []
        text_columns_str = ", ".join(text_cols) if text_cols else "(nincs szöveges mező)"

        system_prompt = SQL_GENERATION_SYSTEM_PROMPT.format(
            schema=schema,
            text_columns=text_columns_str,
        )

        raw = llm_service.generate_clean_response(
            prompt=user_question,
            system_prompt=system_prompt,
        )
        sql = _clean_sql(raw)
        logger.info(f"Generált SQL: {sql}")
        return sql

    # ------------------------------------------------------------------
    # 3. lépés: Végrehajtás a MEGLÉVŐ engine-nel (nem az LLM!)
    # ------------------------------------------------------------------
    @log_exceptions
    @log_step("text-to-sql execution")
    def execute_sql(self, sql: str) -> pd.DataFrame:
        if not _is_safe_select(sql):
            raise ValueError(
                "A generált lekérdezés nem engedélyezett (csak SELECT olvasás támogatott)."
            )

        with self.engine.connect() as conn:
            result: CursorResult = conn.execute(text(sql))
            rows = result.fetchmany(self.max_rows)
            df = pd.DataFrame(rows, columns=result.keys())

        logger.info(f"Lekérdezés visszaadott {len(df)} sort.")
        return df

    # ------------------------------------------------------------------
    # 4. lépés: Nyers adat -> barátságos mondat
    # ------------------------------------------------------------------
    @log_exceptions
    @log_step("text-to-sql answer formulation")
    def formulate_answer(self, user_question: str, df: pd.DataFrame) -> str:
        if df.empty:
            data_str = "(nincs találat / üres eredmény)"
            stats_str = "A lekérdezés 0 sort adott vissza."
        else:
            data_str = df.to_markdown(index=False)
            non_empty_cols = [c for c in df.columns if df[c].notna().any()]
            stats_str = (
                f"A lekérdezés {len(df)} sort adott vissza. "
                f"Kitöltött oszlopok: {', '.join(non_empty_cols)}."
            )

        prompt = (
            f"A felhasználó kérdése: {user_question}\n\n"
            f"{stats_str}\n\n"
            f"A lekérdezés eredménye (nyers adat):\n{data_str}\n\n"
            "Fogalmazz egy rövid, közérthető magyar ÖSSZEFOGLALÁST, majd egy INDOKLÁST, "
            "amelyben pontosan megmondod, mely mezők és hány sor alapján következtettél a válaszra. "
            "Csak a fenti adatból dolgozz, semmit ne találj ki!"
        )
        answer = llm_service.generate_clean_response(
            prompt=prompt,
            system_prompt=ANSWER_SYSTEM_PROMPT,
        )
        return answer.strip()

    # ------------------------------------------------------------------
    # Teljes folyamat egyben
    # ------------------------------------------------------------------
    @log_exceptions
    @log_step("text-to-sql full pipeline")
    def ask(self, user_question: str, return_debug: bool = False) -> Dict[str, Any]:
        sql = self.generate_sql(user_question)

        if "NEM_MEGVALASZOLHATO" in sql.upper():
            return {
                "answer": "Sajnos erre a kérdésre a rendelkezésre álló adatokból nem tudok válaszolni.",
                "sql": sql if return_debug else None,
            }

        try:
            df = self.execute_sql(sql)
        except ValueError as ve:
            logger.warning(f"Elutasított lekérdezés: {ve}")
            return {
                "answer": "Sajnos ezt a kérést biztonsági okból nem tudom végrehajtani.",
                "sql": sql if return_debug else None,
            }
        except Exception as e:
            logger.error(f"SQL végrehajtási hiba: {e}")
            return {
                "answer": "A lekérdezés futtatása közben hiba történt. Pontosítsd a kérdést!",
                "sql": sql if return_debug else None,
                "error": str(e) if return_debug else None,
            }

        answer = self.formulate_answer(user_question, df)

        result: Dict[str, Any] = {"answer": answer}
        if return_debug:
            result["sql"] = sql
            result["row_count"] = len(df)
            result["rows"] = df.to_dict(orient="records")
        return result


# Példányosítás: a CMMS munkalap-tábla (ICMMS_INT környezet)
text_to_sql_service = TextToSQLService(
    table_name="t_cmms_wo",
    db_env="ICMMS_INT",
)