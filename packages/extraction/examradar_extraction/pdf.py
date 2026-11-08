"""Text, tables, and OCR. Documents are parsed only; nothing in them is executed or followed."""

import io
import re
from dataclasses import dataclass, field

import pymupdf

from .malayalam import fix_visual_order, malayalam_quality, malayalam_ratio


@dataclass
class DocText:
    pages: list[str]
    tables: dict[int, list[list[list[str]]]] = field(default_factory=dict)  # page index -> tables -> rows
    ocr_used: bool = False
    quality: float = 1.0
    language: str = "en"
    kind: str = "pdf"

    @property
    def text(self) -> str:
        return "\n".join(self.pages)

    def page_of(self, offset: int) -> int:
        pos = 0
        for i, p in enumerate(self.pages):
            pos += len(p) + 1
            if offset < pos:
                return i + 1
        return len(self.pages)


def ocr_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_page(page: "pymupdf.Page", lang: str = "eng+mal") -> str | None:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None
    try:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang=lang)
    except Exception:
        return None


def _english_quality(text: str) -> float:
    if not text.strip():
        return 0.0
    good = sum(1 for c in text if c.isalnum() or c.isspace() or c in ".,:;()/-₹%&'\"")
    return good / len(text)


def page_needs_ocr(text: str, has_images: bool) -> bool:
    if len(text.strip()) < 40 and has_images:
        return True
    if malayalam_ratio(text) > 0.3 and malayalam_quality(text) < 0.5:
        return True
    return _english_quality(text) < 0.6


def extract_pdf(data: bytes, tables: bool = False, ocr: str = "auto", max_pages: int = 120) -> DocText:
    doc = pymupdf.open(stream=data, filetype="pdf")
    pages: list[str] = []
    out_tables: dict[int, list[list[list[str]]]] = {}
    used_ocr = False
    qualities: list[float] = []
    for i in range(doc.page_count):
        page = doc[i]
        if i >= max_pages:
            break
        text = page.get_text()
        if malayalam_ratio(text) > 0.05:
            text = fix_visual_order(text)
        if ocr != "never" and page_needs_ocr(text, bool(page.get_images())):
            o = _ocr_page(page)
            if o and len(o.strip()) > len(text.strip()) * 0.5:
                text, used_ocr = o, True
        pages.append(text)
        q = _english_quality(text)
        if malayalam_ratio(text) > 0.3:
            q = min(q, malayalam_quality(text))
        qualities.append(q)
        if tables:
            try:
                found = page.find_tables()
                rows = [t.extract() for t in found.tables]
                if rows:
                    out_tables[i] = [[[c or "" for c in r] for r in t] for t in rows]
            except Exception:
                pass
    full = "\n".join(pages)
    lang = "ml" if malayalam_ratio(full) > 0.5 else ("en+ml" if malayalam_ratio(full) > 0.05 else "en")
    quality = sum(qualities) / len(qualities) if qualities else 0.0
    return DocText(pages, out_tables, used_ocr, round(quality, 3), lang, "pdf")


def extract_html(data: bytes | str, selector: str | None = None) -> DocText:
    from examradar_adapters.normalise import main_text

    text = main_text(data, selector)
    return DocText([text], {}, False, _english_quality(text), "en", "html")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
