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


def test_invoice_fingerprint_duplicate_stays_in_review(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "fingerprint.db")
    db.init_db()
    with db.get_connection() as connection:
        user = dict(connection.execute(
            "SELECT id, username, role, company_vkn FROM users WHERE role = 'kobi' LIMIT 1"
        ).fetchone())
    invoice = {
        "seller_vkn": user["company_vkn"],
        "invoice_no": "SAME-INVOICE",
        "total": 1200,
        "issue_date": "2026-10-01",
    }
    first_upload = db.create_upload(
        user, user["company_vkn"], "127.0.0.1", "", "first.png",
        b"\x89PNG\r\n\x1a\nfirst-image",
    )
    first = db.save_upload_extraction(
        first_upload["id"], user, "127.0.0.1", invoice, 0, []
    )
    second_upload = db.create_upload(
        user, user["company_vkn"], "127.0.0.1", "", "second.png",
        b"\x89PNG\r\n\x1a\nsecond-image",
    )
    second = db.save_upload_extraction(
        second_upload["id"], user, "127.0.0.1", invoice, 0, []
    )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["status"] == "incelemede"
    assert any(flag["code"] == "duplicate_invoice" for flag in second["flags"])
    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT status, risk_score FROM uploads WHERE id = ?",
            (second_upload["id"],),
        ).fetchone()
    assert row["status"] == "incelemede"
    assert row["risk_score"] >= 45


def test_financing_volume_includes_api_offer_deal(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "financing-volume.db")
    db.init_db()
    with db.get_connection() as connection:
        seller = connection.execute(
            "SELECT id, company_vkn FROM users WHERE role = 'kobi' LIMIT 1"
        ).fetchone()
        financier = connection.execute(
            "SELECT id FROM users WHERE role = 'finansor' LIMIT 1"
        ).fetchone()
        upload_id = connection.execute(
            """
            INSERT INTO uploads (
                user_id, company_vkn, ip_address, user_agent, file_name, file_size,
                file_sha256, invoice_no, status
            ) VALUES (?, ?, '127.0.0.1', '', 'invoice.png', 0, 'hash', 'API-VOLUME-1', 'finanse_edildi')
            """,
            (seller["id"], seller["company_vkn"]),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO offers (upload_id, financier_user_id, discount_rate, net_amount, status)
            VALUES (?, ?, 0.05, 950, 'kabul')
            """,
            (upload_id, financier["id"]),
        )
        connection.execute(
            "INSERT INTO deals (invoice_no, offer_id, transfer_id) VALUES ('API-VOLUME-1', NULL, 'DEMO-1')"
        )
    assert db.financing_volume() == 950
