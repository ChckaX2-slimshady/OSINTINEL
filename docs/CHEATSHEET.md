# OSINTINEL — Cheat Sheet

A single-page map of *everything that's been built* and *how to reach it*. For the why, see the
numbered docs (`00`–`11`); this is the operator's quick reference.

---

## TL;DR

OSINTINEL is a local-first, multi-agent OSINT reasoning engine. It runs **free** out of the box:
the default inference profile is `deterministic` (no model, no network, no key, $0). Point it at a
model only when you want richer reasoning — your local **Ollama**, a free cloud tier, or any
OpenAI-compatible endpoint. Three ways to drive it: the **CLI**, a **local web app**, and an **MCP
server** (so Claude Desktop — or any MCP client — can run investigations on your machine).

```bash
pip install -e .          # from the repo root
pip install -e ".[tui]"   # …or include the terminal UI (adds Textual)
osintinel verify          # smoke test: persist, reload, replay the ledger — proves it works
osintinel tui             # terminal console (animated mascot + full model control)
osintinel serve           # …or the browser UI at http://127.0.0.1:8765
```

---

## The three front doors

| Door | Command | What it is | State |
|------|---------|-----------|-------|
| **CLI** | `osintinel <cmd>` | demos + diagnostics + the service entrypoints | per-run, optional ledger on disk |
| **TUI** | `osintinel tui` | terminal UI (Textual): animated mascot, question form, **full per-tier model control**, results | runs in memory |
| **Web app** | `osintinel serve [--port 8765] [--host 127.0.0.1]` | stdlib browser UI; ask a question, **pick the model**, see the result | runs held **in memory** (`RUNS` dict) |
| **MCP server** | `osintinel mcp` | JSON-RPC stdio; tools `investigate` + `models_status` | driven by an MCP client (Claude Desktop, etc.) |

> **TUI vs. web app:** the TUI (`osintinel tui`, needs `pip install -e ".[tui]"`) is the
> terminal-native console — it exposes **every** model knob (per-tier reason/small/task/embed
> models, the reason→profile and skeptic→profile decorrelation overrides, and a base-URL/key-env
> endpoint override), which the web dropdown deliberately doesn't. The web app picks the whole
> profile in one click; the TUI lets you edit each tier. Pick the `ollama` profile (or hit
> **Detect models**) and the tier dropdowns auto-populate with the models actually installed on
> your machine — no typing model names, just choose `dollamin:latest` etc. per tier.

> **Dashboard vs. web app:** `osintinel dashboard` writes a *read-only* HTML report of one
> investigation (graph/timeline/confidence) — no inputs, no model picker. The **web app**
> (`osintinel serve`) is the interactive front door: it has the question form **and a model
> dropdown**, then renders that same dashboard for the result.

**One-command Claude Desktop install** (runs on *your* machine, not the cloud sandbox):

```bash
python scripts/install_claude_mcp.py                 # default profile=ollama (local models)
python scripts/install_claude_mcp.py --profile deterministic  # free, no model, no network
python scripts/install_claude_mcp.py --print          # show the JSON, change nothing
```

It finds the `osintinel` binary (or falls back to `python -m osintinel.interfaces.cli.main mcp`
so Claude Desktop's missing-PATH doesn't bite), locates `claude_desktop_config.json` for your OS,
merges in the server (preserving existing servers + writing a `.bak`). Then fully quit & reopen
Claude Desktop and ask it: *"Use osintinel's models_status tool."*

Installer flags: `--profile`, `--net`, `--reason-profile`, `--base-url`, `--key-env`,
`--env KEY=VALUE` (repeatable), `--command`, `--config`, `--print`, `--dry-run`.

---

## CLI commands

| Command | Does |
|---------|------|
| `run [--json] [--max-iterations N]` | run the bundled demo investigation |
| `report` | run the demo and print the insight report |
| `verify [--ledger PATH]` | persist → reload → replay the ledger; verify byte-identical integrity |
| `audit` | print the evidence chain for the leading insight |
| `adapters` | list registered reference + license-gated adapters |
| `slice` | Phase 3 adapter vertical slice (offline, from cassettes) |
| `memory [--rounds 5]` | Phase 4 learning benchmark (cost falls as Memory learns strategy) |
| `image` | Phase 5 image-geolocation pipeline on a sample image |
| `geo` | Phase 6 geospatial constraint-narrowing golden suite |
| `dashboard [--out FILE.html]` | Phase 7 self-contained offline HTML console |
| `models` | show model-tier config + exercise the inference gateway |
| `independence` | embed-tier demo: detect illusory (syndicated) source independence |
| `reason` | reason-tier demo: model explanations + adversarial critique |
| `improve` | Phase 8 self-improvement: calibration + planner tuning across versions |
| `tui` | launch the terminal UI (Textual) — animated mascot + full per-tier model control |
| `serve [--port] [--host]` | launch the local web app |
| `mcp` | run the MCP stdio server |
| `history [--limit 20]` | list saved investigation runs (persisted to `~/.osintinel/runs`) |
| `research` | autonomous web-research demo (gathers its own evidence, offline) |
| `intel` | free infra/threat adapters demo (Shodan InternetDB, URLScan, OTX) |
| `records` | free public-records adapters demo (OpenCorporates, SEC EDGAR, GLEIF) |

Every command runs green offline with **no model and no network** — that's the deterministic floor.

---

## Inference: profiles & how to switch models

A **profile** maps the three tiers (reason / small / task) + embeddings to a concrete endpoint.
Select one with `OSINTINEL_INFERENCE_PROFILE`. All are free except `anthropic`.

| Profile | Backend | Key | Notes |
|---------|---------|-----|-------|
| `deterministic` | none | — | **default**; no network; reproducible; CI/offline floor |
| `ollama` | local Ollama (`localhost:11434`) | none | fully local & private; pick a reason model to fit your VRAM |
| `gemini` | Google AI Studio | `GEMINI_API_KEY` | free tier (key, no card); good free reasoning |
| `groq` | Groq | `GROQ_API_KEY` | free tier, fast 70B; embeddings fall back to local Ollama |
| `openrouter` | OpenRouter `:free` models | `OPENROUTER_API_KEY` | free models; embeddings fall back to local Ollama |
| `huggingface` | HF Inference API | `HF_TOKEN` | free tier (rate-limited) |
| `anthropic` | Anthropic API | `ANTHROPIC_API_KEY` | **paid**; flagship quality |

**Graceful degradation:** every model integration falls back to deterministic behavior when no
model is set, the endpoint is unreachable, or output is unusable. It never crashes and never costs.

### Switching models without touching code (env vars)

| Env var | Effect |
|---------|--------|
| `OSINTINEL_INFERENCE_PROFILE` | pick the base profile (table above) |
| `OSINTINEL_REASON_MODEL` / `_SMALL_MODEL` / `_TASK_MODEL` / `_EMBED_MODEL` | override one tier's model id |
| `OSINTINEL_REASON_PROFILE` | route **only** the reasoning tier to another profile (e.g. local embed/task + free-cloud reasoning) |
| `OSINTINEL_SKEPTIC_PROFILE` | route the Skeptic role to a *different* model (decorrelates the challenge layer) |
| `OSINTINEL_OPENAI_BASE_URL` | retarget the OpenAI-compatible **chat** endpoint — custom Ollama port, remote box, or a **Hermes**-style harness |
| `OSINTINEL_EMBED_BASE_URL` | retarget the OpenAI-compatible **embeddings** endpoint |
| `OSINTINEL_OPENAI_KEY_ENV` | name of the env var holding the bearer token for the `--base-url` endpoint (omit for keyless local servers) |

The base-URL overrides are no-ops for non-OpenAI backends (`deterministic` / `anthropic` /
`huggingface`), so they can't accidentally switch your backend.

**Example — point the reasoning tiers at a Hermes harness on port 8080:**
```bash
export OSINTINEL_INFERENCE_PROFILE=ollama
export OSINTINEL_OPENAI_BASE_URL=http://localhost:8080/v1
export OSINTINEL_OPENAI_KEY_ENV=HERMES_TOKEN   # only if the harness needs a token
osintinel models      # confirms the resolved base_url
```

Inspect what's active any time: `osintinel models` → shows profile, per-tier routing, key
presence, overrides, and net mode.

---

## Network mode (cassettes)

External calls go through a cassette transport with three modes via `OSINTINEL_NET`:

| Mode | Meaning |
|------|---------|
| `replay` | serve only from committed recordings (default in tests/CI) |
| `record` | hit the network and save responses for later replay |
| `live` | hit the network without recording |

`OSINTINEL_RECORD=1` is the older equivalent of `record`. **API keys ride in HTTP headers and never
enter cassettes** (the request key hashes only method + URL + body).

### Safety & persistence env vars

| Env var | Effect |
|---------|--------|
| `OSINTINEL_ALLOW_PRIVATE_NET=1` | disable the SSRF guard on the web-fetch path (only for trusted LAN targets) |
| `OSINTINEL_HOME` | base dir for persisted run history (default `~/.osintinel`) |
| `OSINTINEL_NO_PERSIST=1` | don't persist run summaries to disk (fully ephemeral session) |

The autonomous web-fetch path refuses URLs that resolve to loopback/private/link-local/reserved
addresses (so a malicious link can't reach your local Ollama or cloud metadata), and retries
transient network failures with backoff. The SSRF guard is **off** for inference calls, so a local
Ollama endpoint always works.

---

## Adapters (all free / lawful, public-source only)

Selected by **capability tag**, not by name, so they're interchangeable.

| Capability | Adapter(s) | Key |
|-----------|-----------|-----|
| `geo.geocode` / `geo.reverse_geocode` | Nominatim | none |
| `geo.features` | Overpass | none |
| `archive.timemap` / `archive.snapshot` | Wayback | none |
| `reference.encyclopedic` | Wikidata | none |
| `infra.certs` | crt.sh Certificate Transparency | none |
| `infra.exposure` | Shodan InternetDB | none |
| `infra.urlscan` | URLScan.io | none |
| `threat.intel` | AlienVault OTX | free key |
| `media.exif` | built-in EXIF codec | n/a |
| `compute.symbolic` | NOAA solar geometry | n/a |
| `web.search` / `web.fetch` | Wikipedia (default) + DuckDuckGo | none |
| `record.public` | OpenCorporates, SEC EDGAR, GLEIF | none |

**Commercial / supplemental adapters** (Maltego, Pipl, PimEyes, Recorded Future, …) are
license-gated and **off by default**. *None* are functionally integrated (all paid). Turning one on
requires credentials **and** `OSINTINEL_ATTEST_AUTHORIZED=1`. `osintinel adapters` lists both sets.

---

## Where the records live

- **Web app & MCP runs:** held **in memory** for now (an in-process `RUNS` dict) — nothing persists
  across a restart by design.
- **Ledger:** a hash-chained, append-only JSONL event log; `osintinel verify` proves a run replays
  byte-identically. Heavy bytes (images, fetched pages) go to a **content-addressed store (CAS)**,
  off the ledger.
- **Memory (Phase 4) & self-improvement (Phase 8):** read **strategy/metrics only**, behind an
  evidence firewall — they never read evidence content or mutate the ledger / confidence history.

---

## Common recipes

```bash
# free, no model, fully offline — the floor
osintinel run

# local models via Ollama (private)
OSINTINEL_INFERENCE_PROFILE=ollama osintinel reason

# local embed/task + free-cloud reasoning (hybrid sweet spot)
OSINTINEL_INFERENCE_PROFILE=ollama OSINTINEL_REASON_PROFILE=gemini GEMINI_API_KEY=... osintinel reason

# fit a smaller reason model to your VRAM
OSINTINEL_INFERENCE_PROFILE=ollama OSINTINEL_REASON_MODEL=qwen2.5:7b-instruct osintinel models

# browser UI
osintinel serve   # → http://127.0.0.1:8765

# wire into Claude Desktop (free deterministic default)
python scripts/install_claude_mcp.py
```
