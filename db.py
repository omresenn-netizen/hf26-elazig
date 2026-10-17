"""SQLite helpers for local offers and accepted demo deals."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "vadesiz.db"


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT NOT NULL,
                financier_name TEXT NOT NULL,
                discount_rate REAL NOT NULL,
                net_amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT NOT NULL,
                offer_id INTEGER,
                transfer_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (offer_id) REFERENCES offers(id)
            );
            """
        )


def save_offer(invoice_no, financier_name, discount_rate, net_amount):
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO offers (invoice_no, financier_name, discount_rate, net_amount) VALUES (?, ?, ?, ?)",
            (invoice_no, financier_name, discount_rate, net_amount),
        )
        return cursor.lastrowid


def list_offers(invoice_no=None):
    with get_connection() as connection:
        if invoice_no is None:
            rows = connection.execute("SELECT * FROM offers ORDER BY created_at DESC").fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM offers WHERE invoice_no = ? ORDER BY created_at DESC",
                (invoice_no,),
            ).fetchall()
        return [dict(row) for row in rows]


def create_deal(invoice_no, offer_id, transfer_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO deals (invoice_no, offer_id, transfer_id) VALUES (?, ?, ?)",
            (invoice_no, offer_id, transfer_id),
        )
        if offer_id is not None:
            connection.execute("UPDATE offers SET status = 'accepted' WHERE id = ?", (offer_id,))
        return cursor.lastrowid
