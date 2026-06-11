"""OSINTINEL Web — the full console (zero dependencies, stdlib ``http.server``).

One responsive, mobile-friendly app that puts the whole engine in a browser: a complete
investigation form (question · competing answers · evidence · **Autonomous** web research · **photo**
upload · model profile + per-tier overrides), the rich dashboard result with ranked insights and
tools/sources used, and a **History** of persisted runs. Reach it from a phone by serving with
``--host 0.0.0.0`` and opening ``http://<machine-ip>:8765``.

Pure functions hold the logic and are unit-tested directly; ``serve`` wires them to an HTTP
handler. Runs render from an in-memory store; a compact, evidence-free summary is also persisted to
``~/.osintinel/runs`` (``OSINTINEL_NO_PERSIST=1`` to disable).
"""

from __future__ import annotations

import datetime as _dt
import html
import os
import urllib.parse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ...inference import PROFILES, build_gateway, gateway_status
from ...service import (
    EvidenceInput,
    InvestigationSummary,
    RunStore,
    autoresearch_investigation,
    run_investigation,
)
from ...service.photo import analyze_photo, osm_url
from ..api import build_dashboard_data
from ..dashboard import render_dashboard

RUNS: dict[str, object] = {}
RUN_MODELS: dict[str, str] = {}
_STORE = RunStore()
_MAX_RUNS = 50

# advanced per-tier / endpoint overrides → the env the gateway already reads
_OVERRIDE_ENV = {
    "reason_model": "OSINTINEL_REASON_MODEL", "small_model": "OSINTINEL_SMALL_MODEL",
    "task_model": "OSINTINEL_TASK_MODEL", "embed_model": "OSINTINEL_EMBED_MODEL",
    "reason_profile": "OSINTINEL_REASON_PROFILE", "skeptic_profile": "OSINTINEL_SKEPTIC_PROFILE",
    "base_url": "OSINTINEL_OPENAI_BASE_URL", "key_env": "OSINTINEL_OPENAI_KEY_ENV",
}
_ADVANCED = [("reason_model", "reason model"), ("small_model", "small model"),
             ("task_model", "task model"), ("embed_model", "embed model"),
             ("reason_profile", "reason→profile"), ("skeptic_profile", "skeptic→profile"),
             ("base_url", "base-url override"), ("key_env", "key env var")]


def _e(text) -> str:
    return html.escape(str(text), quote=True)


def model_label(profile: str | None) -> str:
    """Human one-liner for which model a run used (shown on the result page)."""
    st = gateway_status(profile)
    if st["kind"] == "deterministic":
        return f"{st['profile']} — no model (free, offline)"
    reason = st["tier_models"]["reason"]
    override = st.get("reason_override")
    suffix = f" · reasoning→{override}" if override else ""
    return f"{st['profile']} · {reason}{suffix}"


# -- run execution -----------------------------------------------------------
def parse_form(fields: dict[str, list[str]]) -> tuple[str, list[str], list[EvidenceInput]]:
    """Turn posted text fields into (question, candidates, evidence)."""
    question = (fields.get("question", [""])[0] or "").strip()
    candidates = [ln.strip() for ln in fields.get("candidates", [""])[0].splitlines() if ln.strip()]
    evidence: list[EvidenceInput] = []
    for line in fields.get("evidence", [""])[0].splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        source = parts[0] if len(parts) > 1 else "user"
        text = parts[1] if len(parts) > 1 else parts[0]
        supports = None
        if len(parts) > 2 and parts[2].lstrip("-").isdigit():
            supports = int(parts[2]) - 1
        evidence.append(EvidenceInput(text=text, source=source, supports=supports))
    return question, candidates, evidence


@contextmanager
def _applied(overrides: dict | None):
    """Scope advanced model overrides into the environment, then restore exactly."""
    saved: dict[str, str | None] = {}
    try:
        for attr, env in _OVERRIDE_ENV.items():
            val = ((overrides or {}).get(attr) or "").strip()
            if val:
                saved[env] = os.environ.get(env)
                os.environ[env] = val
        yield
    finally:
        for env, prev in saved.items():
            os.environ.pop(env, None) if prev is None else os.environ.__setitem__(env, prev)


def _live_web_adapter():
    import tempfile
    from pathlib import Path

    from ...adapters import Cassette, ContentAddressedStore, HttpClient, WebSearchAdapter
    cas = ContentAddressedStore(tempfile.mkdtemp())
    http = HttpClient(Cassette(Path(tempfile.mkdtemp()) / "web.json"), mode="live",
                      block_private_net=True, min_interval=1.0)
    return WebSearchAdapter(http, cas, backend="wikipedia")


def run_and_store(question: str, candidates: list[str], evidence: list[EvidenceInput],
                  profile: str | None = None, *, autonomous: bool = False,
                  overrides: dict | None = None) -> str:
    """Run an investigation (or, when ``autonomous``, autonomous web research) and store it."""
    profile = profile if profile in PROFILES else None
    with _applied(overrides):
        gateway = build_gateway(profile=profile)
        if autonomous:
            from ...adapters.web.search import to_search_query
            result = autoresearch_investigation(
                question=question, candidates=candidates or None, web_adapter=_live_web_adapter(),
                limit=5, gateway=gateway, rounds=3, backends=["duckduckgo", "wikipedia"],
                query_transform=to_search_query)
        else:
            result = run_investigation(question=question, candidates=candidates,
                                       evidence=evidence, gateway=gateway)
    run_id = result.investigation.investigation_id
    RUNS[run_id] = result
    RUN_MODELS[run_id] = model_label(profile)
    _STORE.save(InvestigationSummary.from_result(result), run_id, model=model_label(profile))
    while len(RUNS) > _MAX_RUNS:
        RUN_MODELS.pop(next(iter(RUNS)), None)
        RUNS.pop(next(iter(RUNS)))
    return run_id


# -- pages -------------------------------------------------------------------
def _page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_e(title)}</title><style>{_CSS}</style></head><body>{body}</body></html>')


def _nav(active: str = "") -> str:
    def link(href: str, label: str, key: str) -> str:
        cls = ' class="on"' if key == active else ""
        return f'<a href="{href}"{cls}>{label}</a>'
    return ('<header><span class="logo">&#9678;</span><b>OSINTINEL</b>'
            '<span class="grow"></span>'
            f'{link("/", "✚ New", "new")}{link("/history", "History", "history")}</header>')


def render_form(message: str = "") -> str:
    note = f'<p class="msg">{_e(message)}</p>' if message else ""
    adv = "\n".join(
        f'<label class="adv">{_e(label)}<input name="{attr}"></label>' for attr, label in _ADVANCED)
    body = f"""{_nav("new")}
<main>{note}
  <form method="post" action="/investigate" enctype="multipart/form-data" class="card">
    <label>Question
      <input name="question" placeholder="What is the structure on the ridge?" required></label>
    <label>Competing answers <span class="muted">(one per line; optional in Autonomous mode)</span>
      <textarea name="candidates" rows="3"
        placeholder="communications mast&#10;wind turbine&#10;water tower"></textarea></label>
    <label>Evidence <span class="muted">(one per line: <code>source | text | supports#</code>)</span>
      <textarea name="evidence" rows="5"
        placeholder="OpenStreetMap | node tagged man_made=mast | 1&#10;Wikidata | radio relay nearby | 1"></textarea></label>
    <label class="check"><input type="checkbox" name="autonomous" value="on">
      <span>Autonomous — research the open web for evidence (needs network; ignores the evidence box)</span></label>
    <label>Photo <span class="muted">(optional JPEG — EXIF geotag + sun/shadow read)</span>
      <input type="file" name="photo" accept="image/jpeg,.jpg,.jpeg"></label>
    <label>Model <span class="muted">(inference profile)</span>
      <select name="profile">{_profile_options()}</select></label>
    <details><summary>Advanced model control</summary>
      <div class="advgrid">{adv}</div>
      <p class="muted">Leave blank to use the profile defaults. Per-tier model names, decorrelation
        profiles, and an OpenAI-compatible base-URL / key env var.</p></details>
    <button type="submit">⌖ Investigate</button>
  </form>
  <p class="muted">Local/free: run <code>ollama serve</code> and pick <code>ollama</code>. Cloud
    profiles read their key from the environment at launch. No model (deterministic)? Tag each
    evidence line with a trailing <code>supports#</code>.</p>
</main>"""
    return _page("OSINTINEL — New investigation", body)


def _profile_options() -> str:
    env_label = model_label(None)
    opts = [f'<option value="" selected>Launch default — {_e(env_label)}</option>']
    for name, p in PROFILES.items():
        cost = "free" if p.free else "paid"
        local = "local" if p.local else "cloud"
        key = f", needs {p.key_env}" if p.key_env else ""
        opts.append(f'<option value="{_e(name)}">{_e(name)} ({local}, {cost}{key})</option>')
    return "\n".join(opts)


def _banner(run_id: str) -> str:
    model = RUN_MODELS.get(run_id, "")
    chip = f'&nbsp;·&nbsp; <span class="hl">model:</span> {_e(model)}' if model else ""
    result = RUNS.get(run_id)
    sources = InvestigationSummary.from_result(result).sources if result is not None else []
    src = (f'&nbsp;·&nbsp; <span class="hl">tools/sources:</span> '
           f'{_e(", ".join(s["source"] for s in sources))}' if sources else "")
    return ('<div class="resultnav"><a href="/">&larr; New</a> &nbsp;·&nbsp; '
            f'<a href="/history">History</a> &nbsp;·&nbsp; OSINTINEL{chip}{src}</div>')


def build_result_page(run_id: str) -> str | None:
    result = RUNS.get(run_id)
    if result is None:
        return None
    page = render_dashboard(build_dashboard_data(result))
    return page.replace("<body>", "<body>\n" + _banner(run_id), 1)


def render_history() -> str:
    runs = _STORE.list(100)
    if not runs:
        cards = '<p class="muted">No saved runs yet. Run an investigation and it appears here.</p>'
    else:
        rows = []
        for r in runs:
            when = _dt.datetime.fromtimestamp(r.get("saved_at", 0)).strftime("%Y-%m-%d %H:%M")
            conf = r.get("leader_confidence", 0.0)
            rid = r.get("id", "")
            head = (f'<a href="/run/{_e(rid)}">{_e(r.get("question") or "—")}</a>'
                    if rid in RUNS else _e(r.get("question") or "—"))
            rows.append(
                f'<div class="hcard"><div class="hq">{head}</div>'
                f'<div class="muted">{when} · {_e(r.get("model") or "—")}</div>'
                f'<div class="leader">{_e(r.get("leader") or "—")} '
                f'<span class="conf">{conf:.0%}</span></div></div>')
        cards = "\n".join(rows)
    return _page("OSINTINEL — History", f'{_nav("history")}<main><h2>History</h2>{cards}</main>')


def render_photo_result(analysis: dict, filename: str) -> str:
    if not analysis["ok"]:
        inner = ('<p class="msg">No EXIF metadata found. This reader handles <b>JPEG with EXIF</b> '
                 '— iPhone HEIC won\'t parse, so export/convert to JPEG first.</p>')
    else:
        rows = [f'<div class="kv"><b>Camera</b><span>{_e(analysis["camera"])}</span></div>'
                if analysis["camera"] else "",
                f'<div class="kv"><b>Captured</b><span>{_e(analysis["captured"])}</span></div>'
                if analysis["captured"] else ""]
        gps = analysis["gps"]
        if gps:
            alt = f' · alt {gps["altitude_m"]} m' if gps.get("altitude_m") is not None else ""
            rows.append(f'<div class="kv"><b>Geotag</b><span>{gps["lat"]}, {gps["lon"]}{alt} '
                        f'&nbsp;<a href="{_e(osm_url(gps["lat"], gps["lon"]))}" '
                        f'target="_blank" rel="noopener">map ↗</a></span></div>')
            sun = analysis["sun"]
            if sun:
                rows.append(f'<div class="kv"><b>Sun (UTC)</b><span>elevation {sun["elevation"]}°, '
                            f'azimuth {sun["azimuth"]}° → shadows point <b>{sun["shadow"]}°</b>'
                            '<br><span class="muted">do the photo\'s shadows match that bearing?'
                            '</span></span></div>')
        else:
            rows.append('<p class="muted">No GPS tag — this image isn\'t geotagged.</p>')
        inner = "".join(rows)
    body = (f'{_nav()}<main><h2>Photo analysis</h2>'
            f'<p class="muted">{_e(filename)}</p><div class="card">{inner}</div></main>')
    return _page("OSINTINEL — Photo analysis", body)


_CSS = """
:root{--bg:#0b0e16;--panel:#141b2d;--line:#222c44;--ink:#e6ecf7;--mut:#8a96b0;--accent:#3ddc84}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#16203a 0,var(--bg) 60%);
color:var(--ink);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{display:flex;align-items:center;gap:14px;padding:14px 20px;border-bottom:1px solid var(--line)}
header b{font-weight:800} .logo{color:var(--accent);font-size:18px} .grow{flex:1}
header a{color:var(--mut);text-decoration:none;font-size:14px;font-weight:600;padding:6px 10px;
border-radius:8px} header a.on,header a:hover{color:var(--accent);background:#0e1626}
.hl{color:var(--accent)} .muted{color:var(--mut);font-weight:400;font-size:13px}
main{max-width:820px;margin:0 auto;padding:20px}
h2{font-size:18px;margin:6px 0 14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px;
display:flex;flex-direction:column;gap:16px}
label{display:flex;flex-direction:column;gap:6px;font-weight:600;font-size:14px}
input,textarea,select{background:#0a0f1c;border:1px solid var(--line);border-radius:9px;
color:var(--ink);padding:12px;font-size:16px;resize:vertical;width:100%}
input:focus,textarea:focus,select:focus{outline:none;border-color:#3a7}
input[type=file]{padding:9px;font-size:14px} input[type=checkbox]{width:auto}
.check{flex-direction:row;align-items:flex-start;gap:10px;font-weight:500}
.check input{margin-top:3px}
details summary{cursor:pointer;color:var(--mut);font-size:14px;font-weight:600}
.advgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.adv{font-weight:500;font-size:12px;color:var(--mut)}
code{font-family:ui-monospace,Menlo,Consolas,monospace;color:#bcd}
button{background:linear-gradient(160deg,#3ddc84,#2bb36a);color:#06121f;border:0;border-radius:10px;
padding:15px;font-size:16px;font-weight:800;cursor:pointer}
.msg{background:#3a2330;border:1px solid #5a2a3a;color:#ffb4c4;padding:11px 13px;border-radius:8px}
.resultnav{background:#0b0e16;border-bottom:1px solid #222c44;padding:10px 20px;font-size:13px;
color:var(--mut)} .resultnav a{color:var(--accent);text-decoration:none}
.hcard{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;
margin-bottom:12px} .hcard .hq{font-weight:700} .hcard a{color:var(--ink)}
.leader{margin-top:6px;color:var(--accent)} .conf{color:var(--mut);font-weight:700}
.kv{display:flex;gap:14px;padding:8px 0;border-bottom:1px solid var(--line)}
.kv b{min-width:96px;color:var(--mut)} .kv a{color:var(--accent)}
@media (max-width:600px){.advgrid{grid-template-columns:1fr}main{padding:14px}.card{padding:16px}}
"""


# -- multipart + HTTP --------------------------------------------------------
def parse_multipart(body: bytes, boundary: bytes) -> tuple[dict[str, list[str]], dict[str, tuple]]:
    """Minimal multipart/form-data parser (the stdlib ``cgi`` module is gone in 3.13+).
    Returns (text fields as parse_qs-shaped dict, files as {name: (filename, bytes)})."""
    fields: dict[str, list[str]] = {}
    files: dict[str, tuple] = {}
    for part in body.split(b"--" + boundary):
        if not part or part in (b"--\r\n", b"--", b"\r\n"):
            continue
        head, _, content = part.partition(b"\r\n\r\n")
        if not _:
            continue
        content = content[:-2] if content.endswith(b"\r\n") else content  # trailing CRLF
        disp = ""
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"content-disposition"):
                disp = line.decode("latin-1", "replace")
        name = _disp_param(disp, "name")
        if name is None:
            continue
        filename = _disp_param(disp, "filename")
        if filename is not None:
            files[name] = (filename, content)
        else:
            fields.setdefault(name, []).append(content.decode("utf-8", "replace"))
    return fields, files


def _disp_param(disposition: str, key: str) -> str | None:
    marker = f'{key}="'
    i = disposition.find(marker)
    if i < 0:
        return None
    i += len(marker)
    return disposition[i:disposition.find('"', i)]


def _overrides_from(fields: dict[str, list[str]]) -> dict:
    return {attr: (fields.get(attr, [""])[0] or "").strip() for attr in _OVERRIDE_ENV}


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/new"):
            self._send(200, render_form())
        elif path == "/history":
            self._send(200, render_history())
        elif path == "/health":
            self._send(200, "ok", "text/plain")
        elif path.startswith("/run/"):
            page = build_result_page(path[len("/run/"):])
            self._send(200, page) if page else self._send(404, render_form("Run not found."))
        else:
            self._send(404, render_form("Not found."))

    def _read_post(self) -> tuple[dict[str, list[str]], dict[str, tuple]]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")
        if ctype.startswith("multipart/form-data") and "boundary=" in ctype:
            boundary = ctype.split("boundary=", 1)[1].strip().strip('"').encode("latin-1")
            return parse_multipart(raw, boundary)
        return urllib.parse.parse_qs(raw.decode("utf-8")), {}

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/investigate":
            self._send(404, render_form("Not found."))
            return
        fields, files = self._read_post()

        photo = files.get("photo")
        if photo and photo[1]:  # a photo takes priority — analyze its EXIF + sun geometry
            self._send(200, render_photo_result(analyze_photo(photo[1]), photo[0]))
            return

        question, candidates, evidence = parse_form(fields)
        autonomous = bool(fields.get("autonomous"))
        if not question:
            self._send(400, render_form("Please provide a question."))
            return
        if not autonomous and not candidates:
            self._send(400, render_form(
                "Provide at least one competing answer, or tick Autonomous."))
            return
        profile = (fields.get("profile", [""])[0] or "").strip() or None
        try:
            run_id = run_and_store(question, candidates, evidence, profile=profile,
                                   autonomous=autonomous, overrides=_overrides_from(fields))
        except Exception as exc:  # network/model failure → a clear page, never a 500
            self._send(502, render_form(f"Run failed: {exc}"))
            return
        self.send_response(303)
        self.send_header("Location", f"/run/{run_id}")
        self.end_headers()


def serve(port: int = 8765, host: str = "127.0.0.1") -> None:
    server = ThreadingHTTPServer((host, port), _Handler)
    where = "all interfaces" if host == "0.0.0.0" else host
    print(f"OSINTINEL web app on http://{host}:{port}  ({where}; Ctrl+C to stop)")
    if host == "0.0.0.0":
        print("  reachable from your phone on the same wifi at  http://<this-machine-ip>:%d" % port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        server.shutdown()
