"""Replication: run the chosen audit design on testmini, which the design was NOT
selected on. The routed pipeline never ran on testmini, so the gate is reconstructed
from the three arms on disk exactly as sweep_ie_replicate.py does.

Evidence is the same retrieved block the 7B arm saw, so this matches the test.json setup.
No cloud calls. Resumable.
"""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

B7   = ROOT/"results"/"condition1_7b_full700"      # 7B, baseline_v1, testmini
ROWS = ROOT/"results"/"ie_analysis"/"ie_rows_testmini.json"
HOST = "http://10.0.0.26:11434"


def parts(cid):
    p = json.load(open(B7/f"{cid}.json"))["prompt"]
    ev = p.split("Financial Report:\n", 1)[1].split("\n\nClaim to verify:\n", 1)[0]
    st = p.split("\n\nClaim to verify:\n", 1)[1].rsplit("\n\nFollow the instructions", 1)[0]
    return ev, st


def main():
    prompt_v = sys.argv[1] if len(sys.argv) > 1 else "ie_audit_v3"
    model    = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5-coder:7b"
    tmpl = open(ROOT/"prompts"/f"{prompt_v}.txt").read()
    outdir = ROOT/"results"/"audit_testmini"/f"{prompt_v}_{model.replace(':','-')}"
    outdir.mkdir(parents=True, exist_ok=True)

    rows = [x for x in json.load(open(ROWS))
            if x["kept"] and x["routed"] is True and x["subset"] in ("ie", "numeric")]
    nw = sum(1 for x in rows if x["gold"] is False)
    assert nw and nw < len(rows), "single-label population"
    print(f"testmini target population {len(rows)}, {nw} wrong ({nw/len(rows)*100:.1f}%)")

    todo = [x for x in rows if not (outdir/f"{x['id']}.json").exists()]
    print(f"{len(rows)-len(todo)} cached, {len(todo)} to run", flush=True)
    t0 = time.time(); done = [0]

    def work(x):
        ev, st = parts(x["id"])
        p = tmpl.replace("<REPORT>", ev).replace("<STATEMENT>", st)
        assert "<REPORT>" not in p and "<STATEMENT>" not in p
        body = json.dumps({"model": model, "prompt": p, "stream": False,
                           "options": {"temperature": 0, "seed": 0,
                                       "num_ctx": 32768, "num_predict": 400}}).encode()
        for a in range(3):
            try:
                d = json.loads(urllib.request.urlopen(urllib.request.Request(
                    HOST+"/api/generate", body, {"Content-Type": "application/json"}),
                    timeout=1200).read())
                break
            except Exception as e:
                if a == 2: return x["id"], f"ERROR {e}"
                time.sleep(15)
        json.dump(dict(example_id=x["id"], subset=x["subset"], gold=x["gold"], model=model,
                       prompt_version=prompt_v, statement=st, evidence=ev,
                       response=d["response"], prompt_eval_count=d["prompt_eval_count"],
                       eval_count=d["eval_count"]), open(outdir/f"{x['id']}.json", "w"))
        done[0] += 1
        if done[0] % 10 == 0:
            el = time.time()-t0
            print(f"  {done[0]}/{len(todo)}  {el/60:5.1f} min  "
                  f"eta {el/done[0]*(len(todo)-done[0])/60:5.1f} min", flush=True)
        return x["id"], "ok"

    errs = 0
    with ThreadPoolExecutor(max_workers=2) as ex:
        for cid, st in ex.map(work, todo):
            if st != "ok": errs += 1; print(f"  {cid}: {st}", flush=True)
    missing = [x for x in rows if not (outdir/f"{x['id']}.json").exists()]
    print(f"done in {(time.time()-t0)/60:.1f} min, {errs} errors, {len(missing)} missing")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
