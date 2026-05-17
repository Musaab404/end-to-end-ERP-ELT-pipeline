"""
load_addresses.py

Loads Addresses.csv into the Supabase bronze.erp_addresses table.
Improvements over v1:
  - Env var validation at startup
  - Proper logging instead of silent execution
  - Batched upserts to avoid request size limits
  - Error handling at each stage (file, transform, DB)
  - Typo fix: 'longitiude' -> 'longitude'
  - numpy dependency removed
  - Pathlib-based file path (no hardcoded relative paths)
  - __main__ guard
"""

import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Logging setup — do this before anything else so every log has a timestamp
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CSV_PATH = Path(__file__).parent / "Addresses.csv"  # always relative to THIS file
SCHEMA = "bronze"
TABLE = "erp_addresses"
BATCH_SIZE = 500  # rows per upsert request — tune based on row width

RENAME_MAP = {
    "ADDRESSID": "address_id",
    "CITY": "city",
    "POSTALCODE": "postal_code",          # fixed typo: 'posta_code' -> 'postal_code'
    "STREET": "street",
    "BUILDING": "building",
    "COUNTRY": "country",
    "REGION": "region",
    "ADDRESSTYPE": "address_type",
    "VALIDITY_STARTDATE": "validity_start_date",
    "VALIDITY_ENDDATE": "validity_end_date",
    "LATITUDE": "latitude",
    "LONGITUDE": "longitude",             # fixed typo: 'longitiude' -> 'longitude'
}


# ---------------------------------------------------------------------------
# Helper functions — each does one thing, making the main() easy to read
# ---------------------------------------------------------------------------

def load_env() -> tuple[str, str]:
    """
    Load and validate required environment variables.
    Raises EnvironmentError early — before any DB connection is attempted —
    so the failure message is clear and actionable.
    """


    
    load_dotenv()

    url = os.getenv("DB_URL")
    key = os.getenv("DB_KEY")

    missing = [name for name, val in [("DB_URL", url), ("DB_KEY", key)] if not val]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Check your .env file."
        )

    return url, key  # type: ignore[return-value]  # already validated above


def read_csv(path: Path) -> pd.DataFrame:
    """
    Read the CSV and immediately replace NaN with None.

    Why None instead of NaN?
    Supabase (and most JSON serialisers) don't understand float('nan').
    None serialises to JSON null, which maps to SQL NULL correctly.

    We use pd.DataFrame.where() here instead of df.replace({np.nan: None})
    so we don't need to import numpy at all.
    """
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file not found at: {path}")

    # Replace NaN with None without numpy
    df = df.where(df.notna(), other=None)

    logger.info("Loaded %d rows from %s", len(df), path.name)
    return df


def transform(df: pd.DataFrame) -> list[dict]:
    """
    Rename columns to snake_case and convert to a list of dicts.
    Validates that all expected source columns are actually present in the file.
    """
    missing_cols = set(RENAME_MAP.keys()) - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"CSV is missing expected columns: {missing_cols}. "
            "Check the file or update RENAME_MAP."
        )

    df = df.rename(columns=RENAME_MAP)
    return df.to_dict(orient="records")


def upsert_batches(client: Client, records: list[dict]) -> None:
    """
    Send records to Supabase in chunks of BATCH_SIZE.

    Why batch?
    A single HTTP request with 50k rows will exceed Supabase's payload limit
    and likely time out. Batching keeps each request small and gives you
    progress logging and partial-failure visibility.
    """
    total = len(records)
    batches = range(0, total, BATCH_SIZE)

    for i, start in enumerate(batches, start=1):
        batch = records[start : start + BATCH_SIZE]
        end = min(start + BATCH_SIZE, total)

        try:
            response = (
                client.schema(SCHEMA)
                .table(TABLE)
                .upsert(batch)
                .execute()
            )
            # Supabase-py raises on HTTP errors, but log the response status too
            logger.info(
                "Batch %d/%d — rows %d–%d upserted successfully.",
                i, len(batches), start + 1, end,
            )
        except Exception as e:
            # Don't swallow the error — re-raise after logging so the caller
            # knows exactly which batch failed and why.
            logger.error("Batch %d/%d failed (rows %d–%d): %s", i, len(batches), start + 1, end, e)
            raise


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("Starting address ingestion pipeline.")

    # 1. Config
    url, key = load_env()
    client = create_client(url, key)
    logger.info("Supabase client initialised.")

    # 2. Extract
    df = read_csv(CSV_PATH)

    # 3. Transform
    records = transform(df)
    logger.info("Transformed %d records. Beginning upsert.", len(records))

    # 4. Load
    upsert_batches(client, records)

    logger.info("Pipeline complete. %d records loaded into %s.%s.", len(records), SCHEMA, TABLE)


if __name__ == "__main__":
    main()