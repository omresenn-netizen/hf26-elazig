from io import BytesIO

from PIL import Image
import pytest

import gemma


def test_pdf_invoice_is_rendered_to_first_page_png(monkeypatch):
    seen = {}

    class FakeBitmap:
        def to_pil(self):
            return Image.new("RGB", (2, 2), color="white")

        def close(self):
            pass

    class FakePage:
        def get_size(self):
            return 1000, 1000

        def render(self, scale):
            assert scale == 2
            return FakeBitmap()

        def close(self):
            pass

    class FakeDocument:
        def __init__(self, content):
            assert content.startswith(b"%PDF-")

        def __len__(self):
            return 1

        def __getitem__(self, index):
            assert index == 0
            return FakePage()

        def close(self):
            pass

    def fake_chat(task, prompt, **kwargs):
        seen.update(task=task, **kwargs)
        return {"invoice_no": "PDF-1"}

    monkeypatch.setattr(gemma.pdfium, "PdfDocument", FakeDocument)
    monkeypatch.setattr(gemma, "_chat", fake_chat)

    result = gemma.extract_invoice(b"%PDF-1.7 demo", "invoice.pdf")

    assert result == {"invoice_no": "PDF-1"}
    assert seen["task"] == "extract_invoice"
    assert seen["image_filename"] == "invoice.pdf"
    assert seen["image_bytes"].startswith(b"\x89PNG\r\n\x1a\n")


def test_pdf_render_rejects_extreme_page_dimensions(monkeypatch):
    class FakePage:
        def get_size(self):
            return 100_000, 100_000

        def close(self):
            pass

    class FakeDocument:
        def __init__(self, content):
            pass

        def __len__(self):
            return 1

        def __getitem__(self, index):
            return FakePage()

        def close(self):
            pass

    monkeypatch.setattr(gemma.pdfium, "PdfDocument", FakeDocument)

    with pytest.raises(ValueError, match="görsele dönüştürülemedi"):
        gemma._pdf_to_png(b"%PDF-1.7 demo")
