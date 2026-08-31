
"""A skill that re-checks claims the two local models agreed were entailed.
It runs two checks and either one escalates the claim to cloud
1.) the claim asserts a figure that appears nowhere in the report filing
2.) a call to a local model and asks it to confirm every detail or name the weakest one"""

import re

# a figure as written in a claim: 3.27, 17.1, 1,204,500
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

# any number below this is a count or an item index rather than a figure worth checking
_MIN_VALUE = 2

def _surface_forms(token: str) -> set[str]:
    # returns every way a filing might print a number with the same magnitude
    bare = token.replace(",", "")
    forms = {token, bare}
    if "." in bare:
        forms.add(bare.rstrip("0").rstrip("."))  # 8.50 is also printed as 8.5
    try:
        value = float(bare)
    except ValueError:
        return forms
    for multiplier in (1, 1000, 1000000):
        scaled = value * multiplier
        if scaled == int(scaled):
            forms.add(str(int(scaled)))
            forms.add(f"{int(scaled):,}")  # :, format specifier inserts thousands separators
    # a one-character form matches almost any text, so it would make the check useless
    return {form for form in forms if len(form) >= 2}


def claim_numbers(statement: str) -> list[str]:
    # returns all the figures a claim asserts as they are written. years and small counts are skipped
    found = []
    for token in _NUMBER.findall(statement):
        bare = token.replace(",", "")
        try:
            value = float(bare)
        except ValueError:
            continue
        if "." not in bare and 1900 <= value <= 2100:  # a year and not a figure
            continue
        if value < _MIN_VALUE:
            continue
        found.append(token)
    return found


def number_absent(statement: str, report_text: str) -> bool:
    # True when the claim states a figure that appears nowhere in the filing.
    for token in claim_numbers(statement):
        if not any(form in report_text for form in _surface_forms(token)):
            return True
    return False