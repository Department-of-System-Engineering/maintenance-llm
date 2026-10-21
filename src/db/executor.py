import pandas as pd
from pathlib import Path
import logging
import uuid
import json
import numpy as np
from sqlalchemy import text
from sqlalchemy.engine import Engine, Connection
from .db_connector import setup_database_connection, bulk_update_table, import_data
from .fetch_definitions import fetch_k1_hokez, fetch_maintenance_df, fetch_proba
from ..logic.decorators import log_step, log_exceptions
from ..utils.logging_utils import setup_logger


@log_exceptions
@log_step("fetch maintenance dataframe example")
def run_fetch_example():
    log = setup_logger("db_fetch_example", "outputs/logs/db_fetch_example")

    csv_output_path = Path("data/raw/maintenance_data.csv")
    log.info(f"Fetching maintenance dataframe to {csv_output_path}")

    try:
        df_maint = import_data(
            fetch_fn=fetch_maintenance_df, file_path=csv_output_path, fetch=True
        )
        log.info(
            f"Maintenance dataframe successfully fetched. " f"Rows: {len(df_maint)}"
        )
    except Exception as e:
        log.error(f"Maintenance fetch operation failed: {e}")


@log_exceptions
@log_step("bulk update example")
def run_bulk_update_example():
    log = setup_logger("db_bulk_update", "outputs/logs/db_bulk_update")

    log.info("Executing bulk update on 'dim_kerek' table...")

    try:
        target_table = "dim_kerek"
        db_env = "AI_REPORTING"

        engine = setup_database_connection(db_env)
        query = f"SELECT TOP 5 [KEREKAZON] FROM [{target_table}]"
        df_sample = pd.read_sql(query, engine)

        if not df_sample.empty:
            df_sample["LAST_MODIFIED"] = pd.Timestamp.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            bulk_update_table(
                df=df_sample,
                target_table=target_table,
                id_columns=["KEREKAZON"],
                update_columns={"LAST_MODIFIED": "NVARCHAR(50)"},
                db_env=db_env,
            )
            log.info(f"Bulk update completed successfully for {len(df_sample)} rows.")
        else:
            log.warning("No records found in target table to update.")

    except Exception as e:
        log.error(f"Bulk update operation failed: {e}")

@log_exceptions
@log_step("fetch proba dataframe example")
def run_proba_fetch():
    log = setup_logger("db_proba_fetch", "outputs/logs/db_proba_fetch")

    csv_output_path = Path("data/raw/proba_data.csv")
    log.info(f"Fetching proba dataframe to {csv_output_path}")

    try:
        df_proba = import_data(
            fetch_fn=fetch_proba, file_path=csv_output_path, fetch=True
        )
        log.info(
            f"Proba dataframe successfully fetched. " f"Rows: {len(df_proba)}"
        )
    except Exception as e:
        log.error(f"Proba fetch operation failed: {e}")

if __name__ == "__main__":
    # Execute the suite
    run_proba_fetch()
