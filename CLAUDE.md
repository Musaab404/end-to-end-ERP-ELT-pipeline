# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`jal-warehouse` is an ERP data warehouse pipeline that extracts data from source systems (MSSQL, Kaggle CSVs) and loads it into Supabase (PostgreSQL). The project follows a staged ETL structure: extract → load → transform (via dbt).

## Environment Setup

```bash
# Activate virtual environment
.venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

Required `.env` variables:
- `SUPABASE_DB_PASSWORD`
- `SUPABASE_DIRECT_CONNECTION_STRING` — full PostgreSQL connection string for Supabase

## Running Scripts

```bash
# Load a CSV into Supabase
python load/csv_to_supabase.py

# Pull and migrate a table from MSSQL to PostgreSQL
python extract/pull_data.py
```

## Architecture

```
kaggle-data/        # Source CSVs (ERP entities: SalesOrders, Products, Employees, etc.)
extract/            # MSSQL → PostgreSQL migration (pyodbc + SQLAlchemy)
load/               # CSV → Supabase loader (pandas + SQLAlchemy)
transform/          # Planned: Python-based transformations
dbt/                # Planned: dbt models for warehouse transformations
sql/                # Planned: Raw SQL queries/scripts
orchestration/      # Planned: Pipeline scheduling/orchestration
configs/            # Planned: Pipeline configuration files
tests/              # Planned: Test suite
logs/               # Runtime logs
supabase/           # Planned: Supabase-specific migrations or config
```

### Key design decisions

- **`load/csv_to_supabase.py`**: Uses `df.to_sql(..., if_exists="replace")` — re-running will drop and recreate the table. Use `"append"` for incremental loads.
- **`extract/pull_data.py`**: MSSQL connection strings are currently hardcoded placeholders — update before use. Same `if_exists="replace"` behavior applies.
- All Supabase credentials are loaded via `python-dotenv` from `.env`. Never hardcode them.
- The Kaggle dataset models SAP-style ERP entities (SalesOrders, BusinessPartners, Products, Addresses, Employees).
