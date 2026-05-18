import logging
import os
from pathlib import Path
import math
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
CSV_PATH = Path("C:\\Users\\musaa\\jal-warehouse\\kaggle-data\\Addresses.csv")
SCHEMA = "bronze"
TABLE = "bronze_erp_addresses"
BATCH_SIZE = 500  # rows per upsert request — tune based on row width


# ---------------------------------------------------------------------------
# Helper functions — each does one thing, making main() easy to read
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


def upsert_batches(client: Client, records: list[dict]) -> None:
    """
    Send records to Supabase in chunks of BATCH_SIZE.

    Why batch?
    A single HTTP request with 50k rows will exceed Supabase's payload limit
    and likely time out. Batching keeps each request small and gives you
    progress logging and partial-failure visibility.
    """
    total = len(records)
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for i, start in enumerate(range(0, total, BATCH_SIZE), start=1):
        batch = records[start : start + BATCH_SIZE]
        end = min(start + BATCH_SIZE, total)

        try:
            (
                client.schema(SCHEMA)
                .table(TABLE)
                .upsert(batch)
                .execute()
            )
            logger.info(
                "Batch %d/%d — rows %d–%d upserted successfully.",
                i, num_batches, start + 1, end,
            )
        except Exception as e:
            # Don't swallow the error — re-raise after logging so the caller
            # knows exactly which batch failed and why.
            logger.error(
                "Batch %d/%d failed (rows %d–%d): %s",
                i, num_batches, start + 1, end, e,
            )
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
    records = [
        {k: (None if isinstance(v, float) and math.isnan(v) else v)
         for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]
    logger.info("Converted DataFrame to %d records.", len(records))
    logger.info("Converted DataFrame to %d records.", len(records))

    logger.info("Converted DataFrame to %d records.", len(records))

    # 4. Load
    upsert_batches(client, records)

    logger.info(
        "Pipeline complete. %d records loaded into %s.%s.",
        len(records), SCHEMA, TABLE,
    )


if __name__ == "__main__":
    main()