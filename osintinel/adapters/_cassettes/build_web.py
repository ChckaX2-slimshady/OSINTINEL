"""Author the committed web-research demo cassette (doc 05 §6).

A recorded DuckDuckGo-lite query returning three results on three *distinct domains*, plus each
page's fetched HTML — so ``osintinel research`` runs fully offline and demonstrates autonomous
web evidence reaching independent-source corroboration. Regenerate:
``python -m osintinel.adapters._cassettes.build_web``.
"""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

from ..transport import request_key
from ..web.search import WebSearchAdapter

HERE = Path(__file__).parent
QUERY = "Bullington ridge communications mast"

RESULTS = [
    ("https://windreach-telecom.example/bullington", "WindReach Telecom — Bullington mast"),
    ("https://hampshire-news.example/ridge-mast", "Hampshire News: the ridge mast explained"),
    ("https://heritage-survey.example/bullington-down", "Heritage survey: Bullington Down"),
]
PAGES = {
    "https://windreach-telecom.example/bullington":
        "<html><body><h1>Bullington communications mast</h1><p>WindReach Telecom operates a "
        "lattice communications mast on Bullington ridge providing radio relay and microwave "
        "backhaul. It is a telecom mast, not a wind turbine.</p></body></html>",
    "https://hampshire-news.example/ridge-mast":
        "<html><body><article>Residents confirmed the ridge structure is a communications mast "
        "installed for mobile and emergency-services coverage near Bullington.</article></body></html>",
    "https://heritage-survey.example/bullington-down":
        "<html><body><p>The Bullington Down survey records a tall mast on the chalk ridge; "
        "the antenna and relay equipment indicate a communications installation.</p></body></html>",
}


def build() -> None:
    a = WebSearchAdapter.__new__(WebSearchAdapter)
    entries: dict[str, dict] = {}

    # DuckDuckGo-lite search result page (matches the adapter's result-link parser)
    links = "".join(f'<a class="result-link" href="{url}">{title}</a>' for url, title in RESULTS)
    ddg_html = f"<html><body>{links}</body></html>"
    body = "q=" + urllib.parse.quote(QUERY)
    entries[request_key("POST", a.DDG_LITE, None, body)] = {"url": a.DDG_LITE, "text": ddg_html}

    # each fetched page
    for url, html_text in PAGES.items():
        entries[request_key("GET", url, None)] = {"url": url, "text": html_text}

    path = HERE / "web.json"
    path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path.name} ({len(entries)} entries)")


if __name__ == "__main__":
    build()
