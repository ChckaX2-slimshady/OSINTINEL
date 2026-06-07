"""Geospatial adapters (doc 05 §4, `geo.*`)."""

from .nominatim import NominatimAdapter
from .overpass import OverpassAdapter

__all__ = ["NominatimAdapter", "OverpassAdapter"]
