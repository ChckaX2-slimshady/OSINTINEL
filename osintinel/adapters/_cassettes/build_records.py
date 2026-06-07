"""Author the committed public-records demo cassette (doc 05 §6).

Recorded OpenCorporates / SEC EDGAR / GLEIF responses for one company so ``osintinel records``
runs the free records adapters offline. Regenerate:
``python -m osintinel.adapters._cassettes.build_records``.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..records.gleif import GLEIFAdapter
from ..records.opencorporates import OpenCorporatesAdapter
from ..records.sec_edgar import SECEdgarAdapter
from ..transport import request_key

HERE = Path(__file__).parent
COMPANY = "WindReach Telecom"


def build() -> None:
    entries: dict[str, dict] = {}

    oc = OpenCorporatesAdapter.__new__(OpenCorporatesAdapter)
    oc_data = {"results": {"companies": [
        {"company": {"name": "WindReach Telecom Ltd", "jurisdiction_code": "gb",
                     "company_number": "12345678", "current_status": "Active"}},
        {"company": {"name": "WindReach Telecom Holdings", "jurisdiction_code": "gb",
                     "company_number": "87654321", "current_status": "Active"}}]}}
    entries[request_key("GET", oc.API, {"q": COMPANY, "per_page": 10}, None)] = {
        "url": oc.API, "text": json.dumps(oc_data)}

    se = SECEdgarAdapter.__new__(SECEdgarAdapter)
    se_data = {"hits": {"hits": [
        {"_id": "f1", "_source": {"display_names": ["WindReach Telecom Ltd (CIK 0001234567)"],
                                  "file_type": "20-F", "file_date": "2024-04-30"}}]}}
    entries[request_key("GET", se.API, {"q": COMPANY}, None)] = {
        "url": se.API, "text": json.dumps(se_data)}

    gl = GLEIFAdapter.__new__(GLEIFAdapter)
    gl_data = {"data": [{"id": "5493001",
                         "attributes": {"lei": "549300EXAMPLE0000001",
                                        "entity": {"legalName": {"name": "WindReach Telecom Ltd"},
                                                   "legalAddress": {"country": "GB"}},
                                        "registration": {"status": "ISSUED"}}}]}
    entries[request_key("GET", gl.API,
                        {"filter[entity.legalName]": COMPANY, "page[size]": 10}, None)] = {
        "url": gl.API, "text": json.dumps(gl_data)}

    path = HERE / "records.json"
    path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path.name} ({len(entries)} entries)")


if __name__ == "__main__":
    build()
