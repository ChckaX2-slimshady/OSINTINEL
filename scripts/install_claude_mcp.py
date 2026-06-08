#!/usr/bin/env python3
"""One-command installer: register the OSINTINEL MCP server with Claude Desktop (or print the
config for any MCP client).

Runs on *your* machine (this is the part a cloud sandbox can't do for you). It locates the
``osintinel`` command, finds Claude Desktop's config for your OS, and merges in the server entry
— preserving any existing servers and backing up the file first. Stdlib only.

Usage:
    python scripts/install_claude_mcp.py                      # install, profile=ollama net=live
    python scripts/install_claude_mcp.py --reason-profile gemini
    python scripts/install_claude_mcp.py --print             # just show the JSON, change nothing
    python scripts/install_claude_mcp.py --config /path/to/other_client_config.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path


def default_config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData/Roaming")
        return Path(base) / "Claude/claude_desktop_config.json"
    return Path.home() / ".config/Claude/claude_desktop_config.json"


def resolve_command() -> tuple[str, list[str]]:
    """Prefer the absolute path to the installed console script (Claude Desktop ignores PATH);
    fall back to running it via the current Python interpreter as a module."""
    found = shutil.which("osintinel")
    if found:
        return found, ["mcp"]
    return sys.executable, ["-m", "osintinel.interfaces.cli.main", "mcp"]


def build_entry(args) -> dict:
    command, cmd_args = (args.command, ["mcp"]) if args.command else resolve_command()
    env = {"OSINTINEL_INFERENCE_PROFILE": args.profile, "OSINTINEL_NET": args.net}
    if args.reason_profile:
        env["OSINTINEL_REASON_PROFILE"] = args.reason_profile
    for extra in args.env or []:
        if "=" in extra:
            k, v = extra.split("=", 1)
            env[k] = v
    return {"command": command, "args": cmd_args, "env": env}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Install the OSINTINEL MCP server into Claude Desktop.")
    p.add_argument("--name", default="osintinel", help="server key in the config")
    p.add_argument("--profile", default="ollama", help="OSINTINEL_INFERENCE_PROFILE")
    p.add_argument("--net", default="live", help="OSINTINEL_NET (live|record|replay)")
    p.add_argument("--reason-profile", default=None, help="route the reasoning tier to a profile")
    p.add_argument("--command", default=None, help="override the server command (absolute path)")
    p.add_argument("--env", action="append", help="extra KEY=VALUE env (repeatable)")
    p.add_argument("--config", default=None, help="config file path (defaults to Claude Desktop)")
    p.add_argument("--print", dest="print_only", action="store_true", help="print JSON; write nothing")
    p.add_argument("--dry-run", action="store_true", help="show what would change; write nothing")
    args = p.parse_args(argv)

    entry = build_entry(args)
    if not args.command and not shutil.which("osintinel"):
        print("note: 'osintinel' not on PATH — using "
              f"'{entry['command']} {' '.join(entry['args'])}'. If that python lacks the package, "
              "run 'pip install -e .' in the repo first, or pass --command /abs/path/to/osintinel.")

    if args.print_only:
        print(json.dumps({"mcpServers": {args.name: entry}}, indent=2))
        return 0

    config_path = Path(args.config) if args.config else default_config_path()
    config: dict = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8")) or {}
        except json.JSONDecodeError:
            print(f"error: {config_path} is not valid JSON; fix or move it first.")
            return 1
    servers = config.setdefault("mcpServers", {})
    existed = args.name in servers
    servers[args.name] = entry

    rendered = json.dumps(config, indent=2)
    if args.dry_run:
        print(f"[dry-run] would write {config_path}:\n{rendered}")
        return 0

    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        backup = config_path.with_suffix(config_path.suffix + ".bak")
        shutil.copy2(config_path, backup)
        print(f"backed up existing config → {backup}")
    config_path.write_text(rendered + "\n", encoding="utf-8")

    print(f"{'updated' if existed else 'added'} MCP server '{args.name}' in {config_path}")
    print(f"  command: {entry['command']} {' '.join(entry['args'])}")
    print(f"  env: {entry['env']}")
    print("\nNext: fully quit and reopen Claude Desktop, then ask it: "
          "\"Use osintinel's models_status tool.\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
