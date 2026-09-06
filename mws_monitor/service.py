from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, load_aliases
from .matcher import resolve_match, search_terms_for
from .models import Alert, MwsAthlete, MwsProduct, Player, PlayerAlias, PriceSnapshot, ReviewQueue
from .mws_client import MwsClient
from .scoring import score_bargain
from .utils import parse_dt, utcnow


def sync_aliases(session: Session) -> None:
    for input_name, row in load_aliases().items():
        alias = session.scalar(select(PlayerAlias).where(PlayerAlias.input_name == input_name))
        if not alias:
            alias = PlayerAlias(input_name=input_name)
            session.add(alias)
        alias.preferred_mws_athlete_name = row.get("preferred_mws_athlete_name") or None
        alias.preferred_mws_category_id = row.get("preferred_mws_category_id") or None
        alias.notes = row.get("notes") or None


def eur_price(prices: list[dict] | None) -> int | None:
    for item in prices or []:
        if isinstance(item, dict) and item.get("currency") == "EUR":
            return item.get("price")
    return None


def labels_text(product: dict) -> str:
    labels = []
    for label in product.get("labels") or []:
        if isinstance(label, dict):
            labels.append(label.get("text", ""))
        else:
            labels.append(str(label))
    return ", ".join(filter(None, labels))


def product_status(product: dict) -> str:
    now = datetime.now(timezone.utc)
    start = parse_dt(product.get("start_date"))
    end = parse_dt(product.get("end_date"))
    if product.get("finished") or (end and end <= now):
        return "finished"
    if start and start > now:
        return "not_started"
    return "live"


def shirt_team_from_detail(detail: dict) -> str | None:
    teams = []
    for category in detail.get("categories") or []:
        ref = category.get("external_reference") or {}
        if ref.get("type") == "team":
            teams.append(category.get("name") or category.get("canonical_name"))
    return "; ".join(filter(None, teams)) or None


class MonitorService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.client = MwsClient(settings)

    def close(self) -> None:
        self.client.close()

    def resolve_player(self, player: Player):
        alias = self.session.scalar(select(PlayerAlias).where(PlayerAlias.input_name == player.input_name))
        alias_dict = None
        if alias:
            alias_dict = {
                "preferred_mws_athlete_name": alias.preferred_mws_athlete_name or "",
                "preferred_mws_category_id": alias.preferred_mws_category_id or "",
                "notes": alias.notes or "",
            }
        candidates: list[dict] = []
        for term in search_terms_for(player.input_name, alias_dict):
            data = self.client.search_products(term)
            candidates.extend(data.get("category_filters", {}).get("athlete", []))
        deduped = {candidate.get("id"): candidate for candidate in candidates if candidate.get("id")}
        match = resolve_match(player.input_name, list(deduped.values()), alias_dict)
        if match.status == "found" and match.category_id:
            athlete = self.session.scalar(select(MwsAthlete).where(MwsAthlete.mws_category_id == match.category_id))
            if not athlete:
                athlete = MwsAthlete(mws_category_id=match.category_id, name=match.athlete_name or player.input_name)
                self.session.add(athlete)
            athlete.name = match.athlete_name or athlete.name
            athlete.confidence = match.confidence
            athlete.match_note = match.note
            athlete.player_id = player.id
        else:
            self.enqueue_review(player, match.note, match.candidates)
        return match

    def enqueue_review(self, player: Player, reason: str, candidates: list[dict]) -> None:
        exists = self.session.scalar(
            select(ReviewQueue).where(ReviewQueue.player_id == player.id, ReviewQueue.status == "open")
        )
        if exists:
            return
        self.session.add(
            ReviewQueue(
                player_id=player.id,
                input_name=player.input_name,
                reason=reason,
                candidates_json=json.dumps(candidates, ensure_ascii=False),
            )
        )

    def crawl_player(self, player: Player) -> dict[str, int | str]:
        match = self.resolve_player(player)
        if match.status != "found" or not match.category_id:
            return {"player": player.input_name, "status": match.status, "products": 0}
        data = self.client.products_for_category(match.category_id)
        products = data.get("results") or []
        count = 0
        for product in products:
            if product.get("type") != "football_shirt":
                continue
            self.upsert_product(player, match.athlete_name or player.input_name, product)
            count += 1
        return {"player": player.input_name, "status": "found", "products": count}

    def upsert_product(self, player: Player, athlete_name: str, product: dict) -> MwsProduct:
        mws_id = product.get("id") or product.get("slug")
        slug = product.get("slug")
        item = self.session.scalar(select(MwsProduct).where(MwsProduct.mws_product_id == mws_id))
        if not item:
            item = MwsProduct(mws_product_id=mws_id, slug=slug, url=f"{self.settings.mws_web_base_url}/{slug}", player_id=player.id)
            self.session.add(item)
        status = product_status(product)
        price = eur_price(product.get("prices"))
        detail = {}
        if slug:
            try:
                detail = self.client.product_detail(slug)
            except Exception:
                detail = {}
        historical = [
            row[0]
            for row in self.session.execute(
                select(MwsProduct.final_price_eur).where(MwsProduct.player_id == player.id, MwsProduct.final_price_eur.is_not(None))
            ).all()
            if row[0]
        ]
        labels = labels_text(product)
        score, reason = score_bargain(player, price, labels, status, parse_dt(product.get("end_date")), historical)
        item.slug = slug
        item.url = f"{self.settings.mws_web_base_url}/{slug}"
        item.player_id = player.id
        item.mws_athlete_name = athlete_name
        item.shirt_team = shirt_team_from_detail(detail)
        item.event_name = detail.get("event_name") or product.get("product_event_name")
        item.labels = labels
        item.status = status
        item.sales_method = product.get("sales_method")
        item.start_date = parse_dt(product.get("start_date"))
        item.end_date = parse_dt(product.get("end_date"))
        item.latest_price_eur = price
        item.final_price_eur = price if status == "finished" else None
        item.bargain_score = score
        item.bargain_reason = reason
        item.fetched_at = utcnow()
        self.session.flush()
        self.session.add(PriceSnapshot(product_id=item.id, price_eur=price, status=status))
        self.maybe_alert(player, item)
        return item

    def maybe_alert(self, player: Player, product: MwsProduct) -> None:
        if product.status != "live":
            return
        price = product.latest_price_eur or 0
        market = player.market_value_eur or 0
        thresholds = self.settings.alert_thresholds
        messages = []
        if market >= thresholds.get("high_value_market_value_eur", 50_000_000) and price < thresholds.get("high_value_price_eur", 500):
            messages.append(f"{player.input_name} live shirt under EUR {thresholds.get('high_value_price_eur', 500)}")
        if market >= thresholds.get("elite_market_value_eur", 100_000_000) and price < thresholds.get("elite_price_eur", 1000):
            messages.append(f"{player.input_name} elite-player shirt under EUR {thresholds.get('elite_price_eur', 1000)}")
        if product.bargain_score >= thresholds.get("closing_score", 75):
            messages.append(f"{player.input_name} bargain score {product.bargain_score}: {product.bargain_reason}")
        for message in messages:
            self.session.add(Alert(product_id=product.id, level="bargain", message=f"{message} - {product.url}"))

    def crawl_all(self) -> list[dict[str, int | str]]:
        sync_aliases(self.session)
        results = []
        for player in self.session.scalars(select(Player).order_by(Player.market_value_eur.desc())).all():
            results.append(self.crawl_player(player))
            self.session.commit()
        return results


def export_results(session: Session, path: str | Path) -> int:
    rows = session.execute(
        select(Player, MwsProduct)
        .join(MwsProduct, MwsProduct.player_id == Player.id, isouter=True)
        .order_by(Player.market_value_eur.desc(), MwsProduct.bargain_score.desc().nullslast())
    ).all()
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "category",
        "rank",
        "name",
        "team",
        "age",
        "position",
        "value",
        "mws_status",
        "mws_athlete",
        "mws_last_price_eur",
        "mws_last_date",
        "mws_type",
        "mws_url",
        "mws_match_note",
        "bargain_score",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for player, product in rows:
            writer.writerow(
                {
                    "category": player.categories,
                    "rank": player.best_rank,
                    "name": player.input_name,
                    "team": player.team,
                    "age": player.age,
                    "position": player.position,
                    "value": player.market_value_eur,
                    "mws_status": product.status if product else "not_found",
                    "mws_athlete": product.mws_athlete_name if product else "",
                    "mws_last_price_eur": product.latest_price_eur if product else "",
                    "mws_last_date": product.end_date.date().isoformat() if product and product.end_date else "",
                    "mws_type": product.labels if product else "",
                    "mws_url": product.url if product else "",
                    "mws_match_note": product.bargain_reason if product else "",
                    "bargain_score": product.bargain_score if product else "",
                }
            )
    return len(rows)
