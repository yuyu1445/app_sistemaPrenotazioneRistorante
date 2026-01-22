from __future__ import annotations

from pathlib import Path
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "ristorante.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def ensure_customer_auth_columns() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='customer'"
        )
        if cursor.fetchone() is None:
            return

        cursor.execute("PRAGMA table_info(customer)")
        columns = {row[1] for row in cursor.fetchall()}

        if "username" not in columns:
            cursor.execute("ALTER TABLE customer ADD COLUMN username VARCHAR(50)")
        if "password_hash" not in columns:
            cursor.execute("ALTER TABLE customer ADD COLUMN password_hash VARCHAR(255)")
        if "is_active" not in columns:
            cursor.execute(
                "ALTER TABLE customer ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
            )
        conn.commit()
    finally:
        conn.close()
