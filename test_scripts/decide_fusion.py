"""Step 2 of the retriever freeze: does the local dense arm earn a place?

Decided on recall alone, at n=700, and that is deliberate. Fusion changes WHICH
k chunks reach the prompt, not how many, so it carries no gold-versus-distractor
tradeoff and needs no end-to-end run. k is the opposite: it is exactly that
tradeoff, so k is decided by condition 1, not here.

Run at three k values because the two decisions must not interact. If fusion
wins at k=10 and loses at k=20 the freeze order breaks, and we would have to
pick a retriever that is better at both or accept a loss at one.

Everything here is free. The vectors are cached (build_embedding_index.py, all
255 reports) and recall is a set comparison against gold.
"""

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.loader import load_claims
from src.run_loop import read_report
from src.bm25_retriever import retrieve as bm25_retrieve
from measure_recall import aggregate, rrf, union
from measure_embedding_recall import embed, load_index

K_VALUES = (10, 15, 20)
BATCH = 64


def main():
    claims = list(load_claims())
    gold = {c.example_id: (c.subset, frozenset(c.relevant_context)) for c in claims}
    print(f"{len(claims)} claims, {sum(len(g[1]) for g in gold.values())} gold elements")

    # Claims embed in batches. nomic returns L2-normalised vectors, so cosine
    # similarity is a plain dot product.
    vectors = []
    for start in range(0, len(claims), BATCH):
        vectors.append(embed([c.statement for c in claims[start:start + BATCH]]))
        print(f"  embedded {min(start + BATCH, len(claims))}/{len(claims)} claims", flush=True)
    claim_vectors = np.vstack(vectors)

    # Full rankings once, then sliced per k, so no work is repeated.
    dense_rank, lex_rank = {}, {}
    for claim, query in zip(claims, claim_vectors):
        report = read_report(claim.report)
        n = len(report["context"])
        similarity = load_index(claim.report, n) @ query
        order = np.lexsort((np.arange(n), -similarity))
        dense_rank[claim.example_id] = [int(i) for i in order]
        lex_rank[claim.example_id] = [e["id"] for e in bm25_retrieve(claim, report, k=n)]

    for k in K_VALUES:
        lex = {e: r[:k] for e, r in lex_rank.items()}
        dense = {e: r[:k] for e, r in dense_rank.items()}
        rows = [
            ("ours BM25 alone", lex),
            ("nomic-embed-text alone", dense),
            ("RRF(BM25, nomic) equal", rrf([lex, dense], k=k)),
            ("RRF(BM25 x1.1, nomic)", rrf([lex, dense], k=k, weights=[1.1, 1.0])),
            ("union, ceiling", union(lex, dense)),
        ]
        print(f"\nk = {k}, n = 700")
        print(f"  {'':<28} {'macro':>8} {'element':>9} {'all-gold':>9}")
        for label, retrievals in rows:
            m = aggregate(retrievals, gold)["overall"]
            print(f"  {label:<28} {m['macro']:>7.2f}% {m['element']:>8.1f}% "
                  f"{m['all_gold']:>8.1f}%")


if __name__ == "__main__":
    main()
