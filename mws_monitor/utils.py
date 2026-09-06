from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_name(value: str | None) -> str:
    text = (value or "").lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    replacements = {"ø": "o", "ı": "i", "ğ": "g", "ł": "l", "đ": "d"}
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_market_value(value: str | None) -> int:
    if not value:
        return 0
    cleaned = value.replace("€", "").replace(",", "").strip().lower()
    match = re.match(r"([0-9]+(?:\.[0-9]+)?)([mk]?)", cleaned)
    if not match:
        return 0
    amount = float(match.group(1))
    suffix = match.group(2)
    if suffix == "m":
        amount *= 1_000_000
    elif suffix == "k":
        amount *= 1_000
    return int(amount)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def csv_int(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None
