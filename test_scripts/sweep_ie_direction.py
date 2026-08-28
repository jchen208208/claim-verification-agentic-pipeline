"""Sweep 2: is the IE gap a refuted-detection failure, and is it IE-specific?"""
import json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims

ROUTED = ROOT/"results"/"condition4_pipeline_test1700"
CLOUD  = ROOT/"results"/"condition2_flash_v2_test1700"

def load_dir(d):
    return {json.load(open(p))["example_id"]: json.load(open(p)) for p in d.glob("*.json")}

claims = {c.example_id: c for c in load_claims("test")}
routed, cloud = load_dir(ROUTED), load_dir(CLOUD)

rows = []
for cid, c in claims.items():
    r, cl = routed[cid], cloud[cid]
    rows.append(dict(id=cid, subset=c.subset, gold=c.entailment_label,
                     routed=r["extracted_label"], cloud=cl["extracted_label"],
                     kept=not r["cloud_called"], a=r["verdict_local_a"], b=r["verdict_local_b"]))

def rate(rs, key, val=True):
    n = [x for x in rs if x[key] is not None]
    return sum(1 for x in n if x[key] == val)/len(n)*100 if n else 0
def acc(rs, key):
    return sum(1 for x in rs if x[key]==x["gold"])/len(rs)*100 if rs else 0

print("=== 1. IS THE PATTERN IE-SPECIFIC? kept-local claims only, per subset ===")
print(f"{'subset':<10}{'n':>5}{'gold ent%':>11}{'routed says ent%':>18}{'cloud says ent%':>17}"
      f"{'routed acc':>12}{'cloud acc':>11}")
for s in ("ie","numeric","knowledge"):
    kl = [x for x in rows if x["subset"]==s and x["kept"]]
    print(f"{s:<10}{len(kl):>5}{rate(kl,'gold'):>11.1f}{rate(kl,'routed'):>18.1f}"
          f"{rate(kl,'cloud'):>17.1f}{acc(kl,'routed'):>12.1f}{acc(kl,'cloud'):>11.1f}")

print("\n=== 2. ACCURACY SPLIT BY GOLD LABEL, kept-local, per subset ===")
print(f"{'subset':<10}{'gold':<7}{'n':>5}{'routed':>9}{'cloud':>8}{'gap':>8}")
for s in ("ie","numeric","knowledge"):
    for g in (True, False):
        sub=[x for x in rows if x["subset"]==s and x["kept"] and x["gold"]==g]
        print(f"{s:<10}{str(g):<7}{len(sub):>5}{acc(sub,'routed'):>9.1f}{acc(sub,'cloud'):>8.1f}"
              f"{acc(sub,'routed')-acc(sub,'cloud'):>+8.1f}")

print("\n=== 3. THE BUDGET: what a 'recheck entailed verdicts' skill would face ===")
for s in ("ie","numeric","knowledge"):
    kl=[x for x in rows if x["subset"]==s and x["kept"]]
    said_e=[x for x in kl if x["routed"] is True]
    wrong=[x for x in said_e if x["gold"] is False]
    right=[x for x in said_e if x["gold"] is True]
    said_r=[x for x in kl if x["routed"] is False]
    wrong_r=[x for x in said_r if x["gold"] is True]
    print(f"{s:<10} kept={len(kl):<4} said ENTAILED={len(said_e):<4} of which wrong={len(wrong):<4}"
          f" (precision {len(right)/len(said_e)*100:.1f}%)   said REFUTED={len(said_r):<4} wrong={len(wrong_r)}")

print("\n=== 4. WOULD A PERFECT 'FLIP WRONG ENTAILED' ORACLE CLOSE THE IE GAP? ===")
ie=[x for x in rows if x["subset"]=="ie"]
base=acc(ie,'routed')
# oracle A: on kept-local IE, every routed-entailed that is gold-refuted flips
o=[dict(x) for x in ie]
for x in o:
    if x["kept"] and x["routed"] is True and x["gold"] is False: x["routed"]=False
print(f"  routed IE now                       {base:.1f}")
print(f"  + perfect flip of wrong entailed    {acc(o,'routed'):.1f}   (+{acc(o,'routed')-base:.1f})")
print(f"  cloud alone IE                      {acc(ie,'cloud'):.1f}")
# oracle B: escalate those instead of flipping (uses cloud verdict)
o2=[dict(x) for x in ie]
n_esc=0
for x in o2:
    if x["kept"] and x["routed"] is True and x["gold"] is False:
        x["routed"]=x["cloud"]; n_esc+=1
print(f"  + escalate them to cloud instead    {acc(o2,'routed'):.1f}   ({n_esc} extra calls)")

print("\n=== 5. WHAT DO THE TWO LOCALS LOOK LIKE ON THE LOSS SET? ===")
kl_ie=[x for x in rows if x["subset"]=="ie" and x["kept"]]
loss=[x for x in kl_ie if x["cloud"]==x["gold"] and x["routed"]!=x["gold"]]
print("  agreement pattern (a,b) on losses:", Counter((x["a"],x["b"]) for x in loss))
print("  agreement pattern (a,b) on all kept IE:", Counter((x["a"],x["b"]) for x in kl_ie))
