from __future__ import annotations

import csv
import re
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

TRANSFERMARKT_BASE_URL = "https://www.transfermarkt.com"
PLAYER_FIELDS = [
    "Nume",
    "Echipă",
    "Post",
    "M.V. (EUR)",
    "Vârstă",
    "Țara campionatului",
    "Competiție",
    "Profil Transfermarkt",
    "Lista sursă",
]


def discover_source_bases(csv_path: str | Path) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            source_url = (row.get("Lista sursă") or "").strip()
            if not source_url:
                continue
            base_url = re.sub(r"/page/\d+/?$", "", source_url.rstrip("/"))
            seen.setdefault(base_url, (row.get("Țara campionatului") or "").strip())
    return list(seen.items())


def parse_transfermarkt_players(html: str, source_url: str, country: str = "") -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("table.items tbody tr.odd, table.items tbody tr.even"):
        cells = tr.select("td")
        if len(cells) < 13:
            continue
        profile_link = cells[3].select_one('a[href*="/profil/spieler/"]')
        if not profile_link:
            continue
        rows.append(
            {
                "Nume": profile_link.get_text(" ", strip=True),
                "Echipă": cells[9].get_text(" ", strip=True),
                "Post": cells[4].get_text(" ", strip=True),
                "M.V. (EUR)": str(_parse_market_value(cells[12].get_text(" ", strip=True)) or ""),
                "Vârstă": cells[5].get_text(" ", strip=True),
                "Țara campionatului": country,
                "Competiție": cells[10].get_text(" ", strip=True),
                "Profil Transfermarkt": urljoin(TRANSFERMARKT_BASE_URL, profile_link["href"]),
                "Lista sursă": source_url,
            }
        )
    return rows


def update_romanian_player_csv(
    source_csv_path: str | Path,
    output_csv_path: str | Path,
    *,
    fetch_html: Callable[[str], str] | None = None,
    page_size: int = 25,
    request_delay_seconds: float = 1.0,
) -> int:
    fetch = fetch_html or _fetch_transfermarkt_html
    all_rows: list[dict[str, str]] = []
    seen_profiles: set[str] = set()
    for base_url, country in discover_source_bases(source_csv_path):
        page = 1
        while True:
            url = base_url if page == 1 else f"{base_url}/page/{page}"
            html = fetch(url)
            rows = parse_transfermarkt_players(html, url, country)
            new_rows = [row for row in rows if row["Profil Transfermarkt"] not in seen_profiles]
            for row in new_rows:
                seen_profiles.add(row["Profil Transfermarkt"])
            all_rows.extend(new_rows)
            if not new_rows or len(rows) < page_size:
                break
            page += 1
            if fetch_html is None:
                time.sleep(request_delay_seconds)

    all_rows.sort(key=lambda row: (_market_sort_value(row), row["Nume"]))
    output = Path(output_csv_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLAYER_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    return len(all_rows)


def _fetch_transfermarkt_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    with httpx.Client(headers=headers, follow_redirects=True, timeout=20) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _parse_market_value(value: str) -> int | None:
    text = value.strip().replace("€", "").replace(",", "")
    if not text or text == "-":
        return None
    multiplier = 1
    if text.lower().endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]
    elif text.lower().endswith("k"):
        multiplier = 1_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def _market_sort_value(row: dict[str, str]) -> int:
    try:
        return -int(row.get("M.V. (EUR)") or 0)
    except ValueError:
        return 0
