# CLAUDE.md

## What this project is

We build an edge-cloud agent that verifies financial claims against long SEC filings, evaluated on the FINDVER benchmark. A local Qwen2.5-Coder-3B model via Ollama does the mechanical work, professor-provided cloud APIs (DeepSeek, Qwen) handle judgment-heavy steps, and a large fraction of the pipeline is plain Python with no model involved. The pipeline is RAG-only by the professor's decision. There is no long-context variant.

This is a two-month undergraduate research project. I am the only developer. I am learning retrieval, NLP evaluation, and finance as I go.

## Reference documents

Two documents outside the code are authoritative. Do not summarise them from memory. Read the relevant section when a question touches it.

- `docs/architecture_plan.md` holds the stable material: architecture, build order, schedule, data schema, related work, evaluation plan.
- `docs/working_state.md` holds fast-changing status only. Read it first when I ask what is done or what is next.

Both are long. Read the section you need rather than the whole file.

## Hard constraints

- Hardware is a 2017 Intel MacBook Pro, 16 GB RAM, macOS 13, CPU-only inference. There is no usable GPU.
- Ollama is pinned at v0.12.3. Auto-update must stay off. Version 0.12.4 dropped macOS 13 support and this machine cannot upgrade.
- Measured throughput on a roughly 4,000 token prompt is 4 m 45 s per example on the 3B model and 11 m 46 s on the 7B. A 100-example run takes about 8 hours on the 3B model. Full testmini (600 examples) takes about two days.
- One configuration per overnight run is the realistic iteration cadence. Do not propose anything that needs repeated full runs without saying what it costs in wall-clock hours.
- There is no training compute. Fine-tuning, pretraining, and distillation are out of scope. Do not suggest them.
- Cloud API access is provided by my professor and is not unlimited. Prefer designs that keep cloud calls low, and say roughly how many calls per example a suggestion adds.

## Data traps that have already cost time

These are confirmed by inspection, not assumed. Any code touching the data must respect them.

1. Each element of a report's `context` array is a dict with `id` and `context` keys, not a string. A loader that assumes strings produces garbage silently instead of failing. This cost a full benchmarking round in week 1.
2. The examples are sorted by label. All refuted examples come first within each subset. Taking the first N examples yields a 100% refuted sample on which "always refuted" scores 100%. Every sample must be stratified by subset and label, or shuffled with a fixed seed, and the sampler must assert the resulting balance before a run starts.
3. Ollama's default `num_ctx` is 4096 and it truncates without warning. A realistic prompt here runs 3,900 to 4,500 tokens. Pass `num_ctx` explicitly in every API call. Interactive `/set parameter` does not persist between sessions.
4. The `numeric` subset spells the explanation field `explaination`. The other two subsets spell it correctly. Handle both keys.
5. Field names are `statement`, `entailment_label` (a bool, not a string), `relevant_context`, and `report`. They are not `claim`, `evidence`, or `doc_id`.
6. Tables appear twice: as pipe-delimited text inside `context`, and as raw HTML in `html_tables`. Gold evidence indices point into `context`, so the mapping between the two has to be built explicitly.
7. Cells that look numeric are strings. `"$1,204,500"`, `"(45,300)"` for a negative, `"—"`, and `"65,300 *"` all need cleaning before arithmetic. A nearby "(in thousands)" changes the true magnitude by 10^3 and produces no error at all.

## Accuracy rules

- Verify before concluding. Before attributing a failure to a model, check that the input reaching the model was actually correct. Before reporting a result, check that the measurement was not corrupted. The week-1 failure looked exactly like model hallucination and was a loader bug.
- Assert evidence presence after building every prompt. Check that a distinctive token from the gold evidence is literally present in the prompt string, and log `prompt eval count` per call. A count equal to the configured context window means truncation.
- Do not invent numbers. Benchmark figures, timings, recall rates, and paper results come from the plan or from something we measured together. If a number is not available, say so.
- Do not claim anything is novel or unattempted without checking. Program of Thought, RAG, multi-agent verification, and table parsing are all established. Our contribution is applying them where nobody has, plus the per-error-category analysis. The leaderboard check and the citation sweep are still outstanding, so any "nobody has done X" sentence is unverified until they are done. Say you are unsure rather than asserting we are first.
- Flag contradictions with the plan. The plan is a living document and parts of it will turn out to be wrong. Say so rather than quietly working around it.
- An unparseable model verdict goes into an explicit `unparseable` bucket that is counted and reported. Neither local model produced the required final sentence in week-1 testing, so label extraction needs regex, paraphrase fallbacks, and that bucket. Never coerce a silent default.

## How to work with me on code

Do not write a whole script in one pass, even a short one. I am here to learn the material, not to receive working files.

1. We discuss the shape of the script first: what it does, what the pieces are, which programming concepts are involved.
2. I restate my understanding. You correct it or confirm it.
3. We break the work into small blocks and write one block at a time.
4. I ask for clarification when something is unclear. Explain concisely but in real detail, assuming no background in the field.

Explain a new concept in plain language the first time it appears, and use a concrete example rather than a definition where one exists. Do not assume I know an acronym because it appeared earlier in a document.

When a question of mine rests on a wrong assumption, say so directly instead of answering it as asked.

## Code conventions

- Temperature 0 everywhere. Fixed seeds. Prompts versioned in git.
- Log every prompt, response, retrieved chunk, and executed snippet, per example, to disk.
- One config file per experiment. Per-example JSON results. One script regenerates every results table.
- The sandbox uses whitelisted builtins, allows nothing beyond pandas and math, has a timeout, and never runs unrestricted `exec`. Return the traceback to the model on failure so it can retry.
- Table parsing ships with a raw-text fallback from day one. A table that fails to parse is passed as text, which is what all prior work did for every table.
- No agent framework. Plain scripts with explicit control flow, chosen for debuggability.

## Where things live

Written so far: nothing beyond throwaway prompt-construction code. The harness is the next task. Keep this section updated as directories appear.

```
FinDVer/               clone of the upstream benchmark repo, not tracked in git
  data/                FINDVER claim records (testmini.json, test.json)
  financial_reports/   one JSON per filing, 600 files
docs/                  architecture plan, working state
src/                   our pipeline code
results/               per-example JSON output, one directory per experiment, not tracked
configs/               one config file per experiment
```

The claim records and the filings live inside `FinDVer/`, not at the top level. That
directory is a clone of https://github.com/yilunzhao/FinDVer.git pinned at commit
e8bb237. It is 1.3 GB and `.gitignore` excludes it. See `README.md` for the clone step.
Code in `src/` must not assume the data sits beside it.

Never commit API keys. Keys live in the environment, not in a tracked file.

## Writing anything my professor will read

He is based in China and English is not his first language.

- Keep sentences short and direct. Complete sentences that begin with a noun or pronoun, not a verb.
- Never use an em dash. Use a comma, a colon, or a full stop.
- Avoid research jargon unless the term is standard in his field. Write "the line between the two models" rather than "the edge-cloud routing boundary."
- Include what went wrong and how I fixed it. He values thoroughness and independent debugging. Clean results alone read as hiding something.
- Never overstate what is finished.
- State both time zones in any proposed meeting time. China is Pacific plus 15 hours. Tuesday 7pm PDT is Wednesday 10am Beijing.
- Cut a third of the words from any explanatory paragraph that survives it.
