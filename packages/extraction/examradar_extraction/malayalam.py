"""Repair Malayalam extracted from PDFs that use legacy font mappings.

Such PDFs store pre-base vowel signs (െ േ ൈ) before the consonant, in visual order, so the text layer
reads 'േകരള' where Unicode order is 'കേരള'. We reorder them and recombine two-part vowel signs.
"""

import re
import unicodedata

PRE_BASE = "െേൈ"  # െ േ ൈ
VIRAMA = "്"
AA = "ാ"  # ാ
AU_LENGTH = "ൗ"  # ൗ
ZW = "‌‍"


def _is_consonant(ch: str) -> bool:
    return "ക" <= ch <= "ഹ" or ch in "ൺൻർൽൾൿ"


def fix_visual_order(s: str) -> str:
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        # In correct Unicode a vowel sign follows its consonant. Only a sign that does not follow one is misplaced.
        prev = s[i - 1] if i else " "
        follows_base = _is_consonant(prev) or prev in (VIRAMA + ZW)
        if ch in PRE_BASE and not follows_base and i + 1 < n and _is_consonant(s[i + 1]):
            j = i + 1
            cluster = s[j]
            j += 1
            while j + 1 < n and s[j] == VIRAMA and (_is_consonant(s[j + 1]) or s[j + 1] in ZW):
                if s[j + 1] in ZW:
                    cluster += s[j : j + 2]
                    j += 2
                    continue
                cluster += s[j : j + 2]
                j += 2
            if j < n and s[j] == AA and ch in "െേ":
                out.append(cluster + ("ൊ" if ch == "െ" else "ോ"))
                j += 1
            elif j < n and s[j] == AU_LENGTH and ch == "െ":
                out.append(cluster + "ൌ")
                j += 1
            else:
                out.append(cluster + ch)
            i = j
        else:
            out.append(ch)
            i += 1
    return unicodedata.normalize("NFC", "".join(out))


_ML_CHAR = re.compile(r"[ഀ-ൿ]")
_DEPENDENT = set("ാിീുൂൃെേൈൊോൌ്ൗ")


def malayalam_ratio(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    return (sum(1 for c in letters if _ML_CHAR.match(c)) / len(letters)) if letters else 0.0


def malayalam_quality(s: str) -> float:
    """1.0 means no structural errors. Counts vowel signs that cannot legally appear where they are."""
    ml = [c for c in s if _ML_CHAR.match(c)]
    if not ml:
        return 1.0
    bad = 0
    prev = " "
    for c in s:
        if c in _DEPENDENT and (prev in _DEPENDENT and c != "്" or not _ML_CHAR.match(prev)):
            bad += 1
        prev = c
    # Long runs of Malayalam with no spaces are another sign of a broken text layer.
    runs = re.findall(r"[ഀ-ൿ]{40,}", s)
    bad += sum(len(r) // 40 for r in runs) * 5
    return max(0.0, 1.0 - bad / max(len(ml), 1) * 10)


def normalise_for_match(s: str) -> str:
    s = fix_visual_order(unicodedata.normalize("NFC", s))
    s = s.replace("‌", "").replace("‍", "")
    return re.sub(r"\s+", " ", s).strip().lower()
