# Panchang Scraper

Scrapes daily panchang data and imports it into Cosmos DB.

## How It Works

1. Reads supported cities from `app/config/cities.py`
2. Detects gaps in Cosmos DB (what's missing between `2026-01-01` and the target end date)
3. Scrapes missing data using Playwright (headless Chromium)
4. Imports results into the `panchang` collection

## Usage

**Via GitHub Actions (recommended):**

Go to Actions → "Scrape Panchang Data" → Run workflow → set `end_date` (e.g. `2026-12-31`).

Re-trigger until the summary shows 0 missing records. Each run scrapes up to `batch_size` (default 500) city×date combos.

**Locally:**

```bash
pip install playwright pymongo
playwright install chromium

# Scrape
python -m scripts.panchang_scraper.scraper \
  --start-date 2026-04-01 --end-date 2026-04-30 \
  --output panchang_data.json

# Import into Cosmos DB
python -m scripts.panchang_scraper.cosmos_writer import \
  --connection-string "$COSMOS_URI" --input panchang_data.json

# Check gaps
python -m scripts.panchang_scraper.cosmos_writer gaps \
  --connection-string "$COSMOS_URI" --end-date 2026-12-31
```

## Adding a City

1. Add it to `SUPPORTED_CITIES` in `app/config/cities.py` (find the GeoName ID at [geonames.org](https://www.geonames.org/))
2. Push to `main`
3. Trigger the GitHub Action — it backfills the new city from `2026-01-01`

## Required Access for GitHub Actions

The service principal in `AZURE_CREDENTIALS` needs **Key Vault Secrets User** on `dharma-kv` to fetch the Cosmos DB connection string at runtime:

```bash
az role assignment create \
  --assignee <service-principal-object-id> \
  --role "Key Vault Secrets User" \
  --scope /subscriptions/<subscription-id>/resourceGroups/dharma-rg/providers/Microsoft.KeyVault/vaults/dharma-kv
```

No other secrets or permissions are needed — the workflow fetches everything from Key Vault.
