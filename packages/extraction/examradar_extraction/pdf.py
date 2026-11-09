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


def _configure_tesseract():
    """Use TESSERACT_CMD / TESSDATA_PREFIX from settings, or a project-local install in .tools/ocr if present."""
    import os

    import pytesseract
    from examradar_core.settings import REPO_ROOT, get_settings

    s = get_settings()
    local = REPO_ROOT / ".tools" / "ocr"
    cmd = s.tesseract_cmd or (str(local / "Library" / "bin" / "tesseract.exe") if (local / "Library" / "bin" / "tesseract.exe").exists() else None)
    data = s.tessdata_prefix or (str(local / "share" / "tessdata") if (local / "share" / "tessdata").exists() else None)
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    if data:
        os.environ["TESSDATA_PREFIX"] = data
    return pytesseract


def ocr_available() -> bool:
    try:
        _configure_tesseract().get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_page(page: "pymupdf.Page", lang: str = "eng+mal") -> str | None:
    try:
        pytesseract = _configure_tesseract()
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


_STOP = frozenset("the of and to in for is be by on with from are as at will shall this that which has have not all any who".split())
_ODD = re.compile(r"[a-z][A-Z]|[A-Za-z]\d[A-Za-z]|[A-Za-z][@{}<>\]\[$*][A-Za-z]")


def looks_garbled(text: str) -> bool:
    """A text layer of Latin-looking junk, as left by legacy Malayalam fonts or bad scanner OCR: almost no common
    English words and many tokens shaped like 'creJccru' or 'oorcoloilo5'. On real pages the odd share stays below 0.1."""
    toks = text.split()
    if len(toks) < 30:
        return False
    words = [w for w in (re.sub(r"[^A-Za-z]", "", t).lower() for t in toks) if w]
    stop = sum(w in _STOP for w in words) / max(len(words), 1)
    odd = sum(1 for t in toks if _ODD.search(t)) / len(toks)
    return odd >= 0.2 and stop < 0.05


def page_needs_ocr(text: str, has_images: bool) -> bool:
    if len(text.strip()) < 40 and has_images:
        return True
    if looks_garbled(text):
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
        if looks_garbled(text):
            q = min(q, 0.2)
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
