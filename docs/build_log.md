# Build log

One entry per working session, newest last. What was built, what was measured, what was decided, and what went wrong.

The architecture plan holds the design. `working_state.md` holds current status. This file holds history, so that a decision made weeks ago can be traced back to the evidence that produced it.

---

## Week 1, to 29 July 2026

Not a build session. Setup and investigation.

Cloned `github.com/yilunzhao/FinDVer` at commit `e8bb237`. Installed Ollama, pinned at 0.12.3, and pulled `qwen2.5-coder:3b`, `qwen2.5-coder:7b`, and `nomic-embed-text`. Benchmarked both models on one real example and recorded throughput.

Confirmed the real data schema by inspection rather than from the paper. Found four things the paper or the plan had wrong: the report `context` elements are dicts and not strings, the examples are grouped by label in contiguous blocks, the split sizes are 700 and 1,700 rather than 600 and 1,500, and the test split ships with real labels.

Lost one test round, roughly 15 minutes, to a prompt construction bug. A loader assumed `context` elements were strings, and the fallback serialised raw dicts into the prompt while truncating each to 2,000 characters. Both models then produced confident figures that appear nowhere in the source document. From the output alone this is indistinguishable from a genuine extraction error. It was caught only because it happened during single example testing. The same bug inside a 100 example overnight run would have cost 8 hours and would have corrupted the error analysis.

Wrote `src/build_prompt.py`, a throwaway script, to produce one realistic prompt for benchmarking. Its output is preserved as `prompts/samples/ie-val-0_filled.txt`.

---

## 30 July 2026, professor meeting

Not a build session. Three decisions, all of which reshape the project. Recorded here on 31 July.

**The deliverable is settled.** A paper of about five pages, submitted to a workshop in Australia called *On-Device Intelligence: Foundation Models under Real-World Constraints*. Submission deadline 30 August 2026. I am first author, my professor is a co-author, and he will recruit about two industry co-authors to strengthen the author list.

This closes what was open question 4 in the architecture plan, and it voids the eight week schedule. Thirty days remain, not eight weeks.

**Baselines will not be re-run.** The paper's published numbers become the historical baseline and are used as they are. The cloud side is extended with two models released after the paper, from 2025 or 2026, with the provider not yet fixed. He offered Anthropic keys in addition to DeepSeek and Qwen. The edge side is extended with local models the paper did not evaluate.

**Run both ends before building the routed system.** He arrived at the edge only and cloud only framing independently. It was already in the plan, which is a useful confirmation rather than a change.

---

## 31 July 2026, first build session

### Built

`src/loader.py`. Reads `FinDVer/data/testmini.json`, validates the subset counts, and returns 700 `Claim` objects.

`Claim` is a frozen dataclass with 11 fields. Every record carries all 11 regardless of subset, with `None` where a subset does not have a field. This absorbs three pieces of raggedness in one place: `numeric` misspells the explanation field as `explaination`, `numeric` adds `python_calculation` and `execution_result`, and `knowledge` adds `knowledge`. Nothing downstream needs to know any of that. Frozen because the 700 objects stay alive for the whole run, so a write on one iteration would persist to every later one.

`src/sampler.py`. Groups claims into the six subset by label cells, draws a fixed number from each with a private seeded generator, shuffles the result, and checks the balance before returning.

The balance check is called inside `stratified_sample`, not by the caller, so an unchecked sample cannot exist. It raises rather than asserts, because `assert` statements are stripped under `python -O` and nothing guarding an 8 hour run should be removable by a command line flag.

The final shuffle exists for a specific reason. Without it the sample comes out in cell order, so a run that dies at example 40 leaves an unbalanced and unusable partial result. Shuffled, any prefix is roughly balanced.

`prompts/`. Split the week 1 `src/prompt.txt`, which was one fully filled prompt, into a reusable template at `prompts/baseline_v1.txt` and the original filled version at `prompts/samples/ie-val-0_filled.txt`. The filled version was recovered from commit `3cf9ffe` and verified byte identical, because it is the input the week 1 throughput numbers were measured on. A `prompts/README.md` records that provenance.

### Measured

Six subset by label cells hold 125, 125, 125, 125, 100, 100. The smallest cell is 100, which caps `per_cell`.

Walking `testmini.json` in file order, the report changes at 693 of the 699 adjacent pairs. Claims that share a report are scattered, not clustered, so caching the previously loaded report would buy nothing.

Parsing one report file takes about 7 milliseconds. Re-reading one per claim across all 700 costs about 5 seconds, which is 0.02 percent of an 8 hour run. Decision: no cache, load per claim. This replaced a guess with a measurement.

A first pass verdict regex was run against `FinDVer/outputs/testmini_outputs/rag/processed_cot_outputs/`, which holds 700 examples for each of 16 models with both the raw response and the label `gpt-4o-mini` extracted from it. Across 11,200 pairs the regex fires on 81.7 percent and, where it fires, agrees with the cloud extractor on 98.9 percent. Coverage falls sharply with model size: 100 percent for claude-3-5-sonnet, 91.3 percent for Qwen2.5-7B, 54.9 percent for Llama-3.2-3B. Full table in `working_state.md`.

### Found

The official FINDVER evaluation does two things that were not known before today, both read from `FinDVer/evaluation.py` and `FinDVer/utils/evaluation_utils.py`.

It extracts verdicts with a `gpt-4o-mini` call per example rather than a regex.

When no verdict is found it assigns `random.choice(["entailed", "refuted"])`. The example is scored as a guess and is never counted or reported. No `random.seed` appears anywhere in the repository, so the official score is not reproducible on identical predictions.

For the models in the paper this is a harmless simplification, because unparseable outputs are rare. At 3B scale it is not. A model failing the format on 30 percent of examples receives roughly 15 accuracy points of imputation.

Separately, the direct prompting extractor tests `"entail" in output` before `"refut"`, and "entail" is a substring of "not entailed", so that path mislabels negated conclusions. Chain of thought does not use that path, so it does not affect the numbers we compare against. Worth not copying.

### Decided

Sample size is 17 per cell, giving 102 examples and about 8 hours on the 3B model. Seed 0, fixed permanently, because every configuration compared has to run on the same examples. Use 2 per cell, giving 12 examples, for smoke tests.

Scoring reports two numbers from the same stored predictions. Strict, where unparseable is its own bucket and counts as wrong for the headline figure, with its rate reported. FINDVER compatible, where unparseable is coin flipped with a fixed seed, used only when placing our number beside a published one. The gap between them quantifies how much of a small model's official score is imputation.

The label extractor will be deterministic. No model based fallback until widened patterns have been measured against the stored responses. The official extractor cannot be replicated regardless, because it uses `gpt-4o-mini` and the available cloud keys are DeepSeek and Qwen, so the model route costs quota without buying comparability.

### Corrected

`working_state.md` described report `context` elements as having `id` and `context` keys. They have three, including `type`, which is `paragraph` or `table` and is free table detection. The architecture plan already had this right. The working state line was stale and is now fixed.

### Replanned

The 30 July meeting was relayed at the end of this session, so the schedule was rebuilt against the 30 August deadline. Section 12 of the architecture plan was rewritten.

Wall clock was converted into nights, because that is the real constraint on this machine. About 20 usable nights remain between 3 and 23 August. One 3B slice run costs one night, one 7B slice run costs two to three, and a full 700 run would cost seven.

**The first version of this replan was wrong and was corrected the same day.** It cut tiers 2 through 5, the full 700 run, and the leaderboard submission outright. Two errors. It cut retrieval, which is the core of the project, since the pipeline is RAG only by the professor's decision. And it priced the whole of tier 2 as needing overnight runs, when retrieval recall is scored against the gold `relevant_context` indices with no model calls at all. A k sweep, a BM25 comparison, and a decomposition comparison are minutes of work. Only the end to end accuracy delta needs a night.

Section 12.3 now bands scope rather than cutting it. Band A is committed and fits on this machine, and it includes standalone retrieval recall. Band B is conditional on faster hardware and holds the full 700 run, the end to end retrieval ablation, and the 7B comparisons. Band C is stretch. The banding exists because a faster machine may become available, which would move the boundary. Specs and date are unknown, recorded as open question 11.

Two results can carry the paper without a long run chain. Retrieval recall, which is cheap, standalone, and the project's stated focus. And the extraction and imputation analysis measured today, which rests on 11,200 responses, needs no compute, and is directly on topic for a venue about on device models under real world constraints. Open question 9 is to confirm the professor agrees before building the paper around the second one.

One consequence of reusing the paper's published numbers, which is easy to miss. Those numbers include coin flip imputation. Mixing them with strictly scored numbers of ours in one table would compare two different measurements and would understate our models exactly where they fail the output format. Any mixed table has to use the FINDVER compatible scoring. The two number reporting decided earlier today stopped being optional the moment the baseline strategy was set.

### Not done

Logging, label extractor, and evidence assertion. Three of the five harness pieces remain, due 2 August.

The script that produced the regex table still lives in a temporary scratchpad and will be wiped. Its numbers are now cited in three documents. It needs to move into the repository.
