from __future__ import annotations

import pytest

from app.core.enums import Region
from app.ingest.normalize import (
    country_from_text,
    email_domain,
    is_free_email_domain,
    normalize_country,
    normalize_domain,
    normalize_email,
    normalize_linkedin,
    normalize_vertical,
    region_for_country,
    stated_country_name,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("www.NordhavenFreight.com", "nordhavenfreight.com"),
        ("nl.nordhavenfreight.com", "nordhavenfreight.com"),
        ("meridianhaulage.co.uk", "meridianhaulage.co.uk"),
        ("mail.meridianhaulage.co.uk", "meridianhaulage.co.uk"),
        ("lionport.com.sg", "lionport.com.sg"),
        ("www.ashdodbay.co.il", "ashdodbay.co.il"),
        ("https://www.stargo.co/rate-quoting", "stargo.co"),
        ("halden-fwd.de", "halden-fwd.de"),
        ("asdf", None),
        ("", None),
        (None, None),
        ("co.uk", None),
    ],
)
def test_normalize_domain(raw: str | None, expected: str | None) -> None:
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Anouk.DeVries@NordhavenFreight.com", "anouk.devries@nordhavenfreight.com"),
        ("  Greta.Holm@balticacargo.eu ", "greta.holm@balticacargo.eu"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_email(raw: str | None, expected: str | None) -> None:
    assert normalize_email(raw) == expected


@pytest.mark.parametrize("raw", ["asdf@asdf", "no-at-sign.com", "a@b@c.com", "x@.com"])
def test_invalid_email_raises(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_email(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.linkedin.com/in/pieterclaes-bcl/", "linkedin.com/in/pieterclaes-bcl"),
        ("https://www.linkedin.com/in/pieterclaes-bcl", "linkedin.com/in/pieterclaes-bcl"),
        ("https://linkedin.com/in/TomBecker-Logistics", "linkedin.com/in/tombecker-logistics"),
        ("linkedin.com/in/someone?utm=x", "linkedin.com/in/someone"),
        ("https://nl.linkedin.com/in/anouk-devries-nf/", "linkedin.com/in/anouk-devries-nf"),
        (None, None),
    ],
)
def test_normalize_linkedin(raw: str | None, expected: str | None) -> None:
    assert normalize_linkedin(raw) == expected


@pytest.mark.parametrize(
    "raw", ["https://example.com/in/x", "https://linkedin.com/company/x", "linkedin.com/in/"]
)
def test_invalid_linkedin_raises(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_linkedin(raw)


def test_free_domains() -> None:
    assert is_free_email_domain(email_domain("yossi.mizrahi@gmail.com"))
    assert is_free_email_domain(email_domain("lior.bd@outlook.com"))
    assert not is_free_email_domain(email_domain("noam@ashdodbay.co.il"))


@pytest.mark.parametrize(
    ("raw", "code", "region"),
    [
        ("NL", "NL", Region.BENELUX),
        ("Netherlands", "NL", Region.BENELUX),
        ("United Kingdom", "GB", Region.UK),
        ("UK", "GB", Region.UK),
        ("DE", "DE", Region.DACH),
        ("SG", "SG", Region.SINGAPORE),
        ("Japan", "JP", Region.APAC_OTHER),
        ("France", "FR", Region.OTHER),
        ("Haifa", "IL", Region.ISRAEL),
    ],
)
def test_country_and_region(raw: str, code: str, region: Region) -> None:
    assert normalize_country(raw) == code
    assert region_for_country(code) == region


def test_unknown_country_stays_unknown() -> None:
    assert normalize_country("") is None
    assert normalize_country("Atlantis") is None
    assert region_for_country(None) is None


def test_country_from_text() -> None:
    assert country_from_text("I own a 40-person customs brokerage in Haifa.") == "IL"
    assert country_from_text("we are a forwarder") is None


def test_vertical() -> None:
    assert normalize_vertical("Freight Forwarder") == "freight-forwarder"
    assert normalize_vertical("customs brokerage") == "customs-broker"
    assert normalize_vertical("") is None


@pytest.mark.parametrize(
    ("stated", "vertical"),
    [
        ("home goods retail", "shipper"),  # found via the held-out set (H2)
        ("Home goods retailer", "shipper"),
        ("food manufacturing", "shipper"),
        ("Electronics manufacturer", "shipper"),
        ("wholesaler", "shipper"),
        ("e-commerce", "shipper"),
        ("consumer goods", "shipper"),
        ("FMCG", "shipper"),
        ("software vendor", "software-vendor"),  # not a freight buyer
        ("bank", "bank"),
        ("Freight Forwarder", "freight-forwarder"),  # exact alias wins
    ],
)
def test_freight_buyers_map_to_shipper(stated: str, vertical: str) -> None:
    assert normalize_vertical(stated) == vertical


@pytest.mark.parametrize(
    ("stated", "name"),
    [("Haifa", "Israel"), ("Rotterdam", "Netherlands"), ("London", "United Kingdom"),
     ("Israel", "Israel"), ("UK", "UK"), ("Atlantis", "Atlantis"), ("  ", None), (None, None)],
)  # fmt: skip
def test_stated_country_name(stated: str | None, name: str | None) -> None:
    assert stated_country_name(stated) == name


@pytest.mark.parametrize(
    ("stated", "vertical"),
    [
        ("logistics", "3pl"), ("Logistics provider", "3pl"), ("logistics company", "3pl"),
        ("3PL", "3pl"), ("shipping company", "carrier"), ("freight company", "freight-forwarder"),
        ("forwarding", "freight-forwarder"), ("Spedition", "freight-forwarder"),
        ("transport company", "trucking"), ("haulage company", "trucking"),
        ("cargo handling", "ground-handling"), ("customs agency", "customs-broker"),
        ("international freight forwarding and logistics", "freight-forwarder"),
        ("logistics software", "software-vendor"), ("freight consulting", "consulting"),
        ("widget services", "widget-services"),
    ],
)  # fmt: skip
def test_icp_synonyms_and_non_icp_categories(stated: str, vertical: str) -> None:
    assert normalize_vertical(stated) == vertical
