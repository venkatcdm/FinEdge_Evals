import re
from datetime import date
from typing import Optional

from dateutil import parser as date_parser

_FILLER_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "to",
        "of",
        "a",
        "an",
        "o",
        "os",
        "as",
        "um",
        "uma",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "por",
        "para",
        "com",
        "sem",
    }
)

_DIGITS_ID_MIN_LEN = 8


def invoice_digits_core(value: Optional[str]) -> str:
    """Digits-only core for matching Brazil NFe keys vs formatted invoice_id."""
    if value is None:
        return ""
    d = re.sub(r"\D", "", str(value).strip())
    d = d.lstrip("0")
    return d if d else ""


def normalize_invoice_id(inv_id: Optional[str]) -> Optional[str]:
    if inv_id is None:
        return None
    s = str(inv_id).strip()
    s = re.sub(r"\.pdf$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^inv_|^invoice_", "", s, flags=re.IGNORECASE)
    stripped = s.lstrip("0")
    return stripped if stripped else "0"


def groundtruth_digit_key(digits_core: str) -> Optional[str]:
    if len(digits_core) < _DIGITS_ID_MIN_LEN:
        return None
    return f"__dig__{digits_core}"


def normalize_currency_code(value: Optional[str]) -> str:
    if value is None:
        return ""
    s = str(value).strip().casefold().replace(" ", "")
    if not s:
        return ""

    alias = {
        "r$": "BRL",
        "reais": "BRL",
        "real": "BRL",
        "brl": "BRL",
        "brazil": "BRL",
        "us$": "USD",
        "usd": "USD",
        "dollar": "USD",
        "dólares": "USD",
        "dolares": "USD",
        "€": "EUR",
        "eur": "EUR",
        "£": "GBP",
        "gbp": "GBP",
    }

    for k, iso in alias.items():
        if s == k or k in s:
            return iso

    if len(s) == 3 and s.isalpha():
        return s.upper()

    return s.upper()


def parse_calendar_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        dt = date_parser.parse(
            s,
            dayfirst=True,
            yearfirst=False,
            fuzzy=False,
        )
        return dt.date()
    except (ValueError, OverflowError, TypeError):
        return None


def normalize_text(text, strip_fillers: bool = True) -> str:
    if text is None:
        return ""

    text = str(text).strip().lower()
    text = re.sub(r"[^\w\s€%/-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    if strip_fillers:
        words = [w for w in text.split() if w not in _FILLER_WORDS]
        text = " ".join(words).strip()

    return text


def normalize_number(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().replace(" ", "")
    if not s:
        return None

    try:
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s and s.count(",") == 1:
            parts = s.split(",")
            if len(parts[1]) <= 2:
                s = s.replace(",", ".")

        s = s.replace("€", "").replace("%", "").replace(" ", "")
        return float(s)
    except (ValueError, TypeError):
        return None