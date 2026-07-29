"""
Build a realistic RAG-sized FinDVer prompt for local model benchmarking.

Report schema (confirmed):
    {
      "url": str,
      "report_type": str,
      "context": [...],       # ~304 paragraphs/chunks
      "html_tables": [...]    # ~83 tables, as HTML
    }

Usage:
    python3 src/build_prompt.py
"""

import json
import os

# Paths are anchored to this file, not to the working directory, so the script
# runs the same from anywhere. The benchmark data is not tracked in git; it lives
# in the FinDVer/ clone at the project root. See README.md.
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)

DATA_FILE = os.path.join(PROJECT_ROOT, "FinDVer", "data", "testmini.json")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "FinDVer", "financial_reports")
PROMPT_OUT = os.path.join(SRC_DIR, "prompt.txt")

EXAMPLE_ID = "ie-val-0"
CONTEXT_WINDOW = 6      # distractor paragraphs on each side of gold evidence
PREVIEW = 300           # chars shown when previewing an element


def load_examples():
    with open(DATA_FILE) as f:
        return json.load(f)


def get_example(examples, example_id):
    for ex in examples:
        if ex["example_id"] == example_id:
            return ex
    raise ValueError(f"{example_id} not found")


def as_text(item):
    """Context elements may be plain strings or dicts; normalize to text."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("context", "text", "content", "paragraph", "value", "table"):
            if key in item:
                return str(item[key])
        return json.dumps(item)[:2000]
    return str(item)


def inspect(report, example):
    ctx = report["context"]
    tables = report.get("html_tables", [])

    print("=" * 70)
    print("STRUCTURE")
    print("=" * 70)
    print(f"url         : {str(report.get('url', ''))[:80]}")
    print(f"report_type : {report.get('report_type')}")
    print(f"context     : {len(ctx)} elements, first element type = {type(ctx[0]).__name__}")
    if tables:
        print(f"html_tables : {len(tables)} tables, first element type = {type(tables[0]).__name__}")
    else:
        print("html_tables : none")

    print("\n--- context[0] ---")
    print(as_text(ctx[0])[:PREVIEW])

    print("\n--- context[1] ---")
    print(as_text(ctx[1])[:PREVIEW])

    print("\n" + "=" * 70)
    print("GOLD EVIDENCE for this claim")
    print("=" * 70)
    for idx in example["relevant_context"]:
        print(f"\n--- context[{idx}] ---")
        print(as_text(ctx[idx])[:800])

    print("\n" + "=" * 70)
    print("html_tables[0] (first 600 chars)")
    print("=" * 70)
    print(str(tables[0])[:600] if tables else "(none)")
    print()


SYSTEM_PROMPT = (
    "As a financial expert, your task is to assess the truthfulness of the given claim "
    "by determining whether it is entailed or refuted based on the provided financial "
    "document. Follow these steps:\n"
    "1. Carefully read the given context and the claim.\n"
    "2. Analyze the document, focusing on the relevant financial data or facts related to the claim.\n"
    "3. Document each step of your reasoning process to ensure your assessment is clear and thorough.\n"
    "4. Conclude your analysis with a final determination. In your last sentence, clearly state "
    'your conclusion in the following format: "Therefore, the claim is {entailment_label}." '
    "Replace {entailment_label} with either 'entailed' (if the claim is supported by the document) "
    "or 'refuted' (if the claim contradicts the document or partially contradicts the document)."
)


def build_prompt(example, context):
    gold = example["relevant_context"]

    wanted = set()
    for idx in gold:
        for j in range(idx - CONTEXT_WINDOW, idx + CONTEXT_WINDOW + 1):
            if 0 <= j < len(context):
                wanted.add(j)
    selected = sorted(wanted)

    chunks = [f"[{i}] {as_text(context[i])}" for i in selected]
    report_text = "\n\n".join(chunks)

    user_prompt = (
        f"Financial Report:\n{report_text}\n\n"
        f"Claim to verify:\n{example['statement']}\n\n"
        "Follow the instructions and think step by step to verify the claim."
    )
    return SYSTEM_PROMPT + "\n\n" + user_prompt, selected


def main():
    examples = load_examples()
    ex = get_example(examples, EXAMPLE_ID)

    print(f"example_id : {ex['example_id']}")
    print(f"subset     : {ex['subset']}")
    print(f"report     : {ex['report']}")
    print(f"gold label : {ex['entailment_label']}")
    print(f"gold ctx   : {ex['relevant_context']}\n")

    with open(os.path.join(REPORTS_DIR, ex["report"])) as f:
        report = json.load(f)

    inspect(report, ex)

    prompt, selected = build_prompt(ex, report["context"])

    words = len(prompt.split())
    print("=" * 70)
    print(f"selected chunks : {selected}")
    print(f"prompt length   : {words} words (~{int(words * 1.4)} tokens)")
    print("target ~2000-3500 words; raise CONTEXT_WINDOW and rerun if short")
    print("=" * 70)

    with open(PROMPT_OUT, "w") as f:
        f.write(prompt)
    print(f"\nwrote {PROMPT_OUT}")
    print("\nNOTE: before pasting into ollama, raise the context window so this")
    print("isn't silently truncated at the 4096-token default:")
    print("    ollama run qwen2.5-coder:3b --verbose")
    print("    /set parameter num_ctx 8192")
    print("    (then paste the prompt)")


if __name__ == "__main__":
    main()
