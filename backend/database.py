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
            if not self.raw.in_transaction:
                self.raw.execute('BEGIN IMMEDIATE')
        else:
            self.raw.execute(f'SELECT id FROM {table} WHERE id=%s FOR UPDATE', (row_id,))

    def lock_for_invoice_number_generation(self) -> None:
        """Serialise generated invoice numbers until the creating transaction commits."""
        if self.dialect == 'sqlite':
            self.raw.execute('BEGIN IMMEDIATE')
        else:
            self.execute('SELECT pg_advisory_xact_lock(?)', (7282026,))

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
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, created_by TEXT
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
    created_at TEXT NOT NULL, recorded_by TEXT,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS invoice_history (
    id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL, event_type TEXT NOT NULL,
    description TEXT NOT NULL, amount NUMERIC(12,2), reference_id TEXT, created_at TEXT NOT NULL, actor_id TEXT,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS payment_submissions (
    id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL, amount NUMERIC(12,2) NOT NULL CHECK(amount > 0),
    payment_date TEXT NOT NULL, payment_method TEXT, reference TEXT,
    submitted_by TEXT NOT NULL, submitted_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','verified','rejected')),
    reviewed_by TEXT, reviewed_at TEXT, decision_note TEXT,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY, expense_date TEXT NOT NULL, category TEXT NOT NULL,
    description TEXT NOT NULL, amount NUMERIC(12,2) NOT NULL CHECK(amount > 0),
    reference TEXT, recorded_by TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'field_officer',
    customer_id TEXT UNIQUE REFERENCES customers(id) ON DELETE CASCADE,
    must_change_password INTEGER NOT NULL DEFAULT 0, token_version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS catalog_items (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    price NUMERIC(12,2) NOT NULL CHECK(price >= 0), active INTEGER NOT NULL DEFAULT 1,
    price_confirmed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoice_items (
    id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL, line_no INTEGER NOT NULL, kind TEXT NOT NULL,
    description TEXT NOT NULL, quantity NUMERIC(12,2) NOT NULL, unit_price NUMERIC(12,2) NOT NULL,
    line_total NUMERIC(12,2) NOT NULL,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_submissions_invoice_status ON payment_submissions(invoice_id,status);
CREATE INDEX IF NOT EXISTS idx_submissions_submitter ON payment_submissions(submitted_by,submitted_at);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_history_invoice ON invoice_history(invoice_id);
CREATE INDEX IF NOT EXISTS idx_history_created ON invoice_history(created_at)
'''


def init_db() -> None:
    with get_db() as conn:
        for statement in SCHEMA.split(';'):
            if statement.strip():
                conn.execute(statement)
        if conn.dialect == 'postgres':
            conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'field_officer'")
            conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE')
            conn.execute('ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS price_confirmed INTEGER NOT NULL DEFAULT 0')
            conn.execute('ALTER TABLE customers ADD COLUMN IF NOT EXISTS created_by TEXT')
            conn.execute('ALTER TABLE payments ADD COLUMN IF NOT EXISTS recorded_by TEXT')
            conn.execute('ALTER TABLE invoice_history ADD COLUMN IF NOT EXISTS actor_id TEXT')
            conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password INTEGER NOT NULL DEFAULT 0')
            conn.execute('ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0')
        else:
            user_columns = {row['name'] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
            if 'role' not in user_columns:
                conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'field_officer'")
            if 'customer_id' not in user_columns:
                conn.execute('ALTER TABLE users ADD COLUMN customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE')
            if 'must_change_password' not in user_columns:
                conn.execute('ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0')
            if 'token_version' not in user_columns:
                conn.execute('ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0')
            catalog_columns = {row['name'] for row in conn.execute('PRAGMA table_info(catalog_items)').fetchall()}
            if 'price_confirmed' not in catalog_columns:
                conn.execute('ALTER TABLE catalog_items ADD COLUMN price_confirmed INTEGER NOT NULL DEFAULT 0')
            customer_columns = {row['name'] for row in conn.execute('PRAGMA table_info(customers)').fetchall()}
            if 'created_by' not in customer_columns:
                conn.execute('ALTER TABLE customers ADD COLUMN created_by TEXT')
            payment_columns = {row['name'] for row in conn.execute('PRAGMA table_info(payments)').fetchall()}
            if 'recorded_by' not in payment_columns:
                conn.execute('ALTER TABLE payments ADD COLUMN recorded_by TEXT')
            history_columns = {row['name'] for row in conn.execute('PRAGMA table_info(invoice_history)').fetchall()}
            if 'actor_id' not in history_columns:
                conn.execute('ALTER TABLE invoice_history ADD COLUMN actor_id TEXT')
        conn.execute("UPDATE users SET role='administrator' WHERE role='admin'")
        conn.execute("UPDATE users SET role='field_officer' WHERE role='staff'")
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_customer ON users(customer_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_customers_created_by ON customers(created_by)')
        conn.commit()
