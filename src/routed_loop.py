"""Run the routed pipeline: 3B, then 7B, then cloud only when needed."""

from dataclasses import dataclass, field
import time
import traceback
from collections import namedtuple
from dataclasses import asdict

from src.numeric_detector import is_numeric_claim
from src.run_loop import run_one_claim
from collections import namedtuple
from dataclasses import asdict

from src.numeric_detector import is_numeric_claim
from src.run_loop import run_one_claim
from src.logger import write_result, has_result
from src.run_loop import load_prompt_template

from src import arithmetic_skill, arbiter, audit_skill
from src.run_loop import build_prompt, read_report


@dataclass
class RoutedRecord:
    # one claim through the pipeline as one JSON file.

    # fiels that are same as Record object
    example_id: str
    subset: str
    gold_label: bool
    gold_explanation: str
    config: dict

    extracted_label: bool | None = None
    extraction_source: str | None = None
    evidence_present: bool | None = None
    context_overflow: bool | None = None
    done_reason: str | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None
    elapsed_seconds: float | None = None   # this covers the whole claim including every stage that ran
    thinking: str | None = None
    served_model: str | None = None
    system_fingerprint: str | None = None
    chunks_requested: int | None = None
    chunks_kept: int | None = None

    # these fields determine the routing decision
    verdict_local_a: bool | None = None  # the 3B's verdict, None if skipped
    verdict_local_b: bool | None = None  # the 7B's verdict, None if skipped
    verdict_cloud: bool | None = None  # None when the cloud was not called
    cloud_called: bool = False
    final_source: str | None = None  # "local_b", "cloud" or "skill"
    escalation_reason: str | None = None  # "numeric_detector", "disagreement", or None when nothing escalated
    locals_skipped: bool = False  # the detector fired = true

    skill_verdict: bool | None = None  # the arithmetic skill's answer
    skill_detail: dict | None = None  # its operands, operation, computed value and decline reason

    arbiter_verdict: bool | None = None
    arbiter_detail: dict | None = None
    audit_fired: bool | None = None  # did the audit send a kept claim to the cloud
    audit_detail: dict | None = None

    # dictionary containing the full stage's records (1 to 3 record objects): {"local_a": {...}, "local_b": {...}, "cloud": {...}}
    stages: dict = field(default_factory=dict)  # without field, all 700 records would share a dict but with field, each get their own

    status: str = "ok"
    traceback: str | None = None


# a stages class
Stage = namedtuple("Stage", ["config", "template", "client"])

def route_one_claim(claim, config, stages, retrieve, ollama_version=None):
    """one claim through the pipeline.
    The order is fixed and per claim:
        detector fires -> cloud, and skip both locals if the config says so
        otherwise -> 3B then 7B
        verdicts agree -> keep the 7B's verdict and no cloud call
        verdicts differ -> cloud
    stages is a dictionary of Stages objects
    """

    record = RoutedRecord(
        example_id=claim.example_id,
        subset=claim.subset,
        gold_label=claim.entailment_label,
        gold_explanation=claim.explanation,
        config=config,
    )

    started = time.perf_counter()

    try:
        # detector first
        escalate = False
        reason = None
        if config.get("escalate_numeric", True) and is_numeric_claim(claim.statement):
            escalate = True
            reason = "numeric_detector"

        skip_locals = escalate and config.get("skip_local_when_escalating", False)
        record.locals_skipped = skip_locals

        # the two local models
        local_b = None
        if not skip_locals:
            local_a = run_one_claim(claim, stages["local_a"].config, stages["local_a"].template, stages["local_a"].client, retrieve, ollama_version)  # runs the claim through the 3B model, nothing else runs until it finishes, returns a Record object
            record.stages["local_a"] = asdict(local_a)  # converts Record object to a dict and stores it in this record's stages field
            record.verdict_local_a = local_a.extracted_label

            local_b = run_one_claim(claim, stages["local_b"].config, stages["local_b"].template, stages["local_b"].client, retrieve, ollama_version)
            record.stages["local_b"] = asdict(local_b) 
            record.verdict_local_b = local_b.extracted_label

            # check for failed stages
            for name, stage_record in (("local_a", local_a), ("local_b", local_b)):
                if stage_record.status != "ok":
                    raise RuntimeError(f"{name} failed:\n{stage_record.traceback}")

            # if the two models' verdicts contradict, escalate to cloud
            if local_a.extracted_label != local_b.extracted_label:
                escalate = True
                reason = reason or "disagreement"

            # audit and arbiter skills
            audit_stage = stages.get("audit")
            arbiter_stage = stages.get("arbiter")
            if audit_stage or arbiter_stage:
                report = read_report(claim.report)
                chunks = retrieve(claim, report)
                _, evidence_block, _ = build_prompt(claim, chunks, stages["local_b"].template, stages["local_b"].config)

            # arbiter block, fired only if a disagreement occured and the claim is not numeric
            if (arbiter_stage and reason == "disagreement" and not is_numeric_claim(claim.statement)):
                verdict, detail = arbiter.decide(claim.statement, evidence_block, arbiter_stage.template,
                lambda prompt: arbiter_stage.client(prompt, arbiter_stage.config)["response"])
                record.arbiter_verdict = verdict
                record.arbiter_detail = detail
                if verdict is not None and verdict == local_b.extracted_label:
                    escalate = False
                    reason = None

            # audit block, fired if both models said entailed
            if (audit_stage and not escalate and local_a.extracted_label == local_b.extracted_label and local_b.extracted_label is True):
                report_text = " ".join(e["context"] for e in report["context"])  # the entire filing text
                fired, detail = audit_skill.should_escalate(claim.statement, evidence_block, report_text, audit_stage.template,
                lambda prompt: audit_stage.client(prompt, audit_stage.config)["response"])
                record.audit_fired = fired
                record.audit_detail = detail
                if fired:
                    escalate = True
                    reason = "audit_detector"

        # the arithmetics skill is tried before any cloud call is made, only on claims the numeric detector already routed to the cloud, so a decline escalates to cloud anyways
        if escalate and "skill" in stages and is_numeric_claim(claim.statement):
            stage = stages["skill"]

            # Rebuild the evidence block the 3B actually read using local_a's own template and config, so the skill and the model it is correcting see the same text.
            report = read_report(claim.report)
            chunks = retrieve(claim, report)
            _, evidence_block, _ = build_prompt(claim, chunks, stages["local_a"].template, stages["local_a"].config)

            record.skill_verdict, record.skill_detail = arithmetic_skill.verify(
                claim.statement,
                evidence_block,
                stage.template,
                lambda prompt: stage.client(prompt, stage.config)["response"]  # passing a lambda function in the place of the call_model paramter slot. this function takes a prompt and outputs a string response, just as call_model inside verify asks.
            )

        # cloud block
        if record.skill_verdict is not None:
            # this means the skill answered so no need for a cloud call
            record.final_source = "skill"
            record.extracted_label = record.skill_verdict
            record.extraction_source = "arithmetic_skill"
            deciding = None
        elif escalate:
            cloud = run_one_claim(claim, stages["cloud"].config, stages["cloud"].template, stages["cloud"].client, retrieve, None)
            record.stages["cloud"] = asdict(cloud)
            record.verdict_cloud = cloud.extracted_label
            record.cloud_called = True
            if cloud.status != "ok":
                raise RuntimeError(f"cloud failed:\n{cloud.traceback}")
            deciding, record.final_source = cloud, "cloud"
        else:
            deciding, record.final_source = local_b, "local_b"  # deciding is a Record object

        record.escalation_reason = reason

        # copy the deciding stage's answer to the top level. if the skill fired, no need for this block
        if deciding is not None:
            for attribute in ("extracted_label", "extraction_source", "evidence_present", "context_overflow", "done_reason", "prompt_eval_count", "eval_count", "thinking", "served_model", "system_fingerprint", "chunks_requested", "chunks_kept"):
                setattr(record, attribute, getattr(deciding, attribute))  # puts the value of each of these attributes in the deciding Recrod object into this pipeline's record object

    except Exception:
        record.status = "failed"
        record.traceback = traceback.format_exc()

    record.elapsed_seconds = time.perf_counter() - started
    return record


STAGE_NAMES = ("local_a", "local_b", "cloud")
OPTIONAL_STAGE_NAMES = ("skill",)

def build_stages(config, clients):
    """load each stage's prompt template and pick its client"""

    stages = {}
    for name in STAGE_NAMES + OPTIONAL_STAGE_NAMES:
        if name not in config:
            if name in OPTIONAL_STAGE_NAMES:
                continue
            raise ValueError(f"pipeline config is missing the '{name}' stage")
        stage_config = config[name]  # a dict from the config file
        stages[name] = Stage(
            config=stage_config,
            template=load_prompt_template(stage_config["prompt_version"]),
            client=clients[stage_config.get("client", "ollama")],  # clients = {"ollama": call_ollama, "deepseek": call_deepseek}
        )
    return stages


def run_routed_sample(sample, config, results_dir, clients, retrieve, ollama_version=None):
    """iterate through the sample, route each claim, and write each record after it finishes."""

    stages = build_stages(config, clients)

    done = failed = skipped = 0
    cloud_calls = 0
    reasons = {"numeric_detector": 0, "disagreement": 0}

    for n, claim in enumerate(sample, start=1):
        if has_result(claim.example_id, results_dir):
            skipped += 1
            continue

        record = route_one_claim(claim, config, stages, retrieve, ollama_version)
        write_result(record, results_dir)

        if record.status == "ok":
            done += 1
        else:
            failed += 1

        if record.cloud_called:
            cloud_calls += 1
        if record.escalation_reason in reasons:
            reasons[record.escalation_reason] += 1

        cloud_rate = cloud_calls / done if done else 0.0
        decision = f"->cloud({record.escalation_reason})" if record.cloud_called else "->local"

        print(f"[{n}/{len(sample)}] {claim.example_id:<18}"
              f" {record.elapsed_seconds or 0:6.1f}s"
              f"  a={record.verdict_local_a} b={record.verdict_local_b}"
              f"  {decision:<28}"
              f"  label={record.extracted_label}"
              f"  cloud={cloud_rate:.1%}"
              f"  status={record.status}", flush=True)

    print(f"\n{done} ok, {failed} failed, {skipped} skipped, out of {len(sample)}")
    if done:
        print(f"cloud calls   {cloud_calls}/{done} = {cloud_calls / done:.1%}")
        print(f"detector    {reasons['numeric_detector']}")
        print(f"disagreement{reasons['disagreement']:>4}")
