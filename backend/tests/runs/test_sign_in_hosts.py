"""Sign-in takeovers may open public hosts (an identity provider) and remember them; private ones stay blocked
(ADR 0012, #477). DNS is stubbed: no network."""

import socket
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.runs.takeover import TakeoverSession, is_public_host

pytestmark = pytest.mark.anyio

RESOLVES = {
    "accounts.example": ["93.184.216.34"],
    "rebind.example": ["93.184.216.34", "10.0.0.7"],  # one private answer is enough to refuse
    "intranet.example": ["192.168.1.20"],
}


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def getaddrinfo(name: str, *_: Any) -> list[Any]:
        if name not in RESOLVES:
            raise socket.gaierror("unknown")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in RESOLVES[name]]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@pytest.mark.parametrize(
    ("host", "public"),
    [
        ("8.8.8.8", True),
        ("accounts.example", True),
        ("127.0.0.1", False),
        ("10.1.2.3", False),
        ("169.254.169.254", False),  # cloud metadata
        ("[::1]", False),
        ("localhost", False),
        ("printer.local", False),
        ("rebind.example", False),
        ("intranet.example", False),
        ("nowhere.example", False),  # doesn't resolve
    ],
)
async def test_public_hosts(host: str, public: bool) -> None:
    assert await is_public_host(host) is public


def session(*, open_sign_in: bool, visits: list[str] | None = None) -> TakeoverSession:
    async def on_end(_reason: str) -> None:
        return None

    return TakeoverSession(
        MagicMock(),
        allowed_hosts=["site.example"],
        on_end=on_end,
        open_sign_in=open_sign_in,
        on_visit=visits.append if visits is not None else None,
    )


async def test_a_sign_in_takeover_may_open_an_identity_provider() -> None:
    visits: list[str] = []
    s = session(open_sign_in=True, visits=visits)

    assert await s.permitted("https://site.example/login")
    assert await s.permitted("https://accounts.example/o/oauth2/auth?client_id=x")
    assert not await s.permitted("http://intranet.example/admin")
    assert not await s.permitted("http://169.254.169.254/latest/meta-data")
    assert not await s.permitted("file:///etc/passwd")
    assert visits == ["accounts.example"]


async def test_other_takeovers_stay_on_the_site() -> None:
    s = session(open_sign_in=False)

    assert await s.permitted("https://site.example/x")
    assert not await s.permitted("https://accounts.example/o/oauth2/auth")
