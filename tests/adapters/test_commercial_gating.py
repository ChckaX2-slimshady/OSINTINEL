"""License-gated supplemental adapters must stay off unless explicitly authorized (doc 05 §4b)."""

from __future__ import annotations

import pytest

from osintinel.adapters import Cassette, HttpClient
from osintinel.adapters.commercial import LicenseGatedAdapter, LicenseGateError, MaltegoAdapter
from osintinel.adapters.commercial.base import ATTESTATION_ENV


def _maltego(tmp_path) -> MaltegoAdapter:
    return MaltegoAdapter(HttpClient(Cassette(tmp_path / "none.json"), record=False))


def test_disabled_without_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("MALTEGO_API_KEY", raising=False)
    monkeypatch.delenv(ATTESTATION_ENV, raising=False)
    adapter = _maltego(tmp_path)
    assert adapter.is_enabled() is False
    with pytest.raises(LicenseGateError, match="credentials"):
        adapter.search("identity.profile", {"handle": "x"})


def test_credentials_without_attestation_still_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("MALTEGO_API_KEY", "secret")
    monkeypatch.delenv(ATTESTATION_ENV, raising=False)
    adapter = _maltego(tmp_path)
    assert adapter.is_enabled() is False
    with pytest.raises(LicenseGateError, match="attestation"):
        adapter.search("identity.profile", {"handle": "x"})


def test_enabled_with_credentials_and_attestation(tmp_path, monkeypatch):
    monkeypatch.setenv("MALTEGO_API_KEY", "secret")
    monkeypatch.setenv(ATTESTATION_ENV, "1")
    adapter = _maltego(tmp_path)
    assert adapter.is_enabled() is True
    # Gate passes, but no live integration is bundled — fails as "not implemented", not gated.
    with pytest.raises(NotImplementedError):
        adapter.search("identity.profile", {"handle": "x"})


def test_is_a_reference_adapter_subclass():
    assert issubclass(MaltegoAdapter, LicenseGatedAdapter)
    assert "link.analysis" in MaltegoAdapter.capabilities
