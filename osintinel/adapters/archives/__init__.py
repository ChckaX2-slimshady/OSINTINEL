"""Archive & reference-archive adapters (doc 05 §4, `archive.*`)."""

from .commons import WikimediaCommonsAdapter
from .wayback import WaybackAdapter
from .wikidata import WikidataAdapter

__all__ = ["WaybackAdapter", "WikidataAdapter", "WikimediaCommonsAdapter"]
