#!/usr/bin/env python3
"""Render B1 brand assets by screenshotting React components in brand-assets.html."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO   = Path(__file__).resolve().parent.parent
PUBLIC = REPO / "src/web/frontend/public"
CHROME = os.environ.get("CHROME_EXECUTABLE")
HTML   = (REPO / "scripts/brand-assets.html").read_text()


def run():
    with sync_playwright() as p:
        launch_kwargs = {"headless": False}
        if CHROME:
            launch_kwargs["executable_path"] = CHROME
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page(
            viewport={"width": 1400, "height": 2400},
            device_scale_factor=1,
        )
        # networkidle waits for CDN resources (React, Babel, Google Fonts) to finish
        page.set_content(HTML, wait_until="networkidle")
        page.evaluate("() => document.fonts.ready")

        def shot(selector, path):
            page.locator(selector).screenshot(path=str(path))
            print(f"Saved {path}")

        def shot_transparent(selector, path):
            page.locator(selector).screenshot(path=str(path), omit_background=True)
            print(f"Saved {path}")

        # App icons and banners — opaque dark background, no transparent corners needed
        shot("#icon-192",    PUBLIC / "icon-192.png")
        shot("#icon-512",    PUBLIC / "icon-512.png")
        shot("#icon-180",    PUBLIC / "apple-touch-icon.png")
        shot("#banner-1280", REPO   / "cashe-banner.png")
        shot("#banner-1200", PUBLIC / "og-image.png")
        shot("#banner-640",  REPO   / "cashe-telegram-banner.png")

        # Favicons — transparent corners so rounded rect shows cleanly in browser tabs
        page.evaluate("() => document.body.style.background = 'transparent'")
        shot_transparent("#favicon-32",  PUBLIC / "favicon-32.png")
        shot_transparent("#favicon-192", PUBLIC / "favicon-192.png")
        shot_transparent("#favicon-512", PUBLIC / "favicon-512.png")

        browser.close()


run()
