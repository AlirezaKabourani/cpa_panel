from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///../data/app.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_sqlite_schema_compat():
    """
    Lightweight startup migration for SQLite environments where create_all
    cannot add newly introduced columns.
    """
    with engine.begin() as conn:
        def has_col(table: str, col: str) -> bool:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            return any(r[1] == col for r in rows)

        if has_col("campaigns", "id") and not has_col("campaigns", "platform"):
            conn.execute(text("ALTER TABLE campaigns ADD COLUMN platform TEXT NOT NULL DEFAULT 'rubika'"))

        if has_col("customer_media", "id") and not has_col("customer_media", "platform"):
            conn.execute(text("ALTER TABLE customer_media ADD COLUMN platform TEXT NOT NULL DEFAULT 'rubika'"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
