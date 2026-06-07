"""Local web app (Phase post-8): a browser front door to OSINTINEL.

``osintinel serve`` launches a dependency-free ``http.server`` where you pose a question, list the
competing answers, paste evidence, and get the full Investigation Console back. Runs are held in
memory (saving is opt-in). The request handlers delegate to small pure functions so the app is
testable without binding a socket.
"""

from .app import build_result_page, parse_form, render_form, run_and_store, serve

__all__ = ["build_result_page", "parse_form", "render_form", "run_and_store", "serve"]
