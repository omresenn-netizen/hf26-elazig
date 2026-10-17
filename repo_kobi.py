"""KOBI-owned queries and state transitions for uploads, offers, and notifications."""
from datetime import datetime, timezone
import json
from pathlib import Path

import db

ROOT = Path(__file__).resolve().parent
OUTBOX_PATH = ROOT / "logs" / "outbox.log"


def list_company_uploads(company_vkn):
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT up.*, COALESCE(company.display_name, '') AS company_name,
                   COUNT(DISTINCT offer.id) AS offer_count
            FROM uploads AS up
            LEFT JOIN users AS company ON company.company_vkn = up.company_vkn
            LEFT JOIN offers AS offer
                ON offer.upload_id = up.id AND offer.status != 'geri_cekildi'
            WHERE up.company_vkn = ?
            GROUP BY up.id
            ORDER BY up.uploaded_at DESC, up.id DESC
            """,
            (company_vkn,),
        ).fetchall()
        uploads = [dict(row) for row in rows]
        for upload in uploads:
            invoice = json.loads(upload["extracted_json"]) if upload["extracted_json"] else {}
            legacy_count = 0
            if invoice.get("invoice_no"):
                legacy_count = connection.execute(
                    "SELECT COUNT(*) FROM legacy_offers WHERE invoice_no = ? AND status != 'withdrawn'",
                    (invoice["invoice_no"],),
                ).fetchone()[0]
            upload["invoice"] = invoice
            upload["flags"] = json.loads(upload["flags_json"] or "[]")
            upload["offer_count"] += legacy_count
        return uploads


def get_company_upload(company_vkn, upload_id):
    with db.get_connection() as connection:
        row = connection.execute(
            """
            SELECT up.*, COALESCE(company.display_name, '') AS company_name
            FROM uploads AS up
            LEFT JOIN users AS company ON company.company_vkn = up.company_vkn
            WHERE up.company_vkn = ? AND up.id = ?
            """,
            (company_vkn, upload_id),
        ).fetchone()
        if not row:
            return None
        upload = dict(row)
        upload["invoice"] = json.loads(upload["extracted_json"]) if upload["extracted_json"] else {}
        upload["flags"] = json.loads(upload["flags_json"] or "[]")
        return upload


def list_upload_offers(company_vkn, upload_id):
    upload = get_company_upload(company_vkn, upload_id)
    if not upload:
        return []
    invoice_no = upload["invoice"].get("invoice_no")
    with db.get_connection() as connection:
        current = connection.execute(
            """
            SELECT offer.id AS offer_id, offer.created_at, offer.discount_rate,
                   offer.net_amount, offer.note, offer.status, offer.financier_user_id,
                   financier.display_name AS financier_name, 'upload' AS source
            FROM offers AS offer
            JOIN users AS financier ON financier.id = offer.financier_user_id
            WHERE offer.upload_id = ?
            ORDER BY offer.created_at DESC, offer.id DESC
            """,
            (upload_id,),
        ).fetchall()
        offers = [dict(row) for row in current]
        if invoice_no:
            legacy = connection.execute(
                """
                SELECT id AS offer_id, created_at, discount_rate, net_amount,
                       '' AS note, status, NULL AS financier_user_id,
                       financier_name, 'legacy' AS source
                FROM legacy_offers
                WHERE invoice_no = ?
                ORDER BY created_at DESC, id DESC
                """,
                (invoice_no,),
            ).fetchall()
            offers.extend(dict(row) for row in legacy)
    return offers


def sync_offer_notifications(user, upload, offers):
    user_id = user["id"]
    company_email = user.get("email") or f"{user['username']}@demo.vadesiz.local"
    invoice_no = upload["invoice"].get("invoice_no") or upload["file_name"]
    outbox_subjects = set()
    if OUTBOX_PATH.exists():
        with OUTBOX_PATH.open(encoding="utf-8") as outbox:
            for line in outbox:
                outbox_subjects.add(json.loads(line)["subject"])
    email_messages = []
    with db.get_connection() as connection:
        for offer in offers:
            if offer["status"] not in {"beklemede", "open"}:
                continue
            subject = f"Yeni finansman teklifi · {invoice_no} · {offer['source']}-{offer['offer_id']}"
            body = (
                f"{offer['financier_name']} faturanıza "
                f"%{offer['discount_rate'] * 100:.2f}".replace(".", ",")
                + f" iskonto ile {_format_money(offer['net_amount'])} net teklif verdi."
            )
            for channel in ("panel", "email"):
                exists = connection.execute(
                    """
                    SELECT 1 FROM notifications
                    WHERE user_id = ? AND channel = ? AND subject = ?
                    """,
                    (user_id, channel, subject),
                ).fetchone()
                if not exists:
                    connection.execute(
                        """
                        INSERT INTO notifications (user_id, channel, subject, body)
                        VALUES (?, ?, ?, ?)
                        """,
                        (user_id, channel, subject, body),
                    )
            if subject not in outbox_subjects:
                email_messages.append(
                    {"to": company_email, "subject": subject, "body": body}
                )
                outbox_subjects.add(subject)
    if email_messages:
        OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUTBOX_PATH.open("a", encoding="utf-8") as outbox:
            for message in email_messages:
                outbox.write(
                    json.dumps(
                        {"at": datetime.now(timezone.utc).isoformat(), **message},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    return len(email_messages)


def _format_money(amount):
    return f"{float(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " TL"


def invoice_fingerprint_seen(fingerprint, exclude_upload_id=None):
    if not fingerprint:
        return False
    with db.get_connection() as connection:
        if exclude_upload_id is None:
            row = connection.execute(
                "SELECT 1 FROM uploads WHERE invoice_fingerprint = ? LIMIT 1",
                (fingerprint,),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT 1 FROM uploads
                WHERE invoice_fingerprint = ? AND id != ? LIMIT 1
                """,
                (fingerprint, exclude_upload_id),
            ).fetchone()
    return row is not None


def open_financing(user, ip_address, upload_id, risk_score):
    status = "incelemede" if risk_score >= 60 else "teklif_bekliyor"
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE uploads SET status = ?
            WHERE id = ? AND company_vkn = ? AND status = 'incelemede'
            """,
            (status, upload_id, user.get("company_vkn")),
        )
        if cursor.rowcount != 1:
            raise ValueError("Fatura finansmana açılamadı; durumunu yenileyip tekrar kontrol edin.")
    db.log_audit(
        "financing_opened",
        user,
        ip_address,
        {"upload_id": upload_id, "risk_score": risk_score, "status": status},
    )
    return status


def _notify_financiers(connection, upload_id, accepted_offer_id, transfer_id=None):
    rows = connection.execute(
        """
        SELECT DISTINCT offer.financier_user_id, offer.id, offer.status
        FROM offers AS offer
        WHERE offer.upload_id = ? AND offer.financier_user_id IS NOT NULL
          AND offer.status IN ('kabul', 'red')
        """,
        (upload_id,),
    ).fetchall()
    for row in rows:
        if accepted_offer_id is not None and row["id"] == accepted_offer_id:
            subject = "Finansman teklifiniz kabul edildi"
            body = f"Teklifiniz kabul edildi. DEMO / MOCK transfer kodu: {transfer_id}"
        else:
            subject = "Fatura için başka bir teklif kabul edildi"
            body = "Fatura başka bir finansörün teklifiyle finanse edildi."
        connection.execute(
            """
            INSERT INTO notifications (user_id, channel, subject, body)
            VALUES (?, 'panel', ?, ?)
            """,
            (row["financier_user_id"], subject, body),
        )


def accept_offer(user, ip_address, upload_id, offer, transfer):
    invoice_no = None
    with db.get_connection() as connection:
        upload = connection.execute(
            """
            SELECT invoice_no, extracted_json FROM uploads
            WHERE id = ? AND company_vkn = ?
            """,
            (upload_id, user.get("company_vkn")),
        ).fetchone()
        if not upload:
            raise ValueError("Fatura bulunamadı veya bu hesaba ait değil.")
        invoice = json.loads(upload["extracted_json"] or "{}")
        invoice_no = invoice.get("invoice_no") or upload["invoice_no"]
        if not invoice_no:
            raise ValueError("Faturanın numarası olmadığı için teklif kabul edilemiyor.")
        deal = connection.execute(
            "SELECT 1 FROM deals WHERE invoice_no = ?", (invoice_no,)
        ).fetchone()
        if deal:
            raise ValueError("Bu fatura için daha önce transfer kaydı oluşturulmuş.")

        if offer["source"] == "upload":
            current = connection.execute(
                """
                SELECT id, financier_user_id FROM offers
                WHERE id = ? AND upload_id = ? AND status = 'beklemede'
                """,
                (offer["offer_id"], upload_id),
            ).fetchone()
            if not current:
                raise ValueError("Teklif artık kabul edilebilir durumda değil.")
            connection.execute(
                "UPDATE offers SET status = 'kabul' WHERE id = ?", (offer["offer_id"],)
            )
            connection.execute(
                """
                UPDATE offers SET status = 'red'
                WHERE upload_id = ? AND id != ? AND status = 'beklemede'
                """,
                (upload_id, offer["offer_id"]),
            )
            connection.execute(
                """
                UPDATE legacy_offers SET status = 'rejected'
                WHERE invoice_no = ? AND status = 'open'
                """,
                (invoice_no,),
            )
        else:
            current = connection.execute(
                """
                SELECT id FROM legacy_offers
                WHERE id = ? AND invoice_no = ? AND status = 'open'
                """,
                (offer["offer_id"], invoice_no),
            ).fetchone()
            if not current:
                raise ValueError("Teklif artık kabul edilebilir durumda değil.")
            connection.execute(
                "UPDATE legacy_offers SET status = 'accepted' WHERE id = ?",
                (offer["offer_id"],),
            )
            connection.execute(
                """
                UPDATE legacy_offers SET status = 'rejected'
                WHERE invoice_no = ? AND id != ? AND status = 'open'
                """,
                (invoice_no, offer["offer_id"]),
            )
            connection.execute(
                """
                UPDATE offers SET status = 'red'
                WHERE upload_id = ? AND status = 'beklemede'
                """,
                (upload_id,),
            )
        connection.execute(
            """
            INSERT INTO deals (invoice_no, offer_id, transfer_id)
            VALUES (?, NULL, ?)
            """,
            (invoice_no, transfer["transfer_id"]),
        )
        connection.execute(
            "UPDATE uploads SET status = 'finanse_edildi' WHERE id = ?",
            (upload_id,),
        )
        accepted_offer_id = offer["offer_id"] if offer["source"] == "upload" else None
        _notify_financiers(connection, upload_id, accepted_offer_id, transfer["transfer_id"])

    detail = {
        "upload_id": upload_id,
        "invoice_no": invoice_no,
        "offer_id": offer["offer_id"],
        "amount": transfer["amount"],
        "transfer_id": transfer["transfer_id"],
    }
    db.log_audit("offer_accepted", user, ip_address, detail)
    db.log_audit("transfer_mock", user, ip_address, detail)


def reject_offer(user, ip_address, upload_id, offer):
    with db.get_connection() as connection:
        upload = connection.execute(
            """
            SELECT up.invoice_no, up.extracted_json FROM uploads AS up
            WHERE up.id = ? AND up.company_vkn = ?
            """,
            (upload_id, user.get("company_vkn")),
        ).fetchone()
        if not upload:
            raise ValueError("Fatura bulunamadı veya bu hesaba ait değil.")
        invoice = json.loads(upload["extracted_json"] or "{}")
        invoice_no = invoice.get("invoice_no") or upload["invoice_no"]
        if offer["source"] == "upload":
            cursor = connection.execute(
                """
                UPDATE offers SET status = 'red'
                WHERE id = ? AND upload_id = ? AND status = 'beklemede'
                """,
                (offer["offer_id"], upload_id),
            )
        else:
            cursor = connection.execute(
                """
                UPDATE legacy_offers SET status = 'rejected'
                WHERE id = ? AND invoice_no = ? AND status = 'open'
                """,
                (offer["offer_id"], invoice_no),
            )
        if cursor.rowcount != 1:
            raise ValueError("Teklif artık reddedilebilir durumda değil.")
    db.log_audit(
        "offer_rejected",
        user,
        ip_address,
        {"upload_id": upload_id, "offer_id": offer["offer_id"]},
    )


def list_notifications(user_id):
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, channel, subject, body, read_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def unread_notification_count(user_id):
    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL",
            (user_id,),
        ).fetchone()
    return row[0]


def mark_notification_read(user, ip_address, notification_id):
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE notifications SET read_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ? AND read_at IS NULL
            """,
            (notification_id, user["id"]),
        )
    if cursor.rowcount:
        db.log_audit(
            "notification_read",
            user,
            ip_address,
            {"notification_id": notification_id},
        )
