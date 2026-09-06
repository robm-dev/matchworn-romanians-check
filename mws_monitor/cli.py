from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import select

from .config import load_settings
from .db import init_db, session_scope
from .importer import import_watchlist
from .models import Alert, MwsProduct, Player, ReviewQueue
from .event_pricing import run_event_pricing
from .romanian_auctions import run_romanian_auctions
from .service import MonitorService, export_results, sync_aliases
from .transfermarkt_romanian_players import update_romanian_player_csv
from .transfermarkt_top_players import update_top_players_csv


def cmd_init_db(_args: argparse.Namespace) -> None:
    init_db()
    with session_scope() as session:
        sync_aliases(session)
    print("Database initialized.")


def cmd_import_watchlist(args: argparse.Namespace) -> None:
    init_db()
    with session_scope() as session:
        count = import_watchlist(session, args.csv_path, args.name)
    print(f"Imported {count} watchlist rows.")


def cmd_crawl_now(_args: argparse.Namespace) -> None:
    init_db()
    settings = load_settings()
    with session_scope() as session:
        service = MonitorService(session, settings)
        try:
            results = service.crawl_all()
        finally:
            service.close()
    found = sum(1 for row in results if row["status"] == "found")
    print(f"Crawled {len(results)} players. Found MWS products for {found}.")


def cmd_monitor_live(_args: argparse.Namespace) -> None:
    settings = load_settings()
    scheduler = BlockingScheduler()

    def job() -> None:
        with session_scope() as session:
            service = MonitorService(session, settings)
            try:
                service.crawl_all()
            finally:
                service.close()

    scheduler.add_job(job, "interval", minutes=settings.crawl_interval_minutes, next_run_time=None)
    print(f"Monitoring every {settings.crawl_interval_minutes} minutes. Press Ctrl+C to stop.")
    job()
    scheduler.start()


def cmd_export_results(args: argparse.Namespace) -> None:
    init_db()
    with session_scope() as session:
        count = export_results(session, args.output_path)
    print(f"Exported {count} rows to {args.output_path}.")


def cmd_review_matches(_args: argparse.Namespace) -> None:
    init_db()
    with session_scope() as session:
        rows = session.scalars(select(ReviewQueue).where(ReviewQueue.status == "open").order_by(ReviewQueue.created_at.desc())).all()
        if not rows:
            print("No open review items.")
            return
        for row in rows:
            print(f"[{row.id}] {row.input_name}: {row.reason}")


def cmd_show_bargains(args: argparse.Namespace) -> None:
    init_db()
    with session_scope() as session:
        rows = session.execute(
            select(Player, MwsProduct)
            .join(MwsProduct, MwsProduct.player_id == Player.id)
            .where(MwsProduct.bargain_score >= args.min_score)
            .order_by(MwsProduct.bargain_score.desc(), MwsProduct.latest_price_eur.asc())
            .limit(args.limit)
        ).all()
        if not rows:
            print("No bargains found yet.")
            return
        for player, product in rows:
            price = product.latest_price_eur or product.final_price_eur or 0
            print(f"{product.bargain_score:3d}  EUR {price:>6,}  {player.input_name}  {product.labels or ''}  {product.url}")


def cmd_backfill_finished(args: argparse.Namespace) -> None:
    cmd_crawl_now(args)


def cmd_serve(args: argparse.Namespace) -> None:
    init_db()
    uvicorn.run("mws_monitor.web:app", host=args.host, port=args.port, reload=args.reload)


def cmd_event_pricing(args: argparse.Namespace) -> None:
    settings = load_settings()
    n = run_event_pricing(
        event_slug=args.event_slug,
        workbook_path=args.workbook,
        tm_csv_path=args.tm_csv,
        output_csv_path=args.output,
        k_neighbors=args.k_neighbors,
        settings=settings,
    )
    print(f"Wrote {n} rows to {args.output}")


def cmd_romanian_auctions(args: argparse.Namespace) -> None:
    settings = load_settings()
    matches = run_romanian_auctions(args.players, args.output_dir, settings)
    print(f"Matched {len(matches)} live bidding shirts. Wrote latest.csv, latest.json, and latest.md to {args.output_dir}.")


def cmd_u23_auctions(args: argparse.Namespace) -> None:
    settings = load_settings()
    matches = run_romanian_auctions(args.players, args.output_dir, settings)
    print(f"Matched {len(matches)} live bidding shirts. Wrote latest.csv, latest.json, and latest.md to {args.output_dir}.")


def cmd_update_romanian_players(args: argparse.Namespace) -> None:
    count = update_romanian_player_csv(
        source_csv_path=args.source,
        output_csv_path=args.output,
        request_delay_seconds=args.delay,
    )
    print(f"Wrote {count} Romanian players to {args.output}.")


def cmd_update_u23_players(args: argparse.Namespace) -> None:
    count = update_top_players_csv(
        source_url=args.source_url,
        output_csv_path=args.output,
        limit=args.limit,
        request_delay_seconds=args.delay,
    )
    print(f"Wrote {count} U23 players to {args.output}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mws-monitor")
    sub = parser.add_subparsers(required=True)

    init = sub.add_parser("init-db")
    init.set_defaults(func=cmd_init_db)

    imp = sub.add_parser("import-watchlist")
    imp.add_argument("csv_path")
    imp.add_argument("--name")
    imp.set_defaults(func=cmd_import_watchlist)

    crawl = sub.add_parser("crawl-now")
    crawl.set_defaults(func=cmd_crawl_now)

    monitor = sub.add_parser("monitor-live")
    monitor.set_defaults(func=cmd_monitor_live)

    backfill = sub.add_parser("backfill-finished")
    backfill.set_defaults(func=cmd_backfill_finished)

    export = sub.add_parser("export-results")
    export.add_argument("output_path")
    export.set_defaults(func=cmd_export_results)

    review = sub.add_parser("review-matches")
    review.set_defaults(func=cmd_review_matches)

    bargains = sub.add_parser("show-bargains")
    bargains.add_argument("--min-score", type=int, default=50)
    bargains.add_argument("--limit", type=int, default=25)
    bargains.set_defaults(func=cmd_show_bargains)

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=cmd_serve)

    ep = sub.add_parser("event-pricing", help="kNN fair prices for an MWS event vs player_pricing_model workbook")
    ep.add_argument("--event-slug", required=True, help="Event URL slug, e.g. 22-04-2026-sprint-auctions-day-3-uk-special-app-exclusive")
    ep.add_argument(
        "--workbook",
        default="player_pricing_model_ranked.xlsx",
        help="Workbook with sheet 'Ranked All 200' used as comp table",
    )
    ep.add_argument(
        "--tm-csv",
        help="Optional CSV: name,market_value_eur[,mws_last_price_eur,mws_slug] (UTF-8). mws_last overrides live bid as comp input.",
    )
    ep.add_argument("--output", required=True, help="Output CSV path")
    ep.add_argument("--k-neighbors", type=int, default=7, dest="k_neighbors")
    ep.set_defaults(func=cmd_event_pricing)

    romanian = sub.add_parser("romanian-auctions", help="Compare a Romanian player list with current MWS live bidding shirts")
    romanian.add_argument("--players", default="data/romanian_players.csv", help="CSV/XLSX player list")
    romanian.add_argument("--output-dir", default="outputs", help="Directory for latest.csv/latest.json/latest.md")
    romanian.set_defaults(func=cmd_romanian_auctions)

    u23 = sub.add_parser("u23-auctions", help="Compare the Top 200 U23 list with current MWS live bidding shirts")
    u23.add_argument("--players", default="data/top_200_u23_players.csv", help="CSV/XLSX player list")
    u23.add_argument("--output-dir", default="outputs/u23", help="Directory for latest.csv/latest.json/latest.md")
    u23.set_defaults(func=cmd_u23_auctions)

    update_ro = sub.add_parser("update-romanian-players", help="Refresh data/romanian_players.csv from Transfermarkt source pages")
    update_ro.add_argument("--source", default="data/romanian_players.csv", help="Existing CSV used to discover Transfermarkt source pages")
    update_ro.add_argument("--output", default="data/romanian_players.csv", help="CSV file to write")
    update_ro.add_argument("--delay", type=float, default=1.0, help="Delay between Transfermarkt page requests")
    update_ro.set_defaults(func=cmd_update_romanian_players)

    update_u23 = sub.add_parser("update-u23-players", help="Refresh data/top_200_u23_players.csv from Transfermarkt")
    update_u23.add_argument(
        "--source-url",
        default=(
            "https://www.transfermarkt.com/spieler-statistik/wertvollstespieler/marktwertetop/plus/0/galerie/0"
            "?ausrichtung=alle&spielerposition_id=alle&altersklasse=u23&jahrgang=0&land_id=0&kontinent_id=0"
            "&jahr=2025&yt0=show&page=1"
        ),
        help="Transfermarkt top players URL",
    )
    update_u23.add_argument("--output", default="data/top_200_u23_players.csv", help="CSV file to write")
    update_u23.add_argument("--limit", type=int, default=200, help="Number of players to keep")
    update_u23.add_argument("--delay", type=float, default=1.0, help="Delay between Transfermarkt page requests")
    update_u23.set_defaults(func=cmd_update_u23_players)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
