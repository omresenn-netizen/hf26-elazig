"""Audit and invoice-network detector views."""
import csv
import html
import io
import math
import sqlite3
from datetime import date, timedelta

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

import db
import fraud
import gemma
import repo_market
import ui
from .common import FLAG_LABELS, _format_tl, _invoice_with_gib_approval, _show_header_metrics

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


def _show_review_queue(user, ip_address):
    st.header("İnceleme Kuyruğu")
    records = repo_market.list_uploads_for_review()
    if not records:
        st.success("İnceleme bekleyen yükleme yok.")
        return
    options = {str(record["id"]): record for record in records}
    st.dataframe([
        {
            "Fatura no": record["invoice"].get("invoice_no") or "Okuma bekleniyor",
            "Satıcı": record["seller_name"] or record.get("company_vkn") or "—",
            "Dosya": record["file_name"],
            "Risk": record["risk_score"] if record["risk_score"] is not None else "—",
            "Yükleme": record["uploaded_at"],
        }
        for record in records
    ], hide_index=True, use_container_width=True)
    selected_id = st.selectbox(
        "İncelenecek kayıt",
        ["", *options],
        format_func=lambda upload_id: (
            "— Kayıt seçin —" if not upload_id else
            f"{options[upload_id]['invoice'].get('invoice_no') or options[upload_id]['file_name']} "
            f"· #{upload_id}"
        ),
        key="review_upload",
    )
    if not selected_id:
        return
    record = options[selected_id]
    invoice = record["invoice"]
    with st.container(border=True):
        st.subheader(invoice.get("invoice_no") or record["file_name"])
        st.write(f"**Satıcı VKN:** {record.get('company_vkn') or '—'}")
        st.write(f"**Dosya:** {record['file_name']} · SHA-256 `{record['file_sha256'][:16]}…`")
        if invoice:
            st.write(f"**Alıcı VKN:** {invoice.get('buyer_vkn', '—')}")
            st.write(f"**Tutar:** {_format_tl(invoice.get('total'))} · **Vade:** {invoice.get('due_date', '—')}")
        st.write(f"**Risk:** {record['risk_score'] if record['risk_score'] is not None else '—'}/100")
        for flag in record["flags"]:
            st.markdown(
                f"- **{FLAG_LABELS.get(flag['code'], flag['code'])}** — "
                f"{html.escape(str(flag['detail']))}"
            )
        reason = st.text_input(
            "Reddetme nedeni",
            key=f"review_reason_{selected_id}",
            max_chars=500,
        )
        approve_col, reject_col = st.columns(2)
        if approve_col.button("Onayla ve pazara aç", key=f"review_approve_{selected_id}", type="primary"):
            try:
                repo_market.decide_review(int(selected_id), True, "", user, ip_address)
            except (ValueError, sqlite3.Error) as exc:
                st.error(f"Onay kaydedilemedi: {exc}")
            else:
                st.success("Fatura teklif bekliyor durumuna alındı.")
                st.rerun()
        if reject_col.button("Reddet", key=f"review_reject_{selected_id}"):
            try:
                repo_market.decide_review(int(selected_id), False, reason, user, ip_address)
            except (ValueError, sqlite3.Error) as exc:
                st.error(f"Reddetme kaydedilemedi: {exc}")
            else:
                st.success("Fatura reddedildi; gerekçe kayıt defterine yazıldı.")
                st.rerun()


def render(user, companies, invoices, ip_address):
    ui.market_styles()
    audit_page = st.sidebar.radio(
        "Denetim sayfası",
        ("Dedektör", "İnceleme Kuyruğu", "Kayıt Defteri"),
    )
    if audit_page == "Dedektör":
        _show_header_metrics(companies, invoices)
        _show_detector_panel(companies, invoices)
    elif audit_page == "İnceleme Kuyruğu":
        _show_review_queue(user, ip_address)
    else:
        _show_audit_ledger()
