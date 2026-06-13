"""Author the committed infra/threat-intel demo cassette (doc 05 §6).

Recorded responses for Shodan InternetDB (an IP), URLScan.io search, and AlienVault OTX (a
domain), so ``osintinel intel`` runs the free modern adapters fully offline. Regenerate:
``python -m osintinel.adapters._cassettes.build_intel``.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..infrastructure.dns import DnsAdapter
from ..infrastructure.ripestat import AsnAdapter
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

    # --- DNS over HTTPS (Google) --------------------------------------------
    dns = DnsAdapter.__new__(DnsAdapter)
    dns_answers = {
        "A": [{"name": f"{DOMAIN}.", "type": 1, "TTL": 300, "data": IP}],
        "AAAA": [],
        "MX": [{"name": f"{DOMAIN}.", "type": 15, "TTL": 300, "data": f"10 mail.{DOMAIN}."}],
        "NS": [{"name": f"{DOMAIN}.", "type": 2, "TTL": 3600, "data": f"ns1.{DOMAIN}."}],
        "TXT": [{"name": f"{DOMAIN}.", "type": 16, "TTL": 300, "data": "v=spf1 -all"}],
    }
    for rtype, ans in dns_answers.items():
        entries[request_key("GET", dns.API, {"name": DOMAIN, "type": rtype})] = {
            "url": dns.API, "text": json.dumps({"Status": 0, "Answer": ans})}

    # --- RIPEstat ASN / network (fictional AS for the demo entity) -----------
    asn = AsnAdapter.__new__(AsnAdapter)
    entries[request_key("GET", asn.NETWORK_INFO, {"resource": IP})] = {
        "url": asn.NETWORK_INFO,
        "text": json.dumps({"data": {"asns": ["64500"], "prefix": "203.0.113.0/24"}})}
    entries[request_key("GET", asn.AS_OVERVIEW, {"resource": "AS64500"})] = {
        "url": asn.AS_OVERVIEW,
        "text": json.dumps({"data": {"holder": "WINDREACH-AS, Example"}})}

    path = HERE / "intel.json"
    path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path.name} ({len(entries)} entries)")


if __name__ == "__main__":
    build()
