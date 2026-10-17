"""KOBI invoice upload and offer workflow."""
import hashlib
import json
import sqlite3
from pathlib import Path

import streamlit as st

import db
import fraud
import gemma
import mocks
from .common import (
    FLAG_LABELS,
    _format_tl,
    _invoice_with_gib_approval,
    _is_complete_invoice,
    _request_metadata,
    _run_checks,
    _show_header_metrics,
)

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "samples"

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

def render(user, companies, invoices, ip_address):
        _, user_agent = _request_metadata()
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
