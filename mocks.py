"""Deterministic demo-only stand-ins for external financial services."""
import hashlib
import json
from pathlib import Path


def _token(*values):
    source = "|".join(str(value) for value in values)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def verify_invoice(invoice, invoices):
    invoice_no = invoice.get("invoice_no")
    found = next((item for item in invoices if item.get("invoice_no") == invoice_no), None)
    return {
        "service": "DEMO / MOCK — GİB e-Fatura",
        "verified": found is not None,
        "invoice_no": invoice_no,
        "buyer_approved": found.get("buyer_approved") if found else None,
    }


def buyer_credit_score(buyer_vkn):
    companies_path = Path(__file__).resolve().parent / "data" / "companies.json"
    companies = json.loads(companies_path.read_text(encoding="utf-8"))
    company = next((item for item in companies if item.get("vkn") == buyer_vkn), None)
    basis = (buyer_vkn, company.get("employees"), company.get("founded")) if company else (buyer_vkn,)
    score = 300 + int(_token(*basis)[:8], 16) % 601
    return {
        "service": "DEMO / MOCK — Findex benzeri",
        "score": score,
        "company": company.get("name") if company else None,
    }


def bank_transfer(invoice_no, amount):
    transfer_id = "DEMO-" + _token(invoice_no, amount)[:12].upper()
    return {
        "service": "DEMO / MOCK — Banka transferi",
        "simulated": True,
        "transfer_id": transfer_id,
        "amount": amount,
    }


def e_signature(signer_vkn, document_id):
    signature_id = "DEMO-" + _token(signer_vkn, document_id)[:12].upper()
    return {
        "service": "DEMO / MOCK — E-imza",
        "signed": True,
        "signature_id": signature_id,
    }
