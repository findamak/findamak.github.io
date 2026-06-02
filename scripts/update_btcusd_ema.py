#!/usr/bin/env python3
"""Generate BTC-USD 20-day/200-day EMA data for btc.html.

Downloads daily BTC-USD candles from Yahoo Finance, computes the 20d and
200d exponential moving averages, detects historical crosses, and writes a
static JSON payload for GitHub Pages.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

TICKER = "BTC-USD"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "btcusd.json"


def _round(value: Any, digits: int = 2) -> float | None:
    """Round numeric values for compact JSON; return None for NaN/None."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def download_history() -> pd.DataFrame:
    """Download max available BTC-USD daily history from Yahoo Finance."""
    df = yf.download(
        TICKER,
        period="max",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df.empty:
        raise RuntimeError(f"No data returned for {TICKER}")

    # yfinance may return a MultiIndex depending on version/options.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    df = df.reset_index()
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    df = df.rename(columns={"Date": "date", "Close": "close"})
    df = df[["date", "close"]].dropna().sort_values("date")

    return df


def compute_payload(df: pd.DataFrame) -> dict[str, Any]:
    """Compute EMA series and cross events, then return JSON payload."""
    df = df.copy()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
    df["diff"] = df["ema20"] - df["ema200"]

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
                "ema200": _round(row["ema200"]),
            }
        )

    series = [
        {
            "date": row["date"].isoformat(),
            "close": _round(row["close"]),
            "ema20": _round(row["ema20"]),
            "ema200": _round(row["ema200"]),
        }
        for _, row in df.iterrows()
    ]

    latest = df.iloc[-1]
    current_trend = "bullish" if latest["ema20"] >= latest["ema200"] else "bearish"

    return {
        "symbol": TICKER,
        "name": "Bitcoin / USD",
        "source": "Yahoo Finance",
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "latest": {
            "date": latest["date"].isoformat(),
            "close": _round(latest["close"]),
            "ema20": _round(latest["ema20"]),
            "ema200": _round(latest["ema200"]),
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
        f"and {len(payload['crosses'])} EMA crosses."
    )


if __name__ == "__main__":
    main()
