"""Deterministic parsing of email header fields — no model call needed, and
none should be used: the sender's name/address are already known facts from
the message itself, not something to infer (docs/EMAIL_INTELLIGENCE.md "Lead
extraction" — an earlier draft asked the model to "extract" these and it
unreliably omitted them even when correctly reading the rest of the email;
the fix is to stop asking a model to echo back data we already have).
"""

import re

_NAME_EMAIL_PATTERN = re.compile(r"^\s*(?P<name>[^<]*?)\s*<(?P<email>[^>]+)>\s*$")


def parse_sender(sender: str) -> tuple[str | None, str]:
    """Returns (display_name_or_None, email_address) from a "Name <email>" or
    bare "email" header string.
    """
    match = _NAME_EMAIL_PATTERN.match(sender)
    if match:
        name = match.group("name").strip().strip('"') or None
        return name, match.group("email").strip()
    return None, sender.strip()
