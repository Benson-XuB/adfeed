#!/usr/bin/env python3
"""Build captioned screencast HTML from listing scenes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCENES = ROOT / "scenes"
OUT = SCENES / "video"
OUT.mkdir(exist_ok=True)

SLIDES = [
    ("01-confirm-brand.html", "After install, App Home opens in Admin. No extra login."),
    ("02-product-list.html", "Confirm your ad brand, select products, then generate."),
    ("03-fix-size.html", "Missing size or color? Add it here, or edit in Shopify."),
    ("04-copy-url.html", "Copy the persistent Google US feed URL into Merchant Center."),
    ("05-ad-image.html", "Pick an ad image without changing your storefront."),
    ("06-change-plan.html", "Change plan in the app, then approve the Shopify charge."),
]


def main() -> None:
    css = (SCENES / "app-home.css").read_text()
    for name, caption in SLIDES:
        html = (SCENES / name).read_text()
        html = html.replace('href="app-home.css"', 'href="../app-home.css"', 1)
        html = html.replace('class="page"', 'class="page with-caption"', 1)
        html = html.replace(
            "</body>",
            f'<div class="caption">{caption}</div>\n</body>',
            1,
        )
        (OUT / name).write_text(html)
    print(f"wrote {len(SLIDES)} captioned scenes in {OUT}")


if __name__ == "__main__":
    main()
