#!/usr/bin/env python3
"""Generate BTC/USD 20-day EMA / 200-day SMA data for btc.html.

Downloads daily BTC/USD candles from Bitstamp, computes the 20d exponential
moving average and 200d simple moving average, detects historical crosses,
and writes a static JSON payload for GitHub Pages.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

SYMBOL = "BTC/USD"
SOURCE = "Bitstamp"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "btcusd.json"
BITSTAMP_OHLC_URL = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
DAY_SECONDS = 86_400
API_LIMIT = 1000
START_TS = int(datetime(2012, 1, 1, tzinfo=timezone.utc).timestamp())


def _round(value: Any, digits: int = 2) -> float | None:
    """Round numeric values for compact JSON; return None for NaN/None."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _fetch_bitstamp_page(start_ts: int) -> list[dict[str, str]]:
    """Fetch one page of daily Bitstamp BTC/USD OHLC data."""
    params = urlencode(
        {
            "step": DAY_SECONDS,
            "limit": API_LIMIT,
            "start": start_ts,
        }
    )
    with urlopen(f"{BITSTAMP_OHLC_URL}?{params}", timeout=30) as response:
        payload = json.load(response)

    return payload.get("data", {}).get("ohlc", [])


def download_history() -> pd.DataFrame:
    """Download all available daily BTC/USD history from Bitstamp."""
    end_ts = int(datetime.now(timezone.utc).timestamp())
    start_ts = START_TS
    rows: list[dict[str, str]] = []
    seen_timestamps: set[int] = set()

    while start_ts <= end_ts:
        page = _fetch_bitstamp_page(start_ts)
        if not page:
            # Move forward one page in case the requested early range has no rows.
            start_ts += API_LIMIT * DAY_SECONDS
            continue

        for row in page:
            ts = int(row["timestamp"])
            if ts not in seen_timestamps:
                rows.append(row)
                seen_timestamps.add(ts)

        last_ts = int(page[-1]["timestamp"])
        next_start = last_ts + DAY_SECONDS
        if next_start <= start_ts:
            break
        start_ts = next_start

        if len(page) < API_LIMIT:
            break

    if not rows:
        raise RuntimeError("No Bitstamp BTC/USD OHLC data returned")

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="raise")
    df["close"] = pd.to_numeric(df["close"], errors="raise")
    df["date"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.date
    df = df[["date", "close"]].dropna().drop_duplicates(subset=["date"]).sort_values("date")

    return df


def compute_payload(df: pd.DataFrame) -> dict[str, Any]:
    """Compute moving-average series and cross events, then return JSON payload."""
    df = df.copy()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["sma200"] = df["close"].rolling(window=200, min_periods=200).mean()
    df["diff"] = df["ema20"] - df["sma200"]

    # Ignore early warm-up values before a full 200 daily closes are available.
    valid = df.index >= 199
    bullish = valid & (df["diff"] > 0) & (df["diff"].shift(1) <= 0)
    bearish = valid & (df["diff"] < 0) & (df["diff"].shift(1) >= 0)

    crosses: list[dict[str, Any]] = []
    for idx, row in df[bullish | bearish].iterrows():
        crosses.append(
            {
                "date": row["date"].isoformat(),
                "direction": "bullish" if bullish.loc[idx] else "bearish",
                "close": _round(row["close"]),
                "ema20": _round(row["ema20"]),
                "sma200": _round(row["sma200"]),
            }
        )

    series = [
        {
            "date": row["date"].isoformat(),
            "close": _round(row["close"]),
            "ema20": _round(row["ema20"]),
            "sma200": _round(row["sma200"]),
        }
        for _, row in df.iterrows()
    ]

    latest = df.iloc[-1]
    current_trend = "bullish" if latest["ema20"] >= latest["sma200"] else "bearish"

    return {
        "symbol": SYMBOL,
        "name": "Bitcoin / USD",
        "source": SOURCE,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "latest": {
            "date": latest["date"].isoformat(),
            "close": _round(latest["close"]),
            "ema20": _round(latest["ema20"]),
            "sma200": _round(latest["sma200"]),
            "trend": current_trend,
        },
        "series": series,
        "crosses": crosses,
    }


def main() -> None:
    df = download_history()
    payload = compute_payload(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        f"Wrote {OUTPUT_PATH} with {len(payload['series'])} daily bars "
        f"from {payload['series'][0]['date']} to {payload['series'][-1]['date']} "
        f"and {len(payload['crosses'])} moving-average crosses."
    )


if __name__ == "__main__":
    main()
