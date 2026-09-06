from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import ROOT, load_settings
from .db import SessionLocal, init_db
from .importer import import_watchlist
from .models import Alert, MwsProduct, Player, PlayerAlias, ReviewQueue
from .romanian_auctions import run_romanian_auctions
from .service import MonitorService, export_results


init_db()
app = FastAPI(title="MWS Value Monitor")
templates = Jinja2Templates(directory=str(ROOT / "mws_monitor" / "templates"))
app.mount("/static", StaticFiles(directory=str(ROOT / "mws_monitor" / "static")), name="static")
ROMANIAN_PLAYERS_PATH = ROOT / "data" / "romanian_players.csv"
ROMANIAN_OUTPUT_DIR = ROOT / "outputs"
ROMANIAN_OUTPUT_PATH = ROMANIAN_OUTPUT_DIR / "latest.json"
U23_PLAYERS_PATH = ROOT / "data" / "top_200_u23_players.csv"
U23_OUTPUT_DIR = ROOT / "outputs" / "u23"
U23_OUTPUT_PATH = U23_OUTPUT_DIR / "latest.json"
_romanian_recheck_jobs: dict[str, dict] = {}
_romanian_recheck_lock = Lock()
_u23_recheck_jobs: dict[str, dict] = {}
_u23_recheck_lock = Lock()


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def aware_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _load_auction_report(path: Path) -> dict:
    if not path.exists():
        return {"checked_at": None, "match_count": 0, "matches": []}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"checked_at": None, "match_count": 0, "matches": []}
    return {
        "checked_at": data.get("checked_at"),
        "match_count": data.get("match_count") or len(data.get("matches") or []),
        "matches": data.get("matches") or [],
    }


def load_romanian_auction_report() -> dict:
    return _load_auction_report(ROMANIAN_OUTPUT_PATH)


def load_u23_auction_report() -> dict:
    return _load_auction_report(U23_OUTPUT_PATH)


def _set_romanian_job(job_id: str, *, percent: int, status: str, message: str, error: str | None = None) -> None:
    with _romanian_recheck_lock:
        job = _romanian_recheck_jobs.setdefault(job_id, {})
        job.update({"percent": percent, "status": status, "message": message, "error": error})


def _run_romanian_recheck_job(job_id: str) -> None:
    try:
        _set_romanian_job(job_id, percent=15, status="running", message="Loading Romanian player list")
        settings = load_settings()
        _set_romanian_job(job_id, percent=35, status="running", message="Fetching live MatchWornShirt auctions")
        run_romanian_auctions(ROMANIAN_PLAYERS_PATH, ROMANIAN_OUTPUT_DIR, settings)
        _set_romanian_job(job_id, percent=90, status="running", message="Writing latest results")
        _set_romanian_job(job_id, percent=100, status="complete", message="Recheck complete")
    except Exception as exc:
        _set_romanian_job(job_id, percent=100, status="failed", message="Recheck failed", error=str(exc))


def _set_u23_job(job_id: str, *, percent: int, status: str, message: str, error: str | None = None) -> None:
    with _u23_recheck_lock:
        job = _u23_recheck_jobs.setdefault(job_id, {})
        job.update({"percent": percent, "status": status, "message": message, "error": error})


def _run_u23_recheck_job(job_id: str) -> None:
    try:
        _set_u23_job(job_id, percent=15, status="running", message="Loading Top 200 U23 player list")
        settings = load_settings()
        _set_u23_job(job_id, percent=35, status="running", message="Fetching live MatchWornShirt auctions")
        run_romanian_auctions(U23_PLAYERS_PATH, U23_OUTPUT_DIR, settings)
        _set_u23_job(job_id, percent=90, status="running", message="Writing latest results")
        _set_u23_job(job_id, percent=100, status="complete", message="Recheck complete")
    except Exception as exc:
        _set_u23_job(job_id, percent=100, status="failed", message="Recheck failed", error=str(exc))


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)):
    min_score = int(request.query_params.get("min_score", 40))
    view = request.query_params.get("view", "live_bargains")
    now = datetime.now(timezone.utc)
    rows = session.execute(
        select(Player, MwsProduct)
        .join(MwsProduct, MwsProduct.player_id == Player.id)
        .order_by(MwsProduct.bargain_score.desc(), MwsProduct.latest_price_eur.asc())
    ).all()
    if view == "live":
        products = [(player, product) for player, product in rows if product.status == "live" and product.bargain_score >= min_score]
    elif view == "closing":
        products = [
            (player, product)
            for player, product in rows
            if product.status == "live" and aware_dt(product.end_date) and now <= aware_dt(product.end_date) <= now + timedelta(hours=24)
        ]
    elif view == "new":
        products = sorted(rows, key=lambda row: row[1].fetched_at, reverse=True)[:100]
    elif view == "finished":
        products = [
            (player, product)
            for player, product in rows
            if product.status == "finished" and product.bargain_score >= min_score
        ]
    else:
        products = [(player, product) for player, product in rows if product.bargain_score >= min_score]
    products = products[:100]
    review = session.scalars(select(ReviewQueue).where(ReviewQueue.status == "open").order_by(ReviewQueue.created_at.desc())).all()
    alerts = session.scalars(select(Alert).order_by(Alert.created_at.desc()).limit(20)).all()
    players = session.scalars(select(Player).order_by(Player.market_value_eur.desc()).limit(200)).all()
    aliases = session.scalars(select(PlayerAlias).order_by(PlayerAlias.input_name.asc())).all()
    romanian_report = load_romanian_auction_report()
    u23_report = load_u23_auction_report()
    alias_player = request.query_params.get("alias_player", "")
    alias_athlete = request.query_params.get("alias_athlete", "")
    alias_category = request.query_params.get("alias_category", "")
    counts = {
        "players": session.scalar(select(func.count()).select_from(Player)) or 0,
        "products": session.scalar(select(func.count()).select_from(MwsProduct)) or 0,
        "live": session.scalar(select(func.count()).select_from(MwsProduct).where(MwsProduct.status == "live")) or 0,
        "review": len(review),
    }
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "products": products,
            "review": review,
            "alerts": alerts,
            "counts": counts,
            "min_score": min_score,
            "view": view,
            "players": players,
            "aliases": aliases,
            "romanian_report": romanian_report,
            "u23_report": u23_report,
            "alias_player": alias_player,
            "alias_athlete": alias_athlete,
            "alias_category": alias_category,
        },
    )


@app.get("/import-path")
def import_from_path(path: str, name: str = "watchlist", session: Session = Depends(get_session)):
    import_watchlist(session, Path(path), name)
    session.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/crawl")
def crawl(session: Session = Depends(get_session)):
    settings = load_settings()
    service = MonitorService(session, settings)
    try:
        service.crawl_all()
        session.commit()
    finally:
        service.close()
    return RedirectResponse("/", status_code=303)


@app.get("/crawl")
def crawl_get_hint():
    return RedirectResponse("/", status_code=303)


@app.post("/romanian-auctions/recheck")
def recheck_romanian_auctions():
    job_id = uuid4().hex
    _set_romanian_job(job_id, percent=0, status="queued", message="Queued")
    Thread(target=lambda: _run_romanian_recheck_job(job_id), daemon=True).start()
    return JSONResponse({"job_id": job_id, "status_url": f"/romanian-auctions/recheck/status/{job_id}"})


@app.get("/romanian-auctions/recheck/status/{job_id}")
def romanian_auction_recheck_status(job_id: str):
    with _romanian_recheck_lock:
        job = _romanian_recheck_jobs.get(job_id)
    if not job:
        return JSONResponse({"status": "missing", "percent": 100, "message": "Job not found"}, status_code=404)
    return job


@app.post("/u23-auctions/recheck")
def recheck_u23_auctions():
    job_id = uuid4().hex
    _set_u23_job(job_id, percent=0, status="queued", message="Queued")
    Thread(target=lambda: _run_u23_recheck_job(job_id), daemon=True).start()
    return JSONResponse({"job_id": job_id, "status_url": f"/u23-auctions/recheck/status/{job_id}"})


@app.get("/u23-auctions/recheck/status/{job_id}")
def u23_auction_recheck_status(job_id: str):
    with _u23_recheck_lock:
        job = _u23_recheck_jobs.get(job_id)
    if not job:
        return JSONResponse({"status": "missing", "percent": 100, "message": "Job not found"}, status_code=404)
    return job


@app.get("/export")
def export_current_results(session: Session = Depends(get_session)):
    path = ROOT / "exports" / "dashboard_results.csv"
    export_results(session, path)
    return FileResponse(path, media_type="text/csv", filename="mws_value_monitor_results.csv")


@app.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(product_id: int, request: Request, session: Session = Depends(get_session)):
    row = session.execute(
        select(Player, MwsProduct).join(MwsProduct, MwsProduct.player_id == Player.id).where(MwsProduct.id == product_id)
    ).first()
    if not row:
        return templates.TemplateResponse("not_found.html", {"request": request, "message": "Product not found"}, status_code=404)
    player, product = row
    related_products = session.scalars(
        select(MwsProduct).where(MwsProduct.player_id == player.id).order_by(MwsProduct.end_date.desc().nullslast()).limit(25)
    ).all()
    return templates.TemplateResponse(
        "product.html",
        {"request": request, "player": player, "product": product, "related_products": related_products},
    )


@app.get("/product/{product_id}/ignore")
def ignore_product(product_id: int, session: Session = Depends(get_session)):
    product = session.get(MwsProduct, product_id)
    if product:
        product.bargain_score = 0
        product.bargain_reason = "ignored by user"
        session.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/product/{product_id}/alias")
def alias_from_product(product_id: int, session: Session = Depends(get_session)):
    row = session.execute(
        select(Player, MwsProduct).join(MwsProduct, MwsProduct.player_id == Player.id).where(MwsProduct.id == product_id)
    ).first()
    if not row:
        return RedirectResponse("/?view=aliases", status_code=303)
    player, product = row
    query = (
        f"/?view=aliases&alias_player={player.input_name}"
        f"&alias_athlete={product.mws_athlete_name or ''}"
    )
    return RedirectResponse(query, status_code=303)


@app.get("/alias-save")
def save_alias(
    input_name: str,
    preferred_mws_athlete_name: str = "",
    preferred_mws_category_id: str = "",
    notes: str = "",
    session: Session = Depends(get_session),
):
    alias = session.scalar(select(PlayerAlias).where(PlayerAlias.input_name == input_name))
    if not alias:
        alias = PlayerAlias(input_name=input_name)
        session.add(alias)
    alias.preferred_mws_athlete_name = preferred_mws_athlete_name or None
    alias.preferred_mws_category_id = preferred_mws_category_id or None
    alias.notes = notes or None
    session.commit()
    return RedirectResponse("/?view=aliases", status_code=303)


@app.post("/review/{review_id}/close")
def close_review(review_id: int, session: Session = Depends(get_session)):
    item = session.get(ReviewQueue, review_id)
    if item:
        item.status = "closed"
        session.commit()
    return RedirectResponse("/?view=review", status_code=303)
