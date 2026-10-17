"""Shared test setup: tests never call the real local Ollama (CI has no GPU or model).

Individual tests can still monkeypatch a Gemma function with their own fake; this only sets safe defaults.
"""
import pytest

import gemma


@pytest.fixture(autouse=True)
def offline_gemma(monkeypatch):
    monkeypatch.setattr(gemma, "explain_flags", lambda invoice, flags: "Test açıklaması; insan incelemesi gerekir.")
    monkeypatch.setattr(gemma, "extract_invoice", lambda image, name: {})
    monkeypatch.setattr(gemma, "risk_report", lambda invoice, buyer: {"summary": "Test risk özeti.", "suggested_discount_rate": 0.05})
    monkeypatch.setattr(gemma, "compare_offers", lambda offers: {"recommendation": "Teklif 1", "reason": "Test."})

    def no_network(*args, **kwargs):
        raise RuntimeError("Tests must not call the real Ollama server; monkeypatch the Gemma function instead.")

    monkeypatch.setattr(gemma, "_chat", no_network)
