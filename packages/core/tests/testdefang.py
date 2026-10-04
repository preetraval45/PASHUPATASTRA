"""R115: an indicator is rendered so that nothing downstream can resolve it,
and the live value survives the round trip."""

from __future__ import annotations

import pytest

from pashupatastra.defang import (
    defang,
    defang_value,
    is_documentation_address,
    is_routable,
    refang,
)

LIVE = [
    "http://113.221.25.94:57880/i/Mozi.m",
    "https://evil.example.com/payload.exe",
    "45.61.184.22",
    "malware-host.example.org",
    "user@phish.example.net",
    "ftp://files.example.io/drop",
]


@pytest.mark.parametrize("value", LIVE)
def test_defanging_round_trips(value: str) -> None:
    """The inverse has to be exact: the lookup is keyed by the live value, and
    an analyst who needs the real thing gets it back by asking."""
    assert refang(defang(value)) == value


@pytest.mark.parametrize("value", LIVE)
def test_nothing_live_survives_defanging(value: str) -> None:
    """The property the filter cares about, stated as the test: no dot
    followed by a word character, no scheme a browser will act on."""
    defanged = defang(value)
    assert "://" not in defanged or defanged.split("://")[0] in ("hxxp", "hxxps", "fxp")
    assert not any(
        part and part[0].isalnum()
        for part in defanged.replace("[.]", "\x00").split(".")[1:]
    ), f"{defanged} still carries a live dot"


def test_defanging_is_idempotent() -> None:
    """It runs at a serialisation boundary, and a value can reach it twice."""
    once = defang("http://evil.example.com")
    assert defang(once) == once
    assert refang(once) == "http://evil.example.com"


def test_the_shapes_are_the_conventional_ones() -> None:
    """Not an invention: this is how the feeds themselves publish, which is
    why an analyst reads it without being told."""
    assert defang("http://evil.example.com") == "hxxp://evil[.]example[.]com"
    assert defang("https://a.b") == "hxxps://a[.]b"
    assert defang("45.61.184.22") == "45[.]61[.]184[.]22"
    assert defang("user@phish.example.net") == "user[@]phish[.]example[.]net"


def test_a_documentation_address_is_left_alone() -> None:
    """RFC 5737 addresses exist to be written down and cannot route. Defanging
    them would make a scripted scenario harder to read for no gain."""
    for address in ("192.0.2.1", "198.51.100.74", "203.0.113.22"):
        assert is_documentation_address(address)
        assert defang_value(address) == address
        assert not is_routable(address)


def test_a_routable_address_is_defanged_even_in_a_scenario() -> None:
    """The judgement is not ours to make per value: the filter reading the
    page is not making it either."""
    assert is_routable("45.61.184.22")
    assert defang_value("45.61.184.22") == "45[.]61[.]184[.]22"


def test_private_and_loopback_are_not_routable() -> None:
    for address in ("10.0.0.1", "192.168.1.1", "127.0.0.1", "169.254.1.1"):
        assert not is_routable(address)


def test_a_version_number_is_not_mistaken_for_an_address() -> None:
    assert not is_routable("1.2.3")
    assert not is_documentation_address("not-an-address")


def test_defanging_leaves_prose_readable() -> None:
    """It runs over whole strings, so a sentence carrying an indicator must
    survive it — the reader still has to be able to read the line."""
    text = "Beacon to 45.61.184.22 every 60s, then http://evil.example/p.exe"
    defanged = defang(text)
    assert "45[.]61[.]184[.]22" in defanged
    assert "hxxp://evil[.]example/p[.]exe" in defanged
    assert refang(defanged) == text
