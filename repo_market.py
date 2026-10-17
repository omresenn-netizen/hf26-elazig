"""Database operations for financier marketplace and audit workflows."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

import db
import fraud

ROOT = Path(__file__).resolve().parent
OUTBOX_PATH = ROOT / "logs" / "outbox.log"


def list_market_records(companies, invoices):
    company_by_vkn = {company["vkn"]: company for company in companies}
    with db.get_connection() as connection:
        stored_rows = connection.execute(
            """
            SELECT uploads.*, users.display_name AS seller_name,
                   (SELECT COUNT(*) FROM offers WHERE offers.upload_id = uploads.id) AS offer_count
            FROM uploads
            LEFT JOIN users ON users.company_vkn = uploads.company_vkn AND users.role = 'kobi'
            WHERE uploads.status IN ('teklif_bekliyor', 'teklif_var')
            ORDER BY uploads.uploaded_at DESC, uploads.id DESC
            """
        ).fetchall()
        stored_records = [dict(row) for row in stored_rows]

    records = []
    stored_invoice_numbers = set()
    for row in stored_records:
        invoice = json.loads(row["extracted_json"] or "{}")
        if not invoice.get("invoice_no"):
            continue
        stored_invoice_numbers.add(invoice["invoice_no"])
        seller = company_by_vkn.get(invoice.get("seller_vkn"), {})
        buyer = company_by_vkn.get(invoice.get("buyer_vkn"), {})
        flags = json.loads(row["flags_json"] or "[]")
        records.append({
            "upload_id": row["id"],
            "invoice": invoice,
            "seller": seller,
            "buyer": buyer,
            "seller_name": row["seller_name"] or seller.get("name", invoice.get("seller_vkn", "—")),
            "flags": flags,
            "risk_score": row["risk_score"] if row["risk_score"] is not None else fraud.risk_score(flags),
            "status": row["status"],
            "offer_count": row["offer_count"],
            "preloaded": False,
        })

    demo_uploads_path = ROOT / "data" / "demo_uploads.json"
    demo_invoice_numbers = {
        item["invoice_no"]
        for item in json.loads(demo_uploads_path.read_text(encoding="utf-8"))
    }
    for invoice in invoices:
        invoice_no = invoice.get("invoice_no")
        if invoice_no in demo_invoice_numbers or invoice_no in stored_invoice_numbers:
            continue
        seller = company_by_vkn.get(invoice.get("seller_vkn"), {})
        buyer = company_by_vkn.get(invoice.get("buyer_vkn"), {})
        flags = fraud.analyze_invoice(invoice, companies, invoices)
        records.append({
            "upload_id": None,
            "invoice": invoice,
            "seller": seller,
            "buyer": buyer,
            "seller_name": seller.get("name", invoice.get("seller_vkn", "—")),
            "flags": flags,
            "risk_score": fraud.risk_score(flags),
            "status": "teklif_bekliyor",
            "offer_count": 0,
            "preloaded": True,
        })
    return records


def list_uploads_for_review():
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT uploads.*, users.display_name AS seller_name
            FROM uploads
            LEFT JOIN users ON users.company_vkn = uploads.company_vkn AND users.role = 'kobi'
            WHERE uploads.status = 'incelemede'
            ORDER BY uploads.uploaded_at, uploads.id
            """
        ).fetchall()
    records = []
    for row in rows:
        record = dict(row)
        record["invoice"] = json.loads(record["extracted_json"] or "{}")
        record["flags"] = json.loads(record["flags_json"] or "[]")
        records.append(record)
    return records


def list_offers_for_upload(upload_id):
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT offers.*, users.display_name AS financier_name
            FROM offers
            JOIN users ON users.id = offers.financier_user_id
            WHERE offers.upload_id = ?
            ORDER BY offers.created_at DESC, offers.id DESC
            """,
            (upload_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_financier_offers(financier_user_id):
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT offers.*, uploads.invoice_no, uploads.extracted_json,
                   uploads.company_vkn, seller.display_name AS seller_name
            FROM offers
            JOIN uploads ON uploads.id = offers.upload_id
            LEFT JOIN users AS seller ON seller.company_vkn = uploads.company_vkn
                AND seller.role = 'kobi'
            WHERE offers.financier_user_id = ?
            ORDER BY offers.created_at DESC, offers.id DESC
            """,
            (financier_user_id,),
        ).fetchall()
    records = []
    for row in rows:
        record = dict(row)
        record["invoice"] = json.loads(record.pop("extracted_json") or "{}")
        records.append(record)
    return records


def create_market_offer(record, user, ip_address, discount_rate, net_amount, note):
    invoice = record["invoice"]
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    subject = f"{invoice.get('invoice_no', 'Fatura')} için yeni finansman teklifi"
    formatted_rate = f"{discount_rate * 100:.2f}".replace(".", ",")
    formatted_amount = (
        f"{net_amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    body = (
        f"{user.get('display_name') or user['username']} faturanız için "
        f"%{formatted_rate} iskonto ile teklif verdi. "
        f"Net ödeme: {formatted_amount} TL."
    )
    with db.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        upload_id = record["upload_id"]
        if upload_id is None:
            existing = connection.execute(
                """
                SELECT id, status FROM uploads
                WHERE invoice_no = ? ORDER BY id LIMIT 1
                """,
                (invoice.get("invoice_no"),),
            ).fetchone()
            if existing:
                if existing["status"] not in {"teklif_bekliyor", "teklif_var"}:
                    raise ValueError("Bu fatura şu anda teklif kabul etmiyor.")
                upload_id = existing["id"]
            else:
                seller_user = connection.execute(
                    "SELECT id FROM users WHERE role = 'kobi' AND company_vkn = ?",
                    (invoice.get("seller_vkn"),),
                ).fetchone()
                if not seller_user:
                    raise ValueError("Faturanın satıcısı için KOBİ demo hesabı bulunamadı.")
                invoice_bytes = json.dumps(invoice, ensure_ascii=False, sort_keys=True).encode("utf-8")
                fingerprint = fraud._fingerprint(invoice)
                cursor = connection.execute(
                    """
                    INSERT INTO uploads (
                        user_id, company_vkn, ip_address, user_agent, file_name, file_size,
                        file_sha256, invoice_no, invoice_fingerprint, extracted_json, risk_score,
                        flags_json, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'teklif_bekliyor')
                    """,
                    (
                        seller_user["id"],
                        invoice.get("seller_vkn"),
                        "127.0.0.1",
                        "DEMO / MOCK preloaded invoice",
                        f"preloaded-{invoice.get('invoice_no', 'invoice')}.json",
                        len(invoice_bytes),
                        hashlib.sha256(b"vadesiz-preloaded:" + invoice_bytes).hexdigest(),
                        invoice.get("invoice_no"),
                        fingerprint,
                        invoice_bytes.decode("utf-8"),
                        record["risk_score"],
                        json.dumps(record["flags"], ensure_ascii=False, sort_keys=True),
                    ),
                )
                upload_id = cursor.lastrowid
        upload = connection.execute(
            "SELECT status, company_vkn, invoice_no FROM uploads WHERE id = ?",
            (upload_id,),
        ).fetchone()
        if not upload or upload["status"] not in {"teklif_bekliyor", "teklif_var"}:
            raise ValueError("Bu fatura şu anda teklif kabul etmiyor.")
        active_offer = connection.execute(
            """
            SELECT id FROM offers
            WHERE upload_id = ? AND financier_user_id = ?
                AND status IN ('beklemede', 'kabul')
            LIMIT 1
            """,
            (upload_id, user["id"]),
        ).fetchone()
        if active_offer:
            raise ValueError("Bu fatura için zaten aktif bir teklifiniz var.")
        cursor = connection.execute(
            """
            INSERT INTO offers (
                upload_id, financier_user_id, discount_rate, net_amount, note, status
            ) VALUES (?, ?, ?, ?, ?, 'beklemede')
            """,
            (upload_id, user["id"], discount_rate, net_amount, note.strip() or None),
        )
        offer_id = cursor.lastrowid
        connection.execute(
            "UPDATE uploads SET status = 'teklif_var' WHERE id = ?",
            (upload_id,),
        )
        seller_user = connection.execute(
            "SELECT id, username, email FROM users WHERE role = 'kobi' AND company_vkn = ?",
            (upload["company_vkn"],),
        ).fetchone()
        if seller_user:
            connection.executemany(
                """
                INSERT INTO notifications (user_id, channel, subject, body)
                VALUES (?, ?, ?, ?)
                """,
                (
                    (seller_user["id"], "panel", subject, body),
                    (seller_user["id"], "email", subject, body),
                ),
            )
            recipient = seller_user["email"] or f"{seller_user['username']}@demo.vadesiz.local"
        else:
            recipient = "seller@demo.vadesiz.local"
        connection.commit()

    db.log_audit(
        "offer_created",
        user,
        ip_address,
        detail={
            "upload_id": upload_id,
            "invoice_no": upload["invoice_no"],
            "offer_id": offer_id,
            "discount_rate": discount_rate,
            "net_amount": net_amount,
        },
    )
    OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTBOX_PATH.open("a", encoding="utf-8") as outbox:
        outbox.write(json.dumps({
            "at": created_at,
            "to": recipient,
            "subject": subject,
            "body": body,
            "channel": "DEMO / MOCK",
        }, ensure_ascii=False) + "\n")
    return offer_id


def withdraw_offer(offer_id, user, ip_address):
    with db.get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        offer = connection.execute(
            """
            SELECT offers.upload_id, offers.status, uploads.invoice_no
            FROM offers
            JOIN uploads ON uploads.id = offers.upload_id
            WHERE offers.id = ? AND offers.financier_user_id = ?
            """,
            (offer_id, user["id"]),
        ).fetchone()
        if not offer or offer["status"] != "beklemede":
            raise ValueError("Yalnızca bekleyen kendi teklifinizi geri çekebilirsiniz.")
        connection.execute(
            "UPDATE offers SET status = 'geri_cekildi' WHERE id = ?",
            (offer_id,),
        )
        active_count = connection.execute(
            "SELECT COUNT(*) AS count FROM offers WHERE upload_id = ? AND status = 'beklemede'",
            (offer["upload_id"],),
        ).fetchone()["count"]
        if not active_count:
            connection.execute(
                "UPDATE uploads SET status = 'teklif_bekliyor' WHERE id = ? AND status = 'teklif_var'",
                (offer["upload_id"],),
            )
    db.log_audit(
        "offer_withdrawn",
        user,
        ip_address,
        detail={"offer_id": offer_id, "invoice_no": offer["invoice_no"]},
    )


def decide_review(upload_id, approved, reason, user, ip_address):
    status = "teklif_bekliyor" if approved else "reddedildi"
    action = "review_approved" if approved else "review_rejected"
    if not approved and not reason.strip():
        raise ValueError("Reddetme nedeni boş olamaz.")
    with db.get_connection() as connection:
        cursor = connection.execute(
            "UPDATE uploads SET status = ? WHERE id = ? AND status = 'incelemede'",
            (status, upload_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("Bu kayıt artık inceleme kuyruğunda değil.")
        invoice = connection.execute(
            "SELECT invoice_no FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
    db.log_audit(
        action,
        user,
        ip_address,
        detail={
            "upload_id": upload_id,
            "invoice_no": invoice["invoice_no"] if invoice else None,
            "reason": reason.strip() if not approved else "",
        },
    )
