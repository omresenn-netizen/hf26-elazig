import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import db
import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    source_root = Path(server.__file__).resolve().parent
    invoices = json.loads((source_root / "data" / "invoices.json").read_text(encoding="utf-8"))
    demo_uploads = json.loads((source_root / "data" / "demo_uploads.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(server.repo_api, "ROOT", tmp_path)
    monkeypatch.setattr(server.repo_api, "DEMO_UPLOAD_NUMBERS", {item["invoice_no"] for item in demo_uploads})
    monkeypatch.setattr(server.repo_api, "COMPANIES", [
        {"vkn": "9200000101", "name": "Hazar Tekstil Atölyesi Ltd. Şti.", "sector": "tekstil", "employees": 18, "founded": 2015, "address": "Elazığ", "type": "sme"},
        {"vkn": "9100000011", "name": "Anadolu Market Zinciri A.Ş.", "sector": "perakende", "employees": 4200, "founded": 1998, "address": "Merkez", "type": "buyer"},
    ])
    monkeypatch.setattr(server.repo_api, "COMPANY_BY_VKN", {
        item["vkn"]: item for item in server.repo_api.COMPANIES
    })
    monkeypatch.setattr(server.repo_api, "load_invoices", lambda: invoices)
    monkeypatch.setattr(server.gemma, "extract_invoice", lambda image, name: {
        "invoice_no": "API-TEST-001",
        "issue_date": "2026-10-01",
        "due_date": "2026-12-01",
        "seller_vkn": "9200000101",
        "seller_name": "Hazar Tekstil Atölyesi Ltd. Şti.",
        "buyer_vkn": "9100000011",
        "buyer_name": "Anadolu Market Zinciri A.Ş.",
        "items": [{"description": "kumaş", "unit": "metre", "quantity": 10, "unit_price": 100}],
        "subtotal": 1000,
        "kdv": 200,
        "total": 1200,
        "irsaliye_no": "IRS-1",
        "buyer_approved": True,
    })
    monkeypatch.setattr(server.gemma, "explain_flags", lambda invoice, flags: "İnsan incelemesi gerekir.")
    monkeypatch.setattr(server.gemma, "compare_offers", lambda offers: {"recommendation": "Teklif 1", "reason": "En yüksek net tutar."})
    monkeypatch.setattr(server.gemma, "risk_report", lambda invoice, buyer: {"summary": "Düşük risk."})
    monkeypatch.setattr(server.gemma, "suspicious_network_report", lambda graph: "Ağ raporu.")
    monkeypatch.setattr(server, "_RISK_REPORT_CACHE", {})
    with TestClient(server.app) as test_client:
        yield test_client


def login(client, role, username):
    response = client.post("/api/login", json={
        "role": role, "username": username, "password": "demo1234",
    })
    assert response.status_code == 200, response.text
    return response.json()["user"]


def test_login_for_each_role(client):
    for role, username in (
        ("kobi", "9200000101"),
        ("finansor", "anadolu_faktoring"),
        ("denetim", "denetim"),
    ):
        client.post("/api/logout")
        user = login(client, role, username)
        assert user["role"] == role
        assert "password_hash" not in user


def test_upload_and_duplicate_conflict(client, tmp_path):
    login(client, "kobi", "9200000101")
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"valid-demo-image"
    first = client.post(
        "/api/uploads",
        files={"file": ("invoice.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert first.status_code == 200, first.text
    doc = first.json()["document"]
    assert doc["file"]["sha256"]
    assert doc["status"] == "incelemede"
    duplicate = client.post(
        "/api/uploads",
        files={"file": ("another.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]


def test_market_contains_preloaded_invoices(client):
    login(client, "finansor", "anadolu_faktoring")
    response = client.get("/api/market")
    assert response.status_code == 200
    assert any(item["id"].startswith("INV-") for item in response.json())


def test_offer_creates_panel_and_email_notifications(client):
    login(client, "kobi", "9200000101")
    upload = client.post(
        "/api/uploads",
        files={"file": ("invoice.png", io.BytesIO(b"\x89PNG\r\n\x1a\napi-image"), "image/png")},
    )
    document_id = upload.json()["document"]["id"]
    extracted = client.post(f"/api/documents/{document_id}/extract")
    assert extracted.status_code == 200
    checked = client.post(f"/api/documents/{document_id}/check", json={"fields": extracted.json()["fields"]})
    assert checked.status_code == 200
    assert client.post(f"/api/documents/{document_id}/publish").status_code == 200

    client.post("/api/logout")
    login(client, "finansor", "anadolu_faktoring")
    offer = client.post("/api/offers", json={
        "document_id": document_id, "net_amount": 1100, "note": "Hızlı teklif",
    })
    assert offer.status_code == 200, offer.text
    client.post("/api/logout")
    login(client, "kobi", "9200000101")
    notifications = client.get("/api/notifications").json()
    assert {item["subject"] for item in notifications} == {"Faturanız için yeni finansman teklifi"}
    assert len(notifications) == 2


def test_accept_offer_finances_document(client):
    login(client, "kobi", "9200000101")
    upload = client.post(
        "/api/uploads",
        files={"file": ("invoice.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfinance-image"), "image/png")},
    )
    document_id = upload.json()["document"]["id"]
    fields = client.post(f"/api/documents/{document_id}/extract").json()["fields"]
    assert client.post(f"/api/documents/{document_id}/check", json={"fields": fields}).status_code == 200
    assert client.post(f"/api/documents/{document_id}/publish").status_code == 200
    client.post("/api/logout")
    login(client, "finansor", "anadolu_faktoring")
    created = client.post("/api/offers", json={"document_id": document_id, "net_amount": 1100})
    offer_id = created.json()["offer"]["id"]
    client.post("/api/logout")
    login(client, "kobi", "9200000101")
    accepted = client.post(f"/api/offers/{offer_id}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["document"]["status"] == "finanse_edildi"
    assert accepted.json()["receipt"]["simulated"] is True
    assert accepted.json()["receipt"]["mock"] is True


def test_preloaded_market_invoice_can_receive_offer(client):
    login(client, "finansor", "anadolu_faktoring")
    documents = client.get("/api/market").json()
    document = next(item for item in documents if item["id"] == "INV-001")
    offer = client.post("/api/offers", json={
        "document_id": document["id"],
        "net_amount": round(document["total"] * 0.9, 2),
    })
    assert offer.status_code == 200, offer.text
    assert offer.json()["offer"]["document_id"] == "INV-001"

    client.post("/api/logout")
    login(client, "kobi", document["seller"]["vkn"])
    detail = client.get(f"/api/documents/{document['id']}")
    assert detail.status_code == 200
    assert len(detail.json()["offers"]) == 1
    accepted = client.post(f"/api/offers/{offer.json()['offer']['id']}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["document"]["status"] == "finanse_edildi"


def test_demo_sample_is_not_a_first_upload_duplicate(client, monkeypatch):
    source_root = Path(server.__file__).resolve().parent
    invoices = json.loads((source_root / "data" / "invoices.json").read_text(encoding="utf-8"))
    demo_uploads = json.loads((source_root / "data" / "demo_uploads.json").read_text(encoding="utf-8"))
    sample_number = demo_uploads[0]["invoice_no"]
    sample_invoice = next(item for item in invoices if item["invoice_no"] == sample_number)
    monkeypatch.setattr(server.gemma, "extract_invoice", lambda image, name: sample_invoice)
    login(client, "kobi", sample_invoice["seller_vkn"])

    first_upload = client.post(
        "/api/uploads",
        files={"file": ("first.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfirst"), "image/png")},
    ).json()["document"]["id"]
    fields = client.post(f"/api/documents/{first_upload}/extract").json()["fields"]
    checked = client.post(f"/api/documents/{first_upload}/check", json={"fields": fields})
    assert checked.status_code == 200, checked.text
    assert not any(flag["code"] == "duplicate_invoice" for flag in checked.json()["document"]["flags"])

    second_upload = client.post(
        "/api/uploads",
        files={"file": ("second.png", io.BytesIO(b"\x89PNG\r\n\x1a\nsecond"), "image/png")},
    ).json()["document"]["id"]
    fields = client.post(f"/api/documents/{second_upload}/extract").json()["fields"]
    duplicate = client.post(f"/api/documents/{second_upload}/check", json={"fields": fields})
    assert duplicate.status_code == 409
