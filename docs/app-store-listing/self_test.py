#!/usr/bin/env python3
"""Self-test App Store listing copy + asset dimensions. Exit 1 on failure."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LISTING = (ROOT / "LISTING.md").read_text()
TESTING = (ROOT / "TESTING.md").read_text()

# Partner Dashboard common limits (English fields).
LIMITS = {
    "subtitle": 70,
    "introduction": 100,
    "feature": 80,
}

FORBIDDEN = re.compile(
    r"\b(best|only|first|#1|number one|guarantee[sd]?|guarantees)\b",
    re.I,
)
# Allowed disclaimer in details.
ALLOWED_GUARANTEE = re.compile(r"does not guarantee", re.I)

PRICING_MARKERS = ("$14.99", "$39", "20 generate", "150 generate", "400 generate")


def fence(md: str, heading: str) -> str:
    """Return first fenced block after a heading substring."""
    idx = md.lower().find(heading.lower())
    if idx < 0:
        raise SystemExit(f"missing heading containing: {heading}")
    rest = md[idx:]
    m = re.search(r"```\n(.*?)```", rest, re.S)
    if not m:
        raise SystemExit(f"missing fenced paste block after: {heading}")
    return m.group(1).strip()


def sips_size(path: Path) -> tuple[int, int]:
    out = subprocess.check_output(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
        text=True,
    )
    w = int(re.search(r"pixelWidth:\s+(\d+)", out).group(1))
    h = int(re.search(r"pixelHeight:\s+(\d+)", out).group(1))
    return w, h


def main() -> int:
    errors: list[str] = []

    subtitle = fence(LISTING, "### Subtitle")
    intro = fence(LISTING, "### App introduction")
    details = fence(LISTING, "### App details")
    features = [ln for ln in fence(LISTING, "### Features").splitlines() if ln.strip()]
    pricing = fence(LISTING, "### Pricing details")

    print(f"subtitle {len(subtitle)}/{LIMITS['subtitle']}: {subtitle}")
    print(f"introduction {len(intro)}/{LIMITS['introduction']}: {intro}")
    print(f"details {len(details)} chars")
    for i, f in enumerate(features, 1):
        print(f"feature {i} {len(f)}/{LIMITS['feature']}: {f}")

    if len(subtitle) > LIMITS["subtitle"]:
        errors.append(f"subtitle {len(subtitle)} > {LIMITS['subtitle']}")
    if len(intro) > LIMITS["introduction"]:
        errors.append(f"introduction {len(intro)} > {LIMITS['introduction']}")
    if len(details) > 500:
        errors.append(f"details {len(details)} > 500")
    if not (3 <= len(features) <= 5):
        errors.append(f"need 3–5 features, got {len(features)}")
    for f in features:
        if len(f) > LIMITS["feature"]:
            errors.append(f"feature too long ({len(f)}): {f}")

    marketing = "\n".join([subtitle, intro, details, *features])
    for m in FORBIDDEN.finditer(marketing):
        word = m.group(0)
        window = marketing[max(0, m.start() - 24) : m.end() + 24]
        if word.lower().startswith("guarantee") and ALLOWED_GUARANTEE.search(window):
            continue
        errors.append(f"forbidden marketing word {word!r} in: {window!r}")

    for token in PRICING_MARKERS:
        if token.lower() in marketing.lower():
            errors.append(f"price/quota {token!r} leaked outside Pricing details")

    for token in ("$14.99", "$39", "Free:"):
        if token not in pricing:
            errors.append(f"pricing details missing {token!r}")

    if "does not guarantee Google Merchant Center approval" not in details:
        errors.append("details must disclaim GMC approval")

    if "https://deltfu.com/api/privacy" not in LISTING:
        errors.append("privacy URL missing")
    for scope in ("read_products", "write_products", "read_legal_policies"):
        if scope not in LISTING:
            errors.append(f"scope {scope!r} missing from LISTING")
    if "write_products" not in TESTING:
        errors.append("write_products scope note missing from TESTING")
    if "Opt out" not in LISTING:
        errors.append("protected customer data opt-out missing")

    if "no extra AdFeed username" not in TESTING:
        errors.append("testing instructions missing no-extra-login note")
    if "Switch to Starter" not in TESTING:
        errors.append("testing instructions missing billing step")
    if "Missing size" not in TESTING and "Needs size" not in TESTING:
        errors.append("testing instructions missing size-fix step")
    if "do not invent" not in TESTING.lower() and "fake barcode" not in TESTING.lower():
        errors.append("testing instructions must forbid fake GTIN")

    icon = ROOT / "icon-1200.png"
    if not icon.exists():
        errors.append("icon-1200.png missing")
    else:
        w, h = sips_size(icon)
        print(f"icon {w}x{h}")
        if (w, h) != (1200, 1200):
            errors.append(f"icon must be 1200x1200, got {w}x{h}")
        kind = subprocess.check_output(["file", str(icon)], text=True)
        if "PNG" not in kind:
            errors.append(f"icon not PNG: {kind.strip()}")

    shot_dir = ROOT / "screenshots"
    expected = [
        "01-confirm-brand.png",
        "02-product-list.png",
        "03-fix-size.png",
        "04-copy-url.png",
        "05-ad-image.png",
    ]
    for name in expected:
        path = shot_dir / name
        if not path.exists():
            errors.append(f"screenshot missing: {name}")
            continue
        w, h = sips_size(path)
        print(f"{name} {w}x{h}")
        if (w, h) != (1600, 900):
            errors.append(f"{name} must be 1600x900, got {w}x{h}")

    video = ROOT / "screencast" / "adfeed-ai-screencast.mp4"
    if not video.exists():
        errors.append("screencast mp4 missing")
    else:
        probe = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ],
            text=True,
        ).strip()
        dur = float(probe)
        print(f"screencast duration {dur:.1f}s")
        if dur < 55 or dur > 95:
            errors.append(f"screencast should be ~60–90s, got {dur:.1f}s")

    # Listing screenshot HTML must not include dollar prices.
    for html in (ROOT / "scenes").glob("0[1-5]-*.html"):
        text = html.read_text()
        if re.search(r"\$\d", text):
            errors.append(f"price in listing scene {html.name}")

    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
