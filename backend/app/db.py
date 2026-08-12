"""Database setup.

Prototype uses SQLite; production target is PostgreSQL. All datetimes are
stored naive-UTC. Concurrency notes: see reservations service — on Postgres
we rely on SELECT ... FOR UPDATE, on SQLite on BEGIN IMMEDIATE (single
writer), both wrapped in one transaction.
"""
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DB_URL = os.environ.get("BUZZ_DB_URL", "sqlite:///./buzz_reservations.db")

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if DB_URL.startswith("sqlite") else {},
)

if DB_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    @event.listens_for(engine, "begin")
    def _sqlite_begin_immediate(conn):
        # Writers take the write-lock up-front so availability check + insert
        # inside one transaction cannot interleave (no double booking).
        conn.exec_driver_sql("BEGIN IMMEDIATE")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
