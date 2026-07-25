from typing import Annotated

from pydantic import BeforeValidator, Field


def _normalize_percentage(value: object) -> object:
    """Open-weight models occasionally answer a "confidence" field on a 0-100
    scale despite the schema/prompt asking for 0-1 (observed live against
    qwen2.5:7b-instruct during email classification, not hypothetical).
    Normalizing here — once — means every schema that has a confidence field
    gets the same defensive handling instead of duplicating this quirk-fix
    per schema. Still bounded by each field's own `ge=0.0, le=1.0`, so a truly
    out-of-range value fails validation loudly rather than being silently
    accepted.
    """
    if isinstance(value, int | float) and value > 1:
        return value / 100
    return value


Confidence = Annotated[float, BeforeValidator(_normalize_percentage), Field(ge=0.0, le=1.0)]
