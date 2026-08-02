"""Check that the relevant context (gold evidence) actually reached the model

evidence_present: after the prompt is built, look for a rare token from each gold
context element in the prompt string. This runs beside the pipeline, never inside it.
The gold indices are not passed to any pipeline stage and the prompt is not changed
by the result, so the retriever is still doing the retrieving.

context_overflow: after the call, prompt_eval_count + eval_count >= num_ctx. Ollama
0.12.3 evicts the oldest prompt tokens when generation fills the window and still
reports done_reason "stop", so evidence that was present at ingestion can be destroyed
mid-response.

This helps us understand if the failure was caused by a corrupted input or a reasoning failure"""

from collections import Counter
import re

# we want the 3 "best" tokens to be the indicators
N_TOKENS = 3
MIN_TOKEN_LEN = 3

_INNER_COMMA = re.compile(r"(?<=\d),(?=\d)")
_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")

def tokenize(text):
    # Split text into comparable tokens
    text = _INNER_COMMA.sub("", text.lower())
    return _TOKEN.findall(text)

def count_report_tokens(report):
    # Counter over every token in one report, it's built once and reused for all claims that reference it.
    text = "\n".join(element["context"] for element in report["context"])
    return Counter(tokenize(text))

def pick_tokens(element_text, report_counts, n=N_TOKENS):
    """Return the n number of rarest tokens in one gold context element with the rarest first.
    report_counts is a Counter object over every token in the whole report, so
    report_counts[t] is how many times t appears in the report. A count of 1
    means the token appears nowhere in the report outside this element, which
    is the case that makes the presence check conclusive. """

    candidates = {
        t for t in tokenize(element_text)
        # token must be a certain length so to check it's not noise (i.e. '*', '-')
        if len(t) >= MIN_TOKEN_LEN
    }

    # ranked by rarest, then longest, then alphabetical
    ranked = sorted(candidates, key=lambda t: (report_counts[t], -len(t), t))

    # Returns a list of n (token, count) pairs unless the element has too few usable tokens or none.
    return [(t, report_counts[t]) for t in ranked[:n]]

def assert_evidence(evidence_block, claim, report):
    """Return (evidence_present, evidence_found) for one claim object from the loader.

    evidence_block is the formatted retrieved text that build_prompt inserted,
    not the whole prompt. Limiting to just this chunk stops the claim's own wording
    from satisfying a match.

    evidence_found maps each relevant context index to (witnesses found, witnesses tried).
    evidence_present is True only when every relevant context element had all of its
    witnesses present."""

    report_counts = count_report_tokens(report)
    seen = set(tokenize(evidence_block))

    evidence_found = {}
    for i in claim.relevant_context:
        witnesses = pick_tokens(report["context"][i]["context"], report_counts) # report["context"] = 304-element list, [i] is the gold index since id = position in the report, and the last ["context"] is each element's actual text
        matches = sum(1 for token, _count in witnesses if token in seen) # checks how many of selected tokens for a gold element are in the prompt
        evidence_found[i] = (matches, len(witnesses)) # stores number of witnesses found per element (0-3), len(witnesses) = how many witnesses we went searching for (always 3 for testmini)

    evidence_present = all(
        searched > 0 and matches == searched for matches, searched in evidence_found.values()
    ) # True only if all matches were found for each relevant context element for a claim, aka all gold evidence present

    return evidence_present, evidence_found