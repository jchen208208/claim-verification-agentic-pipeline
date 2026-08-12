"""Regenerate the BM25 implementation ablation in paper_numbers.md §1.2.

`paper_numbers.md` rule 1: a number enters the paper only when a committed
script can reproduce it. The ablation was measured on 4 August by throwaway code
and had no reproducer, which was found during the 12 August audit.

**What the ablation is for.** Our BM25 scores 74.60% macro recall where
upstream's scores 65.16%, on the same corpus and chunking. The gap is 9.4 points
and the paper claims a mechanism for it, so each implementation choice is turned
off one at a time to price it. The finding it supports is that **upstream's
tokenizer penalises tables**: punctuation inflates measured element length 1.81x
for tables against 1.13x for paragraphs, and length normalisation then divides
table scores down and pushes them out of the top 10.

**Three choices differ from upstream**, and this prices each:

    Lucene IDF          log((n - df + 0.5)/(df + 0.5) + 1), never negative
    punctuation dropped the tokenizer cannot emit $ ( ) * | or the em dash
    no stemming         tokens are compared as written

Recall scoring needs no model calls, so this is arithmetic over files on disk.

Usage:
    python3 test_scripts/measure_bm25_ablation.py
"""

import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "test_scripts"))

import measure_recall as mr
from run_loop import read_report

K1, B = 1.5, 0.75

_INNER_COMMA = re.compile(r"(?<=\d),(?=\d)")
_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")
# NLTK-like: keep punctuation as its own token, which is what inflates table
# lengths. Words, numbers, or any single non-space character.
_TOKEN_WITH_PUNCT = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*|[^\sa-z0-9]")

# A crude suffix stripper standing in for Porter. The 4 August note records that
# stemming changed nothing, so the row exists to confirm a null, not to match a
# reference implementation token for token.
_SUFFIXES = ("ies", "ing", "ed", "es", "s")


def stem(token):
    if not token.isalpha() or len(token) <= 4:
        return token
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def make_tokenizer(*, strip_inner_comma=True, keep_punct=False, stemming=False):
    pattern = _TOKEN_WITH_PUNCT if keep_punct else _TOKEN

    def tokenize(text):
        text = text.lower()
        if strip_inner_comma:
            text = _INNER_COMMA.sub("", text)
        tokens = pattern.findall(text)
        return [stem(t) for t in tokens] if stemming else tokens

    return tokenize


def make_idf(kind):
    """The three IDF variants. `lucene` is ours and can never go negative."""
    if kind == "lucene":
        return lambda n, df: math.log((n - df + 0.5) / (df + 0.5) + 1)
    if kind == "classic":
        return lambda n, df: math.log((n - df + 0.5) / (df + 0.5))
    if kind == "floored":
        # rank_bm25's BM25Okapi: classic, but any negative is replaced by a
        # small positive epsilon derived from the average positive idf.
        return lambda n, df: math.log((n - df + 0.5) / (df + 0.5))
    raise ValueError(kind)


def retrieve_with(tokenize, idf_fn, floor_negatives=False):
    """Build a retriever closure with these choices, matching src/bm25_retriever."""

    def retrieve(claim, report, k=10):
        counts, lengths, doc_freq = [], [], Counter()
        for element in report["context"]:
            tokens = tokenize(element["context"])
            counts.append(Counter(tokens))
            lengths.append(len(tokens))
            doc_freq.update(set(tokens))

        n = len(counts)
        avg_el = sum(lengths) / n
        claim_tokens = set(tokenize(claim.statement))

        idfs = {t: idf_fn(n, doc_freq[t]) for t in claim_tokens if doc_freq[t]}
        if floor_negatives and idfs:
            positives = [v for v in idfs.values() if v > 0]
            epsilon = 0.25 * (sum(positives) / len(positives)) if positives else 0.0
            idfs = {t: (v if v > 0 else epsilon) for t, v in idfs.items()}

        scored = []
        for index in range(n):
            element_counts, length = counts[index], lengths[index]
            score = 0.0
            for token in claim_tokens:
                f = element_counts[token]
                if f == 0:
                    continue
                saturated = f * (K1 + 1) / (f + K1 * (1 - B + B * length / avg_el))
                score += idfs.get(token, 0.0) * saturated
            scored.append((score, index))

        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [report["context"][i] for _, i in scored[:k]]

    return retrieve


VARIANTS = (
    ("ours as written",                        dict(), "lucene", False),
    ("classic IDF, can go negative",           dict(), "classic", False),
    ("rank_bm25 IDF, negatives floored",       dict(), "floored", True),
    ("punctuation kept as tokens, NLTK-like",  dict(keep_punct=True), "lucene", False),
    ("suffix stemming applied",                dict(stemming=True), "lucene", False),
    ("tokenizer without inner-comma stripping", dict(strip_inner_comma=False), "lucene", False),
    ("all three upstream choices combined",    dict(keep_punct=True, stemming=True), "classic", False),
)


def main():
    gold = mr.load_gold()
    claims = mr.load_claims() if hasattr(mr, "load_claims") else None
    from loader import load_claims
    claims = load_claims()

    print(f"{len(claims)} claims, k=10, macro recall. No model calls.\n")
    print(f"  {'variant':42s} {'macro':>8s} {'element':>9s} {'all-gold':>9s}")

    for label, tok_kwargs, idf_kind, floor in VARIANTS:
        tokenize = make_tokenizer(**tok_kwargs)
        retrieve = retrieve_with(tokenize, make_idf(idf_kind), floor_negatives=floor)

        retrievals = {}
        for claim in claims:
            report = read_report(claim.report)
            retrievals[claim.example_id] = [e["id"] for e in retrieve(claim, report, k=10)]

        s = mr.aggregate(retrievals, gold)["overall"]
        print(f"  {label:42s} {s['macro']:7.2f}% {s['element']:8.1f}% {s['all_gold']:8.1f}%")


if __name__ == "__main__":
    main()
