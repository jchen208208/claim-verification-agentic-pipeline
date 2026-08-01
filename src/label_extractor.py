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

TAIL_CHARS = 300

# Level 2: when the model doesn't give a structured anchored output so we check for the last occurance of entailed or refuted
_BARE = re.compile(r"\b(entailed|refuted)\b", re.I)

# hedge = "partially entailed", negation = "not entailed"
# the below two regex contain $ so they only fire when the word sits direclty before the bare word (entailed/refuted)
_HEDGE_BEFORE = re.compile(
    r"\b(?:partially|partly|mostly|largely|somewhat|slightly"
    r"|not\s+(?:entirely|fully|necessarily|completely))\b[\s*_'\"\[]{0,4}$", re.I
)

_NEGATION_BEFORE = re.compile(
    r"\b(?:not|never|isn't|cannot|can't)\b[\s*_'\"\[]{0,4}$", re.I
)

_OPPOSITE = {"entailed": "refuted", "refuted": "entailed"}


def extract_label(response):
    # Returns "entailed", "refuted", or None for a given response string based on the last occuring word

    matches = _ANCHORED.findall(response)
    if matches:
        return matches[-1].lower()

    tail = response[-TAIL_CHARS:] # last 300 chars only
    bare = list(_BARE.finditer(tail))
    if not bare:
        return None

    last = bare[-1] # where bare was last fired
    before = tail[:last.start()] # the word right before a bare fire
    label = last.group(1).lower() # what bare was (entailed/refuted)
    if _HEDGE_BEFORE.search(before):
        return None
    if _NEGATION_BEFORE.search(before):
            return _OPPOSITE[label]
    return label