#!/usr/bin/env python3
"""Generate BTCI ETF vs BTC/USD performance data for btci.html.

Downloads BTCI ETF daily closes from Yahoo Finance and BTC/USD daily closes
from Bitstamp, aligns on common dates, normalizes both instruments to their
first shared trading date, and writes a static JSON payload for GitHub Pages.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

BTCI_SYMBOL = "BTCI"
BTCI_NAME = "NEOS Bitcoin High Income ETF"
BTCI_SOURCE = "Yahoo Finance"
BTCUSD_SYMBOL = "BTC/USD"
BTCUSD_SOURCE = "Bitstamp"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "btci.json"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
BITSTAMP_OHLC_URL = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
DAY_SECONDS = 86_400
API_LIMIT = 1000
START_DATE = date(2024, 1, 1)
START_TS = int(datetime(START_DATE.year, START_DATE.month, START_DATE.day, tzinfo=timezone.utc).timestamp())


def _round(value: Any, digits: int = 2) -> float | None:
    """Round numeric values for compact JSON; return None for NaN/None."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def download_btci_history() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Download all available daily BTCI ETF closes from Yahoo Finance."""
    end_ts = int(datetime.now(timezone.utc).timestamp())
    params = urlencode(
        {
            "period1": START_TS,
            "period2": end_ts,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    payload = _get_json(f"{YAHOO_CHART_URL.format(symbol=BTCI_SYMBOL)}?{params}")
    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(f"Yahoo Finance error for {BTCI_SYMBOL}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"No Yahoo Finance chart data returned for {BTCI_SYMBOL}")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjclose = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or []
    close = quote.get("close") or []
    values = adjclose if len(adjclose) == len(timestamps) else close

    rows: list[dict[str, Any]] = []
    for ts, value in zip(timestamps, values):
        if value is None:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(int(ts), tz=timezone.utc).date(),
                "btci_close": float(value),
            }
        )

    if not rows:
        raise RuntimeError(f"No usable close prices returned for {BTCI_SYMBOL}")

    df = pd.DataFrame(rows).dropna().drop_duplicates(subset=["date"]).sort_values("date")
    return df, result.get("meta", {})


def _fetch_bitstamp_page(start_ts: int) -> list[dict[str, str]]:
    params = urlencode({"step": DAY_SECONDS, "limit": API_LIMIT, "start": start_ts})
    payload = _get_json(f"{BITSTAMP_OHLC_URL}?{params}")
    return payload.get("data", {}).get("ohlc", [])


def download_btcusd_history() -> pd.DataFrame:
    """Download daily BTC/USD closes from Bitstamp from START_DATE onward."""
    end_ts = int(datetime.now(timezone.utc).timestamp())
    start_ts = START_TS
    rows: list[dict[str, str]] = []
    seen_timestamps: set[int] = set()

    while start_ts <= end_ts:
        page = _fetch_bitstamp_page(start_ts)
        if not page:
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
    df["btcusd_close"] = pd.to_numeric(df["close"], errors="raise")
    df["date"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.date
    return df[["date", "btcusd_close"]].dropna().drop_duplicates(subset=["date"]).sort_values("date")


def compute_payload(btci_df: pd.DataFrame, btcusd_df: pd.DataFrame, yahoo_meta: dict[str, Any]) -> dict[str, Any]:
    """Align BTCI and BTC/USD histories and compute normalized performance."""
    merged = btci_df.merge(btcusd_df, on="date", how="inner").sort_values("date")
    if merged.empty:
        raise RuntimeError("No overlapping BTCI and BTC/USD dates after alignment")

    first = merged.iloc[0]
    btci_base = float(first["btci_close"])
    btcusd_base = float(first["btcusd_close"])
    if btci_base <= 0 or btcusd_base <= 0:
        raise RuntimeError("Invalid base close price for performance calculation")

    merged["btci_return_pct"] = (merged["btci_close"] / btci_base - 1.0) * 100.0
    merged["btcusd_return_pct"] = (merged["btcusd_close"] / btcusd_base - 1.0) * 100.0
    merged["relative_return_pct"] = merged["btci_return_pct"] - merged["btcusd_return_pct"]
    last = merged.iloc[-1]

    latest_btci_return = float(last["btci_return_pct"])
    latest_btcusd_return = float(last["btcusd_return_pct"])
    latest_relative = float(last["relative_return_pct"])

    series = [
        {
            "date": row["date"].isoformat(),
            "btci_close": _round(row["btci_close"], 4),
            "btcusd_close": _round(row["btcusd_close"], 2),
            "btci_return_pct": _round(row["btci_return_pct"], 2),
            "btcusd_return_pct": _round(row["btcusd_return_pct"], 2),
            "relative_return_pct": _round(row["relative_return_pct"], 2),
        }
        for _, row in merged.iterrows()
    ]

    return {
        "symbol": BTCI_SYMBOL,
        "name": yahoo_meta.get("longName") or yahoo_meta.get("shortName") or BTCI_NAME,
        "currency": yahoo_meta.get("currency") or "USD",
        "exchange": yahoo_meta.get("exchangeName") or yahoo_meta.get("fullExchangeName") or "Yahoo Finance",
        "source": {"btci": BTCI_SOURCE, "btcusd": BTCUSD_SOURCE},
        "comparison_symbol": BTCUSD_SYMBOL,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "base_date": first["date"].isoformat(),
        "latest": {
            "date": last["date"].isoformat(),
            "btci_close": _round(last["btci_close"], 4),
            "btcusd_close": _round(last["btcusd_close"], 2),
            "btci_return_pct": _round(latest_btci_return, 2),
            "btcusd_return_pct": _round(latest_btcusd_return, 2),
            "relative_return_pct": _round(latest_relative, 2),
            "leader": BTCI_SYMBOL if latest_btci_return >= latest_btcusd_return else BTCUSD_SYMBOL,
        },
        "series": series,
    }


def main() -> None:
    btci_df, yahoo_meta = download_btci_history()
    btcusd_df = download_btcusd_history()
    payload = compute_payload(btci_df, btcusd_df, yahoo_meta)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        f"Wrote {OUTPUT_PATH} with {len(payload['series'])} aligned daily bars "
        f"from {payload['series'][0]['date']} to {payload['series'][-1]['date']}."
    )


if __name__ == "__main__":
    main()
