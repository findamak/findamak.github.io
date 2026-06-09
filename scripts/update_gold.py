#!/usr/bin/env python3
"""Generate gold ETF vs gold futures performance data for gold.html.

Downloads KGLD, IGLD, and IAUI ETF daily closes/distributions plus COMEX gold
futures (GC=F) daily closes from Yahoo Finance, aligns on common trading dates,
normalizes all instruments to their first shared date, and writes a static JSON
payload for GitHub Pages.
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
    "kgld": {"symbol": "KGLD", "name": "Kurv Gold Enhanced Income ETF", "source": "Yahoo Finance"},
    "igld": {"symbol": "IGLD", "name": "FT Vest Gold Strategy Target Income ETF", "source": "Yahoo Finance"},
    "iaui": {"symbol": "IAUI", "name": "NEOS Gold High Income ETF", "source": "Yahoo Finance"},
}
BENCHMARK_PREFIX = "gold"
BENCHMARK_SYMBOL = "GC=F"
BENCHMARK_NAME = "COMEX Gold Futures"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "gold.json"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
START_DATE = date(2024, 1, 1)
START_TS = int(datetime(START_DATE.year, START_DATE.month, START_DATE.day, tzinfo=timezone.utc).timestamp())


def _round(value: Any, digits: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def download_yahoo_history(symbol: str, prefix: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Download daily closes and dividend events for a Yahoo Finance symbol."""
    end_ts = int(datetime.now(timezone.utc).timestamp())
    params = urlencode({
        "period1": START_TS,
        "period2": end_ts,
        "interval": "1d",
        "events": "history,div",
        "includeAdjustedClose": "true",
    })
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


def compute_distribution_rows(etf_df: pd.DataFrame, yahoo_meta: dict[str, Any], prefix: str, symbol: str, limit: int = 24) -> list[dict[str, Any]]:
    """Compute latest ETF distributions as annualized close-price yields."""
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
        rows.append({
            "etf": symbol,
            "date": distribution_date.isoformat(),
            "distribution": _round(amount, 4),
            "close": _round(close, 4),
            "annualized_distribution_pct": _round((float(amount) * 12.0 / close) * 100.0, 2),
        })
    return sorted(rows, key=lambda row: row["date"], reverse=True)[:limit]


def _display_name(prefix: str, meta: dict[str, Any]) -> str:
    config = ETF_CONFIGS[prefix]
    return meta.get("longName") or meta.get("shortName") or config["name"]


def compute_payload(etf_data: dict[str, tuple[pd.DataFrame, dict[str, Any]]], benchmark_df: pd.DataFrame, benchmark_meta: dict[str, Any]) -> dict[str, Any]:
    merged = benchmark_df
    for prefix, (df, _) in etf_data.items():
        merged = merged.merge(df, on="date", how="inner")
    merged = merged.sort_values("date")
    if merged.empty:
        raise RuntimeError("No overlapping KGLD, IGLD, IAUI, and gold futures dates after alignment")

    first = merged.iloc[0]
    prefixes = list(ETF_CONFIGS) + [BENCHMARK_PREFIX]
    bases = {prefix: float(first[f"{prefix}_close"]) for prefix in prefixes}
    if any(base <= 0 for base in bases.values()):
        raise RuntimeError("Invalid base close price for performance calculation")

    for prefix in prefixes:
        merged[f"{prefix}_return_pct"] = (merged[f"{prefix}_close"] / bases[prefix] - 1.0) * 100.0
    for prefix in ETF_CONFIGS:
        merged[f"{prefix}_relative_return_pct"] = merged[f"{prefix}_return_pct"] - merged[f"{BENCHMARK_PREFIX}_return_pct"]

    last = merged.iloc[-1]
    latest_returns = {ETF_CONFIGS[prefix]["symbol"]: float(last[f"{prefix}_return_pct"]) for prefix in ETF_CONFIGS}
    latest_returns["Gold futures"] = float(last[f"{BENCHMARK_PREFIX}_return_pct"])
    leader = max(latest_returns, key=lambda key: latest_returns[key])
    runner_up = sorted(latest_returns.values(), reverse=True)[1]
    leader_margin = latest_returns[leader] - runner_up

    series = []
    for _, row in merged.iterrows():
        item = {"date": row["date"].isoformat()}
        for prefix in ETF_CONFIGS:
            item[f"{prefix}_close"] = _round(row[f"{prefix}_close"], 4)
            item[f"{prefix}_return_pct"] = _round(row[f"{prefix}_return_pct"], 2)
            item[f"{prefix}_relative_return_pct"] = _round(row[f"{prefix}_relative_return_pct"], 2)
        item[f"{BENCHMARK_PREFIX}_close"] = _round(row[f"{BENCHMARK_PREFIX}_close"], 2)
        item[f"{BENCHMARK_PREFIX}_return_pct"] = _round(row[f"{BENCHMARK_PREFIX}_return_pct"], 2)
        series.append(item)

    distributions = sorted(
        sum((compute_distribution_rows(etf_data[prefix][0], etf_data[prefix][1], prefix, ETF_CONFIGS[prefix]["symbol"]) for prefix in ETF_CONFIGS), []),
        key=lambda row: (row["date"], row["etf"]),
        reverse=True,
    )

    names = {prefix: _display_name(prefix, meta) for prefix, (_, meta) in etf_data.items()}
    latest = {
        "date": last["date"].isoformat(),
        "gold_close": _round(last["gold_close"], 2),
        "gold_return_pct": _round(last["gold_return_pct"], 2),
        "leader": leader,
        "leader_margin_pct": _round(leader_margin, 2),
    }
    for prefix in ETF_CONFIGS:
        latest[f"{prefix}_close"] = _round(last[f"{prefix}_close"], 4)
        latest[f"{prefix}_return_pct"] = _round(last[f"{prefix}_return_pct"], 2)
        latest[f"{prefix}_relative_return_pct"] = _round(last[f"{prefix}_relative_return_pct"], 2)

    return {
        "symbol": "KGLD",
        "symbols": [config["symbol"] for config in ETF_CONFIGS.values()],
        "name": names["kgld"],
        "names": names,
        "currency": next((meta.get("currency") for _, meta in etf_data.values() if meta.get("currency")), "USD"),
        "exchange": next((meta.get("exchangeName") or meta.get("fullExchangeName") for _, meta in etf_data.values() if meta.get("exchangeName") or meta.get("fullExchangeName")), "Yahoo Finance"),
        "source": {**{prefix: "Yahoo Finance" for prefix in ETF_CONFIGS}, BENCHMARK_PREFIX: "Yahoo Finance"},
        "comparison_symbol": BENCHMARK_SYMBOL,
        "comparison_name": benchmark_meta.get("longName") or benchmark_meta.get("shortName") or BENCHMARK_NAME,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "base_date": first["date"].isoformat(),
        "latest": latest,
        "distributions": distributions,
        "series": series,
    }


def main() -> None:
    etf_data = {prefix: download_yahoo_history(config["symbol"], prefix) for prefix, config in ETF_CONFIGS.items()}
    benchmark_df, benchmark_meta = download_yahoo_history(BENCHMARK_SYMBOL, BENCHMARK_PREFIX)
    payload = compute_payload(etf_data, benchmark_df, benchmark_meta)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {OUTPUT_PATH} with {len(payload['series'])} aligned daily bars "
        f"from {payload['series'][0]['date']} to {payload['series'][-1]['date']}."
    )


if __name__ == "__main__":
    main()
