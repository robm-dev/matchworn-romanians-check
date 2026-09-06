from datetime import datetime, timedelta, timezone

from mws_monitor.models import Player
from mws_monitor.scoring import score_bargain


def test_elite_low_live_price_scores_high():
    player = Player(input_name="Lamine Yamal", normalized_name="lamine yamal", market_value_eur=200_000_000, best_rank=1)
    score, reason = score_bargain(
        player,
        900,
        "Issued, Signed",
        "live",
        datetime.now(timezone.utc) + timedelta(hours=4),
        [8_000, 9_000],
    )
    assert score >= 75
    assert "elite" in reason


def test_no_price_scores_zero():
    player = Player(input_name="Nobody", normalized_name="nobody", market_value_eur=1)
    assert score_bargain(player, None, "", "finished", None) == (0, "no EUR price")
