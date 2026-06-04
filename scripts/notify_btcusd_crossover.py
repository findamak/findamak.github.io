#!/usr/bin/env python3
"""Email an alert when BTC/USD gets a new latest moving-average crossover.

State is stored outside the repo so a failed email can be retried on the next cron
run. On first run, the script records the current latest crossover without
sending an old historical alert.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_ACCOUNT = "mollylabradorbot@gmail.com"
DEFAULT_RECIPIENT = "findamak@gmail.com"
PAGE_URL = "https://findamak.github.io/btc.html"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def latest_cross(data: dict[str, Any]) -> dict[str, Any] | None:
    crosses = data.get("crosses") or []
    if not crosses:
        return None
    return max(crosses, key=lambda cross: cross["date"])


def latest_close(data: dict[str, Any]) -> dict[str, Any]:
    latest = data.get("latest")
    if isinstance(latest, dict) and latest.get("date"):
        return latest
    series = data.get("series") or []
    if not series:
        raise ValueError("current JSON has no latest/series data")
    return series[-1]


def money(value: float) -> str:
    return f"${value:,.2f}"


def state_payload(cross: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": cross["date"],
        "direction": cross["direction"],
        "close": cross["close"],
        "ema20": cross["ema20"],
        "sma200": cross["sma200"],
    }


def build_email(current: dict[str, Any], cross: dict[str, Any]) -> tuple[str, str]:
    symbol = current.get("symbol", "BTC/USD")
    source = current.get("source", "Bitstamp")
    direction = cross["direction"]
    latest = latest_close(current)
    trend_word = "Bearish" if direction == "bearish" else "Bullish"
    action = "sell / move to cash" if direction == "bearish" else "buy / move back into BTC"

    subject = f"{trend_word} BTC/USD MA crossover detected on {cross['date']}"
    body = f"""{trend_word} {symbol} 20-day EMA / 200-day SMA crossover detected.

Signal date: {cross['date']}
Direction: {direction}
Close: {money(float(cross['close']))}
20d EMA: {money(float(cross['ema20']))}
200d SMA: {money(float(cross['sma200']))}
Strategy action: {action}

Latest data point: {latest['date']} close {money(float(latest['close']))}
Data source: {source} daily OHLC
Chart: {PAGE_URL}

Assumptions: crossover signals are based on daily closes. This alert is informational only, not financial advice.
"""
    return subject, body


def send_email(subject: str, body: str) -> None:
    account = os.environ.get("BTC_EMA_EMAIL_ACCOUNT", DEFAULT_ACCOUNT)
    recipient = os.environ.get("BTC_EMA_EMAIL_RECIPIENT", DEFAULT_RECIPIENT)
    gog = os.environ.get("GOG_BIN", "gog")

    subprocess.run(
        [
            gog,
            "--account",
            account,
            "gmail",
            "send",
            "--to",
            recipient,
            "--subject",
            subject,
            "--body-file",
            "-",
        ],
        input=body,
        text=True,
        check=True,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: notify_btcusd_crossover.py CURRENT_JSON STATE_JSON", file=sys.stderr)
        return 2

    current_path = Path(argv[1])
    state_path = Path(argv[2])
    current = load_json(current_path)
    current_cross = latest_cross(current)

    if current_cross is None:
        print("current JSON has no moving-average crosses; not sending crossover alert")
        return 0

    if not state_path.exists():
        write_json(state_path, state_payload(current_cross))
        print(f"initialized BTC/USD moving-average crossover notification state at {current_cross['date']} {current_cross['direction']}; no historical alert sent")
        return 0

    notified_cross = load_json(state_path)
    notified_date = notified_cross.get("date", "")

    if current_cross["date"] <= notified_date:
        print(f"no new BTC/USD moving-average crossover; latest notified remains {notified_date}")
        return 0

    subject, body = build_email(current, current_cross)
    send_email(subject, body)
    write_json(state_path, state_payload(current_cross))
    print(f"sent BTC/USD moving-average crossover email for {current_cross['date']} {current_cross['direction']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
