"""Sweep 4: free signals inside the responses we already have on disk.

Population: the 213 kept-local FDV-IE claims the routed system called entailed.
55 are wrong. Can anything already logged separate them? No model calls.
"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims

ROUTED = ROOT/"results"/"condition4_pipeline_test1700"
claims = {c.example_id: c for c in load_claims("test") if c.subset=="ie"}
rows = [x for x in json.load(open(ROOT/"results"/"ie_analysis"/"ie_rows.json"))
        if x["kept_local"] and x["routed"] is True]

HEDGE = re.compile(r"\b(however|but |although|though|unclear|not explicit|cannot|does not "
                   r"(?:state|mention|specify)|no (?:explicit|direct) |partially|appears? to|"
                   r"seems?|likely|assum|may be|might be|ambiguous|insufficient)\b", re.I)
CONJ = re.compile(r"\b(while|whereas|despite|although|and|as well as|alongside|in addition|"
                  r"concurrently|meanwhile)\b", re.I)

out=[]
for x in rows:
    r=json.load(open(ROUTED/f"{x['id']}.json"))
    a,b=r["stages"]["local_a"],r["stages"]["local_b"]
    c=claims[x["id"]]
    out.append(dict(x,
        len_a=a["eval_count"], len_b=b["eval_count"],
        hedge_a=len(HEDGE.findall(a["response"])), hedge_b=len(HEDGE.findall(b["response"])),
        conj=len(CONJ.findall(c.statement)),
        words=len(c.statement.split()),
        commas=c.statement.count(","),
        prompt_toks=a["prompt_eval_count"],
        ev=x["evidence_present"], n_gold=x["n_gold"],
    ))

def split(name, key):
    W=[x[key] for x in out if x["gold"] is False]   # wrong entailed
    R=[x[key] for x in out if x["gold"] is True]    # right entailed
    mw,mr=sum(W)/len(W),sum(R)/len(R)
    print(f"  {name:<26} wrong-entailed {mw:>8.2f}   right-entailed {mr:>8.2f}   diff {mw-mr:+8.2f}")

print("MEAN OF EACH SIGNAL, wrong (n=55) vs right (n=158)")
for n,k in [("3B response tokens","len_a"),("7B response tokens","len_b"),
            ("3B hedge words","hedge_a"),("7B hedge words","hedge_b"),
            ("claim conjunctions","conj"),("claim words","words"),
            ("claim commas","commas"),("prompt tokens","prompt_toks"),
            ("gold elements","n_gold")]:
    split(n,k)

print("\nEVIDENCE PRESENT")
for ev in (True,False):
    s=[x for x in out if x["ev"]==ev]
    w=sum(1 for x in s if x["gold"] is False)
    print(f"  evidence={str(ev):<5} n={len(s):>3}   wrong {w:>3} ({w/len(s)*100:.1f}%)")

print("\nBEST SINGLE THRESHOLD ON EACH CONTINUOUS SIGNAL (maximising net flips)")
for n,k in [("3B response tokens","len_a"),("7B response tokens","len_b"),
            ("3B hedge words","hedge_a"),("7B hedge words","hedge_b"),
            ("claim conjunctions","conj"),("claim words","words"),("gold elements","n_gold")]:
    vals=sorted({x[k] for x in out})
    best=None
    for t in vals:
        for direction in (">=","<="):
            f=[x for x in out if (x[k]>=t if direction==">=" else x[k]<=t)]
            if not f or len(f)>len(out)*0.6: continue
            tp=sum(1 for x in f if x["gold"] is False); fp=len(f)-tp
            if best is None or tp-fp>best[0]: best=(tp-fp,direction,t,len(f),tp,fp)
    if best: print(f"  {n:<26} {k}{best[1]}{best[2]:<8} fires {best[3]:>3}  catches {best[4]:>3}  "
                   f"breaks {best[5]:>3}  net {best[0]:+d}")

print("\nDO THE TWO LOCAL MODELS CITE THE SAME EVIDENCE? (free proxy for correlated error)")
NUMTOK=re.compile(r"\d[\d,]*(?:\.\d+)?")
agree=[]
for x in rows:
    r=json.load(open(ROUTED/f"{x['id']}.json"))
    na=set(NUMTOK.findall(r["stages"]["local_a"]["response"]))
    nb=set(NUMTOK.findall(r["stages"]["local_b"]["response"]))
    j=len(na&nb)/len(na|nb) if (na|nb) else 1.0
    agree.append(dict(id=x["id"],gold=x["gold"],jac=j,only_a=len(na-nb),only_b=len(nb-na)))
for lo,hi in [(0,.2),(.2,.4),(.4,.6),(.6,.8),(.8,1.01)]:
    s=[x for x in agree if lo<=x["jac"]<hi]
    if not s: continue
    w=sum(1 for x in s if x["gold"] is False)
    print(f"  number-overlap {lo:.1f}-{hi:.1f}  n={len(s):>3}   wrong {w:>3} ({w/len(s)*100:.1f}%)")
