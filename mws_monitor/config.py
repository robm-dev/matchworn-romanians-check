from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    mws_base_url: str
    mws_web_base_url: str
    mws_platform_key: str
    currency: str
    database_url: str
    cache_dir: Path
    request_timeout_seconds: int
    max_concurrency: int
    request_delay_seconds: float
    crawl_interval_minutes: int
    finished_refresh_days: int
    alert_thresholds: dict[str, Any]
    notifications: dict[str, Any]


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_settings(path: str | Path = ROOT / "config" / "config.yaml") -> Settings:
    data = load_yaml(path)
    cache_dir = Path(data.get("cache_dir", "data/cache"))
    if not cache_dir.is_absolute():
        cache_dir = ROOT / cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    database_url = data.get("database_url", "sqlite:///data/mws_value_monitor.db")
    if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite:////"):
        db_path = ROOT / database_url.replace("sqlite:///", "", 1)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{db_path}"
    return Settings(
        mws_base_url=data.get("mws_base_url", "https://api.mws.com/catalog").rstrip("/"),
        mws_web_base_url=data.get("mws_web_base_url", "https://mws.com/us/product").rstrip("/"),
        mws_platform_key=data.get("mws_platform_key", "matchwornshirt"),
        currency=data.get("currency", "EUR"),
        database_url=database_url,
        cache_dir=cache_dir,
        request_timeout_seconds=int(data.get("request_timeout_seconds", 15)),
        max_concurrency=int(data.get("max_concurrency", 2)),
        request_delay_seconds=float(data.get("request_delay_seconds", 0.25)),
        crawl_interval_minutes=int(data.get("crawl_interval_minutes", 60)),
        finished_refresh_days=int(data.get("finished_refresh_days", 30)),
        alert_thresholds=data.get("alert_thresholds", {}),
        notifications=data.get("notifications", {}),
    )


def load_aliases(path: str | Path = ROOT / "config" / "player_aliases.yaml") -> dict[str, dict[str, str]]:
    data = load_yaml(path)
    aliases: dict[str, dict[str, str]] = {}
    for row in data.get("aliases", []):
        name = row.get("input_name")
        if name:
            aliases[name] = row
    return aliases
