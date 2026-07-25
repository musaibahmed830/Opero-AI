"""Sensitive-case detection for draft generation (docs/EMAIL_INTELLIGENCE.md
"Sensitive email cases"). A deterministic heuristic scan — like
app/services/prompt_injection.py, this flags for a human reviewer's
attention; it does not itself block or alter what the model produces.
"""

import re

_REFUND_REQUEST = re.compile(r"\brefund\b|\bmoney back\b", re.I)
_LEGAL_THREAT = re.compile(r"\blawsuit\b|\blegal action\b|\battorney\b|\bsue (you|us)\b", re.I)
_PAYMENT_DISPUTE = re.compile(
    r"\bchargeback\b|\bdispute(d)? (the|this|my) (charge|payment|invoice)\b", re.I
)
_ACCOUNT_TERMINATION = re.compile(
    r"\bcancel (my|our) account\b|\bterminate\b|\bclose my account\b", re.I
)
_SECURITY_INCIDENT = re.compile(
    r"\bdata breach\b|\bhacked\b|\bsecurity incident\b|\bunauthorized access\b", re.I
)
_PERSONAL_DATA_REQUEST = re.compile(
    r"\bgdpr\b|\bdelete my data\b|\bmy personal (data|information)\b", re.I
)
_HARASSMENT = re.compile(r"\bharass(ment|ed)?\b|\bthreaten(ing|ed)?\b|\babusive\b", re.I)
_HIGH_VALUE_CONTRACT = re.compile(r"\benterprise (deal|contract|agreement)\b|\$[0-9]{5,}", re.I)

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("refund_request", _REFUND_REQUEST),
    ("legal_threat", _LEGAL_THREAT),
    ("payment_dispute", _PAYMENT_DISPUTE),
    ("account_termination", _ACCOUNT_TERMINATION),
    ("security_incident", _SECURITY_INCIDENT),
    ("personal_data_request", _PERSONAL_DATA_REQUEST),
    ("harassment", _HARASSMENT),
    ("high_value_contract", _HIGH_VALUE_CONTRACT),
]


def detect_sensitive_flags(email_body: str) -> list[str]:
    return [name for name, pattern in _PATTERNS if pattern.search(email_body)]
