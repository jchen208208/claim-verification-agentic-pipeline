"""Wiring test for the run loop. No model, no cloud, no network. Seconds, not hours.

The logger's checks were throwaway because the pieces were independent then. The
run loop is the first code where six modules touch each other, so a mismatched
interface between any two of them does not show up as a wrong return value. It
shows up as a wasted night. Run this before every overnight job.

Assumed interface, which is what the run loop has to provide:

    run_sample(sample, config, results_dir, call_model, retrieve)

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

Section 7, added 16 August, covers the routed pipeline on the same terms:

    run_routed_sample(sample, config, results_dir, clients, retrieve)

        config       a pipeline config: three stage blocks under local_a,
                     local_b and cloud, plus escalate_numeric and
                     skip_local_when_escalating
        clients      {"ollama": fn, "deepseek": fn}, as run.py builds

It drives every path through route_one_claim with stubs: locals agreeing,
locals disagreeing, the detector firing with the skip off and with it on, the
detector disabled, an unparseable local verdict, a stage that raises, and
resume. The skip path is there because route_one_claim raised NameError on it
the day it was written, and no run before the final latency job exercises it.

Results go to a scratch directory outside the repo, so results/ is never touched.

Usage:
    python3 test_scripts/test_harness.py
"""

import dataclasses
import json
import sys
import tempfile
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from run import RETRIEVERS
from src.evidence_asserter import check_overflow
from src.logger import Record
from src.loader import EXPECTED_COUNTS, load_claims
from src.numeric_detector import is_numeric_claim
from src.routed_loop import RoutedRecord
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

# Derived from the dataclass rather than typed out, so it cannot fall behind.
# The hand-written list did: it named 21 fields while Record had gained
# chunks_requested and chunks_kept on 5 Aug and ollama_version on 13 Aug, and
# the check kept passing because it only tested that the listed names were
# present, never that the list was complete.
RECORD_FIELDS = {f.name for f in dataclasses.fields(Record)}

GOOD_RESPONSE = ("The filing states the figure directly. Therefore, the claim "
                 "is refuted.")
REFUTED = GOOD_RESPONSE
ENTAILED = "The filing supports this. Therefore, the claim is entailed."
UNPARSEABLE = "I am unable to determine this from the provided document."

# Derived from the dataclass for the same reason RECORD_FIELDS is.
ROUTED_FIELDS = {f.name for f in dataclasses.fields(RoutedRecord)}

# Model names used only by the routed stubs. They never reach a real server;
# they exist so a stub can tell the three stages apart by config["model"].
STUB_3B, STUB_7B, STUB_CLOUD = "stub:3b", "stub:7b", "stub:cloud"
STUB_ARBITER, STUB_AUDIT = "stub:arbiter", "stub:audit"

# what the two new prompts are told to answer with
ARB_ENTAILED = "ENTAILED"
ARB_REFUTED = "REFUTED\nCLAIM PART: the segment revenue increased\nFILING SAYS: revenue decreased"
AUDIT_CONFIRMED = "CONFIRMED"
AUDIT_UNCONFIRMED = ("UNCONFIRMED\nCLAIM PART: the segment revenue increased\n"
                     "FILING SAYS: revenue decreased")
ARB_GARBAGE = "I cannot tell whether this is entailed or refuted from the filing."

PIPELINE_CONFIG = {
    "experiment": "harness_pipeline",
    "pipeline": True,
    "model": "routed_stub",
    "local_a": {"client": "ollama", "model": STUB_3B, "num_ctx": 16384,
                "num_predict": 2000, "temperature": 0, "seed": 0,
                "prompt_version": "baseline_v1", "ollama_host": "localhost"},
    "local_b": {"client": "ollama", "model": STUB_7B, "num_ctx": 16384,
                "num_predict": 2000, "temperature": 0, "seed": 0,
                "prompt_version": "baseline_v1", "ollama_host": "localhost"},
    "cloud": {"client": "deepseek", "model": STUB_CLOUD, "num_ctx": 16384,
              "num_predict": 2000, "temperature": 0, "seed": 0,
              "prompt_version": "baseline_v2"},
    "escalate_numeric": True,
    "skip_local_when_escalating": False,
    "retriever": "bm25", "top_k": 10, "per_cell": None, "sample_seed": 0,
}


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


class RoutedModelStub:
    """Canned responses keyed by model name.

    The routed loop hands every stage the same client dict, so one stub serves
    all three and tells them apart by config["model"]. That is also how a test
    makes the two local models agree or disagree on demand.
    """

    def __init__(self, by_model, raise_on=()):
        self.by_model = by_model
        self.raise_on = set(raise_on)
        self.calls = []          # (model, prompt) in call order

    def __call__(self, prompt, config):
        model = config["model"]
        self.calls.append((model, prompt))
        if model in self.raise_on:
            raise RuntimeError("stub failure: " + model)
        return {
            "response": self.by_model[model],
            "prompt_eval_count": 4102,
            "eval_count": 631,
            "done_reason": "stop",
        }

    def models_called(self):
        return [model for model, _ in self.calls]


def routed_clients(stub):
    """Both client names point at the one stub, as run.py's CLIENTS would."""
    return {"ollama": stub, "deepseek": stub}


def components_config(**overrides):
    """PIPELINE_CONFIG plus the audit and arbiter stages.

    Kept separate so every section 7 check still runs against a pipeline that has
    neither, which is also the backwards-compatibility test: a config without the
    two stage blocks must behave exactly like run 1.
    """
    config = pipeline_config(**overrides)
    config["arbiter"] = {"client": "ollama", "model": STUB_ARBITER, "num_ctx": 16384,
                         "num_predict": 1200, "temperature": 0, "seed": 0,
                         "prompt_version": "arbiter_v1", "ollama_host": "localhost"}
    config["audit"] = {"client": "ollama", "model": STUB_AUDIT, "num_ctx": 16384,
                       "num_predict": 400, "temperature": 0, "seed": 0,
                       "prompt_version": "ie_audit_v3", "ollama_host": "localhost"}
    return config


def pipeline_config(**overrides):
    """A copy of PIPELINE_CONFIG with top-level keys replaced."""
    config = json.loads(json.dumps(PIPELINE_CONFIG))
    config.update(overrides)
    return config


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
        from src.run_loop import run_sample
    except ImportError as exc:
        print("src/run_loop.py does not expose run_sample yet.")
        print("  ", exc)
        print("\nThis test defines the interface the run loop has to satisfy.")
        print("See the module docstring for the expected signature.")
        return 1

    # --- 0. the config files themselves ---------------------------------
    # Every value below is read off disk, never written here, so a config and
    # this test cannot drift apart the way num_ctx did between 16384 and 32768.
    configs = [(p, json.loads(p.read_text()))
               for p in sorted((REPO_ROOT / "configs").glob("*.json"))]

    check("configs/ is not empty", configs)

    for path, cfg in configs:
        # decompose_v1.json drives a different script and carries no retriever
        if "retriever" in cfg:
            check(f"{path.name} names a known retriever",
                  cfg["retriever"] in RETRIEVERS,
                  f"{cfg['retriever']!r} not in {sorted(RETRIEVERS)}")

        # A split typo would otherwise surface only when the run starts, after
        # the harness has already said everything is fine.
        if "split" in cfg:
            check(f"{path.name} names a known split",
                  cfg["split"] in EXPECTED_COUNTS,
                  f"{cfg['split']!r} not in {sorted(EXPECTED_COUNTS)}")

        # A pipeline config has no flat model settings: they live in three stage
        # blocks. Added 16 Aug after configs/pipeline_trial.json crashed this
        # loop with KeyError: 'num_ctx', which took the whole gate down before a
        # single check ran. The stage blocks get the same validation instead.
        if cfg.get("pipeline"):
            stages_present = [n for n in ("local_a", "local_b", "cloud") if n in cfg]
            check(f"{path.name} has all three stages",
                  len(stages_present) == 3, f"has {stages_present}")
            check(f"{path.name} names the system in 'model'", "model" in cfg,
                  "analyse_condition1.score reads config['model']")
            if len(stages_present) == 3:
                host_a = cfg["local_a"].get("ollama_host", "localhost")
                host_b = cfg["local_b"].get("ollama_host", "localhost")
                check(f"{path.name} local stages share one ollama_host",
                      host_a == host_b, f"{host_a} vs {host_b}")
            blocks = [cfg[n] for n in stages_present]
        else:
            blocks = [cfg]

        for block in blocks:
            name = block.get("model", path.name)

            # Every stage names a prompt file that exists. A typo here is
            # otherwise a FileNotFoundError on claim 1 of a 14 hour run.
            version = block.get("prompt_version")
            if version is not None:
                check(f"{path.name} prompt file exists for {version}",
                      (REPO_ROOT / "prompts" / f"{version}.txt").is_file())

            # prompt_budget_tokens overrides the num_ctx - num_predict derivation,
            # which is meaningless for a cloud client that never receives num_ctx.
            # It must not be usable to ask for a prompt bigger than a real context
            # window would hold.
            budget = block.get("prompt_budget_tokens")
            if budget is not None:
                check(f"{path.name} {name} prompt budget fits inside num_ctx",
                      budget + block["num_predict"] <= block["num_ctx"],
                      f"{budget} + {block['num_predict']} > {block['num_ctx']}")

            ctx, predict = block["num_ctx"], block["num_predict"]
            check(f"{path.name} {name} overflow False just under num_ctx {ctx}",
                  check_overflow(ctx - predict - 1, predict, ctx) is False)
            check(f"{path.name} {name} overflow True at num_ctx {ctx}",
                  check_overflow(ctx - predict, predict, ctx) is True)

    # --- 0b. the loader, both splits ------------------------------------
    # Added 16 Aug with the split parameter. test.json is 1,700 claims with a
    # different subset balance, different id prefixes and three fields missing,
    # so "loaded something plausible" is not the same as "loaded the right file".
    from src.loader import load_claims as load_split

    check("default split is still testmini",
          len(load_split()) == 700, f"got {len(load_split())}")

    split_claims = {}
    for split, counts in EXPECTED_COUNTS.items():
        claims = load_split(split)
        split_claims[split] = claims
        total = sum(counts.values())

        check(f"{split} loads {total} claims", len(claims) == total,
              f"got {len(claims)}")
        actual = {s: sum(1 for c in claims if c.subset == s) for s in counts}
        check(f"{split} subset counts match EXPECTED_COUNTS", actual == counts,
              f"{actual} != {counts}")
        check(f"{split} claims all carry split={split!r}",
              all(c.split == split for c in claims))
        check(f"{split} every report file exists",
              all((REPORT_DIR / c.report).is_file() for c in claims))
        check(f"{split} labels are bools, not strings",
              all(isinstance(c.entailment_label, bool) for c in claims))
        check(f"{split} stratified sampling works", 
              len(stratified_sample(claims, 2)) == 12)

    # The id prefix is the cheapest guard against loading the wrong file into
    # the right variable: testmini ids say "val", test ids say "test".
    check("testmini ids use the -val- prefix",
          all("-val-" in c.example_id for c in split_claims["testmini"]))
    check("test ids use the -test- prefix",
          all("-test-" in c.example_id for c in split_claims["test"]))
    check("the two splits share no example_id",
          not ({c.example_id for c in split_claims["testmini"]}
               & {c.example_id for c in split_claims["test"]}))

    for bad in ("val", "TEST", "testmini.json", ""):
        try:
            load_split(bad)
            check(f"load_claims({bad!r}) is rejected", False, "it was accepted")
        except ValueError:
            check(f"load_claims({bad!r}) is rejected", True)
        except Exception as exc:
            check(f"load_claims({bad!r}) is rejected", False,
                  f"raised {type(exc).__name__}, wanted ValueError")

    # Split-specific data facts, asserted so they are never assumed away.
    # Trap 4, the explaination misspelling, is testmini only.
    check("testmini: every claim has a non-empty explanation",
          all(c.explanation and c.explanation.strip()
              for c in split_claims["testmini"]))
    numeric_test = [c for c in split_claims["test"] if c.subset == "numeric"]
    check("test: all 600 numeric explanations are EMPTY, a known data fact",
          len(numeric_test) == 600
          and all(not (c.explanation or "").strip() for c in numeric_test),
          "if this fails the data changed, and error analysis on numeric "
          "test claims may now be possible")
    check("test: no python_calculation or execution_result anywhere",
          all(c.python_calculation is None and c.execution_result is None
              for c in split_claims["test"]))
    check("test: no knowledge field anywhere",
          all(c.knowledge is None for c in split_claims["test"]))

    # build_sample is what run.py actually calls, so the split has to survive
    # the trip through a config dict.
    from run import build_sample
    check("build_sample defaults to testmini",
          len(build_sample({"per_cell": None, "sample_seed": 0})) == 700)
    check("build_sample honours split=test",
          len(build_sample({"per_cell": None, "sample_seed": 0,
                            "split": "test"})) == 1700)
    check("build_sample samples per cell on test",
          len(build_sample({"per_cell": 3, "sample_seed": 0,
                            "split": "test"})) == 18)

    sample = stratified_sample(load_claims(), 2)
    check("sample is 12 examples", len(sample) == 12, f"got {len(sample)}")

    # --- 1. happy path, perfect retrieval -------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        model = ModelStub()
        run_sample(sample, CONFIG, tmp, model, retrieve_gold)
        recs = load_records(tmp)

        check("one file per claim", len(recs) == 12, f"got {len(recs)}")
        check("files named by example_id",
              set(recs) == {c.example_id for c in sample})
        check("model called once per claim", len(model.calls) == 12,
              f"got {len(model.calls)}")

        one = next(iter(recs.values()))
        missing = RECORD_FIELDS - set(one)
        check(f"all {len(RECORD_FIELDS)} Record fields present", not missing,
              f"missing {missing}")

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

        check("label extracted and converted to bool, refuted -> False",
              all(r["extracted_label"] is False for r in recs.values()),
              str({k: v["extracted_label"] for k, v in recs.items()
                   if v["extracted_label"] is not False}))
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
        run_sample(sample, CONFIG, tmp, ModelStub(), retrieve_wrong)
        recs = load_records(tmp)
        wrong = sum(r["evidence_present"] is False for r in recs.values())
        check("evidence_present False when retrieval misses", wrong >= 10,
              f"only {wrong}/12 came back False")

    # --- 3. context overflow -------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        run_sample(sample, CONFIG, tmp,
                   ModelStub(prompt_eval=15000, eval_count=2000),
                   retrieve_gold)
        recs = load_records(tmp)
        check("context_overflow True at 15000+2000 vs 16384",
              all(r["context_overflow"] is True for r in recs.values()))

    # --- 4. unparseable response ---------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        run_sample(sample, CONFIG, tmp, ModelStub(text=UNPARSEABLE),
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
        run_sample(sample, CONFIG, tmp, model, retrieve_gold)
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
        run_sample(sample, CONFIG, tmp, model2, retrieve_gold)
        recs2 = load_records(tmp)
        check("resume re-runs only the failed example", len(model2.calls) == 1,
              f"called {len(model2.calls)} times")
        check("resume repairs the failed example",
              recs2[victim.example_id]["status"] == "ok")
        check("resume leaves the finished ones alone", len(recs2) == 12)

    # --- 7. the routed pipeline ----------------------------------------
    # Added 16 Aug. route_one_claim had three bugs on the day it was written and
    # one of them, a NameError on the skip path, is invisible to every planned
    # run except the last one. Nothing below touches a model or the network.
    from src.routed_loop import run_routed_sample

    all_claims = list(load_claims())
    flagged = next(c for c in all_claims if is_numeric_claim(c.statement))
    unflagged = next(c for c in all_claims if not is_numeric_claim(c.statement))
    check("harness found a detector-flagged and an unflagged claim",
          flagged is not None and unflagged is not None)

    def route(claims, stub, config=None, tmp=None):
        """Run the routed loop over `claims` and return the records."""
        config = config or pipeline_config()
        run_routed_sample(claims, config, tmp, routed_clients(stub),
                          retrieve_gold)
        return load_records(tmp)

    # 7a. the two local models agree: the cloud is never called
    with tempfile.TemporaryDirectory() as tmp:
        stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: REFUTED,
                                STUB_CLOUD: ENTAILED})
        rec = route([unflagged], stub, tmp=tmp)[unflagged.example_id]

        check("agree: cloud not called", rec["cloud_called"] is False)
        check("agree: only the two locals ran",
              stub.models_called() == [STUB_3B, STUB_7B],
              str(stub.models_called()))
        check("agree: two stage records stored", set(rec["stages"]) ==
              {"local_a", "local_b"}, str(sorted(rec["stages"])))
        check("agree: final_source is local_b", rec["final_source"] == "local_b")
        check("agree: no escalation reason", rec["escalation_reason"] is None)
        check("agree: answer is the 7B's", rec["extracted_label"] is False)
        check("agree: verdict_cloud stays None", rec["verdict_cloud"] is None)

        missing = ROUTED_FIELDS - set(rec)
        check(f"all {len(ROUTED_FIELDS)} RoutedRecord fields present", not missing,
              f"missing {missing}")
        check("elapsed_seconds filled on the routed record",
              isinstance(rec["elapsed_seconds"], (int, float)))
        check("locals read the same prompt as each other",
              rec["stages"]["local_a"]["prompt"] == rec["stages"]["local_b"]["prompt"])

    # 7b. the two local models disagree: the cloud settles it
    with tempfile.TemporaryDirectory() as tmp:
        stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: ENTAILED,
                                STUB_CLOUD: REFUTED})
        rec = route([unflagged], stub, tmp=tmp)[unflagged.example_id]

        check("differ: cloud called", rec["cloud_called"] is True)
        check("differ: reason is disagreement",
              rec["escalation_reason"] == "disagreement",
              str(rec["escalation_reason"]))
        check("differ: three stage records stored",
              set(rec["stages"]) == {"local_a", "local_b", "cloud"})
        check("differ: answer comes from the cloud",
              rec["extracted_label"] is False and rec["final_source"] == "cloud")
        check("differ: both local verdicts recorded",
              rec["verdict_local_a"] is False and rec["verdict_local_b"] is True)
        check("cloud stage reads a different prompt than the locals",
              rec["stages"]["cloud"]["prompt"] != rec["stages"]["local_a"]["prompt"],
              "baseline_v2 must differ from baseline_v1")

    # 7c. the detector fires with skip off: locals still run, cloud still answers
    with tempfile.TemporaryDirectory() as tmp:
        stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: REFUTED,
                                STUB_CLOUD: ENTAILED})
        rec = route([flagged], stub, tmp=tmp)[flagged.example_id]

        check("detector, skip off: all three stages ran",
              stub.models_called() == [STUB_3B, STUB_7B, STUB_CLOUD],
              str(stub.models_called()))
        check("detector, skip off: reason is numeric_detector",
              rec["escalation_reason"] == "numeric_detector",
              str(rec["escalation_reason"]))
        check("detector, skip off: locals_skipped is False",
              rec["locals_skipped"] is False)
        check("detector, skip off: cloud answer wins over agreeing locals",
              rec["extracted_label"] is True)

    # 7d. the detector fires with skip on: neither local model runs.
    #     THIS IS THE REGRESSION TEST. Before the fix this raised NameError on
    #     local_a and every skipped claim was silently written as failed.
    with tempfile.TemporaryDirectory() as tmp:
        stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: REFUTED,
                                STUB_CLOUD: ENTAILED})
        config = pipeline_config(skip_local_when_escalating=True)
        rec = route([flagged], stub, config=config, tmp=tmp)[flagged.example_id]

        check("skip on: the claim did not fail", rec["status"] == "ok",
              str(rec["traceback"])[:200])
        check("skip on: only the cloud ran",
              stub.models_called() == [STUB_CLOUD], str(stub.models_called()))
        check("skip on: one stage record stored",
              set(rec["stages"]) == {"cloud"}, str(sorted(rec["stages"])))
        check("skip on: local verdicts are None",
              rec["verdict_local_a"] is None and rec["verdict_local_b"] is None)
        check("skip on: locals_skipped is True", rec["locals_skipped"] is True)
        check("skip on: answer comes from the cloud",
              rec["extracted_label"] is True and rec["final_source"] == "cloud")

    # 7e. escalate_numeric off: the detector is ignored
    with tempfile.TemporaryDirectory() as tmp:
        stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: REFUTED,
                                STUB_CLOUD: ENTAILED})
        config = pipeline_config(escalate_numeric=False)
        rec = route([flagged], stub, config=config, tmp=tmp)[flagged.example_id]

        check("escalate_numeric off: cloud not called on a flagged claim",
              rec["cloud_called"] is False)
        check("escalate_numeric off: no escalation reason",
              rec["escalation_reason"] is None)

    # 7f. an unparseable local verdict escalates, because None != a bool
    with tempfile.TemporaryDirectory() as tmp:
        stub = RoutedModelStub({STUB_3B: UNPARSEABLE, STUB_7B: REFUTED,
                                STUB_CLOUD: ENTAILED})
        rec = route([unflagged], stub, tmp=tmp)[unflagged.example_id]

        check("unparseable local verdict escalates", rec["cloud_called"] is True)
        check("unparseable local verdict recorded as None",
              rec["verdict_local_a"] is None)
        check("unparseable escalation is logged as disagreement",
              rec["escalation_reason"] == "disagreement")

    # 7g. a failing stage fails the whole claim, and resume repairs it
    with tempfile.TemporaryDirectory() as tmp:
        stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: REFUTED,
                                STUB_CLOUD: ENTAILED}, raise_on=[STUB_7B])
        recs = route([unflagged, flagged], stub, tmp=tmp)

        check("a failing stage marks the claim failed",
              recs[unflagged.example_id]["status"] == "failed")
        check("a failed routed claim stores the traceback",
              bool(recs[unflagged.example_id]["traceback"]))
        check("a failed routed claim still stores the stage that ran",
              "local_a" in recs[unflagged.example_id]["stages"])
        check("a failing stage does not end the run", len(recs) == 2)

        # The stub raises on 7B, which both claims reach, so both failed. Resume
        # must re-run both, then a third pass must run nothing at all.
        check("every claim reaching the failing stage is marked failed",
              all(r["status"] == "failed" for r in recs.values()))

        good = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: REFUTED,
                                STUB_CLOUD: ENTAILED})
        recs2 = route([unflagged, flagged], good, tmp=tmp)
        check("routed resume repairs the failed claims",
              all(r["status"] == "ok" for r in recs2.values()))

        idle = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: REFUTED,
                                STUB_CLOUD: ENTAILED})
        route([unflagged, flagged], idle, tmp=tmp)
        check("routed resume calls no model when everything is done",
              idle.models_called() == [], str(idle.models_called()))

    # --- 8. the audit skill and the arbiter -----------------------------
    # Added 31 Aug. Two optional stages that change routing in opposite directions:
    # the arbiter takes a disagreeing claim back from the cloud (section 2.28), the
    # audit sends an agreeing "entailed" claim to it (section 2.26). They must act on
    # disjoint claim sets, which is the one thing a wiring bug would silently break.
    try:
        from src import arbiter, audit_skill
    except ImportError as exc:
        check("src/arbiter.py and src/audit_skill.py exist", False, str(exc))
        arbiter = audit_skill = None

    if arbiter is not None:
        # 8a. a config WITHOUT the two stages must behave exactly like run 1
        with tempfile.TemporaryDirectory() as tmp:
            stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: ENTAILED,
                                    STUB_CLOUD: REFUTED})
            rec = route([unflagged], stub, tmp=tmp)[unflagged.example_id]
            check("no stages declared: neither component runs",
                  STUB_ARBITER not in stub.models_called()
                  and STUB_AUDIT not in stub.models_called(),
                  str(stub.models_called()))
            check("no stages declared: run 1 behaviour is unchanged",
                  rec["cloud_called"] is True
                  and rec["escalation_reason"] == "disagreement")

        cfg = components_config()

        # The audit runs two checks and the free one comes first. To exercise the
        # model-call path these tests need a claim whose figures all appear in its
        # own report, otherwise the short-circuit fires and the stub is never asked.
        audit_safe = next(
            (c for c in all_claims
             if not is_numeric_claim(c.statement)
             and not audit_skill.number_absent(
                 c.statement,
                 " ".join(e["context"] for e in read_report(c)["context"]))),
            None)
        check("harness found a claim the free number check ignores",
              audit_safe is not None)

        # 8b. arbiter agrees with the 7B: the claim is taken back from the cloud
        with tempfile.TemporaryDirectory() as tmp:
            stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: ENTAILED,
                                    STUB_ARBITER: ARB_ENTAILED, STUB_CLOUD: REFUTED})
            rec = route([unflagged], stub, cfg, tmp)[unflagged.example_id]
            check("arbiter agrees with 7B: cloud NOT called",
                  rec["cloud_called"] is False, str(stub.models_called()))
            check("arbiter agrees with 7B: answer is the 7B's",
                  rec["extracted_label"] is True and rec["final_source"] == "local_b")
            check("arbiter agrees with 7B: escalation reason cleared",
                  rec["escalation_reason"] is None, str(rec["escalation_reason"]))
            check("arbiter agrees with 7B: verdict recorded",
                  rec["arbiter_verdict"] is True)
            check("arbiter ran exactly once",
                  stub.models_called().count(STUB_ARBITER) == 1,
                  str(stub.models_called()))

        # 8c. arbiter sides with the 3B: the claim still goes to the cloud
        with tempfile.TemporaryDirectory() as tmp:
            stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: ENTAILED,
                                    STUB_ARBITER: ARB_REFUTED, STUB_CLOUD: REFUTED})
            rec = route([unflagged], stub, cfg, tmp)[unflagged.example_id]
            check("arbiter sides with 3B: cloud called", rec["cloud_called"] is True)
            check("arbiter sides with 3B: reason stays disagreement",
                  rec["escalation_reason"] == "disagreement",
                  str(rec["escalation_reason"]))
            check("arbiter sides with 3B: verdict recorded as refuted",
                  rec["arbiter_verdict"] is False)

        # 8d. an unreadable arbiter answer must not keep the claim on device
        with tempfile.TemporaryDirectory() as tmp:
            stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: ENTAILED,
                                    STUB_ARBITER: ARB_GARBAGE, STUB_CLOUD: REFUTED})
            rec = route([unflagged], stub, cfg, tmp)[unflagged.example_id]
            check("unparseable arbiter: cloud still called",
                  rec["cloud_called"] is True)
            check("unparseable arbiter: verdict recorded as None",
                  rec["arbiter_verdict"] is None, str(rec["arbiter_verdict"]))

        # 8e. the arbiter must not touch a claim the numeric detector flagged
        with tempfile.TemporaryDirectory() as tmp:
            stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: ENTAILED,
                                    STUB_ARBITER: ARB_ENTAILED, STUB_CLOUD: REFUTED})
            rec = route([flagged], stub, cfg, tmp)[flagged.example_id]
            check("numeric claim: arbiter never runs",
                  STUB_ARBITER not in stub.models_called(),
                  str(stub.models_called()))
            check("numeric claim: still escalated by the detector",
                  rec["escalation_reason"] == "numeric_detector")

        # 8f. locals agree on entailed and the audit fires: cloud is called
        with tempfile.TemporaryDirectory() as tmp:
            stub = RoutedModelStub({STUB_3B: ENTAILED, STUB_7B: ENTAILED,
                                    STUB_AUDIT: AUDIT_UNCONFIRMED, STUB_CLOUD: REFUTED})
            rec = route([audit_safe], stub, cfg, tmp)[audit_safe.example_id]
            check("audit fires: cloud called", rec["cloud_called"] is True)
            check("audit fires: reason is audit_detector",
                  rec["escalation_reason"] == "audit_detector",
                  str(rec["escalation_reason"]))
            check("audit fires: answer comes from the cloud",
                  rec["extracted_label"] is False and rec["final_source"] == "cloud")
            check("audit fires: audit_fired recorded True", rec["audit_fired"] is True)

        # 8g. the audit confirms: the claim stays on device
        with tempfile.TemporaryDirectory() as tmp:
            stub = RoutedModelStub({STUB_3B: ENTAILED, STUB_7B: ENTAILED,
                                    STUB_AUDIT: AUDIT_CONFIRMED, STUB_CLOUD: REFUTED})
            rec = route([audit_safe], stub, cfg, tmp)[audit_safe.example_id]
            check("audit confirms: cloud not called", rec["cloud_called"] is False)
            check("audit confirms: audit_fired recorded False",
                  rec["audit_fired"] is False)
            check("audit confirms: answer stays the 7B's",
                  rec["extracted_label"] is True)

        # 8h. the audit must not run on an agreeing REFUTED verdict
        with tempfile.TemporaryDirectory() as tmp:
            stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: REFUTED,
                                    STUB_AUDIT: AUDIT_UNCONFIRMED, STUB_CLOUD: ENTAILED})
            rec = route([unflagged], stub, cfg, tmp)[unflagged.example_id]
            check("agreeing refuted: audit never runs",
                  STUB_AUDIT not in stub.models_called(), str(stub.models_called()))
            check("agreeing refuted: cloud not called", rec["cloud_called"] is False)

        # 8i. THE DISJOINTNESS TEST. The arbiter can clear the escalation on a
        # DISAGREEING claim whose 7B verdict is entailed. The audit must still not
        # run on it: it was measured only on claims where the two locals agreed.
        with tempfile.TemporaryDirectory() as tmp:
            stub = RoutedModelStub({STUB_3B: REFUTED, STUB_7B: ENTAILED,
                                    STUB_ARBITER: ARB_ENTAILED,
                                    STUB_AUDIT: AUDIT_UNCONFIRMED, STUB_CLOUD: REFUTED})
            rec = route([unflagged], stub, cfg, tmp)[unflagged.example_id]
            check("arbiter-released claim: audit does NOT run",
                  STUB_AUDIT not in stub.models_called(), str(stub.models_called()))
            check("arbiter-released claim: stays on device",
                  rec["cloud_called"] is False)

        # 8j. the free number check short-circuits the model call.
        # Note: claim_numbers can keep a trailing comma from a date, so
        # "December 31, 2023" yields "31,". Measured as immaterial: the
        # surface forms include "31", and over all 358 audited claims the
        # stripped and unstripped rules fire on exactly the same 50.
        raiser = RoutedModelStub({STUB_AUDIT: AUDIT_CONFIRMED},
                                 raise_on=[STUB_AUDIT])
        fired, detail = audit_skill.should_escalate(
            "Revenue was $999,999,999 in the quarter.",
            "evidence block", "the filing says nothing of the sort",
            "<REPORT> <STATEMENT>",
            lambda prompt: raiser(prompt, {"model": STUB_AUDIT})["response"])
        check("number absent: fires without calling the model",
              fired is True and detail["model_called"] is False, str(detail))

        present, detail2 = audit_skill.should_escalate(
            "Revenue was $999,999,999 in the quarter.",
            "evidence block", "revenue of 999,999,999 for the quarter",
            "<REPORT> <STATEMENT>",
            lambda prompt: AUDIT_CONFIRMED)
        check("number present: falls through to the model call",
              present is False and detail2["model_called"] is True, str(detail2))

        # 8k. the parsers, on the shapes the two prompts actually produce
        check("arbiter parses ENTAILED",
              arbiter.parse_verdict(ARB_ENTAILED) is True)
        check("arbiter parses REFUTED with quotes",
              arbiter.parse_verdict(ARB_REFUTED) is False)
        check("arbiter returns None on an unreadable answer",
              arbiter.parse_verdict(ARB_GARBAGE) is None)
        check("arbiter returns None on empty", arbiter.parse_verdict("") is None)
        check("CONFIRMED is not read as UNCONFIRMED",
              audit_skill._CONFIRMED.search("UNCONFIRMED") is None)
        check("UNCONFIRMED is matched",
              audit_skill._UNCONFIRMED.search(AUDIT_UNCONFIRMED) is not None)

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
