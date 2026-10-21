# services/schema_inspector.py
"""
Séma-lekérdező az élő MSSQL adatbázisból.

Az INFORMATION_SCHEMA.COLUMNS rendszernézetből olvassa ki egy tábla
oszlopait és típusait, majd az LLM számára emészthető szöveges séma-
leírássá alakítja. Így a Text-to-SQL mindig a VALÓDI, aktuális sémát
látja — nem kell kézzel karbantartani.

Ugyanarra az infrastruktúrára épül, mint a projekt többi része:
    - src.db.db_connector.setup_database_connection()  (Engine a DB_URIS-ből)
    - src.logic.decorators.log_step / log_exceptions
"""

import logging
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.db.db_connector import setup_database_connection
from src.logic.decorators import log_step, log_exceptions

logger = logging.getLogger(__name__)

# Ezeket a típusokat tekintjük "szöveges" mezőnek a szöveges kereséshez.
_TEXT_TYPES = {"nvarchar", "varchar", "nchar", "char", "ntext", "text"}


@log_exceptions
@log_step("inspect table schema")
def get_table_schema(
    table_name: str,
    db_env: str = "ICMMS_INT",
    schema: str = "dbo",
    engine: Optional[Engine] = None,
) -> str:
    """
    Egy tábla oszlopainak lekérdezése az élő DB-ből, LLM-barát szöveggé formázva.

    A séma VÉGÉRE beszúr egy explicit listát a szöveges (NVARCHAR/VARCHAR) mezőkről,
    hogy az LLM ne maga próbálja kikövetkeztetni őket a típusokból — készen kapja,
    mely mezőkben kell szöveget keresnie.

    :param table_name: A tábla neve.
    :param db_env: A db_connector.DB_URIS egyik kulcsa (alapból 'ICMMS_INT').
    :param schema: Az SQL séma neve (MSSQL-ben alapból 'dbo').
    :param engine: Opcionális kész Engine; ha None, felállítja a db_env alapján.
    :return: Szöveges sématábla-leírás az LLM promptjához.

    Példa kimenet:
        Tábla: dbo.WHEEL_MAINTENANCE
            - KEREKAZON      (nvarchar(50)   ) NOT NULL
            - MEGJEGYZES     (nvarchar(500)  ) NULL
            - DAT            (date           ) NULL
            ...

        SZÖVEGES (NVARCHAR/VARCHAR) MEZŐK, ezekben kell szöveget keresni:
            KEREKAZON, MEGJEGYZES
    """
    schema_text, _text_cols = get_schema_and_text_columns(
        table_name=table_name, db_env=db_env, schema=schema, engine=engine
    )
    return schema_text


@log_exceptions
def get_schema_and_text_columns(
    table_name: str,
    db_env: str = "ICMMS_INT",
    schema: str = "dbo",
    engine: Optional[Engine] = None,
) -> Tuple[str, List[str]]:
    """
    Mint a get_table_schema, de VISSZAADJA a szöveges mezők listáját is (külön),
    hogy a hívó (pl. a Text-to-SQL prompt) explicit fel tudja sorolni őket.

    :return: (séma_szöveg, szöveges_mezők_listája)
    """
    if engine is None:
        engine = setup_database_connection(db_env)

    # Paraméteres lekérdezés (nincs string-behelyettesítés a táblanévbe -> SQL injection ellen)
    query = text(
        """
        SELECT
            COLUMN_NAME,
            DATA_TYPE,
            CHARACTER_MAXIMUM_LENGTH,
            IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = :table_name
          AND TABLE_SCHEMA = :schema
        ORDER BY ORDINAL_POSITION
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(
            query, {"table_name": table_name, "schema": schema}
        ).fetchall()

    if not rows:
        raise ValueError(
            f"A(z) '{schema}.{table_name}' tábla nem található a(z) '{db_env}' adatbázisban, "
            f"vagy nincs jogosultság a sémájának olvasására."
        )

    lines: List[str] = [f"Tábla: {schema}.{table_name}"]
    text_columns: List[str] = []

    for col_name, data_type, max_len, is_nullable in rows:
        # Hossz hozzáfűzése a szöveges típusokhoz (pl. nvarchar(255))
        if max_len is not None and max_len != -1:
            type_str = f"{data_type}({max_len})"
        elif max_len == -1:
            type_str = f"{data_type}(max)"
        else:
            type_str = str(data_type)

        nullable_str = "NULL" if is_nullable == "YES" else "NOT NULL"
        lines.append(f"    - {col_name:<20} ({type_str:<15}) {nullable_str}")

        # Szöveges mező? -> gyűjtsük külön listába
        if str(data_type).lower() in _TEXT_TYPES:
            text_columns.append(col_name)

    # A séma VÉGÉRE egy explicit lista a szöveges mezőkről — ezt az LLM készen kapja
    if text_columns:
        lines.append("")
        lines.append("SZÖVEGES (NVARCHAR/VARCHAR) MEZŐK, ezekben kell szöveget keresni:")
        lines.append("    " + ", ".join(text_columns))

    schema_text = "\n".join(lines)
    logger.info(
        f"Séma lekérdezve: {schema}.{table_name} "
        f"({len(rows)} oszlop, ebből {len(text_columns)} szöveges)"
    )
    return schema_text, text_columns


if __name__ == "__main__":
    # Gyors teszt. Futtatás a projekt gyökeréből:  python -m services.schema_inspector
    TABLE = "t_cmms_wo"
    schema_txt, text_cols = get_schema_and_text_columns(TABLE, db_env="ICMMS_INT")
    print(schema_txt)
    print("\n--- Kigyűjtött szöveges mezők ---")
    print(text_cols)