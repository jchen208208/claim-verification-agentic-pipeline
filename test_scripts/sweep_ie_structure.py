"""Sweep 6: is 'a conjunction with exactly one altered conjunct' a real property of FDV-IE?

Measured from the gold explanations, which state which part is wrong. Free.
"""
import re, sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims

INCORRECT = re.compile(r"\b(incorrect|inaccurat|wrong|does not match|contradict|not supported|"
                       r"actually|whereas|instead of|rather than|misstat|erroneous)\b", re.I)

def numbered(expl):
    return re.findall(r"^\s*(\d+)\.", expl, re.M)

for split in ("test", "testmini"):
    claims = load_claims(split)
    print(f"\n===== {split}.json =====")
    for subset in ("ie", "numeric", "knowledge"):
        sub = [c for c in claims if c.subset == subset]
        ref = [c for c in sub if c.entailment_label is False]
        ent = [c for c in sub if c.entailment_label is True]
        # how many numbered steps does an explanation have
        def mean_steps(cs):
            v = [len(numbered(c.explanation)) for c in cs]
            return sum(v)/len(v) if v else 0
        # how many steps mention an error
        errs = []
        for c in ref:
            steps = re.split(r"^\s*\d+\.", c.explanation, flags=re.M)[1:]
            errs.append(sum(1 for s in steps if INCORRECT.search(s)))
        print(f"{subset:<10} refuted n={len(ref):<4} entailed n={len(ent):<4}  "
              f"mean explanation steps: refuted {mean_steps(ref):.2f}  entailed {mean_steps(ent):.2f}")
        if errs:
            c_ = Counter(errs)
            one = c_.get(1, 0)
            print(f"{'':<10} steps flagged as an error, per refuted claim: "
                  f"{dict(sorted(c_.items()))}   exactly one = {one}/{len(ref)} = {one/len(ref)*100:.1f}%")

print("\n===== CLAIM SHAPE, test.json, refuted claims =====")
claims = load_claims("test")
CONJ = re.compile(r"\b(while|whereas|despite|although|and|as well as|alongside|"
                  r"in addition|concurrently|meanwhile)\b", re.I)
for subset in ("ie", "numeric", "knowledge"):
    for lab in (False, True):
        sub = [c for c in claims if c.subset == subset and c.entailment_label is lab]
        w = sum(len(c.statement.split()) for c in sub)/len(sub)
        j = sum(len(CONJ.findall(c.statement)) for c in sub)/len(sub)
        print(f"  {subset:<10} {'refuted' if lab is False else 'entailed':<9} "
              f"mean words {w:5.1f}   mean conjunctions {j:4.2f}")
