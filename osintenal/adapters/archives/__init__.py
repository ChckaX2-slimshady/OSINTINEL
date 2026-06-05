"""Archive & reference-archive adapters (doc 05 §4, `archive.*`)."""

from .wayback import WaybackAdapter
from .wikidata import WikidataAdapter

__all__ = ["WaybackAdapter", "WikidataAdapter"]
