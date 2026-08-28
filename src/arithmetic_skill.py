"""A skill to verify an arithmetic claim by computing it in Python instead of in the model.
The model doesn't write code. It provides numbers and the name of an operation,
and we look that name up in the table below."""

import math
import re

def _percent_change(new, old):
    return (new - old) / old * 100.0


def _difference(a, b):
    return a - b


def _percent_of(part, whole):
    return part / whole * 100.0


def _ratio(a, b):
    return a / b


def _sum(*values):
    return sum(values)


# the allowed operations chosen from analyzing testmini's numeric claims' patterns
OPERATIONS = {
    "percent_change": _percent_change,
    "difference": _difference,
    "percent_of": _percent_of,
    "ratio": _ratio,
    "sum": _sum,
}


def compute(operation, operands):
    # run one operationa dn return the value or None if it cannot run.

    function = OPERATIONS.get(operation)
    if function is None:
        return None

    try:
        return float(function(*operands))  # '*' unpacks the list to comma separated operands
    except (TypeError, ZeroDivisionError, ValueError, OverflowError):
        return None


# regex for finding a number as it is written inside a claim (ex: 3.27, 17.1, $1,204,500, 180,996). ? = 0 or 1, * = 0 or more, + = one or more
_CLAIM_NUMBER = re.compile(r"-?\$?\s?\d[\d,]*(?:\.\d+)?")

# A table under an "in thousands" would print 85,000 instead of 85,000,000. So we check all magnitudes first but the digits would still have to match in order for the number to be considered correct
SCALES = (1, 1e3, 1e-3, 1e6, 1e-6, 1e-2, 1e2)

# the true value may be truncated to the claim's decimal precision, not only rounded. As long as either yield the right answer, then we count it as correct
# accuracy on 250 claims: both 90.0%, round only 89.2%, truncate only 88.0%.
ACCEPT_TRUNCATION = True

def parse_number(text):
    #'15.10' -> (15.1, 2). Turns the model's text into the two things precision_match needs

    match = _CLAIM_NUMBER.search(text or "")  # "" is a for None or "" since re.search(pattern, None) raises a TypeError and crashes
    if match is None:
        return None, None

    cleaned = match.group().replace("$", "").replace(",", "").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return None, None

    decimal_places = len(cleaned.split(".")[1]) if "." in cleaned else 0
    return value, decimal_places


def precision_match(computed, claim_text):
    """checks if the computed value match the claim at the claim's own precision valeu?
    Ex: claim 3.27, truth 3.25, 3.25 at 2 decimal places is 3.25, not 3.27 -> False
        claim 17.1, truth 17.19, 17.19 truncated at 1 decmial place is 17.1 -> True """

    # claim_text is the claim's number given by the model
    claim_value, places = parse_number(claim_text)
    if claim_value is None or computed is None:
        return None

    factor = 10 ** places  # factor matches claim's decimal places
    for scale in SCALES:
        scaled = computed * scale
        for candidate in (claim_value, -claim_value):
            if abs(round(scaled, places) - candidate) < 1e-9:
                return True
            if ACCEPT_TRUNCATION:
                truncated = math.trunc(scaled * factor) / factor
                if abs(truncated - candidate) < 1e-9:
                    return True
    return False