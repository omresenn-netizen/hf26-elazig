"""API-specific queries and serialization helpers for the existing SQLite schema."""
import hashlib
import hmac
import json
from pathlib import Path

import db
import fraud
import mocks

ROOT = Path(__file__).resolve().parent
DEMO_UPLOAD_NUMBERS = {
    item["invoice_no"]
    for item in json.loads((ROOT / "data" / "demo_uploads.json").read_text(encoding="utf-8"))
}
COMPANIES = json.loads((ROOT / "data" / "companies.json").read_text(encoding="utf-8"))
COMPANY_BY_VKN = {item["vkn"]: item for item in COMPANIES}
FLAG_LABELS = {
    "duplicate_invoice": "Olası mükerrer fatura",
    "missing_delivery_note": "İrsaliye eksik",
    "sector_mismatch": "Sektör uyuşmazlığı",
    "capacity_outlier": "Kapasite dışı tutar",
    "round_amount": "Yuvarlak tutar",
    "vague_item": "Belirsiz ürün veya hizmet",
    "buyer_not_approved": "Alıcı onayı eksik",
    "network_cycle": "Fatura ağında döngü",
    "shell_company": "Şüpheli şirket ağı",
    "invoice_broker": "Aracı fatura örüntüsü",
    "year_end_cluster": "Yıl sonu fatura kümelenmesi",
}


def serialize_flags(flags):
    return [
        {
            "code": flag.get("code"),
            "label": FLAG_LABELS.get(flag.get("code"), flag.get("code", "")),
            "detail": flag.get("detail", ""),
        }
        for flag in flags
    ]


def load_invoices():
    # "scenario" is the generator's ground-truth label; it must never reach the API, the UI or Gemma
    invoices = json.loads((ROOT / "data" / "invoices.json").read_text(encoding="utf-8"))
    return [{key: value for key, value in invoice.items() if key != "scenario"} for invoice in invoices]


def api_user(row):
    return {
        key: row.get(key)
        for key in ("id", "username", "role", "display_name", "company_vkn")
    }


def authenticate(username, password, role, ip_address, user_agent):
    username = (username or "").strip()
    with db.get_connection() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user and db._account_locked(user):
            detail = {"role": role, "user_agent": user_agent or "", "reason": "account_locked", "locked_until": user["login_locked_until"]}
            db._write_audit(
                connection, username, ip_address, "login_locked",
                user_id=user["id"], detail=detail,
            )
            return None

        valid_password = False
        if user:
            valid_password = hmac.compare_digest(
                db._password_hash(password or "", user["salt"]),
                user["password_hash"],
            )
        else:
            db._password_hash(password or "", "0" * 32)
        valid = bool(user and user["role"] == role and valid_password)
        detail = {"role": role, "user_agent": user_agent or ""}
        if valid:
            connection.execute(
                "UPDATE users SET failed_login_attempts = 0, login_locked_until = NULL WHERE id = ?",
                (user["id"],),
            )
            db._write_audit(
                connection, username, ip_address, "login",
                user_id=user["id"], detail=detail,
            )
            return api_user(dict(user))

        if user and user["role"] != role:
            detail["reason"] = "role_mismatch"
        else:
            detail["reason"] = "invalid_credentials"
        if user and user["role"] == role:
            attempts = int(db._user_value(user, "failed_login_attempts") or 0) + 1
            lock_until = None
            if attempts >= db.MAX_LOGIN_ATTEMPTS:
                lock_until = (db.datetime.now(db.timezone.utc) + db.timedelta(minutes=db.LOGIN_LOCK_MINUTES)).isoformat()
                db._write_audit(
                    connection, username, ip_address, "login_locked",
                    user_id=user["id"], detail={**detail, "reason": "max_attempts_reached", "locked_until": lock_until},
                )
            connection.execute(
                "UPDATE users SET failed_login_attempts = ?, login_locked_until = ? WHERE id = ?",
                (attempts, lock_until, user["id"]),
            )
            if attempts >= db.MAX_LOGIN_ATTEMPTS:
                detail["reason"] = "max_attempts_reached"
        db._write_audit(
            connection, username or "(empty)", ip_address, "login_failed",
            user_id=user["id"] if user else None, detail=detail,
        )
        return None


def audit(action, user, request, detail=None):
    details = dict(detail or {})
    details["user_agent"] = request.headers.get("user-agent", "")
    db.log_audit(action, user, request.client.host if request.client else "127.0.0.1", details)


def create_upload(user, request, file_name, file_bytes, stored_name):
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    ip_address = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "")
    with db.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        duplicate = connection.execute(
            "SELECT id FROM uploads WHERE file_sha256 = ? ORDER BY id LIMIT 1",
            (file_hash,),
        ).fetchone()
        status = "reddedildi" if duplicate else "incelemede"
        flags = (
            [{"code": "duplicate_invoice", "detail": "Dosyanın SHA-256 özeti daha önce yüklenmiş."}]
            if duplicate else []
        )
        cursor = connection.execute(
            """
            INSERT INTO uploads (
                user_id, company_vkn, ip_address, user_agent, file_name, file_size,
                file_sha256, flags_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"], user.get("company_vkn"), ip_address, user_agent,
                file_name, len(file_bytes), file_hash,
                json.dumps(flags, ensure_ascii=False), status,
            ),
        )
        upload_id = cursor.lastrowid
        action = "duplicate_upload" if duplicate else "upload"
        details = {
            "upload_id": upload_id,
            "file_sha256": file_hash,
            "stored_name": stored_name if not duplicate else None,
        }
        if duplicate:
            details["duplicate_of"] = duplicate["id"]
            details["reason"] = "file_sha256"
        db._write_audit(
            connection, user["username"], ip_address, action,
            user_id=user["id"], detail={**details, "user_agent": user_agent},
        )
    return {
        "id": upload_id,
        "file_sha256": file_hash,
        "duplicate": bool(duplicate),
        "status": status,
    }


def file_path(upload_id):
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT detail_json FROM audit_log
            WHERE action IN ('upload', 'duplicate_upload')
              AND json_extract(detail_json, '$.upload_id') = ?
            ORDER BY id DESC
            """,
            (upload_id,),
        ).fetchall()
    for row in rows:
        try:
            detail = json.loads(row["detail_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if detail.get("upload_id") == upload_id and detail.get("stored_name"):
            path = ROOT / "uploads" / detail["stored_name"]
            if path.is_file() and path.parent.resolve() == (ROOT / "uploads").resolve():
                return path
    return None


def save_extraction(upload_id, user, request, invoice, score, flags):
    result = db.save_upload_extraction(
        upload_id,
        user,
        request.client.host if request.client else "127.0.0.1",
        invoice,
        score,
        flags,
    )
    return result


def save_pending_extraction(upload_id, user, request, invoice):
    with db.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT user_id, status FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        if not row or row["user_id"] != user["id"]:
            raise ValueError("Upload does not belong to the current user.")
        if row["status"] != "incelemede":
            raise ValueError("Only invoices awaiting review can be extracted.")
        connection.execute(
            "UPDATE uploads SET invoice_no = ?, extracted_json = ? WHERE id = ?",
            (
                invoice.get("invoice_no"),
                json.dumps(invoice, ensure_ascii=False, sort_keys=True),
                upload_id,
            ),
        )
        db._write_audit(
            connection,
            user["username"],
            request.client.host if request.client else "127.0.0.1",
            "extract",
            user_id=user["id"],
            detail={
                "upload_id": upload_id,
                "invoice_no": invoice.get("invoice_no"),
                "user_agent": request.headers.get("user-agent", ""),
            },
        )


def upload_row(upload_id):
    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        return dict(row) if row else None


def user_by_id(user_id):
    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT id, username, role, company_vkn, display_name, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def all_upload_rows():
    with db.get_connection() as connection:
        rows = connection.execute("SELECT * FROM uploads ORDER BY id").fetchall()
        return [dict(row) for row in rows]


def invoice_for_row(row):
    if row.get("extracted_json"):
        try:
            value = json.loads(row["extracted_json"])
            if isinstance(value, dict):
                return value
        except (TypeError, json.JSONDecodeError):
            pass
    return {}


def company_name(vkn):
    company = COMPANY_BY_VKN.get(vkn)
    if company:
        return company.get("name")
    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT display_name FROM users WHERE company_vkn = ? LIMIT 1", (vkn,)
        ).fetchone()
        return row["display_name"] if row else None


def get_offer(offer_id):
    with db.get_connection() as connection:
        row = connection.execute(
            """
            SELECT o.*, u.display_name AS financier_name, u.username AS financier_username,
                   up.company_vkn, up.extracted_json, up.invoice_no, up.status AS document_status
            FROM offers o
            JOIN users u ON u.id = o.financier_user_id
            JOIN uploads up ON up.id = o.upload_id
            WHERE o.id = ?
            """,
            (offer_id,),
        ).fetchone()
        return dict(row) if row else None


def offer_objects(upload_id):
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT o.*, u.display_name AS financier_name, u.username AS financier_username
            FROM offers o JOIN users u ON u.id = o.financier_user_id
            WHERE o.upload_id = ? ORDER BY o.created_at DESC, o.id DESC
            """,
            (upload_id,),
        ).fetchall()
        offers = []
        for row in rows:
            item = dict(row)
            offers.append({
                "id": item["id"],
                "document_id": document_id_for_upload(upload_id),
                "financier": {
                    "id": item["financier_user_id"],
                    "name": item["financier_name"],
                },
                "net_amount": item["net_amount"],
                "discount_rate": item["discount_rate"],
                "annual_rate": item["discount_rate"],
                "note": item["note"],
                "created_at": item["created_at"],
                "status": item["status"],
            })
        return offers


def preloaded_upload_id(invoice_id):
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT detail_json FROM audit_log
            WHERE action = 'preloaded_invoice_linked'
              AND json_extract(detail_json, '$.invoice_id') = ?
            ORDER BY id DESC
            """,
            (invoice_id,),
        ).fetchall()
    for row in rows:
        try:
            detail = json.loads(row["detail_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if detail.get("invoice_id") == invoice_id:
            return detail.get("upload_id")
    return None


def document_id_for_upload(upload_id):
    row = upload_row(upload_id)
    if row and row.get("file_name", "").startswith("Preloaded invoice "):
        invoice = invoice_for_row(row)
        return invoice.get("id") or f"U-{upload_id}"
    return f"U-{upload_id}"


def ensure_preloaded_upload(invoice_id, actor, request):
    invoice = next((item for item in load_invoices() if item.get("id") == invoice_id), None)
    if not invoice or invoice.get("invoice_no") in DEMO_UPLOAD_NUMBERS:
        return None
    existing_id = preloaded_upload_id(invoice_id)
    if existing_id:
        return existing_id
    seller_vkn = invoice.get("seller_vkn")
    with db.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            """
            SELECT json_extract(detail_json, '$.upload_id') AS upload_id
            FROM audit_log
            WHERE action = 'preloaded_invoice_linked'
              AND json_extract(detail_json, '$.invoice_id') = ?
            ORDER BY id DESC LIMIT 1
            """,
            (invoice_id,),
        ).fetchone()
        if existing:
            return existing["upload_id"]
        seller = connection.execute(
            "SELECT id FROM users WHERE role = 'kobi' AND company_vkn = ? LIMIT 1",
            (seller_vkn,),
        ).fetchone()
        if not seller:
            return None
        flags = fraud.analyze_invoice(invoice, COMPANIES, load_invoices())
        score = fraud.risk_score(flags)
        cursor = connection.execute(
            """
            INSERT INTO uploads (
                user_id, company_vkn, ip_address, user_agent, file_name, file_size,
                file_sha256, invoice_no, invoice_fingerprint, extracted_json,
                risk_score, flags_json, status
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, 'teklif_bekliyor')
            """,
            (
                seller["id"], seller_vkn,
                request.client.host if request.client else "127.0.0.1",
                request.headers.get("user-agent", ""),
                f"Preloaded invoice {invoice_id}",
                hashlib.sha256(f"preloaded:{invoice_id}".encode("utf-8")).hexdigest(),
                invoice.get("invoice_no"),
                fraud._fingerprint(invoice),
                json.dumps(invoice, ensure_ascii=False, sort_keys=True),
                score,
                json.dumps(flags, ensure_ascii=False, sort_keys=True),
            ),
        )
        db._write_audit(
            connection,
            actor["username"],
            request.client.host if request.client else "127.0.0.1",
            "preloaded_invoice_linked",
            user_id=actor["id"],
            detail={
                "invoice_id": invoice_id,
                "upload_id": cursor.lastrowid,
                "user_agent": request.headers.get("user-agent", ""),
            },
        )
        return cursor.lastrowid


def make_document(document_id):
    if document_id.startswith("U-"):
        try:
            upload_id = int(document_id[2:])
        except ValueError:
            return None
        row = upload_row(upload_id)
        if not row:
            return None
        invoice = invoice_for_row(row)
        seller_vkn = row.get("company_vkn") or invoice.get("seller_vkn")
        seller_data = COMPANY_BY_VKN.get(seller_vkn, {})
        buyer_vkn = invoice.get("buyer_vkn")
        buyer_data = COMPANY_BY_VKN.get(buyer_vkn, {})
        total = invoice.get("total", invoice.get("amount"))
        score = row.get("risk_score")
        score = int(score) if score is not None else None
        flags = serialize_flags(json.loads(row.get("flags_json") or "[]"))
        is_preloaded = row.get("file_name", "").startswith("Preloaded invoice ")
        offers = offer_objects(upload_id)
        best_offer = max(
            (offer for offer in offers if offer["status"] == "beklemede"),
            key=lambda item: item["net_amount"],
            default=None,
        )
        due_date = invoice.get("due_date")
        from fraud import days_to_due

        try:
            days_left = days_to_due(invoice) if due_date else None
        except ValueError:
            days_left = None
        return {
            "id": document_id,
            "invoice_no": invoice.get("invoice_no") or row.get("invoice_no"),
            "type": "Fatura",
            "seller": {
                "vkn": seller_vkn,
                "name": invoice.get("seller_name") or seller_data.get("name") or company_name(seller_vkn),
                "sector": seller_data.get("sector"),
            },
            "buyer": {
                "vkn": buyer_vkn,
                "name": invoice.get("buyer_name") or buyer_data.get("name"),
                "credit_score": mocks.buyer_credit_score(buyer_vkn)["score"] if buyer_vkn else None,
            },
            "total": total,
            "subtotal": invoice.get("subtotal"),
            "kdv": invoice.get("kdv"),
            "issue_date": invoice.get("issue_date"),
            "due_date": due_date,
            "days_left": days_left,
            "irsaliye_no": invoice.get("irsaliye_no"),
            "status": row["status"],
            "risk_score": score,
            "risk_class": None if score is None else "A" if score < 30 else "B" if score < 60 else "C" if score < 80 else "D",
            "flags": flags,
            "offer_count": sum(offer["status"] == "beklemede" for offer in offers),
            "best_offer": best_offer,
            "file": None if is_preloaded else {
                "name": row["file_name"],
                "size": row["file_size"],
                "sha256": row["file_sha256"],
                "uploaded_at": row["uploaded_at"],
                "ip_address": row["ip_address"],
            },
            "steps": [
                {"key": "upload", "label": "Belge yüklendi", "state": "done", "detail": row["file_name"]},
                {"key": "extract", "label": "Gemma ile okuma", "state": "done" if row.get("extracted_json") else "waiting", "detail": ""},
                {"key": "gib", "label": "GİB e-Fatura sorgusu – MOCK", "state": "done" if row.get("risk_score") is not None else "waiting", "detail": ""},
                {"key": "fraud", "label": "Naylon fatura kontrolü", "state": "done" if row.get("risk_score") is not None else "waiting", "detail": ""},
                {"key": "buyer", "label": "Alıcı onayı ve risk – MOCK", "state": "done" if row.get("risk_score") is not None else "waiting", "detail": ""},
            ],
        }
    invoice = next((item for item in load_invoices() if item.get("id") == document_id), None)
    if not invoice or invoice.get("invoice_no") in DEMO_UPLOAD_NUMBERS:
        return None
    invoice_set = load_invoices()
    flags = serialize_flags(fraud.analyze_invoice(invoice, COMPANIES, invoice_set))
    score = fraud.risk_score(flags)
    seller = COMPANY_BY_VKN.get(invoice.get("seller_vkn"), {})
    buyer = COMPANY_BY_VKN.get(invoice.get("buyer_vkn"), {})
    from fraud import days_to_due
    try:
        days_left = days_to_due(invoice)
    except ValueError:
        days_left = None
    linked_upload_id = preloaded_upload_id(document_id)
    offers = offer_objects(linked_upload_id) if linked_upload_id else []
    linked_row = upload_row(linked_upload_id) if linked_upload_id else None
    status = (
        linked_row["status"] if linked_row else
        "incelemede" if score >= 60 else
        "teklif_var" if offers else "teklif_bekliyor"
    )
    return {
        "id": document_id,
        "invoice_no": invoice.get("invoice_no"),
        "type": "Fatura",
        "seller": {"vkn": invoice.get("seller_vkn"), "name": seller.get("name"), "sector": seller.get("sector")},
        "buyer": {
            "vkn": invoice.get("buyer_vkn"),
            "name": buyer.get("name"),
            "credit_score": mocks.buyer_credit_score(invoice.get("buyer_vkn"))["score"] if invoice.get("buyer_vkn") else None,
        },
        "total": invoice.get("total"),
        "subtotal": invoice.get("subtotal"),
        "kdv": invoice.get("kdv"),
        "issue_date": invoice.get("issue_date"),
        "due_date": invoice.get("due_date"),
        "days_left": days_left,
        "irsaliye_no": invoice.get("irsaliye_no"),
        "status": status,
        "risk_score": score,
        "risk_class": "A" if score < 30 else "B" if score < 60 else "C" if score < 80 else "D",
        "flags": serialize_flags(json.loads(linked_row["flags_json"])) if linked_row else flags,
        "offer_count": sum(offer["status"] == "beklemede" for offer in offers),
        "best_offer": max(
            (offer for offer in offers if offer["status"] == "beklemede"),
            key=lambda item: item["net_amount"],
            default=None,
        ),
        "file": None,
        "steps": [
            {"key": "upload", "label": "Belge yüklendi", "state": "done", "detail": ""},
            {"key": "extract", "label": "Gemma ile okuma", "state": "done", "detail": ""},
            {"key": "gib", "label": "GİB e-Fatura sorgusu – MOCK", "state": "done", "detail": ""},
            {"key": "fraud", "label": "Naylon fatura kontrolü", "state": "done", "detail": ""},
            {"key": "buyer", "label": "Alıcı onayı ve risk – MOCK", "state": "done", "detail": ""},
        ],
    }


def insert_notification(connection, user_id, channel, subject, body):
    connection.execute(
        """
        INSERT INTO notifications (user_id, channel, subject, body)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, channel, subject, body),
    )


def upload_owner(upload_id):
    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT user_id FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        return row["user_id"] if row else None


def financier_offer_list(user_id):
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT o.*, up.invoice_no, up.company_vkn, up.extracted_json, up.risk_score,
                   up.status AS document_status, financier.display_name AS financier_name
            FROM offers o JOIN uploads up ON up.id = o.upload_id
            JOIN users financier ON financier.id = o.financier_user_id
            WHERE o.financier_user_id = ? ORDER BY o.created_at DESC, o.id DESC
            """,
            (user_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            invoice = invoice_for_row(item)
            document = make_document(f"U-{item['upload_id']}")
            offer = {
                "id": item["id"],
                "document_id": document_id_for_upload(item["upload_id"]),
                "financier": {"id": user_id, "name": item["financier_name"]},
                "net_amount": item["net_amount"],
                "discount_rate": item["discount_rate"],
                "annual_rate": item["discount_rate"],
                "note": item["note"],
                "created_at": item["created_at"],
                "status": item["status"],
            }
            if item["status"] == "kabul":
                from mocks import bank_transfer
                offer["receipt"] = bank_transfer(item["invoice_no"] or "", item["net_amount"])
            result.append({
                **offer,
                "document": {
                    "id": document_id_for_upload(item["upload_id"]),
                    "invoice_no": item["invoice_no"] or invoice.get("invoice_no"),
                    "seller": document["seller"] if document else None,
                    "buyer": document["buyer"] if document else None,
                    "total": document["total"] if document else None,
                    "due_date": document["due_date"] if document else None,
                    "risk_score": item["risk_score"],
                    "status": item["document_status"],
                },
            })
        return result
