from __future__ import annotations

import httpx


class Notifier:
    def __init__(self, config: dict) -> None:
        self.config = config

    def send(self, message: str) -> None:
        webhook = self.config.get("discord_webhook_url")
        if webhook:
            httpx.post(webhook, json={"content": message}, timeout=10)
        # Dashboard alerts are stored in the database by the service layer.
