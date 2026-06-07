"""Local web app handlers (zero dependencies, stdlib ``http.server``).

Pure functions (``render_form``, ``parse_form``, ``run_and_store``, ``build_result_page``) hold the
logic and are unit-tested directly; ``serve`` just wires them to an HTTP handler. Runs live in an
in-memory dict (the user opted to keep records in memory); the model profile is read from the
environment via ``build_gateway`` so a configured local Ollama is used automatically.
"""

from __future__ import annotations

import html
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ...inference import build_gateway
from ...service import EvidenceInput, run_investigation
from ..api import build_dashboard_data
from ..dashboard import render_dashboard

# In-memory run store (records kept in memory per the operator's choice).
RUNS: dict[str, object] = {}
_MAX_RUNS = 50


def _e(text) -> str:
    return html.escape(str(text), quote=True)


def parse_form(fields: dict[str, list[str]]) -> tuple[str, list[str], list[EvidenceInput]]:
    """Turn posted form fields into (question, candidates, evidence)."""
    question = (fields.get("question", [""])[0] or "").strip()
    candidates = [ln.strip() for ln in fields.get("candidates", [""])[0].splitlines() if ln.strip()]
    evidence: list[EvidenceInput] = []
    for line in fields.get("evidence", [""])[0].splitlines():
        line = line.strip()
        if not line:
            continue
        # format: "source | evidence text | supports#(optional, 1-based)"
        parts = [p.strip() for p in line.split("|")]
        source = parts[0] if len(parts) > 1 else "user"
        text = parts[1] if len(parts) > 1 else parts[0]
        supports = None
        if len(parts) > 2 and parts[2].lstrip("-").isdigit():
            supports = int(parts[2]) - 1  # humans count from 1
        evidence.append(EvidenceInput(text=text, source=source, supports=supports))
    return question, candidates, evidence


def run_and_store(question: str, candidates: list[str],
                  evidence: list[EvidenceInput]) -> str:
    """Run an investigation (using whatever model profile the env configures) and store it."""
    result = run_investigation(question=question, candidates=candidates, evidence=evidence,
                               gateway=build_gateway())
    run_id = result.investigation.investigation_id
    RUNS[run_id] = result
    while len(RUNS) > _MAX_RUNS:
        RUNS.pop(next(iter(RUNS)))
    return run_id


_BANNER = (
    '<div style="background:#0b0e16;border-bottom:1px solid #222c44;padding:10px 24px;'
    'font:13px system-ui;color:#8a96b0">'
    '<a href="/" style="color:#3ddc84;text-decoration:none">&larr; New investigation</a>'
    '&nbsp;·&nbsp; OSINTENAL — records kept in memory for this session</div>')


def build_result_page(run_id: str) -> str | None:
    result = RUNS.get(run_id)
    if result is None:
        return None
    page = render_dashboard(build_dashboard_data(result))
    return page.replace("<body>", "<body>\n" + _BANNER, 1)


def render_form(message: str = "") -> str:
    note = f'<p class="msg">{_e(message)}</p>' if message else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OSINTENAL — New investigation</title><style>{_FORM_CSS}</style></head>
<body>
<header><span class="logo">&#9678;</span> OSINTENAL
  <span class="muted">/ New investigation</span></header>
<main>
  {note}
  <form method="post" action="/investigate" class="card">
    <label>Question
      <input name="question" placeholder="What is the structure on the ridge?" required></label>
    <label>Competing answers <span class="muted">(one per line, 2+)</span>
      <textarea name="candidates" rows="4"
        placeholder="communications mast&#10;wind turbine&#10;water tower" required></textarea></label>
    <label>Evidence <span class="muted">(one per line: <code>source | text | supports#</code>;
        the trailing number is which answer it supports, counting from 1 — optional if a model
        is configured to judge relevance)</span>
      <textarea name="evidence" rows="7"
        placeholder="OpenStreetMap | node tagged man_made=mast at the coordinate | 1&#10;Wikidata | radio relay station entity nearby | 1&#10;Local news | residents call it 'the turbine' | 2"></textarea></label>
    <button type="submit">Investigate</button>
  </form>
  <p class="muted">Tip: set <code>OSINTENAL_INFERENCE_PROFILE=ollama</code> (and optionally
    <code>OSINTENAL_REASON_PROFILE=gemini</code>) before launching to have local/free models judge
    relevance, propose explanations, and critique. Without a model, tag evidence with a supports#.</p>
</main></body></html>"""


_FORM_CSS = """
:root{--bg:#0b0e16;--panel:#141b2d;--line:#222c44;--ink:#e6ecf7;--mut:#8a96b0;--accent:#3ddc84}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#16203a 0,var(--bg) 60%);
color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:16px 24px;border-bottom:1px solid var(--line);font-weight:700}
.logo{color:var(--accent)} .muted{color:var(--mut);font-weight:400;font-size:13px}
main{max-width:780px;margin:0 auto;padding:24px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px;
display:flex;flex-direction:column;gap:18px}
label{display:flex;flex-direction:column;gap:6px;font-weight:600;font-size:14px}
input,textarea{background:#0a0f1c;border:1px solid var(--line);border-radius:9px;color:var(--ink);
padding:11px 12px;font:14px/1.5 system-ui;resize:vertical}
input:focus,textarea:focus{outline:none;border-color:#3a7}
code{font-family:ui-monospace,Menlo,Consolas,monospace;color:#bcd}
button{background:linear-gradient(160deg,#3ddc84,#2bb36a);color:#06121f;border:0;border-radius:10px;
padding:13px;font-size:15px;font-weight:800;cursor:pointer}
.msg{background:#3a2330;border:1px solid #5a2a3a;color:#ffb4c4;padding:10px 12px;border-radius:8px}
"""


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # quiet by default
        pass

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/new"):
            self._send(200, render_form())
        elif path == "/health":
            self._send(200, "ok", "text/plain")
        elif path.startswith("/run/"):
            page = build_result_page(path[len("/run/"):])
            self._send(200, page) if page else self._send(404, render_form("Run not found."))
        else:
            self._send(404, render_form("Not found."))

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/investigate":
            self._send(404, render_form("Not found."))
            return
        length = int(self.headers.get("Content-Length", 0))
        fields = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        question, candidates, evidence = parse_form(fields)
        if not question or len(candidates) < 1:
            self._send(400, render_form("Please provide a question and at least two answers."))
            return
        run_id = run_and_store(question, candidates, evidence)
        self.send_response(303)
        self.send_header("Location", f"/run/{run_id}")
        self.end_headers()


def serve(port: int = 8765, host: str = "127.0.0.1") -> None:
    server = ThreadingHTTPServer((host, port), _Handler)
    print(f"OSINTENAL web app on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        server.shutdown()
