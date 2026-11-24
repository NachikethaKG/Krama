"""Sites Krama refuses to work on (ADR 0012, AGENTS.md §4): banking, payments, government identity, health.

Checked before planning a task and before a sign-in, from the URL alone: Krama never opens such a site.
A list of well-known hosts plus words in the host name; it can't know every bank, so it errs towards refusing
a host that names itself a bank or a pay service. The owner sees why.
"""

import re
from urllib.parse import urlsplit

# Hosts (and their subdomains) of large services in the refused kinds.
_HOSTS: dict[str, str] = {
    "paypal.com": "payments",
    "stripe.com": "payments",
    "razorpay.com": "payments",
    "paytm.com": "payments",
    "phonepe.com": "payments",
    "venmo.com": "payments",
    "wise.com": "payments",
    "revolut.com": "banking",
    "chase.com": "banking",
    "bankofamerica.com": "banking",
    "wellsfargo.com": "banking",
    "hsbc.com": "banking",
    "barclays.co.uk": "banking",
    "onlinesbi.sbi": "banking",
    "hdfcbank.com": "banking",
    "icicibank.com": "banking",
    "axisbank.com": "banking",
    "coinbase.com": "banking",
    "binance.com": "banking",
    "irs.gov": "government identity",
    "login.gov": "government identity",
    "uidai.gov.in": "government identity",
    "incometax.gov.in": "government identity",
    "passportindia.gov.in": "government identity",
    "gov.uk": "government identity",
    "healthcare.gov": "health",
    "mychart.com": "health",
    "practo.com": "health",
}

# Words in a host name that say what the site is. A host's labels (split at "." and "-") are checked: a label
# ending in "bank" or "banking" (mybank, onlinebanking), or one that is exactly a payment or health word.
_BANK_ENDINGS = ("bank", "banking")
_WHOLE_LABELS: dict[str, str] = {
    **dict.fromkeys(("pay", "payment", "payments", "checkout", "wallet", "upi"), "payments"),
    **dict.fromkeys(("health", "patient", "patients", "hospital", "clinic", "pharmacy"), "health"),
}


def sensitive_site(url: str) -> str | None:
    """The kind of sensitive site `url` is (banking, payments, government identity, health), or None."""
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    if not host:
        return None
    for known, kind in _HOSTS.items():
        if host == known or host.endswith("." + known):
            return kind
    if host.endswith(".gov") or ".gov." in host or host.endswith(".gov.in"):
        return "government identity"
    for label in re.split(r"[.-]", host):
        if label.endswith(_BANK_ENDINGS):
            return "banking"
        if label in _WHOLE_LABELS:
            return _WHOLE_LABELS[label]
    return None


def refusal(url: str) -> str | None:
    """The message for a refused site, or None if Krama may work on it."""
    kind = sensitive_site(url)
    if kind is None:
        return None
    return f"Krama doesn't work on {kind} sites, to keep your money, identity and health data safe."
