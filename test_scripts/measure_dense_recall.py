"""The dense-arm go/no-go: is nomic-embed-text worth fusing with our BM25?

Scores the local embedding retriever alone on the 102-claim slice, against our
BM25 on exactly the same claims, then tries fusion. No pipeline code is written
until this passes, because the answer may be to delete embeddings/ entirely.

The decision rule was fixed on 4 August, before seeing any of these numbers, by
the contriever result (docs/build_log.md): RRF weights every list equally, so a
weak arm gets an equal vote and actively drags a strong one down. Contriever at
33.48% cost our BM25 5.1 points.

    nomic near 68%     fuse, expect roughly +2 over BM25 alone
    nomic near 33%     do not fuse, delete embeddings/, ship BM25 alone
    in between         try weighted RRF before deciding

Reads the cached vectors written by build_embedding_index.py. Only the claims
are embedded here, 102 short calls, so this runs in about a minute.
"""

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "test_scripts"))

from src.loader import load_claims
from src.sampler import stratified_sample
from src.run_loop import read_report
from src.bm25_retriever import retrieve as bm25_retrieve
from measure_recall import aggregate, rrf, union, print_table

MODEL = "nomic-embed-text"
DIM = 768
INDEX_DIR = REPO_ROOT / "embeddings"
ENDPOINT = "http://localhost:11434/api/embed"
DEFAULT_K = 10


def embed(texts):
    payload = json.dumps({"model": MODEL, "input": texts}).encode()
    request = urllib.request.Request(
        ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return np.array(json.loads(response.read())["embeddings"], dtype="float32")


def load_index(report_name, n_elements):
    """Cached vectors for one report, rows in report["context"] order.

    Row i is element id i. The reshape asserts the file length agrees with the
    report, so a truncated or stale file fails here rather than silently
    scoring against the wrong elements.
    """
    path = INDEX_DIR / (Path(report_name).stem + ".f32")
    vectors = np.fromfile(path, dtype="float32")
    if vectors.size != n_elements * DIM:
        raise ValueError(f"{path.name}: {vectors.size / DIM:.1f} rows, "
                         f"report has {n_elements} elements")
    return vectors.reshape(n_elements, DIM)


def main():
    per_cell = int(sys.argv[1]) if len(sys.argv) > 1 else 17
    k = DEFAULT_K

    sample = stratified_sample(load_claims(), per_cell)
    gold = {c.example_id: (c.subset, frozenset(c.relevant_context)) for c in sample}
    print(f"{len(sample)} claims, "
          f"{sum(len(g[1]) for g in gold.values())} gold elements, k={k}")

    # Claims embed in one batch. nomic returns L2-normalised vectors (measured
    # 4 Aug), so cosine similarity is a plain dot product with no normalising.
    claim_vectors = embed([c.statement for c in sample])

    dense, lexical = {}, {}
    for claim, query in zip(sample, claim_vectors):
        report = read_report(claim.report)
        matrix = load_index(claim.report, len(report["context"]))

        similarity = matrix @ query
        # argsort descending; ties break on lower id, matching bm25_retriever
        order = np.lexsort((np.arange(len(similarity)), -similarity))
        dense[claim.example_id] = [int(i) for i in order[:k]]
        lexical[claim.example_id] = [e["id"] for e in bm25_retrieve(claim, report, k=k)]

    rows = [
        ("ours, bm25", lexical),
        ("nomic-embed-text alone", dense),
        ("RRF(bm25, nomic)  equal votes", rrf([lexical, dense], k=k)),
        ("RRF(bm25 x2, nomic x1)", rrf([lexical, dense], k=k, weights=[2.0, 1.0])),
        ("RRF(bm25 x3, nomic x1)", rrf([lexical, dense], k=k, weights=[3.0, 1.0])),
        ("union, ceiling on any fusion", union(lexical, dense)),
    ]
    print_table(f"Dense arm go/no-go, {len(sample)}-claim slice, k={k}",
                [(label, aggregate(r, gold)["overall"]) for label, r in rows])


if __name__ == "__main__":
    main()
