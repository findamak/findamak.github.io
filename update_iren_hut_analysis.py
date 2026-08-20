#!/usr/bin/env python3
"""Build dashboard data for a daily IREN versus HUT comparison.

Sources: Yahoo Finance daily closes and SEC EDGAR company-submissions feeds.
The script never overwrites the published JSON if either price series is absent.
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf

REPO = Path("/home/amak/findamak.github.io")
OUTPUT = REPO / "iren-hut-analysis.json"
USER_AGENT = "findamak.github.io dashboard contact@findamak.com"
COMPANIES = {
    "IREN": {"cik": "0001878848", "name": "IREN", "fallback": {"form": "8-K", "date": "2026-08-13", "accession": "0001140361-26-032638", "url": "https://www.sec.gov/Archives/edgar/data/1878848/000114036126032638/ef20080141_8k.htm"}},
    "HUT": {"cik": "0001964789", "name": "Hut 8", "fallback": {"form": "8-K", "date": "2026-08-04", "accession": "0001104659-26-090041", "url": "https://www.sec.gov/Archives/edgar/data/1964789/000110465926090041/tm2621890d1_8k.htm"}},
}


def fetch_json(url):
    result = subprocess.run(
        ["/usr/bin/curl", "--fail", "--silent", "--show-error", "-A", USER_AGENT, url],
        check=True, capture_output=True, text=True, timeout=45
    )
    return json.loads(result.stdout)


def price_snapshot(symbol):
    history = yf.Ticker(symbol).history(period="1y", auto_adjust=False)
    if history.empty or "Close" not in history:
        raise RuntimeError("no daily close data returned for " + symbol)
    closes = history["Close"].dropna()
    if len(closes) < 2:
        raise RuntimeError("insufficient daily close data for " + symbol)
    latest = float(closes.iloc[-1])

    def change(days):
        index = max(0, len(closes) - 1 - days)
        earlier = float(closes.iloc[index])
        return round((latest / earlier - 1) * 100, 1) if earlier else None

    last_date = closes.index[-1]
    return {
        "price": round(latest, 2),
        "date": last_date.strftime("%Y-%m-%d"),
        "returns": {"30d": change(21), "90d": change(63), "1y": change(252)},
        "source": "https://finance.yahoo.com/quote/" + symbol,
    }


def latest_material_filing(symbol, cik, fallback):
    try:
        data = fetch_json("https://data.sec.gov/submissions/CIK" + cik + ".json")
        recent = data["filings"]["recent"]
        for index, form in enumerate(recent["form"]):
            if form in ("10-K", "10-Q", "8-K", "6-K"):
                accession = recent["accessionNumber"][index]
                document = recent["primaryDocument"][index]
                accession_digits = accession.replace("-", "")
                return {
                    "form": form,
                    "date": recent["filingDate"][index],
                    "accession": accession,
                    "url": "https://www.sec.gov/Archives/edgar/data/" + str(int(cik)) + "/" + accession_digits + "/" + document,
                    "status": "live",
                }
        raise RuntimeError("no material filing found")
    except Exception as error:
        print("SEC lookup unavailable for " + symbol + ": " + str(error), file=sys.stderr)
        retained = dict(fallback)
        retained["status"] = "last verified"
        return retained


def signed(value):
    if value is None:
        return "n/a"
    return ("+" if value >= 0 else "") + f"{value:.1f}%"


def momentum_label(iren, hut):
    i30, h30 = iren["returns"]["30d"], hut["returns"]["30d"]
    if i30 is None or h30 is None:
        return "Price momentum was unavailable; use the filings and business-execution sections instead."
    if i30 > h30:
        lead = "IREN has held up better"
    elif h30 > i30:
        lead = "HUT has held up better"
    else:
        lead = "The two shares have moved similarly"
    return (lead + " over the last 30 trading days (IREN " + signed(i30) +
            ", HUT " + signed(h30) + "). This is price performance, not total return or investment advice.")


def filing_reading(symbol, filing):
    kind = filing["form"]
    if kind in ("10-K", "10-Q"):
        return symbol + "'s newest material EDGAR document is its " + kind + " filed " + filing["date"] + "."
    return symbol + "'s newest material EDGAR document is an " + kind + " filed " + filing["date"] + "; read it for new contracts, financing, or operating updates."


def build_payload():
    prices = {symbol: price_snapshot(symbol) for symbol in COMPANIES}
    filings = {symbol: latest_material_filing(symbol, company["cik"], company["fallback"])
               for symbol, company in COMPANIES.items()}
    checked = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "lastUpdated": checked,
        "disclaimer": "Research only — not financial advice. Figures are in US dollars unless stated otherwise.",
        "prices": prices,
        "filings": filings,
        "dailyRead": momentum_label(prices["IREN"], prices["HUT"]),
        "comparison": [
            {
                "title": "IREN — nearer-term AI-cloud execution",
                "text": "The core question is whether IREN keeps converting its Microsoft AI-cloud program into delivered capacity. Its 13 August 2026 announcement said Horizon 1, the first 50MW IT-load deployment in its four-deployment Microsoft program, had been delivered and accepted. The company described the agreement as a five-year US$9.7bn cloud-services contract and targeted 480MW gross AI-cloud capacity in 2026 and 1.2GW in 2027.",
                "source": "https://www.sec.gov/Archives/edgar/data/1878848/000114036126032638/ef20080141_ex99-1.htm"
            },
            {
                "title": "HUT — larger, later-stage AI-data-centre buildout",
                "text": "Hut 8 reported 949MW of contracted AI IT capacity, about US$26.6bn aggregate base-term contract value, more than US$1.75bn expected average annual NOI and US$7.5bn of investment-grade project financing. Its stated initial River Bend and Beacon Point data-hall deliveries were targeted for 2027, making construction, energisation and financing execution central risks.",
                "source": "https://www.sec.gov/Archives/edgar/data/1964789/000110465926090041/tm2621890d1_ex99-1.htm"
            }
        ],
        "takeaway": "IREN is the cleaner choice for investors prioritising demonstrated AI-cloud delivery. HUT is the higher-beta choice for investors willing to underwrite a larger contracted pipeline and a longer construction/financing timetable. The balance sheets are not directly comparable: HUT's project financing and restricted cash make headline cash a poor stand-alone leverage measure.",
        "sources": [
            {"label": "IREN price history", "url": prices["IREN"]["source"]},
            {"label": "HUT price history", "url": prices["HUT"]["source"]},
            {"label": "IREN latest EDGAR filing", "url": filings["IREN"]["url"]},
            {"label": "HUT latest EDGAR filing", "url": filings["HUT"]["url"]},
            {"label": "IREN Horizon 1 announcement", "url": "https://www.sec.gov/Archives/edgar/data/1878848/000114036126032638/ef20080141_ex99-1.htm"},
            {"label": "Hut 8 AI capacity announcement", "url": "https://www.sec.gov/Archives/edgar/data/1964789/000110465926090041/tm2621890d1_ex99-1.htm"}
        ]
    }


def write_json(payload):
    temporary = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=REPO, delete=False)
    try:
        json.dump(payload, temporary, indent=2)
        temporary.write("\n")
        temporary.close()
        os.replace(temporary.name, OUTPUT)
    finally:
        if os.path.exists(temporary.name):
            os.unlink(temporary.name)


def git_commit_and_push():
    def run(*args, check=True):
        return subprocess.run(args, cwd=REPO, check=check, text=True, capture_output=True)
    run("git", "fetch", "origin")
    run("git", "rebase", "origin/main")
    if run("git", "diff", "--quiet", "--", OUTPUT.name, check=False).returncode == 0:
        print("No analysis data change to publish.")
        return
    run("git", "add", OUTPUT.name)
    run("git", "commit", "-m", "Update IREN vs HUT analysis at " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    run("git", "push", "origin", "main")
    print("Published " + OUTPUT.name)


def main():
    try:
        payload = build_payload()
        write_json(payload)
        print("Updated " + str(OUTPUT))
        if "--no-push" not in sys.argv:
            git_commit_and_push()
    except Exception as error:
        print("IREN/HUT update failed: " + str(error), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
