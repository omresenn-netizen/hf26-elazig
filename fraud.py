"""Deterministic invoice checks; flags support human review, not automatic rejection."""
import hashlib
import json
from datetime import date
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parent
VAGUE_TERMS = (
    "danışmanlık", "muhtelif", "çeşitli hizmet", "genel hizmet",
    "pazarlama hizmeti", "aracılık hizmeti",
)
SERVICE_UNITS = {"hizmet", "saat", "ay", "gün"}
SECTOR_TERMS = {
    "tekstil": ("tekstil", "giyim", "kumaş", "konfeksiyon"),
    "içecek": ("içecek", "gıda", "market", "perakende"),
    "gıda": ("gıda", "market", "perakende", "içecek"),
    "elektrik": ("elektrik", "yapı", "beyaz eşya"),
    "mobilya": ("mobilya", "yapı"),
    "ambalaj": ("ambalaj", "üretim", "sanayi"),
    "metal": ("metal", "üretim", "sanayi"),
}
ITEM_TERMS = {
    "içecek": ("kola", "meyve suyu", "maden suyu", "içecek", "su 200 ml"),
    "tekstil": ("tişört", "sweatshirt", "pantolon", "kumaş", "tekstil"),
    "elektrik": ("kablo", "sigorta", "led panel", "elektrik"),
    "gıda": ("kayısı", "pestil", "ceviz", "gıda"),
    "mobilya": ("masa", "raf ünitesi", "mobilya"),
    "ambalaj": ("karton kutu", "streç film", "ambalaj"),
    "metal": ("flanş", "konstrüksiyon", "metal"),
}
FLAG_POINTS = {
    "duplicate_invoice": 45,
    "invoice_broker": 30,
    "year_end_cluster": 20,
    "network_cycle": 30,
    "shell_company": 25,
    "buyer_not_approved": 20,
    "sector_mismatch": 20,
    "capacity_outlier": 15,
    "vague_item": 15,
    "round_amount": 10,
    "missing_delivery_note": 10,
}


def _format_tl(value):
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " TL"


def load_demo_data():
    companies = json.loads((ROOT / "data" / "companies.json").read_text(encoding="utf-8"))
    invoices = json.loads((ROOT / "data" / "invoices.json").read_text(encoding="utf-8"))
    return companies, invoices


def _number(value):
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.strip().replace(" TL", "").replace("₺", "").replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _fingerprint(invoice):
    amount = _number(invoice.get("total", invoice.get("amount")))
    fields = (
        invoice.get("seller_vkn"),
        invoice.get("invoice_no"),
        f"{amount:.2f}" if amount is not None else None,
        invoice.get("issue_date"),
    )
    if not all(fields):
        return None
    value = "|".join(str(field).strip() for field in fields).casefold()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _issue_date(invoice):
    try:
        return date.fromisoformat(str(invoice["issue_date"])[:10])
    except (KeyError, ValueError, TypeError):
        return None


def _is_service(item):
    unit = str(item.get("unit", "")).casefold()
    description = str(item.get("description", "")).casefold()
    return unit in SERVICE_UNITS or any(term in description for term in VAGUE_TERMS)


def _item_category(items):
    text = " ".join(str(item.get("description", "")).casefold() for item in items)
    for category, terms in ITEM_TERMS.items():
        if any(term in text for term in terms):
            return category
    return None


def _seller_month_total(invoice, invoices):
    current_date = _issue_date(invoice)
    if current_date is None:
        return 0.0
    invoice_no = invoice.get("invoice_no")
    total = _number(invoice.get("total", invoice.get("amount"))) or 0.0
    for existing in invoices:
        if existing.get("seller_vkn") != invoice.get("seller_vkn") or existing.get("invoice_no") == invoice_no:
            continue
        existing_date = _issue_date(existing)
        if existing_date and existing_date.year == current_date.year and existing_date.month == current_date.month:
            total += _number(existing.get("total")) or 0.0
    return total


def _network_cycle(invoice, invoices):
    graph = nx.DiGraph()
    for item in [*invoices, invoice]:
        seller = item.get("seller_vkn")
        buyer = item.get("buyer_vkn")
        if seller and buyer:
            graph.add_edge(seller, buyer)
    seller = invoice.get("seller_vkn")
    buyer = invoice.get("buyer_vkn")
    return bool(seller and buyer and seller != buyer and nx.has_path(graph, buyer, seller))


def _shared_young_company(invoice, companies):
    issue_date = _issue_date(invoice)
    if issue_date is None:
        return None
    by_vkn = {company.get("vkn"): company for company in companies}
    addresses = {}
    for company in companies:
        address = company.get("address")
        if address:
            addresses.setdefault(address.casefold(), []).append(company)
    for vkn in (invoice.get("seller_vkn"), invoice.get("buyer_vkn")):
        company = by_vkn.get(vkn)
        if not company or not company.get("address"):
            continue
        try:
            founded = date(int(company["founded"]), 1, 1)
        except (KeyError, ValueError, TypeError):
            continue
        shared = addresses.get(company["address"].casefold(), [])
        other_company = any(other.get("vkn") != vkn for other in shared)
        if other_company and 0 <= (issue_date - founded).days < 365:
            return company
    return None


def analyze_invoice(invoice, companies, invoices):
    flags = []
    add = lambda code, detail: flags.append({"code": code, "detail": detail})

    fingerprint = _fingerprint(invoice)
    if fingerprint and sum(_fingerprint(item) == fingerprint for item in invoices) > 1:
        add("duplicate_invoice", "Aynı satıcı, fatura no, tutar ve tarihle birden fazla kayıt bulundu.")

    items = invoice.get("items") or []
    has_goods = any(not _is_service(item) for item in items)
    delivery_note = str(invoice.get("irsaliye_no") or "").strip().casefold()
    if has_goods and delivery_note in {"", "-", "yok", "null", "none"}:
        add("missing_delivery_note", "Mal içeren faturada irsaliye numarası bulunmuyor.")

    company_by_vkn = {company.get("vkn"): company for company in companies}
    seller = company_by_vkn.get(invoice.get("seller_vkn"), {})
    category = _item_category(items)
    sector = str(seller.get("sector", "")).casefold()
    if category and sector and not any(term in sector for term in SECTOR_TERMS.get(category, (category,))):
        add("sector_mismatch", f"Satıcı sektörü ({seller.get('sector')}) ile ürün kategorisi ({category}) uyuşmuyor.")

    employees = seller.get("employees") or 0
    monthly_total = _seller_month_total(invoice, invoices)
    if employees and monthly_total > max(1_000_000, employees * 100_000):
        add("capacity_outlier", f"Aylık fatura toplamı çalışan sayısına göre yüksek ({employees} çalışan, {_format_tl(monthly_total)}).")

    amount = _number(invoice.get("subtotal", invoice.get("amount")))
    if amount is not None and amount >= 100_000 and abs(amount / 50_000 - round(amount / 50_000)) < 0.000001:
        add("round_amount", f"KDV öncesi ara toplam olağandışı yuvarlak bir tutar ({_format_tl(amount)}).")
    vague = sorted({
        term for item in items
        for term in VAGUE_TERMS
        if term in str(item.get("description", "")).casefold()
    })
    if vague:
        add("vague_item", f"Belirsiz mal/hizmet açıklaması: {', '.join(vague)}.")

    seller_invoices = [
        item for item in invoices
        if item.get("seller_vkn") == invoice.get("seller_vkn")
    ]
    if not any(item.get("invoice_no") == invoice.get("invoice_no") for item in seller_invoices):
        seller_invoices.append(invoice)
    buyer_sectors = {
        company_by_vkn.get(item.get("buyer_vkn"), {}).get("sector")
        for item in seller_invoices
        if item.get("buyer_vkn") and item.get("buyer_vkn") != invoice.get("seller_vkn")
        and company_by_vkn.get(item.get("buyer_vkn"), {}).get("sector")
    }
    buyer_ids = {
        item.get("buyer_vkn")
        for item in seller_invoices
        if item.get("buyer_vkn") and item.get("buyer_vkn") != invoice.get("seller_vkn")
    }
    seller_has_suspicious_invoice = any(
        any(term in str(line.get("description", "")).casefold() for term in VAGUE_TERMS)
        or str(item.get("irsaliye_no") or "").strip().casefold() in {"", "-", "yok", "null", "none"}
        for item in seller_invoices
        for line in item.get("items") or []
    )
    if len(buyer_ids) >= 3 and len(buyer_sectors) >= 3 and seller_has_suspicious_invoice:
        add("invoice_broker", f"Satıcı, en az üç farklı sektörden {len(buyer_ids)} alıcıya şüpheli açıklama veya irsaliyesiz fatura kesmiş.")

    year_end_keys = set()
    for item in seller_invoices:
        item_date = _issue_date(item)
        if item_date and item_date.month == 12 and item_date.day >= 27:
            identity = item.get("invoice_no") or _fingerprint(item)
            if identity:
                year_end_keys.add(identity)
    if len(year_end_keys) >= 3:
        add("year_end_cluster", f"Aynı satıcıdan yılın son beş gününde {len(year_end_keys)} farklı fatura kesilmiş.")

    if invoice.get("buyer_approved") is False:
        add("buyer_not_approved", "Alıcı faturayı henüz onaylamamış.")

    if _network_cycle(invoice, invoices):
        add("network_cycle", "Satıcıdan alıcıya giden işlem, fatura ağında bir döngünün parçası.")
    shell = _shared_young_company(invoice, companies)
    if shell:
        add("shell_company", f"{shell.get('name')} bir yıldan genç ve başka bir şirketle aynı adresi paylaşıyor.")
    return flags


def risk_score(flags):
    return min(100, sum(FLAG_POINTS.get(flag.get("code"), 0) for flag in flags))
