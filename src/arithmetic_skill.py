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


# The three fields we ask the model for
_NUMBERS_LINE = re.compile(r"\**\s*NUMBERS?\**\s*:\s*(.+)", re.IGNORECASE)
_OPERATION_LINE = re.compile(r"\**\s*OPERATION\**\s*:\s*\**\s*([a-z_]+)", re.IGNORECASE)
_CLAIMED_LINE = re.compile(r"\**\s*CLAIMED\**\s*:\s*(.+)", re.IGNORECASE)

def _last(pattern, text):
    # returns the last match in the response since small models often restates the instruction first
    found = pattern.findall(text or "")
    return found[-1].strip(" *\t") if found else None

def parse_response(text):
    """ model output format:
    NUMBERS: <the two values>
    OPERATION: <name>
    CLAIMED: <value> """

    numbers = None
    numbers_text = _last(_NUMBERS_LINE, text)
    if numbers_text:
        values = []
        for token in _CLAIM_NUMBER.findall(numbers_text):
            cleaned = token.replace("$", "").replace(",", "").strip()
            try:
                values.append(float(cleaned))
            except ValueError:
                pass
        numbers = values or None

    operation = _last(_OPERATION_LINE, text)
    if operation:
        operation = operation.lower()

    return numbers, operation, _last(_CLAIMED_LINE, text)


# regex for finding a number as it is printed in a filing, which differs from one written in a claim since parentheses mean negative in accounting, so (45,300) is -45300.
_FILING_NUMBER = re.compile(r"\(?\$?\s?\d[\d,]*(?:\.\d+)?\)?")

# tolerance on how close an operand retrived is to a figure in the filing. higher tolerance allows more coverage but causes invented operands and model hallucination
MATCH_TOL = 1e-9

def numbers_in_filing(text):
    # returns every figure in a block of filing text

    values = set()
    for token in _FILING_NUMBER.findall(text or ""):
        cleaned = token.strip("()").replace("$", "").replace(",", "").strip()
        try:
            value = float(cleaned)
        except ValueError:
            continue
        values.add(value)
        values.add(-value)
    return values


def _appears(operand, values):
    # checks if this one operand is present in the document's numbers at any scale
    if operand == 0:
        return 0.0 in values
    for scale in SCALES:
        target = operand * scale
        for value in values:
            if abs(value - target) <= MATCH_TOL * abs(target):
                return True
    return False

def grounded(numbers, evidence):
    # checks if every operand the model returned is actually present in the evidence retrieved block of the prompt
    if not numbers:
        return False
    values = numbers_in_filing(evidence)
    return all(_appears(operand, values) for operand in numbers)


def build_prompt(statement, evidence_block, template):
    #fill the skill's prompt template.
    prompt = template.replace("<REPORT>", evidence_block).replace("<STATEMENT>", statement)
    assert evidence_block in prompt
    return prompt

