"""One-time script to extract logo SVGs from the JSX resource file and fix spacing."""
import re
import json
import os

JSX_PATH = "/Users/samarthgupta/Desktop/src/dharma-ai-resources/myDharma Logos and Color Pallette.jsx"
OUT_DIR = "website/assets/icons/logos"

with open(JSX_PATH, "r") as f:
    content = f.read()

# Extract the SVG_DATA JSON
start = content.index('const SVG_DATA = {') + len('const SVG_DATA = ')
depth = 0
end = start
for i, ch in enumerate(content[start:], start):
    if ch == '{':
        depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0:
            end = i + 1
            break

svg_json = content[start:end]
svg_data = json.loads(svg_json)

os.makedirs(OUT_DIR, exist_ok=True)

dark = svg_data["dark"]


def fix_text_gap(svg, my_y=245, dharma_y=280):
    """Move text elements closer to the icon."""
    svg = re.sub(
        r'(<text[^>]*y=")300(".*?>my</text>)',
        rf'\g<1>{my_y}\2',
        svg,
    )
    svg = re.sub(
        r'(<text[^>]*y=")340(".*?>Dharma</text>)',
        rf'\g<1>{dharma_y}\2',
        svg,
    )
    return svg


def fix_horizontal_text_gap(svg):
    """Fix horizontal logo text — match stacked logo proportions."""
    # Move text x from 312 to 215 (tighter to icon)
    svg = svg.replace('x="312.0"', 'x="215.0"')
    # Match letter-spacing to stacked logo: Dharma 0.06em → 0.08em
    svg = svg.replace('letter-spacing="0.06em"', 'letter-spacing="0.08em"')
    # Move "my" up and "Dharma" down to create proper gap
    # Original: my y=84, Dharma y=124 (40 gap, but font-size 28+44 = text overlap)
    # Fix: my y=78, Dharma y=128 (50 gap)
    svg = re.sub(
        r'(<text[^>]*y=")84\.0("[^>]*>my</text>)',
        r'\g<1>76.0\2',
        svg,
    )
    svg = re.sub(
        r'(<text[^>]*y=")118\.0("[^>]*>Dharma</text>)',
        r'\g<1>128.0\2',
        svg,
    )
    return svg


# Stacked logos (centered, icon on top)
stacked_transparent = fix_text_gap(dark["logo-transparent-stacked.svg"])
stacked_full = fix_text_gap(dark["logo-full-stacked.svg"])
# Wordmark — fix letter-spacing to match stacked
wordmark = dark["wordmark-stacked.svg"]
wordmark = wordmark.replace('letter-spacing="0.3em"', 'letter-spacing="0.25em"')
wordmark = wordmark.replace('letter-spacing="0.06em"', 'letter-spacing="0.08em"')

# Horizontal — remove bg rect, fix text gap
horiz = dark["logo-horizontal.svg"]
horiz = re.sub(r"<rect[^/]*/>", "", horiz, count=1)
horiz = fix_horizontal_text_gap(horiz)

saves = {
    "logo-stacked.svg": stacked_transparent,
    "logo-icon.svg": dark["logo-transparent-icon.svg"],
    "logo-full-stacked.svg": stacked_full,
    "logo-wordmark.svg": wordmark,
    "logo-horizontal.svg": horiz,
}

# ── App Icons (iOS + Android) ────────────────────────────────────────────────
app_dir = os.path.join(OUT_DIR, "app-icons")
os.makedirs(app_dir, exist_ok=True)

app_icons = {
    # iOS App Store
    "app-icon-1024x1024.svg": dark["app-icon-1024x1024.svg"],
    # iPhone
    "app-icon-180x180.svg": dark["app-icon-180x180.svg"],
    "app-icon-120x120.svg": dark["app-icon-120x120.svg"],
    "app-icon-60x60.svg": dark["app-icon-60x60.svg"],
    # iPad
    "app-icon-167x167.svg": dark["app-icon-167x167.svg"],
    "app-icon-152x152.svg": dark["app-icon-152x152.svg"],
    "app-icon-76x76.svg": dark["app-icon-76x76.svg"],
    # Settings / Spotlight / Notification
    "app-icon-87x87.svg": dark["app-icon-87x87.svg"],
    "app-icon-80x80.svg": dark["app-icon-80x80.svg"],
    "app-icon-58x58.svg": dark["app-icon-58x58.svg"],
    "app-icon-40x40.svg": dark["app-icon-40x40.svg"],
    "app-icon-29x29.svg": dark["app-icon-29x29.svg"],
    "app-icon-20x20.svg": dark["app-icon-20x20.svg"],
    # Android
    "app-icon-adaptive-foreground.svg": dark["app-icon-adaptive-foreground.svg"],
}

for name, svg in app_icons.items():
    path = os.path.join(app_dir, name)
    with open(path, "w") as f:
        f.write(svg)
    print(f"Saved: {path}")

# ── Store & Social Graphics ──────────────────────────────────────────────────
store_dir = os.path.join(OUT_DIR, "store")
os.makedirs(store_dir, exist_ok=True)

store_icons = {
    "og-image.svg": fix_text_gap(dark["og-image.svg"]),
    "twitter-card.svg": fix_text_gap(dark["twitter-card.svg"]),
    "store-feature-graphic.svg": fix_text_gap(dark["store-feature-graphic.svg"]),
}

for name, svg in store_icons.items():
    path = os.path.join(store_dir, name)
    with open(path, "w") as f:
        f.write(svg)
    print(f"Saved: {path}")

# ── Splash Screens ───────────────────────────────────────────────────────────
splash_dir = os.path.join(OUT_DIR, "splash")
os.makedirs(splash_dir, exist_ok=True)

splash_screens = {
    "splash-iphone.svg": fix_text_gap(dark["splash-iphone.svg"]),
    "splash-android.svg": fix_text_gap(dark["splash-android.svg"]),
    "splash-ipad.svg": fix_text_gap(dark["splash-ipad.svg"]),
}

for name, svg in splash_screens.items():
    path = os.path.join(splash_dir, name)
    with open(path, "w") as f:
        f.write(svg)
    print(f"Saved: {path}")

for name, svg in saves.items():
    path = os.path.join(OUT_DIR, name)
    with open(path, "w") as f:
        f.write(svg)
    print(f"Saved: {path}")

print("Done!")
