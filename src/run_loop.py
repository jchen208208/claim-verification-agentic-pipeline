"""Runs one experiment: iterates through a sample, call the model once per claim, logs the result.

The model call and the retriever are passed in rather than imported, so the
harness test can run the whole loop against stubs,
and the Tier 2 retriever can replace the Tier 0 one without touching this file.
"""

import json
import time
import traceback
from pathlib import Path

from src.evidence_asserter import assert_evidence, check_overflow
from src.label_extractor import extract_label_with_source
from src.logger import Record, write_result, has_result

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_DIR = REPO_ROOT / "prompts"
REPORT_DIR = REPO_ROOT / "FinDVer" / "financial_reports"

def load_prompt_template(prompt_version):
    # uses the versioned prompt file as a template, read once per run instead of once per claim
    with open(PROMPT_DIR / f"{prompt_version}.txt") as f:
        return f.read() # returns the entire prompt template as one string

def read_report(filename):
    # reads one report, takes around 7 ms which is why nothing is cached
    with open(REPORT_DIR / filename) as f:
        return json.load(f)

def build_prompt(claim, chunks, template):
    """Returns (prompt, evidence_block).
    The evidence block is the retrieved text and is returned
    separately because the evidence asserter has to check it in isolation."""

    # chunks are the retrieved context element dicts
    evidence_block = "\n\n".join(chunk["context"] for chunk in chunks)

    # builds the prompt
    prompt = (template.replace("<REPORT>", evidence_block).replace("<STATEMENT>", claim.statement))

    # the template could lose its placeholder in a later version and we need to prevent the prompt going to the model with no evidence in it at all
    assert evidence_block in prompt

    return prompt, evidence_block


LABEL_TO_BOOL = {"entailed": True, "refuted": False}

def run_one_claim(claim, config, template, call_model, retrieve):
    """Everything for one claim, returned as a filled Record. Never raises.

    One bad table or a dead Ollama becomes status="failed" plus a traceback on
    this example, so the run continues and resume retries it next time."""

    record = Record(
        example_id=claim.example_id,
        subset=claim.subset,
        gold_label=claim.entailment_label,
        gold_explanation=claim.explanation,
        prompt="",
        config=config,
    )

    try:
        report = read_report(claim.report)
        chunks = retrieve(claim, report)
        prompt, evidence_block = build_prompt(claim, chunks, template)
        record.prompt = prompt   # filled the moment it exists, so a later
                                 # failure still logs what went to the model

        record.evidence_present, record.evidences_found = assert_evidence(evidence_block, claim, report)

        start = time.perf_counter()
        raw = call_model(prompt, config)
        record.elapsed_seconds = time.perf_counter() - start

        record.response = raw["response"]
        record.prompt_eval_count = raw.get("prompt_eval_count")
        record.eval_count = raw.get("eval_count")
        record.done_reason = raw.get("done_reason")

        record.context_overflow = check_overflow(record.prompt_eval_count, record.eval_count, config["num_ctx"])

        label, source = extract_label_with_source(record.response)
        record.extraction_source = source

    except Exception:
        record.status = "failed"
        record.traceback = traceback.format_exc()

    return record