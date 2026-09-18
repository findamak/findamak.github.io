# Daily ETF issuer refresh

`/usr/bin/python3 scripts/update_etf.py` refreshes **all 12 ETFs** in `etf.html`.
It updates only the two performance/yield cells, their source/basis/date annotations,
the high/low summary and refresh status. AUM, inception dates, names, existing notes,
and fund-page links are preserved. This is separate from `fetch-etf.py`.

## Running and scheduling

Dependencies: Python 3.10+, `beautifulsoup4`, `curl_cffi`, timezone data and Poppler
`pdftotext`. These are present for `/usr/bin/python3` on amak. Poppler is currently
`/home/linuxbrew/.linuxbrew/bin/pdftotext`; the updater has that fallback and the
wrapper includes Linuxbrew on PATH. Use a venv if installing elsewhere; no runtime
package installation is performed.

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests -p 'test*etf*.py' -v
bash scripts/update_etf_and_push.sh --check   # offline checks; no Git changes/push
/usr/bin/python3 scripts/update_etf.py       # network + local HTML only, no Git
# Alternate copy for a non-publishing integration check:
/usr/bin/python3 scripts/update_etf.py --page /path/to/copy-of-etf.html
```

Installed **amak user crontab**, daily **13:02 Australia/Sydney** (AEST/AEDT):

```cron
2 13 * * * /home/amak/findamak.github.io/scripts/update_etf_and_push.sh >> /home/amak/scripts/etf-guide-cron.log 2>&1
```

Host cron timezone must be Australia/Sydney (already configured on amak). No cron
is installed by these scripts. 13:02 avoids the noon BTC, 12:30 BTCI, 12:45 gold
and every-five-minute stock jobs. Refresh display explicitly uses Sydney time;
logs/status preserve UTC ISO timestamps. Schedule and logs should be monitored.

The wrapper operates on main in the **shared checkout**, because the existing
stock job pushes without pulling and an isolated clone could leave that job
diverged. It locks against another ETF wrapper run; other legacy jobs do not
share this lock, so this is not a repository-wide mutex. It refuses dirty ETF
edits, pulls fast-forward before fetching, commits **only etf.html**, and supplies
Git identity per command (no persistent config mutation). Push retries rebase
only with a clean tracked worktree/index. On conflict/dirty worktree it exits
nonzero, retains the local commit and never force-pushes or stashes other jobs'
work. Resolve the checkout and retry. `ETF_REPO_DIR` and `ETF_PYTHON` can override
paths for controlled testing. Direct updater invocations should not overlap.

## Data definitions and actual issuer endpoints

| ETFs | Source and selection | Yield definition |
|---|---|---|
| VT, VTI | GET `https://investor.vanguard.com/irr/funds/profile/{3141,0970}`; `performancefees.totalReturns.summary.monthEnd.fundReturn.sinceInceptionPct` and `asOfDate` | Calculated trailing dividends / current NAV, USD, **record-date** window from `distributions.incomeCapitalGains`; not SEC yield |
| VTS, VAS, VEU, VGS | GET `https://www.vanguard.com.au/personal/api/products/personal/funds/etf`; match port IDs 0970,8205,0991,8212; select `ANNL` + `ITD`, not cumulative returns | GET `.../personal/fund/{portId}/overview`; cash distributions / NAV, **ex-date** window; CASH tax component for VAS/VGS, INC for VTS/VEU, never grossed-up or summed tax components |
| GPIX | POST `https://am.gs.com/services/funds`, public website GraphQL `getFundsDetail`; `country=us,language=en,audience=advisors,pvNumber=PV105258,shareClassId=38149W622`; `averageAnnualizedReturns[id=nav].sinceInception` | `yield[label=twelveMthTrailingYield]`, own asAtDate |
| QQQI, BTCI | GET `https://neosfunds.com/{qqqi,btci}/`; first monthly NAV performance table, **Inception (Annualized)** column, never Inception (Cumulative) or the older quarterly banner | Explicit **12-Month Trailing Distribution Rate**, may include return of capital; not forward annualized distribution rate or earned income |
| IVV (ASX) | GET `https://www.blackrock.com/au/products/275304/ishares-s-p-500-etf`; Average Annual, Total Return, Incept. | 12m Trailing Yield and its own date |
| NDQ | GET `https://www.betashares.com.au/fund/nasdaq-100-etf/`; Since inception p.a., fund not benchmark | 12 mth distribution yield |
| IBTC | GET `https://www.monochrome.au/files/monochrome-bitcoin-etf-fund-factsheet`; follows current PDF redirect; `Since Inception p.a.` in IBTC row | **N/A**, not a fabricated 0%. Freshly downloaded `.../monochrome-bitcoin-etf-product-disclosure-statement` must state: “In the normal course Holders should not expect to receive any distributions of ordinary income.” Policy document date displayed separately |

Vanguard calculated yields sum the trailing calendar year `(date minus one year,
date]`, exclude announced future distributions, require at least four quarterly
payments plus older history, reject duplicates and currency mismatches. VTS/VEU
NAV/dividends are **USD underlying fund** data, not AUD ASX distribution yield.
Australian performance comes from the Australian issuer series, never US VTI
substituted for VTS. Inception metadata/listing dates can differ; return windows
are the issuer's series. IVV includes pre-redomiciliation history. Cross-fund
performance numbers differ in currency and period and are not directly comparable.

## Failure and freshness contract

- Four workers; request timeout 45 seconds and up to three attempts with backoff.
  `curl_cffi` Chrome TLS works for issuer sites that reject ordinary urllib.
- All 12 pairs must validate before **any numeric cell** changes. Success means
  23 numeric figures plus a verified IBTC distribution policy, not 24 yields.
- Reject missing/ambiguous fields, nonfinite/out-of-range numbers, future dates,
  daily calculated-yield NAV dates older than 10 days, and published numeric
  dates older than 120 days. An older current PDS is not a market quote and is
  exempt from that age limit; its date is still shown.
- On any source failure, **all previous cells are retained**, last-success time
  does not advance, and the summary + visible status say STALE / ERROR and list
  failed ETFs. Exit status is 1. The wrapper still publishes that honest error
  marker, then returns nonzero. Detailed failures are JSON lines on stdout.
- Successful writes atomically replace one HTML file with fsync + rename, so
  metrics and dates cannot be partially published across multiple payloads.
- “Last updated” is successful retrieval time, **not source valuation time**.
  Source dates are next to each metric, and failure-attempt times below tables.
- If the scheduler never runs or Git push itself fails, a static page cannot
  display the new failure; check the cron log and last successful refresh age.

## First real execution

On 18 September 2026 the live refresh verified 12/12, including both Monochrome
PDFs. Performance source dates were 31 August 2026 except IBTC (31 July 2026).
The PDS was dated 4 July 2025. A second minimal-environment invocation with only
HOME and `/usr/bin:/bin` PATH also exercised Poppler's explicit fallback.
No commit, push or crontab installation is part of the Python updater.
