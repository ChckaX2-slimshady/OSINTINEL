"""Local MCP server: drive OSINTENAL by chatting with Claude.

A dependency-free stdio JSON-RPC server (the MCP stdio transport is newline-delimited JSON-RPC
2.0) exposing OSINTENAL as tools — ``investigate`` and ``models_status`` — so an MCP client
(Claude Desktop/Code) can run multi-agent investigations conversationally. ``handle_request`` is
a pure dispatch function (unit-tested); ``serve_stdio`` is the I/O loop.
"""

from .server import TOOLS, handle_request, serve_stdio

__all__ = ["TOOLS", "handle_request", "serve_stdio"]
