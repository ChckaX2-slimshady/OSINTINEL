"""Author the committed demo cassettes (doc 05 §6).

These are hand-crafted, realistic recordings for a small coherent investigation (a suspected
telecom mast near Bullington, Hampshire, and the domain ``windreach.example``). Keys are
computed with the real :func:`osintinel.adapters.transport.request_key`, so the committed JSON
always matches what the adapters request at replay time.

Run ``python -m osintinel.adapters._cassettes.build_demo`` to regenerate. Live recordings (an
environment with real egress) would replace these via ``OSINTINEL_RECORD=1``; the offline
cassettes keep CI and the demo deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..archives.wayback import WaybackAdapter
from ..archives.wikidata import WikidataAdapter
from ..geospatial.nominatim import NominatimAdapter
from ..geospatial.overpass import OverpassAdapter
from ..infrastructure.cert_transparency import CertTransparencyAdapter
from ..transport import request_key

HERE = Path(__file__).parent

SNAP_HTML = (
    "<html><head><title>WindReach Telecom — Mast Hosting &amp; Backhaul</title></head>"
    "<body><h1>WindReach Telecom</h1><p>Operator of the Bullington communications mast "
    "(grid ref SU 483 414). Services: radio relay, microwave backhaul, colocation.</p>"
    "<footer>Captured 2018.</footer></body></html>"
)


def _entry(url: str, text: str) -> dict:
    return {"url": url, "text": text}


def build() -> None:
    cassettes: dict[str, dict[str, dict]] = {}

    # --- Nominatim (geo.geocode + geo.reverse_geocode) -----------------------
    nomi = NominatimAdapter.__new__(NominatimAdapter)
    geocode_resp = [{
        "place_id": 123, "osm_type": "node", "osm_id": 1001,
        "lat": "51.01530", "lon": "-1.32530",
        "display_name": "Telecom mast, Bullington, Hampshire, England",
        "category": "man_made", "type": "mast", "importance": 0.21,
    }]
    reverse_resp = {
        "place_id": 456, "osm_type": "node", "osm_id": 1001,
        "lat": "51.0153", "lon": "-1.3253",
        "display_name": "Bullington, Hampshire, England",
        "category": "place", "type": "hamlet",
    }
    cassettes["nominatim"] = {
        request_key("GET", nomi.SEARCH_URL, {
            "q": "Bullington telecom mast", "format": "jsonv2", "limit": 5}):
            _entry(nomi.SEARCH_URL, json.dumps(geocode_resp)),
        request_key("GET", nomi.REVERSE_URL, {
            "lat": 51.0153, "lon": -1.3253, "format": "jsonv2"}):
            _entry(nomi.REVERSE_URL, json.dumps(reverse_resp)),
    }

    # --- Overpass (geo.features) --------------------------------------------
    over = OverpassAdapter.__new__(OverpassAdapter)
    ql = over._ql(51.0153, -1.3253, 500, "man_made", None)
    overpass_resp = {"elements": [
        {"type": "node", "id": 1001, "lat": 51.0153, "lon": -1.3253,
         "tags": {"man_made": "mast", "operator": "WindReach Telecom", "name": "Bullington Mast"}},
        {"type": "way", "id": 2002, "center": {"lat": 51.0155, "lon": -1.3250},
         "tags": {"man_made": "tower", "tower:type": "communication"}},
    ]}
    cassettes["overpass"] = {
        request_key("POST", over.API_URL, None, "data=" + ql):
            _entry(over.API_URL, json.dumps(overpass_resp)),
    }

    # --- Wayback (archive.timemap + archive.snapshot) -----------------------
    way = WaybackAdapter.__new__(WaybackAdapter)
    cdx_resp = [
        ["timestamp", "original", "digest", "statuscode"],
        ["20180512093000", "http://windreach.example/", "ABCD1234", "200"],
        ["20200101000000", "http://windreach.example/about", "EFGH5678", "200"],
    ]
    snap_url = f"{way.SNAPSHOT_URL}/20180512093000id_/http://windreach.example/"
    cassettes["wayback"] = {
        request_key("GET", way.CDX_URL, {
            "url": "windreach.example", "output": "json", "limit": 10,
            "fl": "timestamp,original,digest,statuscode"}):
            _entry(way.CDX_URL, json.dumps(cdx_resp)),
        request_key("GET", snap_url, None):
            _entry(snap_url, SNAP_HTML),
    }

    # --- Wikidata (reference.encyclopedic) ----------------------------------
    wd = WikidataAdapter.__new__(WikidataAdapter)
    qid = "Q12345"
    entity_resp = {"entities": {qid: {
        "labels": {"en": {"value": "Bullington radio mast"}},
        "descriptions": {"en": {"value": "telecommunications mast in Hampshire, England"}},
        "claims": {"P625": [{"mainsnak": {"datavalue": {"value": {
            "latitude": 51.0153, "longitude": -1.3253}}}}]},
    }}}
    cassettes["wikidata"] = {
        request_key("GET", f"{wd.ENTITY_URL}/{qid}.json", None):
            _entry(f"{wd.ENTITY_URL}/{qid}.json", json.dumps(entity_resp)),
    }

    # --- crt.sh (infra.certs) -----------------------------------------------
    ct = CertTransparencyAdapter.__new__(CertTransparencyAdapter)
    crt_resp = [
        {"id": 1, "name_value": "windreach.example\nmail.windreach.example",
         "issuer_name": "C=US, O=Let's Encrypt", "not_before": "2019-03-01T00:00:00"},
        {"id": 2, "name_value": "*.windreach.example",
         "issuer_name": "C=US, O=Let's Encrypt", "not_before": "2020-06-15T00:00:00"},
    ]
    cassettes["crtsh"] = {
        request_key("GET", ct.API_URL, {"q": "windreach.example", "output": "json"}):
            _entry(ct.API_URL, json.dumps(crt_resp)),
    }

    for name, entries in cassettes.items():
        path = HERE / f"{name}.json"
        path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(HERE.parent.parent.parent)} ({len(entries)} entries)")


if __name__ == "__main__":
    build()
