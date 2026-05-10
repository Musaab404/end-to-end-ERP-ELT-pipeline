import pyodbc
import psycopg2
import pandas as pd
from sqlalchemy import create_engine

# --- Connections ---
mssql_conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=your_server;"
    "DATABASE=your_db;"
    "UID=your_user;"
    "PWD=your_password;"
)

pg_engine = create_engine(
    "postgresql+psycopg2://user:password@host:5432/your_db"
)



def migrate_table(table_name: str, mssql_conn, pg_engine):
    df = pd.read_sql(f"SELECT * FROM {table_name}", mssql_conn)
    df.to_sql(
        table_name,
        pg_engine,
        if_exists="replace",   # or "append"
        index=False,
        method="multi",        # batches INSERT statements
        chunksize=1000
    )
    print(f"Migrated {len(df)} rows → {table_name}")