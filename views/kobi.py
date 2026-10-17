"""KOBI invoice upload, financing, and notification workflows."""
import hashlib
import html
import io
import json
from pathlib import Path
import sqlite3

import streamlit as st
from PIL import Image, UnidentifiedImageError

import db
import fraud
import gemma
import mocks
import repo_kobi
import ui
from .common import (
    FLAG_LABELS,
    _format_tl,
    _is_complete_invoice,
    _request_metadata,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO_UPLOADS_PATH = ROOT / "data" / "demo_uploads.json"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
STATUS_LABELS = {
    "incelemede": "İncelemede",
    "teklif_bekliyor": "Teklif bekliyor",
    "teklif_var": "Teklif var",
    "finanse_edildi": "Finanse edildi",
    "reddedildi": "Reddedildi",
}
OFFER_STATUS_LABELS = {
    "beklemede": "Beklemede",
    "open": "Açık",
    "kabul": "Kabul edildi",
    "accepted": "Kabul edildi",
    "red": "Reddedildi",
    "rejected": "Reddedildi",
    "geri_cekildi": "Geri çekildi",
    "withdrawn": "Geri çekildi",
}


def _step_indicator(active):
    steps = ("① Yükle", "② Okuma", "③ Kontrol", "④ Teklife aç")
    markup = " <span aria-hidden=\"true\">→</span> ".join(
        f'<span class="{"kobi-step-active" if index == active else ""}">{label}</span>'
        for index, label in enumerate(steps, 1)
    )
    st.markdown(f'<div class="kobi-steps">{markup}</div>', unsafe_allow_html=True)


def _file_type_error(uploaded, content):
    extension = Path(uploaded.name).suffix.casefold()
    expected = {
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".jpeg": content.startswith(b"\xff\xd8\xff"),
        ".pdf": content.startswith(b"%PDF-"),
    }
    if extension not in expected:
        return "Yalnızca PNG, JPG, JPEG veya PDF dosyası yükleyebilirsiniz."
    if not expected[extension]:
        return "Dosya uzantısı ile içeriği eşleşmiyor; lütfen doğru belgeyi seçin."
    if extension != ".pdf":
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > 30_000_000:
                    return "Görsel çözünürlüğü desteklenen sınırı aşıyor."
                image.verify()
        except (OSError, UnidentifiedImageError):
            return "Görsel dosyası bozuk veya okunamıyor; lütfen yeniden dışa aktarın."
    return None


def _demo_invoice_numbers():
    return {
        row["invoice_no"]
        for row in json.loads(DEMO_UPLOADS_PATH.read_text(encoding="utf-8"))
    }


def _cached_offer_comparison(offers_json):
    return gemma.compare_offers(json.loads(offers_json))


_cached_offer_comparison = st.cache_data(show_spinner=False)(_cached_offer_comparison)


def _editable_invoice(draft):
    items_json = json.dumps(draft.get("items") or [], ensure_ascii=False, indent=2)
    approval_values = ["Belgede belirtilmemiş", "Onaylandı", "Onaylanmadı"]
    approval = draft.get("buyer_approved")
    approval_index = 1 if approval is True else 2 if approval is False else 0
    with st.form(f"invoice_check_{st.session_state['active_upload_id']}"):
        st.markdown("### Okunan alanları doğrulayın")
        first, second = st.columns(2)
        invoice_no = first.text_input("Fatura numarası", value=str(draft.get("invoice_no") or ""))
        issue_date = second.text_input("Düzenleme tarihi (YYYY-AA-GG)", value=str(draft.get("issue_date") or ""))
        seller_name = first.text_input("Satıcı", value=str(draft.get("seller_name") or ""))
        seller_vkn = second.text_input("Satıcı VKN", value=str(draft.get("seller_vkn") or ""))
        buyer_name = first.text_input("Alıcı", value=str(draft.get("buyer_name") or ""))
        buyer_vkn = second.text_input("Alıcı VKN", value=str(draft.get("buyer_vkn") or ""))
        due_date = first.text_input("Vade tarihi (YYYY-AA-GG)", value=str(draft.get("due_date") or ""))
        delivery_note = second.text_input("İrsaliye numarası", value=str(draft.get("irsaliye_no") or ""))
        subtotal = first.text_input("Ara toplam (TL)", value=str(draft.get("subtotal") or ""))
        kdv = second.text_input("KDV (TL)", value=str(draft.get("kdv") or ""))
        total = first.text_input("Genel toplam (TL)", value=str(draft.get("total") or ""))
        buyer_approved = second.selectbox(
            "Alıcı onayı",
            approval_values,
            index=approval_index,
        )
        items = st.text_area(
            "Fatura kalemleri (JSON)",
            value=items_json,
            height=170,
            help='Her kalemde "description", "quantity", "unit" ve "unit_price" alanları olmalıdır.',
        )
        submitted = st.form_submit_button("Kontrol et", type="primary")
    if not submitted:
        return None
    try:
        parsed_items = json.loads(items)
        if not isinstance(parsed_items, list) or not all(isinstance(item, dict) for item in parsed_items):
            raise ValueError("Fatura kalemleri JSON dizisi olmalıdır.")
        updated = {
            **draft,
            "invoice_no": invoice_no.strip(),
            "issue_date": issue_date.strip(),
            "seller_name": seller_name.strip(),
            "seller_vkn": seller_vkn.strip(),
            "buyer_name": buyer_name.strip(),
            "buyer_vkn": buyer_vkn.strip(),
            "due_date": due_date.strip() or None,
            "irsaliye_no": delivery_note.strip() or None,
            "items": parsed_items,
            "buyer_approved": {
                "Belgede belirtilmemiş": None,
                "Onaylandı": True,
                "Onaylanmadı": False,
            }[buyer_approved],
        }
        for field, value in (("subtotal", subtotal), ("kdv", kdv), ("total", total)):
            updated[field] = fraud._number(value) if value.strip() else None
        if not _is_complete_invoice(updated):
            raise ValueError("Fatura no, tarih, satıcı/alıcı VKN, kalemler ve toplam alanlarını kontrol edin.")
        if updated["total"] is None or updated["total"] <= 0:
            raise ValueError("Fatura toplamı sıfırdan büyük bir tutar olmalıdır.")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        st.error(f"Fatura alanları geçersiz: {exc}")
        return None
    return updated


def _risk_badge(score):
    if score < 30:
        label, css = "Düşük", "kobi-risk-low"
    elif score < 60:
        label, css = "Orta", "kobi-risk-medium"
    else:
        label, css = "Yüksek", "kobi-risk-high"
    st.markdown(
        f'<span class="kobi-risk {css}">Risk {score}/100 · {label}</span>',
        unsafe_allow_html=True,
    )


def _run_invoice_checks(invoice, companies, invoices, upload_id, user, ip_address):
    checked_invoice = dict(invoice)
    if checked_invoice.get("buyer_approved") is None:
        verification = mocks.verify_invoice(checked_invoice, invoices)
        if verification["buyer_approved"] is not None:
            checked_invoice["buyer_approved"] = verification["buyer_approved"]

    flags = fraud.analyze_invoice(checked_invoice, companies, invoices)
    fingerprint = fraud._fingerprint(checked_invoice)
    if (
        checked_invoice.get("invoice_no") in _demo_invoice_numbers()
        and not repo_kobi.invoice_fingerprint_seen(fingerprint, exclude_upload_id=upload_id)
    ):
        flags = [flag for flag in flags if flag["code"] != "duplicate_invoice"]
    try:
        explanation = gemma.explain_flags(checked_invoice, flags)
    except RuntimeError as exc:
        db.log_audit(
            "extract",
            user,
            ip_address,
            {"upload_id": upload_id, "invoice_no": checked_invoice.get("invoice_no"), "error": str(exc)},
        )
        st.error(f"Gemma açıklaması alınamadı: {exc}")
        return None

    score = fraud.risk_score(flags)
    saved = db.save_upload_extraction(
        upload_id,
        user,
        ip_address,
        checked_invoice,
        score,
        flags,
    )
    if saved["duplicate"]:
        flags = saved["flags"]
        score = fraud.risk_score(flags)
        try:
            explanation = gemma.explain_flags(checked_invoice, flags)
        except RuntimeError as exc:
            st.error(f"Mükerrer fatura açıklaması alınamadı: {exc}")
            return None
    return {
        "invoice": checked_invoice,
        "flags": flags,
        "score": score,
        "explanation": explanation,
        "status": saved["status"],
    }


def _show_analysis(result):
    invoice = result["invoice"]
    score = result["score"]
    _risk_badge(score)
    st.caption("Risk puanı karar desteğidir; fatura otomatik olarak reddedilmez.")
    st.write(
        f"**Fatura:** {invoice.get('invoice_no') or '—'} · "
        f"**Satıcı:** {invoice.get('seller_name') or '—'} ({invoice.get('seller_vkn') or '—'})"
    )
    st.write(
        f"**Alıcı:** {invoice.get('buyer_name') or '—'} ({invoice.get('buyer_vkn') or '—'}) · "
        f"**Düzenleme:** {invoice.get('issue_date') or '—'} · **Vade:** {invoice.get('due_date') or '—'}"
    )
    st.write(f"**Genel toplam:** {_format_tl(invoice.get('total'))}")
    if result["flags"]:
        st.markdown("**İnceleme bayrakları**")
        for flag in result["flags"]:
            st.markdown(
                f"- **{FLAG_LABELS.get(flag['code'], flag['code'])}** — {flag['detail']}"
            )
    else:
        st.success("Kontrol kurallarında uyarı bulunmadı.")
    st.info(f"**Gemma açıklaması:** {result['explanation']}")


def _upload_page(user, companies, invoices, ip_address, user_agent):
    st.header("Faturanızı yükleyin")
    st.caption("Fatura belgenizi ekleyin, alanları doğrulayın ve finansman kararını siz verin.")
    st.markdown('<div class="kobi-upload-card"></div>', unsafe_allow_html=True)
    current_id = st.session_state.get("active_upload_id")
    current_digest = st.session_state.get("active_upload_digest")

    with st.container(border=True):
        st.markdown("📄")
        analysis = st.session_state.get("invoice_analysis")
        if analysis and (
            analysis.get("status") in {"teklif_bekliyor", "teklif_var", "finanse_edildi"}
            or analysis.get("financing_opened")
        ):
            active_step = 4
        elif st.session_state.get("invoice_analysis_digest"):
            active_step = 3
        elif st.session_state.get("kobi_invoice_draft"):
            active_step = 2
        elif current_id:
            active_step = 2
        else:
            active_step = 1
        _step_indicator(active_step)
        st.markdown("#### Faturayı buraya sürükleyin veya cihazınızdan seçin")
        uploaded = st.file_uploader(
            "PNG, JPG veya PDF · en fazla 10 MB",
            type=("png", "jpg", "jpeg", "pdf"),
            max_upload_size=10,
            key="kobi_invoice_file",
            help="Dosyalarınız yalnızca bu demo uygulamasında işlenir.",
        )
        if uploaded is None:
            st.info("PNG, JPG veya PDF fatura dosyanızı seçin.")
            return

        file_bytes = uploaded.getvalue()
        digest = hashlib.sha256(file_bytes).hexdigest()
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            st.error("Dosya boyutu 10 MB sınırını aşıyor.")
            return
        type_error = _file_type_error(uploaded, file_bytes)
        if type_error:
            st.error(type_error)
            return
        if current_digest and current_digest != digest:
            for key in (
                "active_upload_id",
                "active_upload_digest",
                "invoice_analysis",
                "invoice_analysis_digest",
                "kobi_invoice_draft",
                "kobi_invoice_draft_digest",
                "invoice_raw",
                "invoice_raw_digest",
                "duplicate_upload_digest",
            ):
                st.session_state.pop(key, None)
            current_id = None
        current_id = st.session_state.get("active_upload_id")
        current_digest = st.session_state.get("active_upload_digest")
        if current_digest != digest:
            st.session_state.pop("active_upload_id", None)
            st.session_state.pop("invoice_analysis", None)
            st.session_state.pop("invoice_analysis_digest", None)
            st.session_state.pop("kobi_invoice_draft", None)
            st.session_state.pop("kobi_invoice_draft_digest", None)
            st.session_state.pop("invoice_raw", None)
            st.session_state.pop("invoice_raw_digest", None)

        meta, preview = st.columns([1.4, 0.6], vertical_alignment="center")
        with meta:
            st.write(f"**Dosya:** {uploaded.name}")
            st.write(f"**Boyut:** {len(file_bytes) / 1024:.1f} KB")
            st.write(f"**SHA-256:** `{digest[:16]}…`")
        with preview:
            if uploaded.name.casefold().endswith((".png", ".jpg", ".jpeg")):
                st.image(file_bytes, caption="Belge önizlemesi", width=210)
            else:
                st.caption("PDF dosyası eklendi · ilk sayfa önizlemesi kullanılamıyor.")

        already_processed = any(
            st.session_state.get(key) == digest
            for key in (
                "kobi_invoice_draft_digest",
                "invoice_analysis_digest",
                "invoice_raw_digest",
                "duplicate_upload_digest",
            )
        )
        if st.button("Faturayı oku", type="primary", disabled=already_processed):
            if current_id and current_digest == digest:
                upload_id = current_id
            else:
                try:
                    created = db.create_upload(
                        user,
                        user.get("company_vkn"),
                        ip_address,
                        user_agent,
                        uploaded.name,
                        file_bytes,
                    )
                except sqlite3.Error as exc:
                    st.error(f"Yükleme kaydedilemedi: {exc}")
                    return
                if created["duplicate"]:
                    st.session_state["active_upload_id"] = created["id"]
                    st.session_state["active_upload_digest"] = digest
                    st.session_state["duplicate_upload_digest"] = digest
                    st.error("Bu dosya daha önce yüklenmiş; tekrar işlenmedi ve denetim kaydına alındı.")
                    return
                st.session_state["active_upload_id"] = created["id"]
                st.session_state["active_upload_digest"] = digest
                upload_id = created["id"]
            current_id = upload_id
            if uploaded.name.casefold().endswith(".pdf"):
                message = (
                    "PDF güvenle kaydedildi; ancak yerel Gemma görsel okuma çağrısı PDF sayfasını "
                    "doğrudan çözemiyor. İlk sayfayı PNG/JPG olarak dışa aktarıp yükleyin."
                )
                db.log_audit(
                    "extract",
                    user,
                    ip_address,
                    {"upload_id": upload_id, "error": "pdf_rendering_unavailable"},
                )
                st.error(message)
            else:
                with st.spinner("Gemma faturanızı okuyor..."):
                    try:
                        extracted = gemma.extract_invoice(file_bytes, uploaded.name)
                    except RuntimeError as exc:
                        db.log_audit(
                            "extract",
                            user,
                            ip_address,
                            {"upload_id": upload_id, "error": str(exc)},
                        )
                        st.error(str(exc))
                        extracted = None
                if isinstance(extracted, dict) and _is_complete_invoice(extracted):
                    st.session_state["kobi_invoice_draft"] = extracted
                    st.session_state["kobi_invoice_draft_digest"] = digest
                elif extracted is not None:
                    raw = json.dumps(extracted, ensure_ascii=False, indent=2) if isinstance(extracted, dict) else str(extracted)
                    st.session_state["invoice_raw"] = raw
                    st.session_state["invoice_raw_digest"] = digest
                    st.warning("Gemma çıktısı eksik veya geçersiz; JSON'u düzenleyip devam edebilirsiniz.")
                    db.log_audit(
                        "extract",
                        user,
                        ip_address,
                        {"upload_id": upload_id, "parse_success": False},
                    )

        if (
            st.session_state.get("invoice_raw_digest") == digest
            and st.session_state.get("active_upload_id")
        ):
            raw_text = st.text_area(
                "Gemma çıktısını düzeltin (JSON)",
                value=st.session_state["invoice_raw"],
                height=220,
            )
            if st.button("Düzeltilmiş JSON ile devam et"):
                try:
                    corrected = json.loads(raw_text)
                    if not isinstance(corrected, dict) or not _is_complete_invoice(corrected):
                        raise ValueError("Gerekli fatura alanları eksik.")
                except (json.JSONDecodeError, ValueError) as exc:
                    st.error(f"JSON düzeltmesi geçersiz: {exc}")
                else:
                    st.session_state["kobi_invoice_draft"] = corrected
                    st.session_state["kobi_invoice_draft_digest"] = digest
                    st.session_state.pop("invoice_raw", None)
                    st.session_state.pop("invoice_raw_digest", None)

        if (
            st.session_state.get("kobi_invoice_draft_digest") == digest
            and st.session_state.get("active_upload_id")
            and st.session_state.get("invoice_analysis_digest") != digest
        ):
            draft = st.session_state["kobi_invoice_draft"]
            updated = _editable_invoice(draft)
            if updated is not None:
                with st.spinner("Fatura kuralları ve Gemma açıklaması hazırlanıyor..."):
                    result = _run_invoice_checks(
                        updated,
                        companies,
                        invoices,
                        st.session_state["active_upload_id"],
                        user,
                        ip_address,
                    )
                if result is not None:
                    st.session_state["invoice_analysis"] = result
                    st.session_state["invoice_analysis_digest"] = digest

        if st.session_state.get("invoice_analysis_digest") == digest:
            result = st.session_state["invoice_analysis"]
            _show_analysis(result)
            upload_id = st.session_state["active_upload_id"]
            if result["status"] == "reddedildi":
                st.error("Fatura bilgileri daha önce işlendi; bu kayıt finansmana açılamaz.")
            elif result["status"] == "finanse_edildi":
                st.success("Bu fatura için finansman tamamlandı.")
            elif result["score"] >= 60:
                if result.get("financing_opened"):
                    st.warning("Yüksek riskli fatura denetim kuyruğuna gönderildi; finansörlere ancak inceleme sonrası açılır.")
                else:
                    st.warning("Yüksek risk puanı: finansörlere açılmadan önce denetim kuyruğuna gönderilecektir.")
                if not result.get("financing_opened") and st.button("Finansmana aç", key=f"open_finance_{upload_id}", type="primary"):
                    try:
                        status = repo_kobi.open_financing(user, ip_address, upload_id, result["score"])
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["invoice_analysis"]["status"] = status
                        st.session_state["invoice_analysis"]["financing_opened"] = True
                        st.success("Fatura denetim incelemesi için kuyruğa alındı.")
                        st.rerun()
            elif result["status"] == "teklif_bekliyor":
                st.success("Fatura finansörlerin değerlendirmesine açıldı; teklifler otomatik oluşturulmaz.")
            elif result["status"] == "teklif_var":
                st.success("Fatura finansörlerin değerlendirmesine açık; gelen teklifleri Faturalarım'dan inceleyin.")
            else:
                if st.button("Finansmana aç", key=f"open_finance_{upload_id}", type="primary"):
                    try:
                        status = repo_kobi.open_financing(user, ip_address, upload_id, result["score"])
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["invoice_analysis"]["status"] = status
                        st.success("Faturanız finansörlerin değerlendirmesine açıldı. Teklif oluştuğunda bildirim alırsınız.")
                        st.rerun()


def _status_label(status):
    return STATUS_LABELS.get(status, status or "—")


def _offer_is_open(offer):
    return offer["status"] in {"beklemede", "open"}


def _show_invoice_detail(user, ip_address, upload):
    invoice = upload["invoice"]
    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        with st.container(border=True):
            st.subheader(f"Fatura {invoice.get('invoice_no') or upload['file_name']}")
            _risk_badge(upload["risk_score"] or 0)
            st.write(f"**Satıcı:** {invoice.get('seller_name') or '—'}")
            st.write(f"**Alıcı:** {invoice.get('buyer_name') or '—'}")
            st.write(f"**Toplam:** {_format_tl(invoice.get('total'))}")
            st.write(f"**Vade:** {invoice.get('due_date') or '—'}")
            st.write(f"**Durum:** {_status_label(upload['status'])}")
            for flag in upload["flags"]:
                st.markdown(
                    f"- **{FLAG_LABELS.get(flag['code'], flag['code'])}** — {flag['detail']}"
                )
    with right:
        with st.container(border=True):
            st.subheader("Finansör teklifleri")
            offers = repo_kobi.list_upload_offers(user.get("company_vkn"), upload["id"])
            try:
                repo_kobi.sync_offer_notifications(user, upload, offers)
            except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
                st.error(f"Mock e-posta günlüğüne yazılamadı: {exc}")

            if not offers:
                st.info("Bu fatura için henüz finansör teklifi yok.")
            open_offers = [offer for offer in offers if _offer_is_open(offer)]
            for offer in offers:
                st.markdown(f"**{offer['financier_name']}** · {_format_tl(offer['net_amount'])}")
                st.caption(
                    f"İskonto %{offer['discount_rate'] * 100:.2f}".replace(".", ",")
                    + f" · {offer['created_at']} · "
                    + OFFER_STATUS_LABELS.get(offer["status"], offer["status"])
                )
                if offer.get("note"):
                    st.caption(offer["note"])
                if _offer_is_open(offer) and upload["status"] != "finanse_edildi":
                    accept, reject = st.columns(2)
                    if accept.button("Kabul et", key=f"accept_{upload['id']}_{offer['source']}_{offer['offer_id']}", type="primary"):
                        transfer = mocks.bank_transfer(
                            invoice.get("invoice_no"),
                            offer["net_amount"],
                        )
                        try:
                            repo_kobi.accept_offer(user, ip_address, upload["id"], offer, transfer)
                        except (ValueError, sqlite3.Error) as exc:
                            st.error(f"Teklif kabul edilemedi: {exc}")
                        else:
                            st.success(
                                f"DEMO / MOCK transfer tamamlandı: {_format_tl(transfer['amount'])} · "
                                f"İşlem kodu: {transfer['transfer_id']}"
                            )
                            st.rerun()
                    if reject.button(
                        "Reddet",
                        key=f"reject_{upload['id']}_{offer['source']}_{offer['offer_id']}",
                    ):
                        try:
                            repo_kobi.reject_offer(user, ip_address, upload["id"], offer)
                        except (ValueError, sqlite3.Error) as exc:
                            st.error(f"Teklif reddedilemedi: {exc}")
                        else:
                            st.success("Teklif reddedildi.")
                            st.rerun()
                st.divider()

            if open_offers:
                try:
                    offers_json = json.dumps(open_offers, ensure_ascii=False, sort_keys=True)
                    recommendation = _cached_offer_comparison(offers_json)
                except RuntimeError as exc:
                    st.error(f"Gemma teklif karşılaştırması alınamadı: {exc}")
                else:
                    with st.container(border=True):
                        st.markdown(
                            '<span class="kobi-offer-heading"></span>**Gemma teklif karşılaştırması**',
                            unsafe_allow_html=True,
                        )
                        if isinstance(recommendation, dict):
                            st.write(recommendation.get("recommendation", ""))
                            st.caption(recommendation.get("reason", ""))
                        else:
                            st.warning("Gemma geçerli JSON döndürmedi; ham çıktı:")
                            st.code(recommendation)


def _invoices_page(user, ip_address):
    st.header("Faturalarım")
    uploads = repo_kobi.list_company_uploads(user.get("company_vkn"))
    if not uploads:
        st.info("Henüz yüklenmiş faturanız yok.")
        return
    table = []
    for upload in uploads:
        invoice = upload["invoice"]
        table.append(
            {
                "Fatura no": invoice.get("invoice_no") or upload["file_name"],
                "Alıcı": invoice.get("buyer_name") or "—",
                "Toplam": _format_tl(invoice.get("total")),
                "Vade": invoice.get("due_date") or "—",
                "Risk": f"{upload['risk_score']}/100" if upload["risk_score"] is not None else "—",
                "Durum": _status_label(upload["status"]),
                "Teklif": upload["offer_count"],
            }
        )
    st.dataframe(table, hide_index=True, use_container_width=True)
    labels = {
        upload["id"]: (
            f"{upload['invoice'].get('invoice_no') or upload['file_name']} · "
            f"{_status_label(upload['status'])}"
        )
        for upload in uploads
    }
    selected_id = st.selectbox(
        "Fatura detayını görüntüleyin",
        list(labels),
        format_func=lambda upload_id: labels[upload_id],
        key="kobi_invoice_detail",
    )
    selected = repo_kobi.get_company_upload(user.get("company_vkn"), selected_id)
    if selected:
        _show_invoice_detail(user, ip_address, selected)


def _notifications_page(user, ip_address):
    st.header("Bildirimler")
    notifications = repo_kobi.list_notifications(user["id"])
    if not notifications:
        st.info("Gelen kutunuz boş.")
        return
    for notification in notifications:
        unread = notification["read_at"] is None
        channel = "E-posta (demo)" if notification["channel"] == "email" else "Panel"
        subject = html.escape(notification["subject"])
        body = html.escape(notification["body"])
        unread_class = "font-weight:700;" if unread else ""
        st.markdown(
            f'<div style="padding:12px 14px;border-bottom:1px solid #E5E7EB;{unread_class}">'
            f'<div>{subject} <span style="color:#64748B;font-size:12px">· {channel}</span></div>'
            f'<div style="margin-top:4px">{body}</div>'
            f'<div style="margin-top:4px;color:#64748B;font-size:12px">{notification["created_at"]}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        if unread and st.button("Okundu olarak işaretle", key=f"read_notification_{notification['id']}"):
            repo_kobi.mark_notification_read(user, ip_address, notification["id"])
            st.rerun()


def render(user, companies, invoices, ip_address):
    ui.kobi_styles()
    _, user_agent = _request_metadata()
    uploads = repo_kobi.list_company_uploads(user.get("company_vkn"))
    for upload in uploads:
        offers = repo_kobi.list_upload_offers(user.get("company_vkn"), upload["id"])
        try:
            repo_kobi.sync_offer_notifications(user, upload, offers)
        except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
            st.error(f"Mock e-posta günlüğüne yazılamadı: {exc}")

    unread_count = repo_kobi.unread_notification_count(user["id"])
    if unread_count:
        st.markdown(
            f'Okunmamış bildirim <span class="kobi-unread-badge">{unread_count}</span>',
            unsafe_allow_html=True,
        )
    page = st.radio(
        "KOBİ işlemleri",
        ("Fatura Yükle", "Faturalarım", "Bildirimler"),
        horizontal=True,
        label_visibility="collapsed",
    )
    if page == "Fatura Yükle":
        _upload_page(user, companies, invoices, ip_address, user_agent)
    elif page == "Faturalarım":
        _invoices_page(user, ip_address)
    else:
        _notifications_page(user, ip_address)
