#!/usr/bin/env python3
"""Render B1 brand assets via Chrome — fonts embedded, CSS verbatim from B1 mockup."""

import base64
from playwright.sync_api import sync_playwright

REPO   = "/Users/xinweichong/personal/expense-tracker"
PUBLIC = f"{REPO}/src/web/frontend/public"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ── Embed fonts as base64 (prevents Google Fonts network dependency) ──────────

def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

PJS_800_B64 = b64("/tmp/package/files/plus-jakarta-sans-latin-800-normal.woff")
JBM_600_B64 = b64("/tmp/jbm/package/files/jetbrains-mono-latin-600-normal.woff")

FONT_FACE = f"""
@font-face {{
  font-family: 'Plus Jakarta Sans';
  font-weight: 800;
  font-style: normal;
  src: url('data:font/woff;base64,{PJS_800_B64}') format('woff');
}}
@font-face {{
  font-family: 'JetBrains Mono';
  font-weight: 600;
  font-style: normal;
  src: url('data:font/woff;base64,{JBM_600_B64}') format('woff');
}}
"""

# ── CSS — copied verbatim from B1 HTML mockup, plus font-weight: 800 fix ─────
# (Plus Jakarta Sans max available weight is 800; requesting 900 in mockup
#  falls back to 800 anyway — we lock it explicitly here)

CSS = f"""
{FONT_FACE}

*  {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg:   #0B0B14;
  --teal: #00D4AA;
  --warm: linear-gradient(135deg, #D97706 0%, #EA580C 50%, #DC2626 100%);
  --fd:   'Plus Jakarta Sans', sans-serif;
  --fm:   'JetBrains Mono', monospace;
}}

.cool {{ color: var(--teal); }}
.cash, .cash-text {{
  background: var(--warm);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}}

/* Verbatim from mockup — font-weight 800 (max available) */
.brand, .wordmark {{
  display: inline-flex;
  align-items: baseline;
  justify-content: center;
  font-family: var(--fd);
  font-weight: 800;
  letter-spacing: -.068em;
  line-height: .9;
  white-space: nowrap;
}}
.wordmark {{
  position: relative;
  z-index: 1;
  transform: translateX(-1px);
}}
.wordmark.hero {{ font-size: 38px; }}
.wordmark.mid  {{ font-size: 34px; }}

.logo-stack {{
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  transform: translateY(-1px);
}}
.tagline {{
  color: rgba(238,234,245,.68);
  font-family: var(--fm);
  font-size: 8.5px;
  font-weight: 600;
  letter-spacing: .24em;
  line-height: 1;
  text-align: center;
  text-transform: uppercase;
  white-space: nowrap;
}}

.dollar {{
  position: relative;
  z-index: 1;
  display: block;
  font-family: var(--fd);
  font-size: 84px;
  font-weight: 800;
  letter-spacing: -.05em;
  line-height: .9;
  transform: translate(-1px,-1px);
}}

/* Verbatim from mockup */
.icon {{
  position: relative;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 25.5%;
  box-shadow: 0 18px 40px -30px rgba(0,212,170,.85);
  isolation: isolate;
}}
.icon::after {{
  content: "";
  position: absolute;
  inset: 1px;
  border-radius: inherit;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.11), inset 0 -20px 36px rgba(0,0,0,.12);
  pointer-events: none;
}}
.wash-b {{
  background:
    linear-gradient(135deg,
      rgba(0,212,170,.38)  0%,
      rgba(11,11,20,.94)  35%,
      rgba(11,11,20,.98)  58%,
      rgba(234,88,12,.34) 82%,
      rgba(220,38,38,.3) 100%),
    #0B0B14;
  border: 1px solid #2A2A3F;
}}
"""


# ── HTML builders ─────────────────────────────────────────────────────────────

def page(w, h, body):
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
{CSS}
html, body {{ width: {w}px; height: {h}px; overflow: hidden; background: var(--bg); }}
body {{ display: flex; align-items: center; justify-content: center; }}
</style></head>
<body>{body}</body></html>"""


def icon_wordmark_html(size):
    """B2: ca$he wordmark on B1 wash — app icons.
    Structure mirrors CasheBrandLockup React component exactly:
      outer  = inline-flex, align+justify center, overflow hidden
      inner  = flex column, align-items center  ← the true centering layer
      wm     = inline-flex, align-items baseline, translateX(-1px) optical shift
    Font ratio 34/116 matches the React component's wmSize formula.
    """
    wm_px = round(size * 34 / 116)
    gap   = round(size * 8 / 116)
    return page(size, size, f"""
      <div style="
        width:{size}px; height:{size}px;
        background: linear-gradient(135deg, rgba(0,212,170,.38) 0%, rgba(11,11,20,.94) 35%, rgba(11,11,20,.98) 58%, rgba(234,88,12,.34) 82%, rgba(220,38,38,.3) 100%), #0B0B14;
        border: 1px solid #2A2A3F;
        border-radius: 25.5%;
        box-shadow: 0 18px 40px -30px rgba(0,212,170,.85);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
      ">
        <div style="
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          transform: translateY(-1px);
        ">
          <span style="
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-weight: 800;
            letter-spacing: -0.068em;
            line-height: 1.5;
            font-size: {wm_px}px;
            display: inline-flex;
            align-items: baseline;
            transform: translateX(-{round(wm_px * 0.03)}px);
          ">
            <span class="cool">ca</span><span class="cash" style="margin:0 -0.033em 0 0;">$</span><span class="cool">he</span>
          </span>
        </div>
      </div>""")


def icon_dollar_html(size):
    """B3: $ only on B1 wash — favicon icons.
    Uses flex centering (not CSS grid) to match React component centering behaviour.
    letter-spacing: 0 removes trailing space that shifts single-char rightward.
    Font size 0.55× gives ~22% breathing room per side.
    """
    dol_px = round(size * 0.55)
    return page(size, size, f"""
      <div style="
        width:{size}px; height:{size}px;
        background: linear-gradient(135deg, rgba(0,212,170,.38) 0%, rgba(11,11,20,.94) 35%, rgba(11,11,20,.98) 58%, rgba(234,88,12,.34) 82%, rgba(220,38,38,.3) 100%), #0B0B14;
        border: 1px solid #2A2A3F;
        border-radius: 25.5%;
        box-shadow: 0 18px 40px -30px rgba(0,212,170,.85);
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
      ">
        <span style="
          font-family: 'Plus Jakarta Sans', sans-serif;
          font-weight: 800;
          font-size: {dol_px}px;
          line-height: 1;
          letter-spacing: 0;
          background: linear-gradient(135deg, #D97706 0%, #EA580C 50%, #DC2626 100%);
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
          color: transparent;
        ">$</span>
      </div>""")


def banner_html(w, h, wm_px, tl_px, gap_px):
    """B1-style banner: ca$he + CASH, CAUGHT. on B1 wash."""
    return page(w, h, f"""
      <div style="
        width:{w}px; height:{h}px;
        background:
          linear-gradient(135deg,
            rgba(0,212,170,.38)  0%,
            rgba(11,11,20,.94)  35%,
            rgba(11,11,20,.98)  58%,
            rgba(234,88,12,.34) 82%,
            rgba(220,38,38,.3) 100%),
          #0B0B14;
        display:flex; flex-direction:column;
        align-items:center; justify-content:center; gap:{gap_px}px;">
        <div class="wordmark" style="font-size:{wm_px}px;transform:translateX(0);justify-content:center;width:100%;">
          <span class="cool">ca</span><span class="cash" style="margin:0 -0.033em 0 0;">$</span><span class="cool">he</span>
        </div>
        <div class="tagline" style="font-size:{tl_px}px;">CASH, CAUGHT.</div>
      </div>""")


# ── Render ────────────────────────────────────────────────────────────────────

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=False)

        def shot(html, w, h, path):
            page_ = browser.new_page(viewport={"width": w, "height": h},
                                     device_scale_factor=1)
            page_.set_content(html, wait_until="load")
            # Wait for fonts to be ready before screenshotting
            page_.evaluate("() => document.fonts.ready")
            page_.screenshot(path=path,
                             clip={"x": 0, "y": 0, "width": w, "height": h})
            page_.close()
            print(f"Saved {path}  ({w}×{h})")

        # Banners — proportions from original working Pillow render
        shot(banner_html(1280, 420, 160, 20, 26), 1280, 420, f"{REPO}/cashe-banner.png")
        shot(banner_html(1200, 630, 200, 26, 34), 1200, 630, f"{PUBLIC}/og-image.png")

        # App icons — B2: ca$he wordmark only
        shot(icon_wordmark_html(192), 192, 192, f"{PUBLIC}/icon-192.png")
        shot(icon_wordmark_html(512), 512, 512, f"{PUBLIC}/icon-512.png")
        shot(icon_wordmark_html(180), 180, 180, f"{PUBLIC}/apple-touch-icon.png")

        # Favicon icons — B3: $ only (PNG, no SVG — Chrome render is the canonical source)
        shot(icon_dollar_html(32),  32,  32,  f"{PUBLIC}/favicon-32.png")
        shot(icon_dollar_html(192), 192, 192, f"{PUBLIC}/favicon-192.png")
        shot(icon_dollar_html(512), 512, 512, f"{PUBLIC}/favicon-512.png")

        browser.close()


run()
