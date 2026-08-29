"""Score the testmini replication with the SAME rules chosen on test.json.

Nothing is re-tuned here. That is the point: testmini is the check on whether the
design survives on data it was not selected on.
"""
import json, re, sys
from math import comb
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.loader import load_claims

D=ROOT/"results"/"audit_testmini"/"ie_audit_v3_qwen2.5-coder-7b"
rows=json.load(open(ROOT/"results"/"ie_analysis"/"ie_rows_testmini.json"))
recs={json.load(open(p))["example_id"]:json.load(open(p)) for p in D.glob("*.json")}
cl={c.example_id:c for c in load_claims("testmini")}

def mc(b,c):
    n=b+c
    if n==0: return 1.0
    k=min(b,c); return min(1.0,sum(comb(n,i) for i in range(k+1))/(2**n)*2)
def q(r,t):
    m=re.search(rf"{t}\s*:?\s*(.+)",r,re.I); return m.group(1).strip() if m else ""
def fires(r): return bool(re.search(r"\bUNCONFIRMED\b",r["response"]))

tgt=[x for x in rows if x["kept"] and x["routed"] is True and x["subset"] in ("ie","numeric")]
cov=[x for x in tgt if x["id"] in recs]
print(f"testmini target {len(tgt)}, audited {len(cov)}")
if len(cov)<len(tgt): print(f"  WARNING partial, {len(tgt)-len(cov)} missing")
F=[x for x in cov if fires(recs[x["id"]])]
nw=sum(1 for x in cov if x["gold"] is False)
print(f"fires {len(F)}  catches {sum(1 for x in F if x['gold'] is False)}/{nw}  "
      f"breaks {sum(1 for x in F if x['gold'] is True)}/{len(cov)-nw}")
if F: print(f"precision {sum(1 for x in F if x['gold'] is False)/len(F)*100:.1f}%")

base=sum(1 for x in rows if x["routed"]==x["gold"]); N=len(rows)
ie=[x for x in rows if x["subset"]=="ie"]; ieb=sum(1 for x in ie if x["routed"]==x["gold"])
cloud=sum(1 for x in rows if x["cloud"]==x["gold"])
print(f"\ntestmini baselines: routed {base/N*100:.1f}%  cloud alone {cloud/N*100:.1f}%  "
      f"FDV-IE routed {ieb/len(ie)*100:.1f}%")
print(f"\n{'policy':<46}{'fires':>6}{'gain':>6}{'lose':>6}{'overall':>9}{'delta':>7}{'p':>9}{'FDV-IE':>8}")

def rep(name, sel, mode):
    g=l=0; ied=0
    for x in sel:
        v = False if mode=="flip" else x["cloud"]
        if v==x["gold"] and x["routed"]!=x["gold"]:
            g+=1; ied+= 1 if x["subset"]=="ie" else 0
        elif v!=x["gold"] and x["routed"]==x["gold"]:
            l+=1; ied-= 1 if x["subset"]=="ie" else 0
    print(f"  {name:<44}{len(sel):>6}{g:>6}{l:>6}{(base+g-l)/N*100:>9.1f}"
          f"{(g-l)/N*100:>+7.1f}{mc(g,l):>9.4f}{(ieb+ied)/len(ie)*100:>8.1f}")

frac=[x for x in F if 0<len(q(recs[x["id"]]["response"],"CLAIM PART").split())
      <= 0.33*len(cl[x["id"]].statement.split())]
w14=[x for x in F if 0<len(q(recs[x["id"]]["response"],"CLAIM PART").split())<=14]
rep("LOCAL ONLY: quote <= 33% of claim, flip", frac, "flip")
rep("LOCAL ONLY: quote <= 14 words, flip", w14, "flip")
rep("flip every fire (no precision filter)", F, "flip")
rep("ESCALATE every fire", F, "escalate")
