"""Author the committed infra/threat-intel demo cassette (doc 05 §6).

Recorded responses for Shodan InternetDB (an IP), URLScan.io search, and AlienVault OTX (a
domain), so ``osintinel intel`` runs the free modern adapters fully offline. Regenerate:
``python -m osintinel.adapters._cassettes.build_intel``.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..infrastructure.shodan_internetdb import ShodanInternetDBAdapter
from ..infrastructure.urlscan import UrlscanAdapter
from ..threat.otx import OTXAdapter
from ..transport import request_key

HERE = Path(__file__).parent
IP = "203.0.113.10"            # TEST-NET-3 documentation address
DOMAIN = "windreach-telecom.example"


def build() -> None:
    entries: dict[str, dict] = {}

    # --- Shodan InternetDB ---------------------------------------------------
    sh = ShodanInternetDBAdapter.__new__(ShodanInternetDBAdapter)
    shodan = {"ip": IP, "ports": [22, 80, 443], "cpes": ["cpe:/a:nginx:nginx"],
              "hostnames": [f"mast.{DOMAIN}"], "tags": ["self-signed"],
              "vulns": ["CVE-2023-44487"]}
    entries[request_key("GET", f"{sh.API}/{IP}", None, None)] = {
        "url": f"{sh.API}/{IP}", "text": json.dumps(shodan)}

    # --- URLScan.io search ---------------------------------------------------
    us = UrlscanAdapter.__new__(UrlscanAdapter)
    urlscan = {"results": [
        {"task": {"url": f"https://{DOMAIN}/"},
         "page": {"url": f"https://{DOMAIN}/", "asnname": "EXAMPLE-AS"}},
        {"task": {"url": f"https://login.{DOMAIN}/"},
         "page": {"url": f"https://login.{DOMAIN}/", "asnname": "EXAMPLE-AS"}},
    ]}
    entries[request_key("GET", us.API, {"q": f"domain:{DOMAIN}", "size": 10}, None)] = {
        "url": us.API, "text": json.dumps(urlscan)}

    # --- AlienVault OTX ------------------------------------------------------
    otx = OTXAdapter.__new__(OTXAdapter)
    otx_data = {"pulse_info": {"count": 1, "pulses": [
        {"name": "Telecom infrastructure scanning campaign", "tags": ["scanning", "telecom"]}]}}
    otx_url = f"{otx.API}/domain/{DOMAIN}/general"
    entries[request_key("GET", otx_url, None, None)] = {
        "url": otx_url, "text": json.dumps({"indicator": DOMAIN, "type": "domain",
                                            "data": otx_data}) and json.dumps(otx_data)}

    path = HERE / "intel.json"
    path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path.name} ({len(entries)} entries)")


if __name__ == "__main__":
    build()
