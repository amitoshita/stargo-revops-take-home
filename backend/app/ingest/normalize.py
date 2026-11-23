"""Normalization rules from ql_standard.md §3: emails, LinkedIn URLs, domains, countries."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.core.enums import Region

# Multi-part public suffixes we must keep whole (QLS §3 names .co.uk, .com.sg, .co.il).
# A small built-in list instead of the full Public Suffix List; see docs/ASSUMPTIONS.md.
MULTI_PART_SUFFIXES: frozenset[str] = frozenset(
    {
        "co.uk", "org.uk", "ac.uk", "gov.uk", "ltd.uk", "plc.uk",
        "com.sg", "edu.sg", "gov.sg", "org.sg", "net.sg",
        "co.il", "org.il", "ac.il", "gov.il", "net.il",
        "com.au", "net.au", "org.au", "co.nz", "co.jp", "co.kr",
        "com.hk", "com.cn", "com.tw", "com.my", "co.in", "com.br", "co.za",
    }
)  # fmt: skip

FREE_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
        "yahoo.com", "ymail.com", "icloud.com", "me.com", "aol.com", "proton.me",
        "protonmail.com", "gmx.de", "gmx.net", "web.de", "mail.com", "yandex.com",
        "zoho.com", "walla.co.il",
    }
)  # fmt: skip

_EMAIL_RE = re.compile(r"^[a-z0-9._%+'-]+@([a-z0-9-]+\.)+[a-z]{2,}$")
_LINKEDIN_PATH_RE = re.compile(r"^/in/([a-z0-9][a-z0-9_%-]*)/?$")
_LABEL_RE = re.compile(r"^[a-z0-9-]+$")


def normalize_email(value: str | None) -> str | None:
    """Trim and lowercase. Returns None for blank input; raises ValueError if invalid."""
    if value is None or not value.strip():
        return None
    email = value.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValueError("invalid email address")
    return email


def normalize_linkedin(value: str | None) -> str | None:
    """Canonical form `linkedin.com/in/<slug>`. Raises ValueError if not a profile URL."""
    if value is None or not value.strip():
        return None
    raw = value.strip().lower()
    if "://" not in raw:
        raw = "https://" + raw
    parts = urlsplit(raw)
    host = (parts.hostname or "").removeprefix("www.")
    if host != "linkedin.com" and not host.endswith(".linkedin.com"):
        raise ValueError("not a linkedin.com URL")
    match = _LINKEDIN_PATH_RE.match(parts.path)
    if not match:
        raise ValueError("not a LinkedIn profile URL (expected /in/<name>)")
    return f"linkedin.com/in/{match.group(1)}"


def normalize_domain(value: str | None) -> str | None:
    """Registrable domain: lowercase, no scheme/path/www/subdomains, multi-part suffix kept."""
    if value is None or not value.strip():
        return None
    raw = value.strip().lower()
    if "://" in raw:
        raw = urlsplit(raw).hostname or ""
    raw = raw.split("/")[0].split(":")[0].strip(".")
    labels = [label for label in raw.split(".") if label]
    if len(labels) < 2 or not all(_LABEL_RE.match(label) for label in labels):
        return None
    last_two = ".".join(labels[-2:])
    if last_two in MULTI_PART_SUFFIXES:
        return ".".join(labels[-3:]) if len(labels) >= 3 else None
    return last_two


def email_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return normalize_domain(email.rsplit("@", 1)[1])


def is_free_email_domain(domain: str | None) -> bool:
    return domain is not None and domain in FREE_EMAIL_DOMAINS


_COUNTRY_ALIASES: dict[str, str] = {
    "nl": "NL", "netherlands": "NL", "the netherlands": "NL", "holland": "NL",
    "be": "BE", "belgium": "BE",
    "lu": "LU", "luxembourg": "LU",
    "se": "SE", "sweden": "SE", "no": "NO", "norway": "NO", "dk": "DK", "denmark": "DK",
    "fi": "FI", "finland": "FI", "is": "IS", "iceland": "IS",
    "uk": "GB", "gb": "GB", "united kingdom": "GB", "great britain": "GB", "england": "GB",
    "scotland": "GB", "wales": "GB",
    "de": "DE", "germany": "DE", "deutschland": "DE", "at": "AT", "austria": "AT",
    "ch": "CH", "switzerland": "CH",
    "sg": "SG", "singapore": "SG",
    "us": "US", "usa": "US", "united states": "US", "united states of america": "US",
    "il": "IL", "israel": "IL",
    "fr": "FR", "france": "FR", "es": "ES", "spain": "ES", "it": "IT", "italy": "IT",
    "pl": "PL", "poland": "PL", "ie": "IE", "ireland": "IE", "pt": "PT", "portugal": "PT",
    "au": "AU", "australia": "AU", "jp": "JP", "japan": "JP", "hk": "HK", "hong kong": "HK",
    "my": "MY", "malaysia": "MY", "cn": "CN", "china": "CN", "in": "IN", "india": "IN",
    "kr": "KR", "south korea": "KR", "th": "TH", "thailand": "TH", "vn": "VN", "vietnam": "VN",
    "id": "ID", "indonesia": "ID", "ph": "PH", "philippines": "PH", "tw": "TW", "taiwan": "TW",
    "nz": "NZ", "new zealand": "NZ", "ca": "CA", "canada": "CA", "mx": "MX", "mexico": "MX",
    "br": "BR", "brazil": "BR", "ae": "AE", "united arab emirates": "AE", "uae": "AE",
}  # fmt: skip

_REGION_BY_COUNTRY: dict[str, Region] = {
    "NL": Region.BENELUX, "BE": Region.BENELUX, "LU": Region.BENELUX,
    "SE": Region.NORDICS, "NO": Region.NORDICS, "DK": Region.NORDICS, "FI": Region.NORDICS,
    "IS": Region.NORDICS,
    "GB": Region.UK,
    "DE": Region.DACH, "AT": Region.DACH, "CH": Region.DACH,
    "SG": Region.SINGAPORE,
    "US": Region.US,
    "IL": Region.ISRAEL,
    "AU": Region.APAC_OTHER, "JP": Region.APAC_OTHER, "HK": Region.APAC_OTHER,
    "MY": Region.APAC_OTHER, "CN": Region.APAC_OTHER, "IN": Region.APAC_OTHER,
    "KR": Region.APAC_OTHER, "TH": Region.APAC_OTHER, "VN": Region.APAC_OTHER,
    "ID": Region.APAC_OTHER, "PH": Region.APAC_OTHER, "TW": Region.APAC_OTHER,
    "NZ": Region.APAC_OTHER,
}  # fmt: skip

# Cities a buyer may state instead of a country (used for stated, unverified facts).
_CITY_TO_COUNTRY: dict[str, str] = {
    "haifa": "IL", "tel aviv": "IL", "jerusalem": "IL", "ashdod": "IL", "eilat": "IL",
    "rotterdam": "NL", "amsterdam": "NL", "antwerp": "BE", "brussels": "BE",
    "hamburg": "DE", "bremen": "DE", "frankfurt": "DE", "munich": "DE", "berlin": "DE",
    "vienna": "AT", "zurich": "CH", "basel": "CH", "geneva": "CH",
    "london": "GB", "manchester": "GB", "felixstowe": "GB", "southampton": "GB",
    "copenhagen": "DK", "stockholm": "SE", "gothenburg": "SE", "oslo": "NO", "helsinki": "FI",
    "singapore": "SG",
    "new york": "US", "chicago": "US", "dallas": "US", "los angeles": "US", "miami": "US",
    "houston": "US", "atlanta": "US", "seattle": "US",
}  # fmt: skip


def normalize_country(value: str | None) -> str | None:
    """ISO-3166 alpha-2 code, or None if blank or unrecognised (unknown stays unknown)."""
    if value is None or not value.strip():
        return None
    key = value.strip().lower().rstrip(".")
    return _COUNTRY_ALIASES.get(key) or _CITY_TO_COUNTRY.get(key)


def country_from_text(value: str | None) -> str | None:
    """Find a known country or city name inside free text (e.g. 'customs brokerage in Haifa')."""
    if not value:
        return None
    lowered = value.lower()
    for name, code in {**_CITY_TO_COUNTRY, **_COUNTRY_ALIASES}.items():
        if len(name) > 3 and re.search(rf"\b{re.escape(name)}\b", lowered):
            return code
    return None


def _country_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for alias, code in _COUNTRY_ALIASES.items():
        if len(alias) > 3:
            names.setdefault(code, alias.title())
    return names


def stated_country_name(value: str | None) -> str | None:
    """A stated location as a country name: 'Haifa' -> 'Israel'. Unrecognised text is kept."""
    if value is None or not value.strip():
        return None
    if value.strip().lower().rstrip(".") in _COUNTRY_ALIASES:
        return value.strip()
    code = normalize_country(value) or country_from_text(value)
    return _country_names().get(code, value.strip()) if code else value.strip()


def region_for_country(country: str | None) -> Region | None:
    if country is None:
        return None
    return _REGION_BY_COUNTRY.get(country, Region.OTHER)


def display_country(country: str | None) -> str | None:
    return "UK" if country == "GB" else country


_VERTICAL_ALIASES: dict[str, str] = {
    "freight-forwarder": "freight-forwarder", "forwarder": "freight-forwarder",
    "freight-forwarding": "freight-forwarder",
    "carrier": "carrier", "ocean-carrier": "carrier", "shipping-line": "carrier",
    "3pl": "3pl", "third-party-logistics": "3pl", "logistics-provider": "3pl",
    "trucking": "trucking", "haulage": "trucking", "road-freight": "trucking",
    "air-cargo": "air-cargo", "ground-handling": "ground-handling",
    "ground-handler": "ground-handling",
    "customs-broker": "customs-broker", "customs-brokerage": "customs-broker",
    "shipper": "shipper", "retail": "shipper", "manufacturer": "shipper",
    "trade-finance": "trade-finance",
}  # fmt: skip

ICP_VERTICALS: frozenset[str] = frozenset(
    {
        "freight-forwarder", "carrier", "3pl", "trucking", "air-cargo", "ground-handling",
        "customs-broker", "shipper", "trade-finance",
    }
)  # fmt: skip

VENDOR_VERTICALS: frozenset[str] = frozenset({"software-vendor", "software", "saas"})


def normalize_vertical(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    slug = re.sub(r"[\s_/]+", "-", value.strip().lower())
    return _VERTICAL_ALIASES.get(slug, slug)
