# Fear & Greed updates

The dashboard uses **CFGI's separate Bitcoin and Ethereum 1D readings**. These
are not Alternative.me's crypto-wide index and are not the former
BitcoinFear/EthereumFear social posts. The source links on each dial disclose
the provider and timeframe. The old Nitter RSS endpoints returned HTTP 410 Gone,
leaving both dials frozen at 20 August 2026 despite an active hourly cron.

`fetch-fear-greed.py` reads each asset's structured Next.js JSON from its public
CFGI page. Values, classifications and UTC observation times come from the same
`current` record. Labels are preserved, not recalculated with another provider's
thresholds. If that schema changes, parsing fails closed.

- Each source is fetched independently. Failure retains its last-known reading
  and original source timestamp, marks it `error`, and does not block the other.
- A source observation older than three hours is marked `stale`. Future-dated
  readings beyond five minutes are rejected. Browser rendering also checks age,
  so a stopped scheduler cannot leave old data looking current.
- `sourcePublishedAt` is the observation time displayed on the card.
  `lastCheckedAt` and top-level `lastUpdated` are pipeline attempt times only.
- JSON is atomically replaced. Generation does not commit or push. A nonzero
  generator exit means at least one asset is stale/unavailable; the wrapper
  still publishes the honest partial result before returning that status.

## Local automation

The installed local crontab runs hourly at minute **7**, away from five-minute
stock updates (machine timezone Australia/Sydney):

```cron
7 * * * * /bin/bash /home/amak/findamak.github.io/scripts/update_fear_greed_and_push.sh >> /home/amak/scripts/fear-greed-cron.log 2>&1
```

The wrapper sets PATH/HOME, locks overlapping Fear & Greed runs, verifies `main`,
synchronizes the remote, generates the JSON, commits **only `fear-greed.json`**,
and pushes with bounded retries. It uses the same checkout as stock automation
because that publisher does not pull remote-only commits. No force-push, reset
or stash is used; divergent history with uncommitted work fails safely. Git's
own index locking protects concurrent commits; an interrupted run can be retried.
There is no second scheduled GitHub Actions updater for this data.

Manual refresh (also publishes):

```sh
bash scripts/update_fear_greed_and_push.sh
```

Tests (no live publication; the Git integration test uses a temporary local remote):

```sh
/usr/bin/python3 -m unittest discover -s tests -p 'test_fear_greed*.py' -v
node tests/test_fear_greed_dashboard.cjs
bash -n scripts/update_fear_greed_and_push.sh
```

To verify production, check the timestamped cron log, the latest Pages deployment,
`https://findamak.github.io/fear-greed.json` and both dials on
`https://findamak.github.io/dashboard.html`. Confirm **source** dates, not just
pipeline timestamps. If a provider stops publishing, fix the provider/parser;
never stamp a cached observation with the current date.
