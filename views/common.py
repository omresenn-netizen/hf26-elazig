"""Shared helpers for role-specific Vadesiz views."""
import streamlit as st

import db
import fraud
import gemma
import mocks

FLAG_LABELS = {
    "duplicate_invoice": "Mükerrer fatura",
    "invoice_broker": "Fatura aracılığı şüphesi",
    "year_end_cluster": "Yıl sonu fatura yoğunlaşması",
    "network_cycle": "Fatura ağında döngü",
    "shell_company": "Paravan şirket şüphesi",
    "buyer_not_approved": "Alıcı faturayı onaylamadı",
    "sector_mismatch": "Sektör ve ürün uyuşmazlığı",
    "capacity_outlier": "Kapasite aşımı şüphesi",
    "vague_item": "Belirsiz mal/hizmet açıklaması",
    "round_amount": "Yuvarlak tutar",
    "missing_delivery_note": "İrsaliye eksik",
}

def _show_header_metrics(companies, invoices):
    verified_count = 0
    review_count = 0
    for source in invoices:
        verified_count += bool(mocks.verify_invoice(source, invoices)["verified"])
        invoice = _invoice_with_gib_approval(source, invoices)
        review_count += bool(fraud.analyze_invoice(invoice, companies, invoices))
    metrics = (
        ("Fatura", len(invoices)),
        ("GİB doğrulandı", verified_count),
        ("İncelemede", review_count),
        ("Finansman hacmi", _format_tl(db.financing_volume())),
    )
    for column, (label, value) in zip(st.columns(4), metrics):
        column.metric(label, value)

def _run_checks(invoice, companies, invoices):
    flags = fraud.analyze_invoice(invoice, companies, invoices)
    explanation = gemma.explain_flags(invoice, flags)
    return {"invoice": invoice, "flags": flags, "score": fraud.risk_score(flags), "explanation": explanation}

def _is_complete_invoice(invoice):
    required = ("invoice_no", "issue_date", "seller_vkn", "buyer_vkn", "items", "total")
    if not all(invoice.get(field) is not None and invoice.get(field) != "" for field in required):
        return False
    items = invoice["items"]
    return isinstance(items, list) and bool(items) and all(
        isinstance(item, dict) and item.get("description") for item in items
    )

def _format_tl(value):
    if value is None:
        return "Okunamadı"
    if isinstance(value, str) and "," in value:
        value = value.replace(".", "").replace(",", ".").replace(" TL", "").replace("₺", "").strip()
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "Okunamadı"
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " TL"

def _invoice_with_gib_approval(invoice, invoices):
    enriched = dict(invoice)
    verification = mocks.verify_invoice(invoice, invoices)
    enriched["buyer_approved"] = verification["buyer_approved"]
    return enriched

def _request_metadata():
    ip_address = getattr(st.context, "ip_address", None)
    if not isinstance(ip_address, str) or not ip_address.strip():
        ip_address = "127.0.0.1"
    headers = getattr(st.context, "headers", None)
    user_agent = headers.get("User-Agent", "") if headers else ""
    if not isinstance(user_agent, str):
        user_agent = ""
    return ip_address, user_agent
