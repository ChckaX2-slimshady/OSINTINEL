"""Web research adapters (doc 05 `web.*`) — autonomous open-web evidence gathering."""

from .search import WebSearchAdapter, registrable_domain, strip_html

__all__ = ["WebSearchAdapter", "registrable_domain", "strip_html"]
