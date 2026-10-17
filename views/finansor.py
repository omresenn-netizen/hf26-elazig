"""Financier marketplace and offer workflow."""
import json
import sqlite3

import streamlit as st

import db
import fraud
import gemma
import mocks
from .common import FLAG_LABELS, _format_tl, _invoice_with_gib_approval, _show_header_metrics

@st.cache_data(show_spinner=False)
def _cached_risk_report(invoice_no, invoice_json, buyer_json):
    return gemma.risk_report(json.loads(invoice_json), json.loads(buyer_json))

def _build_financier_rows(companies, invoices):
    company_by_vkn = {company["vkn"]: company for company in companies}
    rows = []
    for source in invoices:
        invoice = _invoice_with_gib_approval(source, invoices)
        flags = fraud.analyze_invoice(invoice, companies, invoices)
        deal = db.get_deal(invoice["invoice_no"])
        if deal:
            status = "Finansman tamamlandı"
        elif not mocks.verify_invoice(source, invoices)["verified"]:
            status = "GİB kaydı bulunamadı"
        elif invoice.get("buyer_approved") is False:
            status = "Alıcı onayı bekleniyor"
        elif flags:
            status = "İnsan incelemesi"
        else:
            status = "İncelemeye hazır"
        rows.append({
            "Fatura no": invoice["invoice_no"],
            "Satıcı": company_by_vkn.get(invoice["seller_vkn"], {}).get("name", invoice.get("seller_vkn")),
            "Alıcı": company_by_vkn.get(invoice["buyer_vkn"], {}).get("name", invoice.get("buyer_vkn")),
            "Toplam": _format_tl(invoice.get("total")),
            "Vade": invoice.get("due_date", "—"),
            "Risk": fraud.risk_score(flags),
            "Durum": status,
        })
    return rows

def _show_financier_panel(companies, invoices, user, ip_address):
    st.header("Finansör paneli")
    st.caption("Faturalar yerel kurgusal veri setinden alınır; risk puanı karar desteğidir.")
    rows = _build_financier_rows(companies, invoices)
    st.dataframe(rows, hide_index=True, use_container_width=True)

    invoice_by_no = {invoice["invoice_no"]: invoice for invoice in invoices}
    selected_no = st.selectbox(
        "İncelenecek fatura",
        list(invoice_by_no),
        format_func=lambda invoice_no: (
            f"{invoice_no} · {_format_tl(invoice_by_no[invoice_no].get('total'))}"
        ),
    )
    source = invoice_by_no[selected_no]
    invoice = _invoice_with_gib_approval(source, invoices)
    flags = fraud.analyze_invoice(invoice, companies, invoices)
    existing_deal = db.get_deal(selected_no)
    st.metric("Kural tabanlı risk puanı", f"{fraud.risk_score(flags)}/100")
    if flags:
        for flag in flags:
            st.markdown(f"- **{FLAG_LABELS.get(flag['code'], flag['code'])}** — {flag['detail']}")

    buyer = next((company for company in companies if company["vkn"] == invoice.get("buyer_vkn")), {})
    credit = mocks.buyer_credit_score(invoice.get("buyer_vkn"))
    st.subheader("Alıcı bilgileri")
    st.write(f"**Alıcı:** {buyer.get('name', '—')}")
    st.write(f"**Mock kredi skoru:** {credit['score']} / 900 · {credit['service']}")

    try:
        suggested_rate = fraud.base_discount_rate(invoice, fraud.risk_score(flags))
    except ValueError as exc:
        st.error(f"İskonto oranı hesaplanamadı: {exc}")
        return
    days_to_due = fraud.days_to_due(invoice)
    context = {
        "company": buyer,
        "credit_score": credit,
        "gib_verification": mocks.verify_invoice(source, invoices),
        "flags": flags,
        "risk_score": fraud.risk_score(flags),
        "base_discount_rate": suggested_rate,
        "days_to_due": days_to_due,
    }
    report_invoice = {key: value for key, value in invoice.items() if key != "scenario"}
    report = None
    with st.spinner("Gemma risk raporunu hazırlıyor..."):
        try:
            report = _cached_risk_report(
                selected_no,
                json.dumps(report_invoice, ensure_ascii=False, sort_keys=True),
                json.dumps(context, ensure_ascii=False, sort_keys=True),
            )
        except RuntimeError as exc:
            st.error(f"Gemma risk raporu alınamadı: {exc}")

    if isinstance(report, dict):
        st.subheader("Gemma risk raporu")
        st.write(report.get("summary", "Özet üretilemedi."))
        st.write(report.get("discount_explanation", ""))
        st.write(
            f"**Kural tabanlı iskonto oranı:** "
            f"%{suggested_rate * 100:.2f}".replace(".", ",")
            + f" · Yıllık %45 × {days_to_due} gün / 365 + risk primi"
        )
    elif report is not None:
        st.subheader("Gemma risk raporu")
        st.warning("Gemma geçerli JSON döndürmedi; ham çıktı:")
        st.code(report)

    if existing_deal:
        st.success(
            f"Bu fatura zaten finanse edilmiş. DEMO / MOCK transfer kodu: "
            f"{existing_deal['transfer_id']}"
        )
        return

    st.subheader("Teklif oluştur")
    invoice_total = float(invoice.get("total") or 0)
    current_rate = suggested_rate
    with st.form(f"offer_form_{selected_no}"):
        financier_name = st.text_input("Finansör adı", value="Vadesiz Demo Finans")
        discount_rate = st.number_input(
            "İskonto oranı",
            min_value=0.005,
            max_value=max(0.5, suggested_rate),
            value=current_rate,
            step=0.005,
            format="%.3f",
        )
        net_amount = st.number_input(
            "Net ödeme (TL)",
            min_value=0.0,
            max_value=max(invoice_total, 0.01),
            value=round(invoice_total * (1 - discount_rate), 2),
            step=100.0,
            format="%.2f",
        )
        submitted = st.form_submit_button("Teklifi kaydet")
    if submitted:
        if not financier_name.strip():
            st.error("Finansör adı boş olamaz.")
        elif invoice_total <= 0:
            st.error("Faturanın geçerli toplam tutarı yok; teklif oluşturulamadı.")
        else:
            try:
                offer_id = db.save_offer(
                    selected_no,
                    financier_name.strip(),
                    discount_rate,
                    net_amount,
                    audit_user=user,
                    ip_address=ip_address,
                )
            except sqlite3.Error as exc:
                st.error(f"Teklif kaydedilemedi: {exc}")
            else:
                st.success(f"Teklif kaydedildi (#{offer_id}): {_format_tl(net_amount)} net.")

def render(user, companies, invoices, ip_address):
    _show_header_metrics(companies, invoices)
    _show_financier_panel(companies, invoices, user, ip_address)
