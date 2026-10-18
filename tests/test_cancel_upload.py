"""Cancelling a wrong upload, and detecting images that are not invoices."""
import io

import server
from tests.test_api import client, login  # noqa: F401  (reuse the isolated app fixture)

PNG = b"\x89PNG\r\n\x1a\nnot-an-invoice-photo"


def upload(client, data=PNG, name="photo.png"):
    return client.post("/api/uploads", files={"file": (name, io.BytesIO(data), "image/png")})


def test_cancel_allows_reupload_and_is_audited(client):
    login(client, "kobi", "9200000101")
    doc_id = upload(client).json()["document"]["id"]
    assert upload(client).status_code == 409  # same file twice is still a duplicate

    cancelled = client.delete(f"/api/documents/{doc_id}")
    assert cancelled.status_code == 200, cancelled.text
    doc = client.get(f"/api/documents/{doc_id}").json()["document"]
    assert doc["status"] == "reddedildi"
    assert any(flag["code"] == "user_cancelled" for flag in doc["flags"])

    assert upload(client).status_code == 200  # cancelled upload no longer blocks the same file

    client.post("/api/logout")
    login(client, "denetim", "denetim")
    actions = [row["action"] for row in client.get("/api/audit").json()]
    assert "upload_cancelled" in actions


def test_only_owner_can_cancel(client):
    login(client, "kobi", "9200000101")
    doc_id = upload(client, b"\x89PNG\r\n\x1a\nowner-file").json()["document"]["id"]
    client.post("/api/logout")
    login(client, "kobi", "9200000202")
    assert client.delete(f"/api/documents/{doc_id}").status_code == 404


def test_non_invoice_image_is_reported(client, monkeypatch):
    monkeypatch.setattr(server.gemma, "extract_invoice", lambda image, name: {
        "invoice_no": None, "total": None, "seller_vkn": None, "seller_name": None,
        "buyer_vkn": None, "buyer_name": None, "items": [],
    })
    login(client, "kobi", "9200000101")
    doc_id = upload(client, b"\x89PNG\r\n\x1a\nbaklava").json()["document"]["id"]
    result = client.post(f"/api/documents/{doc_id}/extract").json()
    assert result["not_invoice"] is True
    assert "fatura" in result["message"]
