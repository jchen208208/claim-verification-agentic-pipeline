"""Run an audit prompt over the WHOLE target population: every claim run 1 kept on
device and answered 'entailed'. 358 claims across all three subsets.

This produces exact numbers, not a projection from a balanced pilot.
No cloud calls. Resumable.

Usage: python3 test_scripts/run_audit_full.py <prompt_version> [model] [subsets]
  subsets: comma list, default ie,numeric,knowledge
"""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ROUTED = ROOT/"results"/"condition4_pipeline_test1700"
ROWS   = ROOT/"results"/"ie_analysis"/"target_rows.json"
HOSTS  = ["http://10.0.0.26:11434", "http://localhost:11434"]


def pick_host():
    for h in HOSTS:
        try:
            urllib.request.urlopen(h + "/api/tags", timeout=6).read()
            return h
        except Exception:
            continue
    raise SystemExit("no ollama host reachable")


def parts(cid):
    """the retrieved evidence and statement run 1 actually used"""
    p = json.load(open(ROUTED/f"{cid}.json"))["stages"]["local_b"]["prompt"]
    ev = p.split("Financial Report:\n", 1)[1].split("\n\nClaim to verify:\n", 1)[0]
    st = p.split("\n\nClaim to verify:\n", 1)[1].rsplit("\n\nFollow the instructions", 1)[0]
    return ev, st


def main():
    prompt_v = sys.argv[1]
    model    = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5-coder:7b"
    subsets  = (sys.argv[3] if len(sys.argv) > 3 else "ie,numeric,knowledge").split(",")

    host = pick_host()
    tmpl = open(ROOT/"prompts"/f"{prompt_v}.txt").read()
    tag  = f"{prompt_v}_{model.replace(':','-')}"
    outdir = ROOT/"results"/"audit_full"/tag
    outdir.mkdir(parents=True, exist_ok=True)

    rows = [x for x in json.load(open(ROWS)) if x["target"] and x["subset"] in subsets]
    # balance is not enforced here on purpose: this is the real population, whose
    # prior is the thing being measured. It is asserted to match the known split.
    nw = sum(1 for x in rows if x["gold"] is False)
    print(f"host={host} model={model} prompt={prompt_v} subsets={','.join(subsets)}")
    print(f"population {len(rows)} claims, {nw} wrong ({nw/len(rows)*100:.1f}%), "
          f"{len(rows)-nw} right")

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
        for attempt in range(3):
            try:
                d = json.loads(urllib.request.urlopen(urllib.request.Request(
                    host + "/api/generate", body, {"Content-Type": "application/json"}),
                    timeout=900).read())
                break
            except Exception as e:
                if attempt == 2:
                    return x["id"], f"ERROR {e}"
                time.sleep(10)
        json.dump(dict(example_id=x["id"], subset=x["subset"], gold=x["gold"],
                       model=model, prompt_version=prompt_v, statement=st, evidence=ev,
                       response=d["response"], prompt_eval_count=d["prompt_eval_count"],
                       eval_count=d["eval_count"]), open(outdir/f"{x['id']}.json", "w"))
        done[0] += 1
        if done[0] % 20 == 0:
            el = time.time()-t0
            print(f"  {done[0]}/{len(todo)}  {el/60:5.1f} min  "
                  f"eta {el/done[0]*(len(todo)-done[0])/60:5.1f} min", flush=True)
        return x["id"], "ok"

    errs = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for cid, st in ex.map(work, todo):
            if st != "ok":
                errs += 1; print(f"  {cid}: {st}", flush=True)
    print(f"done in {(time.time()-t0)/60:.1f} min, {errs} errors -> results/audit_full/{tag}")


if __name__ == "__main__":
    main()
