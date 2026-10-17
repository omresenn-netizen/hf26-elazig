"""Generates the fictional demo data for Vadesiz: companies, invoices and invoice images.

All companies, tax numbers and invoices are invented for the hackathon demo.
Run: python scripts/make_demo_data.py
"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SAMPLES = ROOT / "samples"
KDV = 0.20
random.seed(26)

SHELL_ADDRESS = "Cumhuriyet Mah. 12. Sok. No:4, Merkez/Elazığ"

COMPANIES = [
    # Big buyers
    ("9100000011", "Anadolu Market Zinciri A.Ş.", "perakende", 4200, 1998, "Sanayi Cad. No:1, Merkez/Elazığ", "buyer"),
    ("9100000022", "Fırat Beyaz Eşya A.Ş.", "beyaz eşya üretimi", 1800, 2003, "OSB 3. Cad. No:7, Merkez/Elazığ", "buyer"),
    ("9100000033", "Harput Giyim Mağazaları A.Ş.", "giyim perakende", 950, 2006, "Gazi Cad. No:45, Merkez/Elazığ", "buyer"),
    ("9100000044", "Doğu Yapı Market A.Ş.", "yapı market", 600, 2009, "Malatya Yolu No:12, Merkez/Elazığ", "buyer"),
    # Real SMEs
    ("9200000101", "Hazar Tekstil Atölyesi Ltd. Şti.", "tekstil", 18, 2015, "Hilalkent Mah. 3. Sok. No:9, Merkez/Elazığ", "sme"),
    ("9200000202", "Keban İçecek Dağıtım Ltd. Şti.", "içecek dağıtım", 25, 2012, "Abdullahpaşa Mah. No:21, Merkez/Elazığ", "sme"),
    ("9200000303", "Palu Ambalaj Ltd. Şti.", "ambalaj", 12, 2017, "OSB 1. Cad. No:14, Merkez/Elazığ", "sme"),
    ("9200000404", "Kayısı Diyarı Gıda Ltd. Şti.", "gıda", 30, 2010, "Sürsürü Mah. No:5, Merkez/Elazığ", "sme"),
    ("9200000505", "Elazığ Mobilya Ltd. Şti.", "mobilya", 15, 2014, "Ataşehir Mah. No:33, Merkez/Elazığ", "sme"),
    ("9200000606", "Sivrice Elektrik Malzemeleri Ltd. Şti.", "elektrik malzemesi", 9, 2016, "Rızaiye Mah. No:8, Merkez/Elazığ", "sme"),
    ("9200000707", "Mastar Metal İşleme Ltd. Şti.", "metal işleme", 22, 2011, "OSB 5. Cad. No:2, Merkez/Elazığ", "sme"),
    # Fake-invoice ring: same address, founded this year
    ("9300000801", "Yıldız Danışmanlık Ltd. Şti.", "danışmanlık", 1, 2026, SHELL_ADDRESS, "shell"),
    ("9300000802", "Akarsu Ticaret Ltd. Şti.", "genel ticaret", 1, 2026, SHELL_ADDRESS, "shell"),
    ("9300000803", "Bereket Pazarlama Ltd. Şti.", "pazarlama", 2, 2026, SHELL_ADDRESS, "shell"),
    # Invoice broker: sells invoices to unrelated companies
    ("9300000904", "Kartal Genel Ticaret Ltd. Şti.", "genel ticaret", 2, 2025, "Yeni Mah. 41. Sok. No:1, Merkez/Elazığ", "broker"),
]

# Items each real SME sells: (description, unit, unit price range)
CATALOG = {
    "9200000101": [("Pamuklu tişört", "adet", (85, 140)), ("Kapüşonlu sweatshirt", "adet", (210, 320)), ("Kot pantolon", "adet", (260, 380))],
    "9200000202": [("Kola 330 ml (24'lü koli)", "koli", (310, 360)), ("Maden suyu 200 ml (24'lü koli)", "koli", (140, 175)), ("Meyve suyu 1 L (12'li koli)", "koli", (290, 340))],
    "9200000303": [("Oluklu karton kutu 40x30", "adet", (11, 18)), ("Streç film rulo", "rulo", (240, 300))],
    "9200000404": [("Gün kurusu kayısı", "kg", (290, 360)), ("Kayısı pestili", "kg", (330, 410)), ("Ceviz içi", "kg", (520, 640))],
    "9200000505": [("Ofis masası", "adet", (6200, 8400)), ("Raf ünitesi", "adet", (3100, 4500))],
    "9200000606": [("NYM kablo 3x2,5 (100 m)", "makara", (2900, 3600)), ("Sigorta 16A", "adet", (95, 140)), ("LED panel 60x60", "adet", (640, 820))],
    "9200000707": [("CNC işlenmiş flanş", "adet", (420, 610)), ("Kaynaklı konstrüksiyon", "kg", (95, 130))],
}
# Which big buyer each SME usually sells to
CUSTOMER = {
    "9200000101": "9100000033", "9200000202": "9100000011", "9200000303": "9100000022",
    "9200000404": "9100000011", "9200000505": "9100000044", "9200000606": "9100000044",
    "9200000707": "9100000022",
}


def company_dicts():
    return [
        {"vkn": v, "name": n, "sector": s, "employees": e, "founded": f, "address": a, "type": t}
        for v, n, s, e, f, a, t in COMPANIES
    ]


def money(x):
    return round(x, 2)


def make_invoice(no, seller, buyer, issue, items, irsaliye, approved, due_days, scenario):
    subtotal = money(sum(i["quantity"] * i["unit_price"] for i in items))
    kdv = money(subtotal * KDV)
    return {
        "invoice_no": no,
        "seller_vkn": seller,
        "buyer_vkn": buyer,
        "issue_date": issue.isoformat(),
        "due_date": (issue + timedelta(days=due_days)).isoformat(),
        "items": items,
        "subtotal": subtotal,
        "kdv_rate": KDV,
        "kdv": kdv,
        "total": money(subtotal + kdv),
        "irsaliye_no": irsaliye,
        "buyer_approved": approved,
        "scenario": scenario,  # ground truth for the demo, never shown to the model
    }


def real_items(seller):
    picks = random.sample(CATALOG[seller], k=min(len(CATALOG[seller]), random.randint(1, 3)))
    items = []
    for desc, unit, (lo, hi) in picks:
        qty = random.choice([40, 60, 75, 120, 150, 200, 240, 300])
        if hi > 1000:  # furniture, cable drums: small batches
            qty = random.randint(5, 25)
        if unit == "kg" and seller == "9200000707":
            qty = random.randint(800, 2500)
        items.append({"description": desc, "unit": unit, "quantity": qty, "unit_price": money(random.uniform(lo, hi))})
    return items


def build_invoices():
    invoices = []
    counter = 1

    def next_no(prefix):
        nonlocal counter
        counter += 1
        return f"{prefix}2026{counter:06d}"

    # 1. Legitimate trade: 30 invoices
    for _ in range(30):
        seller = random.choice(list(CATALOG))
        issue = date(2026, 8, 1) + timedelta(days=random.randint(0, 75))
        invoices.append(make_invoice(
            next_no("VDZ"), seller, CUSTOMER[seller], issue, real_items(seller),
            f"IRS{issue:%Y%m%d}{random.randint(100, 999)}", True, random.choice([60, 90, 120]), "legit"))

    # 2. Fake-invoice ring: Yıldız -> Akarsu -> Bereket -> Yıldız, round amounts, vague items
    ring = ["9300000801", "9300000802", "9300000803"]
    for month in (7, 8, 9):
        for i, seller in enumerate(ring):
            buyer = ring[(i + 1) % 3]
            amount = random.choice([250_000, 500_000, 750_000])
            invoices.append(make_invoice(
                next_no("YAB"), seller, buyer, date(2026, month, 28 + i % 2),
                [{"description": "Danışmanlık hizmeti", "unit": "hizmet", "quantity": 1, "unit_price": float(amount)}],
                None, True, 90, "ring"))

    # 3. Invoice broker selling "expenses" to unrelated real companies at year end
    broker_sales = [
        ("9200000101", "Kola 330 ml (24'lü koli)", "koli", 625, 320.0),
        ("9200000707", "Danışmanlık hizmeti", "hizmet", 1, 300_000.0),
        ("9200000505", "Pazarlama hizmeti", "hizmet", 1, 150_000.0),
        ("9200000606", "Muhtelif malzeme", "parti", 1, 200_000.0),
    ]
    for d, (buyer, desc, unit, qty, price) in enumerate(broker_sales):
        invoices.append(make_invoice(
            next_no("KRT"), "9300000904", buyer, date(2025, 12, 27 + d),
            [{"description": desc, "unit": unit, "quantity": qty, "unit_price": price}],
            None, True, 30, "broker"))

    # 4. Sector mismatch: textile workshop selling cola to a supermarket, no delivery note
    invoices.append(make_invoice(
        next_no("VDZ"), "9200000101", "9100000011", date(2026, 10, 3),
        [{"description": "Kola 330 ml (24'lü koli)", "unit": "koli", "quantity": 625, "unit_price": 320.0}],
        None, True, 90, "sector_mismatch"))

    # 5. Capacity: 9-person shop invoicing 4.8M TL in one go
    invoices.append(make_invoice(
        next_no("VDZ"), "9200000606", "9100000044", date(2026, 10, 9),
        [{"description": "NYM kablo 3x2,5 (100 m)", "unit": "makara", "quantity": 1250, "unit_price": 3200.0},
         {"description": "LED panel 60x60", "unit": "adet", "quantity": 1000, "unit_price": 800.0}],
        "IRS20261009311", True, 120, "capacity"))

    # 6. Not approved by the buyer
    issue = date(2026, 10, 12)
    invoices.append(make_invoice(
        next_no("VDZ"), "9200000505", "9100000044", issue, real_items("9200000505"),
        "IRS20261012507", False, 90, "not_approved"))

    # 7. Double financing: a legit invoice uploaded a second time
    dup = dict(invoices[3])
    dup["scenario"] = "duplicate"
    invoices.append(dup)

    for i, inv in enumerate(invoices, start=1):
        inv["id"] = f"INV-{i:03d}"
    return invoices


def tl(x):
    s = f"{x:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " TL"


def draw_invoice(inv, companies, path):
    from PIL import Image, ImageDraw, ImageFont

    font = "C:/Windows/Fonts/arial.ttf"
    bold = "C:/Windows/Fonts/arialbd.ttf"
    f_title, f_h, f_b, f_s = (ImageFont.truetype(bold, 34), ImageFont.truetype(bold, 20),
                              ImageFont.truetype(font, 19), ImageFont.truetype(font, 16))
    seller, buyer = companies[inv["seller_vkn"]], companies[inv["buyer_vkn"]]
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)

    d.text((60, 50), "e-FATURA", font=f_title, fill="#1a3a6b")
    d.text((60, 95), "Bu belge hackathon demosu için üretilmiş kurgusal bir faturadır.", font=f_s, fill="#999")
    d.text((780, 60), f"Fatura No: {inv['invoice_no']}", font=f_b, fill="black")
    d.text((780, 90), f"Düzenleme Tarihi: {inv['issue_date']}", font=f_b, fill="black")
    d.text((780, 120), f"Vade Tarihi: {inv['due_date']}", font=f_b, fill="black")
    d.text((780, 150), f"İrsaliye No: {inv['irsaliye_no'] or '-'}", font=f_b, fill="black")

    def party(x, y, title, c):
        d.text((x, y), title, font=f_h, fill="#1a3a6b")
        d.text((x, y + 32), c["name"], font=f_b, fill="black")
        d.text((x, y + 60), c["address"], font=f_s, fill="black")
        d.text((x, y + 86), f"VKN: {c['vkn']}", font=f_s, fill="black")

    party(60, 220, "SATICI", seller)
    party(660, 220, "ALICI", buyer)

    y = 400
    d.rectangle((60, y, 1180, y + 40), fill="#e8eef7")
    for x, h in ((70, "Mal / Hizmet"), (610, "Miktar"), (760, "Birim Fiyat"), (980, "Tutar")):
        d.text((x, y + 10), h, font=f_h, fill="black")
    y += 50
    for it in inv["items"]:
        d.text((70, y), it["description"], font=f_b, fill="black")
        d.text((610, y), f"{it['quantity']} {it['unit']}", font=f_b, fill="black")
        d.text((760, y), tl(it["unit_price"]), font=f_b, fill="black")
        d.text((980, y), tl(it["quantity"] * it["unit_price"]), font=f_b, fill="black")
        y += 36
    y += 20
    d.line((60, y, 1180, y), fill="#999", width=2)
    y += 20
    for label, val in (("Mal Hizmet Toplamı", inv["subtotal"]), (f"KDV (%{int(inv['kdv_rate'] * 100)})", inv["kdv"]),
                       ("Ödenecek Tutar", inv["total"])):
        d.text((700, y), label, font=f_h, fill="black")
        d.text((980, y), tl(val), font=f_h, fill="black")
        y += 36
    img.save(path)


def main():
    DATA.mkdir(exist_ok=True)
    SAMPLES.mkdir(exist_ok=True)
    companies = company_dicts()
    invoices = build_invoices()
    (DATA / "companies.json").write_text(json.dumps(companies, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "invoices.json").write_text(json.dumps(invoices, ensure_ascii=False, indent=2), encoding="utf-8")

    by_vkn = {c["vkn"]: c for c in companies}
    picks = {
        "01_gercek_icecek.png": next(i for i in invoices if i["scenario"] == "legit" and i["seller_vkn"] == "9200000202"),
        "02_gercek_tekstil.png": next(i for i in invoices if i["scenario"] == "legit" and i["seller_vkn"] == "9200000101"),
        "03_supheli_sektor.png": next(i for i in invoices if i["scenario"] == "sector_mismatch"),
        "04_naylon_danismanlik.png": next(i for i in invoices if i["scenario"] == "broker" and i["buyer_vkn"] == "9200000707"),
        "05_dongu_sebeke.png": next(i for i in invoices if i["scenario"] == "ring"),
        # last legit furniture invoice, so it is never the one copied as the duplicate scenario
        "06_gercek_mobilya.png": [i for i in invoices if i["scenario"] == "legit" and i["seller_vkn"] == "9200000505"][-1],
    }
    for name, inv in picks.items():
        draw_invoice(inv, by_vkn, SAMPLES / name)
    demo_uploads = [{"file": name, "invoice_no": inv["invoice_no"], "scenario": inv["scenario"]} for name, inv in picks.items()]
    (DATA / "demo_uploads.json").write_text(json.dumps(demo_uploads, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {}
    for i in invoices:
        counts[i["scenario"]] = counts.get(i["scenario"], 0) + 1
    print(f"{len(companies)} companies, {len(invoices)} invoices: {counts}")
    print("images:", ", ".join(picks))


if __name__ == "__main__":
    main()
