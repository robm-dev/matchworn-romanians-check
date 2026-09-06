from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .config import Settings, load_settings
from .mws_client import MwsClient
from .pricing_knn import (
    bid_ladder,
    estimate_fair_knn,
    labels_to_mws_type,
    load_comp_rows_from_workbook,
    load_tm_overrides_csv,
    parse_event_player_title,
)
from .utils import normalize_name


def _eur_price(product: dict[str, Any]) -> int | None:
    for item in product.get("prices") or []:
        if isinstance(item, dict) and item.get("currency") == "EUR":
            return int(item["price"]) if item.get("price") is not None else None
    return None


def run_event_pricing(
    *,
    event_slug: str,
    workbook_path: str | Path,
    tm_csv_path: str | Path | None,
    output_csv_path: str | Path,
    k_neighbors: int = 7,
    settings: Settings | None = None,
) -> int:
    """
    Fetch all products for an MWS event, optionally merge Transfermarkt-style fields from tm_csv,
    estimate fair EUR via kNN against the ranked workbook, write a CSV report.
    """
    settings = settings or load_settings()
    comps = load_comp_rows_from_workbook(workbook_path)
    overrides_by_name: dict[str, dict[str, int | None]] = {}
    overrides_by_slug: dict[str, dict[str, int | None]] = {}
    if tm_csv_path:
        overrides_by_name, overrides_by_slug = load_tm_overrides_csv(tm_csv_path)

    client = MwsClient(settings)
    try:
        event = client.event_by_slug(event_slug, cache=False)
        event_id = event.get("id")
        if not event_id:
            raise RuntimeError(f"Event {event_slug!r} has no id in API response")
        data = client.products_for_event(str(event_id), page_size=100, cache=False)
        products = data.get("results") or []
    finally:
        client.close()

    out_path = Path(output_csv_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "event_slug",
        "event_name",
        "mws_title",
        "player_name",
        "club",
        "mws_slug",
        "labels_mws_type",
        "current_bid_eur",
        "market_value_eur",
        "mws_last_used_eur",
        "last_source",
        "fair_price_knn_eur",
        "steal_bid_eur",
        "strong_bid_eur",
        "max_bid_eur",
        "current_vs_fair_pct",
        "knn_note",
    ]
    event_name = (event.get("canonical_name") or event.get("name") or "").strip()

    rows_written = 0
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for product in products:
            title = (product.get("canonical_name") or "").strip()
            slug = product.get("slug") or ""
            labels = labels_to_mws_type(product.get("labels"))
            current = _eur_price(product) or 0
            player_name, club = parse_event_player_title(title)
            key = normalize_name(player_name)
            ovr: dict[str, int | None] = {}
            if slug:
                ovr.update(overrides_by_slug.get(slug.lower()) or {})
            ovr.update(overrides_by_name.get(key) or {})
            mv = ovr.get("market_value_eur")
            last_override = ovr.get("mws_last_price_eur")
            if last_override is not None and last_override > 0:
                last_used = int(last_override)
                last_source = "tm_csv"
            else:
                last_used = int(current) if current > 0 else 0
                last_source = "live_bid_proxy" if current > 0 else "missing"

            is_squad = title.lower().startswith("squad signed")
            if is_squad or not player_name:
                fair, note = 0, "team lot — no single-player kNN"
                steal, strong, mx = 0, 0, 0
                vs_fair = ""
            elif mv is None or mv <= 0:
                fair, note = 0, "missing market_value_eur (add to tm-csv)"
                steal, strong, mx = 0, 0, 0
                vs_fair = ""
            elif last_used <= 0:
                fair, note = 0, "missing last price / live bid"
                steal, strong, mx = 0, 0, 0
                vs_fair = ""
            else:
                fair, note = estimate_fair_knn(float(mv), float(last_used), labels, comps, k=k_neighbors)
                steal, strong, mx = bid_ladder(fair)
                vs_fair = f"{(current / fair - 1.0):.3f}" if fair and current else ""

            writer.writerow(
                {
                    "event_slug": event_slug,
                    "event_name": event_name,
                    "mws_title": title,
                    "player_name": player_name,
                    "club": club or "",
                    "mws_slug": slug,
                    "labels_mws_type": labels,
                    "current_bid_eur": current,
                    "market_value_eur": mv if mv is not None else "",
                    "mws_last_used_eur": last_used if last_source != "missing" else "",
                    "last_source": last_source,
                    "fair_price_knn_eur": fair,
                    "steal_bid_eur": steal,
                    "strong_bid_eur": strong,
                    "max_bid_eur": mx,
                    "current_vs_fair_pct": vs_fair,
                    "knn_note": note,
                }
            )
            rows_written += 1
    return rows_written
