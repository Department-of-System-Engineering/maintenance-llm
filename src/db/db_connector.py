import json
import logging
import os
from typing import Callable, Optional, Dict, Any, Union, List
import uuid
import numpy as np
import pandas as pd
from pandas import DataFrame
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, CursorResult, Connection
from sqlalchemy.types import NVARCHAR
from dotenv import load_dotenv

from ..logic.fetchers import fetch_data_from_sql
from ..logic.decorators import log_step, log_exceptions

load_dotenv()

DB_URIS: Dict[str, Optional[str]] = {
    "PTSP": os.getenv("MSSQL_URI_PTSP"),
    "INTP": os.getenv("MSSQL_URI_INTP"),
    "AI_REPORTING": os.getenv("MSSQL_URI_AI_REPORTING"),
    "ICMMS_INT": os.getenv("MSSQL_URI_ICMMS_INT"),
    "LLM_DEV": os.getenv("MSSQL_URI_LLM_DEV"),
}

logger: logging.Logger = logging.getLogger(__name__)


@log_exceptions
@log_step("database connection")
def setup_database_connection(env: str) -> Engine:
    db_uri: str = DB_URIS.get(env)
    engine: Engine = create_engine(db_uri, fast_executemany=False)

    with engine.connect() as connection:
        result: CursorResult = connection.execute(
            text("SELECT DB_NAME() AS [Current Database]")
        )
        for row in result:
            logger.info(f"Connected to database: {row[0]}")

    return engine


def make_fetch_function(
    sql_filename: str,
    default_params: Optional[Dict[str, Any]] = None,
    step_name: str = "fetching data",
    db_env: Optional[str] = "PTSP",
    json_output: bool = False,
) -> Callable[..., Union[DataFrame, Dict[str, Any]]]:
    @log_exceptions
    @log_step(step_name)
    def fetch_func(
        engine: Engine, output_path: Optional[Path] = None, **kwargs: Any
    ) -> Union[DataFrame, Dict[str, Any]]:
        sql_path: Path = Path(__file__).parent / "queries" / sql_filename
        params: Dict[str, Any] = {**(default_params or {}), **kwargs}
        query: str = sql_path.read_text(encoding="utf-8")

        if json_output:
            if output_path is None:
                raise ValueError("Missing 'output_path' for JSON stream output.")

            with engine.connect() as conn, open(
                output_path, "w", encoding="utf-8"
            ) as f:
                result = conn.execute(text(query), params)
                for row in result:
                    if row[0]:
                        f.write(row[0])
                logger.info(f"Streamed JSON directly to file: {output_path}")
            return {"file": str(output_path)}

        else:
            df = fetch_data_from_sql(engine, str(sql_path), params)
            return df

    fetch_func.db_env = db_env
    fetch_func.json_output = json_output
    fetch_func.sql_filename = sql_filename
    return fetch_func


@log_exceptions
@log_step("bulk update from dataframe")
def bulk_update_table(
    df: DataFrame,
    target_table: str,
    id_columns: List[str],
    update_columns: Dict[str, str],
    db_env: str = "AI_REPORTING",
    chunksize: int = 50_000,
) -> None:
    engine: Engine = setup_database_connection(db_env)
    temp_table_name: str = f"##temp_bulk_{target_table}"
    index_name: str = f"IX_STAGING_{target_table}"

    update_col_names: List[str] = list(update_columns.keys())

    with engine.begin() as conn:
        conn: Connection

        column_check_query: str = """
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = :table_name
        """
        result: CursorResult = conn.execute(
            text(column_check_query), {"table_name": target_table}
        )
        existing_columns: List[str] = [row[0] for row in result]

        for col_name, sql_type in update_columns.items():
            if col_name not in existing_columns:
                logger.info(f"Adding missing column '{col_name}' as {sql_type}")
                conn.execute(
                    text(f"ALTER TABLE [{target_table}] ADD [{col_name}] {sql_type}")
                )

        cols_to_upload: List[str] = id_columns + update_col_names
        df[cols_to_upload].to_sql(
            name=temp_table_name,
            con=conn,
            if_exists="replace",
            index=False,
            chunksize=chunksize,
            dtype={
                col: NVARCHAR(255) for col in id_columns if df[col].dtype == "object"
            },
        )

        id_cols_str: str = ", ".join([f"[{col}]" for col in id_columns])
        conn.execute(
            text(f"CREATE INDEX [{index_name}] ON [{temp_table_name}] ({id_cols_str})")
        )

        set_clause: str = ", ".join(
            [f"T.[{col}] = S.[{col}]" for col in update_col_names]
        )
        join_clause: str = " AND ".join(
            [f"T.[{col}] = S.[{col}]" for col in id_columns]
        )

        conn.execute(text(f"""
            UPDATE T SET {set_clause}
            FROM [{target_table}] AS T
            INNER JOIN [{temp_table_name}] AS S ON {join_clause}
        """))

        conn.execute(text(f"DROP TABLE [{temp_table_name}]"))
        logger.info(f"Successfully updated {len(df)} rows in {target_table}")


@log_exceptions
@log_step("fetch vectors from sql for chromadb")
def fetch_vectors_for_chroma(
    sql_filename: str = "fetch_vector_data.sql", db_env: str = "LLM_DEV"
) -> Dict[str, List[Any]]:
    """
    Lerántja a vektorokat az SQL Serverről, és közvetlenül a ChromaDB
    által várt lista-struktúrává alakítja (Pandas DataFrame megkerülésével).
    """
    engine: Engine = setup_database_connection(db_env)
    sql_path: Path = Path(__file__).parent / "queries" / sql_filename
    query: str = sql_path.read_text(encoding="utf-8")

    # Ezekbe a listákba gyűjtjük az adatokat a ChromaDB számára
    data = {"ids": [], "documents": [], "metadatas": [], "embeddings": []}

    with engine.connect() as conn:
        # A fetchall() egy nyers tuple-listát ad vissza, ami a leggyorsabb
        result = conn.execute(text(query)).fetchall()

        for row in result:
            data["ids"].append(str(row[0]))  # Id
            data["documents"].append(row[1])  # Document
            data["metadatas"].append(
                json.loads(row[2])
            )  # Metadata (JSON string -> Dict)

            # A VARBINARY (bájtok) visszakódolása lebegőpontos listává
            emb_list = np.frombuffer(row[3], dtype=np.float32).tolist()
            data["embeddings"].append(emb_list)

    logger.info(f"Sikeresen kinyerve {len(data['ids'])} vektor az SQL-ből.")
    return data


@log_exceptions
@log_step("import data")
def import_data(
    fetch_fn: Callable[..., Any],
    file_path: Path,
    engine: Optional[Engine] = None,
    fetch: bool = False,
    chunksize: int = 100_000,
    **fetch_kwargs: Any,
) -> DataFrame:
    env_key = getattr(fetch_fn, "db_env", None)
    engine = setup_database_connection(env_key)

    is_json = getattr(fetch_fn, "json_output", False)
    os.makedirs(file_path.parent, exist_ok=True)

    if fetch:
        if is_json:
            fetch_fn(
                engine=engine,
                output_path=file_path.with_suffix(".json"),
                **fetch_kwargs,
            )
            logger.info(
                f"Fetched JSON and streamed to file: {file_path.with_suffix('.json')}"
            )
            return pd.DataFrame()
        else:
            df = fetch_fn(engine=engine, **fetch_kwargs)
            df.to_csv(
                file_path,
                index=False,
                encoding="utf-8",
                na_rep="NULL",
                mode="w",
                header=True,
                escapechar="\\",
            )
            logger.info(f"Fetched data and saved to CSV: {file_path}")
            return df

    if is_json:
        json_path = file_path.with_suffix(".json")
        with open(json_path, "r", encoding="utf-8") as f:
            return pd.DataFrame([json.load(f)])
    else:
        df = pd.read_csv(file_path, parse_dates=["DAT", "SCRAP_DAT"])
        logger.info(f"Data loaded from CSV: {file_path} (rows: {len(df)})")
        return df


@log_exceptions
@log_step("upload chunks to sql vector database")
def upload_vectors_to_sql(
    final_db_documents: list,
    embedding_model: Any,
    sql_filename: str = "insert_vector_chunk.sql",
    db_env: str = "LLM_DEV",
) -> int:
    """
    Extracts text, generates embeddings, and performs a bulk insert
    into the SQL Server vector table.
    """
    if not final_db_documents:
        logger.warning("No documents provided for vector upload.")
        return 0

    logger.info(
        f"Generating embeddings for {len(final_db_documents)} chunks. This may take a while..."
    )

    # 1. Extract raw data
    texts = [doc.page_content for doc in final_db_documents]
    metadatas = [doc.metadata for doc in final_db_documents]

    # 2. Generate embeddings
    vectors = embedding_model.embed_documents(texts)

    # 3. Prepare data dictionaries for SQLAlchemy Bulk Insert
    data_to_insert = []
    for i in range(len(final_db_documents)):
        data_to_insert.append(
            {
                "id": str(uuid.uuid4()),
                "doc": texts[i],
                "meta": json.dumps(metadatas[i]),
                "emb": np.array(vectors[i], dtype=np.float32).tobytes(),
            }
        )

    # 4. Read SQL file and execute transaction
    engine: Engine = setup_database_connection(db_env)
    sql_path: Path = Path(__file__).parent / "queries" / sql_filename
    insert_sql: str = sql_path.read_text(encoding="utf-8")

    with engine.begin() as conn:
        conn: Connection
        conn.execute(text(insert_sql), data_to_insert)

    logger.info(
        f"Successfully inserted {len(data_to_insert)} chunks into the vector table."
    )
    return len(data_to_insert)


@log_exceptions
@log_step("create vector table if not exists")
def setup_vector_table(
    sql_filename: str = "create_vector_table.sql", db_env: str = "LLM_DEV"
) -> None:
    """Reads the SQL file and creates the vector table if it does not already exist."""

    # 1. Establish database connection using the provided environment
    engine: Engine = setup_database_connection(db_env)

    # 2. Load the SQL query from the queries directory based on project architecture
    sql_path: Path = Path(__file__).parent / "queries" / sql_filename
    query: str = sql_path.read_text(encoding="utf-8")

    # 3. Execute the schema creation script within a transaction
    with engine.begin() as conn:
        conn: Connection
        conn.execute(text(query))

    logger.info(f"Vector table check/creation successful in environment: {db_env}")
