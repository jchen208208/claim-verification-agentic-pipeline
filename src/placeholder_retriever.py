"""Placeholder retriever for testing only: Score every element in the filing
by how many tokens it shares with the claim, and then
returns the top k elements (where k is the number of elements retrieved)

Will later be replaced by a more complex retriever
with claim decomposition plus hybrid dense/BM25.
It's injected into the run loop."""

from src.evidence_asserter import tokenize

TOP_K = 10 # the number FINDVER themselves used
# scripts/inference/retrieval.sh  "We use text-embedding-3-large & top-10 as the
                                 # main RAG evaluation setting"
                                 # top_ks=( #3  #5  10 )   3 and 5 commented out"""

def retrieve(claim, report, k=TOP_K):
    claim_tokens = set(tokenize(claim.statement))

    scored = []
    for element in report["context"]:
        overlap = len(claim_tokens & set(tokenize(element["context"]))) # tallies up the total number of tokens that exist both inside the claim and inside each report element, set & set returns values that are in both sets
        scored.append((overlap, element["id"], element))

    # highest overlap first, sorted then by id so the result cannot vary between runs
    scored.sort(key=lambda row: (-row[0], row[1])) # row[0] = overlap, row[1] = id
    chosen = scored[:k] # chooses top 10

    # hand them back in document order, not score order, so tables stay near their captions and the model reads the report the way it was written
    chosen.sort(key=lambda row: row[1])
    return [element for _, _, element in chosen]