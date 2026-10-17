import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import db
import pytest


def test_payment_stats_and_history_order(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "stats.db")
    db.init_db()
    today = date.today()
    recent_due = (today - timedelta(days=30)).isoformat()
    old_due = (today - timedelta(days=400)).isoformat()
    with db.get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO payment_history (
                company_vkn, invoice_no, counterparty_vkn, amount,
                due_date, paid_date, days_late
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("test-vkn", "INV-1", "buyer-1", 100.0, recent_due, recent_due, 0),
                ("test-vkn", "INV-2", "buyer-2", 200.0, recent_due, recent_due, 5),
                ("test-vkn", "INV-3", "buyer-3", 300.0, old_due, old_due, -1),
            ],
        )

    assert db.payment_stats("test-vkn") == {
        "invoice_count": 3,
        "on_time_ratio": 2 / 3,
        "avg_days_late": 1.33,
        "max_days_late": 5,
        "volume_12m": 300.0,
    }
    history = db.get_payment_history("test-vkn", limit=2)
    assert [item["invoice_no"] for item in history] == ["INV-2", "INV-1"]
    assert db.get_payment_history("missing") == []


def test_audit_log_is_append_only(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "audit.db")
    db.init_db()
    db.log_audit("test_action", {"username": "tester"})

    with db.get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE audit_log SET action = 'changed'")
    with db.get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM audit_log")


def test_payment_history_seeding_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seed.db")
    db.init_db()
    with db.get_connection() as connection:
        count_before = connection.execute(
            "SELECT COUNT(*) FROM payment_history"
        ).fetchone()[0]
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"

    db.init_db()
    with db.get_connection() as connection:
        count_after = connection.execute(
            "SELECT COUNT(*) FROM payment_history"
        ).fetchone()[0]
    records = json.loads(
        (Path(db.__file__).resolve().parent / "data" / "payment_history.json")
        .read_text(encoding="utf-8")
    )
    assert count_before == count_after == len(records)


def test_existing_audit_rows_and_legacy_offers_survive_migration(monkeypatch, tmp_path):
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            username TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            action TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{}'
        );
        INSERT INTO audit_log (username, ip_address, action)
        VALUES ('legacy-user', '127.0.0.1', 'legacy_action');
        CREATE TABLE offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL,
            financier_name TEXT NOT NULL,
            discount_rate REAL NOT NULL,
            net_amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO offers (invoice_no, financier_name, discount_rate, net_amount)
        VALUES ('LEGACY-1', 'Legacy financier', 0.05, 950.0);
        """
    )
    connection.close()
    monkeypatch.setattr(db, "DB_PATH", database)

    db.init_db()

    with db.get_connection() as connection:
        assert connection.execute(
            "SELECT action FROM audit_log WHERE username = 'legacy-user'"
        ).fetchone()[0] == "legacy_action"
        assert connection.execute(
            "SELECT invoice_no FROM legacy_offers WHERE invoice_no = 'LEGACY-1'"
        ).fetchone()[0] == "LEGACY-1"
