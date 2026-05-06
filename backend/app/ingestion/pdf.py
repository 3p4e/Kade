"""PDF text extraction with OCR fallback."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class PageText:
    page: int
    text: str
    via_ocr: bool


def _ocr_pdf_pages(pdf_path: Path) -> list[PageText]:
    """Render each page to an image and run Tesseract."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception as e:  # pragma: no cover
        logger.warning("OCR unavailable: %s", e)
        return []

    settings = get_settings()
    pages: list[PageText] = []
    images = convert_from_path(str(pdf_path), dpi=200)
    for i, img in enumerate(images, start=1):
        try:
            text = pytesseract.image_to_string(img, lang=settings.ocr_lang)
        except Exception as e:  # pragma: no cover
            logger.exception("OCR failed on page %d: %s", i, e)
            text = ""
        pages.append(PageText(page=i, text=text, via_ocr=True))
    return pages


def extract_pages(pdf_path: Path) -> list[PageText]:
    """Try direct PDF text extraction; fall back to OCR for pages with no text."""
    pages: list[PageText] = []
    doc = fitz.open(str(pdf_path))
    try:
        for i, page in enumerate(doc, start=1):
            txt = page.get_text("text") or ""
            pages.append(PageText(page=i, text=txt, via_ocr=False))
    finally:
        doc.close()

    # Heuristic: if ALL pages are empty, the PDF is likely scanned -> OCR everything.
    total_chars = sum(len(p.text.strip()) for p in pages)
    if total_chars < 40:
        logger.info("PDF appears scanned (%s); running OCR", pdf_path.name)
        ocr_pages = _ocr_pdf_pages(pdf_path)
        if ocr_pages:
            return ocr_pages

    # Otherwise OCR only the empty pages
    if any(len(p.text.strip()) < 20 for p in pages):
        try:
            from pdf2image import convert_from_path
            import pytesseract
        except Exception:
            return pages
        settings = get_settings()
        images = convert_from_path(str(pdf_path), dpi=200)
        for idx, page in enumerate(pages):
            if len(page.text.strip()) < 20 and idx < len(images):
                try:
                    page.text = pytesseract.image_to_string(images[idx], lang=settings.ocr_lang)
                    page.via_ocr = True
                except Exception:
                    pass
    return pages


def extract_text(pdf_path: Path) -> str:
    return "\n\n".join(p.text for p in extract_pages(pdf_path) if p.text)
