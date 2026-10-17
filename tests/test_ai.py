import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import db
import server


@pytest.fixture
def ai_client(tmp_path, monkeypatch):
    source_root = Path(server.__file__).resolve().parent
    invoices = json.loads(
        (source_root / "data" / "invoices.json").read_text(encoding="utf-8")
    )
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "ai-test.db")
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(server.repo_api, "ROOT", tmp_path)
    monkeypatch.setattr(server.repo_api, "load_invoices", lambda: invoices)
    monkeypatch.setattr(server.repo_ai, "ROOT", tmp_path)
    server.repo_ai.clear_ai_cache()
    monkeypatch.setattr(server, "_RISK_REPORT_CACHE", {})
    monkeypatch.setattr(server.forecast, "forecast_delay", lambda buyer, amount, due: {
        "expected_days_late": 2.5,
        "late_probability": 0.1,
        "model": "TabPFN",
        "n_train": 10,
        "features": {},
    })
    monkeypatch.setattr(
        server.gemma,
        "extract_invoice",
        lambda image, name: {
            "invoice_no": "AI-TEST-001",
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
            "irsaliye_no": "IRS-AI-1",
            "buyer_approved": True,
        },
    )
    monkeypatch.setattr(
        server.gemma,
        "invoice_insight",
        lambda invoice, flags, buyer: {
            "summary": "Fatura tutarlı görünüyor.",
            "strengths": ["Alıcı onayı mevcut."],
            "concerns": [],
            "verdict": "uygun",
        },
    )
    monkeypatch.setattr(
        server.gemma,
        "payment_comment",
        lambda company, stats, history: "Ödeme geçmişi verisi sınırlı.",
    )
    insight_calls = []

    def offers_insight(invoice, offers):
        insight_calls.append(offers)
        return {
            "offers": [
                {"offer_id": offer["offer_id"], "comment": "Net ödeme tutarı uygun."}
                for offer in offers
            ],
            "recommendation": "Teklif 1",
            "reason": "Net tutarı daha yüksek.",
        }

    monkeypatch.setattr(server.gemma, "offers_insight", offers_insight)
    monkeypatch.setattr(
        server.gemma,
        "ai_digest",
        lambda role, context: {
            "bullets": ["Durum özeti.", "Önceliği inceleyin.", "Son tarihi takip edin."]
        },
    )
    monkeypatch.setattr(
        server.gemma,
        "compare_offers",
        lambda offers: {"recommendation": "Teklif 1", "reason": "Net tutarı yüksek."},
    )
    monkeypatch.setattr(
        server.gemma, "risk_report", lambda invoice, buyer: {"summary": "Düşük risk."}
    )
    monkeypatch.setattr(server.gemma, "suspicious_network_report", lambda graph: "Ağ özeti.")
    with TestClient(server.app) as test_client:
        yield test_client, insight_calls


def login(client, role, username):
    response = client.post(
        "/api/login",
        json={"role": role, "username": username, "password": "demo1234"},
    )
    assert response.status_code == 200, response.text
    return response.json()["user"]


def make_offered_invoice(client):
    login(client, "kobi", "9200000101")
    uploaded = client.post(
        "/api/uploads",
        files={
            "file": (
                "invoice.png",
                io.BytesIO(b"\x89PNG\r\n\x1a\nai-test-invoice"),
                "image/png",
            )
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["document"]["id"]
    extracted = client.post(f"/api/documents/{document_id}/extract")
    assert extracted.json()["model"] == "gemma4"
    assert extracted.json()["generated_at"]
    fields = extracted.json()["fields"]
    checked = client.post(f"/api/documents/{document_id}/check", json={"fields": fields})
    assert checked.status_code == 200, checked.text
    assert checked.json()["model"] == "gemma4"
    assert checked.json()["generated_at"]
    assert client.post(f"/api/documents/{document_id}/publish").status_code == 200
    client.post("/api/logout")
    login(client, "finansor", "anadolu_faktoring")
    offer = client.post(
        "/api/offers",
        json={"document_id": document_id, "net_amount": 1100, "note": "Hızlı teklif"},
    )
    assert offer.status_code == 200, offer.text
    client.post("/api/logout")
    login(client, "kobi", "9200000101")
    return document_id, offer.json()["offer"]


def test_ai_endpoints_return_contract_shapes_and_enforce_roles(ai_client):
    client, _ = ai_client
    document_id, offer = make_offered_invoice(client)

    insight = client.get(f"/api/documents/{document_id}/insight")
    assert insight.status_code == 200
    assert set(insight.json()) == {
        "summary", "strengths", "concerns", "verdict", "model", "generated_at"
    }
    assert insight.json()["model"] == "gemma4"

    payment = client.get("/api/companies/9100000011/payment-profile")
    assert payment.status_code == 200
    payment_body = payment.json()
    assert set(payment_body["company"]) == {
        "vkn", "name", "sector", "founded", "employees"
    }
    assert set(payment_body["stats"]) == {
        "invoice_count", "on_time_ratio", "avg_days_late", "max_days_late", "volume_12m"
    }
    assert isinstance(payment_body["history"], list)
    assert payment_body["ai_comment"]
    assert payment_body["model"] == "gemma4"
    assert payment_body["generated_at"]

    offers = client.get(f"/api/documents/{document_id}/offers-insight")
    assert offers.status_code == 200
    offers_body = offers.json()
    assert {
        "offers", "recommendation", "reason", "model", "generated_at"
    } <= set(offers_body)
    assert offers_body["offers"][0]["offer_id"] == offer["id"]
    assert offers_body["offers"][0]["annual_rate"] == pytest.approx(
        offer["discount_rate"] / max(
            client.get(f"/api/documents/{document_id}").json()["document"]["days_left"], 1
        ) * 365
    )
    assert offers_body["model"] == "gemma4"

    digest = client.get("/api/my/ai-digest")
    assert digest.status_code == 200
    assert 3 <= len(digest.json()["bullets"]) <= 5
    assert digest.json()["model"] == "gemma4"
    assert digest.json()["generated_at"]
    comparison = client.get(f"/api/documents/{document_id}/compare")
    assert comparison.status_code == 200
    assert comparison.json()["model"] == "gemma4"
    assert comparison.json()["generated_at"]

    report = client.get(f"/api/documents/{document_id}/risk-report")
    assert report.status_code == 403
    assert client.get(
        "/api/companies/9100000022/payment-profile"
    ).status_code == 404

    client.post("/api/logout")
    login(client, "finansor", "anadolu_faktoring")
    assert client.get(f"/api/documents/{document_id}/insight").status_code == 200
    assert client.get(f"/api/documents/{document_id}/offers-insight").status_code == 403
    assert client.get(
        "/api/companies/9100000011/payment-profile"
    ).status_code == 200
    assert client.get("/api/my/ai-digest").status_code == 200
    assert client.get(f"/api/documents/{document_id}/risk-report").json()["model"] == "gemma4"

    client.post("/api/logout")
    login(client, "denetim", "denetim")
    assert client.get(f"/api/documents/{document_id}/insight").status_code == 200
    assert client.get(
        "/api/companies/9100000011/payment-profile"
    ).status_code == 200
    assert client.get("/api/my/ai-digest").status_code == 200
    assert client.get(f"/api/documents/{document_id}/offers-insight").status_code == 403
    network_report = client.post("/api/network/report")
    assert network_report.status_code == 200
    assert network_report.json()["model"] == "gemma4"
    assert network_report.json()["generated_at"]


def test_ai_cache_tracks_changed_offer_contents(ai_client):
    client, insight_calls = ai_client
    document_id, original_offer = make_offered_invoice(client)
    first = client.get(f"/api/documents/{document_id}/offers-insight").json()
    cached = client.get(f"/api/documents/{document_id}/offers-insight").json()
    assert len(insight_calls) == 1
    assert first["generated_at"] == cached["generated_at"]

    client.post("/api/logout")
    login(client, "finansor", "anadolu_faktoring")
    updated = client.post(
        "/api/offers",
        json={"document_id": document_id, "net_amount": 1000, "note": "Güncel teklif"},
    )
    assert updated.status_code == 200, updated.text
    client.post("/api/logout")
    login(client, "kobi", "9200000101")
    changed = client.get(f"/api/documents/{document_id}/offers-insight").json()
    assert len(insight_calls) == 2
    assert changed["offers"][0]["net_amount"] != original_offer["net_amount"]


def test_notifications_exclude_email_channel(ai_client):
    client, _ = ai_client
    make_offered_invoice(client)
    notifications = client.get("/api/notifications")
    assert notifications.status_code == 200
    assert len(notifications.json()) == 1


def test_payment_history_json_fallback(tmp_path, monkeypatch):
    history_dir = tmp_path / "data"
    history_dir.mkdir()
    (history_dir / "payment_history.json").write_text(
        json.dumps([
            {
                "company_vkn": "9100000011",
                "invoice_no": "OLD",
                "due_date": "2025-05-01",
                "paid_date": "2025-05-03",
                "amount": 100,
                "days_late": 2,
            },
            {
                "company_vkn": "9100000011",
                "invoice_no": "NEW",
                "due_date": "2026-09-01",
                "paid_date": "2026-09-01",
                "amount": 300,
                "days_late": 0,
            },
            {
                "company_vkn": "9100000022",
                "invoice_no": "OTHER",
                "due_date": "2026-09-01",
                "paid_date": "2026-09-06",
                "amount": 900,
                "days_late": 5,
            },
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(server.repo_ai, "ROOT", tmp_path)
    monkeypatch.setattr(server.repo_ai.db, "get_payment_history", None, raising=False)
    monkeypatch.setattr(server.repo_ai.db, "payment_stats", None, raising=False)

    assert [row["invoice_no"] for row in server.repo_ai.get_payment_history(
        "9100000011", limit=1
    )] == ["NEW"]
    stats = server.repo_ai.payment_stats("9100000011")
    assert stats["invoice_count"] == 2
    assert stats["on_time_ratio"] == 0.5
    assert stats["max_days_late"] == 2
