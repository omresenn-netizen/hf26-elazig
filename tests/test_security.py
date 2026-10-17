import hashlib
from pathlib import Path

import db
import repo_kobi
import views.kobi as kobi


def test_password_hash_uses_pbkdf2_with_salt(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "security.db")
    db.init_db()
    salt = "A" * 32
    expected = hashlib.pbkdf2_hmac(
        "sha256",
        b"demo1234",
        bytes.fromhex(salt),
        db.PASSWORD_ITERATIONS,
    ).hex()
    assert db.PASSWORD_ITERATIONS >= 200000
    assert db._password_hash("demo1234", salt) == expected


def test_account_lockout_after_repeated_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "lockout.db")
    db.init_db()
    username = "lockme"
    salt = "B" * 32
    password_hash = db._password_hash("CorrectPass123", salt)
    with db.get_connection() as connection:
        connection.execute(
            "INSERT INTO users (username, password_hash, salt, role, company_vkn, display_name, email, failed_login_attempts, login_locked_until) VALUES (?, ?, ?, 'kobi', 'VKN-1', 'Lock Me', 'lock@example.com', 0, NULL)",
            (username, password_hash, salt),
        )

    for _ in range(db.MAX_LOGIN_ATTEMPTS - 1):
        assert db.authenticate_user(username, "wrong", "kobi") is None

    assert db.authenticate_user(username, "wrong", "kobi") is None
    assert db.authenticate_user(username, "CorrectPass123", "kobi") is None

    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT failed_login_attempts, login_locked_until FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        assert row[0] >= db.MAX_LOGIN_ATTEMPTS
        assert row[1] is not None


def test_magic_byte_validation_for_uploads():
    sample_bytes = (Path(__file__).resolve().parents[1] / "samples" / "01_gercek_icecek.png").read_bytes()
    assert kobi._file_type_error(type("Upload", (), {"name": "invoice.png"})(), sample_bytes) is None
    assert "eşleşmiyor" in kobi._file_type_error(type("Upload", (), {"name": "invoice.png"})(), b"NOTPNG")


def test_duplicate_hash_is_recorded(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "duplicate.db")
    db.init_db()
    user = {"id": 1, "username": "dup-user", "company_vkn": "VKN-9", "role": "kobi"}
    bytes_payload = b"\x89PNG\r\n\x1a\nclient-image"
    first = db.create_upload(user, "VKN-9", "127.0.0.1", "pytest", "invoice.png", bytes_payload)
    second = db.create_upload(user, "VKN-9", "127.0.0.1", "pytest", "invoice-copy.png", bytes_payload)
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["file_sha256"] == first["file_sha256"]


def test_streamlit_invoice_duplicate_remains_in_review(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "streamlit-duplicate.db")
    db.init_db()
    with db.get_connection() as connection:
        user = dict(connection.execute(
            "SELECT id, username, role, company_vkn FROM users WHERE role = 'kobi' LIMIT 1"
        ).fetchone())
    invoice = {
        "invoice_no": "STREAMLIT-DUP-1",
        "issue_date": "2026-10-01",
        "due_date": "2026-12-01",
        "seller_vkn": user["company_vkn"],
        "seller_name": "Test seller",
        "buyer_vkn": "9100000011",
        "buyer_name": "Test buyer",
        "items": [{"description": "kumaş", "unit": "metre", "quantity": 10, "unit_price": 100}],
        "subtotal": 1000,
        "kdv": 200,
        "total": 1200,
        "irsaliye_no": "IRS-TEST-1",
        "buyer_approved": True,
    }
    first_upload = db.create_upload(
        user, user["company_vkn"], "127.0.0.1", "", "first.png",
        b"\x89PNG\r\n\x1a\nfirst",
    )
    kobi._run_invoice_checks(
        invoice, [], [], first_upload["id"], user, "127.0.0.1"
    )
    second_upload = db.create_upload(
        user, user["company_vkn"], "127.0.0.1", "", "second.png",
        b"\x89PNG\r\n\x1a\nsecond",
    )

    result = kobi._run_invoice_checks(
        invoice, [], [], second_upload["id"], user, "127.0.0.1"
    )

    assert result["status"] == "incelemede"
    assert any(flag["code"] == "duplicate_invoice" for flag in result["flags"])
    assert repo_kobi.open_financing(
        user, "127.0.0.1", second_upload["id"], result["score"]
    ) == "incelemede"
