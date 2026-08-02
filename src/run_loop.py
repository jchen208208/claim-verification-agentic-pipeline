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

