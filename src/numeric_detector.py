"""Detect claims that assert a computed quantity from the claim statement alone.
Using regex to find which claim belongs in the numeric subset and thus needs escalation to cloud."""

import re

# A number with an optional dollar sign, or digits with thousands separators, and an optional decimal part.
_NUMBER = r"(?:\$\s?)?\d[\d,]*(?:\.\d+)?"

# What might trail a number (optional)
_UNITS = (
    r"(?:\s?%"
    r"|\s+percent(?:age)?(?:\s+points?)?"
    r"|\s+(?:million|billion|thousand|dollars?|days|years|shares|square\s+feet)\b"
    r")?"
)

# words the numeric claims put in front of the value (optional)
_HEDGE = (
    r"(?:precisely|exactly|approximately|nearly|about|roughly"
    r"|more\s+than|less\s+than)?"
)