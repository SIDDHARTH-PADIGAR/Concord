"""Tests for the reconciler entrypoint's interval resolution."""

import pytest

from concord_reconciler.main import _DEFAULT_INTERVAL_SECONDS, _interval_seconds


def test_uses_env_var_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONCORD_RECONCILER_INTERVAL_SECONDS", "5")
    assert _interval_seconds() == 5.0


def test_falls_back_to_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONCORD_RECONCILER_INTERVAL_SECONDS", raising=False)
    assert _interval_seconds() == _DEFAULT_INTERVAL_SECONDS
