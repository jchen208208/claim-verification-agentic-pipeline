"""Score the FDV-IE audit pilot.

Balanced sample (55 gold-refuted + 55 gold-entailed) drawn from the 213 kept-local
FDV-IE claims run 1 called entailed. Recall and false-positive rate are measured on
the balanced sample, then projected onto the true 55/158 population.
"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.label_extractor import extract_label

CACHE = ROOT/"results"/"pilot_ie_audit"
POP_WRONG, POP_RIGHT = 55, 158          # the real kept-local entailed population
IE_N, IE_CORRECT = 600, 465             # run 1 FDV-IE: 77.5%

def norm(s):
    s = s.lower().replace("’","'").replace("—","-").replace("–","-")
    s = re.sub(r"[\"'*`]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def quoted(resp, tag):
    m = re.search(rf"{tag}\s*:?\s*(.+)", resp, re.I)
    return m.group(1).strip() if m else ""

def contains(hay, needle, min_len=12):
    n = norm(needle)
    if len(n) < min_len: return False
    if n in norm(hay): return True
    # allow a long prefix match, models truncate quotes
    return len(n) > 40 and n[:40] in norm(hay)

def load(arm):
    d = CACHE/arm
    return [json.load(open(p)) for p in sorted(d.glob("*.json"))] if d.exists() else []

def detectors(arm, r):
    """returns {rule_name: fired?} for one record"""
    resp = r["response"]; ev = r["evidence"]; stmt = r["statement"]
    out = {}
    if arm == "control":
        out["re-roll says refuted"] = extract_label(resp) is False
    elif arm == "audit_v1":
        fired = bool(re.search(r"\bCONTRADICTED\b", resp))
        cp, fs = quoted(resp, "CLAIM PART"), quoted(resp, "FILING SAYS")
        out["fires on CONTRADICTED (no guard)"] = fired
        out["+ filing quote is real"]           = fired and contains(ev, fs)
        out["+ claim quote is real"]            = fired and contains(stmt, cp)
        out["+ both quotes are real"]           = fired and contains(ev, fs) and contains(stmt, cp)
    elif arm == "audit_v3":
        fired = bool(re.search(r"\bUNCONFIRMED\b", resp))
        cp, fs = quoted(resp, "CLAIM PART"), quoted(resp, "FILING SAYS")
        out["fires on UNCONFIRMED (no guard)"] = fired
        out["+ filing quote is real"] = fired and contains(ev, fs)
        out["+ conflict, not NOT FOUND"] = fired and "NOT FOUND" not in fs.upper()
    elif arm == "audit_v4":
        v = re.search(r"VERDICT\s*:?\s*(MISMATCH|CLEAN)", resp, re.I)
        out["VERDICT: MISMATCH"] = bool(v and v.group(1).upper() == "MISMATCH")
        out["any MISMATCH line"] = bool(re.search(r"\bMISMATCH\b", resp))
        out["MISMATCH or NOT FOUND"] = bool(re.search(r"\bMISMATCH\b|\bNOT FOUND\b", resp))
    elif arm == "audit_v2":
        lab = extract_label(resp)
        any_c = bool(re.search(r"\bCONTRADICTED\b", resp))
        out["final verdict refuted"]      = lab is False
        out["any assertion CONTRADICTED"] = any_c
        # guard: the line that says CONTRADICTED must quote something real
        ok = False
        for line in resp.splitlines():
            if re.search(r"\bCONTRADICTED\b", line):
                q = re.sub(r".*CONTRADICTED\s*[-:]?\s*", "", line).strip()
                if contains(ev, q): ok = True; break
        out["+ contradiction quote is real"] = any_c and ok
    return out

def main():
    print(f"population being fixed: {POP_WRONG} wrong + {POP_RIGHT} right = {POP_WRONG+POP_RIGHT} "
          f"kept-local FDV-IE claims run 1 called entailed")
    print(f"run 1 FDV-IE baseline: {IE_CORRECT}/{IE_N} = {IE_CORRECT/IE_N*100:.1f}%\n")
    print(f"{'arm / rule':<46}{'fires':>7}{'catch':>7}{'break':>7}{'rec%':>7}{'fpr%':>7}"
          f"{'net':>6}{'IE%':>8}{'esc-IE%':>9}{'calls':>7}")
    print("-"*111)

    cloud = {x["id"]: x for x in json.load(open(ROOT/"results"/"ie_analysis"/"ie_rows.json"))}

    for arm in ("control", "audit_v1", "audit_v2", "audit_v3", "audit_v4"):
        recs = load(arm)
        if not recs:
            print(f"{arm:<46}  (no results yet)"); continue
        W = [r for r in recs if r["gold"] is False]
        R = [r for r in recs if r["gold"] is True]
        names = list(detectors(arm, recs[0]).keys())
        for name in names:
            fw = [r for r in W if detectors(arm, r)[name]]
            fr = [r for r in R if detectors(arm, r)[name]]
            rec  = len(fw)/len(W) if W else 0
            fpr  = len(fr)/len(R) if R else 0
            # project onto the real population, flipping every fired claim
            catch = POP_WRONG*rec
            brk   = POP_RIGHT*fpr
            net   = catch - brk
            ie    = (IE_CORRECT + net)/IE_N*100
            # alternative: escalate fired claims to cloud instead of flipping.
            # measured exactly, from the real cloud verdict on each claim that fired,
            # not from a population average.
            cr_w = sum(1 for r in fw if cloud[r["example_id"]]["cloud"] ==
                       cloud[r["example_id"]]["gold"])
            cr_r = sum(1 for r in fr if cloud[r["example_id"]]["cloud"] ==
                       cloud[r["example_id"]]["gold"])
            p_gain = cr_w/len(fw) if fw else 0.0   # cloud rescues a claim we got wrong
            p_lose = 1-(cr_r/len(fr)) if fr else 0.0  # cloud breaks one we got right
            esc_net = POP_WRONG*rec*p_gain - POP_RIGHT*fpr*p_lose
            esc_ie  = (IE_CORRECT + esc_net)/IE_N*100
            calls   = POP_WRONG*rec + POP_RIGHT*fpr
            print(f"{arm+' / '+name:<46}{len(fw)+len(fr):>7}{len(fw):>7}{len(fr):>7}"
                  f"{rec*100:>7.1f}{fpr*100:>7.1f}{net:>+6.0f}{ie:>8.1f}{esc_ie:>9.1f}{calls:>7.0f}")
        print()

    print("columns: fires/catch/break are counts on the balanced 55+55 pilot.")
    print("  rec% = share of wrong-entailed caught. fpr% = share of right-entailed broken.")
    print("  net  = verdicts gained on the real 213-claim population if every fired claim is FLIPPED.")
    print("  IE%  = resulting FDV-IE accuracy. Run 1 is 77.5%, cloud alone is 82.3%.")
    print("  esc-IE% = if fired claims are ESCALATED to cloud instead of flipped; calls = extra cloud calls.")

if __name__ == "__main__":
    main()
