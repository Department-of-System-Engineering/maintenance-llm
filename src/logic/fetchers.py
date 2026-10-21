from sqlalchemy.engine import Engine, CursorResult
from sqlalchemy import text
from pandas import DataFrame
from typing import Optional, Any, Dict
import pandas as pd
from pathlib import Path

from .decorators import log_exceptions


@log_exceptions
def read_sql(query_file: str) -> str:
    p = Path(query_file)
    if not p.is_absolute():
        base_path = Path(__file__).parent
        p = base_path / query_file
    return p.read_text(encoding="utf-8")


@log_exceptions
def fetch_data_from_sql(
    engine: Engine, sql_path: str, params: Optional[Dict[str, Any]] = None
) -> DataFrame:
    with engine.begin() as conn:
        query = read_sql(sql_path)
        result: CursorResult = conn.execute(text(query), params or {})
        return pd.DataFrame(result.fetchall(), columns=result.keys())
