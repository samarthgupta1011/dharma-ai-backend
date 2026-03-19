#!/usr/bin/env python3
"""
Cosmos DB Writer for Panchang Data

Takes scraped panchang JSON (from scraper.py output) and upserts into
the Cosmos DB `panchang` collection. Skips records that already exist
(matched by date + city unique index).

Also supports "gap detection" mode: given a set of cities and a target
end date, determines what data is missing in the DB and reports the
gaps that need to be scraped.

Usage:
    # Import scraped data into Cosmos DB
    python -m scripts.panchang_scraper.cosmos_writer import \
        --connection-string "$COSMOS_URI" \
        --input panchang_data.json

    # Detect gaps for all supported cities
    python -m scripts.panchang_scraper.cosmos_writer gaps \
        --connection-string "$COSMOS_URI" \
        --end-date 2026-12-31
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, BulkWriteError


def _get_supported_cities() -> dict[str, int]:
    """Import city config."""
    try:
        from app.config.cities import SUPPORTED_CITIES
        return SUPPORTED_CITIES
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cities",
            Path(__file__).resolve().parent.parent.parent / "app" / "config" / "cities.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.SUPPORTED_CITIES


def _get_panchang_start() -> str:
    try:
        from app.config.cities import PANCHANG_DATA_START
        return PANCHANG_DATA_START
    except ImportError:
        return "2026-01-01"


def _extract_core_fields(raw_data: dict) -> dict:
    """Extract promoted top-level fields from raw scraper data."""
    panchang = raw_data.get("panchang", {})
    sunrise = raw_data.get("sunrise_and_moonrise", {})

    return {
        "tithi": panchang.get("tithi", ""),
        "nakshatra": panchang.get("nakshatra", ""),
        "yoga": panchang.get("yoga", ""),
        "karana": panchang.get("karana", ""),
        "paksha": panchang.get("paksha", ""),
        "sunrise": sunrise.get("sunrise", ""),
        "sunset": sunrise.get("sunset", ""),
    }


def import_data(connection_string: str, input_path: str, db_name: str = "dharma_db"):
    """Import scraped JSON data into Cosmos DB panchang collection."""
    with open(input_path, 'r') as f:
        data = json.load(f)

    client = MongoClient(connection_string)
    db = client[db_name]
    collection = db["panchang"]

    # Ensure unique index exists
    collection.create_index([("date", 1), ("city", 1)], unique=True)

    total = 0
    inserted = 0
    skipped = 0
    errors = 0

    empty = 0

    for date_str, cities in data.items():
        record_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        for city_name, raw_data in cities.items():
            total += 1

            # Skip records where the scraper got an empty/blocked page
            if not raw_data or not raw_data.get("panchang"):
                empty += 1
                continue

            core = _extract_core_fields(raw_data)

            doc = {
                "date": datetime.combine(record_date, datetime.min.time()),
                "city": city_name,
                **core,
                "raw_data": raw_data,
                "inferences": [],
            }

            try:
                collection.insert_one(doc)
                inserted += 1
                print(f"  Inserted: {city_name} {date_str}")
            except DuplicateKeyError:
                skipped += 1
            except Exception as e:
                errors += 1
                print(f"  Error: {city_name} {date_str}: {e}")

    client.close()

    print(f"\nImport complete:")
    print(f"  Total: {total}")
    print(f"  Inserted: {inserted}")
    print(f"  Skipped (already exists): {skipped}")
    print(f"  Skipped (empty data): {empty}")
    print(f"  Errors: {errors}")

    return {"total": total, "inserted": inserted, "skipped": skipped, "empty": empty, "errors": errors}


def detect_gaps(connection_string: str, end_date: date, db_name: str = "dharma_db"):
    """
    Detect missing panchang data for all supported cities.

    For each city, finds the latest date with data (or PANCHANG_DATA_START
    if no data exists), and reports the gap between that date and end_date.

    Returns a dict of {city: {"start": first_missing_date, "end": end_date, "missing_days": N}}
    """
    cities = _get_supported_cities()
    start_str = _get_panchang_start()
    data_start = datetime.strptime(start_str, "%Y-%m-%d").date()

    client = MongoClient(connection_string)
    db = client[db_name]
    collection = db["panchang"]

    gaps = {}
    total_missing = 0

    for city_name in cities:
        # Delete any records with empty raw_data so they get re-scraped
        deleted = collection.delete_many(
            {"city": city_name, "$or": [
                {"raw_data": {}},
                {"raw_data": None},
                {"tithi": "", "nakshatra": "", "sunrise": ""},
            ]}
        )
        if deleted.deleted_count > 0:
            print(f"  Cleaned {deleted.deleted_count} empty record(s) for {city_name}")

        # Find the latest date for this city
        latest = collection.find_one(
            {"city": city_name},
            sort=[("date", -1)],
            projection={"date": 1},
        )

        if latest and latest.get("date"):
            latest_date = latest["date"]
            if isinstance(latest_date, datetime):
                latest_date = latest_date.date()
            next_missing = latest_date + timedelta(days=1)
        else:
            next_missing = data_start

        if next_missing <= end_date:
            missing_days = (end_date - next_missing).days + 1
            gaps[city_name] = {
                "start": next_missing.isoformat(),
                "end": end_date.isoformat(),
                "missing_days": missing_days,
            }
            total_missing += missing_days
        else:
            gaps[city_name] = {
                "start": None,
                "end": end_date.isoformat(),
                "missing_days": 0,
            }

    client.close()

    print(f"\nGap analysis (target end date: {end_date}):")
    print(f"{'City':<15} {'First missing':<15} {'Missing days':<12}")
    print("-" * 42)
    for city, info in sorted(gaps.items()):
        start = info['start'] or 'up to date'
        print(f"{city:<15} {start:<15} {info['missing_days']:<12}")
    print(f"\nTotal missing city×date combos: {total_missing}")

    return gaps, total_missing


def main():
    parser = argparse.ArgumentParser(description="Panchang data Cosmos DB operations")
    sub = parser.add_subparsers(dest="command", required=True)

    # Import command
    imp = sub.add_parser("import", help="Import scraped JSON into Cosmos DB")
    imp.add_argument("--connection-string", required=True, help="Cosmos DB MongoDB connection URI")
    imp.add_argument("--input", required=True, help="Input JSON file from scraper")
    imp.add_argument("--db-name", default="dharma_db", help="Database name")

    # Gaps command
    gap = sub.add_parser("gaps", help="Detect missing data for all supported cities")
    gap.add_argument("--connection-string", required=True, help="Cosmos DB MongoDB connection URI")
    gap.add_argument("--end-date", required=True, help="Target end date (YYYY-MM-DD)")
    gap.add_argument("--db-name", default="dharma_db", help="Database name")

    args = parser.parse_args()

    if args.command == "import":
        import_data(args.connection_string, args.input, args.db_name)
    elif args.command == "gaps":
        end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
        detect_gaps(args.connection_string, end, args.db_name)


if __name__ == "__main__":
    main()
