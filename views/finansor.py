"""Financier marketplace and own-offers views."""
import html
import json
import sqlite3

import streamlit as st

import db
import fraud
import gemma
import mocks
import repo_market
import ui
from .common import FLAG_LABELS, _format_tl, _show_header_metrics


@st.cache_data(show_spinner=False)
def _cached_risk_report(invoice_no, invoice_json, buyer_json):
    return gemma.risk_report(json.loads(invoice_json), json.loads(buyer_json))


def _risk_label(score):
    if score < 30:
        return "Düşük", "low"
    if score < 60:
        return "Orta", "medium"
    return "Yüksek", "high"


def _market_table(records):
    rows = []
    for record in records:
        invoice = record["invoice"]
        score = record["risk_score"]
        risk, risk_class = _risk_label(score)
        days = fraud.days_to_due(invoice)
        credit = mocks.buyer_credit_score(invoice.get("buyer_vkn"))
        cells = (
            record["seller_name"],
            record["buyer"].get("name", invoice.get("buyer_vkn", "—")),
            _format_tl(invoice.get("total")),
            invoice.get("due_date", "—"),
            f"{days} gün",
            f"{credit['score']} / 900",
            f'<span class="market-risk market-risk-{risk_class}">{risk} · {score}</span>',
            str(record["offer_count"]),
        )
        rows.append("<tr>" + "".join(
            f"<td>{cell if index == 6 else html.escape(str(cell))}</td>"
            for index, cell in enumerate(cells)
        ) + "</tr>")
    headers = ("Satıcı", "Alıcı", "Tutar", "Vade", "Kalan", "Mock kredi skoru", "Risk", "Teklif")
    return (
        '<div class="market-table-wrap"><table class="market-table"><thead><tr>'
        + "".join(f"<th>{header}</th>" for header in headers)
        + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )


def _filter_market(records):
    sectors = sorted({record["seller"].get("sector", "Belirtilmemiş") for record in records})
    total_values = [float(record["invoice"].get("total") or 0) for record in records]
    minimum = min(total_values, default=0.0)
    maximum = max(total_values, default=1000000.0)
    if maximum <= minimum:
        maximum = minimum + 1
    columns = st.columns(4)
    sector = columns[0].selectbox("Sektör", ["Tüm sektörler", *sectors], key="market_sector")
    amount_range = columns[1].slider(
        "Tutar aralığı (TL)",
        min_value=float(minimum),
        max_value=float(maximum),
        value=(float(minimum), float(maximum)),
        step=float(max(1000, round((maximum - minimum) / 100))),
        key="market_amount_range",
    )
    due_limit = columns[2].selectbox(
        "Vade içinde",
        ("Tümü", "30 gün", "60 gün", "90 gün", "120 gün"),
        key="market_due_limit",
    )
    max_risk = columns[3].slider("En yüksek risk", 0, 100, 100, key="market_max_risk")
    due_days = int(due_limit.split()[0]) if due_limit != "Tümü" else None
    filtered = []
    for record in records:
        invoice = record["invoice"]
        amount = float(invoice.get("total") or 0)
        days = fraud.days_to_due(invoice)
        if sector != "Tüm sektörler" and record["seller"].get("sector", "Belirtilmemiş") != sector:
            continue
        if not amount_range[0] <= amount <= amount_range[1] or record["risk_score"] > max_risk:
            continue
        if due_days is not None and days > due_days:
            continue
        filtered.append(record)
    return filtered


def _show_risk_report(record, invoices, suggested_rate):
    invoice = record["invoice"]
    buyer = record["buyer"]
    credit = mocks.buyer_credit_score(invoice.get("buyer_vkn"))
    days_to_due = fraud.days_to_due(invoice)
    context = {
        "company": buyer,
        "credit_score": credit,
        "gib_verification": mocks.verify_invoice(invoice, invoices),
        "flags": record["flags"],
        "risk_score": record["risk_score"],
        "base_discount_rate": suggested_rate,
        "days_to_due": days_to_due,
    }
    report_invoice = {key: value for key, value in invoice.items() if key != "scenario"}
    st.subheader("Gemma risk raporu")
    st.caption(
        f"Deterministik öneri: %{suggested_rate * 100:.2f}".replace(".", ",")
        + f" · Yıllık %45 × {days_to_due} gün / 365 + risk primi"
    )
    try:
        with st.spinner("Gemma risk raporunu hazırlıyor..."):
            report = _cached_risk_report(
                invoice.get("invoice_no", ""),
                json.dumps(report_invoice, ensure_ascii=False, sort_keys=True),
                json.dumps(context, ensure_ascii=False, sort_keys=True),
            )
    except RuntimeError as exc:
        st.error(f"Gemma risk raporu alınamadı: {exc}")
        return
    if isinstance(report, dict):
        st.info(report.get("summary", "Özet üretilemedi."))
        if report.get("discount_explanation"):
            st.write(report["discount_explanation"])
    else:
        st.warning("Gemma geçerli JSON döndürmedi; ham çıktı:")
        st.code(str(report))


def _show_market_detail(record, invoices, user, ip_address):
    invoice = record["invoice"]
    invoice_no = invoice.get("invoice_no", "—")
    flags = record["flags"]
    score = record["risk_score"]
    st.subheader("Fatura ayrıntıları")
    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            st.write(f"**Fatura no:** {invoice_no}")
            st.write(f"**Satıcı:** {record['seller_name']} · {invoice.get('seller_vkn', '—')}")
            st.write(f"**Alıcı:** {record['buyer'].get('name', '—')} · {invoice.get('buyer_vkn', '—')}")
            st.write(f"**Düzenlenme tarihi:** {invoice.get('issue_date', '—')}")
            st.write(f"**Vade:** {invoice.get('due_date', '—')} · {fraud.days_to_due(invoice)} gün kaldı")
        with right:
            st.write(f"**Toplam:** {_format_tl(invoice.get('total'))}")
            st.write(f"**İrsaliye:** {invoice.get('irsaliye_no') or 'Bulunmuyor'}")
            st.write(f"**Alıcı mock kredi skoru:** {mocks.buyer_credit_score(invoice.get('buyer_vkn'))['score']} / 900")
            st.write(f"**Durum:** {'Yeni yükleme' if record['preloaded'] else record['status']}")
        st.markdown("**Kalemler**")
        st.dataframe([
            {
                "Açıklama": item.get("description", "—"),
                "Miktar": item.get("quantity", "—"),
                "Birim": item.get("unit", "—"),
                "Birim fiyat": _format_tl(item.get("unit_price")),
            }
            for item in invoice.get("items", [])
        ], hide_index=True, use_container_width=True)
        st.markdown(f"**Risk puanı:** {score}/100 · {_risk_label(score)[0]}")
        if flags:
            for flag in flags:
                st.markdown(
                    f"- **{FLAG_LABELS.get(flag['code'], flag['code'])}** — "
                    f"{html.escape(str(flag['detail']))}"
                )
        else:
            st.write("Kural tabanlı bayrak bulunmadı.")

    try:
        suggested_rate = fraud.base_discount_rate(invoice, score)
    except ValueError as exc:
        st.error(f"İskonto oranı hesaplanamadı: {exc}")
        return
    _show_risk_report(record, invoices, suggested_rate)
    offers = repo_market.list_offers_for_upload(record["upload_id"]) if record["upload_id"] else []
    active_offer = next(
        (offer for offer in offers if offer["financier_user_id"] == user["id"]
         and offer["status"] in {"beklemede", "kabul"}),
        None,
    )
    if active_offer:
        if active_offer["status"] == "kabul":
            st.success("Bu fatura için teklifiniz kabul edildi.")
        else:
            st.info(
                f"Aktif teklifiniz: {_format_tl(active_offer['net_amount'])} net · "
                f"%{active_offer['discount_rate'] * 100:.2f}".replace(".", ",")
            )
            if st.button("Teklifi geri çek", key=f"withdraw_market_{active_offer['id']}"):
                try:
                    repo_market.withdraw_offer(active_offer["id"], user, ip_address)
                except (ValueError, sqlite3.Error, OSError) as exc:
                    st.error(f"Teklif geri çekilemedi: {exc}")
                else:
                    st.success("Teklif geri çekildi.")
                    st.rerun()
        return

    st.subheader("Teklif ver")
    total = float(invoice.get("total") or 0)
    if total <= 0:
        st.error("Faturanın tutarı geçerli değil; teklif oluşturulamadı.")
        return
    discount_rate = st.slider(
        "İskonto oranı",
        min_value=0.005,
        max_value=0.5,
        value=min(0.5, max(0.005, suggested_rate)),
        step=0.005,
        format="%.3f",
        key=f"market_rate_{invoice_no}",
    )
    net_amount = round(total * (1 - discount_rate), 2)
    st.metric("Net ödeme (otomatik)", _format_tl(net_amount))
    with st.form(f"market_offer_form_{invoice_no}"):
        note = st.text_area("KOBİ'ye not (isteğe bağlı)", max_chars=500)
        submitted = st.form_submit_button("Teklif ver", type="primary")
    if submitted:
        try:
            offer_id = repo_market.create_market_offer(
                record,
                user,
                ip_address,
                discount_rate,
                net_amount,
                note,
            )
        except (ValueError, sqlite3.Error, OSError) as exc:
            st.error(f"Teklif kaydedilemedi: {exc}")
        else:
            st.success(f"Teklif #{offer_id} kaydedildi; KOBİ paneli ve e-posta kutusu bilgilendirildi.")
            st.rerun()


def _show_marketplace(companies, invoices, user, ip_address):
    st.header("Fatura Pazarı")
    st.caption("Yalnızca teklif bekleyen ve teklif almış faturalar gösterilir. Mock kredi puanı bilgilendirme amaçlıdır.")
    records = repo_market.list_market_records(companies, invoices)
    records = _filter_market(records) if records else []
    if not records:
        st.info("Filtrelerle eşleşen fatura bulunamadı.")
        return
    st.markdown(_market_table(records), unsafe_allow_html=True)
    record_by_no = {record["invoice"]["invoice_no"]: record for record in records}
    selected_no = st.selectbox(
        "İncelemek için fatura seçin",
        ["", *record_by_no],
        format_func=lambda invoice_no: (
            "— Fatura seçin —" if not invoice_no else
            f"{invoice_no} · {_format_tl(record_by_no[invoice_no]['invoice'].get('total'))}"
        ),
        key="market_selected_invoice",
    )
    if selected_no:
        _show_market_detail(record_by_no[selected_no], invoices, user, ip_address)


def _show_my_offers(user):
    st.header("Tekliflerim")
    records = repo_market.list_financier_offers(user["id"])
    if not records:
        st.info("Henüz teklifiniz bulunmuyor.")
        return
    rows = []
    for record in records:
        invoice = record["invoice"]
        status = {
            "beklemede": "Beklemede",
            "kabul": "Kabul edildi",
            "red": "Reddedildi",
            "geri_cekildi": "Geri çekildi",
        }.get(record["status"], record["status"])
        rows.append({
            "Fatura no": record["invoice_no"] or invoice.get("invoice_no", "—"),
            "Satıcı": record["seller_name"] or "—",
            "Tutar": _format_tl(invoice.get("total")),
            "İskonto": f"%{record['discount_rate'] * 100:.2f}".replace(".", ","),
            "Net ödeme": _format_tl(record["net_amount"]),
            "Durum": status,
            "Tarih": record["created_at"],
        })
    st.dataframe(rows, hide_index=True, use_container_width=True)
    for record in records:
        if record["status"] == "kabul":
            invoice_no = record["invoice_no"] or record["invoice"].get("invoice_no")
            receipt = mocks.bank_transfer(invoice_no, record["net_amount"])
            with st.container(border=True):
                st.subheader(f"DEMO / MOCK · Transfer dekontu · {invoice_no}")
                st.write(f"**Satıcı:** {record['seller_name'] or '—'}")
                st.write(f"**Net tutar:** {_format_tl(receipt['amount'])}")
                st.code(receipt["transfer_id"])
                st.caption(receipt["service"])


def render(user, companies, invoices, ip_address):
    ui.market_styles()
    _show_header_metrics(companies, invoices)
    page = st.sidebar.radio("Finansör sayfası", ("Fatura Pazarı", "Tekliflerim"))
    if page == "Fatura Pazarı":
        _show_marketplace(companies, invoices, user, ip_address)
    else:
        _show_my_offers(user)
