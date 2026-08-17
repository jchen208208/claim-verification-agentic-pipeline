"""Measure retrieval recall against FINDVER's gold relevant_context indices.

Regenerates the retrieval table in section 3.4 of docs/architecture_plan.md.

No model calls, no cloud quota, no GPU. Gold indices are on disk, so scoring a
retriever is set comparison and takes seconds. That is what makes the retriever
choosable in daytime rather than overnight (section 12.2).

Three metrics, because "68% recall" is ambiguous and each number has one job
(the reporting rule in section 3.4):

    macro     mean over claims of matched/needed. This is what upstream's
              FinDVer/retriever/recall_evaluation.py computes, so it is the
              only one that may sit in a table beside a published figure.
    element   sum(matched)/sum(needed). Weights every gold element equally,
              instead of letting a claim needing 1 element count as much as a
              claim needing 6. The honest retrieval measurement.
    all-gold  fraction of claims that received EVERY element they needed. The
              ceiling number, because a claim missing a piece cannot be got
              right for the right reason no matter what the model does.

They differ a lot. text-embedding-3-large is 68.01 / 62.4 / 42.6, so reading
the first as "68% of claims are fine" overstates it by 25 points.

This script scores; it does not retrieve. Everything it measures arrives as one
dict, example_id -> list of element ids, so upstream's shipped output, our own
BM25, a fusion of the two, and a reranker are all scored by the same code.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.loader import load_claims
from src.placeholder_retriever import retrieve
from src.bm25_retriever import retrieve as bm25_retrieve
from src.run_loop import read_report

# Upstream's shipped rankings. all/ holds the FULL ranking over every element in
# the report, not just the top 10, so one loader serves any k for the k sweep.
# Both splits are shipped, which is what makes a held-out recall measurement free.
def upstream_dir(split):
    return (REPO_ROOT / "FinDVer" / "outputs" / f"{split}_outputs"
            / "retriever_output" / "all")

DEFAULT_K = 10  # FINDVER's chosen setting, adopted unchanged by MACE
RRF_C = 60      # the standard reciprocal-rank-fusion constant, not tuned

# Section 3.4, recomputed 2 Aug 2026. The scorer is correct when it reproduces
# these. If bm25 comes back as anything but 65.16, the bug is here, not in the
# retriever, and every number measured afterwards would inherit it.
KNOWN = {
    "text-embedding-3-large": (68.01, 62.4, 42.6),
    "bm25": (65.16, 62.8, 38.6),
    "contriever-msmarco": (33.48, 28.4, 16.3),
}


def load_gold(split="testmini"):
    """example_id -> (subset, frozenset of gold element indices).

    relevant_context is a tuple of ints indexing report["context"]. Checked on
    2 Aug 2026: id == list position for all 137,045 elements across all 600
    reports, so indices and element ids are interchangeable with no mapping.

    frozenset also handles trap 8: relevant_context repeats an index on 5
    testmini claims and 11 test claims, so the distinct gold count is lower than
    the raw length. Recall is unaffected because it was always a set comparison.
    """
    gold = {}
    for claim in load_claims(split):
        gold[claim.example_id] = (claim.subset, frozenset(claim.relevant_context))
    return gold


def score_one(retrieved, needed):
    """One claim: how many of its gold elements did retrieval fetch.

    Returns (matched, n_needed). Order and duplicates in `retrieved` are
    irrelevant to recall, so it is coerced to a set here rather than trusting
    the caller to have done it.
    """
    return len(needed & set(retrieved)), len(needed)


def aggregate(retrievals, gold):
    """The three metrics over a whole retriever's output.

    The distinction that matters, and the one place this script could return
    plausible wrong numbers:

        macro    averages the FRACTIONS, one vote per claim
        element  divides the TOTALS, one vote per gold element
        all-gold counts CLAIMS THAT GOT EVERYTHING, one vote per claim,
                 but all-or-nothing rather than partial credit

    Worked example, two claims. Claim A needs 1 element and gets it. Claim B
    needs 5 and gets 1. Macro is (1/1 + 1/5) / 2 = 60%. Element is
    (1 + 1) / (1 + 5) = 33%. All-gold is 1/2 = 50%. Same retrieval, three very
    different-looking numbers.
    """
    per_claim = []   # (subset, matched/needed, matched, needed, got_all)
    for example_id, (subset, needed) in gold.items():
        if example_id not in retrievals:
            raise KeyError(
                f"no retrieval for {example_id}: scoring a partial set would "
                f"silently report recall over fewer than {len(gold)} claims"
            )
        matched, n_needed = score_one(retrievals[example_id], needed)
        per_claim.append((subset, matched / n_needed, matched, n_needed,
                          matched == n_needed))

    def summarise(rows):
        n = len(rows)
        macro = sum(r[1] for r in rows) / n
        element = sum(r[2] for r in rows) / sum(r[3] for r in rows)
        all_gold = sum(r[4] for r in rows) / n
        return {"n": n, "macro": macro * 100, "element": element * 100,
                "all_gold": all_gold * 100}

    out = {"overall": summarise(per_claim)}
    for subset in sorted({r[0] for r in per_claim}):
        out[subset] = summarise([r for r in per_claim if r[0] == subset])
    return out


def load_upstream(name, k=DEFAULT_K, split="testmini"):
    """Read one of upstream's shipped rankings, truncated to top k.

    Each record's retrieved_paragraphs is a list of [element_id, score] pairs
    already sorted best-first, so the ids are pair[0] and truncation is a slice.
    """
    with open(upstream_dir(split) / f"{name}.json") as f:
        records = json.load(f)
    return {r["example_id"]: [pair[0] for pair in r["retrieved_paragraphs"][:k]]
            for r in records}


def run_placeholder(k=DEFAULT_K, split="testmini"):
    """Run src/placeholder_retriever.py over all 700 claims.

    The only retriever here that has to actually execute rather than be read
    off disk. Reports are re-read per claim, which the loader's 7 ms measurement
    says costs about 5 s in total.
    """
    retrievals = {}
    for claim in load_claims(split):
        report = read_report(claim.report)
        retrievals[claim.example_id] = [e["id"] for e in retrieve(claim, report, k=k)]
    return retrievals


def run_ours(retrieve_fn, k=DEFAULT_K, split="testmini"):
    """Run one of our own retrievers over all 700 claims.

    Returns ranked order, best first, because RRF consumes rank positions.
    Reports are re-read per claim, about 5 s in total across all 700.
    """
    retrievals = {}
    for claim in load_claims(split):
        report = read_report(claim.report)
        retrievals[claim.example_id] = [e["id"] for e in retrieve_fn(claim, report, k=k)]
    return retrievals


def union(*retrievals_list):
    """Merge several retrievers' outputs by taking the union per claim.

    Not a fusion rule. This is the diagnostic for whether fusion is worth
    building at all: a merge can only reorder what at least one retriever
    already found, so the union is the ceiling any fusion could reach from
    those candidate pools. If the union of two top-10s scores barely above
    either alone, the two are missing the same elements and no weighting will
    recover them.

    Deliberately generous, since it scores up to 2k elements against k. Real
    fusion at k always lands below it.
    """
    keys = set(retrievals_list[0])
    merged = {}
    for example_id in keys:
        ids = set()
        for retrievals in retrievals_list:
            ids |= set(retrievals[example_id])
        merged[example_id] = sorted(ids)
    return merged


def rrf(rankings, k=DEFAULT_K, c=RRF_C, weights=None):
    """Reciprocal rank fusion of several ranked lists into one top-k.

    Each element scores 1/(c + rank) in every list it appears in, and the scores
    are summed. Only positions are used, never the retrievers' own scores, which
    is the point: BM25 returns values around 70 and cosine similarity returns
    values under 1, so the two cannot be added or compared directly. Rank is the
    common currency.

    c=60 flattens the top of each list. At c=0 rank 1 scores 1.0 and rank 2
    scores 0.5, so one list's favourite dominates. At c=60 they are 0.0164 and
    0.0161, so an element BOTH retrievers ranked highly beats an element one
    ranked first and the other ranked 40th. Agreement is what the constant buys.

    rankings: list of dicts, example_id -> ranked list of ids, best first.
    Ties break on element id so a run cannot vary.
    """
    if weights is None:
        weights = [1.0] * len(rankings)

    fused = {}
    for example_id in rankings[0]:
        scores = {}
        for ranking, weight in zip(rankings, weights):
            for rank, element_id in enumerate(ranking[example_id], start=1):
                scores[element_id] = scores.get(element_id, 0.0) + weight / (c + rank)
        ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        fused[example_id] = [element_id for element_id, _ in ordered[:k]]
    return fused


def print_table(title, rows):
    """rows: list of (label, metrics dict)."""
    print(f"\n{title}")
    print(f"    {'retriever':<28} {'macro':>8} {'element':>9} {'all-gold':>9}")
    for label, m in rows:
        print(f"    {label:<28} {m['macro']:>7.2f}% {m['element']:>8.1f}% "
              f"{m['all_gold']:>8.1f}%")


def main():
    """Usage: measure_recall.py [k] [split]

    split defaults to testmini. Upstream ships full rankings for both splits, so
    scoring the held-out 1,700 costs nothing but CPU: gold indices are on disk
    and no model is involved anywhere in this file.
    """
    k = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_K
    split = sys.argv[2] if len(sys.argv) > 2 else "testmini"

    gold = load_gold(split)
    print(f"split {split}: {len(gold)} claims, "
          f"{sum(len(g[1]) for g in gold.values())} distinct gold elements, k={k}")

    upstream = {name: load_upstream(name, k, split) for name in KNOWN}
    scored = {name: aggregate(r, gold) for name, r in upstream.items()}
    ours_bm25 = run_ours(bm25_retrieve, k, split)
    scored["ours, placeholder"] = aggregate(run_placeholder(k, split), gold)
    scored["ours, bm25"] = aggregate(ours_bm25, gold)

    print_table(f"Recall at k={k}, all {len(gold)} {split} claims",
                [(name, m["overall"]) for name, m in scored.items()])

    # Validation. Only meaningful at k=10 on testmini, which is what section 3.4
    # recorded. On test.json there is nothing published to check against, so the
    # guarantee that the scorer is right comes from it reproducing on testmini.
    if k == DEFAULT_K and split == "testmini":
        print("\nValidation against the section 3.4 figures")
        ok = True
        for name, (macro, element, all_gold) in KNOWN.items():
            m = scored[name]["overall"]
            for label, got, want, tol in (("macro", m["macro"], macro, 0.01),
                                          ("element", m["element"], element, 0.05),
                                          ("all-gold", m["all_gold"], all_gold, 0.05)):
                if abs(got - want) > tol:
                    print(f"    MISMATCH {name} {label}: got {got:.2f}, expected {want}")
                    ok = False
        print("    all figures reproduced" if ok else "    SCORER IS WRONG, do not use")

    elif k == DEFAULT_K:
        print(f"\n  No published figures exist for {split}, so nothing is validated here.")
        print("  The scorer is trusted because it reproduces section 3.4 exactly on testmini.")

    print_table("Per subset, text-embedding-3-large",
                [(s, scored["text-embedding-3-large"][s])
                 for s in ("ie", "numeric", "knowledge")])

    print_table("Per subset, ours, bm25",
                [(s, scored["ours, bm25"][s])
                 for s in ("ie", "numeric", "knowledge")])

    # The union diagnostic: is fusion worth building?
    both = union(upstream["bm25"], upstream["text-embedding-3-large"])
    print_table(f"Union diagnostic (ceiling on any fusion of the two, up to {2 * k} elements)",
                [("bm25 alone", scored["bm25"]["overall"]),
                 ("text-embedding-3 alone", scored["text-embedding-3-large"]["overall"]),
                 ("union of both", aggregate(both, gold)["overall"])])

    # Real RRF, returning exactly k elements, so it is comparable to the single
    # retrievers above rather than to the 2k union ceiling. Candidate pool depth
    # is swept because fusion can only reorder what it is given: a pool of k sees
    # only what each retriever already had in its top k, while a deeper pool lets
    # an element ranked 30th by one and 4th by the other surface.
    print_table(f"RRF, bm25 + text-embedding-3, c={RRF_C}, returning k={k}",
                [(f"pool = top {d} of each" if d else "pool = full ranking",
                  aggregate(rrf([load_upstream("bm25", d or 10 ** 6, split),
                                 load_upstream("text-embedding-3-large",
                                               d or 10 ** 6, split)],
                                k=k), gold)["overall"])
                 for d in (k, 25, 50, 100, None)])


if __name__ == "__main__":
    main()
