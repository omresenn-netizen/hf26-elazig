"""Seeds a lived-in demo state through the real API: uploads, checks, offers, accepted deals.

Needs the server running (uvicorn server:app --port 8600) and Ollama with gemma4 (the check step
asks Gemma for its explanation). Invoices are new, fictional and registered in the mock GİB registry;
they are not part of the preloaded market, so nothing is duplicated.

Run on a fresh database:  python scripts/seed_demo.py
"""
import json
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import make_demo_data as gen  # noqa: E402  (reuses the e-Fatura image renderer and the catalog)

API = "http://localhost:8600/api"
PASSWORD = "demo1234"
TODAY = date(2026, 10, 17)
random.seed(1717)

# seller VKN, buyer VKN, outcome, offers [(financier, discount)]
PLAN = [
    ("9200000202", "9100000011", "financed", [("anadolu_faktoring", .052), ("firat_finans", .058)]),
    ("9200000202", "9100000011", "offers", [("harput_katilim", .049), ("firat_finans", .055)]),
    ("9200000101", "9100000033", "financed", [("firat_finans", .047)]),
    ("9200000101", "9100000033", "offers", [("anadolu_faktoring", .051)]),
    ("9200000505", "9100000044", "offers", [("anadolu_faktoring", .071), ("firat_finans", .079), ("harput_katilim", .068)]),
    ("9200000505", "9100000044", "waiting", []),
    ("9200000303", "9100000022", "financed", [("harput_katilim", .044), ("anadolu_faktoring", .046)]),
    ("9200000404", "9100000011", "offers", [("firat_finans", .053), ("harput_katilim", .057)]),
    ("9200000606", "9100000044", "waiting", []),
    ("9200000707", "9100000022", "financed", [("anadolu_faktoring", .048)]),
]


def session(role, username):
    s = requests.Session()
    r = s.post(f"{API}/login", json={"role": role, "username": username, "password": PASSWORD}, timeout=30)
    r.raise_for_status()
    return s


def make_invoice(n, seller, buyer):
    issue = TODAY - timedelta(days=random.randint(3, 40))
    inv = gen.make_invoice(f"SDX2026{n:06d}", seller, buyer, issue, gen.real_items(seller),
                           f"IRS{issue:%Y%m%d}{random.randint(100, 999)}", True, random.choice([60, 90, 120]), "seed")
    inv.pop("scenario")
    return inv


def main():
    companies = json.loads((ROOT / "data" / "companies.json").read_text(encoding="utf-8"))
    by_vkn = {c["vkn"]: c for c in companies}
    invoices = [make_invoice(i + 1, seller, buyer) for i, (seller, buyer, _, _) in enumerate(PLAN)]
    (ROOT / "data" / "gib_registry.json").write_text(json.dumps(invoices, ensure_ascii=False, indent=2), encoding="utf-8")
    financiers = {}
    tmp = Path(tempfile.mkdtemp())
    for (seller, buyer, outcome, offers), inv in zip(PLAN, invoices):
        kobi = session("kobi", seller)
        png = tmp / f"{inv['invoice_no']}.png"
        gen.draw_invoice(inv, by_vkn, png)
        with png.open("rb") as fh:
            doc = kobi.post(f"{API}/uploads", files={"file": (png.name, fh, "image/png")}, timeout=60).json()["document"]
        fields = {
            "invoice_no": inv["invoice_no"], "issue_date": inv["issue_date"], "due_date": inv["due_date"],
            "seller_vkn": seller, "seller_name": by_vkn[seller]["name"], "buyer_vkn": buyer, "buyer_name": by_vkn[buyer]["name"],
            "items": inv["items"], "subtotal": inv["subtotal"], "kdv": inv["kdv"], "total": inv["total"],
            "irsaliye_no": inv["irsaliye_no"], "buyer_approved": True,
        }
        checked = kobi.post(f"{API}/documents/{doc['id']}/check", json={"fields": fields}, timeout=300).json()
        kobi.post(f"{API}/documents/{doc['id']}/publish", timeout=60)
        made = []
        for name, discount in offers:
            fin = financiers.get(name) or financiers.setdefault(name, session("finansor", name))
            r = fin.post(f"{API}/offers", json={"document_id": doc["id"], "net_amount": round(inv["total"] * (1 - discount), 2),
                                                "note": "Vade ve alıcı ödeme geçmişine göre fiyatlandırıldı."}, timeout=60)
            made.append(r.json()["offer"])
        if outcome == "financed" and made:
            best = max(made, key=lambda o: o["net_amount"])
            kobi.post(f"{API}/offers/{best['id']}/accept", timeout=60)
        risk = checked.get("document", {}).get("risk_score")
        print(f"{doc['id']} {inv['invoice_no']} {by_vkn[seller]['name'][:24]:24} → {by_vkn[buyer]['name'][:22]:22} "
              f"{inv['total']:>12,.2f} TL  risk {risk}  {outcome} ({len(made)} teklif)")


if __name__ == "__main__":
    main()
