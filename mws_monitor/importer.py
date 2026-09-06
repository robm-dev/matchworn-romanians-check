from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Player, Watchlist
from .utils import csv_int, normalize_name, parse_market_value, utcnow


def import_watchlist(session: Session, csv_path: str | Path, name: str | None = None) -> int:
    path = Path(csv_path)
    watchlist_name = name or path.stem
    watchlist = session.scalar(select(Watchlist).where(Watchlist.name == watchlist_name))
    if not watchlist:
        watchlist = Watchlist(name=watchlist_name, source_path=str(path))
        session.add(watchlist)
    imported = 0
    seen: dict[str, Player] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"category", "rank", "name", "team", "age", "position", "value"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
        for row in reader:
            normalized = normalize_name(row["name"])
            player = seen.get(normalized) or session.scalar(select(Player).where(Player.normalized_name == normalized))
            rank = csv_int(row.get("rank"))
            market_value = parse_market_value(row.get("value"))
            category = row.get("category", "").strip()
            if player:
                categories = set(filter(None, player.categories.split(",")))
                if category:
                    categories.add(category)
                player.categories = ",".join(sorted(categories))
                player.market_value_eur = max(player.market_value_eur or 0, market_value)
                if rank and (player.best_rank is None or rank < player.best_rank):
                    player.best_rank = rank
                player.updated_at = utcnow()
            else:
                player = Player(
                    input_name=row["name"].strip(),
                    normalized_name=normalized,
                    team=row.get("team"),
                    age=csv_int(row.get("age")),
                    position=row.get("position"),
                    market_value_eur=market_value,
                    categories=category,
                    best_rank=rank,
                )
                session.add(player)
            seen[normalized] = player
            imported += 1
    return imported
