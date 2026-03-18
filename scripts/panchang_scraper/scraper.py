#!/usr/bin/env python3
"""
Panchang Scraper — adapted for dharma-ai-backend.

Scrapes daily panchang data for configurable cities and
date ranges. Outputs structured JSON with checkpoint/resume support.

City configuration is read from app/config/cities.py (single source of truth).

Usage (standalone):
    python -m scripts.panchang_scraper.scraper --start-date 2026-04-01 --end-date 2026-04-30
    python -m scripts.panchang_scraper.scraper --start-date 2026-04-01 --end-date 2026-04-30 --cities Delhi,Mumbai
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from scripts.panchang_scraper.parser import parse_panchang_page

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL = "https://www.drikpanchang.com/panchang/day-panchang.html"
REQUEST_DELAY = 1.0
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]
PAGE_TIMEOUT = 60000
PROGRESS_FILE = "progress.json"


def _get_supported_cities() -> dict[str, int]:
    """Import city config. Works whether run as module or standalone."""
    try:
        from app.config.cities import SUPPORTED_CITIES
        return SUPPORTED_CITIES
    except ImportError:
        # Fallback for running outside the app context
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cities",
            Path(__file__).resolve().parent.parent.parent / "app" / "config" / "cities.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.SUPPORTED_CITIES


def build_url(geoname_id, date):
    date_str = date.strftime("%d/%m/%Y")
    return f"{BASE_URL}?geoname-id={geoname_id}&date={date_str}"


def generate_dates(start_date, end_date):
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def load_progress(progress_path):
    if progress_path.exists():
        with open(progress_path, 'r') as f:
            return json.load(f)
    return {"completed": [], "failed": {}}


def save_progress(progress_path, progress):
    with open(progress_path, 'w') as f:
        json.dump(progress, f, indent=2)


def load_output(output_path):
    if output_path.exists():
        with open(output_path, 'r') as f:
            return json.load(f)
    return {}


def save_output(output_path, data):
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def make_task_key(date, city_name):
    return f"{date.strftime('%Y-%m-%d')}__{city_name}"


def expand_all_sections(page):
    try:
        toggles = page.query_selector_all(
            '.dpTableHeaderRow, [data-toggle], .accordion-toggle, '
            '.collapsible-header, .panel-heading'
        )
        for toggle in toggles:
            try:
                toggle.click()
                page.wait_for_timeout(200)
            except Exception:
                pass
    except Exception:
        pass


def scrape_single_page(page, city_name, geoname_id, date, save_html_path=None):
    url = build_url(geoname_id, date)
    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(5000)

    for selector in ['#dpPanchangDetailTbl', '.dpTableBorderFull', 'table.dpTable', 'table']:
        try:
            page.wait_for_selector(selector, timeout=5000)
            break
        except Exception:
            continue

    _dismiss_popups(page)
    expand_all_sections(page)
    page.wait_for_timeout(500)

    if save_html_path:
        html = page.content()
        with open(save_html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  Saved HTML to {save_html_path}")

    data = parse_panchang_page(page)
    return data


def _dismiss_popups(page):
    popup_selectors = [
        'button:has-text("Accept")',
        'button:has-text("OK")',
        'button:has-text("Got it")',
        'button:has-text("Close")',
        '.cookie-consent-accept',
        '#cookie-accept',
        '.modal .close',
    ]
    for selector in popup_selectors:
        try:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                btn.click()
                page.wait_for_timeout(300)
        except Exception:
            pass


def scrape_with_retry(page, city_name, geoname_id, date, save_html_path=None):
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            data = scrape_single_page(page, city_name, geoname_id, date, save_html_path)
            return data, None
        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES - 1:
                backoff = RETRY_BACKOFF[attempt] if attempt < len(RETRY_BACKOFF) else RETRY_BACKOFF[-1]
                print(f"  Attempt {attempt + 1}/{MAX_RETRIES} failed: {last_error}")
                print(f"  Retrying in {backoff}s...")
                time.sleep(backoff)
            else:
                print(f"  All {MAX_RETRIES} attempts failed: {last_error}")
    return None, last_error


def run_scraper(cities, start_date, end_date, output_path, progress_path,
                save_html=False, headless=True, request_delay=REQUEST_DELAY):
    dates = generate_dates(start_date, end_date)
    total_tasks = len(dates) * len(cities)

    progress = load_progress(progress_path)
    output_data = load_output(output_path)

    completed_count = len(progress["completed"])
    if completed_count > 0:
        print(f"Resuming: {completed_count}/{total_tasks} already completed")

    pending_tasks = []
    for date in dates:
        for city_name, geoname_id in cities.items():
            task_key = make_task_key(date, city_name)
            if task_key not in progress["completed"]:
                pending_tasks.append((date, city_name, geoname_id, task_key))

    if not pending_tasks:
        print("All tasks already completed!")
        return

    print(f"Tasks remaining: {len(pending_tasks)}/{total_tasks}")
    print(f"Cities: {', '.join(cities.keys())}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Output: {output_path}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            for i, (date, city_name, geoname_id, task_key) in enumerate(pending_tasks):
                task_num = completed_count + i + 1
                date_display = date.strftime('%d/%m/%Y')

                print(f"[{task_num}/{total_tasks}] {city_name} {date_display}...", end=" ", flush=True)

                html_path = None
                if save_html and i == 0:
                    html_path = str(output_path.parent / "debug_page.html")

                data, error = scrape_with_retry(page, city_name, geoname_id, date, html_path)

                if error:
                    progress["failed"][task_key] = error
                    save_progress(progress_path, progress)
                    print(f"\nFAILED: {city_name} {date_display} after {MAX_RETRIES} retries.")
                    print(f"Error: {error}")
                    print(f"\nProgress saved. Re-run to resume.")
                    print(f"Completed: {len(progress['completed'])}/{total_tasks}")
                    browser.close()
                    sys.exit(1)

                date_str = date.strftime('%Y-%m-%d')
                if date_str not in output_data:
                    output_data[date_str] = {}
                output_data[date_str][city_name] = data

                progress["completed"].append(task_key)
                progress["failed"].pop(task_key, None)

                save_output(output_path, output_data)
                save_progress(progress_path, progress)

                print("done")

                if i < len(pending_tasks) - 1:
                    time.sleep(request_delay)

        except KeyboardInterrupt:
            print(f"\n\nInterrupted. Progress saved.")
            print(f"Completed: {len(progress['completed'])}/{total_tasks}")
            browser.close()
            sys.exit(1)
        finally:
            browser.close()

    # Retry previously failed tasks
    if progress["failed"]:
        failed_keys = list(progress["failed"].keys())
        print(f"\nRetrying {len(failed_keys)} previously failed task(s)...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            try:
                for task_key in failed_keys:
                    date_str, city_name = task_key.split("__", 1)
                    date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    geoname_id = cities[city_name]

                    print(f"  Retrying {city_name} {date.strftime('%d/%m/%Y')}...", end=" ", flush=True)

                    data, error = scrape_with_retry(page, city_name, geoname_id, date)

                    if error:
                        print(f"FAILED again: {error}")
                        continue

                    if date_str not in output_data:
                        output_data[date_str] = {}
                    output_data[date_str][city_name] = data

                    progress["completed"].append(task_key)
                    del progress["failed"][task_key]

                    save_output(output_path, output_data)
                    save_progress(progress_path, progress)
                    print("done")

                    time.sleep(request_delay)
            finally:
                browser.close()

    # Final summary
    total_completed = len(progress["completed"])
    total_failed = len(progress["failed"])
    print(f"\nScraping complete!")
    print(f"  Completed: {total_completed}/{total_tasks}")
    if total_failed > 0:
        print(f"  Still failed: {total_failed}")
        for key, err in progress["failed"].items():
            print(f"    - {key}: {err}")
        print(f"\nRe-run to retry failed tasks.")
    else:
        print(f"  All tasks successful!")
        if progress_path.exists():
            progress_path.unlink()
            print(f"  Cleaned up progress file.")


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: '{date_str}'. Use YYYY-MM-DD."
        )


def parse_cities(cities_str):
    supported = _get_supported_cities()
    names = [c.strip() for c in cities_str.split(",") if c.strip()]
    result = {}
    for name in names:
        matched = False
        for default_name, geoname_id in supported.items():
            if name.lower() == default_name.lower():
                result[default_name] = geoname_id
                matched = True
                break
        if not matched:
            print(f"Error: Unknown city '{name}'. Supported: {', '.join(supported.keys())}")
            sys.exit(1)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Scrape panchang data"
    )
    parser.add_argument("--start-date", type=parse_date, required=True)
    parser.add_argument("--end-date", type=parse_date, required=True)
    parser.add_argument("--output", type=str, default="panchang_data.json")
    parser.add_argument("--cities", type=str, default=None)
    parser.add_argument("--save-html", action="store_true")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--delay", type=float, default=None)

    args = parser.parse_args()

    if args.start_date > args.end_date:
        print("Error: start-date must be before or equal to end-date")
        sys.exit(1)

    supported = _get_supported_cities()
    cities = parse_cities(args.cities) if args.cities else supported

    request_delay = args.delay if args.delay is not None else REQUEST_DELAY

    output_path = Path(args.output).resolve()
    progress_path = output_path.parent / PROGRESS_FILE

    run_scraper(
        cities=cities,
        start_date=args.start_date,
        end_date=args.end_date,
        output_path=output_path,
        progress_path=progress_path,
        request_delay=request_delay,
        save_html=args.save_html,
        headless=not args.headed,
    )


if __name__ == "__main__":
    main()
