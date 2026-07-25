"""Prompt-injection detection over untrusted text (docs/PROMPT_INJECTION_DEFENCE.md).

Document content and email bodies are untrusted input from the moment they
enter the system — this is a heuristic pattern scanner, not a guarantee, and
is explicitly documented as such. It flags suspicious text for logging/review;
the actual defense against a successful injection is structural (typed tool
schemas, human approval before anything irreversible — see
docs/SECURITY_MODEL.md §6), not this scanner. This module is a detector, not a
preventer.
"""

import re
from dataclasses import dataclass

_IGNORE_INSTRUCTIONS = re.compile(
    r"\bignore (all |the )?(previous|prior|above) instructions?\b", re.I
)
_REVEAL_SECRETS = re.compile(
    r"\b(reveal|disclose|print|show)\b.{0,20}\b(secret|password|api key|token|credential)", re.I
)
_EXECUTE_COMMANDS = re.compile(r"\b(execute|run)\b.{0,20}\b(command|script|code|shell)\b", re.I)
_CHANGE_SYSTEM_BEHAVIOUR = re.compile(
    r"\byou are now\b|\bnew instructions?\b|\bsystem prompt\b|\bact as\b", re.I
)
_CONTACT_EXTERNAL_SERVICES = re.compile(
    r"\b(send|forward|email|post)\b.{0,30}\b(to|at)\b.{0,10}(http|www\.|@)", re.I
)
_OVERRIDE_ROLE = re.compile(r"\bdisregard (your|the) (role|guidelines|rules)\b", re.I)

_SUSPICIOUS_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ignore_instructions", _IGNORE_INSTRUCTIONS),
    ("reveal_secrets", _REVEAL_SECRETS),
    ("execute_commands", _EXECUTE_COMMANDS),
    ("change_system_behaviour", _CHANGE_SYSTEM_BEHAVIOUR),
    ("contact_external_services", _CONTACT_EXTERNAL_SERVICES),
    ("override_role", _OVERRIDE_ROLE),
]


@dataclass(frozen=True)
class InjectionFlag:
    pattern_name: str
    matched_text: str


def scan_for_prompt_injection(text: str) -> list[InjectionFlag]:
    flags = []
    for name, pattern in _SUSPICIOUS_PATTERNS:
        match = pattern.search(text)
        if match:
            flags.append(InjectionFlag(pattern_name=name, matched_text=match.group(0)))
    return flags
