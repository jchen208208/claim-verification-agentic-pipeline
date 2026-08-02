"""Wiring test for the run loop. No model, no cloud, no network. Seconds, not hours.

The logger's checks were throwaway because the pieces were independent then. The
run loop is the first code where six modules touch each other, so a mismatched
interface between any two of them does not show up as a wrong return value. It
shows up as a wasted night. Run this before every overnight job.

Assumed interface, which is what the run loop has to provide:

    run_experiment(sample, config, results_dir, call_model, retrieve)

        sample       list of Claim objects from src.sampler
        config       dict with model, num_ctx, num_predict, temperature, seed,
                     prompt_version
        results_dir  written one JSON per claim by src.logger.write_result
        call_model   call_model(prompt, config) -> the raw Ollama response dict,
                     with keys response, prompt_eval_count, eval_count, done_reason
        retrieve     retrieve(claim, report) -> list of context element dicts,
                     each {"id": int, "context": str, "type": "paragraph"|"table"}

Everything else, reading the report, building the prompt, asserting evidence,
extracting the label, filling the Record, is internal to the run loop.

Results go to a scratch directory outside the repo, so results/ is never touched.

Usage:
    python3 test_scripts/test_harness.py
"""

import json
import sys
import tempfile
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.loader import load_claims
from src.sampler import stratified_sample

REPORT_DIR = REPO_ROOT / "FinDVer" / "financial_reports"

CONFIG = {
    "model": "qwen2.5-coder:3b",
    "num_ctx": 16384,
    "num_predict": 2000,
    "temperature": 0,
    "seed": 0,
    "prompt_version": "baseline_v1",
}

RECORD_FIELDS = {
    "example_id", "subset", "gold_label", "gold_explanation", "prompt", "config",
    "response", "extracted_label", "extraction_source", "prompt_eval_count",
    "eval_count", "done_reason", "elapsed_seconds", "evidence_present",
    "context_overflow", "status", "traceback",
}

GOOD_RESPONSE = ("The filing states the figure directly. Therefore, the claim "
                 "is refuted.")
UNPARSEABLE = "I am unable to determine this from the provided document."


# ---------------------------------------------------------------- stubs

def read_report(claim):
    with open(REPORT_DIR / claim.report) as f:
        return json.load(f)


def retrieve_gold(claim, report):
    """Perfect retriever. evidence_present must come back True."""
    return [report["context"][i] for i in claim.relevant_context]


def retrieve_wrong(claim, report):
    """Retriever that misses entirely. evidence_present must come back False."""
    gold = set(claim.relevant_context)
    pool = [e for i, e in enumerate(report["context"]) if i not in gold]
    return pool[:len(claim.relevant_context)] or pool[:1]


class ModelStub:
    """Canned Ollama responses. Records how many times it was called."""

    def __init__(self, text=GOOD_RESPONSE, prompt_eval=4102, eval_count=631,
                 raise_on=()):
        self.text = text
        self.prompt_eval = prompt_eval
        self.eval_count = eval_count
        self.raise_on = set(raise_on)
        self.calls = []

    def __call__(self, prompt, config):
        self.calls.append(prompt)
        for marker in self.raise_on:
            if marker in prompt:
                raise RuntimeError("stub failure: " + marker)
        return {
            "response": self.text,
            "prompt_eval_count": self.prompt_eval,
            "eval_count": self.eval_count,
            "done_reason": "stop",
        }


# ---------------------------------------------------------------- helpers

CHECKS = []


def check(name, condition, detail=""):
    CHECKS.append((name, bool(condition), detail))


def load_records(results_dir):
    return {p.stem: json.loads(p.read_text())
            for p in Path(results_dir).glob("*.json")}


# ---------------------------------------------------------------- the tests

def main():
    try:
        from src.run_loop import run_experiment
    except ImportError as exc:
        print("src/run_loop.py does not expose run_experiment yet.")
        print("  ", exc)
        print("\nThis test defines the interface the run loop has to satisfy.")
        print("See the module docstring for the expected signature.")
        return 1

    sample = stratified_sample(load_claims(), 2)
    check("sample is 12 examples", len(sample) == 12, f"got {len(sample)}")

    # --- 1. happy path, perfect retrieval -------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        model = ModelStub()
        run_experiment(sample, CONFIG, tmp, model, retrieve_gold)
        recs = load_records(tmp)

        check("one file per claim", len(recs) == 12, f"got {len(recs)}")
        check("files named by example_id",
              set(recs) == {c.example_id for c in sample})
        check("model called once per claim", len(model.calls) == 12,
              f"got {len(model.calls)}")

        one = next(iter(recs.values()))
        missing = RECORD_FIELDS - set(one)
        check("all 17 Record fields present", not missing, f"missing {missing}")

        check("all status ok",
              all(r["status"] == "ok" for r in recs.values()))
        check("config recorded",
              all(r["config"]["num_ctx"] == 16384 for r in recs.values()))
        check("elapsed_seconds filled",
              all(isinstance(r["elapsed_seconds"], (int, float))
                  for r in recs.values()))

        check("evidence_present True under perfect retrieval",
              all(r["evidence_present"] is True for r in recs.values()),
              str({k: v["evidence_present"] for k, v in recs.items()
                   if v["evidence_present"] is not True}))
        check("context_overflow False at 4102+631 vs 16384",
              all(r["context_overflow"] is False for r in recs.values()))

        check("label extracted from the canned response",
              all(r["extracted_label"] == "refuted" for r in recs.values()))
        check("extraction_source recorded",
              all(r["extraction_source"] == "anchored" for r in recs.values()))

        by_id = {c.example_id: c for c in sample}
        check("prompt contains the claim statement",
              all(by_id[eid].statement in r["prompt"] for eid, r in recs.items()))
        check("prompt is realistic length (>1000 chars)",
              all(len(r["prompt"]) > 1000 for r in recs.values()),
              str(sorted(len(r["prompt"]) for r in recs.values())[:3]))

    # --- 2. retrieval misses -------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        run_experiment(sample, CONFIG, tmp, ModelStub(), retrieve_wrong)
        recs = load_records(tmp)
        wrong = sum(r["evidence_present"] is False for r in recs.values())
        check("evidence_present False when retrieval misses", wrong >= 10,
              f"only {wrong}/12 came back False")

    # --- 3. context overflow -------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        run_experiment(sample, CONFIG, tmp,
                       ModelStub(prompt_eval=15000, eval_count=2000),
                       retrieve_gold)
        recs = load_records(tmp)
        check("context_overflow True at 15000+2000 vs 16384",
              all(r["context_overflow"] is True for r in recs.values()))

    # --- 4. unparseable response ---------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        run_experiment(sample, CONFIG, tmp, ModelStub(text=UNPARSEABLE),
                       retrieve_gold)
        recs = load_records(tmp)
        check("unparseable response gives label None, not a coerced default",
              all(r["extracted_label"] is None for r in recs.values()))
        check("unparseable response records extraction_source none",
              all(r["extraction_source"] == "none" for r in recs.values()))

    # --- 5. one example blows up ---------------------------------------
    victim = sample[3]
    with tempfile.TemporaryDirectory() as tmp:
        model = ModelStub(raise_on=[victim.statement])
        run_experiment(sample, CONFIG, tmp, model, retrieve_gold)
        recs = load_records(tmp)

        check("a raising example does not end the run", len(recs) == 12,
              f"got {len(recs)}")
        failed = [k for k, r in recs.items() if r["status"] == "failed"]
        check("the failure is marked failed", failed == [victim.example_id],
              f"got {failed}")
        if failed:
            check("the traceback is stored",
                  bool(recs[victim.example_id]["traceback"]))
            check("a failed example still records its prompt",
                  bool(recs[victim.example_id]["prompt"]))
        check("the other 11 still succeeded",
              sum(r["status"] == "ok" for r in recs.values()) == 11)

        # --- 6. resume ---------------------------------------------------
        model2 = ModelStub()
        run_experiment(sample, CONFIG, tmp, model2, retrieve_gold)
        recs2 = load_records(tmp)
        check("resume re-runs only the failed example", len(model2.calls) == 1,
              f"called {len(model2.calls)} times")
        check("resume repairs the failed example",
              recs2[victim.example_id]["status"] == "ok")
        check("resume leaves the finished ones alone", len(recs2) == 12)

    # ---------------------------------------------------------------- report
    width = max(len(n) for n, _, _ in CHECKS)
    failures = 0
    for name, ok, detail in CHECKS:
        print(f"  {'ok  ' if ok else 'FAIL'} {name:<{width}}"
              + (f"   {detail}" if detail and not ok else ""))
        failures += not ok
    print(f"\n{len(CHECKS) - failures}/{len(CHECKS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
