import socket
from pathlib import Path

import pytest

from scripts.make_fixtures import main as make_fixtures

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


class NetworkBlockedError(OSError):
    """Raised for any non-loopback connection or DNS lookup during tests."""


def _is_local(host) -> bool:
    host = str(host)
    return host in LOCAL_HOSTS or host.startswith("127.")


def _block_network() -> None:
    """Block outbound network for the whole test session. Loopback stays allowed: asyncio on
    Windows builds its self-pipe from a local TCP socket pair."""
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex
    real_getaddrinfo, real_create = socket.getaddrinfo, socket.create_connection

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_local(address[0]):
            raise NetworkBlockedError(f"network blocked in tests: {address}")
        return real_connect(self, address)

    def connect_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_local(address[0]):
            raise NetworkBlockedError(f"network blocked in tests: {address}")
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_local(host):
            raise NetworkBlockedError(f"DNS blocked in tests: {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    def create_connection(address, *args, **kwargs):
        if not _is_local(address[0]):
            raise NetworkBlockedError(f"network blocked in tests: {address}")
        return real_create(address, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo
    socket.create_connection = create_connection


def pytest_configure(config):
    _block_network()


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    make_fixtures(["--out", str(FIXTURES)])
    return FIXTURES


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never let tests write a ledger or forensic copies into the real home directory."""
    home = tmp_path / "rag_shield_home"
    monkeypatch.setenv("RAG_SHIELD_HOME", str(home))
    for var in ("RAG_SHIELD_LLM", "RAG_SHIELD_LLM_MODEL", "RAG_SHIELD_MAX_BYTES",
                "RAG_SHIELD_MAX_PAGES", "RAG_SHIELD_SCAN_TIMEOUT", "RAG_SHIELD_DATASET_TIMEOUT"):
        monkeypatch.delenv(var, raising=False)
    return home
