"""EXIF adapter (doc 05 §4 ``media.exif``) — the image-binary acquisition path.

Unlike the network adapters, this one's artifact is a *local image file*: the raw bytes are
pushed into the content-addressed store (the heavy-artifact rule, doc 05 §5.6) and only their
hash travels onward, while the small structured EXIF (camera, timestamp, GPS) becomes evidence.
``parse``/``normalize`` are pure; the binary decoding lives in ``media.exif``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...core.schemas import AcquisitionMethod, EvidenceObject, Provenance
from ..base import CollectTarget, RawArtifact, RawHit, ReferenceAdapter
from ..storage import ContentAddressedStore
from .exif import parse_exif

SOURCE = "EXIF (image metadata)"


class ExifAdapter(ReferenceAdapter):
    id = "media.exiftool"
    capabilities = ["media.exif", "media.metadata"]
    license_note = "metadata extracted from the operator-provided image"

    def __init__(self, cas: ContentAddressedStore) -> None:
        super().__init__(client=None, cas=cas)

    def _bytes(self, target: CollectTarget) -> bytes:
        if "bytes" in target.arguments:
            return target.arguments["bytes"]
        return Path(target.arguments["path"]).read_bytes()

    def search(self, capability: str, arguments: dict[str, Any]) -> list[RawHit]:
        # A local artifact: "discovery" is trivially the image itself.
        return [RawHit(hit_id="image", capability=capability, payload=arguments)]

    def collect(self, target: CollectTarget) -> RawArtifact:
        data = self._bytes(target)
        digest = self.cas.put(data)  # image bytes -> CAS (heavy artifact off the ledger)
        return RawArtifact(
            capability="media.exif", source=SOURCE, url=None,
            content_hash=digest, payload_ref=self.cas.ref(digest),
            structured={"bytes": len(data), "exif": parse_exif(data)},
            license_note=self.license_note)

    def parse(self, raw: RawArtifact) -> list[dict[str, Any]]:
        exif = raw.structured.get("exif", {})
        return [{
            "exif": exif, "gps": exif.get("gps"),
            "datetime_original": exif.get("datetime_original"),
            "make": exif.get("make"), "model": exif.get("model"),
            "content_hash": raw.content_hash, "payload_ref": raw.payload_ref,
            "bytes": raw.structured["bytes"],
        }]

    def normalize(self, parsed: dict[str, Any], provenance: Provenance) -> EvidenceObject:
        self._stamp(provenance, source=SOURCE, method=AcquisitionMethod.FILE_UPLOAD,
                    content_hash=parsed["content_hash"])
        gps = parsed["gps"]
        loc = f"GPS {gps['lat']:.5f}, {gps['lon']:.5f}" if gps else "no embedded GPS"
        cam = " ".join(p for p in (parsed["make"], parsed["model"]) if p) or "unknown camera"
        return EvidenceObject(
            kind="exif",
            summary=f"EXIF from {cam}: {loc}; captured {parsed['datetime_original'] or 'unknown'}.",
            payload_ref=parsed["payload_ref"],  # the image bytes live in the CAS
            structured={
                "gps": gps, "datetime_original": parsed["datetime_original"],
                "make": parsed["make"], "model": parsed["model"],
                "independence_group": "exif",
            },
            provenance=provenance,
        )

    def acquire_image(self, image_bytes: bytes, provenance: Provenance) -> list[EvidenceObject]:
        """Convenience: EXIF-extract an in-memory image, emitting one evidence object."""
        self.last_artifact = self.collect(CollectTarget(hit_id="image",
                                                        arguments={"bytes": image_bytes}))
        return self._emit(provenance)
