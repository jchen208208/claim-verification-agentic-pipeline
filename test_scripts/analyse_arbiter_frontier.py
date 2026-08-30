"""The efficiency frontier: accuracy against cloud calls, for partial-escalation policies.

Population: disagreement claims where the numeric detector is silent. Those are exactly
run 1's 459 `disagreement` escalations, so excluding arithmetic needs no benchmark label.
No model calls.
"""
import json, re, sys
from math import comb
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.numeric_detector import is_numeric_claim

D=ROOT/"results"/"arbiter"/"arbiter_v1_qwen2.5-coder-7b"
recs=[json.load(open(p)) for p in D.glob("*.json")]
# the deployable population: locals disagree AND the numeric detector stays silent
pop=[r for r in recs if not is_numeric_claim(r["statement"])]
print(f"sampled disagreement claims {len(recs)}, numeric detector silent on {len(pop)}")
print("  (run 1 has 459 such claims in total; rates below are measured on this sample)")

def mc(b,c):
    n=b+c
    if n==0: return 1.0
    k=min(b,c); return min(1.0,sum(comb(n,i) for i in range(k+1))/(2**n)*2)

def verdict(r):
    t=r["response"]
    m=re.search(r"VERDICT\s*:?\s*(REFUTED|ENTAILED)",t,re.I)
    if m: return m.group(1).upper()=="ENTAILED"
    if re.search(r"^\s*REFUTED\b",t,re.I|re.M): return False
    if re.search(r"^\s*ENTAILED\b",t,re.I|re.M): return True
    hr=bool(re.search(r"\bREFUTED\b",t,re.I)); he=bool(re.search(r"\bENTAILED\b",t,re.I))
    if hr!=he: return he
    return None

def qwords(r):
    m=re.search(r"CLAIM PART\s*:?\s*(.+)",r["response"],re.I)
    return len(m.group(1).split()) if m else 0

n=len(pop)
print(f"\nBARS on these {n} claims")
print(f"  keep 7B          {sum(1 for r in pop if r['b']==r['gold'])/n*100:5.1f}%   0 cloud calls")
print(f"  cloud, today     {sum(1 for r in pop if r['cloud']==r['gold'])/n*100:5.1f}%   {n} cloud calls")
print(f"  oracle locals    {sum(1 for r in pop if (r['a']==r['gold'])!=(r['b']==r['gold']))/n*100:5.1f}%")

def policy(name, decide):
    """decide(r, v) -> 'arb' | 'cloud' | 'keep7b'"""
    ok=calls=0
    for r in pop:
        v=verdict(r)
        act=decide(r,v)
        if act=="cloud": ans=r["cloud"]; calls+=1
        elif act=="arb": ans=r["b"] if v is None else v
        else: ans=r["b"]
        ok += ans==r["gold"]
    print(f"  {name:<46}{ok/n*100:>7.1f}%{calls:>8}{calls/n*100:>8.1f}%")

print(f"\n{'policy':<48}{'acc':>7}{'calls':>8}{'% esc':>8}")
policy("escalate everything (today)",        lambda r,v:"cloud")
policy("arbiter decides everything",         lambda r,v:"arb")
policy("keep the 7B, no arbiter, no cloud",  lambda r,v:"keep7b")
policy("arbiter if it says REFUTED, else cloud", lambda r,v:"arb" if v is False else "cloud")
policy("arbiter if it says ENTAILED, else cloud", lambda r,v:"arb" if v is True else "cloud")
policy("arbiter if REFUTED w/ quote <=12 words, else cloud",
       lambda r,v:"arb" if (v is False and 0<qwords(r)<=12) else "cloud")
policy("arbiter if it agrees with the 7B, else cloud",
       lambda r,v:"arb" if v is not None and v==r["b"] else "cloud")
policy("arbiter if it agrees with the 3B, else cloud",
       lambda r,v:"arb" if v is not None and v==r["a"] else "cloud")

print("\nWHEN THE ARBITER SIDES WITH EACH LOCAL, HOW OFTEN IS IT RIGHT?")
for who,key in (("7B","b"),("3B","a")):
    s=[r for r in pop if verdict(r) is not None and verdict(r)==r[key]]
    if not s: continue
    print(f"  arbiter sides with the {who}: n={len(s):>4}  correct "
          f"{sum(1 for r in s if r[key]==r['gold'])/len(s)*100:5.1f}%   "
          f"cloud on the same claims {sum(1 for r in s if r['cloud']==r['gold'])/len(s)*100:5.1f}%")
