
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# Locate the project root and load .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Read database configuration
connection_url = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME")
)

engine = create_engine(connection_url)

try:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT DATABASE(), VERSION()")
        )
        database, version = result.fetchone()

        print("MySQL connection successful!")
        print("Database:", database)
        print("MySQL version:", version)

except Exception as error:
    print("Connection failed:", error)

finally:
    engine.dispose()
