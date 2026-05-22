"""
alerts/discord.py — Discord webhook sender for Signal Brain alerts (Session 6).

All outbound calls are fire-and-forget: functions return True/False and
never raise exceptions so a failed alert never crashes the scheduler.

Requires:
    DISCORD_WEBHOOK_URL in .env or Codespaces secrets.

Returns:
    send_discord_alert, send_premarket_summary.
"""

from __future__ import annotations

import datetime
from typing import Any

import requests

import config
from journal.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT_SECONDS: int = 10


def send_discord_alert(message: str) -> bool:
    """
    Send message to the Discord webhook configured in DISCORD_WEBHOOK_URL.

    Args:
        message: Plain text or markdown message to post.

    Returns:
        True on HTTP 2xx, False on any error (missing URL, network, non-2xx).
        Never raises.
    """
    url = config.DISCORD_WEBHOOK_URL
    if not url:
        logger.warning("DISCORD_WEBHOOK_URL not set — alert not sent")
        return False
    try:
        resp = requests.post(
            url,
            json={"content": message},
            timeout=_TIMEOUT_SECONDS,
        )
        if resp.status_code in (200, 204):
            logger.info("Discord alert sent (%d chars)", len(message))
            return True
        logger.warning(
            "Discord webhook returned %d: %s", resp.status_code, resp.text[:200]
        )
        return False
    except Exception as exc:
        logger.error("send_discord_alert failed: %s", exc)
        return False


def send_premarket_summary(candidates: list[dict[str, Any]]) -> bool:
    """
    Send the 9:00 AM pre-market watchlist summary to Discord.

    Format:
        📋 PRE-MARKET WATCHLIST — YYYY-MM-DD
        TICKER: +X.X% gap | $X.XX pre-market high
        ...
        Watching N tickers at open.

    Args:
        candidates: List of gap dicts from scan_premarket_gaps() — already
                    sorted descending by gap_pct.

    Returns:
        True on success, False on any error. Never raises.
    """
    today = datetime.date.today().isoformat()
    lines = [f"📋 PRE-MARKET WATCHLIST — {today}", ""]
    if candidates:
        for c in candidates:
            lines.append(
                f"**{c['ticker']}**: +{c['gap_pct']:.1f}% gap"
                f" | ${c['premarket_high']:.2f} pre-market high"
            )
        lines.append("")
        lines.append(f"Watching **{len(candidates)}** tickers at open.")
    else:
        lines.append("No meaningful gaps today. Sitting on hands. 💤")
    return send_discord_alert("\n".join(lines))
