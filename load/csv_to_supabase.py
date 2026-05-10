import pandas as pd
import os
from pathlib import Path
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("SUPABASE_URL")
engine = create_engine(db_url)


df = pd.read_csv(Path("C:\\Users\\musaa\\jal-warehouse\\kaggle-data\\Addresses.csv"))

df.to_sql('erp_addresses', engine, if_exists='replace', index=False)