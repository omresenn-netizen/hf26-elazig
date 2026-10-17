"""Streamlit UI for the first Vadesiz demo."""
import hashlib
import json
from pathlib import Path

import streamlit as st

import db
import fraud
import gemma

ROOT = Path(__file__).resolve().parent
SAMPLE_DIR = ROOT / "samples"


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
            st.markdown(f"- **{flag['code']}** — {flag['detail']}")
    else:
        st.success("Otomatik kurallarda belirgin bir uyarı bulunmadı; yine de insan incelemesi gerekir.")
    st.subheader("Gemma açıklaması")
    st.write(result["explanation"])


def main():
    st.set_page_config(page_title="Vadesiz", page_icon="🧾", layout="centered")
    db.init_db()
    st.title("Vadesiz")
    st.caption("KOBİ'ler için fatura finansmanı • Yerel yapay zekâ ile demo")

    role = st.sidebar.selectbox("Panel", ("KOBİ paneli", "Finansör paneli", "Dedektör"))
    st.sidebar.info("DEMO / MOCK: GİB, kredi skoru, banka transferi ve e-imza gerçek servis değildir.")
    if role != "KOBİ paneli":
        st.info("Bu panel sonraki sürümde hazırlanacak. Şimdilik KOBİ panelini kullanabilirsiniz.")
        return

    st.header("Faturanı yükle")
    companies, invoices = fraud.load_demo_data()
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
                st.session_state["invoice_analysis"] = _run_checks(corrected, companies, invoices)
                st.session_state["invoice_analysis_digest"] = digest
                del st.session_state["invoice_raw"]
                del st.session_state["invoice_raw_digest"]
            except (json.JSONDecodeError, ValueError) as exc:
                st.error(f"JSON düzeltmesi geçersiz: {exc}")
            except RuntimeError as exc:
                st.error(f"Gemma açıklaması alınamadı: {exc}")

    if st.session_state.get("invoice_analysis_digest") == digest:
        _show_analysis(st.session_state["invoice_analysis"])

    st.caption("Risk puanı yalnızca karar desteğidir. Nihai değerlendirme insana aittir.")


if __name__ == "__main__":
    main()
