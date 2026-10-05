import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import DB_PATH, DATABASE_URL

DIALECT = 'postgres' if DATABASE_URL else 'sqlite'

try:
    import psycopg
    from psycopg.rows import dict_row
    IntegrityError = (sqlite3.IntegrityError, psycopg.IntegrityError)
except ImportError:  # psycopg is only required when DATABASE_URL is set
    psycopg = None
    IntegrityError = (sqlite3.IntegrityError,)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Connection:
    """Runs the same '?'-placeholder SQL on SQLite and PostgreSQL."""

    def __init__(self, raw, dialect: str):
        self.raw = raw
        self.dialect = dialect

    def execute(self, sql, params=()):
        if self.dialect == 'postgres':
            sql = sql.replace('?', '%s')
        return self.raw.execute(sql, params)

    def lock_for_write(self, table: str, row_id: str) -> None:
        """Serialise writers on one row so balance checks cannot race."""
        if self.dialect == 'sqlite':
            self.raw.execute('BEGIN IMMEDIATE')
        else:
            self.raw.execute(f'SELECT id FROM {table} WHERE id=%s FOR UPDATE', (row_id,))

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def connect() -> Connection:
    if DIALECT == 'postgres':
        if psycopg is None:
            raise RuntimeError('DATABASE_URL is set but psycopg is not installed')
        return Connection(psycopg.connect(DATABASE_URL, row_factory=dict_row), 'postgres')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return Connection(conn, 'sqlite')


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = '''
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT,
    tier INTEGER, tier_reason TEXT, requested_deposit NUMERIC(12,2),
    first_deposit_amount NUMERIC(12,2), expected_payment_days INTEGER,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
    invoice_number TEXT NOT NULL UNIQUE, total_amount NUMERIC(12,2) NOT NULL CHECK(total_amount > 0),
    due_date TEXT, status TEXT NOT NULL DEFAULT 'NO_PAYMENT',
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL, amount NUMERIC(12,2) NOT NULL CHECK(amount > 0),
    payment_date TEXT NOT NULL, payment_method TEXT, reference TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS invoice_history (
    id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL, event_type TEXT NOT NULL,
    description TEXT NOT NULL, amount NUMERIC(12,2), reference_id TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_history_invoice ON invoice_history(invoice_id);
CREATE INDEX IF NOT EXISTS idx_history_created ON invoice_history(created_at)
'''


def init_db() -> None:
    with get_db() as conn:
        for statement in SCHEMA.split(';'):
            if statement.strip():
                conn.execute(statement)
        conn.commit()
