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

### Found from the workshop site: the deadline is a day earlier than every document said

Read from odi2026.github.io on 1 August, provided as page content rather than from the professor. This closes open question 10, which had been waiting on him.

The submission deadline is **29 August 2026 at 23:59 anywhere on earth**, not 30 August. Every plan document carried 30 August, taken from the professor at the 30 July meeting. The AoE clock runs to 04:59 Pacific on the 30th, which is upload buffer rather than a working day, so Phase 5 writing is six days and not seven. Corrected in section 1.1 and section 12.2 of the plan, in `working_state.md`, and in `CLAUDE.md`.

Three other mechanics matter beyond the date.

Review is **double blind**. That changes how the paper is written and not only how it is formatted: no author names, no reference to our own earlier work, and the repository link anonymised or withheld. Better known now than during the final edit.

The venue is **non archival**. A fuller version can go to an archival venue afterwards, so this paper does not have to be the last word on the project. That lowers the cost of Band B not landing in time.

It is a **NeurIPS 2026 workshop** in Sydney on 11 or 12 December, which the plan had recorded only as a workshop in Australia. Organisers are from ETH Zurich, MPI for Intelligent Systems, and MIT. Five pages excluding references, NeurIPS 2026 LaTeX template, submitted through OpenReview, notification 29 September.

Two of the five listed topics fit directly. Topic 05, benchmarks and evaluation for real world deployment, asks for metrics that jointly assess performance and reliability under realistic deployment conditions, which is exactly what the extraction and imputation analysis is. Topic 02 covers the edge and cloud pipeline itself. Both should be named on the submission.

### Not done

Logging, label extractor, and evidence assertion. Three of the five harness pieces remain, due 2 August.

### Also built

`scripts/measure_extractor_baseline.py`, which regenerates the regex table above. Its data path is anchored to `__file__` rather than hardcoded, matching the loader. It holds its own copy of the regex in a constant called `PATTERN`, because it was written before `label_extractor.py` existed. That copy has to become an import once the extractor exists, otherwise the two drift apart and the measurement stops describing what is shipped.

---

## 1 August 2026, second build session

### Built

`src/label_extractor.py`. Raw response string in, `"entailed"`, `"refuted"`, or `None` out. Three levels tried in order of precision, last match winning inside a level.

The anchored level matches a concluding sentence such as "the claim is entailed" over the whole response. The bare level matches a standalone `entailed` or `refuted` but only inside the last 300 characters, because both words appear all through the reasoning and in the prompt's own instructions, so a match in the body is not a conclusion. Two guards sit on the bare level. A hedge such as "partially entailed" returns `None`, because that is not a binary verdict and inventing one is exactly what the `None` bucket exists to prevent. A direct negation such as "not entailed" returns the opposite label, which is safe only because the FINDVER label space is binary.

`extract_label_with_source()` returns the level that fired alongside the verdict. `extract_label()` is a one line wrapper over it, so the pipeline keeps a simple call and there is one implementation rather than two that can drift.

`scripts/measure_extractor_baseline.py` now imports the extractor instead of holding its own `PATTERN` constant, which was the first thing on the session's list. It also reports the per level breakdown.

### Measured

Coverage across all 11,200 upstream responses rose from 81.7 to 87.8 percent. Agreement with the `gpt-4o-mini` labels fell from 98.9 to 98.3. On Llama-3.2-3B, the closest analogue to our model, coverage rose from 54.9 to 65.3 percent, which in whole examples is 373 correct extractions rising to 437 against 11 wrong rising to 20.

Level breakdown over 11,200: anchored 81.7 percent, bare 5.8, negated 0.3, hedged 2.3, none 9.9.

The hedged and none buckets separate models in a way a single unparseable number would hide. `gemini-1.5-pro` is 6.3 percent hedged and 0.4 percent none. `Meta-Llama-3.1-8B` is 1.9 percent hedged and 40.3 percent none. One model always concludes and then qualifies it, the other frequently never concludes at all. The two buckets stay separate for that reason.

### Decided: no model based fallback

This was deferred on 31 July pending a measurement, and the measurement settles it.

Of Llama-3.2-3B's 231 remaining `none` responses, 81 percent contain the strings "entail" or "refut" nowhere in the response at all. There is no verdict in the text. A DeepSeek or Qwen call on those would not be extracting anything, it would be reading the reasoning and forming its own judgment. That is imputation wearing a parser's clothes, and it is worse than the coin flip because it does not look random. It would also cost quota per unparseable example.

Widening also stops here. Only 15 percent of the residual has a verdict word in the body but outside the tail window, and reaching it means widening the window into the reasoning and trading precision for a handful of examples.

### Found: the upstream outputs were generated at temperature 1.0 with a 1024 token cap

The most consequential thing learned today. Read from `run_llm.py` lines 44 to 47 and `scripts/inference/main_vllm.sh`, which passes no sampling overrides, so the argparse defaults reached vLLM at `run_llm.py:125`. Temperature 1.0, top_p 1.0, max_tokens 1024.

None of that is an error by the authors. All three are ordinary defaults. But they are not our settings, and two of them are doing real damage to the small models.

The cap is provably biting. On Llama-3.2-3B, 108 of 700 responses end with no terminal punctuation, and their word counts pile against a hard ceiling, p90 863 and max 916, that cleanly ending responses never approach at max 827. A ceiling in one group and not the other is the signature of a generation cap. Ninety of those truncated responses land in the `none` bucket, which is 39 percent of that bucket and about 13 percent of all 700 examples. Those responses were cut off mid reasoning, not incapable of concluding.

The consequence is that the 33 percent unparseable rate is not a forecast of ours. We run at temperature 0 and we set `num_predict` ourselves, so both mechanisms most likely driving it are already off. The line "3B models fail the output format 45 percent of the time" must not go into the paper on the strength of the upstream table. Our own number has to come from our own model.

A second consequence for the framing. The published FINDVER baselines are non reproducible on two axes rather than one: sampled generation at temperature 1.0, then the unseeded coin flip at scoring time. Section 11.8 previously recorded only the second.

The token soup and near empty generations in the upstream files are consistent with temperature 1.0, but that is unverified, since testing it would mean re-running their models.

### Found: `num_predict` is the silent twin of `num_ctx`

`num_ctx` caps the input and drops evidence out of the prompt. `num_predict` caps the output and cuts the response off before the verdict, which sends the example to the unparseable bucket disguised as a format failure. Same silence, opposite end of the call. Added to section 4.3 and to the config gotchas in section 11. Ollama's default on v0.12.3 has not been checked and must be before the first batch run.

### Corrected two false claims in the plan

Sections 4.6 and 11.8 both stated that neither local model produced the required output sentence in week 1 testing. That was wrong. It described the first test round, which ran before `num_ctx` was set and whose prompt was corrupted by the loader bug. On the re-run at `num_ctx` 8192 both models did produce the required sentence. The section 4.6 table had been mixing the two rounds, since its own caption already says `num_ctx` 8192.

The corrected value comes from recollection rather than a preserved artifact, so both places now mark it provisional. It will be settled by the first smoke run. Section 11.8 also gained a line saying the case for the extractor never rested on that datapoint, since otherwise the correction reads as undermining the whole item.

One bad test round propagated a false claim into two sections of the plan. Worth remembering when a week 1 finding is cited later.

### Decided provisionally: the cloud tier emits the verdict sentence

Section 4.4 assigned "filling the final output template" to the edge 3B model, on the reasoning that formatting is mechanical once the thinking is done. The cloud tier is already generating the explanation, so it is already emitting text. Passing that text to a 3B model purely to wrap it in the required sentence adds a second model call, a second failure mode, and about 35 seconds per example extrapolated from the section 4.6 rates, and it means the extractor reads the 3B's formatting rather than the cloud model's.

That row is now provisionally reassigned to cloud, recorded as a sub question under open question 1 for the professor. It costs the contribution nothing, since role to model assignment across decomposition, `.loc` generation, glossary spotting and the first pass verifier screen is untouched, and moving a row because measurement says so is section 4.5's method working.

One trap named while deciding this. The safe version is cloud doing the reasoning and emitting the verdict as one step. The unsafe version is cloud as a formatting pass over edge reasoning, because on the examples where the 3B never concluded, the cloud model would be handed inconclusive reasoning and asked to state a verdict. It would comply. That converts a `none` into a confident verdict by judgment, which is imputation with extra steps and is worse than the coin flip because it looks like reasoning. Same architecture diagram, opposite epistemics.

### Also recorded: why strict scoring is the working number

Section 9 already said when to use FINDVER compatible scoring but never said why using it elsewhere is dangerous. Added. Every internal comparison is strict against strict, because strict has no random component, so a difference between two runs is a real difference. FINDVER compatible cannot do that job. It injects a coin flip into every cell, and worse, the flip inflates weak configurations more than strong ones, because a configuration with more unparseables has more examples to guess on. An ablation table scored that way would misreport which change helped.

### Three silent bugs, all in one afternoon

Worth logging as a class, because none of them raised an exception.

An `if` block written one indentation level short sat outside its `for` loop. The loop ran 700 times rebinding a variable and the body ran once, on the last record. Coverage read 0.1 percent.

`agrees ++ 1` instead of `agrees += 1`. Python has no `++` operator, so that parses as `agrees + (+1)`, a legal expression whose value is discarded. The counter never moved and the column read 0.0 percent.

The same guard condition pasted twice, so a branch tested `_HEDGE_BEFORE` where it needed `_NEGATION_BEFORE`. The first branch already returned on that condition, making the second unreachable, so 30 negated responses came back with the label reversed. Coverage looked perfect and only the agreement column moved, by 0.2 points.

All three produced plausible looking tables. This is the argument for making each block's verification "reproduce this exact number" rather than "check it looks reasonable", and it is the same failure mode as the week 1 loader bug.

### Measured at the end of the session: Ollama 0.12.3 evicts prompt tokens during generation

Started as a two minute sanity check on an open question and turned into the most operationally important finding of the day.

The question was what Ollama does when generation fills the context window. Documentation was not consulted, because this behaviour has changed across versions and we are pinned to 0.12.3, so any answer found online would describe a different build. Tested directly against the local server instead. A canary string was placed at the very start of a 74 token prompt, a long generation was requested, and only `num_ctx` was varied.

    num_ctx  192 | prompt  74 | eval 268 | total 342 | done=stop | canary LOST
    num_ctx  256 | prompt  74 | eval 339 | total 413 | done=stop | canary LOST
    num_ctx  512 | prompt  74 | eval 286 | total 360 | done=stop | canary OK
    num_ctx  512 | prompt 512 | eval 277 | total 789 | done=stop | canary LOST, confabulated

Generation is not stopped by the window. Totals reached 342 and 413 against windows of 192 and 256, so decoding continues and the oldest tokens are evicted to make room. `done_reason` returned `stop` in every case and never `length`, so the API reports a clean normal completion while data is being destroyed. The model confabulates rather than reporting the loss: in the overflow run it stated the secret code was "double entry", and it silently dropped the trailing instruction to state the code at all, because that had scrolled out of view as well.

The first attempt at this test failed to overflow anything, because the model abbreviated a counting task with an ellipsis and stopped after 36 tokens. The second attempt confounded two mechanisms, because the prompt was itself larger than the window. Only the third design, holding the prompt fixed and small while shrinking `num_ctx`, isolated context shifting from input truncation.

**This changes the evidence assertion in section 11.9, which was wrong as written.** It said to alarm when `prompt_eval_count` equals the configured window. That catches input side truncation only. A prompt that fits perfectly at ingestion can still have its evidence scrolled out mid generation if the response is long, and the planned string presence check passes while that happens because the prompt string is fine. The loss occurs later, inside the model. The correct condition is `prompt_eval_count + eval_count >= num_ctx`, and both counts have to be logged per call. That sum is the only available signal, since the response text and `done_reason` both look healthy.

### Measured: KV cache cost, and a corrected claim

Resident size for `qwen2.5-coder:3b` as `num_ctx` varies, on 16 GB physical: 4096 gives 2.4 GB, 8192 gives 2.6, 16384 gives 3.2, 32768 gives 4.4. About 0.07 GB per extra 1k of window.

This corrects a claim made earlier the same day in section 4.3, that 16 GB was no place to allocate a 32k window. That was an assumption, not a measurement, and it was wrong. RAM is not the binding constraint for the 3B model. The 7B has a larger cache and has not been measured.

The consequence is that a generous window is cheap insurance, because an unused window costs only that RAM and not time, while actual prompt tokens cost 19.1 tok/s of ingestion. Settings chosen: `num_ctx` 16384 and `num_predict` between 1500 and 2000. Upstream's 1024 truncated a verbose 3B mid reasoning, and Llama-3.2-3B's cleanly ending responses ran a median of 354 words and a max of 827, so roughly 1100 tokens covers the longest observed. That leaves 16384 against about 4500 prompt plus 2000 generation, roughly 9800 tokens of slack, which makes overflow arithmetically impossible rather than merely unlikely. Our own model still has to confirm the generation figure on the smoke run.

The model reports a 32768 context length and ships no baked-in parameters, so Ollama's own defaults apply unless we override them. We override both on every call regardless, which makes the defaults irrelevant.

Also recorded in section 4.3: raising both caps is not the fix and is not a coherent setting. `num_ctx` is the total window and prompt plus generation share it, so raising `num_predict` past the remaining room only changes which limit binds first. Uncapped output is a hazard rather than a fix, because a small model at temperature 0 can loop and consume an entire night on one example. And a larger `num_ctx` costs RAM at load time whether the tokens are used or not, which matters at 16 GB on CPU.


### Not done at the end of the afternoon session

Per example logging and the evidence assertion. Two of the five harness pieces remained. The extractor was committed across `9b09cfc`, `95da412`, and `5128a21`.

---

## 1 August 2026, evening session
A short session, about an hour. One piece was chosen deliberately rather than starting both.

### Decided: build the logger before the evidence assertion

The two remaining pieces are not independent and the dependency runs one way.

The evidence assertion is now two checks. The second one, `prompt_eval_count + eval_count >= num_ctx`, reads two numbers off the Ollama response and has to record them somewhere per example. That somewhere is the log record. Building the assertion first means inventing the record shape implicitly and reworking it afterwards.

The second check is also untestable without a live model call, so it does not fit an hour. The logger is testable with fabricated inputs and no model at all.

### Built

`src/logger.py`. Three parts.

`Record`, a dataclass of 17 fields. Six are known before the model call: `example_id`, `subset`, `gold_label`, `gold_explanation`, `prompt`, `config`. Seven are filled after it: `response`, `extracted_label`, `extraction_source`, `prompt_eval_count`, `eval_count`, `done_reason`, `elapsed_seconds`. Two are left for the evidence asserter: `evidence_present`, `context_overflow`. Two belong to the run loop's try/except: `status`, `traceback`.

`Record` is deliberately **not** frozen, which is the opposite choice from `Claim` in the loader. A claim is input data and nothing should write into it. A record is output filled in three stages, so freezing it would mean rebuilding the object each time.

`write_result(record, results_dir)` writes one JSON file per claim, named `<example_id>.json`, into a per experiment directory. It calls `mkdir(parents=True, exist_ok=True)` itself, so the experiment directory appears on first write and no setup step has to remember to create it. `results/` is already in `.gitignore`.

`has_result(example_id, results_dir)` is the resume check.

### Decided: three small things inside the logger

**Resume tests `status == "ok"`, not file existence.** A failed example still writes a file, because that is the whole point of logging the traceback. Existence alone would skip failures forever and re-running to fix them would silently do nothing.

**A `json.JSONDecodeError` returns `False` rather than propagating.** A process killed mid write leaves a half file. Without the catch, resume crashes on startup on the one file it exists to recover from.

**The filename helper was inlined.** A two line `_result_path()` was written first and then removed, on the grounds that a one line abstraction used twice is not worth a function. The cost is that the `.json` suffix and the naming scheme now appear in two places, `write_result` and `has_result`, and if they ever disagree then resume returns `False` for every example, re-runs the whole night, and raises nothing. Recorded because the failure is silent, which is the class of bug this project keeps hitting.

### Two bugs, both loud for once

`mkdir(parent=True)` instead of `parents=True`. No such keyword, so it raises `TypeError`.

`results_dir.mkdir(...)` called before coercing the argument with `Path()`. `has_result` coerced internally and `write_result` did not, so the same argument had two different contracts, and passing a string worked in one function and raised `AttributeError` in the other.

Unlike the afternoon's three bugs, both of these raise. Worth noting the contrast: the afternoon's bugs all produced plausible tables and no exception.

### Verified

15 checks, all passing, in `scratchpad/verify_logger.py`. It uses fabricated `Record` objects and a scratch directory, so it never touches `results/`.

    directory absent before the write, created by the writer
    file is named for the example_id
    all 17 fields survive the round trip through JSON
    nested config survives, gold_label stays a bool, unfilled asserter fields are null
    has_result: ok True, failed False, unknown id False
    three writes of the same id leave one file, not three
    a truncated json file returns False instead of raising
    both functions accept a plain string path

The last two are the ones that matter. A truncated file is exactly the state a crash mid write leaves behind, and it is the case that would otherwise take down resume on startup. Three writes leaving one file settles the duplicate question by test rather than by argument.

### Checked: `example_id` is safe to use as a filename

All 700 ids in testmini are unique and match `[A-Za-z0-9._-]+`, so no sanitising is needed and no two claims can collide on one file. Checked against the loader rather than assumed.

### Estimated: the storage cost of logging every prompt

The measured part is the prompt. The one filled sample kept from 31 July, `prompts/samples/ie-val-0_filled.txt`, is 15,017 characters. The response is assumed at roughly 2,000 tokens, about 8,000 characters, and the remaining fields at about 1,000. That gives roughly 23 KB per record.

    102 example run     about 2.3 MB
    700 example run     about 16 MB

Twenty experiments at 102 examples is under 50 MB, and `results/` is not tracked. Storage is not a reason to log less. The alternative, dropping the prompt from the record, saves 15 KB per example and costs the ability to answer whether the evidence was actually in the prompt, which is the question that cost a test round in week 1.

These are estimates from one real prompt, not a measurement of written files. The real number arrives with the smoke run.

### Not done

The evidence assertion, and the run loop. Four of the five harness pieces are now built and verified. See the next session note in `working_state.md`.
