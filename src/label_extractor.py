"""Extract a verdict from a model's raw response using regex. String input, verdict output.

Returns "entailed", "refuted", or None.

The official FINDVER evaluation replaces an unfound verdict with
random.choice(["entailed", "refuted"]), unseeded. For a 3B model that returns an unparseable
verdict for a large share of the reported score, we have to output a strict None first for troubleshooting
"""

import re

# Level 1: the concluding sentence, allowing light markdown or quote decoration around the label ("the claim is **entailed**").
_ANCHORED = re.compile(
    r"the (?:claim|statement) is\s*[*_'\"\[]*\s*(entailed|refuted)", re.I
)

def extract_label(response):
    # Returns "entailed", "refuted", or None for a given response string based on the last occuring word

    matches = _ANCHORED.findall(response)
    if not matches:
        return None
    return matches[-1].lower()