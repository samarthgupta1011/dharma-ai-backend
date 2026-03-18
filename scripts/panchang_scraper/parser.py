"""
Parser for panchang HTML pages.

Extracts structured data from rendered panchang page sections using
CSS class selectors.
"""

import re


def parse_panchang_page(page):
    """
    Parse all panchang sections from a rendered Playwright page.
    Returns a dict with section names as keys and parsed data as values.
    """
    result = {}

    # Each section has a wrapper class and produces a dict of key-value pairs
    sections = [
        ("dpSunriseMoonriseCardWrapper", "sunrise_and_moonrise"),
        ("dpCorePanchangCardWrapper", "panchang"),
        ("dpRashiNakshatraCardWrapper", "rashi_and_nakshatra"),
        ("dpAyanaRituCardWrapper", "ritu_and_ayana"),
        ("dpAuspiciousCardWrapper", "auspicious_timings"),
        ("dpInauspiciousCardWrapper", "inauspicious_timings"),
        ("dpTamilYogaCardWrapper", "anandadi_and_tamil_yoga"),
        ("dpNivasaShoolaCardWrapper", "nivas_and_shool"),
        ("dpCalendarEpochCardWrapper", "other_calendars_and_epoch"),
        ("dpDayEventCardWrapper", "day_festivals_and_events"),
    ]

    # Handle multiple dpLunarDateCardWrapper (Lunar Month + Mantri Mandala)
    lunar_wrappers = page.query_selector_all('.dpLunarDateCardWrapper')
    for wrapper in lunar_wrappers:
        title_el = wrapper.query_selector('.dpTableCardTitle')
        if title_el:
            title = _clean_text(title_el.inner_text())
            if 'Mantri' in title:
                data = _parse_card_wrapper(wrapper)
                if data:
                    result['mantri_mandala'] = data
            else:
                data = _parse_card_wrapper(wrapper)
                if data:
                    result['lunar_month_samvat'] = data

    for wrapper_class, section_key in sections:
        if section_key in ('lunar_month_samvat',):
            continue  # Already handled above
        try:
            wrapper = page.query_selector(f'.{wrapper_class}')
            if not wrapper:
                continue
            if section_key == 'day_festivals_and_events':
                data = _parse_festivals(wrapper)
            else:
                data = _parse_card_wrapper(wrapper)
            if data:
                result[section_key] = data
        except Exception as e:
            print(f"  Warning: Failed to parse '{section_key}': {e}")

    # Extract header info
    try:
        header_data = _parse_header(page)
        if header_data:
            result['header'] = header_data
    except Exception as e:
        print(f"  Warning: Failed to parse header: {e}")

    return result


def _clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalize_key(text):
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    text = text.strip().lower()
    text = re.sub(r'\s+', '_', text)
    return text


def _parse_card_wrapper(wrapper):
    """
    Parse a card wrapper section into a dict.
    Rows have dpTableCell elements alternating dpTableKey and dpTableValue.
    Typical layout: key1, val1, key2, val2 (4-column).
    Continuation rows have empty key cells.
    """
    card = wrapper.query_selector('.dpTableCard')
    if not card:
        return None

    result = {}
    rows = card.query_selector_all('.dpTableRow')
    last_key_left = None
    last_key_right = None

    for row in rows:
        cells = row.query_selector_all('.dpTableCell')
        if not cells:
            continue

        pairs = []
        i = 0
        while i < len(cells):
            cell = cells[i]
            classes = cell.get_attribute('class') or ''
            text = _clean_text(cell.inner_text())

            if 'dpTableKey' in classes:
                val_text = ""
                if i + 1 < len(cells):
                    val_text = _clean_text(cells[i + 1].inner_text())
                    i += 2
                else:
                    i += 1
                pairs.append((text, val_text))
            elif 'dpTableValue' in classes:
                pairs.append(("", text))
                i += 1
            else:
                i += 1

        for idx, (key, val) in enumerate(pairs):
            if not val or val == '\xa0':
                continue

            if key:
                norm_key = _normalize_key(key)
                if not norm_key:
                    continue
                result[norm_key] = val
                if idx == 0:
                    last_key_left = norm_key
                else:
                    last_key_right = norm_key
            else:
                target_key = last_key_left if idx == 0 else last_key_right
                if target_key and target_key in result:
                    result[target_key] += " | " + val

    return result if result else None


def _parse_festivals(wrapper):
    """Parse the Day Festivals and Events section."""
    festivals = []
    events = wrapper.query_selector_all('.dpEventName')
    for ev in events:
        name = _clean_text(ev.inner_text())
        if name:
            festivals.append(name)

    if not festivals:
        links = wrapper.query_selector_all('a.dpEvent')
        for link in links:
            name = _clean_text(link.get_attribute('title') or link.inner_text())
            if name:
                festivals.append(name)

    return {"festivals": festivals} if festivals else None


def _parse_header(page):
    """Parse the page header info block."""
    result = {}
    header = page.query_selector('.dpPHeaderWrapper')
    if not header:
        return None

    left_title = header.query_selector('.dpPHeaderLeftTitle')
    if left_title:
        result['lunar_date'] = _clean_text(left_title.inner_text())

    left_content = header.query_selector('.dpPHeaderLeftContent')
    if left_content:
        lines = [_clean_text(t) for t in left_content.inner_text().split('\n') if _clean_text(t)]
        if len(lines) > 1:
            result['paksha_tithi'] = lines[1] if len(lines) > 1 else ''
            result['samvat_info'] = lines[2] if len(lines) > 2 else ''

    left_wrapper = header.query_selector('.dpPHeaderLeftWrapper')
    if left_wrapper:
        all_text = left_wrapper.inner_text()
        lines = [_clean_text(t) for t in all_text.split('\n') if _clean_text(t)]
        for line in lines:
            if 'India' in line or ',' in line:
                result['location'] = line
                break

    right = header.query_selector('.dpPHeaderRightContent')
    if right:
        result['gregorian_date'] = _clean_text(right.inner_text())

    events_el = header.query_selector('.dpPHeaderEventList')
    if events_el:
        event_links = events_el.query_selector_all('a')
        events = [_clean_text(a.inner_text()) for a in event_links if _clean_text(a.inner_text())]
        if events:
            result['events'] = events

    return result if result else None
