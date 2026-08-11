"""returns the claim's gold evidence chunks, plus BM25's best
non-gold elements until there are k chunks."""

from src.bm25_retriever import TOP_K, report_stats, score_element
from src.evidence_asserter import tokenize

def retrieve(claim, report, k=TOP_K):
    # returns k context elements in BM25 scored order with the gold elements guaranteed present\

    stats = report_stats(report)
    claim_tokens = set(tokenize(claim.statement))

    # returns the score for each element in a report
    scored = [(score_element(claim_tokens, index, stats), index) for index in range(stats["n"])]

    # sort the scores
    scored = sorted(scored, key = lambda tup : (-tup[0], tup[1]))

    gold = set(claim.relevant_context)

    returned_elements = [row for row in scored if row[1] in gold]  # every gold elment first
    non_gold_elements = [row for row in scored if row[1] not in gold]

    while len(returned_elements) < TOP_K:
        returned_elements.append(non_gold_elements.pop(0))

    # sort back into score ordered.
    returned_elements = sorted(returned_elements, key = lambda tup : (-tup[0], tup[1]))

    return [report["context"][index] for _, index in returned_elements]