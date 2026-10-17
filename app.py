"""Streamlit UI for the first Vadesiz demo."""
import csv
import html
import hashlib
import io
import json
import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

import db
import fraud
import gemma
import mocks
import ui

ROOT = Path(__file__).resolve().parent
SAMPLE_DIR = ROOT / "samples"
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


@st.cache_data(show_spinner=False)
def _cached_risk_report(invoice_no, invoice_json, buyer_json):
    return gemma.risk_report(json.loads(invoice_json), json.loads(buyer_json))


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


def _show_analysis(result):
    invoice = result["invoice"]
    st.subheader("Fatura bilgileri")
    st.write(f"**Fatura no:** {invoice.get('invoice_no', '—')}")
    st.write(
        f"**Satıcı:** {invoice.get('seller_name') or '—'} (VKN: {invoice.get('seller_vkn') or '—'})"
        f" → **Alıcı:** {invoice.get('buyer_name') or '—'} (VKN: {invoice.get('buyer_vkn') or '—'})"
    )
    st.write(
        f"**Düzenleme tarihi:** {invoice.get('issue_date') or '—'} · "
        f"**Vade:** {invoice.get('due_date') or '—'} · "
        f"**İrsaliye no:** {invoice.get('irsaliye_no') or '—'}"
    )
    approval = {True: "Onaylandı", False: "Onaylanmadı", None: "Belgede belirtilmemiş"}
    st.write(f"**Alıcı onayı:** {approval.get(invoice.get('buyer_approved'), 'Belgede belirtilmemiş')}")
    st.write("**Fatura kalemleri**")
    for item in invoice.get("items", []):
        quantity = item.get("quantity", "—")
        unit = item.get("unit", "")
        unit_price = _format_tl(item.get("unit_price"))
        st.write(f"- {item.get('description', '—')} · {quantity} {unit} × {unit_price}")
    st.write(
        f"**Ara toplam:** {_format_tl(invoice.get('subtotal'))} · "
        f"**KDV:** {_format_tl(invoice.get('kdv'))} · "
        f"**Genel toplam:** {_format_tl(invoice.get('total'))}"
    )
    score = result["score"]
    st.metric("Risk puanı", f"{score}/100")
    if result["flags"]:
        st.warning("İnceleme gerekli — bu araç faturayı otomatik reddetmez.")
        st.subheader("Tespit edilen bayraklar")
        for flag in result["flags"]:
            label = FLAG_LABELS.get(flag["code"], flag["code"])
            st.markdown(f"- **{label}** — {flag['detail']}")
    else:
        st.success("Otomatik kurallarda belirgin bir uyarı bulunmadı; yine de insan incelemesi gerekir.")
    st.subheader("Gemma açıklaması")
    st.write(result["explanation"])


def _invoice_with_gib_approval(invoice, invoices):
    enriched = dict(invoice)
    verification = mocks.verify_invoice(invoice, invoices)
    enriched["buyer_approved"] = verification["buyer_approved"]
    return enriched


def _display_offer_workflow(invoice, user, ip_address):
    invoice_no = invoice.get("invoice_no")
    if not invoice_no:
        return
    st.divider()
    st.subheader("Finansör teklifleri")
    offers = db.list_offers(invoice_no)
    deal = db.get_deal(invoice_no)
    if deal:
        st.success(
            f"Teklif kabul edildi: {deal.get('financier_name') or 'Finansör'} — "
            f"{_format_tl(deal.get('net_amount'))} net. "
            f"DEMO / MOCK transfer kodu: {deal['transfer_id']}"
        )
        return
    if not offers:
        st.info("Bu fatura için henüz finansör teklifi yok.")
        return

    st.dataframe(
        [
            {
                "Finansör": offer["financier_name"],
                "İskonto": f"%{offer['discount_rate'] * 100:.2f}".replace(".", ","),
                "Net ödeme": _format_tl(offer["net_amount"]),
                "Durum": "Açık" if offer["status"] == "open" else offer["status"],
            }
            for offer in offers
        ],
        hide_index=True,
        use_container_width=True,
    )
    open_offers = [offer for offer in offers if offer["status"] == "open"]
    if open_offers:
        comparison_key = tuple(
            (offer["id"], offer["discount_rate"], offer["net_amount"]) for offer in open_offers
        )
        cached = st.session_state.setdefault("offer_comparisons", {})
        if comparison_key not in cached:
            try:
                cached[comparison_key] = gemma.compare_offers(open_offers)
            except RuntimeError as exc:
                st.error(f"Gemma teklif karşılaştırması alınamadı: {exc}")
        recommendation = cached.get(comparison_key)
        if isinstance(recommendation, dict):
            st.info(
                f"**Gemma önerisi:** {recommendation.get('recommendation', '—')}  \n"
                f"{recommendation.get('reason', '')}"
            )
        elif recommendation is not None:
            st.warning("Gemma geçerli karşılaştırma JSON'u döndürmedi:")
            st.code(recommendation)

        selected_offer_id = st.selectbox(
            "Kabul edilecek teklif",
            [offer["id"] for offer in open_offers],
            format_func=lambda offer_id: next(
                f"{offer['financier_name']} — {_format_tl(offer['net_amount'])} net"
                for offer in open_offers if offer["id"] == offer_id
            ),
            key=f"offer_choice_{invoice_no}",
        )
        if st.button("Teklifi kabul et", key=f"accept_offer_{invoice_no}"):
            selected = next(offer for offer in open_offers if offer["id"] == selected_offer_id)
            transfer = mocks.bank_transfer(invoice_no, selected["net_amount"])
            try:
                db.create_deal(
                    invoice_no,
                    selected["id"],
                    transfer["transfer_id"],
                    audit_user=user,
                    ip_address=ip_address,
                    transfer_amount=transfer["amount"],
                )
            except sqlite3.Error as exc:
                st.error(f"Teklif kabul edilemedi: {exc}")
                return
            st.success(
                f"DEMO / MOCK transfer tamamlandı: {_format_tl(transfer['amount'])} · "
                f"İşlem kodu: {transfer['transfer_id']}"
            )
            st.rerun()
    else:
        st.info("Bu faturadaki teklifler artık açık değil.")


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


def _detector_graph_html(companies, invoices, invoice_flags):
    company_by_vkn = {company["vkn"]: company for company in companies}
    totals = {company["vkn"]: 0.0 for company in companies}
    suspicious_vkns = set()
    suspicious_codes = {"network_cycle", "shell_company", "invoice_broker"}
    for invoice in invoices:
        seller_vkn = invoice.get("seller_vkn")
        if seller_vkn in totals:
            totals[seller_vkn] += float(invoice.get("total") or 0)
        codes = {flag["code"] for flag in invoice_flags[invoice["invoice_no"]]}
        if codes & suspicious_codes:
            suspicious_vkns.update(
                vkn for vkn in (seller_vkn, invoice.get("buyer_vkn")) if vkn in company_by_vkn
            )

    highest_total = max(totals.values(), default=0) or 1
    network = Network(
        height="620px",
        width="100%",
        directed=True,
        notebook=False,
        cdn_resources="in_line",
    )
    for company in companies:
        vkn = company["vkn"]
        total = totals[vkn]
        node_size = 15 + 45 * math.sqrt(total / highest_total)
        color = "#d94b4b" if vkn in suspicious_vkns else "#37a66b"
        title = (
            f"{html.escape(company.get('name', vkn))}<br>"
            f"Satıcı faturaları toplamı: {html.escape(_format_tl(total))}"
        )
        network.add_node(
            vkn,
            label=company.get("name", vkn),
            title=title,
            size=node_size,
            color=color,
        )

    for index, invoice in enumerate(invoices):
        codes = {flag["code"] for flag in invoice_flags[invoice["invoice_no"]]}
        suspicious = bool(codes & suspicious_codes)
        labels = [
            FLAG_LABELS.get(flag["code"], flag["code"])
            for flag in invoice_flags[invoice["invoice_no"]]
        ]
        title = (
            f"Fatura: {html.escape(str(invoice.get('invoice_no', '—')))}<br>"
            f"Tutar: {html.escape(_format_tl(invoice.get('total')))}"
        )
        if labels:
            title += "<br>Bayraklar: " + html.escape(", ".join(labels))
        network.add_edge(
            invoice["seller_vkn"],
            invoice["buyer_vkn"],
            id=f"invoice-{index}",
            label=invoice.get("invoice_no", ""),
            title=title,
            color="#d94b4b" if suspicious else "#37a66b",
            arrows="to",
        )
    return network.generate_html()


def _show_detector_panel(companies, invoices):
    st.header("Dedektör")
    st.caption("Şirketler düğüm, faturalar satıcıdan alıcıya yönlü kenardır; renkler kural tabanlı sinyallerdir.")
    invoices_with_approval = [
        _invoice_with_gib_approval(invoice, invoices) for invoice in invoices
    ]
    flags_by_no = {
        invoice["invoice_no"]: fraud.analyze_invoice(invoice, companies, invoices)
        for invoice in invoices_with_approval
    }
    st.subheader("Fatura ağı")
    st.caption("Düğüm büyüklüğü satıcının fatura hacmine göre ölçeklenir. Yeşil: seçili ağ bayrağı yok · Kırmızı: döngü, paravan veya fatura aracılığı sinyali.")
    components.html(
        _detector_graph_html(companies, invoices_with_approval, flags_by_no),
        height=640,
        scrolling=True,
    )

    company_by_vkn = {company["vkn"]: company for company in companies}
    risk_rows = []
    for invoice in invoices_with_approval:
        flags = flags_by_no[invoice["invoice_no"]]
        risk_rows.append({
            "Fatura no": invoice["invoice_no"],
            "Satıcı": company_by_vkn.get(invoice["seller_vkn"], {}).get("name", invoice["seller_vkn"]),
            "Alıcı": company_by_vkn.get(invoice["buyer_vkn"], {}).get("name", invoice["buyer_vkn"]),
            "Toplam": _format_tl(invoice.get("total")),
            "Risk puanı": fraud.risk_score(flags),
            "Bayraklar": ", ".join(FLAG_LABELS.get(flag["code"], flag["code"]) for flag in flags) or "Yok",
        })
    top_risks = sorted(
        risk_rows,
        key=lambda row: (-row["Risk puanı"], row["Fatura no"]),
    )[:10]
    st.subheader("En yüksek riskli 10 fatura")
    st.dataframe(top_risks, hide_index=True, use_container_width=True)

    suspicious_codes = {"network_cycle", "shell_company", "invoice_broker"}
    suspicious_invoices = [
        invoice for invoice in invoices_with_approval
        if any(flag["code"] in suspicious_codes for flag in flags_by_no[invoice["invoice_no"]])
    ]
    st.subheader("Kırmızı ağ raporu")
    if not suspicious_invoices:
        st.info("Gemma incelemesi için kırmızı ağ sinyali bulunamadı.")
        return
    network_summary = {
        "companies": [
            {
                "vkn": company["vkn"],
                "name": company["name"],
                "sector": company.get("sector"),
            }
            for company in companies
            if any(
                company["vkn"] in (invoice.get("seller_vkn"), invoice.get("buyer_vkn"))
                for invoice in suspicious_invoices
            )
        ],
        "invoices": [
            {
                "invoice_no": invoice["invoice_no"],
                "seller_vkn": invoice["seller_vkn"],
                "buyer_vkn": invoice["buyer_vkn"],
                "total": invoice.get("total"),
                "flags": [
                    FLAG_LABELS.get(flag["code"], flag["code"])
                    for flag in flags_by_no[invoice["invoice_no"]]
                    if flag["code"] in suspicious_codes
                ],
            }
            for invoice in suspicious_invoices
        ],
    }
    if st.button("Gemma'dan şüpheli ağ raporu al"):
        with st.spinner("Gemma kırmızı ağı inceliyor..."):
            try:
                st.session_state["detector_network_report"] = gemma.suspicious_network_report(network_summary)
            except RuntimeError as exc:
                st.error(f"Gemma ağ raporu alınamadı: {exc}")
    if "detector_network_report" in st.session_state:
        st.write(st.session_state["detector_network_report"])


def _request_metadata():
    ip_address = getattr(st.context, "ip_address", None)
    if not isinstance(ip_address, str) or not ip_address.strip():
        ip_address = "127.0.0.1"
    headers = getattr(st.context, "headers", None)
    user_agent = headers.get("User-Agent", "") if headers else ""
    if not isinstance(user_agent, str):
        user_agent = ""
    return ip_address, user_agent


def _show_audit_ledger():
    st.header("Kayıt Defteri")
    companies, actions = db.audit_filter_options()
    company_options = {"Tüm şirketler": ""}
    company_options.update({
        f"{company['name']} · {company['vkn']}": company["vkn"]
        for company in companies
    })
    filter_columns = st.columns(4)
    selected_company = filter_columns[0].selectbox(
        "Şirket",
        list(company_options),
        key="audit_company_filter",
    )
    start_date = filter_columns[1].date_input(
        "Başlangıç",
        value=date.today() - timedelta(days=30),
        key="audit_start_date",
    )
    end_date = filter_columns[2].date_input(
        "Bitiş",
        value=date.today(),
        key="audit_end_date",
    )
    action_options = {"Tüm işlemler": ""}
    action_options.update({action: action for action in actions})
    selected_action = filter_columns[3].selectbox(
        "İşlem",
        list(action_options),
        key="audit_action_filter",
    )

    records = db.list_audit_records(
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        company_vkn=company_options[selected_company],
        action=action_options[selected_action],
    )
    st.caption(f"{len(records)} kayıt")
    csv_output = io.StringIO()
    columns = (
        "time",
        "company",
        "user",
        "ip",
        "file",
        "sha256",
        "invoice_no",
        "risk",
        "status",
        "action",
    )
    writer = csv.DictWriter(csv_output, fieldnames=columns)
    writer.writeheader()
    table_rows = []
    for record in records:
        row = {
            "time": record["at"],
            "company": record["company_name"] or record["company_vkn"] or "—",
            "user": record["username"],
            "ip": record["ip_address"],
            "file": record["file_name"] or "—",
            "sha256": record["file_sha256"] or "",
            "invoice_no": record["invoice_no"] or "—",
            "risk": record["risk_score"] if record["risk_score"] is not None else "—",
            "status": record["status"] or "—",
            "action": record["action"],
        }
        writer.writerow(row)
        cells = []
        for column in columns:
            value = str(row[column])
            if column == "sha256" and value:
                cell = (
                    f'<td title="{html.escape(value, quote=True)}">'
                    f"{html.escape(value[:16])}…</td>"
                )
            else:
                cell = f"<td>{html.escape(value)}</td>"
            cells.append(cell)
        table_rows.append("<tr>" + "".join(cells) + "</tr>")
    headers = (
        "Zaman",
        "Şirket",
        "Kullanıcı",
        "IP",
        "Dosya",
        "SHA-256",
        "Fatura no",
        "Risk",
        "Durum",
        "İşlem",
    )
    table_html = (
        '<div style="overflow-x:auto"><table class="vadesiz-audit-table"><thead><tr>'
        + "".join(f"<th>{header}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table></div>"
    )
    st.download_button(
        "CSV dışa aktar",
        data=csv_output.getvalue().encode("utf-8-sig"),
        file_name="vadesiz-kayit-defteri.csv",
        mime="text/csv",
        use_container_width=False,
    )
    st.markdown(table_html, unsafe_allow_html=True)


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


def main():
    st.set_page_config(page_title="Vadesiz", page_icon="🧾", layout="wide")
    ui.apply_styles()
    db.init_db()
    user = st.session_state.get("authenticated_user")
    ip_address, user_agent = _request_metadata()
    if not user:
        ui.render_topbar()
        authenticated_user = ui.render_login(db.authenticate_user, ip_address)
        if authenticated_user:
            st.session_state["authenticated_user"] = authenticated_user
            st.rerun()
        ui.render_footer()
        return

    if ui.render_topbar(user):
        db.logout_user(user, ip_address)
        st.session_state.pop("authenticated_user", None)
        st.rerun()

    st.caption("KOBİ'ler için fatura finansmanı • Yerel yapay zekâ ile demo")
    companies, invoices = fraud.load_demo_data()
    if user["role"] == "finansor":
        _show_header_metrics(companies, invoices)
        _show_financier_panel(companies, invoices, user, ip_address)
        ui.render_footer()
        return
    if user["role"] == "denetim":
        audit_page = st.sidebar.selectbox(
            "Denetim sayfası",
            ("Dedektör", "Kayıt Defteri"),
        )
        if audit_page == "Dedektör":
            _show_header_metrics(companies, invoices)
            _show_detector_panel(companies, invoices)
        else:
            _show_audit_ledger()
        ui.render_footer()
        return

    _show_header_metrics(companies, invoices)
    st.sidebar.info("DEMO / MOCK: GİB, kredi skoru, banka transferi ve e-imza gerçek servis değildir.")
    st.header("Faturanı yükle")
    sample_files = sorted(SAMPLE_DIR.glob("*.png"))
    sample_names = ["— Örnek seçmeden yükle —", *[path.name for path in sample_files]]
    selected_sample = st.selectbox("Demo görseli", sample_names)
    uploaded = st.file_uploader("Fatura görseli (PNG veya JPG)", type=("png", "jpg", "jpeg"))

    image_bytes = None
    filename = None
    if uploaded is not None:
        image_bytes = uploaded.getvalue()
        filename = uploaded.name
    elif selected_sample != sample_names[0]:
        sample_path = SAMPLE_DIR / selected_sample
        image_bytes = sample_path.read_bytes()
        filename = sample_path.name

    if image_bytes is None:
        st.info("Bir demo görseli seçin veya kendi fatura görselinizi yükleyin.")
        ui.render_footer()
        return

    st.image(image_bytes, caption=filename, use_container_width=True)
    digest = hashlib.sha256(image_bytes).hexdigest()
    if st.button("Gemma ile faturayı oku ve risk kontrolü yap", type="primary"):
        upload = db.create_upload(
            user,
            user.get("company_vkn"),
            ip_address,
            user_agent,
            filename,
            image_bytes,
        )
        if upload["duplicate"]:
            st.error(
                "Bu dosya daha önce yüklenmiş. SHA-256 eşleşmesi nedeniyle tekrar işlenmedi "
                "ve denetim kaydına alındı."
            )
            ui.render_footer()
            return
        st.session_state["active_upload_id"] = upload["id"]
        st.session_state["active_upload_digest"] = digest
        with st.spinner("Gemma faturayı okuyor; ilk çağrı daha uzun sürebilir..."):
            try:
                extracted = gemma.extract_invoice(image_bytes, filename)
            except RuntimeError as exc:
                db.log_audit(
                    "extract",
                    user,
                    ip_address,
                    {"upload_id": upload["id"], "error": str(exc)},
                )
                st.error(str(exc))
                st.info("Ollama'nın http://localhost:11434 adresinde çalıştığını ve gemma4 modelinin kurulu olduğunu kontrol edin.")
                ui.render_footer()
                return
        if isinstance(extracted, dict) and _is_complete_invoice(extracted):
            gib_result = mocks.verify_invoice(extracted, invoices)
            extracted["buyer_approved"] = gib_result["buyer_approved"]
            try:
                result = _run_checks(extracted, companies, invoices)
                saved = db.save_upload_extraction(
                    upload["id"],
                    user,
                    ip_address,
                    result["invoice"],
                    result["score"],
                    result["flags"],
                )
                result["flags"] = saved["flags"]
                result["score"] = fraud.risk_score(saved["flags"])
                if saved["duplicate"]:
                    st.error("Fatura bilgileri daha önce yüklenmiş; kayıt reddedildi ve denetime alındı.")
                st.session_state["invoice_analysis"] = result
                st.session_state["invoice_analysis_digest"] = digest
            except RuntimeError as exc:
                st.error(f"Gemma açıklaması alınamadı: {exc}")
                ui.render_footer()
                return
        else:
            st.session_state["invoice_raw"] = (
                json.dumps(extracted, ensure_ascii=False, indent=2)
                if isinstance(extracted, dict)
                else extracted
            )
            st.session_state["invoice_raw_digest"] = digest
            st.warning("Gemma çıktısı geçersiz veya eksik. JSON'u düzeltip tekrar deneyebilirsiniz.")
            db.log_audit(
                "extract",
                user,
                ip_address,
                {"upload_id": upload["id"], "parse_success": False},
            )

    if st.session_state.get("invoice_raw_digest") == digest:
        raw_text = st.text_area("Gemma çıktısını düzeltin (JSON)", value=st.session_state.get("invoice_raw", ""))
        if st.button("Düzeltilmiş JSON ile devam et"):
            try:
                corrected = json.loads(raw_text)
                if not isinstance(corrected, dict) or not _is_complete_invoice(corrected):
                    raise ValueError("Fatura no, tarih, satıcı/alıcı VKN, kalemler ve toplam alanlarını kontrol edin.")
                gib_result = mocks.verify_invoice(corrected, invoices)
                corrected["buyer_approved"] = gib_result["buyer_approved"]
                result = _run_checks(corrected, companies, invoices)
                upload_id = st.session_state.get("active_upload_id")
                if upload_id and st.session_state.get("active_upload_digest") == digest:
                    saved = db.save_upload_extraction(
                        upload_id,
                        user,
                        ip_address,
                        result["invoice"],
                        result["score"],
                        result["flags"],
                    )
                    result["flags"] = saved["flags"]
                    result["score"] = fraud.risk_score(saved["flags"])
                st.session_state["invoice_analysis"] = result
                st.session_state["invoice_analysis_digest"] = digest
                del st.session_state["invoice_raw"]
                del st.session_state["invoice_raw_digest"]
            except (json.JSONDecodeError, ValueError) as exc:
                st.error(f"JSON düzeltmesi geçersiz: {exc}")
            except RuntimeError as exc:
                st.error(f"Gemma açıklaması alınamadı: {exc}")

    if st.session_state.get("invoice_analysis_digest") == digest:
        result = st.session_state["invoice_analysis"]
        _show_analysis(result)
        _display_offer_workflow(result["invoice"], user, ip_address)

    st.caption("Risk puanı yalnızca karar desteğidir. Nihai değerlendirme insana aittir.")
    ui.render_footer()


if __name__ == "__main__":
    main()
