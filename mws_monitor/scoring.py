from __future__ import annotations

from datetime import datetime, timezone
from statistics import median

from .models import Player


def score_bargain(
    player: Player,
    price_eur: int | None,
    labels: str,
    status: str,
    end_date: datetime | None,
    historical_prices: list[int] | None = None,
) -> tuple[int, str]:
    if not price_eur or price_eur <= 0:
        return 0, "no EUR price"
    reasons: list[str] = []
    score = 0
    market = player.market_value_eur or 0

    if market >= 100_000_000 and price_eur < 1_000:
        score += 35
        reasons.append("elite player under EUR 1k")
    elif market >= 50_000_000 and price_eur < 500:
        score += 30
        reasons.append("high-value player under EUR 500")
    elif market:
        ratio = price_eur / market
        if ratio < 0.00002:
            score += 25
            reasons.append("very low price-to-market ratio")
        elif ratio < 0.00005:
            score += 15
            reasons.append("low price-to-market ratio")

    lower_labels = labels.lower()
    if "worn" in lower_labels:
        score += 16
        reasons.append("worn")
    if "signed" in lower_labels:
        score += 10
        reasons.append("signed")
    if "issued" in lower_labels and "worn" not in lower_labels:
        score += 3
        reasons.append("issued")

    if player.best_rank and player.best_rank <= 10:
        score += 10
        reasons.append("top 10 watchlist rank")
    elif player.best_rank and player.best_rank <= 25:
        score += 5
        reasons.append("top 25 watchlist rank")

    if status == "live" and end_date:
        hours_left = (end_date - datetime.now(timezone.utc)).total_seconds() / 3600
        if 0 <= hours_left <= 6:
            score += 18
            reasons.append("closing within 6h")
        elif 0 <= hours_left <= 24:
            score += 10
            reasons.append("closing within 24h")

    if historical_prices:
        med = median(historical_prices)
        if med and price_eur < med * 0.65:
            score += 14
            reasons.append("below player historical median")

    return min(100, int(score)), ", ".join(reasons) or "baseline"
