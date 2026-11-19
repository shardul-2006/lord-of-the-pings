"""The whole test suite runs with outbound network blocked (tests/conftest.py)."""

import socket
import urllib.request

import pytest

from tests.conftest import NetworkBlockedError


def test_outbound_connection_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkBlockedError):
            s.connect(("93.184.216.34", 80))
    finally:
        s.close()


def test_dns_and_http_blocked():
    with pytest.raises(OSError):
        socket.getaddrinfo("example.com", 443)
    with pytest.raises(OSError):
        urllib.request.urlopen("https://example.com", timeout=2)


def test_loopback_still_works():
    a, b = socket.socketpair()
    try:
        a.sendall(b"ok")
        assert b.recv(2) == b"ok"
    finally:
        a.close()
        b.close()


def test_real_llm_cannot_be_reached_from_tests(monkeypatch):
    from rag_shield.rag.llm import RealLLM

    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-value")
    with pytest.raises(OSError):
        RealLLM("openai", "some-model").generate("hello")
