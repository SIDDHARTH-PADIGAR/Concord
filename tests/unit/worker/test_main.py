"""Tests for the worker entrypoint's consumer-name resolution."""

import socket

import pytest

from concord_worker.main import _consumer_name


def test_uses_env_var_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONCORD_WORKER_CONSUMER_NAME", "worker-custom")
    assert _consumer_name() == "worker-custom"


def test_falls_back_to_hostname_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONCORD_WORKER_CONSUMER_NAME", raising=False)
    assert _consumer_name() == socket.gethostname()
