from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from .transfermarkt_romanian_players import TRANSFERMARKT_BASE_URL, _parse_market_value

TOP_PLAYER_FIELDS = [
    "rank",
    "name",
    "team",
    "position",
    "market_value_eur",
    "age",
    "source_url",
    "list_source_url",
]


def parse_top_players(html: str, list_source_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("table.items tbody tr.odd, table.items tbody tr.even"):
        cells = tr.select("td")
        if len(cells) < 9:
            continue
        profile_link = cells[3].select_one('a[href*="/profil/spieler/"]')
        if not profile_link:
            continue
        club_link = cells[7].select_one("a[title]")
        rows.append(
            {
                "rank": cells[0].get_text(" ", strip=True),
                "name": profile_link.get_text(" ", strip=True),
                "team": club_link.get("title", "").strip() if club_link else "",
                "position": cells[4].get_text(" ", strip=True),
                "market_value_eur": str(_parse_market_value(cells[8].get_text(" ", strip=True)) or ""),
                "age": cells[5].get_text(" ", strip=True),
                "source_url": urljoin(TRANSFERMARKT_BASE_URL, profile_link["href"]),
                "list_source_url": list_source_url,
            }
        )
    return rows


def update_top_players_csv(
    source_url: str,
    output_csv_path: str | Path,
    *,
    fetch_html: Callable[[str], str] | None = None,
    limit: int = 200,
    page_size: int = 25,
    request_delay_seconds: float = 1.0,
) -> int:
    fetch = fetch_html or _fetch_transfermarkt_html
    rows: list[dict[str, str]] = []
    seen_profiles: set[str] = set()
    page = 1
    while len(rows) < limit:
        url = _with_page(source_url, page)
        page_rows = parse_top_players(fetch(url), url)
        if not page_rows:
            break
        new_count = 0
        for row in page_rows:
            if row["source_url"] in seen_profiles:
                continue
            seen_profiles.add(row["source_url"])
            rows.append(row)
            new_count += 1
            if len(rows) >= limit:
                break
        if new_count == 0 or len(page_rows) < page_size:
            break
        page += 1
        if fetch_html is None:
            time.sleep(request_delay_seconds)

    output = Path(output_csv_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TOP_PLAYER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _with_page(url: str, page: int) -> str:
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["page"] = str(page)
    return urlunparse(parsed._replace(query=urlencode(params)))


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
