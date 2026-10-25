"""Player names, compared across sources."""

import re
import unicodedata

from rapidfuzz import fuzz

# Letters that NFKD does not decompose into ASCII, so would otherwise be dropped.
_TRANSLITERATIONS = str.maketrans(
    {"đ": "d", "Đ": "D", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss", "ł": "l", "Ł": "L"}
)


def normalize(name: str) -> str:
    """Lower case ASCII words: accents and punctuation removed, hyphens split."""
    ascii_name = (
        unicodedata.normalize("NFKD", name.translate(_TRANSLITERATIONS))
        .encode("ascii", "ignore")
        .decode()
    )
    return " ".join(re.sub(r"[^a-z ]+", " ", ascii_name.lower()).split())


def similarity(a: str, b: str) -> float:
    """0 to 1. Word order and extra words do not count against a match ("Ezri Konsa Ngoyo"
    and "Ezri Konsa" score 1), so a high score alone can name the wrong teammate ("Gabriel"
    and "Gabriel Martinelli"): the rules that use it ask for other evidence too."""
    return fuzz.token_set_ratio(normalize(a), normalize(b)) / 100
