"""Score the local arbiter against the two bars it has to clear."""
import json, re, sys
from math import comb
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
A=ROOT/"results"/"arbiter"

def mc(b,c):
    n=b+c
    if n==0: return 1.0
    k=min(b,c); return min(1.0,sum(comb(n,i) for i in range(k+1))/(2**n)*2)

def verdict(r):
    """None when unparseable, which is counted and never silently defaulted"""
    t=r["response"]
    m=re.search(r"VERDICT\s*:?\s*(REFUTED|ENTAILED)",t,re.I)
    if m: return m.group(1).upper()=="ENTAILED"
    if re.search(r"^\s*REFUTED\b",t,re.I|re.M): return False
    if re.search(r"^\s*ENTAILED\b",t,re.I|re.M): return True
    has_r=bool(re.search(r"\bREFUTED\b",t,re.I)); has_e=bool(re.search(r"\bENTAILED\b",t,re.I))
    if has_r != has_e: return has_e
    return None

for d in sorted(A.glob("*")):
    recs=[json.load(open(p)) for p in d.glob("*.json")]
    if not recs: continue
    n=len(recs)
    keep7=sum(1 for r in recs if r["b"]==r["gold"])/n*100
    cloud=sum(1 for r in recs if r["cloud"]==r["gold"])/n*100
    orac=sum(1 for r in recs if (r["a"]==r["gold"])!=(r["b"]==r["gold"]))/n*100
    v=[(r,verdict(r)) for r in recs]
    unp=sum(1 for _,x in v if x is None)
    arb=sum(1 for r,x in v if x is not None and x==r["gold"])/n*100
    # unparseable falls back to the 7B, the current behaviour
    fb=sum(1 for r,x in v if (r["b"] if x is None else x)==r["gold"])/n*100
    says_e=sum(1 for _,x in v if x is True)/n*100
    print(f"\n=== {d.name}  n={n} ===")
    print(f"  keep 7B (bar to beat)        {keep7:5.1f}%")
    print(f"  ARBITER, 7B on unparseable   {fb:5.1f}%   ({fb-keep7:+.1f} vs the bar)")
    print(f"  cloud (break-even target)    {cloud:5.1f}%")
    print(f"  oracle over the two locals   {orac:5.1f}%")
    print(f"  unparseable {unp} = {unp/n*100:.1f}%   arbiter says entailed {says_e:.1f}% "
          f"(gold {sum(1 for r in recs if r['gold'] is True)/n*100:.1f}%)")
    b=sum(1 for r,x in v if (r["b"] if x is None else x)==r["gold"] and r["b"]!=r["gold"])
    c=sum(1 for r,x in v if (r["b"] if x is None else x)!=r["gold"] and r["b"]==r["gold"])
    print(f"  vs keep-7B: {b} gained, {c} lost, p={mc(b,c):.4f}")
    b2=sum(1 for r,x in v if (r["b"] if x is None else x)==r["gold"] and r["cloud"]!=r["gold"])
    c2=sum(1 for r,x in v if (r["b"] if x is None else x)!=r["gold"] and r["cloud"]==r["gold"])
    print(f"  vs cloud:   {b2} we win, {c2} cloud wins, p={mc(b2,c2):.4f}")
    print(f"  {'subset':<10}{'n':>5}{'keep7B':>9}{'arbiter':>9}{'cloud':>8}")
    for s in ("ie","numeric","knowledge"):
        sub=[(r,x) for r,x in v if r["subset"]==s]
        if not sub: continue
        k=sum(1 for r,_ in sub if r["b"]==r["gold"])/len(sub)*100
        a_=sum(1 for r,x in sub if (r["b"] if x is None else x)==r["gold"])/len(sub)*100
        cl=sum(1 for r,_ in sub if r["cloud"]==r["gold"])/len(sub)*100
        print(f"  {s:<10}{len(sub):>5}{k:>9.1f}{a_:>9.1f}{cl:>8.1f}")
