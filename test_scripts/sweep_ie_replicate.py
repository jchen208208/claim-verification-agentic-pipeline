"""Sweep 7: does the FDV-IE failure replicate on testmini?

run 1 only exists on test.json. But testmini has the same three arms on disk
(3B baseline_v1, 7B baseline_v1, cloud baseline_v2), so the gate can be
reconstructed exactly: escalate on disagreement or when the numeric detector fires.
No model calls.
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims
from src.numeric_detector import is_numeric_claim

A = ROOT/"results"/"condition1_3b_full700"        # 3B, baseline_v1
B = ROOT/"results"/"condition1_7b_full700"        # 7B, baseline_v1
C = ROOT/"results"/"condition2_flash_v2_full700"  # cloud, baseline_v2

def load(d): return {json.load(open(p))["example_id"]: json.load(open(p)) for p in d.glob("*.json")}

claims = {c.example_id: c for c in load_claims("testmini")}
a, b, c_ = load(A), load(B), load(C)
print(f"testmini arms: 3B {len(a)}, 7B {len(b)}, cloud {len(c_)}")

rows = []
for cid, cl in claims.items():
    va, vb, vc = a[cid]["extracted_label"], b[cid]["extracted_label"], c_[cid]["extracted_label"]
    numeric = is_numeric_claim(cl.statement)
    escalate = numeric or (va != vb)
    routed = vc if escalate else vb          # local_b is the kept-local verdict
    rows.append(dict(id=cid, subset=cl.subset, gold=cl.entailment_label,
                     routed=routed, cloud=vc, a=va, b=vb,
                     kept=not escalate,
                     reason=("numeric_detector" if numeric else ("disagreement" if va != vb else None))))

def acc(rs, k): return sum(1 for x in rs if x[k] == x["gold"])/len(rs)*100 if rs else 0
def ent(rs, k):
    n=[x for x in rs if x[k] is not None]
    return sum(1 for x in n if x[k] is True)/len(n)*100 if n else 0

print("\n=== RECONSTRUCTED ROUTED PIPELINE ON testmini, n=700 ===")
print(f"  3B {acc(rows,'a'):.1f}   7B {acc(rows,'b'):.1f}   routed {acc(rows,'routed'):.1f}   "
      f"cloud {acc(rows,'cloud'):.1f}   escalation {sum(1 for x in rows if not x['kept'])/len(rows)*100:.1f}%")
print("  (test.json run 1 for comparison: 3B 59.8, 7B 67.8, routed 75.8, cloud 77.4, esc 53.4%)")

print("\n=== PER SUBSET, KEPT LOCAL ===")
print(f"{'subset':<10}{'n':>5}{'routed':>9}{'cloud':>8}{'gap':>8}")
for s in ("ie","numeric","knowledge"):
    kl=[x for x in rows if x["subset"]==s and x["kept"]]
    print(f"{s:<10}{len(kl):>5}{acc(kl,'routed'):>9.1f}{acc(kl,'cloud'):>8.1f}"
          f"{acc(kl,'routed')-acc(kl,'cloud'):>+8.1f}")

print("\n=== THE DIRECTION TEST: does the loss sit on refuted claims? kept-local ===")
print(f"{'subset':<10}{'gold':<7}{'n':>5}{'routed':>9}{'cloud':>8}{'gap':>8}")
for s in ("ie","numeric","knowledge"):
    for g in (True, False):
        sub=[x for x in rows if x["subset"]==s and x["kept"] and x["gold"]==g]
        if not sub: continue
        print(f"{s:<10}{str(g):<7}{len(sub):>5}{acc(sub,'routed'):>9.1f}{acc(sub,'cloud'):>8.1f}"
              f"{acc(sub,'routed')-acc(sub,'cloud'):>+8.1f}")

print("\n=== THE TARGET POPULATION ON testmini: kept-local IE called entailed ===")
for s in ("ie","knowledge"):
    kl=[x for x in rows if x["subset"]==s and x["kept"]]
    se=[x for x in kl if x["routed"] is True]
    w=[x for x in se if x["gold"] is False]
    print(f"  {s:<10} kept={len(kl):<4} said entailed={len(se):<4} wrong={len(w):<4} "
          f"({len(w)/len(se)*100:.1f}% of them)   test.json IE was 55/213 = 25.8%")

print("\n=== ORACLE: flip only the wrong entailed verdicts, kept-local ===")
for s in ("ie","knowledge"):
    sub=[x for x in rows if x["subset"]==s]
    base=acc(sub,'routed')
    o=[dict(x) for x in sub]
    for x in o:
        if x["kept"] and x["routed"] is True and x["gold"] is False: x["routed"]=False
    print(f"  {s:<10} routed {base:.1f} -> {acc(o,'routed'):.1f}  (+{acc(o,'routed')-base:.1f})   "
          f"cloud alone {acc(sub,'cloud'):.1f}")

json.dump(rows, open(ROOT/"results"/"ie_analysis"/"ie_rows_testmini.json","w"))
