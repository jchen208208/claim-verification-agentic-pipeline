"""Runs one experiment: iterates through a sample, call the model once per claim, logs the result.

The model call and the retriever are passed in rather than imported, so the
harness test can run the whole loop against stubs,
and the Tier 2 retriever can replace the Tier 0 one without touching this file.
"""

import json
import time
import traceback
from pathlib import Path
from collections.abc import Callable

from src.evidence_asserter import assert_evidence, check_overflow
from src.label_extractor import extract_label_with_source
from src.logger import Record, write_result, has_result
from src.loader import Claim

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

def run_one_claim(claim: Claim, config: dict, template: str, call_model: Callable[[str, dict], dict], retrieve: Callable[[Claim, dict], list[dict]]) -> Record:
    """Fills in the Record for one claim. Doesn't raise any errors.
    
    function paramters:
    - claim: a Claim object from the loader
    - config: a dict, one per experiment, from configs/. Holds model, num_ctx, num_predict, temperature, seed, prompt_version. It goes two places: into call_model, which needs the Ollama options, and whole into the Record, so a result file states exactly what produced it.
    - template: the prompt text with <REPORT> and <STATEMENT> still in it.
    - call_model: a function: (prompt, config) -> dict
    - retrieve: a function: (claim, report) -> list of context element dicts."""

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
        record.prompt = prompt

        record.evidence_present, record.evidences_found = assert_evidence(evidence_block, claim, report)

        # times how long the entire generation took (including prompt evaluation and output generation)
        start = time.perf_counter()
        raw = call_model(prompt, config)
        record.elapsed_seconds = time.perf_counter() - start

        # Ollama returns a raw dictionary with these elements: response = output string, prompt_eval_count = how many tokens it read from the prompt, eval_count = how many tokens it outputed, done_reason = stop (naturally finished generation) | length (generation truncated by num_predict cap)
        record.response = raw["response"]
        record.prompt_eval_count = raw.get("prompt_eval_count")
        record.eval_count = raw.get("eval_count")
        record.done_reason = raw.get("done_reason")

        record.context_overflow = check_overflow(record.prompt_eval_count, record.eval_count, config["num_ctx"])

        label, source = extract_label_with_source(record.response)
        record.extraction_label = label
        record.extraction_source = source

    except Exception:
        """A bad table or a Ollama bug becomes status="failed" plus a traceback on
        this example, so the run continues and resume retries it next time."""

        record.status = "failed"
        record.traceback = traceback.format_exc()

    return record