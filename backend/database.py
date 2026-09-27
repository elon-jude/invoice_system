import sqlite3
from datetime import datetime, timezone
from .config import DB_PATH


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    return conn


def init_db() -> None:
    conn = get_db()
    try:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT,
            tier INTEGER, tier_reason TEXT, requested_deposit REAL,
            first_deposit_amount REAL, expected_payment_days INTEGER,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
            invoice_number TEXT NOT NULL UNIQUE, total_amount REAL NOT NULL CHECK(total_amount > 0),
            due_date TEXT, status TEXT NOT NULL DEFAULT 'NO_PAYMENT',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL, amount REAL NOT NULL CHECK(amount > 0),
            payment_date TEXT NOT NULL, payment_method TEXT, reference TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS invoice_history (
            id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL, event_type TEXT NOT NULL,
            description TEXT NOT NULL, amount REAL, reference_id TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);
        CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
        CREATE INDEX IF NOT EXISTS idx_history_invoice ON invoice_history(invoice_id);
        CREATE INDEX IF NOT EXISTS idx_history_created ON invoice_history(created_at);
        ''')
        conn.commit()
    finally:
        conn.close()
