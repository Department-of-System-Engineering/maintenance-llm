from .db_connector import make_fetch_function, fetch_vectors_for_chroma
from functools import partial

# example
fetch_k1_hokez = make_fetch_function(
    sql_filename="fetch_k1_hokez_json.sql",
    step_name="fetching k1 hokez data",
    db_env="AI_REPORTING",
    json_output=True,
)

fetch_maintenance_df = make_fetch_function(
    sql_filename="fetch_maintenance_df.sql",
    step_name="fetching maintenance dataframe",
    db_env="AI_REPORTING",
    json_output=False,
)

fetch_t_cmms_wo = make_fetch_function(
    sql_filename="t_cmms_wo.sql",
    step_name="fetching maintenance dataframe",
    db_env="ICMMS_INT",
    json_output=False,
)


fetch_chromadb_data = partial(
    fetch_vectors_for_chroma,
    sql_filename="fetch_vector_data.sql",  # src/db/queries/fetch_vector_data.sql
    db_env="LLM_DEV",
)
