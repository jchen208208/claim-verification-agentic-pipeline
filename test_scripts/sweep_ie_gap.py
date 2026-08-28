"""Sweep 1: characterise the FDV-IE gap between the routed pipeline and cloud alone.

No model calls. Reads run 1 (condition 4) and condition 2 off disk.
"""
import json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.loader import load_claims

ROUTED = ROOT / "results" / "condition4_pipeline_test1700"
CLOUD  = ROOT / "results" / "condition2_flash_v2_test1700"


def load_dir(d):
    out = {}
    for p in d.glob("*.json"):
        r = json.load(open(p))
        out[r["example_id"]] = r
    return out


def main():
    claims = {c.example_id: c for c in load_claims("test") if c.subset == "ie"}
    routed = load_dir(ROUTED)
    cloud = load_dir(CLOUD)

    rows = []
    for cid, c in claims.items():
        r, cl = routed[cid], cloud[cid]
        rows.append(dict(
            id=cid,
            gold=c.entailment_label,
            routed=r["extracted_label"],
            cloud=cl["extracted_label"],
            kept_local=not r["cloud_called"],
            reason=r["escalation_reason"],
            a=r["verdict_local_a"],
            b=r["verdict_local_b"],
            evidence_present=r["evidence_present"],
            n_gold=len(set(c.relevant_context)),
            claim=c.statement,
        ))

    def acc(rs, key):
        ok = [x for x in rs if x[key] == x["gold"]]
        return len(ok) / len(rs) * 100 if rs else 0.0

    print(f"FDV-IE, test.json, n={len(rows)}")
    print(f"  routed {acc(rows,'routed'):.1f}   cloud {acc(rows,'cloud'):.1f}")
    kl = [x for x in rows if x["kept_local"]]
    es = [x for x in rows if not x["kept_local"]]
    print(f"  kept local n={len(kl)}: routed {acc(kl,'routed'):.1f}  cloud {acc(kl,'cloud'):.1f}")
    print(f"  escalated  n={len(es)}: routed {acc(es,'routed'):.1f}  cloud {acc(es,'cloud'):.1f}")

    # the loss set
    loss = [x for x in kl if x["cloud"] == x["gold"] and x["routed"] != x["gold"]]
    win  = [x for x in kl if x["routed"] == x["gold"] and x["cloud"] != x["gold"]]
    both_r = [x for x in kl if x["routed"] == x["gold"] and x["cloud"] == x["gold"]]
    both_w = [x for x in kl if x["routed"] != x["gold"] and x["cloud"] != x["gold"]]
    print(f"\nKEPT-LOCAL PARTITION, n={len(kl)}")
    print(f"  cloud right, we wrong   {len(loss):>4}   <- the target")
    print(f"  we right, cloud wrong   {len(win):>4}")
    print(f"  both right              {len(both_r):>4}")
    print(f"  both wrong              {len(both_w):>4}")
    print(f"  net loss                {len(loss)-len(win):>4}")

    # direction of our error on the loss set
    print("\nDIRECTION OF ERROR ON THE LOSS SET")
    print("  gold label of the claims we lose:", Counter(x["gold"] for x in loss))
    print("  what we answered:               ", Counter(x["routed"] for x in loss))
    print("  what we answered on kept-local: ", Counter(x["routed"] for x in kl))
    print("  gold on kept-local:             ", Counter(x["gold"] for x in kl))

    print("\nACCURACY BY GOLD LABEL, kept-local IE")
    for g in (True, False):
        sub = [x for x in kl if x["gold"] == g]
        print(f"  gold={str(g):<5} n={len(sub):>4}   routed {acc(sub,'routed'):.1f}   cloud {acc(sub,'cloud'):.1f}"
              f"   gap {acc(sub,'routed')-acc(sub,'cloud'):+.1f}")

    print("\nSAME, escalated IE")
    for g in (True, False):
        sub = [x for x in es if x["gold"] == g]
        print(f"  gold={str(g):<5} n={len(sub):>4}   routed {acc(sub,'routed'):.1f}   cloud {acc(sub,'cloud'):.1f}"
              f"   gap {acc(sub,'routed')-acc(sub,'cloud'):+.1f}")

    print("\nEVIDENCE PRESENT, kept-local IE")
    for ev in (True, False):
        sub = [x for x in kl if x["evidence_present"] == ev]
        if not sub: continue
        l = [x for x in sub if x["cloud"]==x["gold"] and x["routed"]!=x["gold"]]
        print(f"  evidence={str(ev):<5} n={len(sub):>4}   routed {acc(sub,'routed'):.1f}   cloud {acc(sub,'cloud'):.1f}"
              f"   losses {len(l)} ({len(l)/len(sub)*100:.1f}%)")

    print("\nNUMBER OF GOLD ELEMENTS, kept-local IE")
    for n in sorted({x["n_gold"] for x in kl}):
        sub = [x for x in kl if x["n_gold"] == n]
        l = [x for x in sub if x["cloud"]==x["gold"] and x["routed"]!=x["gold"]]
        print(f"  n_gold={n:<3} n={len(sub):>4}   routed {acc(sub,'routed'):.1f}   cloud {acc(sub,'cloud'):.1f}"
              f"   losses {len(l)}")

    json.dump(rows, open(ROOT/"results"/"ie_analysis"/"ie_rows.json","w"))
    print(f"\nwrote results/ie_analysis/ie_rows.json ({len(rows)} rows)")


if __name__ == "__main__":
    main()
