"""OSINTINEL terminal UI (Textual) — the terminal-native front door.

A launch splash with the animated sentinel mascot, then a single console: pose a question, list
the competing answers, paste evidence, and — unlike the web picker — tune **every model knob**
(per-tier models, reasoning/skeptic decorrelation profiles, OpenAI-compatible base-URL) right in
the terminal. Runs go through the same ``service.run_investigation`` as every other front door.

Textual is an optional dependency (``pip install -e ".[tui]"``); the heavy logic lives in
``logic.py`` / ``mascot.py`` (no Textual import) so it stays unit-testable.
"""

from __future__ import annotations

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Select, Static, TextArea

from .logic import (
    InferenceForm,
    effective_base_url,
    format_summary,
    form_from_profile,
    is_openai_profile,
    list_installed_models,
    parse_candidates,
    parse_evidence,
    photo_report,
    profile_names,
    run_autoresearch,
    run_summary,
    status_lines,
)
from .mascot import splash_frames

# tier model fields are dropdowns (auto-populated from the endpoint's installed models)
_TIER_SELECTS = [("reason_model", "reason model"), ("small_model", "small model"),
                 ("task_model", "task model"), ("embed_model", "embed model")]
# the remaining knobs stay free-text
_TEXT_INPUTS = [("reason_profile", "reason→profile"), ("skeptic_profile", "skeptic→profile"),
                ("base_url", "base-url override"), ("key_env", "key env var")]
_TIER_ATTRS = [a for a, _ in _TIER_SELECTS]


class SplashScreen(Screen):
    """The launch animation; auto-advances to the console (any key skips)."""

    BINDINGS = [("escape,enter,space,q", "skip", "skip")]

    def compose(self) -> ComposeResult:
        yield Static(id="splash")

    def on_mount(self) -> None:
        self._frames = splash_frames()
        self._i = 0
        self._loops = 0
        self.query_one("#splash", Static).update(self._frames[0])
        self._timer = self.set_interval(0.07, self._tick)

    def _tick(self) -> None:
        self._i += 1
        if self._i >= len(self._frames):
            self._i = 0
            self._loops += 1
            if self._loops >= 2:
                self.action_skip()
                return
        self.query_one("#splash", Static).update(self._frames[self._i])

    def action_skip(self) -> None:
        self._timer.stop()
        self.app.switch_screen(ConsoleScreen())


class ConsoleScreen(Screen):
    """The investigation console: inputs + full model panel + results."""

    BINDINGS = [("ctrl+r", "run", "Investigate"), ("ctrl+q", "quit", "Quit")]
    last_summary: str = ""
    _note: str = ""        # sticky detection banner shown above the live status

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with VerticalScroll(id="left"):
                yield Static("[b]Investigation[/b]", classes="section")
                q = Input(placeholder="What is the structure on the ridge?", id="question")
                q.border_title = "question"
                yield q
                ca = TextArea(id="candidates")
                ca.border_title = "competing answers — one per line"
                yield ca
                ev = TextArea(id="evidence")
                ev.border_title = "evidence — source | text | supports#"
                yield ev
                yield Checkbox("Autonomous — gather evidence from the open web (needs network; "
                               "ignores the evidence box)", id="autonomous")
                photo = Input(placeholder="/path/to/photo.jpg — EXIF geotag + sun/shadow analysis",
                              id="photo")
                photo.border_title = "photo (optional)"
                yield photo

                yield Static("[b]Model[/b]  [dim]pick a profile; tiers populate from your "
                             "installed models[/dim]", classes="section")
                yield Select([(n, n) for n in profile_names()], value="deterministic",
                             allow_blank=False, id="profile")
                form = form_from_profile("deterministic")
                for i in range(0, len(_TIER_SELECTS), 2):
                    with Horizontal(classes="pair"):
                        for attr, label in _TIER_SELECTS[i:i + 2]:
                            default = getattr(form, attr)
                            sel = Select([(default, default)], value=default, allow_blank=False,
                                         id=attr, classes="model")
                            sel.border_title = label
                            yield sel
                for i in range(0, len(_TEXT_INPUTS), 2):
                    with Horizontal(classes="pair"):
                        for attr, label in _TEXT_INPUTS[i:i + 2]:
                            inp = Input(value=getattr(form, attr), id=attr, classes="model")
                            inp.border_title = label
                            yield inp
                with Horizontal(classes="pair"):
                    yield Button("⌖  Investigate", variant="success", id="run")
                    yield Button("✚  New", id="new")
                    yield Button("↻  Detect models", id="detect")
                    yield Button("↻  Status", id="refresh")
            with VerticalScroll(id="right"):
                yield Static(status_lines(form), id="status")
                yield Static("[dim]Pose a question and press Investigate (Ctrl+R).[/dim]",
                             id="summary")
        yield Footer()

    # -- form helpers --------------------------------------------------------
    def _sel(self, ident: str) -> str:
        v = self.query_one(f"#{ident}", Select).value
        return v if isinstance(v, str) else ""

    def _inp(self, ident: str) -> str:
        return self.query_one(f"#{ident}", Input).value

    def _form(self) -> InferenceForm:
        return InferenceForm(
            profile=self._sel("profile"),
            reason_model=self._sel("reason_model"), small_model=self._sel("small_model"),
            task_model=self._sel("task_model"), embed_model=self._sel("embed_model"),
            reason_profile=self._inp("reason_profile"), skeptic_profile=self._inp("skeptic_profile"),
            base_url=self._inp("base_url"), key_env=self._inp("key_env"))

    def _refresh_status(self, note: str | None = None) -> None:
        if note is not None:
            self._note = note
        body = status_lines(self._form())
        self.query_one("#status", Static).update(f"{self._note}\n{body}" if self._note else body)

    def _set_tier_options(self, attr: str, options: list[str], value: str) -> None:
        """Repopulate a tier dropdown, always keeping ``value`` selectable."""
        opts = list(dict.fromkeys([value, *options])) if value else list(dict.fromkeys(options))
        sel = self.query_one(f"#{attr}", Select)
        sel.set_options([(o, o) for o in opts])
        sel.value = value if value in opts else (opts[0] if opts else Select.BLANK)

    @on(Select.Changed, "#profile")
    def _profile_changed(self, event: Select.Changed) -> None:
        name = str(event.value)
        form = form_from_profile(name)
        for attr in _TIER_ATTRS:
            self._set_tier_options(attr, [], getattr(form, attr))  # reset to the profile default
        self._refresh_status(note="")
        if is_openai_profile(name):
            self.detect_models()  # auto-pull the installed list when you choose a live endpoint

    @on(Select.Changed, ".model")
    def _tier_changed(self) -> None:
        self._refresh_status()  # keep the status pane live as you pick per-tier models

    @on(Button.Pressed, "#refresh")
    def _on_refresh(self) -> None:
        self._refresh_status()

    @on(Button.Pressed, "#new")
    def _on_new(self) -> None:
        """Clear the investigation fields for a fresh run (keeps the model setup)."""
        self.query_one("#question", Input).value = ""
        self.query_one("#candidates", TextArea).text = ""
        self.query_one("#evidence", TextArea).text = ""
        self.query_one("#photo", Input).value = ""
        self.query_one("#autonomous", Checkbox).value = False
        self.query_one("#summary", Static).update(
            "[dim]New investigation — pose a question and press Investigate (Ctrl+R).[/dim]")
        self.query_one("#question", Input).focus()

    @on(Button.Pressed, "#detect")
    def _on_detect(self) -> None:
        self.detect_models()

    @work(thread=True, exclusive=True, group="detect")
    def detect_models(self) -> None:
        base = effective_base_url(self._form())
        models = list_installed_models(base)
        self.app.call_from_thread(self._apply_detected, base, models)

    def _apply_detected(self, base: str | None, models: list[str]) -> None:
        if models:
            for attr in _TIER_ATTRS:
                self._set_tier_options(attr, models, self._sel(attr))
            self._refresh_status(f"[green]✓ found {len(models)} model(s) at {base}[/green] — "
                                 "pick one per tier")
        else:
            self._refresh_status(f"[yellow]no models detected at {base or '—'}[/yellow] — is "
                                 "`ollama serve` running and a model pulled?")

    @on(Button.Pressed, "#run")
    def _on_run(self) -> None:
        self.action_run()

    def action_run(self) -> None:
        photo = self.query_one("#photo", Input).value.strip()
        if photo:  # a photo path takes priority — analyze its EXIF + sun geometry
            self._show(photo_report(photo))
            return
        question = self.query_one("#question", Input).value.strip()
        candidates = parse_candidates(self.query_one("#candidates", TextArea).text)
        autonomous = self.query_one("#autonomous", Checkbox).value
        if not question:
            self.query_one("#summary", Static).update("[red]Provide a question.[/red]")
            return
        if not autonomous and not candidates:
            self.query_one("#summary", Static).update(
                "[red]Provide at least one competing answer, or tick Autonomous to let it "
                "gather its own evidence.[/red]")
            return
        evidence = parse_evidence(self.query_one("#evidence", TextArea).text)
        self.query_one("#run", Button).disabled = True
        self.query_one("#summary", Static).update(
            "🌐  [b]researching the open web…[/b]  [dim]search → fetch → frame answers → chase "
            "known-unknowns → skeptic gate[/dim]" if autonomous else
            "⏳  [b]investigating…[/b]  [dim]quorum: synthesis → skeptic → confidence → "
            "epistemology[/dim]")
        self._refresh_status()
        self._investigate(question, candidates, evidence, self._form(), autonomous)

    @work(thread=True, exclusive=True)
    def _investigate(self, question, candidates, evidence, form, autonomous) -> None:
        try:
            if autonomous:
                summary = run_autoresearch(question, form, candidates=candidates or None)
            else:
                summary = run_summary(question, candidates, evidence, form)
            text = format_summary(summary)
        except Exception as exc:  # network/model failures surface as data, never a crash
            text = f"[red]Run failed:[/red] {exc}\n[dim]Tip: autonomous mode needs network; the " \
                   "deterministic profile needs no model.[/dim]"
        self.app.call_from_thread(self._show, text)

    def _show(self, text: str) -> None:
        self.last_summary = text
        self.query_one("#summary", Static).update(text)
        self.query_one("#run", Button).disabled = False


class OsintinelTUI(App):
    TITLE = "OSINTINEL"
    SUB_TITLE = "Open-Source Intelligence Sentinel"
    CSS = """
    Screen { background: $background; }
    #splash { width: auto; height: auto; color: #3ddc84; text-style: bold; }
    SplashScreen { align: center middle; }
    #body { height: 1fr; }
    #left { width: 3fr; padding: 0 1; }
    #right { width: 2fr; padding: 0 1; border-left: vkey $panel; }
    .section { margin: 1 0 0 0; color: #3ddc84; }
    Input { border: round $panel; border-title-align: left; }
    Input.model { width: 1fr; }
    Select.model { width: 1fr; border: round $panel; border-title-align: left; }
    TextArea { height: 5; border: round $panel; }
    TextArea#candidates { height: 4; }
    .pair { height: auto; }
    #run { width: 1fr; }
    #refresh { width: 1fr; }
    #status { border: round $panel; padding: 1; color: $text; }
    #summary { padding: 1; }
    """
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(SplashScreen())


def run_tui() -> None:
    OsintinelTUI().run()
