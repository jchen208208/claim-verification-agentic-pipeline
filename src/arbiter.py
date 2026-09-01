"""a tiebreaker verdict for when the two local models disagree.
We ask the 7B a third question, asking it to search for a contradiction rather than a verdict,
and when it confirms with 7B's verdict, the verdict is kept on device. If it confirms with 3B, it's escalated."""

import re

_VERDICT_LINE = re.compile(r"VERDICT\s*:?\s*(REFUTED|ENTAILED)", re.IGNORECASE)
_STARTS_REFUTED = re.compile(r"^\s*REFUTED\b", re.IGNORECASE | re.MULTILINE)
_STARTS_ENTAILED = re.compile(r"^\s*ENTAILED\b", re.IGNORECASE | re.MULTILINE)
_REFUTED = re.compile(r"\bREFUTED\b", re.IGNORECASE)
_ENTAILED = re.compile(r"\bENTAILED\b", re.IGNORECASE)


def parse_verdict(response):
    # True for entailed, False for refuted, None when unparseable.
    
    if not response:
        return None

    # 1.) an explicit "VERDICT: X" line, which is what the arbiter_v2 prompt asked for
    labelled = _VERDICT_LINE.search(response)
    if labelled:
        return labelled.group(1).upper() == "ENTAILED"

    # 2.) a line that begins with the verdict, which is what arbiter_v1 asked for
    if _STARTS_REFUTED.search(response):
        return False
    if _STARTS_ENTAILED.search(response):
        return True

    # 3.) the word appears somewhere, but only one of the two
    has_refuted = bool(_REFUTED.search(response))
    has_entailed = bool(_ENTAILED.search(response))
    if has_refuted != has_entailed:
        return has_entailed

    # 4.) both words or neither.
    return None


def decide(statement, evidence_block, template, call_model):
    # returns (verdict, detail)
    prompt = template.replace("<REPORT>", evidence_block).replace("<STATEMENT>", statement)
    response = call_model(prompt)
    return parse_verdict(response), {"response": response}