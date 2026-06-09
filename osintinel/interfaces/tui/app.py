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
from textual.widgets import Button, Footer, Header, Input, Select, Static, TextArea

from .logic import (
    InferenceForm,
    format_summary,
    form_from_profile,
    parse_candidates,
    parse_evidence,
    profile_names,
    run_summary,
    status_lines,
)
from .mascot import splash_frames

_MODEL_FIELDS = [
    ("reason_model", "reason model"), ("small_model", "small model"),
    ("task_model", "task model"), ("embed_model", "embed model"),
    ("reason_profile", "reason→profile"), ("skeptic_profile", "skeptic→profile"),
    ("base_url", "base-url override"), ("key_env", "key env var"),
]


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

                yield Static("[b]Model[/b]  [dim]profile sets the tiers; edit any below[/dim]",
                             classes="section")
                yield Select([(n, n) for n in profile_names()], value="deterministic",
                             allow_blank=False, id="profile")
                form = form_from_profile("deterministic")
                for i in range(0, len(_MODEL_FIELDS), 2):
                    with Horizontal(classes="pair"):
                        for attr, label in _MODEL_FIELDS[i:i + 2]:
                            inp = Input(value=getattr(form, attr), id=attr, classes="model")
                            inp.border_title = label
                            yield inp
                with Horizontal(classes="pair"):
                    yield Button("⌖  Investigate", variant="success", id="run")
                    yield Button("↻  Refresh status", id="refresh")
            with VerticalScroll(id="right"):
                yield Static(status_lines(form), id="status")
                yield Static("[dim]Pose a question and press Investigate (Ctrl+R).[/dim]",
                             id="summary")
        yield Footer()

    # -- form helpers --------------------------------------------------------
    def _form(self) -> InferenceForm:
        get = lambda i: self.query_one(f"#{i}", Input).value  # noqa: E731
        return InferenceForm(
            profile=self.query_one("#profile", Select).value,
            reason_model=get("reason_model"), small_model=get("small_model"),
            task_model=get("task_model"), embed_model=get("embed_model"),
            reason_profile=get("reason_profile"), skeptic_profile=get("skeptic_profile"),
            base_url=get("base_url"), key_env=get("key_env"))

    def _refresh_status(self) -> None:
        self.query_one("#status", Static).update(status_lines(self._form()))

    @on(Select.Changed, "#profile")
    def _profile_changed(self, event: Select.Changed) -> None:
        form = form_from_profile(str(event.value))
        for attr in ("reason_model", "small_model", "task_model", "embed_model"):
            self.query_one(f"#{attr}", Input).value = getattr(form, attr)
        self._refresh_status()

    @on(Button.Pressed, "#refresh")
    def _on_refresh(self) -> None:
        self._refresh_status()

    @on(Button.Pressed, "#run")
    def _on_run(self) -> None:
        self.action_run()

    def action_run(self) -> None:
        question = self.query_one("#question", Input).value.strip()
        candidates = parse_candidates(self.query_one("#candidates", TextArea).text)
        if not question or not candidates:
            self.query_one("#summary", Static).update(
                "[red]Provide a question and at least one competing answer.[/red]")
            return
        evidence = parse_evidence(self.query_one("#evidence", TextArea).text)
        self.query_one("#run", Button).disabled = True
        self.query_one("#summary", Static).update("⏳  [b]investigating…[/b]  "
                                                  "[dim]quorum: synthesis → skeptic → "
                                                  "confidence → epistemology[/dim]")
        self._refresh_status()
        self._investigate(question, candidates, evidence, self._form())

    @work(thread=True, exclusive=True)
    def _investigate(self, question, candidates, evidence, form) -> None:
        try:
            text = format_summary(run_summary(question, candidates, evidence, form))
        except Exception as exc:  # network/model failures surface as data, never a crash
            text = f"[red]Run failed:[/red] {exc}\n[dim]Tip: the deterministic profile " \
                   "needs no model/network.[/dim]"
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
