"""Sweep 8: the combined target. The false-entailed failure is not IE-only.

Sizes the population a 'recheck entailed verdicts' skill would act on, across
both splits, and the oracle it is bounded by. No model calls.
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims

ROUTED = ROOT/"results"/"condition4_pipeline_test1700"
CLOUD  = ROOT/"results"/"condition2_flash_v2_test1700"
def load(d): return {json.load(open(p))["example_id"]: json.load(open(p)) for p in d.glob("*.json")}

claims = {c.example_id: c for c in load_claims("test")}
r_, c_ = load(ROUTED), load(CLOUD)
rows = [dict(id=k, subset=v.subset, gold=v.entailment_label,
             routed=r_[k]["extracted_label"], cloud=c_[k]["extracted_label"],
             kept=not r_[k]["cloud_called"]) for k, v in claims.items()]

def acc(rs, k): return sum(1 for x in rs if x[k] == x["gold"])/len(rs)*100 if rs else 0

print("=== TARGET POPULATION, test.json n=1,700 ===")
print(f"{'subset':<11}{'kept':>6}{'said ent':>10}{'wrong':>7}{'prec%':>8}")
tot_pop = tot_wrong = 0
for s in ("ie","numeric","knowledge"):
    kl=[x for x in rows if x["subset"]==s and x["kept"]]
    se=[x for x in kl if x["routed"] is True]
    w =[x for x in se if x["gold"] is False]
    tot_pop += len(se); tot_wrong += len(w)
    print(f"{s:<11}{len(kl):>6}{len(se):>10}{len(w):>7}{(1-len(w)/len(se))*100:>8.1f}")
print(f"{'ALL':<11}{sum(1 for x in rows if x['kept']):>6}{tot_pop:>10}{tot_wrong:>7}"
      f"{(1-tot_wrong/tot_pop)*100:>8.1f}")
print(f"\n  the skill would fire on {tot_pop}/1700 = {tot_pop/1700*100:.1f}% of claims")
print(f"  {tot_wrong} of those {tot_pop} verdicts are wrong = {tot_wrong/tot_pop*100:.1f}%")

base = acc(rows,'routed')
print(f"\n=== ORACLE, overall test.json ===")
print(f"  routed now                                {base:.1f}%")
o=[dict(x) for x in rows]
for x in o:
    if x["kept"] and x["routed"] is True and x["gold"] is False: x["routed"]=False
print(f"  + perfect flip of wrong entailed          {acc(o,'routed'):.1f}%  (+{acc(o,'routed')-base:.1f})")
print(f"  cloud alone                               {acc(rows,'cloud'):.1f}%")
print(f"  -> the oracle BEATS cloud alone by {acc(o,'routed')-acc(rows,'cloud'):+.1f} points at zero extra cloud cost")

print("\n=== WHAT A REALISTIC DETECTOR BUYS, by recall and false-positive rate ===")
print(f"  rows = recall on the {tot_wrong} wrong. cols = false-positive rate on the {tot_pop-tot_wrong} right.")
print(f"  cell = overall test.json accuracy if fired verdicts are FLIPPED. routed now {base:.1f}, cloud {acc(rows,'cloud'):.1f}")
print(f"\n  {'recall':>8}" + "".join(f"{f'fpr {f:.0%}':>10}" for f in (0.0,0.05,0.10,0.20)))
n_correct = sum(1 for x in rows if x["routed"]==x["gold"])
for rec in (0.3,0.4,0.5,0.6,0.7,0.8):
    cells=[]
    for fpr in (0.0,0.05,0.10,0.20):
        net = tot_wrong*rec - (tot_pop-tot_wrong)*fpr
        cells.append(f"{(n_correct+net)/1700*100:>10.1f}")
    print(f"  {rec:>8.0%}" + "".join(cells))
print(f"\n  break-even against cloud alone ({acc(rows,'cloud'):.1f}%) needs net "
      f"{(acc(rows,'cloud')/100*1700)-n_correct:+.0f} verdicts")

print("\n=== SAME, FDV-IE ONLY (the subset with the significant loss) ===")
ie=[x for x in rows if x["subset"]=="ie"]
ie_se=[x for x in ie if x["kept"] and x["routed"] is True]
ie_w=sum(1 for x in ie_se if x["gold"] is False); ie_r=len(ie_se)-ie_w
n_ie=sum(1 for x in ie if x["routed"]==x["gold"])
print(f"  routed IE {acc(ie,'routed'):.1f}   cloud IE {acc(ie,'cloud'):.1f}   population {len(ie_se)} ({ie_w} wrong)")
print(f"  {'recall':>8}" + "".join(f"{f'fpr {f:.0%}':>10}" for f in (0.0,0.05,0.10,0.20)))
for rec in (0.3,0.4,0.5,0.6,0.7,0.8):
    cells=[f"{(n_ie+ie_w*rec-ie_r*fpr)/600*100:>10.1f}" for fpr in (0.0,0.05,0.10,0.20)]
    print(f"  {rec:>8.0%}" + "".join(cells))
