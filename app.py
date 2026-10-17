"""Streamlit UI for the first Vadesiz demo."""
import hashlib
import json
import sqlite3
from pathlib import Path

import streamlit as st

import db
import fraud
import gemma
import mocks

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


def _display_offer_workflow(invoice):
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
                db.create_deal(invoice_no, selected["id"], transfer["transfer_id"])
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


def _show_financier_panel(companies, invoices):
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
                )
            except sqlite3.Error as exc:
                st.error(f"Teklif kaydedilemedi: {exc}")
            else:
                st.success(f"Teklif kaydedildi (#{offer_id}): {_format_tl(net_amount)} net.")


def main():
    st.set_page_config(page_title="Vadesiz", page_icon="🧾", layout="centered")
    db.init_db()
    st.title("Vadesiz")
    st.caption("KOBİ'ler için fatura finansmanı • Yerel yapay zekâ ile demo")

    role = st.sidebar.selectbox("Panel", ("KOBİ paneli", "Finansör paneli", "Dedektör"))
    st.sidebar.info("DEMO / MOCK: GİB, kredi skoru, banka transferi ve e-imza gerçek servis değildir.")
    companies, invoices = fraud.load_demo_data()
    if role == "Finansör paneli":
        _show_financier_panel(companies, invoices)
        return
    if role != "KOBİ paneli":
        st.info("Dedektör paneli sonraki sürümde hazırlanacak.")
        return

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
        return

    st.image(image_bytes, caption=filename, use_container_width=True)
    digest = hashlib.sha256(image_bytes).hexdigest()
    if st.button("Gemma ile faturayı oku ve risk kontrolü yap", type="primary"):
        with st.spinner("Gemma faturayı okuyor; ilk çağrı daha uzun sürebilir..."):
            try:
                extracted = gemma.extract_invoice(image_bytes, filename)
            except RuntimeError as exc:
                st.error(str(exc))
                st.info("Ollama'nın http://localhost:11434 adresinde çalıştığını ve gemma4 modelinin kurulu olduğunu kontrol edin.")
                return
        if isinstance(extracted, dict) and _is_complete_invoice(extracted):
            gib_result = mocks.verify_invoice(extracted, invoices)
            extracted["buyer_approved"] = gib_result["buyer_approved"]
            try:
                st.session_state["invoice_analysis"] = _run_checks(extracted, companies, invoices)
                st.session_state["invoice_analysis_digest"] = digest
            except RuntimeError as exc:
                st.error(f"Gemma açıklaması alınamadı: {exc}")
                return
        else:
            st.session_state["invoice_raw"] = (
                json.dumps(extracted, ensure_ascii=False, indent=2)
                if isinstance(extracted, dict)
                else extracted
            )
            st.session_state["invoice_raw_digest"] = digest
            st.warning("Gemma çıktısı geçersiz veya eksik. JSON'u düzeltip tekrar deneyebilirsiniz.")

    if st.session_state.get("invoice_raw_digest") == digest:
        raw_text = st.text_area("Gemma çıktısını düzeltin (JSON)", value=st.session_state.get("invoice_raw", ""))
        if st.button("Düzeltilmiş JSON ile devam et"):
            try:
                corrected = json.loads(raw_text)
                if not isinstance(corrected, dict) or not _is_complete_invoice(corrected):
                    raise ValueError("Fatura no, tarih, satıcı/alıcı VKN, kalemler ve toplam alanlarını kontrol edin.")
                gib_result = mocks.verify_invoice(corrected, invoices)
                corrected["buyer_approved"] = gib_result["buyer_approved"]
                st.session_state["invoice_analysis"] = _run_checks(corrected, companies, invoices)
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
        _display_offer_workflow(result["invoice"])

    st.caption("Risk puanı yalnızca karar desteğidir. Nihai değerlendirme insana aittir.")


if __name__ == "__main__":
    main()
