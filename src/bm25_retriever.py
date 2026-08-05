"""BM25 retrieval over one report's context elements.
BM25 weighs each shared token by how rare it is in this report, how often it repeats
inside the context element, and how long the element is.
Returns elements ranked best-first, not in document order, because reciprocal
rank fusion uses rank positions. Then the prompt builder will re-sort.
"""

from collections import Counter
from src.evidence_asserter import tokenize
import math

K1 = 1.5   # term-frequency saturation aka how fast repetition stops helping
B = 0.75   # length normalisation strength (long elements aren't always better since a 500-word paragraph will contain a certain word more often than a 50-word one purely by being longer)
# elements with twice the average element length has their score divided down and vice versa for elements with lengths half the average

def report_stats(report):
    """Everything the scorer needs about one report and computed once per report.

        counts = Counter of token: occurrences per element
        lengths = token count per element
        avg_el = average element length
        doc_freq = how many elements contain a specific token it at least once
        n = number of elements
    """
    counts = []
    lengths = []
    doc_freq = Counter()

    for element in report["context"]:
        tokens = tokenize(element["context"])
        counts.append(Counter(tokens))
        lengths.append(len(tokens))
        doc_freq.update(set(tokens)) # cast tokens as a set first since doc_freq counts elements containing the token, not total occurrences of it.

    n = len(counts)

    return {
        "counts": counts,
        "lengths": lengths,
        "avg_el": sum(lengths) / n,
        "doc_freq": doc_freq,
        "n": n,
    }


def score_element(claim_tokens, index, stats):
    """BM25 score for one context element against one claim.
    For each distinct claim token, it adds how rare the token is in this report,
    times a saturated and length-normalised count of it inside this context element.
    
    claim_tokens is a set since how often a word repeats inside the claim doesn't decide which tokens to return
    """
    counts = stats["counts"][index]
    length = stats["lengths"][index]
    n = stats["n"]
    avg_el = stats["avg_el"]

    score = 0.0
    for token in claim_tokens:
        f = counts[token]
        if f == 0:
            continue  # Counter returns 0 for absent keys so skip

        df = stats["doc_freq"][token]
        idf = math.log((n - df + 0.5) / (df + 0.5) + 1)

        saturated = f * (K1 + 1) / (f + K1 * (1 - B + B * length / avg_el))
        score += idf * saturated

    return score


TOP_K = 10  # returns the top 10 elements

def retrieve(claim, report, k=TOP_K):
    """returns the top 10 elements of one filing ranked by best score first."""

    stats = report_stats(report)
    claim_tokens = set(tokenize(claim.statement))

    scored = [(score_element(claim_tokens, index, stats), index)
              for index in range(stats["n"])]

    # ranekd by highest score first then lowest id so ties cannot vary between runs
    scored.sort(key=lambda row: (-row[0], row[1]))

    return [report["context"][index] for _, index in scored[:k]]