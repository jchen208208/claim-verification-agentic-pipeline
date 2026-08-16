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

_PATTERNS = (
    # 1.) claim ends with "is <number>."
    r"\b(?:is|was|are|were)\s+" + _HEDGE + r"\s*" + _NUMBER + _UNITS + r"[^.]{0,15}\.?\s*$",

    # 2.) claim contains the word "percentage".
    r"\bpercentage\b",

    # 3.) claim contains "is approximately" / "precisely" / "exactly".
    r"\b(?:is|was)\s+(?:approximately|precisely|exactly|nearly|roughly)\b",
)

# join with "|" so one pass over the string tests all three.
_DETECTOR = re.compile("|".join(_PATTERNS), re.IGNORECASE)