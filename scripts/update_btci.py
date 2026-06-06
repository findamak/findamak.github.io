#!/usr/bin/env python3
"""Generate BTCI/BITO ETF vs BTC/USD performance data for btci.html.

Downloads BTCI and BITO ETF daily closes/distributions from Yahoo Finance and
BTC/USD daily closes from Bitstamp, aligns on common dates, normalizes all
instruments to their first shared trading date, and writes a static JSON payload
for GitHub Pages.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

ETF_CONFIGS = {
    "btci": {
        "symbol": "BTCI",
        "name": "NEOS Bitcoin High Income ETF",
        "source": "Yahoo Finance",
    },
    "bito": {
        "symbol": "BITO",
        "name": "ProShares Bitcoin Strategy ETF",
        "source": "Yahoo Finance",
    },
}
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


def download_yahoo_history(symbol: str, prefix: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Download all available daily closes and dividend events for a Yahoo Finance symbol."""
    end_ts = int(datetime.now(timezone.utc).timestamp())
    params = urlencode(
        {
            "period1": START_TS,
            "period2": end_ts,
            "interval": "1d",
            "events": "history,div",
            "includeAdjustedClose": "true",
        }
    )
    payload = _get_json(f"{YAHOO_CHART_URL.format(symbol=symbol)}?{params}")
    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(f"Yahoo Finance error for {symbol}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise RuntimeError(f"No Yahoo Finance chart data returned for {symbol}")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adjclose = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or []
    close = quote.get("close") or []
    values = adjclose if len(adjclose) == len(timestamps) else close

    rows: list[dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        value = values[i] if i < len(values) else None
        raw_close = close[i] if i < len(close) else None
        if value is None:
            continue
        row = {
            "date": datetime.fromtimestamp(int(ts), tz=timezone.utc).date(),
            f"{prefix}_close": float(value),
        }
        if raw_close is not None:
            row[f"{prefix}_raw_close"] = float(raw_close)
        rows.append(row)

    if not rows:
        raise RuntimeError(f"No usable close prices returned for {symbol}")

    df = pd.DataFrame(rows).dropna(subset=[f"{prefix}_close"]).drop_duplicates(subset=["date"]).sort_values("date")
    meta = dict(result.get("meta", {}))
    meta["events"] = result.get("events", {})
    return df, meta


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


def compute_distribution_rows(
    etf_df: pd.DataFrame,
    yahoo_meta: dict[str, Any],
    prefix: str,
    symbol: str,
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Compute the latest ETF distributions as annualized close-price yields."""
    dividends = (yahoo_meta.get("events") or {}).get("dividends") or {}
    if not dividends:
        return []

    close_lookup = {}
    for _, row in etf_df.iterrows():
        close = row.get(f"{prefix}_raw_close", row.get(f"{prefix}_close"))
        if close is not None and not pd.isna(close):
            close_lookup[row["date"]] = float(close)

    latest_date = max(close_lookup.keys()) if close_lookup else None
    rows = []
    for event in dividends.values():
        amount = event.get("amount")
        ts = event.get("date")
        if amount is None or ts is None:
            continue
        distribution_date = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
        if latest_date and distribution_date > latest_date:
            continue
        close = close_lookup.get(distribution_date)
        if close is None or close <= 0:
            continue
        annualized_distribution_pct = (float(amount) * 12.0 / close) * 100.0
        rows.append(
            {
                "etf": symbol,
                "date": distribution_date.isoformat(),
                "distribution": _round(amount, 4),
                "close": _round(close, 4),
                "annualized_distribution_pct": _round(annualized_distribution_pct, 2),
            }
        )

    return sorted(rows, key=lambda row: row["date"], reverse=True)[:limit]


def _display_name(prefix: str, meta: dict[str, Any]) -> str:
    config = ETF_CONFIGS[prefix]
    return meta.get("longName") or meta.get("shortName") or config["name"]


def compute_payload(
    etf_data: dict[str, tuple[pd.DataFrame, dict[str, Any]]],
    btcusd_df: pd.DataFrame,
) -> dict[str, Any]:
    """Align ETF and BTC/USD histories and compute normalized performance."""
    btci_df, btci_meta = etf_data["btci"]
    bito_df, bito_meta = etf_data["bito"]
    merged = btci_df.merge(bito_df, on="date", how="inner").merge(btcusd_df, on="date", how="inner").sort_values("date")
    if merged.empty:
        raise RuntimeError("No overlapping BTCI, BITO, and BTC/USD dates after alignment")

    first = merged.iloc[0]
    bases = {
        "btci": float(first["btci_close"]),
        "bito": float(first["bito_close"]),
        "btcusd": float(first["btcusd_close"]),
    }
    if any(base <= 0 for base in bases.values()):
        raise RuntimeError("Invalid base close price for performance calculation")

    for key in ("btci", "bito", "btcusd"):
        merged[f"{key}_return_pct"] = (merged[f"{key}_close"] / bases[key] - 1.0) * 100.0
    merged["btci_relative_return_pct"] = merged["btci_return_pct"] - merged["btcusd_return_pct"]
    merged["bito_relative_return_pct"] = merged["bito_return_pct"] - merged["btcusd_return_pct"]
    merged["btci_vs_bito_return_pct"] = merged["btci_return_pct"] - merged["bito_return_pct"]
    last = merged.iloc[-1]

    latest_returns = {
        "BTCI": float(last["btci_return_pct"]),
        "BITO": float(last["bito_return_pct"]),
        BTCUSD_SYMBOL: float(last["btcusd_return_pct"]),
    }
    leader = max(latest_returns, key=lambda key: latest_returns[key])
    runner_up = sorted(latest_returns.values(), reverse=True)[1]
    leader_margin = latest_returns[leader] - runner_up

    series = [
        {
            "date": row["date"].isoformat(),
            "btci_close": _round(row["btci_close"], 4),
            "bito_close": _round(row["bito_close"], 4),
            "btcusd_close": _round(row["btcusd_close"], 2),
            "btci_return_pct": _round(row["btci_return_pct"], 2),
            "bito_return_pct": _round(row["bito_return_pct"], 2),
            "btcusd_return_pct": _round(row["btcusd_return_pct"], 2),
            "relative_return_pct": _round(row["btci_relative_return_pct"], 2),
            "btci_relative_return_pct": _round(row["btci_relative_return_pct"], 2),
            "bito_relative_return_pct": _round(row["bito_relative_return_pct"], 2),
            "btci_vs_bito_return_pct": _round(row["btci_vs_bito_return_pct"], 2),
        }
        for _, row in merged.iterrows()
    ]

    distributions = sorted(
        compute_distribution_rows(btci_df, btci_meta, "btci", "BTCI")
        + compute_distribution_rows(bito_df, bito_meta, "bito", "BITO"),
        key=lambda row: (row["date"], row["etf"]),
        reverse=True,
    )

    return {
        "symbol": "BTCI",
        "symbols": ["BTCI", "BITO"],
        "name": _display_name("btci", btci_meta),
        "names": {
            "btci": _display_name("btci", btci_meta),
            "bito": _display_name("bito", bito_meta),
        },
        "currency": btci_meta.get("currency") or bito_meta.get("currency") or "USD",
        "exchange": btci_meta.get("exchangeName") or btci_meta.get("fullExchangeName") or "Yahoo Finance",
        "source": {"btci": "Yahoo Finance", "bito": "Yahoo Finance", "btcusd": BTCUSD_SOURCE},
        "comparison_symbol": BTCUSD_SYMBOL,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "base_date": first["date"].isoformat(),
        "latest": {
            "date": last["date"].isoformat(),
            "btci_close": _round(last["btci_close"], 4),
            "bito_close": _round(last["bito_close"], 4),
            "btcusd_close": _round(last["btcusd_close"], 2),
            "btci_return_pct": _round(last["btci_return_pct"], 2),
            "bito_return_pct": _round(last["bito_return_pct"], 2),
            "btcusd_return_pct": _round(last["btcusd_return_pct"], 2),
            "relative_return_pct": _round(last["btci_relative_return_pct"], 2),
            "btci_relative_return_pct": _round(last["btci_relative_return_pct"], 2),
            "bito_relative_return_pct": _round(last["bito_relative_return_pct"], 2),
            "btci_vs_bito_return_pct": _round(last["btci_vs_bito_return_pct"], 2),
            "leader": leader,
            "leader_margin_pct": _round(leader_margin, 2),
        },
        "distributions": distributions,
        "series": series,
    }


def main() -> None:
    etf_data = {
        prefix: download_yahoo_history(config["symbol"], prefix)
        for prefix, config in ETF_CONFIGS.items()
    }
    btcusd_df = download_btcusd_history()
    payload = compute_payload(etf_data, btcusd_df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(
        f"Wrote {OUTPUT_PATH} with {len(payload['series'])} aligned daily bars "
        f"from {payload['series'][0]['date']} to {payload['series'][-1]['date']}."
    )


if __name__ == "__main__":
    main()
