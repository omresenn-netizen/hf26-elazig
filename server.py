"""FastAPI backend for the VadeX web client."""
import csv
import io
import json
import math
import os
import re
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import db
import fraud
import gemma
import mocks
import repo_api
import repo_ai

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"
WEB = ROOT / "web"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
_RISK_REPORT_CACHE = {}


@asynccontextmanager
async def lifespan(application):
    db.init_db()
    UPLOADS.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="VadeX API", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("VADEX_SECRET") or secrets.token_urlsafe(48),
    same_site="lax",
    https_only=os.environ.get("VADEX_COOKIE_SECURE", "").lower() == "true",
)


@app.exception_handler(RuntimeError)
async def service_runtime_error(request, exc):
    return Response(
        content=json.dumps({"error": str(exc)}, ensure_ascii=False),
        status_code=502,
        media_type="application/json",
    )


@app.exception_handler(StarletteHTTPException)
async def json_http_error(request, exc):
    return Response(
        content=json.dumps({"error": str(exc.detail)}, ensure_ascii=False),
        status_code=exc.status_code,
        media_type="application/json",
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def json_validation_error(request, exc):
    return Response(
        content=json.dumps({"error": "İstek verileri geçersiz."}, ensure_ascii=False),
        status_code=422,
        media_type="application/json",
    )


def session_user(request):
    user = request.session.get("user")
    if not isinstance(user, dict) or user.get("role") not in {"kobi", "finansor", "denetim"}:
        raise HTTPException(401, "Oturum açmanız gerekiyor.")
    return user


def require_role(user, *roles):
    if user["role"] not in roles:
        raise HTTPException(403, "Bu işlem için yetkiniz yok.")
    return user


def ai_metadata():
    return {
        "model": gemma.MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def annual_rate(discount_rate, days_left):
    days = max(days_left if isinstance(days_left, int) else 1, 1)
    return float(discount_rate or 0) / days * 365


def normalize_document_annual_rate(document):
    if not document:
        return document
    best_offer = document.get("best_offer")
    if best_offer:
        best_offer["annual_rate"] = annual_rate(
            best_offer.get("discount_rate"), document.get("days_left")
        )
    return document


def document_or_404(document_id):
    document = repo_api.make_document(document_id)
    if not document:
        raise HTTPException(404, "Fatura bulunamadı.")
    return normalize_document_annual_rate(document)


def upload_id_from(document_id):
    if not document_id.startswith("U-"):
        return None
    try:
        return int(document_id[2:])
    except ValueError:
        raise HTTPException(404, "Fatura bulunamadı.")


def user_can_view_document(user, document_id, document=None):
    document = document or document_or_404(document_id)
    if user["role"] == "kobi":
        upload_id = upload_id_from(document_id)
        if upload_id is None:
            upload_id = repo_api.preloaded_upload_id(document_id)
        if upload_id is None or repo_api.upload_owner(upload_id) != user["id"]:
            raise HTTPException(404, "Fatura bulunamadı.")
    elif user["role"] == "finansor":
        if document["status"] not in {"teklif_bekliyor", "teklif_var"}:
            raise HTTPException(404, "Fatura bulunamadı.")
    return document


def document_invoice(document_id):
    if document_id.startswith("U-"):
        upload_id = upload_id_from(document_id)
        row = repo_api.upload_row(upload_id)
        return repo_api.invoice_for_row(row or {})
    invoice = next((item for item in repo_api.load_invoices() if item.get("id") == document_id), None)
    return invoice or {}


def serialize_offers(document_id):
    upload_id = upload_id_from(document_id)
    if upload_id is None:
        upload_id = repo_api.preloaded_upload_id(document_id)
    if not upload_id:
        return []
    document = repo_api.make_document(document_id) or {}
    days_left = document.get("days_left")
    return [
        {
            **offer,
            "annual_rate": annual_rate(offer.get("discount_rate"), days_left),
        }
        for offer in repo_api.offer_objects(upload_id)
    ]


def validate_fields(invoice, user):
    if not isinstance(invoice, dict):
        raise HTTPException(400, "Fatura alanları nesne olmalıdır.")
    seller_vkn = str(invoice.get("seller_vkn") or "").strip()
    if not seller_vkn:
        raise HTTPException(400, "Satıcı VKN alanı gereklidir.")
    if user.get("company_vkn") and seller_vkn != user["company_vkn"]:
        raise HTTPException(403, "Yalnızca şirketinize ait faturaları kontrol edebilirsiniz.")
    for field in ("invoice_no", "issue_date", "due_date"):
        if not str(invoice.get(field) or "").strip():
            raise HTTPException(400, f"{field} alanı gereklidir.")
    try:
        issue_date = date.fromisoformat(str(invoice["issue_date"])[:10])
        due_date = date.fromisoformat(str(invoice["due_date"])[:10])
    except ValueError:
        raise HTTPException(400, "Fatura tarihleri YYYY-MM-DD biçiminde olmalıdır.")
    if due_date < issue_date:
        raise HTTPException(400, "Vade tarihi fatura tarihinden önce olamaz.")
    total = fraud._number(invoice.get("total", invoice.get("amount")))
    if total is None or not math.isfinite(total) or total <= 0:
        raise HTTPException(400, "Fatura toplamı sıfırdan büyük geçerli bir tutar olmalıdır.")
    invoice["total"] = total
    for field in ("subtotal", "kdv"):
        if invoice.get(field) is not None:
            amount = fraud._number(invoice[field])
            if amount is None or not math.isfinite(amount) or amount < 0:
                raise HTTPException(400, "Fatura ara toplamı ve KDV geçerli tutarlar olmalıdır.")
            invoice[field] = amount
    if not isinstance(invoice.get("items", []), list):
        raise HTTPException(400, "Fatura kalemleri liste biçiminde olmalıdır.")
    if any(not isinstance(item, dict) for item in invoice.get("items", [])):
        raise HTTPException(400, "Her fatura kalemi nesne biçiminde olmalıdır.")
    return invoice


def mock_invoice_list():
    return repo_api.load_invoices()


@app.post("/api/login")
def login(payload: dict, request: Request):
    role = payload.get("role")
    if not isinstance(role, str) or role not in {"kobi", "finansor", "denetim"}:
        raise HTTPException(400, "Geçersiz kullanıcı rolü.")
    username = payload.get("username", "")
    password = payload.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str) or len(password) > 256:
        raise HTTPException(400, "Kullanıcı adı veya parola biçimi geçersiz.")
    user = repo_api.authenticate(
        username,
        password,
        role,
        request.client.host if request.client else "127.0.0.1",
        request.headers.get("user-agent", ""),
    )
    if not user:
        raise HTTPException(401, "Kullanıcı adı, parola veya rol hatalı.")
    request.session.clear()
    request.session["user"] = user
    return {"user": user}


@app.post("/api/logout")
def logout(request: Request):
    user = session_user(request)
    repo_api.audit("logout", user, request)
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    return {"user": session_user(request)}


@app.get("/api/demo-accounts")
def demo_accounts():
    users = db.list_users()
    return [
        {
            "role": role,
            "accounts": [
                {"username": user["username"], "display_name": user["display_name"]}
                for user in users if user["role"] == role
            ],
        }
        for role in ("kobi", "finansor", "denetim")
    ]


@app.post("/api/uploads")
async def upload_invoice(request: Request, file: UploadFile = File(...)):
    user = require_role(session_user(request), "kobi")
    file_name = Path(file.filename or "").name
    suffix = Path(file_name).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".pdf"}:
        raise HTTPException(400, "Yalnızca PNG, JPG veya PDF dosyası yükleyebilirsiniz.")
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "Dosya boyutu 10 MB sınırını aşamaz.")
    signatures = {
        ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
        ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
        ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
        ".pdf": (b"%PDF-", "application/pdf"),
    }
    signature, mime = signatures[suffix]
    if not content.startswith(signature):
        raise HTTPException(400, "Dosya içeriği uzantısıyla uyuşmuyor.")
    if file.content_type and file.content_type not in {mime, "application/octet-stream"}:
        raise HTTPException(400, "Dosya türü geçersiz.")
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    result = repo_api.create_upload(user, request, file_name, content, stored_name)
    if result["duplicate"]:
        raise HTTPException(409, "Bu dosya daha önce yüklenmiş.")
    try:
        (UPLOADS / stored_name).write_bytes(content)
    except OSError as exc:
        with db.get_connection() as connection:
            connection.execute("DELETE FROM uploads WHERE id = ?", (result["id"],))
            connection.execute(
                "DELETE FROM audit_log WHERE action = 'upload' AND json_extract(detail_json, '$.upload_id') = ?",
                (result["id"],),
            )
        raise HTTPException(500, "Dosya güvenli biçimde kaydedilemedi.") from exc
    return {"document": document_or_404(f"U-{result['id']}")}


@app.post("/api/documents/{document_id}/extract")
def extract_document(document_id: str, request: Request):
    user = require_role(session_user(request), "kobi")
    upload_id = upload_id_from(document_id)
    if upload_id is None or repo_api.upload_owner(upload_id) != user["id"]:
        raise HTTPException(404, "Fatura bulunamadı.")
    path = repo_api.file_path(upload_id)
    if not path:
        raise HTTPException(404, "Yüklenen fatura dosyası bulunamadı.")
    fields = gemma.extract_invoice(path.read_bytes(), path.name)
    if not isinstance(fields, dict):
        return {"fields": fields, **ai_metadata()}
    corrections = _reconcile_parties(fields)
    if corrections:
        fields["corrections"] = corrections
    try:
        repo_api.save_pending_extraction(upload_id, user, request, fields)
    except ValueError as exc:
        raise HTTPException(409, "Fatura artık okunabilir durumda değil.") from exc
    return {"fields": fields, **ai_metadata()}


def _reconcile_parties(fields):
    """Fix OCR slips in VKNs (e.g. a dropped zero) by matching the party name against the registry."""
    corrections = []
    for side in ("seller", "buyer"):
        vkn = re.sub(r"\D", "", str(fields.get(f"{side}_vkn") or ""))
        name = str(fields.get(f"{side}_name") or "").casefold().strip()
        if len(vkn) == 10 and vkn in repo_api.COMPANY_BY_VKN:
            fields[f"{side}_vkn"] = vkn
            continue
        match = next((c for c in repo_api.COMPANY_BY_VKN.values()
                      if name and str(c.get("name", "")).casefold() == name), None)
        if match:
            corrections.append({
                "field": f"{side}_vkn", "read": fields.get(f"{side}_vkn"), "corrected": match["vkn"],
                "reason": "Okunan VKN kayıtlı değil veya 10 hane değil; firma unvanıyla eşleştirildi.",
            })
            fields[f"{side}_vkn"] = match["vkn"]
    return corrections


@app.post("/api/documents/{document_id}/check")
def check_document(document_id: str, payload: dict, request: Request):
    user = require_role(session_user(request), "kobi")
    upload_id = upload_id_from(document_id)
    row = repo_api.upload_row(upload_id or -1)
    if upload_id is None or not row or row["user_id"] != user["id"]:
        raise HTTPException(404, "Fatura bulunamadı.")
    if row["status"] != "incelemede":
        raise HTTPException(409, "Teklif verilmiş veya finanse edilmiş fatura yeniden kontrol edilemez.")
    with db.get_connection() as connection:
        active_offer = connection.execute(
            "SELECT 1 FROM offers WHERE upload_id = ? AND status = 'beklemede' LIMIT 1",
            (upload_id,),
        ).fetchone()
    if active_offer:
        raise HTTPException(409, "Aktif teklif bulunan fatura yeniden kontrol edilemez.")
    invoice = validate_fields(payload.get("fields"), user)
    companies = repo_api.COMPANIES
    invoices = mock_invoice_list()
    existing_invoices = [
        repo_api.invoice_for_row(row)
        for row in repo_api.all_upload_rows()
        if row["id"] != upload_id and row.get("extracted_json")
    ]
    fraud_invoices = [*invoices, *existing_invoices]
    flags = fraud.analyze_invoice(invoice, companies, [*fraud_invoices, invoice])
    if invoice.get("invoice_no") in repo_api.DEMO_UPLOAD_NUMBERS:
        flags = [flag for flag in flags if flag.get("code") != "duplicate_invoice"]
    score = fraud.risk_score(flags)
    gib_result = mocks.verify_invoice(invoice, invoices)
    buyer_result = mocks.buyer_credit_score(invoice.get("buyer_vkn"))
    result = repo_api.save_extraction(upload_id, user, request, invoice, score, flags)
    if result["duplicate"]:
        raise HTTPException(409, "Bu fatura daha önce yüklenmiş.")
    explanation = gemma.explain_flags(invoice, result["flags"])
    repo_api.audit("invoice_checked", user, request, {"upload_id": upload_id, "risk_score": score})
    document = document_or_404(document_id)
    document["buyer"]["credit_score"] = buyer_result["score"]
    document["steps"][2]["detail"] = "Doğrulandı" if gib_result["verified"] else "Kayıt demo verisinde bulunamadı"
    document["steps"][4]["detail"] = f"Skor {buyer_result['score']} — DEMO / MOCK"
    return {
        "document": document,
        "explanation": explanation,
        **ai_metadata(),
        "services": {
            "gib": {**gib_result, "mock": True},
            "buyer": {**buyer_result, "mock": True},
        },
    }


@app.post("/api/documents/{document_id}/publish")
def publish_document(document_id: str, request: Request):
    user = require_role(session_user(request), "kobi")
    upload_id = upload_id_from(document_id)
    row = repo_api.upload_row(upload_id or -1)
    if not row or row["user_id"] != user["id"]:
        raise HTTPException(404, "Fatura bulunamadı.")
    if row["status"] != "incelemede":
        raise HTTPException(409, "Teklif verilmiş veya finanse edilmiş fatura açılamaz.")
    with db.get_connection() as connection:
        active_offer = connection.execute(
            "SELECT 1 FROM offers WHERE upload_id = ? AND status = 'beklemede' LIMIT 1",
            (upload_id,),
        ).fetchone()
    if active_offer:
        raise HTTPException(409, "Aktif teklif bulunan fatura yeniden yayımlanamaz.")
    if row["risk_score"] is None:
        raise HTTPException(400, "Finansmana açmadan önce faturayı kontrol edin.")
    with db.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT status, risk_score FROM uploads WHERE id = ? AND user_id = ?",
            (upload_id, user["id"]),
        ).fetchone()
        active_offer = connection.execute(
            "SELECT 1 FROM offers WHERE upload_id = ? AND status = 'beklemede' LIMIT 1",
            (upload_id,),
        ).fetchone()
        if not current or current["status"] != "incelemede" or current["risk_score"] is None or active_offer:
            raise HTTPException(409, "Fatura finansmana açılamıyor.")
        status = "teklif_bekliyor" if current["risk_score"] < 60 else "incelemede"
        connection.execute(
            "UPDATE uploads SET status = ? WHERE id = ? AND status = 'incelemede'",
            (status, upload_id),
        )
        db._write_audit(
            connection, user["username"], request.client.host if request.client else "127.0.0.1",
            "document_published", user_id=user["id"],
            detail={"upload_id": upload_id, "status": status, "user_agent": request.headers.get("user-agent", "")},
        )
    return {"document": document_or_404(document_id)}


@app.get("/api/my/documents")
def my_documents(request: Request):
    user = require_role(session_user(request), "kobi")
    rows = repo_api.all_upload_rows()
    return [
        doc for row in rows if row["user_id"] == user["id"]
        if (doc := document_or_404(f"U-{row['id']}"))
    ]


@app.get("/api/documents/{document_id}")
def get_document(document_id: str, request: Request):
    user = session_user(request)
    document = user_can_view_document(user, document_id)
    return {"document": document, "offers": serialize_offers(document_id)}


@app.get("/api/documents/{document_id}/compare")
def compare_document_offers(document_id: str, request: Request):
    user = require_role(session_user(request), "kobi")
    document = user_can_view_document(user, document_id)
    offers = serialize_offers(document_id)
    invoice = document_invoice(document_id)

    def generate():
        result = gemma.compare_offers(offers)
        if isinstance(result, dict):
            return {
                "recommendation": result.get("recommendation", ""),
                "reason": result.get("reason", ""),
            }
        return {"recommendation": "", "reason": str(result)}

    return repo_ai.cached_ai_result(
        "compare_offers",
        document_id,
        {"invoice": invoice, "offers": offers},
        generate,
    )


@app.post("/api/offers/{offer_id}/accept")
def accept_offer(offer_id: int, request: Request):
    user = require_role(session_user(request), "kobi")
    offer = repo_api.get_offer(offer_id)
    if not offer or offer["company_vkn"] != user.get("company_vkn"):
        raise HTTPException(404, "Teklif bulunamadı.")
    if offer["status"] != "beklemede" or offer["document_status"] == "finanse_edildi":
        raise HTTPException(409, "Bu teklif artık kabul edilemez.")
    invoice = repo_api.invoice_for_row(offer)
    receipt = {
        **mocks.bank_transfer(offer["invoice_no"] or invoice.get("invoice_no"), offer["net_amount"]),
        "mock": True,
    }
    upload_id = offer["upload_id"]
    with db.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT status, company_vkn FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        current_offer = connection.execute(
            "SELECT status FROM offers WHERE id = ?", (offer_id,)
        ).fetchone()
        if not current or current["company_vkn"] != user.get("company_vkn"):
            raise HTTPException(404, "Teklif bulunamadı.")
        if current["status"] == "finanse_edildi" or not current_offer or current_offer["status"] != "beklemede":
            raise HTTPException(409, "Bu teklif artık kabul edilemez.")
        connection.execute("UPDATE uploads SET status = 'finanse_edildi' WHERE id = ?", (upload_id,))
        connection.execute(
            "UPDATE offers SET status = CASE WHEN id = ? THEN 'kabul' ELSE 'red' END WHERE upload_id = ? AND status = 'beklemede'",
            (offer_id, upload_id),
        )
        financiers = connection.execute(
            "SELECT DISTINCT financier_user_id FROM offers WHERE upload_id = ?",
            (upload_id,),
        ).fetchall()
        body = f"{offer['invoice_no']}: finansman tamamlandı. Transfer {receipt['transfer_id']} (DEMO / MOCK)."
        for financier in financiers:
            repo_api.insert_notification(connection, financier["financier_user_id"], "panel", "Fatura finanse edildi", body)
        db._write_audit(
            connection, user["username"], request.client.host if request.client else "127.0.0.1",
            "offer_accepted", user_id=user["id"],
            detail={"offer_id": offer_id, "upload_id": upload_id, "net_amount": offer["net_amount"], "user_agent": request.headers.get("user-agent", "")},
        )
        db._write_audit(
            connection, user["username"], request.client.host if request.client else "127.0.0.1",
            "transfer_mock", user_id=user["id"],
            detail={"transfer_id": receipt["transfer_id"], "amount": receipt["amount"], "mock": True, "user_agent": request.headers.get("user-agent", "")},
        )
    return {"document": document_or_404(repo_api.document_id_for_upload(upload_id)), "receipt": receipt}


@app.post("/api/offers/{offer_id}/reject")
def reject_offer(offer_id: int, request: Request):
    user = require_role(session_user(request), "kobi")
    offer = repo_api.get_offer(offer_id)
    if not offer or offer["company_vkn"] != user.get("company_vkn"):
        raise HTTPException(404, "Teklif bulunamadı.")
    with db.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT status FROM offers WHERE id = ? AND financier_user_id = ?",
            (offer_id, offer["financier_user_id"]),
        ).fetchone()
        if not current or current["status"] != "beklemede":
            raise HTTPException(409, "Bu teklif artık reddedilemez.")
        connection.execute(
            "UPDATE offers SET status = 'red' WHERE id = ? AND status = 'beklemede'",
            (offer_id,),
        )
        remaining = connection.execute(
            "SELECT 1 FROM offers WHERE upload_id = ? AND status = 'beklemede' LIMIT 1",
            (offer["upload_id"],),
        ).fetchone()
        if not remaining:
            connection.execute(
                "UPDATE uploads SET status = 'teklif_bekliyor' WHERE id = ? AND status = 'teklif_var'",
                (offer["upload_id"],),
            )
        db._write_audit(
            connection, user["username"], request.client.host if request.client else "127.0.0.1",
            "offer_rejected", user_id=user["id"],
            detail={"offer_id": offer_id, "user_agent": request.headers.get("user-agent", "")},
        )
    return {"offer": next(item for item in serialize_offers(f"U-{offer['upload_id']}") if item["id"] == offer_id)}


@app.get("/api/stats")
def stats(request: Request):
    user = require_role(session_user(request), "kobi")
    with db.get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(DISTINCT up.id) AS document_count,
                   COUNT(DISTINCT CASE WHEN up.status IN ('incelemede', 'teklif_bekliyor', 'teklif_var') THEN up.id END) AS waiting_count,
                   SUM(CASE WHEN o.status = 'beklemede' THEN 1 ELSE 0 END) AS offer_count,
                   AVG(CASE WHEN o.status = 'beklemede' THEN o.discount_rate END) AS avg_discount,
                   SUM(CASE WHEN o.status = 'kabul' THEN o.net_amount ELSE 0 END) AS financed_total
            FROM uploads up LEFT JOIN offers o ON o.upload_id = up.id
            WHERE up.user_id = ?
            """,
            (user["id"],),
        ).fetchone()
    return {
        "financed_total": row["financed_total"] or 0,
        "waiting_count": row["waiting_count"] or 0,
        "offer_count": row["offer_count"] or 0,
        "avg_discount": row["avg_discount"] or 0,
    }


@app.get("/api/market")
def market(
    request: Request,
    q: str = "",
    min: float | None = Query(default=None, ge=0),
    max_days: int | None = Query(default=None, ge=0),
    risk: int | None = Query(default=None, ge=0, le=100),
    sector: str | None = None,
    sort: str = "amount",
):
    user = require_role(session_user(request), "finansor")
    if sort not in {"amount", "due"}:
        raise HTTPException(400, "Sıralama türü geçersiz.")
    documents = []
    for doc in [repo_api.make_document(item["id"]) for item in repo_api.load_invoices()]:
        if doc and doc["status"] in {"teklif_bekliyor", "teklif_var"}:
            documents.append(normalize_document_annual_rate(doc))
    for row in repo_api.all_upload_rows():
        doc = repo_api.make_document(f"U-{row['id']}")
        if doc and doc["status"] in {"teklif_bekliyor", "teklif_var"}:
            documents.append(normalize_document_annual_rate(doc))
    filtered = []
    for doc in documents:
        if min is not None and (doc.get("total") is None or doc["total"] < min):
            continue
        if max_days is not None and (doc.get("days_left") is None or doc["days_left"] > max_days):
            continue
        if risk is not None and doc["risk_score"] > risk:
            continue
        if sector and sector.casefold() not in str(doc["seller"].get("sector") or "").casefold():
            continue
        if q and q.casefold() not in json.dumps(doc, ensure_ascii=False).casefold():
            continue
        filtered.append(doc)
    if sort == "due":
        filtered.sort(key=lambda item: item.get("days_left") if item.get("days_left") is not None else 10**9)
    else:
        filtered.sort(key=lambda item: item.get("total") or 0, reverse=True)
    return filtered


@app.get("/api/documents/{document_id}/risk-report")
def risk_report(document_id: str, request: Request):
    user = require_role(session_user(request), "finansor")
    document = user_can_view_document(user, document_id)
    invoice = document_invoice(document_id)
    score = document["risk_score"]
    rate = fraud.base_discount_rate(invoice, score) if invoice.get("due_date") else 0.0
    total = float(document.get("total") or 0)
    buyer_data = mocks.buyer_credit_score(invoice.get("buyer_vkn"))

    def generate():
        response = gemma.risk_report(invoice, buyer_data)
        return {
            "summary": response.get("summary", "")
            if isinstance(response, dict) else str(response)
        }

    result = repo_ai.cached_ai_result(
        "risk_report",
        document_id,
        {"invoice": invoice, "buyer": buyer_data, "rate": rate, "total": total},
        generate,
    )
    return {
        **result,
        "suggested_discount_rate": rate,
        "suggested_net_amount": round(total * (1 - rate), 2),
    }


def _normalized_insight(value):
    result = value if isinstance(value, dict) else {"summary": str(value or "")}
    verdict = result.get("verdict")
    return {
        "summary": str(result.get("summary") or ""),
        "strengths": [str(item) for item in result.get("strengths", []) if item is not None]
        if isinstance(result.get("strengths", []), list) else [],
        "concerns": [str(item) for item in result.get("concerns", []) if item is not None]
        if isinstance(result.get("concerns", []), list) else [],
        "verdict": verdict if verdict in {"uygun", "dikkat", "riskli"} else "dikkat",
    }


@app.get("/api/documents/{document_id}/insight")
def document_insight(document_id: str, request: Request):
    user = session_user(request)
    document = user_can_view_document(user, document_id)
    invoice = document_invoice(document_id)
    buyer_vkn = invoice.get("buyer_vkn")
    buyer_company = repo_api.COMPANY_BY_VKN.get(buyer_vkn, {})
    buyer_profile = {
        **{
            key: buyer_company.get(key)
            for key in ("vkn", "name", "sector", "founded", "employees")
        },
        **(mocks.buyer_credit_score(buyer_vkn) if buyer_vkn else {}),
        "payment_stats": repo_ai.payment_stats(buyer_vkn) if buyer_vkn else {},
    }
    flags = document.get("flags") or []
    result = repo_ai.cached_ai_result(
        "invoice_insight",
        document_id,
        {"invoice": invoice, "flags": flags, "buyer_profile": buyer_profile},
        lambda: _normalized_insight(
            gemma.invoice_insight(invoice, flags, buyer_profile)
        ),
    )
    return {
        **_normalized_insight(result),
        "model": result["model"],
        "generated_at": result["generated_at"],
    }


@app.get("/api/companies/{vkn}/payment-profile")
def payment_profile(vkn: str, request: Request):
    user = session_user(request)
    if user["role"] == "kobi":
        own_buyer_vkns = {
            str(invoice.get("buyer_vkn") or "")
            for row in repo_api.all_upload_rows()
            if row.get("user_id") == user["id"]
            if (invoice := repo_api.invoice_for_row(row))
        }
        if str(vkn) not in own_buyer_vkns:
            raise HTTPException(404, "Şirket ödeme profili bulunamadı.")
    else:
        require_role(user, "finansor", "denetim")

    company_data = repo_api.COMPANY_BY_VKN.get(vkn)
    if not company_data:
        raise HTTPException(404, "Şirket bulunamadı.")
    company = {
        key: company_data.get(key)
        for key in ("vkn", "name", "sector", "founded", "employees")
    }
    stats = repo_ai.payment_stats(vkn)
    history = repo_ai.get_payment_history(vkn, limit=12)
    result = repo_ai.cached_ai_result(
        "payment_comment",
        vkn,
        {"company": company, "stats": stats, "history": history},
        lambda: {"ai_comment": str(gemma.payment_comment(company, stats, history) or "")},
    )
    return {
        "company": company,
        "stats": stats,
        "history": history,
        "ai_comment": result["ai_comment"],
        "model": result["model"],
        "generated_at": result["generated_at"],
    }


@app.get("/api/documents/{document_id}/offers-insight")
def document_offers_insight(document_id: str, request: Request):
    user = require_role(session_user(request), "kobi")
    document = user_can_view_document(user, document_id)
    invoice = document_invoice(document_id)
    active_offers = [
        offer for offer in serialize_offers(document_id)
        if offer.get("status") == "beklemede"
    ]
    model_offers = [
        {
            "offer_id": offer["id"],
            "financier": offer["financier"]["name"],
            "net_amount": offer["net_amount"],
            "discount_rate": offer["discount_rate"],
            "annual_rate": offer["annual_rate"],
            "note": offer.get("note"),
        }
        for offer in active_offers
    ]

    def generate():
        raw = gemma.offers_insight(invoice, model_offers)
        generated = raw if isinstance(raw, dict) else {}
        comments = {
            item.get("offer_id"): item.get("comment", "")
            for item in generated.get("offers", [])
            if isinstance(item, dict)
        } if isinstance(generated.get("offers", []), list) else {}
        raw_text = str(raw) if not isinstance(raw, dict) else ""
        return {
            "offers": [
                {
                    "offer_id": offer["id"],
                    "financier": offer["financier"]["name"],
                    "net_amount": offer["net_amount"],
                    "discount_rate": offer["discount_rate"],
                    "annual_rate": offer["annual_rate"],
                    "comment": str(comments.get(offer["id"]) or raw_text),
                }
                for offer in active_offers
            ],
            "recommendation": str(generated.get("recommendation") or ""),
            "reason": str(generated.get("reason") or raw_text),
        }

    result = repo_ai.cached_ai_result(
        "offers_insight",
        document_id,
        {"invoice": invoice, "offers": model_offers},
        generate,
    )
    return {
        **result,
        "offers": result.get("offers", []),
        "recommendation": result.get("recommendation", ""),
        "reason": result.get("reason", ""),
    }


def _digest_context(user):
    if user["role"] == "kobi":
        rows = [
            row for row in repo_api.all_upload_rows()
            if row.get("user_id") == user["id"]
        ]
        documents = [
            normalize_document_annual_rate(document)
            for row in rows
            if (document := repo_api.make_document(f"U-{row['id']}"))
        ]
        documents.sort(
            key=lambda item: item.get("days_left")
            if item.get("days_left") is not None else 10**9
        )
        return {
            "documents": [
                {
                    "invoice_no": item["invoice_no"],
                    "status": item["status"],
                    "days_left": item["days_left"],
                    "offer_count": item["offer_count"],
                    "best_offer": item["best_offer"],
                }
                for item in documents[:10]
            ]
        }
    if user["role"] == "finansor":
        documents = [
            normalize_document_annual_rate(repo_api.make_document(item["id"]))
            for item in repo_api.load_invoices()
        ]
        documents.extend(
            normalize_document_annual_rate(repo_api.make_document(f"U-{row['id']}"))
            for row in repo_api.all_upload_rows()
        )
        opportunities = [
            item for item in documents
            if item and item.get("status") in {"teklif_bekliyor", "teklif_var"}
        ]
        opportunities.sort(
            key=lambda item: (
                item.get("risk_score") if item.get("risk_score") is not None else 100,
                -(item.get("total") or 0),
            )
        )
        return {
            "opportunities": [
                {
                    "invoice_no": item["invoice_no"],
                    "total": item["total"],
                    "risk_score": item["risk_score"],
                    "risk_class": item["risk_class"],
                    "days_left": item["days_left"],
                    "best_offer": item["best_offer"],
                }
                for item in opportunities[:10]
            ]
        }
    return network_data_for_report()


@app.get("/api/my/ai-digest")
def ai_digest(request: Request):
    user = session_user(request)
    context = _digest_context(user)

    def generate():
        raw = gemma.ai_digest(user["role"], context)
        if isinstance(raw, dict) and isinstance(raw.get("bullets"), list):
            bullets = [str(item) for item in raw["bullets"] if item is not None]
        else:
            bullets = [str(raw or "Gemma özeti oluşturulamadı.")]
        if len(bullets) < 3:
            bullets.extend(
                ["Güncel belge ve teklif durumunuzu düzenli olarak kontrol edin."]
                * (3 - len(bullets))
            )
        return {"bullets": bullets[:5]}

    result = repo_ai.cached_ai_result(
        "ai_digest",
        user.get("id") or user["role"],
        {"role": user["role"], "context": context},
        generate,
    )
    return {
        **result,
        "bullets": result.get("bullets", []),
    }


@app.post("/api/offers")
def create_offer(payload: dict, request: Request):
    user = require_role(session_user(request), "finansor")
    document_id = str(payload.get("document_id") or "")
    document = user_can_view_document(user, document_id)
    upload_id = upload_id_from(document_id)
    if upload_id is None:
        upload_id = repo_api.preloaded_upload_id(document_id)
    if upload_id is None:
        upload_id = repo_api.ensure_preloaded_upload(document_id, user, request)
    if upload_id is None:
        raise HTTPException(400, "Bu fatura için teklif verilemiyor.")
    try:
        net_amount = float(payload.get("net_amount"))
    except (TypeError, ValueError):
        raise HTTPException(400, "Teklif tutarı geçerli bir sayı olmalıdır.")
    total = document.get("total")
    if total is None or not math.isfinite(net_amount) or net_amount <= 0 or net_amount > float(total):
        raise HTTPException(400, "Teklif tutarı fatura toplamından büyük veya sıfır olamaz.")
    discount_rate = round((float(total) - net_amount) / float(total), 6)
    note = str(payload.get("note") or "").strip()[:500]
    owner_id = repo_api.upload_owner(upload_id)
    owner = repo_api.user_by_id(owner_id)
    if not owner:
        raise HTTPException(404, "Fatura sahibi bulunamadı.")
    subject = "Faturanız için yeni finansman teklifi"
    body = f"{document['invoice_no']} için {user['display_name']} tarafından {net_amount:.2f} TL teklif verildi."
    with db.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        active = connection.execute(
            "SELECT id FROM offers WHERE upload_id = ? AND financier_user_id = ? AND status = 'beklemede' ORDER BY id DESC LIMIT 1",
            (upload_id, user["id"]),
        ).fetchone()
        if active:
            connection.execute(
                "UPDATE offers SET discount_rate = ?, net_amount = ?, note = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?",
                (discount_rate, net_amount, note, active["id"]),
            )
            offer_id = active["id"]
        else:
            cursor = connection.execute(
                """
                INSERT INTO offers (upload_id, financier_user_id, discount_rate, net_amount, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (upload_id, user["id"], discount_rate, net_amount, note),
            )
            offer_id = cursor.lastrowid
        connection.execute(
            "UPDATE uploads SET status = 'teklif_var' WHERE id = ? AND status = 'teklif_bekliyor'",
            (upload_id,),
        )
        repo_api.insert_notification(connection, owner["id"], "panel", subject, body)
        repo_api.insert_notification(connection, owner["id"], "email", subject, body)
        db._write_audit(
            connection, user["username"], request.client.host if request.client else "127.0.0.1",
            "offer_created", user_id=user["id"],
            detail={"offer_id": offer_id, "upload_id": upload_id, "net_amount": net_amount, "user_agent": request.headers.get("user-agent", "")},
        )
    outbox = ROOT / "logs" / "outbox.log"
    outbox.parent.mkdir(parents=True, exist_ok=True)
    with outbox.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "to": owner.get("email") or owner["username"],
            "subject": subject,
            "body": body,
        }, ensure_ascii=False) + "\n")
    return {"offer": next(item for item in serialize_offers(document_id) if item["id"] == offer_id)}


@app.delete("/api/offers/{offer_id}")
def withdraw_offer(offer_id: int, request: Request):
    user = require_role(session_user(request), "finansor")
    offer = repo_api.get_offer(offer_id)
    if not offer or offer["financier_user_id"] != user["id"]:
        raise HTTPException(404, "Teklif bulunamadı.")
    with db.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT status FROM offers WHERE id = ? AND financier_user_id = ?",
            (offer_id, user["id"]),
        ).fetchone()
        if not current or current["status"] != "beklemede":
            raise HTTPException(409, "Bu teklif artık geri çekilemez.")
        connection.execute(
            "UPDATE offers SET status = 'geri_cekildi' WHERE id = ? AND status = 'beklemede'",
            (offer_id,),
        )
        remaining = connection.execute(
            "SELECT 1 FROM offers WHERE upload_id = ? AND status = 'beklemede' LIMIT 1",
            (offer["upload_id"],),
        ).fetchone()
        if not remaining:
            connection.execute(
                "UPDATE uploads SET status = 'teklif_bekliyor' WHERE id = ? AND status = 'teklif_var'",
                (offer["upload_id"],),
            )
        db._write_audit(
            connection, user["username"], request.client.host if request.client else "127.0.0.1",
            "offer_withdrawn", user_id=user["id"],
            detail={"offer_id": offer_id, "user_agent": request.headers.get("user-agent", "")},
        )
    return {"offer": next(item for item in serialize_offers(f"U-{offer['upload_id']}") if item["id"] == offer_id)}


@app.get("/api/my/offers")
def my_offers(request: Request):
    user = require_role(session_user(request), "finansor")
    offers = repo_api.financier_offer_list(user["id"])
    return [
        {
            **offer,
            "annual_rate": annual_rate(
                offer.get("discount_rate"),
                (offer.get("document") or {}).get("days_left"),
            ),
            "document": normalize_document_annual_rate(offer["document"])
            if offer.get("document") else offer.get("document"),
        }
        for offer in offers
    ]


@app.get("/api/portfolio")
def portfolio(request: Request):
    user = require_role(session_user(request), "finansor")
    offers = [offer for offer in repo_api.financier_offer_list(user["id"]) if offer["status"] == "kabul"]
    for offer in offers:
        offer["annual_rate"] = annual_rate(
            offer.get("discount_rate"),
            (offer.get("document") or {}).get("days_left"),
        )
        if offer.get("document"):
            normalize_document_annual_rate(offer["document"])
    invested = sum(item["net_amount"] for item in offers)
    expected = sum((item["document"].get("total") or item["net_amount"]) for item in offers)
    return {
        "documents": [item["document"] for item in offers],
        "invested": invested,
        "expected_collection": expected,
        "expected_profit": expected - invested,
    }


@app.get("/api/review-queue")
def review_queue(request: Request):
    require_role(session_user(request), "denetim")
    return [
        document_or_404(f"U-{row['id']}")
        for row in repo_api.all_upload_rows()
        if row["status"] == "incelemede" and (row["risk_score"] or 0) >= 60
    ]


@app.post("/api/documents/{document_id}/review")
def review_document(document_id: str, payload: dict, request: Request):
    user = require_role(session_user(request), "denetim")
    upload_id = upload_id_from(document_id)
    row = repo_api.upload_row(upload_id or -1)
    if not row:
        raise HTTPException(404, "Fatura bulunamadı.")
    decision = payload.get("decision")
    reason = str(payload.get("reason") or "").strip()
    if decision not in {"approve", "reject"}:
        raise HTTPException(400, "İnceleme kararı geçersiz.")
    if decision == "reject" and not reason:
        raise HTTPException(400, "Ret kararı için gerekçe gereklidir.")
    if row["status"] != "incelemede":
        raise HTTPException(409, "Fatura inceleme kuyruğunda değil.")
    if row["risk_score"] is None or row["risk_score"] < 60:
        raise HTTPException(409, "Fatura inceleme kuyruğu risk eşiğini karşılamıyor.")
    status = "teklif_bekliyor" if decision == "approve" else "reddedildi"
    with db.get_connection() as connection:
        cursor = connection.execute(
            "UPDATE uploads SET status = ? WHERE id = ? AND status = 'incelemede'",
            (status, upload_id),
        )
        if not cursor.rowcount:
            raise HTTPException(409, "Fatura inceleme kuyruğunda değil.")
        db._write_audit(
            connection, user["username"], request.client.host if request.client else "127.0.0.1",
            "document_reviewed", user_id=user["id"],
            detail={"upload_id": upload_id, "decision": decision, "reason": reason, "user_agent": request.headers.get("user-agent", "")},
        )
    return {"document": document_or_404(document_id)}


def audit_results(company, action, from_date, to_date):
    rows = db.list_audit_records(
        start_date=from_date,
        end_date=to_date,
        company_vkn=company,
        action=action,
    )
    return [{
        "at": row["at"],
        "username": row["username"],
        "company": row["company_name"],
        "ip_address": row["ip_address"],
        "action": row["action"],
        "file_name": row["file_name"],
        "sha256": row["file_sha256"],
        "invoice_no": row["invoice_no"],
        "detail": row["detail_json"],
    } for row in rows]


@app.get("/api/audit")
def audit_log(
    request: Request,
    company: str | None = None,
    action: str | None = None,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
):
    require_role(session_user(request), "denetim")
    return audit_results(company, action, from_date, to_date)


@app.get("/api/audit.csv")
def audit_csv(
    request: Request,
    company: str | None = None,
    action: str | None = None,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
):
    require_role(session_user(request), "denetim")
    records = audit_results(company, action, from_date, to_date)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[
        "at", "username", "company", "ip_address", "action",
        "file_name", "sha256", "invoice_no", "detail",
    ])
    writer.writeheader()
    writer.writerows(records)
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="vadesiz-audit.csv"'},
    )


@app.get("/api/network")
def network(request: Request):
    require_role(session_user(request), "denetim")
    invoices = repo_api.load_invoices()
    for row in repo_api.all_upload_rows():
        invoice = repo_api.invoice_for_row(row)
        if invoice:
            invoices.append(invoice)
    nodes = {}
    edges = {}
    for invoice in invoices:
        seller_id, buyer_id = invoice.get("seller_vkn"), invoice.get("buyer_vkn")
        if not seller_id or not buyer_id:
            continue
        seller = repo_api.COMPANY_BY_VKN.get(seller_id, {})
        buyer = repo_api.COMPANY_BY_VKN.get(buyer_id, {})
        flags = fraud.analyze_invoice(invoice, repo_api.COMPANIES, invoices)
        total = float(invoice.get("total") or invoice.get("amount") or 0)
        flagged = bool(flags)
        for company_id, company in ((seller_id, seller), (buyer_id, buyer)):
            node = nodes.setdefault(company_id, {
                "id": company_id,
                "name": company.get("name") or company_id,
                "sector": company.get("sector"),
                "total": 0.0,
                "flagged": False,
            })
            node["total"] += total
            node["flagged"] = node["flagged"] or flagged
        edge = edges.setdefault((seller_id, buyer_id), {
            "source": seller_id, "target": buyer_id, "total": 0.0,
            "invoice_count": 0, "flagged": False,
        })
        edge["total"] += total
        edge["invoice_count"] += 1
        edge["flagged"] = edge["flagged"] or flagged
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


@app.post("/api/network/report")
def network_report(request: Request):
    require_role(session_user(request), "denetim")
    graph = network_data_for_report()
    return repo_ai.cached_ai_result(
        "network_report",
        "flagged-network",
        graph,
        lambda: {"report": gemma.suspicious_network_report(graph)},
    )


def network_data_for_report():
    invoices = repo_api.load_invoices()
    invoices.extend(
        invoice for row in repo_api.all_upload_rows()
        if (invoice := repo_api.invoice_for_row(row))
    )
    flags_by_invoice = []
    for invoice in invoices:
        flags = fraud.analyze_invoice(invoice, repo_api.COMPANIES, invoices)
        if flags:
            flags_by_invoice.append({
                "invoice_no": invoice.get("invoice_no"),
                "seller_vkn": invoice.get("seller_vkn"),
                "buyer_vkn": invoice.get("buyer_vkn"),
                "flags": flags,
            })
    return {"flagged_invoices": flags_by_invoice[:30]}


@app.get("/api/notifications")
def notifications(request: Request):
    user = session_user(request)
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, subject, body, read_at
            FROM notifications
            WHERE user_id = ? AND channel = 'panel'
            ORDER BY created_at DESC, id DESC
            """,
            (user["id"],),
        ).fetchall()
    return [
        {
            "id": row["id"], "created_at": row["created_at"],
            "subject": row["subject"], "body": row["body"],
            "read": row["read_at"] is not None,
        }
        for row in rows
    ]


@app.post("/api/notifications/read")
def read_notifications(request: Request):
    user = session_user(request)
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE notifications SET read_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND channel = 'panel' AND read_at IS NULL
            """,
            (user["id"],),
        )
        if cursor.rowcount:
            db._write_audit(
                connection, user["username"], request.client.host if request.client else "127.0.0.1",
                "notifications_read", user_id=user["id"],
                detail={"count": cursor.rowcount, "user_agent": request.headers.get("user-agent", "")},
            )
    return {"ok": True}


if WEB.is_dir():
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
else:
    @app.get("/")
    def index():
        return FileResponse(WEB / "index.html")
