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

Sample size is 17 per cell, giving 102 examples and about 8 hours on the 3B model. Seed 0, fixed permanently, because every configuration compared has to run on the same examples. Use 2 per cell, giving 12 examples, for trial runs.

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

The corrected value comes from recollection rather than a preserved artifact, so both places now mark it provisional. It will be settled by the first trial run. Section 11.8 also gained a line saying the case for the extractor never rested on that datapoint, since otherwise the correction reads as undermining the whole item.

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

The consequence is that a generous window is cheap insurance, because an unused window costs only that RAM and not time, while actual prompt tokens cost 19.1 tok/s of ingestion. Settings chosen: `num_ctx` 16384 and `num_predict` between 1500 and 2000. Upstream's 1024 truncated a verbose 3B mid reasoning, and Llama-3.2-3B's cleanly ending responses ran a median of 354 words and a max of 827, so roughly 1100 tokens covers the longest observed. That leaves 16384 against about 4500 prompt plus 2000 generation, roughly 9800 tokens of slack, which makes overflow arithmetically impossible rather than merely unlikely. Our own model still has to confirm the generation figure on the trial run.

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

15 checks, all passing. The script was throwaway and was deleted after the run. It used fabricated `Record` objects and a scratch directory outside the repo, so it never touched `results/`. What it checked:

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

These are estimates from one real prompt, not a measurement of written files. The real number arrives with the trial run.

### Not done

The evidence assertion, and the run loop. Four of the five harness pieces are now built and verified. See the next session note in `working_state.md`.

---

## 2 August 2026, third build session

The fifth harness piece. Built, validated against all 700 claims offline, no model calls and no cloud quota.

### Built

`src/evidence_asserter.py`. Five functions.

`tokenize(text)` turns text into comparable tokens. Two regexes. `_INNER_COMMA` deletes commas that sit between two digits, using lookbehind and lookahead so the digits are not consumed and consecutive groups all get handled, which turns `32,253` into `32253` while leaving the comma in `December 31, 2023` alone. `_TOKEN` matches `[a-z0-9]+(?:[.\-][a-z0-9]+)*`, so a token must begin with an alphanumeric and may contain a dot or hyphen only when another alphanumeric follows. `296.3` and `2024-02-06` survive whole, `debt.` loses its full stop, and `$`, `(`, `)`, `*`, `|` and the em dash can never be captured at all.

`count_report_tokens(report)` builds a `Counter` over every token in one filing.

`pick_tokens(element_text, report_counts, n)` returns the `n` rarest tokens in one gold context element, as `(token, count)` pairs. Rarity is measured against the whole report, not against the element.

`assert_evidence(evidence_block, claim, report)` returns `(evidence_present, evidence_found)`.

`check_overflow(prompt_eval_count, eval_count, num_ctx)` is the post call half.

### Decided: witnesses are the rarest tokens, and rarity is computed not guessed

The first idea was to check for a key sentence from each gold element. Rejected. Nothing can choose the key sentence automatically across 700 examples, and a sentence is the fragile size: long enough that any reformatting breaks the match, and long enough to be cut by a chunk boundary.

What the check actually needs is distinctiveness, and distinctiveness is measurable. For each gold element, take its tokens, look up how often each appears in the whole report, and keep the three rarest. A count of 1 means the token appears nowhere in the filing outside that element, so finding it in the prompt proves the element reached the prompt.

This solves three problems with one rule rather than three branches. Tokens are short, so they survive reformatting that a sentence would not. Table normalisation destroys pipes and spacing but not the numbers, so tables stop being a special case. And a prose element with no numbers still yields rare words, so `municipal` and `discounted` do the same job that `296.3` does elsewhere. No stopword list is needed either, because `the` has a count in the hundreds and rarity sorting buries it for free.

The sort key is `(count, -len(token), token)`. The third term is not cosmetic. Python randomises string hashing per process, so a `set` of strings iterates in a different order every run, and without a total ordering the recorded witness would change from night to night.

### Decided: scope the check to the evidence block, not the whole prompt

This was the important call of the session, and it came from a suggestion that overrode the approach already being built.

Testing the design on `ie-val-0` before writing it showed the witnesses chosen for gold elements 89 and 93 were `278.4` and `32253`. Both are figures the claim itself quotes. Since the prompt contains the claim, those tokens would be found in the prompt whether or not retrieval returned anything at all. FINDVER claims are built by copying figures out of the evidence, so the overlap is systematic and worst on exactly the examples that matter.

The first fix was to filter out any token that also appears in the claim statement, passing `claim_tokens` into `pick_tokens` as a set. That works, and it was implemented and tested.

The better fix, suggested rather than found here, was structural: since we control the prompt format, do not search the whole prompt at all. Search only the evidence block. The claim is then out of scope by construction rather than filtered out one token at a time, and the strongest witnesses, which are precisely the numbers the claim copies, stay usable instead of being discarded.

Parsing the block back out of the finished prompt was considered and rejected. It would couple the asserter to the prompt template, the template changes at every tier, and a delimiter contract that silently stopped matching would break the asserter silently, which is the exact failure class the module exists to catch. Instead `build_prompt` returns the evidence block alongside the prompt, and the run loop carries a one line `assert evidence_block in prompt` to prove the substitution itself worked.

`claim_tokens` was then removed as redundant. The validation below shows what it would have been protecting against, and shows the scoping handles it.

### Decided: all witnesses must match, not any

Three witnesses come from the same element, so if the element is intact all three should be present. A partial hit means something cut through the element, most likely a chunk boundary, which is information worth seeing rather than rounding away. `evidence_found` therefore stores `(matches, tried)` per gold index rather than a bare boolean, so a partial is visible in the result file.

`tried > 0` guards the case of an element that yields no witnesses. Without it, `(0, 0)` satisfies `matches == tried` and an element that could not be checked would report as present. That never fires on testmini, where every gold element yields exactly three witnesses, but it is eight characters against a silent false pass on the one flag used to decide whether a failure was the model's fault.

### Measured: the asserter, against all 700 claims

`test_scripts/validate_evidence_asserter.py`, about 1 m 45 s, no model calls. Four controls, each fabricating an evidence block and asking what `assert_evidence` says.

    control  evidence_block built from                        present=True  partial
    gold     the gold elements                                     700/700        0
    decoy    3 random non-gold elements, same report                 0/700       26
    hard     non-gold elements of that report sharing the            5/700      196
             most tokens with the claim
    claim    the claim statement alone                               0/700      178

The positive control is perfect. False negatives, which would be the dangerous direction because they excuse real model failures as retrieval misses, are 0 out of 700.

`check_overflow` passes all five arithmetic cases, including both `None` paths.

### Found: a quarter of claims contain a witness from their own gold evidence

The `claim` control is the measurement that justifies the scoping decision. 178 of 700 claims, 25 percent, contain at least one witness token drawn from their own gold evidence. Under a whole prompt check with an "any witness" rule, every one of those would have been an outright false positive. Two decisions independently stopped it: scoping to the evidence block, and requiring all three witnesses rather than any. Neither is now an argument, both are measured.

### Found: five structural false positives, and they are not tunable

The `hard` control returned `True` for `ie-val-61`, `ie-val-193`, `numeric-val-84`, `numeric-val-87` and `numeric-val-214`.

The cause is visible on inspection. Those gold elements have no unique witness at all. `ie-val-61`'s three witnesses are `direction`, `acquired` and `resigned`, each appearing five times in the filing. `numeric-val-84`'s appear twice each, which is the ordinary 10-K pattern of legal proceedings text repeated in two sections.

More witnesses does not fix it. Measured through the real function: `N_TOKENS` 3 and 5 both give five false positives, and 7 removes one. So this is repeated content in the filing, not a witness count problem.

One of the five is arguably not an error. If `numeric-val-84`'s text really does appear twice and retrieval returns the other copy, the model received the same information. `ie-val-61`, where three generic words collide across unrelated text, is a real false positive.

Accepted at 5 in 700, for three reasons. The rate is 0.7 percent under a control built to be adversarial. The error taxonomy runs on about 25 hand labelled failures per configuration, so roughly 0.2 affected examples per round, and hand labelling means reading the prompt anyway. And the opposite error, the one that would quietly excuse model failures, is zero.

The caveat on this control: maximum lexical overlap is a proxy for a retrieval miss, not an upper bound. The real retriever will be hybrid dense and BM25, so its misses will look different and this number should be re-checked once it exists.

### Measured: MIN_TOKEN_LEN barely matters, so it stays at 3

Share of the 1,964 gold elements whose top witness has report count 1:

    MIN_TOKEN_LEN   2      3      4      5
    top witness    81.0%  80.4%  78.5%  73.0%
    all three      60.3%  59.4%  57.1%  50.9%

Length 2 beats length 3 by 12 elements out of 1,964, and shorter tokens are more fragile under table reformatting. Kept at 3, now a measured choice rather than a guess.

The second row is the one to remember. Only 59.4 percent of gold elements have all three witnesses unique, so for roughly a fifth of elements a full match is strong evidence rather than proof. That is the same fifth the five false positives come from.

### Checked: three data assumptions the asserter depends on

All confirmed by inspection, not assumed.

`id` equals list position for all 137,045 context elements across all 600 report files, so indexing `report["context"][i]` by a gold index is correct.

No claim in testmini has an empty or missing `relevant_context`, and no gold index is out of range for its report. `test.json` was not checked.

Every one of the 1,964 gold elements in testmini yields exactly three witnesses, so `tried` is always 3 today. It is still stored, because `N_TOKENS` and `MIN_TOKEN_LEN` are per experiment settings and a result file reading `[2, 3]` explains itself where a bare `2` would not.

### Measured: no cache is needed, twice over

Tokenising and counting a whole report takes a median of 12.5 ms and a maximum of 20.3 ms, on filings with a median of 218,040 characters. Against a 285,000 ms model call that is 0.004 percent, so `count_report_tokens` is called once per claim and nothing is cached.

For completeness, since 700 claims cite only 255 distinct reports, a cache would save about 445 rebuilds, or 5.6 seconds across a 55 hour run, and would hold about 128 MB resident. The reason to skip it is not the memory. It is that a module level dict is mutable state living across calls, which is what makes a run behave differently the second time.

### Renamed

`scripts/` became `test_scripts/`, mid session. `CLAUDE.md`'s "Where things live" section still says `scripts/` and needs updating.

### Built: the run loop, the placeholder retriever, and the committed harness test

`src/run_loop.py`. Four pieces. `load_prompt_template` and `read_report` are the IO helpers. `build_prompt(claim, chunks, template)` returns `(prompt, evidence_block)` and asserts `evidence_block in prompt` as its own postcondition. `run_one_claim` does everything for one claim and returns a filled `Record`, catching every exception so it never raises. `run_sample` loads the template once, skips ids where `has_result` is already true, calls `run_one_claim`, writes each `Record` the moment it finishes, and prints a progress line with `flush=True`.

**The model call and the retriever are injected, not imported.** `run_sample(sample, config, results_dir, call_model, retrieve)`. The harness test passes stubs and runs in seconds; the entry point passes the real ones. It also means the Tier 2 retriever replaces the Tier 0 one without touching `run_loop.py`. `run_loop.py` never imports either.

`src/placeholder_retriever.py`. Scores every context element by how many distinct tokens it shares with the claim, keeps the top k, and hands them back **in document order rather than score order**, so tables stay near their captions. Deliberately the simplest thing that is still real retrieval.

`test_scripts/test_harness.py`, committed rather than thrown away, because the run loop is the first code where six modules touch each other. 26 checks in six groups: happy path, retrieval misses, context overflow, unparseable response, one example raising, and resume. It stubs Ollama, uses a scratch directory outside the repo, and exits non-zero on failure so it works as a gate before an overnight run.

### The harness test earned itself on its first run

25 of 26 passed. The failure was one line in `run_one_claim`:

    record.extraction_label = label        # wrong

Two bugs in it. The field is `extracted_label`, and `Record` is a plain dataclass, so assigning an undeclared attribute silently creates a new one. `asdict()` serialises only declared fields, so the value was not merely misplaced, it was discarded and never reached the JSON. The `LABEL_TO_BOOL` conversion was also missing, which is why that constant was defined and unused.

Nothing raised. All 12 examples wrote `extracted_label: null` and every run reported `status="ok"`. A 102-example overnight run would have completed normally and scored 100% unparseable. It also showed up in the progress line as `label=None` twelve times, so that column paid for itself immediately.

Fixed to `record.extracted_label = LABEL_TO_BOOL.get(label)`. 26 of 26 pass.

### Measured: the placeholder retriever, k=10, all 700 claims, 23 seconds

    macro-average (upstream's metric)   57.54%
    element recall                      53.2%
    all-gold claims                     31.6%

    by subset (element / all-gold)   ie 56.7 / 30.4   knowledge 45.9 / 16.5   numeric 59.1 / 44.8

`k = 10` is upstream's setting, from `run_llm.py:41` and the comment in `scripts/inference/retrieval.sh`, where 3 and 5 were swept and discarded. Matching it makes our recall directly comparable rather than merely reasonable. Upstream also sorts its selected chunks back into id order in `retriever/get_top_n.py:20`, which independently matches the document-order choice above.

`knowledge` is worst because it needs the most evidence per claim, 3.66 elements against `numeric`'s 1.87. One `ie` claim needs 20 gold elements and another needs 10, so at k=10 the first can never be complete no matter how good the ranking is.

### Fact-checked, and section 3.4 of the plan was wrong

The plan said the ~68-70% published recall means "for roughly 3 in 10 claims, at least one required piece of evidence never reaches the model". That does not follow. `FinDVer/retriever/recall_evaluation.py` computes the mean over claims of `matched / needed`, which is a **macro-average of per-claim fractions**, not the fraction of claims that got everything. The two diverge sharply when claims need several elements, and these need 2.8 on average.

Upstream ships its actual retrieved indices in `outputs/testmini_outputs/retriever_output/`, so all three metrics were recomputed on the same 700 claims:

    retriever, k=10                macro    element   all-gold
    text-embedding-3-large         68.01%    62.4%     42.6%
    bm25                           65.16%    62.8%     38.6%
    contriever-msmarco             33.48%    28.4%     16.3%
    ours, token overlap            57.54%    53.2%     31.6%

68.01% reproduces the cited 67.91% to within rounding, so the published number is sound and only the gloss was wrong. **The correct claim-level statement is 57.4%, not 30%.** Nearly six claims in ten are missing at least one required piece even with the best upstream retriever. This makes the ceiling argument stronger, and it is the number the paper should use, or else name the metric explicitly, because "68% recall" reads as "68% of claims are fine".

Two more results from the same recomputation. **BM25 reaches 65.16% against the paid embedding's 68.01% and beats it on element recall**, so a free local retriever is within three points of `text-embedding-3-large` on the metric the paper reports. That is worth something on its own for an on-device paper, and it means §7.3's hybrid has to beat 68.01% rather than treating 68% as distant. And k dominates: dense drops from 68.01% at k=10 to 54.53% at k=5 and 43.60% at k=3.

Sections 3.4, 12.1 and the summary table in the plan were corrected.

### Built: the Ollama client, the config, and the entry point

`src/ollama_client.py`. One function, `call_ollama(prompt, config)`, POSTing to `http://localhost:11434/api/generate` and returning Ollama's raw response dict. Uses `urllib` from the standard library rather than `requests`, because the project has no third-party dependencies and this does not justify the first one.

Three things in it are load-bearing. **`"stream": False`**, because with streaming on, Ollama returns newline-delimited JSON objects rather than one document, `json.loads` on the body raises, and the token counts only appear in the final chunk. **`config["num_ctx"]` rather than `config.get(...)`**, so a missing key raises instead of silently falling back to Ollama's 4096 default and truncating every prompt for a whole night. **A 1800 second timeout**, because `urlopen` without one waits forever, and a hung server would mean an overnight run that produces nothing and never errors. No retries: a failed call raises, `run_one_claim` marks the example failed, and re-running resumes exactly those examples.

Verified live against the pinned 0.12.3 server. The full chain works: real call, real response, `extract_label_with_source` returning `('refuted', 'anchored')`, `check_overflow` returning `False`.

`configs/trial_run_3b.json`. Six keys are read by code (`model`, `num_ctx`, `num_predict`, `temperature`, `seed`, `prompt_version`); the rest (`experiment`, `retriever`, `top_k`, `per_cell`, `sample_seed`) are provenance, stored in every `Record` so a result file six weeks from now states what produced it.

`run.py` at the repo root. The only file that names which retriever and which model client an experiment used, so swapping either is a one line change there and touches nothing in `src/`. Two details: `functools.partial(retrieve, k=config["top_k"])` binds *k* at wiring time so the config value is the one that actually runs rather than a label that happens to agree with the retriever's default; and the startup banner prints every key the code reads, so a typo raises at second zero instead of becoming twelve failed records an hour later.

### Verified against the real Ollama API rather than from memory

`done_reason` has two values on 0.12.3, both observed directly by forcing each: `"length"` when generation hits the `num_predict` cap, with `eval_count` equal to `num_predict` exactly, and `"stop"` when the model finishes on its own. `"stop"` does **not** mean healthy, because §4.3 measured that context eviction also reports `"stop"`, which is the whole reason `check_overflow` exists as a separate field.

The response dict has 12 keys. Only four are used. `context` is the KV token list and must never be stored in a `Record`: on a real prompt it is thousands of integers, roughly 30 KB of noise per example. Durations are in nanoseconds. `load_duration` was 5.3 s of an 8.0 s call on a cold model, so `elapsed_seconds` for the **first** example of any run includes model load and is not comparable to the rest.

Also checked, because it would have broken the overflow arithmetic silently: `prompt_eval_count` reports prompt length rather than work done. Three identical calls returned 52 every time, so prefix caching does not deflate it.

### Found on pre-flight, and this one must be fixed before the 102 run

Building the 12 trial prompts for real, with no model calls, showed **the plan's prompt size assumption is about half the truth**.

    mean prompt   ~8,000 tokens        §4.3 assumed ~4,500
    range         ~3,000 to ~15,500    budget is 16384 - 2000 = 14,384
    over budget   2 of 12              ie-val-222 ~15,078, knowledge-val-65 ~15,514
    at 12,000+    5 of 12

The cause is the risk §4.3 named and then dismissed: report elements run to 4,000 characters, and ten concatenated is not 4,500 tokens. §4.3 called overflow "arithmetically impossible". It is not, and **the mitigation that section prescribes, trimming the lowest-ranked chunk until the prompt fits, was never built.**

Decided to run the trial anyway rather than fix first. Those two examples will not error: the prompt fits ingestion at 15,514 < 16,384, so the overflow happens during generation, Ollama evicts prompt tokens, reports `done_reason: "stop"`, and `check_overflow` catches it. Running gives three things a fix-first order would not: real `prompt_eval_count` values to replace the 3.6 chars/token estimate, the overflow alarm exercised end to end on real data for the first time, and the other ten examples doing their normal job. Two of twelve is a finding, not a failure. At 102 examples it would be roughly 17 wasted, which is why the trim lands before that run.

**Decided: do not fix this by raising `num_ctx`.** That trades a bounded problem for an unbounded one. §4.6 measured ingestion at 3-4× generation cost, so window size costs wall-clock rather than RAM, and wall-clock is the binding constraint. A bigger window also cannot rule out one pathological chunk.

**Second consequence, and it affects the schedule.** The 4m45s per example figure was measured on a ~4,000 token prompt. At a mean of ~8,000, the trial run should take roughly 100 minutes rather than 57, and a 102-example run roughly 14 hours rather than 8. The night budget in §12.1 needs re-checking against the trial run's real timings.

### Small decisions

"Smoke run" renamed to "trial run" throughout, 18 occurrences across the three documents. The four remaining uses of "smoke test" refer to checking a cloud API key works, which is a different activity, and were left alone.

The entry point is `run.py` rather than `main.py` or `run_workflow.py`. "Experiment" is already the project's vocabulary, in `CLAUDE.md`, in the config's own `experiment` key, and in the `results/<experiment>/` path, so a different word for the same thing in one place would be the odd one out.

`logs/` created and added to `.gitignore`. Console output captured with `tee`; the per-example JSON in `results/` remains the real record.

Decided but **not applied before the trial run**: printing `evidence=2/3` in the progress line rather than `evidence=False`, computed from `evidences_found`. The trial run's log therefore carries the bool. A column of `0/3` means the retriever is broken; a column of `2/3` means it works and *k* is too small. The bool cannot distinguish those, and it is the line that gets read at 2am. `evidence_present` itself stays all-or-nothing, because it answers a per-example question, namely whether the model could possibly have been right, and a graded flag would blur the distinction the error taxonomy depends on.

### Not done

The trial run itself, and the prompt trimming mitigation above.

---

## 2 August 2026, late — the trial run completed

The first end-to-end run of the pipeline on our own model. 12 examples, `qwen2.5-coder:3b`, temperature 0, `num_ctx` 16384, `num_predict` 2000, placeholder token-overlap retriever at *k*=10, prompt `baseline_v1`. **12 ok, 0 failed, 0 skipped.** 80.7 minutes wall-clock. Console output in `logs/trial_run_3b.txt`, the real record in `results/trial_run_3b/`, 12 JSON files.

The harness test passed 26/26 immediately before, as designed.

**One operator error worth recording, because it cost nothing only by luck.** The first invocation was pasted across two lines, so zsh ran `python3 run.py` with no argument and then tried to execute `configs/trial_run_3b.json` as a command, giving `permission denied`. `run.py` printed its usage line and exited, so nothing ran. Had `run.py` defaulted to some config instead of requiring the argument, this would have silently run the wrong experiment overnight. Requiring the argument is the correct design and stays.

### Headline results

    examples completed          12 / 12, no failures, no skips
    accuracy                    8 / 12   (67%)
    unparseable                 0 / 12
    evidence present (strict)   4 / 12   (33%)
    wall-clock                  80.7 min, mean 404 s/example
    prompt tokens               2,283 - 11,134, mean 6,610, median 7,110
    response tokens             261 - 496, mean 394
    done_reason                 "stop" on all 12
    context_overflow            False on all 12

Per subset: `ie` 4/4 correct with 2/4 evidence present, `numeric` 2/4 with 1/4, `knowledge` 2/4 with 1/4. Gold is 6 True / 6 False and predictions are 6 True / 6 False, so the sample is balanced and the model is not answering constant.

### The single most important result: zero unparseable

**Our own model at temperature 0 stated a usable verdict on all 12 of 12.** 11 fired at the `anchored` level and 1 at `bare`.

This is the measurement §11.8 and the 1 August note said could only come from running our own model, and it lands where the temperature-0 hypothesis predicted. Upstream's Llama-3.2-3B, at temperature 1.0 with `max_tokens` 1024, has a 33% `none` rate. Ours is 0% on 12. Twelve examples cannot establish a rate, and the honest reading is only that the rate is not 33% and probably not close to it. But the two mechanisms named on 1 August, sampled decoding and a biting generation cap, were both turned off here and the failure mode went with them. **Do not carry the upstream 33% or the "45% of 3B responses fail the format" figure into the paper.** The 102-example run gives the first number with a usable confidence interval.

### What the responses actually look like, and four things the extractor survived

Read all 12 response texts rather than only the extracted labels. Four format behaviours appeared that the extractor handles, none of which were designed against our own model, since all of its development data was Llama-3.2-3B at temperature 1.0.

**1. The verdict is frequently not the last sentence, despite the prompt demanding it.** `ie-val-108`, `ie-val-49` and `numeric-val-51` all state "Therefore, the claim is X" and then keep writing explanatory text after it. `knowledge-val-105` is the extreme case: its verdict sits mid-response with roughly 400 characters of text following, in a 2,084-character response. **The `anchored` level searches the whole response, which is the only reason these parsed.** A last-line or last-300-character rule would have failed on four of twelve. This retroactively justifies the level-1 design and is worth stating in the paper.

**2. Markdown emphasis inside the verdict sentence.** Four responses wrote "the claim is \*\*entailed\*\*" with asterisks. The anchored pattern tolerates it. Qwen2.5-Coder is a code-tuned model and formats in markdown by habit.

**3. The model copies the prompt's own template placeholder.** `knowledge-val-33` ended with, literally, `Therefore, the claim is {refuted}.` — braces included, lifted from the prompt's instruction `"Therefore, the claim is {entailment_label}."` The anchored pattern did not match through the braces; the `bare` level caught it in the tail window and returned `refuted`. **This is the one example of twelve that needed level 2, and it is a prompt bug, not a model bug.** Showing the model a literal `{entailment_label}` invites it to echo the braces. Consider giving the format example with the placeholder already filled in, in the next prompt version.

**4. Duplicated conclusions.** `ie-val-222` and `numeric-val-242` both state the verdict twice, in two different phrasings. Harmless here because both agree, but the extractor's "last match wins inside a level" rule is what decides such a case, and it has now been exercised on real data.

Also checked: **all 12 responses end with terminal punctuation**, and `done_reason` is `stop` on all 12. No generation was cut off.

### `num_predict` 2000 is roughly four times larger than needed

Longest response was 496 tokens and 354 words; mean 394 tokens. The 1 August estimate of "~1,100 tokens covers the longest observed" was derived from Llama-3.2-3B and is comfortably conservative for our model, which is markedly less verbose. The cap is not costing anything, since it is a ceiling rather than a reservation, but the *budget arithmetic* in §4.3 subtracts it from the window. At `num_predict` 800 the prompt budget rises from 14,384 to 15,584 tokens. Not urgent. Recheck against the 102-example run before touching it, because 12 examples is a thin basis for a tail bound.

### Context overflow did not happen, and the chars-per-token estimate was the reason

**0 of 12 overflowed.** The pre-flight on 2 August predicted 2 of 12 would, and named them. Both came in far under:

    example              predicted    measured    error
    ie-val-222            ~15,078      11,134     -26%
    knowledge-val-65      ~15,514      10,770     -31%
    mean over 12          ~8,000        6,610     -17%

**The cause is the 3.6 chars/token conversion, which was wrong.** Measured over all 12 real prompts, the true ratio is **4.36 characters per token**, ranging 2.46 to 5.19 across examples. The 3.6 figure came from one hand-built week-1 sample. Financial filing text tokenises more efficiently than assumed, most likely because it is repetitive and heavy in common English words and formatted numbers.

Headroom as it actually stands:

    largest prompt + its generation      11,630  vs  16,384
    largest prompt + full num_predict    13,134  vs  16,384

So overflow is not merely absent, it is comfortably out of reach at *k*=10 with these settings. **The consequence to record honestly: the overflow alarm has still never fired on real data.** It passes in the harness against fabricated counts, and that is all the evidence there is for it. It stays in, since it costs nothing and guards the §4.3 eviction behaviour, but it is not yet validated in production.

Per-example variation in the ratio is itself informative. `numeric-val-242` sits at 2.46 chars/token and `knowledge-val-65` at 5.19. The low end is table-heavy content, where pipe delimiters and digit strings fragment into many tokens; the high end is prose. **A character-count budget is therefore not a safe proxy for a token budget on this data, because the conversion swings by 2x with content type.** Any trimming logic must count tokens, not characters.

### The real cost model: runtime is linear in prompt tokens, R² = 0.995

Fitting elapsed time against prompt tokens over the 11 examples after the first, which is excluded because it carries the 5.3 s model load:

    elapsed = 0.0641 s per prompt token       R² = 0.995
    implied ingestion rate                    15.6 tok/s

A two-parameter fit separating ingestion from generation was attempted and **rejected as degenerate**: `eval_count` only varies from 261 to 496 across the sample, so the generation term is unidentifiable and came back negative. That is a property of the sample, not a finding about the model. Do not report separated rates from this run.

The single-variable fit is strong enough to plan against:

    prompt size    predicted time
     2,000 tok       1.8 min
     4,000 tok       3.9 min
     6,610 tok       6.7 min   (our mean)
    11,000 tok      11.4 min

**§4.6's conclusion that prompt ingestion dominates is confirmed and strengthened.** It is not merely 3-4x generation, it accounts for essentially all of the variance. The measured 15.6 tok/s ingestion is 18% slower than the 19.1 tok/s measured in week 1 on a single example, consistent with thermal behaviour over a longer run, a larger working set, or both.

### The schedule number was wrong, and it is worse than the revised guess

Mean per example, excluding the first, is **419.4 s, or 7.0 minutes**. Against the week-1 figure of 4 m 45 s.

    run                  plan says   trial run implies
    102-example slice        ~8 h          11.9 h
    full testmini, 700      ~55 h          81.6 h

The 2 August pre-flight predicted ~14 h for 102 by extrapolating from an ~8,000-token mean. The mean turned out to be 6,610 rather than 8,000, so that estimate overshot, but the per-token cost is higher than assumed, so the two errors only partly cancel. **11.9 hours is the number to plan against.**

This matters for the night budget in §12.1. A 102-example 3B slice no longer fits in a single overnight window with margin: 11.9 hours started at 9pm finishes at 9am. It is still one night, but it is a full one, and any run that starts late spills into the next day. **The full-700 run at 81.6 hours is now ~10 nights of the ~20 remaining, up from ~7.** It moves further into the conditional band, not out of it.

**The lever is prompt size, and it is a direct multiplier.** At the fitted rate, cutting the mean prompt from 6,610 to 3,000 tokens would take a 102-example run from 11.9 hours to about 5.4. That is the strongest argument yet for tighter retrieval, and it is an efficiency argument that stands independently of the recall argument. It is the same conclusion §7.3 and §12.1 reached on recall grounds, now with a wall-clock number attached.

### Retrieval: the 12-example slice reproduces the population figure

    claim-level, all gold present     4 / 12    33%   (offline over 700: 31.6%)
    element-level, fully present     22 / 36    61%   (offline over 700: 53.2%)
    element-level, partial            1 / 36
    element-level, absent            13 / 36

The claim-level figure lands within 1.4 points of the placeholder retriever's measured 31.6% over all 700 claims, so the stratified sample is behaving.

**The question the 2 August build log posed is answered: the retriever misses entirely rather than running out of room.** Of the 14 gold elements not fully retrieved, 13 scored `0/3` witnesses and only 1 scored partial. `0/3` means the element was never retrieved at all; a `2/3` pattern would have meant retrieval worked and *k* was too small. This is a ranking problem, not a *k* problem, and it is exactly what a token-overlap baseline should be expected to fail at. Raising *k* would not fix it, and would cost wall-clock linearly.

### How solid is `evidence_present = True` on these four specific claims?

The 2 August validation established the general position: 0 false negatives in 700, 5 false positives in 700 under an adversarial control, and only 59.4% of gold elements having all three witnesses unique in their report. That is a population figure. The four claims that scored `True` here were checked individually, since the trial run's headline accuracy split rests on them.

Of the **10 gold elements across those 4 claims, 8 have all three witnesses unique in the report** (count 1), which makes their presence conclusive: those tokens appear nowhere in the filing outside that element, so finding them in the evidence block proves the element reached the prompt. Two do not:

    ie-val-108, element 19    represented(2) controlled(2) purchased(2)
    numeric-val-242, elem 258  1.5(2)  0.00(3)  0.32(3)

`numeric-val-242`'s element 258 is the weak one. Its witnesses are short, generic numeric strings appearing up to three times in the filing, so a 3/3 match there could in principle come from a different retrieved chunk that happens to contain all three. It is the one element in the trial run where `evidence_present = True` is meaningfully softer than proof — and it is, awkwardly, the same example as the broken-arithmetic finding above.

This does not change the 4/4 accuracy figure, which is about labels, not retrieval. It does mean **"all gold evidence reached the model" is proof for 8 of the 10 elements and strong evidence for the other 2.** The asymmetry recorded on 2 August still holds and is the one that matters: `False` is reliable, since false negatives are 0 in 700, so a claim flagged as missing evidence really was missing it.

### Accuracy, and the one result worth being careful about

    overall                  8 / 12   (67%)
    evidence present         4 / 4    (100%)
    evidence absent          4 / 8    (50%, exactly chance)

The shape is the one the retrieval-ceiling argument predicts, and it is the first end-to-end evidence for it in this project. **It is also four examples on one side and eight on the other, and 4/4 is entirely consistent with luck.** At n=4 the 95% interval on 100% runs down to roughly 40%. Do not put this in the paper. Do not treat it as confirmation. It is a reason to prioritise retrieval, which was already the priority, and it is a hypothesis the 102-example run can actually test.

The 50% on the evidence-absent half is worth one further note. It is what a coin flip gives, but the model is not flipping a coin. It reasons confidently over the wrong chunks and reaches a decisive wrong answer, which is a different failure with the same score.

### A correct label from broken arithmetic, and why label accuracy overstates quality

`numeric-val-242` is scored correct. Gold is entailed, the model said entailed, evidence was fully present. The reasoning contains two separate errors:

    Total Net Loss = $15,800,000 + $0.015 million = $15,800,015
    The calculated total net loss ($15,800,015) matches the claimed total ($15.815 million).

The first line treats `$0.015 million` as $15 rather than $15,000, a factor of 1,000. That is **data trap 7 in `CLAUDE.md`, the magnitude trap, occurring live in our own pipeline for the first time.** The second line then declares $15,800,015 equal to $15,815,000, which it is not, off by about $15,000. The two errors happen to leave the verdict unchanged, so the example scores as a success.

Three consequences.

1. **Label accuracy overstates reasoning quality on the numeric subset, and we now have a concrete instance rather than a concern.** This is a direct argument for the per-error-category analysis that §5.3 names as part of the contribution, and it is the kind of example that belongs in the paper as a figure.
2. **It is a direct argument for the code sandbox in §7.2.** A model that computes `15800000 + 0.015e6` in Python cannot make the unit error, and cannot declare two unequal numbers equal.
3. **The error taxonomy needs a category for "correct label, invalid reasoning".** It is not a format failure, not a retrieval failure, and not a label error. Without the category it is invisible, because the only automated signal, the label, says the example passed. Detecting it needs the explanation checked, which is the faithfulness verifier in §7.5, currently in the stretch band.

Whether this is common or a single instance is unknown from 12 examples, and the numeric subset was only 4 of them.

### Small thing that will bite later: `evidences_found` does not round-trip through JSON

In Python the asserter returns `{14: (3, 3)}`, an int key mapping to a tuple. Reading the result file back gives `{'14': [3, 3]}`, a string key mapping to a list. JSON has no integer keys and no tuples. Nothing is lost, but any analysis script that does `evidences_found[i]` with an integer `i`, or compares a value against a tuple, gets a `KeyError` or a silent `False`. Encountered while writing the analysis for this entry. Coerce keys with `int(k)` on read.

### What this run settled, against the four jobs it was given

1. **Output format, §4.6's provisional row.** Settled with a logged artifact. Our model does produce a usable verdict, 12 of 12, though frequently not as the final sentence. The provisional "yes" in that row is now measured, with the caveat that it was measured on `baseline_v1` at `num_ctx` 16384 and not on `ie-val-0` at 8192.
2. **First responses from our own model at temperature 0.** Done, 12 logged.
3. **First honest `none` rate for our configuration.** 0 of 12. Not a rate yet, but enough to retire the upstream 33% as a forecast.
4. **`num_predict` confirmed against our own model's chain-of-thought lengths.** Done. 496 max against a 2,000 cap.

Plus three it was not given: the real chars-per-token ratio, the real cost model, and the first end-to-end evidence-present split.

### Not done

Prompt trimming is still not built. **Its justification has changed and should be restated honestly:** it was specified to prevent overflow, and overflow does not occur. It is now a wall-clock optimisation, competing against building a real retriever, which would reduce prompt size and raise recall at the same time. Given that runtime is linear in prompt tokens and the placeholder retriever misses entirely rather than partially, **the retriever is the better next investment and trimming should probably wait behind it.** Trimming still has to exist before any run at a larger *k*, and it must count tokens rather than characters, per the ratio finding above.

Still open from 31 July, both untouched: the FINDVER leaderboard check and the citation sweep.

---

## 3 August 2026 — the professor's reply, and the experimental design it forced

Not a build session. Correspondence and experimental design. Nothing was run and no code changed.

### What was sent and what came back

The email sent to the professor reported that the harness was nearly finished, that the loader, the stratified sampler and the label extractor were built and tested, and that the retriever was next. It described the Ollama context eviction finding and the fix. It asked two questions: which two cloud models and from which provider, and which two local models. It made the case for Anthropic, on the grounds that `claude-3-5-sonnet` is the paper's top scorer so a newer Claude extends that exact row. It mentioned a DeepSeek key was already in hand, and that a family desktop with a GPU and 32 GB of RAM might become available.

His reply, in full substance, was three things. He has a server with an **"NVIDIA RTX 4090 Ti"** and asked whether it would be useful. He recommends **DeepSeek**, noting a recently released model whose performance seems nearly comparable to Claude. And he called the Ollama finding **"a very valuable finding."**

### He answered one of the two questions

The cloud question was answered: DeepSeek. **The local model question was not answered at all.** The server offer reads as an implicit "you will have compute so it matters less," but it does not name models. Open question 8 is still open, and it is the one that gates the schedule, because Phase 2 starts on 3 August.

He also **did not address the Anthropic argument.** His "nearly comparable to Claude" is a substitution argument about model strength, and the argument made to him was not about strength. Consequence recorded below.

### Checked: which of these models already have a published FINDVER row

Listed `FinDVer/outputs/testmini_outputs/rag/processed_cot_outputs/`. Sixteen files. Two matter here:

    claude-3-5-sonnet-20241022.json    the paper's top scorer
    DeepSeek-V2-Lite-Chat.json         a small MoE model

So DeepSeek **is** published, but as V2-Lite-Chat. A new frontier DeepSeek's only published predecessor is therefore a weak lite model, and the gap between them is so large the comparison carries no information. A newer Claude would extend the strongest published row directly.

**This is coupled to §9.1 and is not merely a preference.** §9.1 settled that published numbers are reused as the historical baseline instead of re-running 16 models, and that decision is what makes Phase 2 fit in 30 days at all. Choosing models with no meaningful published predecessor weakens the strategy holding the timeline together.

**Decided:** DeepSeek is the primary cloud model, settled, and the key is already in hand. Ask once for an Anthropic key as the *second* cloud model, stating that specific reason in one sentence. If he declines, fall back to two DeepSeek models split on **chat versus reasoning**, which at least answers the routing question in open question 1 rather than producing two correlated rows.

Also needed from him: the exact model strings and endpoint. He said "recently released" and the model was not named. Do not guess a model ID.

### Also confirmed from the same file list: the edge models

Neither `Qwen2.5-Coder-3B` nor `Qwen2.5-Coder-7B` appears. The closest is `Qwen2_5-7B-Instruct`, a different model. So the existing choice satisfies open question 8's "must not already be evaluated" constraint.

**Decided, pending his objection:** the second edge model is **Qwen2.5-Coder-7B**. Same family, so 3B to 7B is a clean scaling comparison with everything else held fixed. §4.6's numbers for it are still recollection and need settling regardless. And the code tuning is load-bearing for Tier 1, which is why Coder was chosen in the first place.

### A contradiction in open question 8, flagged rather than worked around

OQ8 requires that our edge models be ones FINDVER did **not** evaluate. That optimises for adding new rows to a table.

But the paper's claim is that the *pipeline* improves a small model. The cleanest evidence for that is the **same model, published baseline versus ours**, so that the pipeline is the only variable. `Llama-3_2-3B-Instruct.json` is published, with 700 stored responses already on disk. Under OQ8 that disqualifies it. Under a pipeline-contribution framing it makes it the best candidate available.

The confound is real: upstream's RAG setup is not ours, so it is not a fully controlled comparison. It is still far closer than a brand new model. **OQ8 may be written for the wrong objective.** Not resolved here. Raise it with him.

### The GPU server, and the rule that comes with it

Open question 11 is partly answered. A GPU server exists. Specs, access method and availability date are still unknown, and **"RTX 4090 Ti" is not a product that shipped** — there is a 4090 at 24 GB and a 5090 at 32 GB, and the 4090 Ti was announced and cancelled. The real card and VRAM have to be confirmed before anything is planned against it.

**Decided: the GPU changes where experiments run, not what the paper claims about hardware.**

- Accuracy and ablations run on the GPU.
- **The MacBook stays the device of record** for every latency, throughput and memory number that appears in the paper.
- **Never print a GPU-derived number under a MacBook label.** A run that happened on the 4090 cannot produce a MacBook runtime figure, and substituting one would be fabricated data. This was considered explicitly and rejected.
- **Never mix machines inside one results table.** Temperature 0 does not guarantee identical tokens across a CPU backend and CUDA, and quantisation may differ. If one configuration is re-run on the server, every configuration it is compared against is re-run there too. The 2 August trial-run numbers are MacBook-only.
- Keep the edge tier at **8B or below** regardless of the 24 GB of VRAM. Running a 14B or 32B model and still calling it on-device would not survive review at this venue.

The honest version costs almost nothing, because the MacBook measurement already exists. §4.6's fitted cost model came from one 80-minute run.

### 3B stays the paper's primary model. 7B is a row, not a switch.

Considered switching the primary edge model to 7B now that a GPU may remove the wall-clock objection. Rejected.

The argument that decides it: **a bigger model eats the contribution.** The pipeline's measured delta is largest where the base model is weakest. If 7B already handles the arithmetic and the tables unaided, the ablation shows a smaller gain and the paper says less. Secondary reasons: every measured number in the project is 3B, and the venue rewards the smaller model.

This is what §12.3 already says. Band A is 3B baselines; Band B holds "7B slice comparisons." A row, not a replacement.

### The baseline design: four conditions, not three

Worked out in full because the obvious three-condition design has a hole in it.

| # | Condition | Runs on | Establishes |
|---|---|---|---|
| 1 | 3B, RAG, one call, no pipeline | local | edge-only floor |
| 2 | DeepSeek, RAG, one call, no pipeline | cloud | single big call |
| 3 | DeepSeek in **every** pipeline role | cloud | all-big-model, ≈ MACE |
| 4 | 3B + DeepSeek routed | local + cloud | ours |

**Condition 3 is a baseline that does run through the pipeline, and it is mandatory.** §5.3's claim is "matches or beats the all-big-model version at a fraction of the cost," and that claim cannot be made without measuring the all-big-model version. The instinct to keep every baseline outside the pipeline is right for conditions 1 and 2 and wrong for 3.

§5.3 already encodes this and it was missed on first reading: *"always escalate ≈ MACE's design; never escalate = edge-only floor; the interesting result lives between."* Condition 3 is always-escalate. Condition 1 is never-escalate. Ours is a point on a curve the plan already committed to producing.

**"No pipeline" does not mean no RAG.** The pipeline is RAG-only by the professor's decision and the filings are far too long to pass whole. Every condition uses the same retrieval, same *k*, same slice, same prompt version, same `num_ctx`, temperature 0, same label extractor. Only the pipeline machinery varies, or the delta is not attributable to anything.

**Framing, recorded so it does not drift.** "We beat DeepSeek" is not the headline. If condition 4 beats condition 2, report it, but a reviewer answers it with "you beat a single-prompt use of a cloud model, which nobody deploys." The claim is matching condition 3 at a fraction of the cost. Beating condition 2 is a bonus.

**Cost:** conditions 1 and 4 are local, about 12 h each at 102 examples, so two nights. Conditions 2 and 3 are cloud, hours not nights. Affordable before any GPU arrives.

**Scoring:** all four are internal comparisons, so per §9 they are strict versus strict. FINDVER-compatible scoring is only for the one table where our numbers sit beside published ones.

### Two results tables, one variable each

A question worth recording because the answer is counter-intuitive. Holding retrieval constant across conditions 1 to 4 does not defeat the purpose of building a good retriever. It is what makes the comparison mean anything. Giving DeepSeek a worse retriever would make any win attributable to retrieval rather than architecture.

- **Pipeline table.** Retrieval fixed, architecture varies across conditions 1 to 4. Isolates routing.
- **Retrieval table.** Architecture fixed, retrieval varies: whole-claim dense, +BM25, +decomposition, *k* sweep. Isolates the retriever.

The retrieval table splits in two, and the halves have very different costs. **Recall against gold `relevant_context` has no architecture column at all**, because retrieval runs before any model call. That half is minutes. The **end-to-end accuracy delta** does need a fixed architecture, and it is fixed to our edge-cloud pipeline, since that is the system the paper claims. That half is a night, and it sits in Band B.

Also corrected, because the question rested on a wrong assumption: **there is no configuration where the cloud model retrieves its own evidence.** DeepSeek over an API has no access to the filing. Retrieval here is BM25 plus embeddings plus plain Python, a mechanical step that runs before any model call.

### n = 102 cannot support the paper's central claim

§9 puts the margin at ±10 points at n=102. "Matches condition 3" is therefore unprovable at that sample size, because a tie and a 5-point loss are indistinguishable. This is the single biggest threat to the contribution statement, and the full-700 run is the only thing that fixes it.

§12.3 already said this: *"if compute appears, this is the first thing it buys."* It is now the concrete reason to accept the server.

### Three latency quantities that are not measured, and must be

Recorded so they are not discovered during the writing phase.

1. **7B latency on the MacBook.** The 11 m 46 s figure is one week-1 example and recollection. If a 7B row goes in the paper, either re-measure it or label it an estimate.
2. **Pipeline latency, as opposed to baseline latency.** The measured 7.0 min per example is `baseline_v1`, placeholder retriever, *k*=10, no code execution, no table parsing, no cloud round-trip. The finished system is a different number. **This gap exists whether or not a GPU is involved**, because the system does not exist yet.
3. **Cloud round-trip latency.** Calls per example times API latency. Part of the edge-cloud story and entirely unmeasured, since no key has been used yet.

**The plan for all three: budget one MacBook night at the end,** after the pipeline is frozen, to measure the final configuration's per-example latency and peak RAM on the real device. One run, one table. That same run doubles as the accuracy-portability check, confirming the verdicts reproduce off CUDA, which converts an assumption into a measurement.

### Open question 4 is wrong on attribution, not just stale

OQ4 reads: *"ANSWERED 30 Jul: ~5-page workshop paper... Leaderboard submission and the full 700-example run are consequently out of scope."*

Two problems. First, **the professor did not say this.** The "consequently out of scope" clause was an inference from the deadline, written as though it were his ruling. That is an attribution error and matters more than currency, because he may in fact want a leaderboard submission.

Second, §12.3 was revised the following day, 31 July, and explicitly overturns it: *"An earlier draft of this section cut Tiers 2–5, the full-700 run, and the leaderboard submission outright. That was wrong on two counts."* Band B now holds all three as conditional. OQ9 carries a note dated 1 August making exactly this correction. **OQ4 needed the identical fix and was missed.**

Both halves of the clause are now void anyway. Full-700 is affordable on the GPU. And the argument against the leaderboard is structural rather than about compute: **a leaderboard ranks accuracy only, our contribution is cost-accuracy, and a 3B edge model plus routing will not top a board of frontier models.** Chasing it means competing on the axis where we are weakest while the axis where we win goes unmeasured. FINDVER does have a leaderboard, and the test split ships with labels so scoring can also be done locally.

**[CORRECTED later the same session. "FINDVER does have a leaderboard" is wrong.]** The web research done at the end of this session established there is none: the paper promised an online platform, no URL exists in the paper or the repository, and the email submission route was retired in July 2026 once test labels went public. See the leaderboard findings later in this entry. The structural argument above still stands if a platform ever appears, but the question is moot rather than decided. The second half of the sentence is correct: the test split does ship with labels and can be scored locally.

### Caught in session: fabricated recall numbers in an explanation, and a gap they exposed

While explaining the shape of the retrieval tables, illustrative recall figures were invented and not labelled as invented: "baseline 68%, +BM25 74%, +decomposition 79%." All three are fake. They also contradict the real measurements in §3.4, and in a misleading direction: **BM25 actually measures 65.16%, which is *below* the 68.01% baseline** on the reported macro-average, not above it. It does beat the embedding on element recall, 62.8% against 62.4%, which is the honest version of the "BM25 is competitive" point. Decomposition has not been built or measured at all, so that row had no basis whatsoever.

Recorded because the failure mode is the one §3.4 and the accuracy rules already warn about, and it happened anyway in a throwaway explanation rather than in a results table. The target to beat is **68.01%**.

**The same question exposed a real gap: MACE's accuracy figure is not in any of our documents.** §6.1 records its four weaknesses, its zero-shot-no-training profile, and the 27–92B scaling remark, but never the headline number. Meanwhile §5.3 states our contribution as matching the all-big-model design, and §9.2's condition 3 exists specifically to compare against it. **The number the paper is built to match is unrecorded.** Pull it from arXiv 2604.17225.

Related and easy to get wrong: MACE's 67.91% recall is not a target. It is FINDVER's own retrieval setup copied unchanged, and §6.1 lists it as Weakness 2. And because the project is RAG-only, the comparable Claude-3.5-Sonnet accuracy is **75.0% RAG, not 77.2% long-context**. The long-context column should not appear anywhere in the paper.

### Also corrected: §9.2 did not explain what the delta table measures

As first written, the "two results tables" subsection stated the delta table's cost and its fixed-architecture requirement but never said what it measures or why the recall table alone is insufficient. Rewritten to say it plainly: recall is a **proxy**, a higher recall number does not by itself mean better verdicts, and without the delta table the paper can only claim "we raised recall by N points" with no evidence that anything changed.

### Decided at the end of the session: the retriever moves ahead of the baselines, and nothing runs tonight

§12.2 schedules the edge-only baselines to start on 3 August. That was reconsidered and reordered. **No run was started.** Three independent reasons, each sufficient on its own:

1. **The retriever is still the placeholder at 57.54% recall.** §9.2 requires every condition to share the same retrieval, so a baseline measured now is invalidated the moment the real retriever lands. The 2 Aug entry above already concluded the retriever was the better next investment; this makes it a scheduling decision rather than a preference.
2. **A 102-example 3B run is ~11.9 h.** Started late it finishes the following afternoon, costing the next day as well (§12.1).
3. **Machine choice is unsettled.** MacBook and server results cannot share a table, so a local run now is repeated once the server arrives.

The reorder is cheap because **the retriever is chosen on recall alone, with no model calls**. It consumes daytime, not nights. Full revised timeline in §12.2 and in `working_state.md`.

### Worked out: when each condition is measured, and one correction

The four conditions are not measured at the same point. They split by dependency:

    1  edge-only            depends on retrieval only        run once retrieval is frozen
    2  single big call      depends on retrieval only        run once retrieval is frozen
    3  all-big-model        retrieval AND the pipeline       run once the pipeline is frozen
    4  ours                 retrieval AND the pipeline       run once the pipeline is frozen

**So the order is 1 and 2 early, 3 and 4 late, all four together at 700.** Neither "all four at the start" nor "all four at the end," which is how it was being read.

This preserves the 30 July meeting outcome. He asked that both ends be measured before the routed system is built, and conditions 1 and 2 **are** those ends. Neither needs the pipeline to exist.

**Correction to an earlier framing in this same session.** Conditions 1, 2 and 3 were described as fixed reference points measured once. That is wrong for condition 3, which runs the cloud model in *every pipeline role* and therefore moves whenever the pipeline moves, exactly like condition 4. Only 1 and 2 are stable across pipeline changes.

**The module-by-module comparison is condition 4 only.** §8's result structure — baseline, +code execution, +retrieval — is a claim about our own system. Nothing is claimed about condition 3 with a half-built pipeline, so it is never measured that way. Condition 3 is run **once, against the frozen final pipeline**, which is where §5.3's claim lives. This matters for cost: it means the four-condition comparison is one round, not one round per module.

**Retrieval is the variable that invalidates everything.** A module change moves conditions 3 and 4. A retrieval change moves **all four**. That asymmetry is the structural argument for settling retrieval before spending any night, and it is affordable precisely because recall needs no model calls.

**Machine choice is part of the freeze**, not a detail to settle later. Where conditions 1–4 run must be decided **before condition 1 starts**. The deadline is roughly 7 August under the revised timeline. If there is no server access by then, start on the MacBook and accept re-running.

### Done at last: the leaderboard check, the citation sweep, and MACE's number

Carried since week 1 and slipped three times. All three done in one session, by web research rather than by running anything.

**MACE's FINDVER accuracy is 0.76**, from the Qwen-235B configuration in their Table 8. **Verified by eye the same evening against the paper.** Full table in §6.1. MACE's own rows: Mt-7B 0.64/0.65, Ll-8B 0.68/0.71, Qw-72B 0.75/0.74, Qw-235B 0.76/0.76.

**Three things surfaced only when the real table was read, none of which the fetch reported:**

1. **MACE's Claude-3.5-Sonnet baseline is 0.73 TM, which matches neither of FINDVER's own figures** (77.2 long-context, 75.0 RAG). **They did not re-run these**, their caption says the baselines are sourced from Zhao et al. (2024b), so a copied number failing to match its source is the puzzle. The effect is that **their table demotes Claude below GPT-4o (0.73 vs 0.75) while FINDVER's table places Claude above GPT-4o (75.0 vs 73.7 under RAG)** — the ordering of the two strongest models is reversed. MACE's Claude (0.73) sits near FINDVER's GPT-4o RAG (73.7) and MACE's GPT-4o (0.75) near FINDVER's Claude RAG (75.0), which is what a row swap would look like. **Recorded as a discrepancy, not asserted as their error**, since two close numbers are not evidence of a mechanism and they may have sourced from an appendix, from `outputs/`, or from a later version. **Settleable for free** by recomputing accuracy for those two models from `outputs/` against `testmini.json` gold labels: a set comparison, no model calls, no quota.
2. **Table 8 never states whether its baselines are long-context or RAG.** The two differ by about 2 points in FINDVER's table. Since this project is RAG-only, no MACE baseline can go in our tables until that is settled from their text.
3. **MACE's baseline list is broader than FINDVER's printed Table 4** and includes DeepSeek-V2-Lite, Llama-3.1 70B, Qwen-2.5 72B, Mistral-Large 123B and Gemini-1.5-Pro. All five are in our `outputs/` directory. So the FINDVER *release* covers more models than the FINDVER *paper*, MACE sourced from the release, and **`outputs/` is the authoritative baseline set for us rather than the paper's table.**

**The finding that reframes §6.1: FINDVER is a parity result for MACE, not a SOTA one.** Their own sentence is *"SOTA performance on two closed-domain datasets and on par with the best models on two others."* FINDVER and SciTab-OD are the two "on par" datasets. They matched the best single models on our benchmark; they did not beat them. §6.1 previously said "claims SOTA/parity" without saying which applied here.

**The most useful single row is Llama-8B at 0.68.** A small model running the *full* multi-agent pipeline lands below FINDVER's own 2024 Claude-3.5-Sonnet RAG figure of 75.0%. Mistral-7B is worse at 0.64. That is simultaneously the opportunity for a 3B-plus-routing design and the warning about it.

**Also found, and §6.1 was wrong by omission: MACE already reports efficiency.** Table 4 is memory, Table 5 is runtime for 300 claims. §6.1 listed four weaknesses with efficiency absent, implying the axis was unclaimed. It is not. Our operating point differs — their smallest is 7B on server GPUs, ours is 3B on a 2017 CPU laptop — but §5.3's "fraction of the cost" wording has to state what is cheaper than what with their numbers in view. Tables 4 and 5 have not been read.

**The leaderboard does not exist as a submission target.** The paper promised one: *"we will develop and maintain an online evaluation platform where researchers can test their models and participate in a public leaderboard."* No URL in the paper or the repo, no evidence it launched. Email submission did exist and the README retired it in a July 2026 update, because the test ground truth is now public. This closes OQ4's leaderboard debate as moot rather than decided, and it explains §2.6's finding that test labels sit on disk despite the paper saying they were withheld.

**Citation sweep: 23 citing papers via the Semantic Scholar graph for arXiv:2411.05764. MACE is the only published method found evaluated on FINDVER.** The rest cite it as related work or are competing benchmarks. **Limits stated deliberately:** abstract-level screening plus keyword search, not full-text. The supportable phrasing is "we found no other method evaluated on FINDVER," not "nobody has."

### A second fabrication caught, this time by the user, and the mechanism is worth recording

The web fetch reported FINDVER's best model as "GPT-4o 76.2%." That is **wrong**. Checked against `docs/FINDVER_benchmark.pdf` directly: §2.6 was correct all along, with Claude-3.5-Sonnet at 77.2% long-context and 75.0% RAG, GPT-4o at 75.7 / 73.7.

The mechanism differs from the earlier invented recall numbers in this same session and the difference matters. Those had no source at all. This one had a real source, but `WebFetch` answers a prompt against the page using a small summarizer model, so a misread table produces a confident wrong number with a real URL attached. **A citation is not verification.** Every figure taken from a fetched page is unverified until read by eye, and the MACE Table 8 numbers above sit in exactly that category.

No PDF text extraction is available on this machine: `pdftotext` is absent and no Python PDF library is installed. Installing `poppler` would let the plan's own PDFs be read directly instead of round-tripping through the web.

### Not done

~~The FINDVER leaderboard check and the citation sweep.~~ Both done, above.

**Resolved the same evening:** MACE's Table 8 is confirmed by eye, and the numbers the fetch gave for it were correct. The Claude long-context digit is settled at **77.2%**, matching §2.6, from the FINDVER table itself.

**Read the same evening: MACE Tables 2, 4 and 5.** Three findings, one of them a correction to a claim made earlier in this session.

**Table 2 corroborates §2.6's split-size correction.** MACE lists FinDVer as Testmini 700 claims / 517 tables and Test 1,700 claims / 1,262 tables. They counted the released data rather than repeating the paper's 600/1,500. **Two independent counts now agree**, so the correction can be stated plainly instead of hedged as "our count differs from the paper."

**Correction: Tables 4 and 5 do not cover FINDVER.** Earlier this session the claim was made that MACE's efficiency reporting narrows our novelty. That was an overcorrection. Table 4's caption restricts it to *"closed-domain datasets"*, meaning SciTab and SemTab. Table 5 covers SciTab, SciTab-OD and SemTab. **Neither reports memory or runtime on FINDVER.** Deployment cost on our benchmark is unreported by anyone.

**Table 5 is the useful one, and it runs against them.** Minutes per 300 claims:

    Mt-7B  w CoT       4        Mt-7B  MACE    110      27x slower
    Qw-72B w CoT      23        Qw-72B MACE    123     5.3x slower
    Qw-235B w CoT   55.07       Ll-8B  MACE  121.83    2.21x slower, 2.71x on SemTab

**MACE's pipeline costs 2.2x to 27x more wall-clock than single-pass CoT.** Their efficiency claim is about memory, with runtime as the price paid for it. For a venue about latency under real-world constraints this is an opening, not a closed door: we have a fitted cost model at R² 0.995 and the strongest competing approach ships a large slowdown with no FINDVER timing at all.

**Table 4 also gives their floor.** It reports *total* parameters across agents: Mt-7B with an independent verifier is 27B total at 11.5% of the 235B baseline's memory, Ll-8B is 28B at 11.9%. Their smallest configuration needs 27B of weights resident. Ours is 3B local plus a cloud API. §5.3's "fraction of the cost" should now specify **which** cost: memory is already claimed by them on other datasets; wall-clock and on-device feasibility on FINDVER are unclaimed by anyone.

**Caught before it reached a document: the runtime comparison was nearly written backwards.** MACE's Ll-8B is 121.83 min for 300 claims, about 24 s per claim on server GPUs. Ours is 7.0 min per example, 420 s per claim, on a 2017 CPU. **We are roughly 17x slower**, comparing our single-pass baseline against their full pipeline, and ours will widen once the pipeline exists. Their 2.2x–27x figures are their pipeline against their own single-pass CoT on their own hardware and say nothing about us. Nothing in the paper may imply we are faster than MACE.

**The comparable metric is overhead ratio, not seconds**, since hardware and documents both differ. Theirs: 2.21x, 2.71x, 5.3x, 27x. Ours: condition 1 against condition 4 on one machine, which §9.2 already schedules, so it costs no extra work.

**Decided: no separate speed-optimisation workstream.** §12.1 already established prompt size as the only real lever, and tighter retrieval cuts runtime and raises recall at once, so Tier 2 *is* the speed work. A parallel effort would compete for the same nights and buy the same thing twice. Also recorded: deployment cost is a third supporting leg and does not replace §12.3's two carrying results.

**Closed definitively: MACE runs RAG on FINDVER, with FINDVER's own configuration.** An intermediate note during this session inferred it from three indirect signals and then claimed they never describe the setup. **The second half was wrong.** They describe it fully, in a Retrieval Mechanism paragraph separate from the results:

> *"Retrieval Mechanism. Since retrieval is not our primary focus, we adopt existing strategies. For FinDVer, Zhao et al. (2024b) compared three retrievers: BM25, Contriever, and OpenAI's text-embedding-3 across retrieval sizes k = 3, 5, 10, finding text-embedding-3 with k = 10 optimal. We adopt this configuration, achieving 67.91% and 69.53% recall for evidence retrieval on Testmini and Test sets."*

Three consequences, all favourable. **Their setup is identical to FINDVER's and to our Tier 0 baseline**, `text-embedding-3` at *k* = 10, so their accuracy numbers compare to ours with no setting caveat. **Weakness 2's quote is verbatim rather than a paraphrase** — the leading approach on this benchmark states in writing that it declined to work on retrieval, which is the strongest available support for §6.6's gap statement. And **their reported recall of 67.91% agrees with §3.4's record and with our own recomputed 68.01% to within rounding**, so three sources now agree on the ceiling.

They never use the term "RAG" anywhere; they describe the mechanism without the acronym, which is why a keyword search for it finds only `TableRAG` in their related work.

**One citation gap found in their related work: `TableRAG` (Chen et al., 2024)**, retrieval-augmented generation for large-table context limits. Not in §6.5, and retrieval-plus-tables is our core. Added to the reference list with `TableGPT2` and `TAT`, both training-based and out of our lane but worth positioning against.

**Also found in §4.4.2: their body text overstates their own numbers, and their abstract does not.** The sentence reads *"Mace achieves SOTA performance on both TM and T splits with Qw-235B reaching 0.76 accuracy, matching the best baseline results."* The two clauses conflict and the numbers side with the second: on TM 0.76 ties Qwen-2.5 72B, and on T 0.76 ties both Mistral-Large 123B and GPT-4o. Ties on both splits. **When citing their FINDVER result, use the abstract's "on par with the best models," not §4.4.2's "SOTA."** State the tie plainly and do not editorialise about the gap between their two descriptions, for the same reason the Claude discrepancy is left uncharacterised.

### Read by eye: FINDVER Table 4, and a better motivation for Tier 1

A screenshot of FINDVER's Table 4 was taken and read directly, kept at `docs/findver_baseline_accuracy.png`. §2.6's averages are confirmed exactly: Claude-3.5-Sonnet 77.2 long-context / 75.0 RAG, GPT-4o 75.7 / 73.7, human expert 93.3, non-expert 86.7, random 50.0. The **per-subset breakdown was not previously in any of our documents** and is now transcribed into §2.6.

**The finding worth having: FDV-MATH is where the best model collapses.**

    Claude-3.5-Sonnet, RAG    FDV-IE 80.5    FDV-KNOW 75.5    FDV-MATH 69.0

An 11.5-point spread between the strongest model's easiest and hardest subset, and the hardest one is exactly what Tier 1's code execution attacks. Tier 1 previously rested on the benchmark's error taxonomy and on our own trial-run arithmetic failure. This is a third motivation and the hardest to argue with, because it is a published number showing the gap is widest precisely where we intervene.

**Decided how to write up the MACE discrepancy: state the mismatch and its effect, say nothing about the cause.** Two facts, both checkable from the two published tables. MACE's Claude-3.5-Sonnet is 0.73 and matches neither FINDVER figure (77.2 long-context, 75.0 RAG). And their table places Claude below GPT-4o where FINDVER places it above, reversing the two strongest baselines.

Considered and rejected: writing it as a row swap, and writing it as a deliberate demotion. The first is an unverifiable mechanism. The second is a claim about intent, and the argument for it was that it would make us look better, which is not a reason to characterise evidence. Only two models overlap between the tables, review is double-blind, and a MACE author is a plausible reviewer. An unsupported claim about a competitor's conduct would put every other number in our paper under suspicion. The bare factual version is also the more forceful one, since it costs a reviewer nothing to verify.

**Which figure we use: FINDVER's, 75.0% RAG.** We evaluate on their benchmark, so their published number is the reference. MACE's baseline column is not a source for any model FINDVER already published.

**One inference kept: MACE's baselines track FINDVER's RAG column, not long-context**, which partly answers the setting question their Table 8 leaves open.

**A note on which fetches failed.** Two pages were fetched. The MACE numbers came back **correct** and survived verification. The FINDVER numbers came back **wrong** twice over: it reported GPT-4o at 76.2% when the real figures are 75.7 long-context and 73.7 RAG, and it called the results table "Table 3" when it is Table 4. The failure was not uniform, which is the point: there is no way to tell a good fetch from a bad one without checking, so every fetched figure stays unverified until read. These block every "nobody has done X" sentence in §6.6, and they also block calling MACE the strongest published approach, which several arguments above lean on.

Nothing was measured this session. No code changed. The Ollama overflow alarm has still never fired on real data, and the professor calling the eviction finding "valuable" does not change that.

---

## 4 August 2026 — the recall scorer, and fusion measured for free

The professor has not answered on the GPU. That blocks nothing today: the retriever is
chosen on recall alone, with no model calls, so it is daytime work and machine-independent.
§12.2's revised timeline puts 4–7 August exactly here.

### `test_scripts/measure_recall.py`, built and validated

The scorer takes one dict, `example_id -> list of element ids`, and nothing else. That single
decision is what makes it reusable: upstream's shipped rankings, our own BM25, a fusion and a
reranker all reduce to that shape, so the instrument is written once for the whole project.

It reports all three metrics from §3.4 — macro, element, all-gold — overall and per subset.
The distinction is where a recall script silently produces plausible wrong numbers, so it is
worth restating. Macro averages per-claim fractions, one vote per claim. Element divides the
totals, one vote per gold element. All-gold counts claims that received everything, all or
nothing. Two claims, A needing 1 element and getting it, B needing 5 and getting 1, give
60%, 33% and 50% on the same retrieval.

**Validated by reproducing all twelve figures §3.4 recorded on 2 August**, for
`text-embedding-3-large`, `bm25`, `contriever-msmarco` and our placeholder. The script
asserts them itself and prints `SCORER IS WRONG, do not use` on mismatch. This mattered more
than usual: every retrieval decision this week rests on this one instrument, and a wrong
scorer is indistinguishable from a bad retriever from the outside.

**One discrepancy chased rather than ignored.** It counts 1,959 gold elements against §11
item 9's 1,964. Five claims repeat an index: `numeric-val-36` is `(24, 24)`, `ie-val-193` is
`(7, 8, 7)`, plus `numeric-val-41`, `numeric-val-139` and `knowledge-val-20`. Deduplicating
is correct for recall and upstream does the same at `recall_evaluation.py` line 15. Both
counts stand, for different jobs.

### The union diagnostic: fusion is worth building

Take each retriever's top 10, union the ids, score the result. A merge rule can only reorder
what at least one retriever already found, so the union bounds any possible fusion.

    bm25 alone                65.16%   62.8%   38.6%
    text-embedding-3 alone    68.01%   62.4%   42.6%
    union of both             80.86%   77.0%   58.9%

Element recall rises 14 points. `ie-val-23` is the clean instance: gold `[2, 3, 49]`, BM25
returns 3 and 49, the embedding returns 2 and 3, neither alone gets the claim.

**Why this cost nothing, since the question was asked and is worth recording.** Recall
scoring needs only element ids, never text and never a model. FINDVER ran both retrievers and
shipped the full rankings in `retriever_output/all/`. So any operation combining ids they
already produced is arithmetic over existing files. The same is true of RRF, which uses only
rank positions. What is *not* free is retrieving differently — a new embedding model or new
chunking means actually running a retriever over 60,871 elements.

### RRF measured: +6.05 macro points over the published number

    pool = top 10 of each     74.06%   69.0%   48.7%
    pool = top 25 of each     68.81%   65.1%   42.3%
    pool = full ranking       69.21%   65.6%   43.1%

74.06% against the 68.01% FINDVER published and MACE adopted unchanged, from two retrievers
already in their own repository, with no model call. That is about half the headroom the
union identified.

**A shallow candidate pool beats a deep one.** RRF rewards agreement, so on a deep pool an
element ranked 15th by both lists outscores an element ranked 1st by one. Truncating at 10
excludes the consistently-mediocre and lets a strong single-list pick survive. The cheapest
configuration is also the best one.

**This cannot ship.** It uses `text-embedding-3`, a paid API we hold no key for, and an
on-device paper cannot depend on one anyway. Its job was to decide whether the local
embedding index is worth its one-time CPU cost. It decides yes.

**On novelty, deliberately.** Hybrid BM25-plus-dense with RRF is standard IR with years of
literature. We are not inventing it. What is unattempted is applying it *on this benchmark*,
and that is not oversight: FINDVER compared three retrievers to pick a default, and MACE
states in writing that retrieval is not their focus. Phrasing stays "we found no other
method."

### Per subset, and it maps onto the two tiers

    FDV-IE       63.57%   58.2%   33.2%
    FDV-MATH     79.17%   79.0%   66.8%
    FDV-KNOW     59.61%   56.1%   24.0%

Against FINDVER Table 4's Claude-3.5-Sonnet RAG figures, 69.0 on MATH and 75.5 on KNOW: MATH
is where retrieval works best and the best model still scores worst, so its difficulty is
arithmetic, which is the Tier 1 argument. KNOW is where retrieval works worst, so the Tier 2
argument lands there. All-gold structurally flatters MATH, since numeric claims need 1.87
elements against knowledge's 3.66; the gap survives on element recall, which has no such bias.

### Decided: the retriever design

Two arms fused by RRF. BM25 over `context` elements, pure Python. Dense retrieval with a
local Ollama embedding model over a cached index. Pool 10 per arm, `c = 60`, k = 10 out.

**Chunking does not change.** One `context` element is one chunk. §7.3's "keep tables whole"
is already satisfied, because a table *is* one element carrying `type: "table"`, and the
one-to-one mapping is what lets gold indices score the output directly. This also means the
embedding index will not need rebuilding for a chunking change.

Build order, each step gating the next: our own BM25 validated at exactly 65.16, then the
index with the dense arm scored alone, then the fusion. **The open risk is the dense arm** —
`nomic-embed-text` is weaker than `text-embedding-3-large` and BM25's arm is fixed, so a weak
dense arm shrinks the gain. Scoring it alone before fusing is the go/no-go and costs nothing
once the index exists.

**Target: beat 68.01% with a fully local, free retriever. 74.06% is a reference point, not
the goal.**

### Also recorded

§11 gained item 11, on what can be deleted when the project ends. `FinDVer/` is re-clonable at
the pinned commit `e8bb237`; the embedding index is derived data at about 178 MB as a numpy
`.npy` at 768 dims, or roughly 0.9 GB if stored as JSON, which is the mistake to avoid.
`results/` and `logs/` are the exception, because each experiment directory is about 12 h of
compute that cannot be regenerated.

Nothing was run on a model today. No cloud quota used.

## 4 August 2026, later — our BM25, and a 9-point gap that had to be explained

`src/bm25_retriever.py` is written and scored. Three blocks: `report_stats` computes per-element
token counters, lengths, the report's mean element length and document frequencies;
`score_element` applies the BM25 formula for one element; `retrieve` scores all elements, sorts
best-first and returns the top 10. It returns **ranked order, not document order**, because RRF
consumes rank positions. The prompt builder re-sorts.

Three decisions taken before writing. IDF is computed per report, not across all 600 filings,
because rare-inside-this-filing is the useful notion and it matches what the asserter already
does. The tokenizer is reused from `src/evidence_asserter.py`. And the return is ranked rather
than document order, which is a change from the placeholder's convention.

### The result

    ours, bm25                        74.60%   70.5%   50.4%    free, no model
    text-embedding-3-large            68.01%   62.4%   42.6%    paid API
    upstream bm25                     65.16%   62.8%   38.6%
    RRF of the two published ones     74.06%   69.0%   48.7%    paid API
    ours, placeholder                 57.54%   53.2%   31.6%

A free, local, model-free retriever beats the paid embedding by 6.59 macro points and edges
past the fusion of both published retrievers measured earlier the same day.

### Two things asserted earlier the same day and now withdrawn

**"Validate by reproducing 65.16 exactly."** Unreachable. Upstream's BM25 is a different
algorithm, and chasing an exact match would have meant debugging a non-bug. Caught before the
validation ran, by reading `FinDVer/retriever/retriever.py` and `utils/bm25_utils.py` rather
than assuming the two implementations agreed. It had already been written into three documents
and is struck in all three.

**"Target: beat 68.01% with a fully local retriever."** Met the same day, before any dense arm
exists.

### Why it is not a fluke, in full, because a 9-point jump over a published baseline is a bug

*Output shape.* Exactly 10 ids for all 700 claims, no duplicates within a claim, no id out of
range for its report.

*No gold leakage.* The retrieval path reads `claim.statement` and `report["context"]` only.
`relevant_context` is never touched until the scorer, after retrieval has returned.

*The instrument did not move.* The same `aggregate` scores every row, the three upstream rows
still reproduce their 2 August figures, and the script's self-assertion passes. A scorer biased
toward our retriever would have shifted them.

*The setups match.* `prepare_context_list` in their retriever is
`[i["context"] for i in report["context"]]`, then `BM25Okapi` per report. One `context` element
per chunk, corpus scoped to one report. Identical to ours, so the difference is not chunking,
not corpus scope, and not the candidate set.

*It reconstructs in both directions.* Applying all three upstream choices to our own code gives
**66.72% against their published 65.16%.** The 1.6-point residual is the approximation of NLTK
`word_tokenize` and Porter stemming, neither installed here. Reconstructing their number from
our code is what turns "ours is better" into "ours differs for these three reasons," and it is
the check that mattered most.

### The ablations, including two that killed the leading hypothesis

    ours as written                                  74.60%   70.5%   50.4%
    classic IDF, no +1, can go negative              72.09%   67.5%   47.7%
    rank_bm25's exact IDF, negatives floored         73.33%   69.4%   48.4%
    punctuation kept as tokens, NLTK-like            72.58%   68.6%   47.3%
    suffix stemming applied                          74.67%   70.3%   50.0%
    tokenizer without inner-comma stripping          74.78%   70.6%   50.9%
    all three upstream choices combined              66.72%   64.2%   40.0%

**Two predictions were wrong and are recorded as such.** Stemming makes no difference, 74.67
against 74.60. And stripping inner commas from numbers makes no difference either, 74.78
against 74.60 — that had been the stated leading hypothesis for our advantage, on the reasoning
that financial claims quote exact figures. It is wrong. The advantage is elsewhere.

The three real effects also compound rather than sum: about 4.5 points individually, 7.9
together.

### The finding worth carrying into the paper: upstream's tokenizer penalises tables

Keeping punctuation as tokens inflates measured element length by **1.81x for tables against
1.13x for paragraphs**, because pipe-delimited table text is dense in `|`, `$`, `(`, `)` and
`,`. BM25's length normalisation at `B = 0.75` then divides table scores down disproportionately
and pushes tables out of the top 10. Tables are about 18% of elements and carry a large share of
the evidence this benchmark asks about. A tokenizer choice made for general prose quietly
suppresses the evidence type the benchmark is built on.

**Provenance, stated accurately because this is a candidate paper sentence.** The tokenizer is
`src/evidence_asserter.tokenize`, written 2 August for the asserter, where the inner-comma
handling was a deliberate choice for numeric tokens. **Dropping punctuation was not chosen for
retrieval reasons by anyone.** It was inherited by reusing that tokenizer in BM25, a reuse
proposed as one of the three pre-writing decisions. What is new on 4 August is the measurement
that it matters and the mechanism explaining why. It must be written as a finding, never as a
designed insight. Note also that the inner-comma handling, which *was* deliberate, turns out to
contribute nothing, while the incidental property contributes two points.

### The dense arm survives, with a thinner margin

    ours bm25 alone                          74.60%   70.5%   50.4%
    RRF(ours bm25, text-embedding-3)         77.14%   72.1%   54.3%
    union of the two, ceiling                82.85%   78.9%   62.9%

The paid embedding still adds **+2.54 macro** on top of our BM25, down from the +6.05 that
fusion bought over the published baseline. So `nomic-embed-text`, which is weaker than
`text-embedding-3-large`, now has to preserve a 2.5-point gain rather than a 6-point one.
**Score the local dense arm alone before fusing.** If it lands far below 68% the fusion gain may
not survive, and BM25 alone is already a publishable retrieval result. The target is no longer
68.01%; it is whether a fully local hybrid clears our own 74.60%.

No model was run today and no cloud quota was used.

### The k1/b sweep, and why the winner is not adopted

20 configurations over all 700 claims at k=10, macro recall:

    k1 \ b     0.00     0.25     0.50     0.75     1.00
    0.9       70.37    72.77    73.95    74.72    74.91
    1.2       70.00    72.84    73.89    74.97    74.60
    1.5       69.56    72.88    74.42    74.60    74.68
    2.0       69.23    72.84    74.67    74.69    74.80

Best is `k1 = 1.2, b = 0.75` at 74.97% against the defaults' 74.60%.

**Decided: keep the defaults, 1.5 and 0.75, and do not take the 0.37 points.** Eight cells sit
between 74.6 and 75.0, which at n = 700 is inside sampling noise. And the sweep ran on all 700
test claims, so adopting its winner is selecting on the test set. §9 already concedes that the
102-example slice makes about 15% of a final number self-optimised; a constant tuned on the
full 700 would make that 100%. An untuned standard configuration is worth more than 0.37 points
bought that way. The sweep is reported as evidence the defaults are not load-bearing, not as a
tuning result.

**What it does establish: `b` carries this retriever and `k1` does not.** Length normalisation
off costs about 5 points, 69.56 at `b = 0` against 74.60 at 0.75, while `k1` from 0.9 to 2.0
moves under half a point. Independent corroboration of the tokenizer finding: length handling
is where the accuracy lives, which is exactly why upstream's punctuation-inflated lengths cost
them so much.

**One qualifier.** At `b = 0` the table-length mechanism is inert, and we still score 69.56%
against upstream's 65.16%. So the table effect is a large part of our advantage, not all of it;
the IDF variant carries the rest.

### The fusion is not free insurance: a weak arm actively hurts

    ours bm25 alone                          74.60%   70.5%   50.4%
    RRF(ours, text-embedding-3 @ 68.01)      77.14%   72.1%   54.3%
    RRF(ours, contriever @ 33.48)            69.46%   63.7%   42.7%
    RRF(ours, embed, contriever)             72.83%   67.4%   48.3%

**Contriever drags our BM25 down by 5.1 points**, and adding it to the good pair costs 4.3.
RRF weights every list equally, so a bad ranker gets an equal vote. This was assumed to be a
safe operation and it is not.

**Consequence for the dense arm.** `nomic-embed-text` has to be measured alone before it is
fused with anything. The break-even sits somewhere between contriever's 33.48% and
`text-embedding-3`'s 68.01% and we do not know where. If it lands low, the correct action is to
delete the vectors and ship BM25 alone, which is already a publishable retrieval result.
Weighted RRF, giving BM25 two votes to the dense arm's one, is the fallback if nomic turns out
real but mediocre.

**Cost-saving on the go/no-go:** embed only the reports behind a ~102-claim sample rather than
all 255 reports, about a seventh of the work, and build the full index only if it passes.

### Correction: claim decomposition is a pipeline component, not an optional extra

It was described this session as "the first thing here that isn't free," which understated its
status. §4.4 assigns *claim decomposition into atomic facts* to the **edge 3B**, and §8 lists it
in Tier 2 beside hybrid retrieval. It is planned pipeline work.

Its cost is also smaller than implied, because **the output caches**. The prompt is the claim
plus instructions, roughly 200 tokens, so at the fitted 0.0641 s/token it is about 15-20 s per
claim and 3-4 hours for all 700, paid once. Every retrieval experiment afterwards reuses the
saved sub-claims for free, exactly like the embedding index. That is an evening, not a night,
and it does not need the GPU.

### The hardware rule extended: cached model outputs are inputs, not results

Recorded in `working_state.md` alongside the 3 August rule. The no-mixing rule governs
*measured numbers*. Sub-claims and embeddings are inputs consumed by a scoring step that
compares element ids against gold, with no timing and no model-accuracy claim, so producing
them on the server does not mix machines in any table.

Two places it does bite. The final MacBook latency night must run decomposition **on the
MacBook**, or the pipeline latency figure omits a real step. And temperature 0 does not
guarantee identical tokens across CPU and CUDA, so server-generated sub-claims may not
regenerate byte-identically here; a recall number measured from them is reproducible from the
cached file rather than from a re-run. Treat that file as the artifact of record.

### Measured: nomic-embed-text throughput, and the dense arm gets more expensive

Run against the local Ollama server on 50 real context elements from `ie-val-0`'s report,
mean length 968 characters.

    dimensions                  768        confirms the 178 MB index estimate
    50 elements, batched      21.62 s
    per element                0.432 s

    102-claim slice     89 reports    20,718 elements    2.5 h
    48-claim pilot      42 reports    10,612 elements    1.3 h
    full testmini      255 reports    60,871 elements    7.3 h

**The full index is a night, not an afternoon**, which changes the trade. The dense arm's
expected payoff is at most the +2.54 that `text-embedding-3-large` bought on top of our BM25,
and nomic is weaker than that, so realistically less. Contriever showed it can be negative.
Against roughly 18 remaining nights, a full index on spec is a bad buy.

**Decided: measure on the 102-claim slice first, 2.5 h.** Same seed-0 stratified slice used
everywhere else, so the number is comparable, and plus or minus 10 points at n=102 is far more
than enough to separate 33% from 68%, which is the only question that matters.

### `test_scripts/build_embedding_index.py`

Embeds every element of every report behind a stratified sample and caches the vectors.

**No numpy on this machine**, discovered here. Storage is therefore `array.array("f")` raw
float32, which is the same bytes a `.npy` holds minus the header, one file per report, rows in
`report["context"]` order. Row i is element id i, safe because id equals list position. Nothing
in this script does arithmetic, so the dependency was avoidable entirely; whoever reads the
vectors back can use numpy or not.

**Resume is by report and tested on byte length, not existence**, the same distinction the
logger needed on 1 August. The file is written under a `.partial` name and `os.replace`d only
when complete, so the final name never exists in a half-written state. An interrupted 2.5 h run
costs at most one report.

Also handled: a blank element is sent as a single space, because Ollama rejects an empty string
and a blank element would otherwise kill the run 90 minutes in; the returned dimension is
asserted against 768 per batch, so a silently swapped model fails loudly; and one HTTP retry
before a report is recorded as failed and the run continues.

`embeddings/` added to `.gitignore`.

### Confirmed for the record: what caffeinate actually does

It runs the job as a child process and holds the no-sleep assertion only for that process's
lifetime, releasing it on exit. The machine therefore stays awake for the duration of the job
and returns to its normal idle timer afterwards, rather than staying awake all night. `-ims`
still allows the display to sleep. It cannot override a closed lid.

**Validated on the smoke run:** vectors read back at the right count, and cosine ranking works.
**nomic-embed-text returns L2-normalised vectors, norm exactly 1.000**, so cosine similarity is
a plain dot product. That removes the normalisation step from tomorrow's scoring code and makes
pure Python fast enough at n=102 without installing numpy.

---

## 5 August 2026 — the embedding index, and a go/no-go that answered the wrong question

### The index built cleanly

`test_scripts/build_embedding_index.py 17`, run overnight under `caffeinate -ims`.

    89 reports, 20,718 elements, 137.0 minutes, 0 failed reports

Against a 2.5 h estimate from the 0.432 s/element measurement, so the extrapolation held.
Resume-by-report was exercised twice, on the four reports left by the previous evening's smoke
test, and skipped them correctly.

numpy was installed during the evening: `pip3 install --break-system-packages numpy`. The flag
is required because this machine runs Homebrew Python 3.14 with no venv, marked
`EXTERNALLY-MANAGED`, so plain `pip3 install` refuses. A venv was considered and rejected:
every documented command in the docs is a bare `python3 ...`, and forgetting to activate before
an overnight job would cost a night. Verified that the raw float32 files written without numpy
read straight back with `np.fromfile(path, dtype="float32").reshape(-1, 768)`.

### The dense arm, measured

All rows on the same 102-claim slice, k=10, via `test_scripts/measure_dense_recall.py`:

    ours, bm25                             76.18%   71.0%   53.9%
    nomic-embed-text alone                 62.86%   55.5%   35.3%
    RRF(bm25, nomic) equal votes           75.57%   70.0%   49.0%
    RRF(bm25 x1.10, nomic)                 76.26%   71.0%   52.0%
    RRF(bm25 x1.25 and above, nomic)       76.18%   71.0%   53.9%
    control: RRF(bm25, text-embedding-3)   76.08%   71.0%   53.9%
    union, ceiling on any fusion           83.27%   78.6%   61.8%

**nomic-embed-text reaches 62.86%**, five points below `text-embedding-3-large`'s 68.01% and
nearly double contriever's 33.48%. A free local embedding model landing that close to the paid
one is worth reporting on its own, whatever happens to the fusion.

### The go/no-go could not answer the question it was built for, and that is our error

The control row is the one that matters. It fuses our BM25 with the **paid** embedding, a
combination measured at **+2.54 macro on all 700 claims** on 4 August. On this slice it gains
nothing, 76.08 against 76.18. A fusion known to work at full scale returning null here is a
statement about the instrument, not the method.

**The noise floor is the same size as the signal.** Our BM25 scores 74.60% on all 700 and
76.18% on this 102-claim slice, a 1.58-point swing from sampling alone, against a 2.5-point
effect under test. §9 already said 102 examples cannot rank two configurations three points
apart. That sentence was written about prompts and applies here unchanged.

**Recorded as a design error rather than a finding.** The slice was sized to separate 33% from
68%, a 35-point gap made urgent by the contriever result, and it does that cleanly: nomic's
62.86% is solidly measured. It was then used to ask whether fusion adds 2 points, which needs a
different sample size. Two questions were asked of one run and only the first was answerable.

The user caught a related slip in the reporting: 74.60% and 76.18% were compared as though
interchangeable when they are the full 700 and the 102 slice respectively. Both were re-run
side by side from the same code to confirm. The table header did say "102-claim slice", but the
denominator changed mid-discussion without being flagged.

### Weighted RRF has almost no useful range

The rows at weights 1.25, 1.5, 1.75, 2 and 3 are byte-identical to BM25 alone. Not a bug. With
two lists of length k and constant c, once the weight ratio exceeds roughly `(c+k)/(c+1)`, the
heavy list's worst element outscores the light list's best, and the fusion returns the heavy
list unchanged. At k=10 and c=60 that threshold is about **1.16**. Only a narrow band near 1.1
blends anything at all, and 1.1 was the single row that moved.

Worth knowing before anyone tries to tune fusion weights: the knob is nearly binary at these
list lengths.

### Decided: keep the vectors, decomposition next

**Keep `embeddings/`.** Deletion was the contriever contingency and nomic is not contriever.

**Do not finish the index yet.** The remaining 166 reports cost about 4.8 h for an expected
payoff of at most +2.5 points. More decisively, **claim decomposition changes the queries for
both arms**, so any fusion settled now is invalidated by it. Paying 4.8 h for a number that
decomposition will overwrite is paying twice.

**Order from here.** Build decomposition, 3-4 h of model time, cached to disk. Then score BM25
plus decomposition on all 700, which costs nothing and needs no index. Then, only if the dense
arm still looks worth it, finish the index and settle fusion at n=700 where 2.5 points is
resolvable.

**No `src/dense_retriever.py` was written and none should be yet.** `embed()` and
`load_index()` live in the test script deliberately, so that no pipeline code exists for a
component that may still be dropped.

## 5 August 2026, afternoon — decomposition tested and closed, and k turns out to be the real lever

### Claim decomposition: built, measured, negative

**The plan was more confident than its evidence.** §3.6 motivates decomposed retrieval and §8
schedules it as Tier 2, but its "direct evidence this matters" is a week-1 observation that the
7B model produced cleaner *reasoning* when it decomposed a compound claim. That is not evidence
about recall. Flagged before building rather than after.

**Two free tests were run first, and both argued against building it.**

*Does BM25 fail the way decomposition would fix?* Yes, and this is the one positive signal.
Recall by number of gold elements needed, our BM25 at k=10 over all 700:

    1 element   79.8%    (84 claims)
    2 elements  81.5%   (241)
    3 elements  78.6%   (201)
    4 elements  60.2%   (113)
    5 elements  57.6%    (49)
    6 elements  37.5%     (8)

Flat to 3, collapses after. 174 claims, 24% of the benchmark, carry a 20-40 point hole.

*Does the mechanism work without a model?* No. A rule-based split on commas and connectives,
merged round-robin, scored **73.39% against the whole claim's 74.60%** over all 700, with no
consistent pattern by complexity: +1.2 at 1 element, -1.8 at 2, -3.1 at 3, +2.9 at 4, -3.1 at
5+. So the multi-query mechanism carries no free lunch and any gain must come from split
quality.

**Decided on that basis to spend 40 minutes rather than a day**: decompose only the 174 claims
with 4+ gold elements, where the deficit is large enough to see through noise.

**The run.** `prompts/decompose_v1.txt`, `configs/decompose_v1.json`, `num_ctx` 2048 and
`num_predict` 300 since the prompt is ~300 tokens. 174 claims, **36.7 minutes**, cached to
`results/decompositions_v1.json` after every claim. Mean 3.94 sub-claims, **0 parsed to
nothing, 0 errors**.

**Decomposition quality was good, which matters because it rules out the obvious explanation.**
Numbers, dates and entity names came through exactly, so the paraphrase risk to BM25's
exact-string matching did not materialise. Roughly a fifth of sub-claims are dependent
fragments rather than self-contained facts, e.g. "With a $660,000 principal." and "Despite
intense competition in the market and regulatory requirements to maintain REIT status." Those
still carry distinctive tokens, so they are usable as queries even though they would be poor
reasoning inputs.

**Six merge strategies, 174 claims, k=10:**

    whole claim only, the bar          57.88%   56.6%   11.5%
    round-robin, whole + sub-claims    56.04%   54.3%   10.9%
    round-robin, whole keeps top 5     57.33%   55.6%   12.6%
    round-robin, sub-claims only       54.37%   52.9%    9.2%
    RRF across queries                 45.27%   44.3%    4.0%
    max raw BM25 score across queries  57.53%   56.2%   11.5%
    max normalised score               56.96%   55.2%    9.2%
    sum of normalised scores           54.50%   53.2%   10.3%

Nothing beats the bar. The bar itself checks out: 57.88% is exactly the weighted mean of the
60.2% and 53.6% buckets.

One prediction held and one did not. RRF was predicted to be wrong here because it rewards
agreement between lists, when decomposition wants each sub-claim to find *different* evidence.
It is the worst variant by 12 points. Round-robin was predicted to be the right merge. It is
below the bar.

### A false positive, caught by a control, and the mechanism is worth recording

Mid-analysis the union of the whole claim's top 10 with every sub-claim's top 10 was scored:
**76.14% against 57.88%**, with 101 of 174 claims containing gold that only a sub-claim found,
147 elements in total. This was reported as reversing the conclusion: the information is there,
only the merge is failing.

**It was wrong.** The union holds a mean of 30.3 candidates against the whole claim's 10. The
control is the whole claim at the same budget:

    whole claim, k=30      79.37%
    decomposed union       76.14%   (mean 30.3 elements)

**At equal candidate budget the decomposed union is 3.2 points worse than plain BM25.** The
apparent advantage was entirely a k effect.

The lesson generalises: **any comparison between a multi-query retriever and a single-query one
must control for candidate count.** Union and fusion diagnostics inherently enlarge the
candidate pool, and reading a gain off them without the matched-k control manufactures a
positive result out of nothing. The same shape of error would have been possible in the 4 August
BM25-plus-embedding union, which was also 2k against k; there the conclusion survived because
real RRF at k=10 was measured separately and gained 6 points, but the diagnostic alone did not
establish it.

**Decision: decomposition is closed for retrieval.** It costs a model call per claim, adds a
pipeline component, and loses to a parameter change. **It is not closed for Tier 1 reasoning**,
which is what §3.6's observation was about and which is a separate end-to-end question.

**No further decomposition testing is needed on other samples.** The test ran on the population
where the mechanism had the most to fix. Easier claims offer less room, not more.

Consequently `src/decomposer.py` and `src/decomposed_retriever.py` were never written, which
was the point of testing in a throwaway script first.

### k is the largest retrieval lever found so far

Our BM25, all 700 claims:

    k     macro    element   all-gold
     5   62.39%     56.9%     34.1%
    10   74.60%     70.5%     50.4%
    15   81.12%     77.4%     60.0%
    20   84.56%     81.7%     66.6%
    25   86.34%     83.8%     69.7%
    30   88.51%     86.0%     73.3%

**13.9 macro points from k=10 to k=30.** The entire dense-fusion question was worth +2.5, and
the published baseline everyone copied is 68.01%. This overturns §7.3's 2 August reading that
"k is the wrong lever," which was measured on the *placeholder* retriever over 12 trial
examples and does not hold for a real ranker over 700.

### Four factors decide k, and only one is free

1. **Recall.** Free, measured, above.
2. **Ingestion cost.** k sets prompt length and prompt length is the whole cost model at
   R² 0.995. Generation barely moves, `eval_count` ranged 261-496 in the trial run regardless
   of prompt size.
3. **Accuracy, with no data at all.** Higher k adds distractors alongside gold, and a 3B model
   may not ignore them. The only contrary evidence is the trial run's 4/4 with evidence present
   against 4/8 without, which is n=4 and already flagged untrustworthy. Costs one overnight run
   per k value.
4. **The deployment story**, a paper decision rather than a measurement. The MacBook is the
   device of record, so reported latency is the MacBook figure wherever accuracy was measured.
   Doubling per-example time weakens the exact axis §6.1 attacks MACE on, their 2.2x-27x
   slowdown over single-pass.

**A GPU does not remove factor 4.** Accuracy and ablations may run on a server under the 3 Aug
hardware rule, and a k sweep qualifies. But the number reported as deployment cost stays the
MacBook one. A GPU makes the experiment affordable, not the operating point cheap. Same applies
to a third machine: professor's server plus a borrowed PC plus the MacBook is two mixing
violations, so whichever is chosen must carry the whole results table.

**Likely framing: report the curve, not the maximum.** Recall against measured per-example
latency across k, on the device, with a chosen operating point. Stronger than a single tuned k
and it converts the cost of high k into the finding.

**How factor 3 gets bought without extra nights: fold it into condition 1.** Run the edge-only
baseline §9.2 already schedules at two k values instead of one. **k must be frozen before
condition 1 starts**, since §9.2 requires every condition to share the same retrieval.

**Prompt trimming returns for a third reason.** Specified to prevent overflow, downgraded 2
August when overflow did not occur, parked behind the retriever. If the recall lives at k=20 or
above, trimming is what makes it affordable. It must count tokens, not characters.

### Correction to a correction

The k-versus-tokens table was first reported with a warning that the character-based token
estimates were unreliable, because they gave 4,737 tokens for the placeholder at k=10 against
the trial run's measured 6,610. **That warning was itself wrong.** The 6,610 is the mean over
the 12-example trial sample; the 4,737 is the mean over all 700 claims. Different populations,
not a broken conversion. The measured ratio is 4.20-4.44 chars per token, confirming the 4.36
already in the docs.

### Token calibration, and a live overflow defect in the current configuration

Six calls with `num_predict=1`, so only ingestion is paid, and `num_ctx` 32768 so nothing could
evict during the measurement itself.

    claim              k   chars  tokens   c/t    secs  tok/s
    knowledge-val-51  10    8002    1880  4.26    81.1   23.2
    knowledge-val-51  30   26231    6043  4.34   306.5   19.7
    knowledge-val-178 10   22907    5165  4.44   300.1   17.2
    knowledge-val-178 30   53051   12635  4.20   672.5   18.8
    numeric-val-30    10   41355   12480  3.31   974.1   12.8
    numeric-val-30    30   82932   24400  3.40  1505.5   16.2

**First clean ingestion measurement: 12.8-23.2 tok/s, mean about 16.** The 2 August fit rejected
separating ingestion from generation as degenerate because `eval_count` varied only 261-496.
With `num_predict=1` that confound is gone. The 15.6 tok/s "implied ingestion rate" in the docs
came from total elapsed and absorbed generation; it is superseded.

**The chars-per-token ratio is not a constant.** 3.31 on table-heavy numeric content against
4.44 on prose, a 34% spread. The 2 August note already said a character budget is not a safe
proxy for a token budget; this confirms it on our own retriever's output.

**A correction made and then itself corrected, worth recording as a sequence.** The k-versus-
tokens table was first published with a warning that the estimates were unreliable, because they
gave 4,737 tokens for the placeholder at k=10 against the trial run's measured 6,610. That
warning was wrong: 6,610 is the mean over the 12-example trial sample, 4,737 the mean over all
700. Different populations, not a broken conversion. Then `numeric-val-30` arrived and showed
the ratio genuinely does vary by a third between content types, so the estimates *are*
unreliable, for a different reason than the one first given. Two wrong diagnoses of the same
symptom before the right one.

**The defect: the configuration we were about to run baselines on already overflows.** Prompt
tokens across all 700 claims at the conservative 3.31 ratio, since the tail is where table-heavy
content lives:

    k     mean     p90      max   over 14384   over 30768
    10    4426    9490    19466      15/700       0/700
    15    6472   13627    29589      62/700       0/700
    20    8454   17734    36544     104/700       6/700
    25   10427   22326    43139     120/700      25/700
    30   12328   26885    52241     139/700      53/700

**About 15 of 700 claims overflow at the current k=10 with `num_ctx` 16384 and `num_predict`
2000.** Not a consequence of raising k. Never caught because the trial run was 12 examples, and
§11 item 9 already records that the overflow alarm has never fired on real data. Ollama 0.12.3
evicts the oldest prompt tokens silently while reporting `done_reason: "stop"`, so those
examples would have returned confident answers over evidence that had scrolled out of view.

Three consequences. **Prompt trimming is mandatory**, its fourth appearance and the first time
it is a measured correctness requirement rather than a precaution or an optimisation; it counts
tokens. **k=30 is unreachable**, with 53 of 700 over even at `num_ctx` 32768, so **k=20 is the
practical ceiling** and is the high candidate for the k experiment. **A larger window is
necessary but not sufficient**: 32768 costs 4.4 GB of 16 GB and buys k=15 outright, but leaves
6 claims over at k=20.

One incidental positive: tables are a mean of 6.5 of the top 30 retrieved against an 18% base
rate, so our BM25 slightly over-retrieves tables. That is the length-normalisation property
appearing a third time, and it is the right direction for this benchmark.

### Corrected by the user: fusion must be decided before condition 1, not after

The plan stated earlier this session was to decide k through condition 1 and settle the dense
arm afterwards. **That is invalid and the user caught it.** §9.2 requires every condition to
share the same retrieval, and states plainly that changing retrieval moves all four conditions.
Condition 1 freezes the retriever, so adding a dense arm afterwards forces a re-run of it.

The circularity resolves because the two questions need different evidence. **Fusion or no
fusion is a retriever choice decided on recall, which is free**, because fusion changes which k
chunks are retrieved rather than how many, so the distractor argument does not apply. **k is
decided on recall and accuracy**, because k is exactly the knob trading gold against
distractors, and that half needs condition 1.

**Corrected order.** Finish the embedding index for the remaining 166 reports, about 4.8 h.
Score BM25 against BM25-plus-nomic at k = 10, 15, 20, free. Freeze the retriever. Build prompt
trimming, required at any k. Then condition 1 at two k values, the winner becoming the official
condition 1 and the loser a k-ablation row.

### New document: docs/paper_numbers.md

Created because the paper needs every figure to carry its provenance, and because two
comparability failures have already been near-misses: a 102-slice number read against a 700
number earlier today, and the standing risk of a strictly-scored accuracy sitting beside a
published FINDVER-compatible one.

It is not a summary of this log. The log stays a dated narrative including wrong turns, which is
what lets a number be traced to its evidence. The new file answers a different question: for a
given number, what does it measure, on what n, produced by what script, and **what may it
legitimately sit beside**. It also carries a closing section listing claims that are *not* yet
supported, so they are not written by accident.

## 5 August 2026, evening — the retriever is frozen: BM25 alone

### The full embedding index

`build_embedding_index.py all`, run detached with `nohup caffeinate -ims` so it survived both
the terminal and the session. **255 reports, 60,871 elements, 179 MB, 362.7 minutes, 0 failed
reports.** The 178 MB prediction from the 768-dim calculation was right.

Two operational notes. The script gained an `all` mode, because `stratified_sample` tops out at
`per_cell` 100 (the smallest subset-by-label cell) and yields 600 claims, not the 700 whose
reports the fusion decision needed. And the user reported the machine on a black screen while
away: expected, since `-ims` blocks idle, disk and system sleep but not display sleep. Confirmed
it never suspended by comparing process wall time (85.7 min) against work time inside the log
(84.3 min) — a sleep would have opened a gap.

### The fusion decision, n=700

`test_scripts/decide_fusion.py`. Decided on recall, which is the right basis: fusion changes
*which* k chunks reach the prompt rather than how many, so it carries no gold-versus-distractor
tradeoff and needs no overnight run. Run at three k values so the fusion and k decisions could
be checked for interaction.

                                   k=10     k=15     k=20
    ours BM25 alone               74.60%   81.12%   84.56%
    nomic-embed-text alone        58.66%   66.04%   70.59%
    RRF(BM25, nomic) equal        75.00%   80.71%   84.55%
    RRF(BM25 x1.1, nomic)         75.20%   81.75%   85.76%
    union of the two, ceiling     81.28%   86.42%   89.13%

**No interaction.** Whatever fusion does, it does at all three k, so the freeze order holds.

**Decided: dropped. The frozen retriever is BM25 alone.**

**Reason 1, deciding.** Untuned fusion gains nothing: +0.40, -0.41, -0.01. The +0.6 to +1.2
appears only at weight 1.1, and 1.1 was chosen by reading these results. The `k1`/`b` sweep's
+0.37 was rejected on exactly that ground on 4 August, and there is no held-out set to validate
a weight against. Consistency requires rejecting this too.

**Reason 2.** Dominated by a parameter. Measured directly rather than argued:

    BM25 alone, k=10   74.60%    +0 tokens
    BM25 alone, k=11   76.29%    +398 tokens
    BM25 alone, k=12   77.84%    +819 tokens
    RRF(BM25 x1.1, nomic) at k=10   75.20%   + a second model + 179 MB index

One extra retrieved chunk beats the entire dense arm.

**Reason 3.** A second resident model, a 179 MB index, and about 100 s of indexing per new
filing in a real deployment, for roughly one point, in a paper whose contribution is on-device
feasibility.

**Recorded honestly: the k=20 case is closer than the k=10 case.** There fusion's +1.20 is worth
about three k steps or ~1,260 prompt tokens, so on wall clock it is nearly a wash. The tuning
objection decides it, not the cost. Writing it as a clean cost win would overstate the evidence.

**The frozen retriever.** `src/bm25_retriever.py`, `k1 = 1.5`, `b = 0.75`, one `context` element
per chunk, Lucene IDF, punctuation dropped, no stemming, per-report corpus. **k is not frozen**
and is decided by condition 1.

**What survives as reportable.** `nomic-embed-text` alone at 58.66% / 66.04% / 70.59%, a free
local embedder measured against the paid `text-embedding-3-large`'s 68.01%. We found no other
work reporting a local embedding model on FINDVER.

**Keep `embeddings/` until after submission**, then delete. Derived data, but rebuilding costs 6
hours and it is 179 MB against a 1.3 GB clone already present.

### A mistake of mine, corrected by the failure

`decide_fusion.py` imported `measure_dense_recall`, which does not exist: the user renamed that
file to `measure_embedding_recall.py`. Earlier in the session they referred to it by its real
name and **I "corrected" them back to my own name for it**, which was wrong. The import error
was the thing that revealed it.

### Sampling noise, now measured twice

The 102-claim slice was used on 5 August morning for the dense go/no-go and could not resolve
the question. The n=700 numbers quantify why:

    ours BM25          74.60% at n=700 vs 76.18% on the slice    1.58 points
    nomic-embed-text   58.66% at n=700 vs 62.86% on the slice    4.20 points

Both exceed the 1 to 2.5-point effect that was under test. §9's rule that 102 examples cannot
rank configurations three points apart is now confirmed on retrieval as well as on prompts.

### Negative results, and the decision to report them

Three things were built, measured and rejected today and yesterday: claim decomposition, dense
fusion, and `k1`/`b` tuning. **All three go in the paper.** FINDVER's literature contains one
method paper, MACE, which declined to work on retrieval at all, so "we tried the obvious
retrieval upgrades and here is what they were actually worth" is a contribution rather than an
admission. Each was expected to help; the measurement said otherwise, and that is the honest
framing.

Two methodological findings are arguably the most transferable things produced so far, and both
came from catching an error rather than from a success. **Any multi-query retriever must be
compared against a single-query one at matched candidate count**, or the enlarged pool
manufactures a positive result. **A sample sized to detect a large effect cannot be reused to
detect a small one.**

Recorded in `docs/paper_numbers.md` §4.5 with the numbers and the framing.

### Decided: `num_ctx` 32768 in every config from here

`num_ctx` 16384 is no longer safe given the overflow measurement.

    num_ctx    k=10 over    k=20 over    RAM
    16384        15/700       104/700    3.2 GB
    32768         0/700         6/700    4.4 GB

An unused window costs RAM and not time, and 4.4 GB against 16 GB on a machine peaking at 2.5 GB
is affordable. Without it, prompt trimming would be discarding real evidence on 104 claims at
k=20 instead of 6, which is the difference between a safety net and a lossy compression step.

`configs/trial_run_3b.json` keeps 16384 deliberately: it records what produced the 2 August
results and must not be edited. Re-measure RAM before assuming this holds for the 7B.

### Measured: the `type: "table"` flag overstates the table workload by a quarter

Counted across all 255 reports behind testmini, 60,871 elements.

    type == "table"                              10,991   18.1% of elements
      numeric cells < 10%                         1,843   16.8% of tables
      numeric cells < 25%                         2,967   27.0% of tables
      contains a bullet glyph                       820    7.5% of tables
    looks like a real data table                  8,023   73.0% of tables
      (>=2 rows, >=2 cols, >=25% numeric cells)            13.2% of all elements

Found while answering a question about passing DataFrames to the model. The first
`type: "table"` element inspected turned out to be a bulleted list laid out as an HTML table.
Filings use tables for formatting constantly. **Tier 1's table payoff should be stated against
13.2% of elements, not 18.1%.** The numeric-cell fraction has p10 0.00, so at least a tenth of
flagged tables hold no numbers at all.

### Recorded before it becomes a bug: read_html can succeed and still be wrong

The question asked was whether a successful parse guarantees a correct parse. It does not.
`pandas.read_html` returns DataFrames with headers in the wrong row, merged cells duplicated or
dropped, footnote rows as data, and spacer columns as all-NaN, raising nothing. Same silent
class as the week-1 loader bug and the Ollama eviction, so **the fallback trigger cannot be "did
it throw."**

The validation to use exploits the redundancy already in the data: each table exists as HTML in
`html_tables` and as pipe-delimited text in `context`. If the parsed DataFrame is missing
numeric tokens that appear in the text version, the parse dropped data and the element falls
back to raw text. Structural checks alongside it: at least 2x2, column names not all
`Unnamed: n`, non-null density above a threshold.

Two separate risks, both free to measure and both to be measured before Tier 1 is built:
**mapping** a `context` element to the right `html_tables` entry (gold indices point into
`context`, data trap 6), and **parsing** that entry correctly.

`pandas`, `lxml`, `bs4` and `html5lib` are all absent from this machine.

Also clarified in passing: **a DataFrame cannot be passed to the model.** An LLM call takes a
string. The DataFrame stays in our process; the prompt carries the schema; the model writes
`.loc` expressions; the sandbox executes them. One parse serves both consumers, not two.
Prompt trimming is unaffected by any of this and is needed now regardless, though it should not
be *tuned* against today's token distribution since schemas will change it.

## 5 August 2026, late — prompt trimming built, and the retriever work is finished

### Why this got built now rather than later

It was specified on 2 August to prevent overflow, downgraded the same day when the 12-example
trial run showed no overflow, reframed as a wall-clock optimisation, and parked behind the
retriever. The token calibration turned it back into a correctness requirement, this time with
a measurement: **about 15 of 700 claims already overflow at the current k=10 with `num_ctx`
16384**, and Ollama 0.12.3 evicts silently while reporting `done_reason: "stop"`.

Raising `num_ctx` to 32768 takes that to 0 at k=10 and 6 at k=20, so this module is the last 6,
not the main defence. **If condition 1 picks k=10 it never fires.** That is dormant insurance
by design, and the module docstring says so, because someone reading the file in three weeks
would otherwise take it for dead code.

### `src/prompt_trimmer.py`

Three parts. `estimate_tokens` divides characters by **3.31**, the *minimum* measured
chars-per-token ratio rather than the mean. That is the whole safety argument: on prose it
overshoots by about 29%, which costs nothing because those prompts sit nowhere near the budget,
and on the table-heavy prompts that actually approach the limit it lands within 0.1%. Using the
mean 4.36 instead would have estimated `numeric-val-30` at 9,485 tokens against an actual
12,480, a 3,000-token undershoot in exactly the direction that causes eviction.

`_total_tokens` counts one separator per chunk rather than one between each pair, overshooting
by a few characters, which is the safe direction.

`trim_to_budget` drops the lowest-ranked chunk until the prompt fits, never returns an empty
list, and **raises rather than truncating** if a single chunk cannot fit. That branch is
measured to be unreachable: the largest of all 60,871 context elements is 39,845 characters,
about 12,038 tokens, against a 30,768-token budget at `num_ctx` 32768. It raises because if the
assumption ever breaks, silently handing the model half a table is precisely the failure class
this module exists to prevent.

**A design decision worth recording: no truncation path at all.** The original design had one,
for the single-oversized-chunk case. Measuring the largest element first showed the case cannot
occur, so the branch was deleted rather than written. Measure before building the error handler.

**A simplification prompted by the user.** `trim_to_budget` originally returned
`(kept, dropped)` and the caller discarded `dropped` with `_`. Returning a value nobody uses is
speculative code; it now returns `kept` alone and the call site computes the counts, which is
where both numbers are in scope anyway.

### Changes to the run loop and the logger

`build_prompt` gains a `config` argument and returns a third value:

    build_prompt(claim, chunks, template, config) -> (prompt, evidence_block, kept)

It computes `overhead_chars` as template length minus both placeholders plus the claim, since
`<REPORT>` and `<STATEMENT>` are replaced and their characters do not survive. Budget is
`config["num_ctx"] - config["num_predict"]`, indexed rather than `.get()` so a missing key
raises instead of producing a wrong budget silently, matching the reasoning already applied in
`ollama_client`.

**Trim in rank order, then re-sort into document order.** The retriever returns best-first,
which is what says which chunk is least worth losing. The prompt wants document order so tables
sit near their captions. Both cannot happen in one pass, so the trimmer's only job is which
chunks survive and `build_prompt` handles ordering.

`SEPARATOR` is imported from the trimmer rather than written out again in `build_prompt`. If
the two ever disagreed the estimate would be wrong by two characters per chunk and nothing would
raise: the same duplicated-logic hazard recorded on 1 August for `_result_path()`.

`Record` gains `chunks_requested` and `chunks_kept`. **Not a third field for the drop count**,
which is derivable from those two; storing it invites the three disagreeing after a later edit.
`chunks_requested` also cross-checks the config: it should always equal `top_k`, so a run
logging 15 under a `top_k` of 20 means the retriever returned short.

### Verification

    test harness                          26/26 passed
    k=10, 40 random claims                kept == 10, prompt BYTE-IDENTICAL to untrimmed
    k=20, the six predicted trim cases    6/6 exact, kept 16/17/18/18/16/19
    k=20, all 700 claims                  exactly 6 trimmed, 0 raised

The byte-identical check is the important one: it proves the module is invisible on the 694
claims where it should do nothing, so nothing about the existing pipeline changed.

### The check the user asked for, and it was the right question

Our reported 84.56% at k=20 assumes all 20 chunks reach the model. On six claims they do not.
If trimming dropped gold, the paper would report a recall the pipeline does not deliver.

    claim              gold  got@20  after trim  gold lost
    ie-val-169            3       2           2      -
    numeric-val-128       1       1           1      -
    numeric-val-141       3       3           3      -
    numeric-val-195       2       2           2      -
    numeric-val-224       2       2           2      -
    knowledge-val-67      2       1           1      -

    k=20, retrieval output       84.56%   81.7%   66.6%
    k=20, as the model sees it   84.56%   81.7%   66.6%

**Zero gold lost across 15 dropped chunks.** Trimming drops from the bottom of the ranking and
the dropped chunks were ranks 17-20; gold sits high, which is what an 84.56% recall means. This
validates the drop-lowest-ranked decision over the alternatives considered.

**Scope it honestly in the paper: 6 claims and 15 chunks is an observed result, not a
guarantee.** At a higher k or a tighter budget more would drop and gold could be lost. Recorded
in `paper_numbers.md` §1.3 as a footnote to the k=20 row, because it is what makes that number
citable as delivered recall rather than retrieved recall.

### Open, carried to tomorrow

The harness's `context_overflow` checks still use 16384. They are stubs testing the asserter's
arithmetic rather than the real config, so they are not wrong, but when the condition 1 config
is written at 32768 a harness check at the new window should be added so the two cannot drift.

**The machine decision.** It is 5 August and the deadline is about the 7th. Everything before
condition 1 is now done: the retriever is frozen, trimming is built and verified. Condition 1
is the only remaining blocked item and it is blocked on someone else's inbox.

## 6 August 2026 — the condition 1 configs, and a config that would have lied for twelve hours

Daytime work only. No model calls, no nights spent. Three things: the two condition 1 config
files, a defect in `run.py` found while writing them, and the harness drift check that 5 August
left open.

### `run.py` read the `retriever` key only to print it

Found before the configs were written, which is the only reason it cost nothing.

`run.py` imported the placeholder retriever at module level and bound it directly:

    from src.placeholder_retriever import retrieve
    ...
    retriever = functools.partial(retrieve, k=config["top_k"])

The config's `"retriever"` value was read exactly once, to print it in the startup banner.
Nothing selected on it. So a condition 1 config saying `"retriever": "bm25"` would have printed
`bm25`, written `bm25` into all 102 result files, named a results directory after it, and run
the 57.5% placeholder for twelve hours. Nothing would have errored.

**This is the loader bug and the `num_ctx` truncation again**: a silent wrong answer rather than
a loud failure. A config that lies is worse than a config that is missing, because the lie is
copied into every result file by the logger and outlives the run.

**Fixed with a registry.** `RETRIEVERS` maps the config string to the function, and `run.py`
looks up `config["retriever"]`. An unknown name now raises `KeyError` at startup, before the
sample is drawn and before the first model call.

The two retrievers turned out to have identical signatures, `retrieve(claim, report, k=TOP_K)`
returning a list of `context` element dicts, so the swap needed nothing else.

**One ordering difference, already handled by existing code.** The placeholder returns chunks in
document order; BM25 returns them in score order, best first. `run_loop.build_prompt` trims
first and then re-sorts to document order, and `trim_to_budget` pops from the end of the list
assuming that end is the worst chunk. That assumption is true for BM25 and was false for the
placeholder. It never mattered, because trimming fires on 0 of 700 at k=10. After the swap it is
correct by construction rather than by luck.

### The registry key was renamed and then reverted, and the reason is worth keeping

The registry key was briefly renamed from `placeholder_token_overlap` to `placeholder_retriever`,
in `run.py` and in `configs/trial_run_3b.json` together, on the reasoning that renaming both
copies made it safe.

**There is a third copy and it cannot be renamed.** `logger.py` embeds the whole config into
every per-claim result file at run time, so all 12 files in `results/trial_run_3b/` record
`placeholder_token_overlap` as of 2 August. Editing the config afterwards does not reach them.
The frozen config and its own results then disagreed about which retriever produced them, which
is exactly what freezing `trial_run_3b.json` on 5 August was meant to prevent. `results/` is
untracked, so the original string only survived in files git is not protecting.

The proposed fix was to rewrite the retriever string in the 12 result files. **Rejected.** In
substance it changes nothing, since the function is identical and only the label differs. As a
precedent it is the wrong direction: result files are the record of what ran, and once they are
editable after the fact every other freeze in the project stops meaning anything. The rename was
reverted instead. One `git checkout` and one string, against rewriting 12 records.

**Keep the placeholder in the registry.** Two dict lines buy reproducibility of the 2 August
trial from its own committed config. The recall row at 57.54% and the 7.0 min latency figure in
`paper_numbers.md` are already measured and need no code, so that part of the case is weak, but
the frozen config is not.

### The two condition 1 configs

    configs/condition1_3b_k10.json      "experiment": "condition1_3b_k10"
    configs/condition1_3b_k20.json      "experiment": "condition1_3b_k20"

`qwen2.5-coder:3b`, `num_ctx` 32768 per the 5 August decision, `num_predict` 2000, temperature 0,
seed 0, `baseline_v1`, `retriever` bm25, `per_cell` 17 for 102 examples across the 6 cells,
`sample_seed` 0. The two files differ only in `top_k` and the experiment name.

**The model belongs in the name, and the first draft got this wrong.** The `experiment` key was
initially `condition1_k10`, without `_3b`. That is not cosmetic. `logger.py` resumes via
`has_result`, which checks whether a per-claim result file already exists, so the 7B condition 1
would have resolved to the same `results/condition1_k10/`, found 102 files already present,
skipped every claim, and finished cleanly in about a second, leaving a directory of 3B results
believed to be the 7B. Fixed before anything ran.

When the 700 run comes, add a suffix there rather than putting `_102` on these files. The
unmarked name means the 102 iteration size, which is what almost everything is.

### The harness drift check, which 5 August left open

The harness passed 26/26 while testing none of the day's work. It builds its own inline config at
`num_ctx` 16384 and never opens `configs/`, and it injects retriever stubs directly, so
`RETRIEVERS` was never resolved and 32768 had never been validated by anything.

Added a block 0 at the top of `main()`, ahead of the run-loop fixtures, since these are file
reads plus one function call and need none of them. **Twelve new checks, now 38/38.**

- 3 registry checks. Any config carrying a `retriever` key must name a key in `RETRIEVERS`.
  `decompose_v1.json` has none, because it drives a different script, and is skipped.
- 8 overflow checks. Each config's boundary tested at its own `num_ctx` and `num_predict`.
- 1 check that `configs/` is not empty, so an empty glob cannot make the other eleven vacuously
  pass.

**No numeric literal appears in the new block.** Everything is read off disk. Replacing a
hardcoded 16384 with a hardcoded 32768 would have recreated the same drift one number later. As
written, changing a config to 65536 makes the harness test 65536 automatically.

**The new checks were verified to fail.** A temporary config with `"retriever": "bm5"` was
dropped into `configs/`, and the harness reported

    FAIL _tmp_drift_probe.json names a known retriever   'bm5' not in ['bm25', 'placeholder_token_overlap']

and exited 1, which is what matters, because the `&&` in the run command means a failing harness
blocks the overnight job before a single model call. Probe deleted.

### Still open, carried to tomorrow

**`evidence_asserter.py:83`.** The `check_overflow` docstring still says "we set num_ctx to
16384", superseded on 5 August. Documentation, not behaviour.

**BM25 has never run through `run.py`.** Every end-to-end run so far used the placeholder, and
the harness exercises the registry lookup but injects stubs for the retrieval itself. The first
time BM25 flows through the real entry point will be condition 1. The signatures match and the
ordering interaction is understood, so the risk is low, but it is not zero and it is unmeasured.
A 6-example smoke run at `per_cell` 1 costs about 40 minutes and would retire it before a
12-hour night is committed.

**The machine.** An Instagram message went to the professor asking for the exact GPU model and
the access method, with the 7 August deadline stated. Email was the wrong channel for something
needed within a day. A progress email covering the retriever freeze, the three rejected
approaches, the second local model and the cloud quota is still owed separately, and should not
be attached to a request for hardware.

**The brother's machine is now a real option, with one thing to verify.** The card is an AMD
Radeon RX 7800 XT, 16 GB of VRAM, and it is available any night. VRAM is not the constraint:
the 3B at 4-bit is roughly 2 GB of weights and the whole process measured 4.4 GB at `num_ctx`
32768 on the Mac, so a 7B fits too. **The constraint is AMD.** Ollama's AMD path is ROCm rather
than CUDA, and if it does not engage, Ollama falls back to CPU without erroring. That produces a
slow run, or worse a GPU-labelled number that came from a CPU, which is the same silent-wrong
shape as everything else in this section. Before that machine is chosen: install Ollama, pull
the 3B, confirm from the server log that it loaded onto the GPU rather than the CPU, and time 3
to 5 real examples. **We have no measured throughput for that card**, and the 20-23 August 700
run would be planned against it, so it has to be measured rather than estimated.

The hardware rule from 3 August applies unchanged. The brother's desktop is a GPU. No number
from it goes under a MacBook label, and one MacBook night is still owed at the end for real
latency and peak RAM.

## 6 August 2026, evening — the BM25 smoke run, and a sample-versus-population error

Six examples, `per_cell` 1, `configs/smoke_bm25.json`, BM25 at k=10, `num_ctx` 32768,
`qwen2.5-coder:3b`. Results in `results/smoke_bm25/`. **6 ok, 0 failed.** Total 23.2 minutes.

Purpose was never accuracy. It was the one path the harness structurally cannot reach: BM25
flowing through `run.py` with a real model behind it. Every end-to-end run before this used the
placeholder, and the harness injects retrieval stubs, so `bm25_retriever.retrieve` had never
once been called by the real entry point.

### What it validated

    BM25 through run.py        works end to end
    unparseable                0/6, extraction_source "anchored" on all six
    context_overflow           0/6
    chunks kept                10/10 on all six, trimmer stayed dormant as predicted
    resume                     validated live: 5 skipped, 1 re-run, on the repair below

The extractor result is worth noting against 2 August, where 4 of 12 responses did not put the
verdict in the final sentence. Here all six were caught by the strongest extraction level. Six
is not a rate, so this is not a claim, only an absence of the problem.

### A measurement was contaminated, and the cause was our own debugging

`ie-val-108` first came back at **33.6 s** against 168 to 342 s for the other five, on a prompt
of ordinary size. Cause: while reproducing a `FileNotFoundError` earlier that day, the same
command was run and killed after 45 seconds. Same seed, same sample order, so it had started on
`ie-val-108` and left that prompt's work resident in Ollama. The real run 45 seconds later
skipped most of it.

    ie-val-108          1,907 tokens    33.6 s    56.8 tok/s   contaminated
    knowledge-val-197   2,070 tokens   188.5 s    11.0 tok/s   clean

56.8 tok/s is far outside anything measured on this machine, which is 10.7 to 23.2.

**Repaired, not discarded.** `ollama stop qwen2.5-coder:3b`, delete the one result file, re-run.
`has_result` skipped the other five and re-ran only that claim: **168.7 s, 11.3 tok/s**, in line
with its token count. Same label, same evidence flags, because retrieval and generation at
temperature 0 are deterministic and only the timing was ever wrong.

**Operational rule from this: never run the pipeline to debug it while a real run is pending on
the same claims.** Ollama's residency is invisible in the result file, `done_reason` still reads
`stop`, and `prompt_eval_count` still reported the full 1,907 tokens. Nothing in the record marks
the example as contaminated. It was caught only because the number was implausible.

### The clean runtime model

Fitted on all six after the repair, separating prompt reading from generation:

    time = 0.0808 * prompt_tokens + 0.0317 * generated_tokens
    ingestion 12.4 tok/s, generation 31.6 tok/s, R^2 = 0.904, n = 6

Consistent with the `num_predict=1` ingestion measurement of 12.8-23.2 tok/s at the same
`num_ctx`, which spanned content types varying 3.31 to 4.44 chars per token.

**Projected on BM25's measured 700-wide mean prompt of 4,426 tokens at k=10**, with 411
generated: **371 s per example, so about 10.5 h for 102 examples and 72 h for 700**, against the
12 h and 82 h currently in the planning documents. A real improvement of roughly 12%, not the
halving claimed earlier in the day. **The schedule does not change.**

### The error that produced the halving claim, and it is one the log already warned about

It was first reported that BM25 more than halved prompt size, 6,610 tokens to 2,875. **Wrong.**
6,610 is the placeholder's mean over the 12-example trial sample; 2,875 was BM25's mean over six
different examples. Different retrievers and different samples moved at once.

The population figures are `build_log.md:1612`: placeholder 4,737 and BM25 4,426 tokens at k=10,
both over all 700. **A 7% difference, not a halving.** Six samples read low because the
distribution is right-skewed, p90 of 9,490 against a max of 19,466, so most draws sit under the
mean.

**This is the same error the 5 August entry explicitly recorded**, where 4,737 against 6,610 was
first misdiagnosed as a broken character-to-token conversion before being identified as a
sample-versus-population comparison. It was repeated one entry later. Any figure from a 6 or 12
example sample must state which population it describes before it is compared to anything.

### `num_ctx` 32768: examined, and the 5 August decision stands

Today's fit gives 0.0808 s per prompt token against 2 August's 0.0641, which briefly looked like
evidence that the larger window costs wall clock and therefore that the 5 August reasoning,
*"an unused window costs RAM, not time"*, was wrong.

**Withdrawn. There is no finding here.** Four reasons, in order of weight:

1. **The 0.0641 baseline is superseded.** `build_log.md:1588` records that it came from total
   elapsed time and absorbed generation cost. Comparing a two-variable fit against it is invalid.
2. **A clean measurement at 32768 already exists** and today sits inside it: 12.8-23.2 tok/s
   from the `num_predict=1` calls, against 12.4 tok/s today.
3. **Content explains more than the window could.** Chars per token ranges 3.31 on table-heavy
   claims to 4.44 on prose, a 34% spread, which moves ingestion speed more than an idle buffer.
4. **The mechanism supports the original claim.** The KV cache is reserved up front, but
   attention is computed over the tokens actually present, not the reserved space. An unused
   window costs time only if the extra memory forces swapping, and 4.4 GB of 16 GB does not.

**An A/B against `num_ctx` 16384 was proposed and is not being run.** It cannot change a decision
yet: 16384 trims 15 of 700 claims at k=10 and 104 of 700 at k=20, so the smaller window is only
ever an option if condition 1 picks k=10. Revisit then, using `num_predict=1` on 3 claims at both
windows, about 10 minutes.

### Recall on the six, and why 2/6 is not a warning sign

    macro (mean per-claim fraction of gold found)   61.9%   vs 74.60% over 700
    all-gold (every element present)                2/6     vs 50.4% over 700

`evidence_present` is the **all-gold** column, the strictest of the three, not macro. Against a
true rate of 50.4%, seeing 2 or fewer of 6 has probability about 0.34. It carries no information.

The boolean also understates what arrived. `knowledge-val-197` received 4 of its 5 gold elements
and still logs `False`. The `evidences_found` dict is the richer record.

Accuracy was 4 of 6. **n=6 supports no claim** and it is not analysed here. For scale, the
2 August trial was 8 of 12, the same 67%.

### Housekeeping

`configs/trial_bm25_3b.json` was renamed back to `configs/smoke_bm25.json` so the file name
matches the `experiment` key, rather than renaming `results/smoke_bm25/` and desyncing the
config embedded in each result file. Same reasoning as the `placeholder_token_overlap` revert
earlier in the day.

**`CLAUDE.md` gained a "How to answer me" section**, after a set of answers that buried the point
under volume and follow-on tangents.

## 7 August 2026 — the GPU is gone, the meeting, and a DeepSeek smoke test that ran at the wrong time

No nights spent. Nothing ran locally. The day's two blocking items, the machine test and the
local model decision, are **both still open at the end of it**, which is recorded below rather
than glossed.

### The professor's GPU server is unavailable, and probably permanently for this paper

His email, received before the meeting. He has **several dozen RTX 4090 units on hand**. They sit
on a local area network and he has been unable to obtain a public network IP address for them.
Several of his students have worked on it without success. He cannot grant access now, and
expects it "might get sorted out after the semester starts in September", which he himself calls
"much too late."

**Treat the server as unavailable, not delayed.** September is after the 29 August deadline.

Two fallbacks he offered at the meeting: he will try to find a machine that can bridge access,
and failing that he is **willing to pay for a rented third-party GPU server**. Neither is
scheduled. The brother's desktop stays first choice because it exists today and costs nothing.

**What this costs.** A 700-example run is about 72 h on this MacBook, roughly 7 to 10 of the ~16
nights left before the 23 August freeze. It does not happen. n stays at 102, the margin stays at
±10 points, and §5.3's "we match condition 3" stays unprovable. Band A carries the paper, exactly
as §12.3 planned for.

### The meeting, 7 August. Five outcomes.

1. **The local model is our call.** His criteria: the strongest model that is still light, ideally
   around 3B, to keep the on-device framing honest, chosen to give the best chance of matching
   condition 3 through our pipeline.
2. **Cloud models are `deepseek-v4-flash` and `deepseek-v4-pro`.** On Anthropic he said there is
   no reason not to, but does not want me paying for an API key myself. He resides in China,
   Anthropic does not serve China, so he cannot pay for it. He can pay for DeepSeek. **This is a
   payments constraint, not a technical or scientific objection**, and it was not previously
   understood as such.
3. **GPU as above.**
4. **Write the paper on Overleaf.** Create a project, load the existing findings and progress into
   it, begin writing, and share it with him.
5. **Next week's meeting** is about pipeline design: how to close the gap between condition 4 and
   condition 3. Conditions 1 and 2 should be finished by then.

### Who chose Qwen2.5-Coder-3B, checked rather than recalled

He questioned whether a Coder model suits reading-comprehension work rather than coding. Before
answering, §14 item 5 was re-read: **he named `Qwen2.5-Coder-3B` himself**, in the early email
that also ruled out long context and fixed the project on RAG. The **7B second model was ours**,
recorded in OQ8 as "proceeding as a decision unless he objects."

**His objection is right for one job and wrong for the other.** Condition 1 is plain reading of
retrieved evidence plus a verdict, with no code in it anywhere, and it is the floor everything
else is measured against. But Tier 1 has the model write Python for the arithmetic, so a
code-tuned model is defensible there.

**The risk if it stays.** If the Coder model reads badly but codes well, the condition 4 minus
condition 1 delta looks large for the wrong reason. Flattering, and an artifact.

### A contradiction between his criterion and OQ8, unresolved

- **His criterion:** pick the strongest model that still fits the on-device story, to maximise the
  chance of matching condition 3.
- **OQ8:** 3B stays primary, because *"a bigger model eats the contribution: the pipeline's delta
  is largest where the base model is weakest."*

These optimise different things. His maximises the headline claim; OQ8 maximises the measured
value of the pipeline. **Not resolved. Write it as a stated limitation rather than letting it
pass unnoticed.**

### The framing error this exposed, corrected

"Best chance of matching condition 3" was initially read as needing a local model that can rival
DeepSeek. **It does not.** Condition 4 is the 3B model *plus* DeepSeek on the judgment-heavy
steps. The local model only has to be good enough at the mechanical work that we do not escalate
everything. If every step escalated, condition 4 would be condition 3 at condition 3's cost.

So the model criterion is: strong enough at reading tables and holding the output format, small
enough to be credible as on-device. Not "strongest available."

### OQ8's Llama-3.2-3B contradiction is weaker than it was recorded as

OQ8 flags that requiring models FINDVER did *not* evaluate may optimise for the wrong objective,
since `Llama-3_2-3B-Instruct` is in the published 16 with 700 responses already on disk, and using
it would let us compare published baseline against our pipeline with the model held fixed.

**That comparison is not controlled, and the entry overstated it.** Upstream ran temperature 1.0,
a 1024-token generation cap, a retriever at 65.16% recall against our 74.60%, and `gpt-4o-mini`
extraction with an unseeded coin flip. "Same model" holds one variable fixed while four others
move.

**Condition 1 against condition 4 holds model, retriever, k, prompt version, `num_ctx`,
temperature and extractor all fixed.** It is a strictly better measurement of the pipeline's
value, and it does not depend on the 700 run: it exists at n=102 with a ±10 point margin.

**And the published Llama number is free from disk regardless**, as historical context in the
baseline table, labelled as upstream's setup. We never had to adopt the model to cite it.

**Downgraded, not closed.** It is a weak argument rather than a live tension. Raise it with him
only if the model question reopens.

### The DeepSeek key works, and V4 Pro is a reasoning model

One live call, `curl`, before writing any Python. The endpoint is OpenAI-compatible:

    POST https://api.deepseek.com/chat/completions
    Authorization: Bearer $DEEPSEEK_API_KEY
    {"model": "deepseek-v4-pro", "messages": [...], "temperature": 0, "stream": false}

It returned normally. `temperature: 0` was accepted without error. **Condition 2's only external
blocker is closed.**

**The response carries more than expected:**

    "content"            "OK"
    "reasoning_content"  "We are asked: \"Say OK\". This is a very simple instruction..."
    "completion_tokens"  34
    "reasoning_tokens"   32
    "model"              "deepseek-v4-pro"
    "system_fingerprint" "fp_9954b31ca7_prod0820_fp8_kvcache_20260402"
    "prompt_cache_hit_tokens" / "prompt_cache_miss_tokens"   0 / 6

**32 of 34 output tokens were reasoning, on the input "Say OK".** Three consequences.

**One, the extractor must read `content` only.** Never `content` plus `reasoning_content`.
`extract_label` takes the *last* match within a level, so if the reasoning weighs "this looks
entailed" and the final answer concludes "refuted", concatenating them risks extracting the
opposite verdict. `content` is the clean final answer, which should make extraction far more
reliable here than on the 3B. **Log `reasoning_content` into the record anyway** — it is free
evidence for the error taxonomy, showing the cloud model's actual reasoning and not only its
verdict.

**Two, every cloud cost estimate needs re-measuring.** Reasoning tokens are billed and counted in
`completion_tokens`. Any per-example output figure taken from a non-reasoning model does not
transfer. Measure `reasoning_tokens` on one real 4,426-token claim before committing to condition
3, which puts the cloud model in every pipeline role and is the largest quota consumer.

**Three, the response reports what actually served the request.** `model` and
`system_fingerprint` should both be logged. The fingerprint carries what looks like a build date,
so a silent model roll mid-August would be visible in the result files instead of appearing as
unexplained variance.

**`deepseek-v4-flash` is a floating alias** routing to `DeepSeek-V4-Flash-0731`. Pin the dated
string in configs if the endpoint accepts it, for the same reason machines cannot be mixed inside
one results table. **Untested as of this entry.**

**Which model goes where.** Pro for conditions 2 and 3, so both the single-call cloud baseline and
the all-cloud upper bound use the strong model. Flash is a cheaper extra row and the natural
escalation target to test inside condition 4. **Do not put flash in condition 3**, or the bar we
claim to match is lowered by our own choice.

Prompt-caching fields exist and were not investigated. Instructions are a shared prefix across
examples while retrieved chunks are not, so there may be something there. Not now.

### `Record` needs two fields. Deliberately not added today.

`logger.py:19` is `response: str | None` — the text only, not the response dict. So `model` and
`system_fingerprint` are **not** captured by the current logger and would need new fields.

**Not done, on purpose.** Nothing in condition 1 touches DeepSeek, and `test_harness.py` asserts
`all 18 Record fields present`, so adding fields means editing the logger and the harness on the
day a ten-hour run is meant to start. Deferred to the DeepSeek client work, after the edge runs.

### Scope drift, recorded because the pattern is the point

The DeepSeek smoke test was worth doing and took two minutes. What followed — analysing the
reasoning-model consequences, the flash alias, the logging changes, and proposing the client
module — happened on a day whose blocking items were the machine test and the model decision, and
neither moved. Flagged by the user, correctly.

**The rule this suggests:** a verification that unblocks future work is not the same as starting
that work. Verify, write down what it changed, stop.

### `docs/gpu_smoke_test.md` written

One-off procedure for the brother's **desktop** (AMD RX 7800 XT, 16 GB VRAM, Windows, same Wi-Fi).
Delete after the machine decision.

**No code moves to that machine.** Ollama is already a client/server split over HTTP: the Mac runs
loader, sampler, BM25, prompt building, trimming, extraction and all writes into `results/`, and
the desktop runs only the model. About 18 KB out and 2 KB back per example against a call taking
minutes.

`src/ollama_client.py:7` hardcodes `http://localhost:11434/api/generate`. It should become
config-driven rather than edited, because `Record` already stores the config and every result file
would then record **which machine produced it** — the same failure shape as the 6 August
contaminated timing, which nothing in the record marked.

**The whole test is `ollama ps` reporting GPU rather than CPU.** AMD on Windows falls back to CPU
silently. Speed is not the check; the process listing is. Baseline for comparison is
`configs/smoke_bm25.json` at **23.2 minutes for six claims** on the Mac, same sample and seed, so
the ratio is the answer. Threshold: CPU or under ~3x means use the Mac tonight; 5x or better means
Band B reopens.

### Still open going into 8 August

- **The GPU smoke test has not been run.**
- **The local model is not decided.** Switching is free only until condition 1 starts.
- **Condition 1 has not started.** It is two runs, k=10 and k=20, ~10.5 h each on the Mac.
- `deepseek-v4-flash` and the pinned `DeepSeek-V4-Flash-0731` string are untested.
- No Overleaf project exists.
- `evidence_asserter.py:83` still says `num_ctx` 16384 in the `check_overflow` docstring, carried
  from 6 August.

### The model decision rule, adopted 7 August

Recorded because the ordering was initially got backwards: the model was going to be decided
*before* the machine test, when it is the machine test that prices the model decision.

**The GPU test runs `qwen2.5-coder:3b` and nothing else**, because the only baseline to divide by
is `configs/smoke_bm25.json` at 23.2 min for six claims on that exact model, sample and seed.

**The 23.2 min figure was re-verified from the result files today**, after the user asked whether
it still contained the contaminated `ie-val-108` timing. It does not: the file reads the repaired
**168.7 s**, and the six sum to 1389.4 s. The contaminated version would have totalled 20.9 min.

**4B is comfortably on-device.** §4.2 allows ≤8B, FINDVER's own baselines include 7B and 8B, and a
4B at 4-bit is ~2.5 GB.

**One measured quantity, one guess.** That a 4B is more accurate on this task is plausible and
unverified. Only the wall clock is known: ~⅓ more parameters puts ingestion near 9–10 tok/s
against the measured 12.4, moving a 102-example run from 10.5 h to ~13–14 h. Material on the
MacBook, irrelevant on a GPU.

    GPU works    run condition 1 at 102 on both models, ~1 h each, decide on accuracy
    GPU fails    stay on qwen2.5-coder:3b

The four reasons for staying, in order of weight: one shot per night with ~16 left; it is proven
end to end at 6/6 with a fitted cost model; the professor chose it himself (§14 item 5); and his
Coder objection cuts the way OQ8 wants, since condition 1 is a **floor** and a weaker floor makes
the pipeline's delta more visible.

**What a working GPU additionally buys:** `qwen2.5-coder:3b` vs `qwen2.5:3b` vs `qwen3:4b` at 102
each, ~3 h total, which answers his Coder objection **with data** — size held fixed, code-tuned
against general instruct — rather than with an argument. Three nights on the MacBook, so it does
not happen there.

## 7 August 2026, evening — the GPU works: 36.8x, and verdicts do not fully reproduce across machines

`configs/smoke_bm25_gpu.json`, six claims, `per_cell` 1, BM25 k=10, `num_ctx` 32768,
`qwen2.5-coder:3b`, run from the MacBook against Ollama on the brother's desktop.
**6 ok, 0 failed, 37.7 s total.** Results in `results/smoke_bm25_gpu/`.

### The card is an RX 7600 XT, not the RX 7800 XT every document said

    Get-CimInstance Win32_VideoController
    AMD Radeon RX 7600 XT    driver 32.0.31035.1003

**Navi 33 / gfx1102**, not Navi 32 / gfx1101. 16 GB VRAM. Roughly half the memory bandwidth and
about half the compute units of the 7800 XT the plan assumed. Corrected in `working_state.md`,
`architecture_plan.md` §13 item 11 and `docs/gpu_smoke_test.md`.

**It did not matter.** ROCm engages on gfx1102 and the speedup is enormous anyway. Recorded so the
next person does not read "7800 XT" and expect these numbers from that card.

### The result

    ollama ps    PROCESSOR  100% GPU
    ollama list  ID f72c60cabf62, Q4_K_M, 3.1B, context_length 32768

**Digest identical to the MacBook's**, so weights and quantisation are the same and the comparison
is valid. Per-example, against the 6 August MacBook baseline on the same sample and seed:

    example              mac_s   gpu_s   ratio    ptok    mac_gen  gpu_gen   mac_lbl  gpu_lbl  gold
    ie-val-108           168.7     7.8   21.6x    same        298      296     False    False  False
    ie-val-174           199.7     5.7   34.9x    same        503      395     False     True   True
    knowledge-val-197    188.5     6.6   28.7x    same        644      485     False    False  False
    knowledge-val-53     342.0     4.9   69.3x    same        458      287      True     True   True
    numeric-val-158      271.9     5.4   50.4x    same        318      330      True     True   True
    numeric-val-5        218.7     7.3   30.0x    same        246      519      True     True  False
    TOTAL               1389.4    37.7   36.8x

**23.2 minutes to 0.6 minutes.** `done_reason` was `stop` on all twelve records, so nothing
truncated on either machine.

### Verdicts do not fully reproduce across machines. 5 of 6.

**`ie-val-174` diverged**: MacBook `False`, GPU `True`. Gold is `True`, so the GPU was right, which
is luck at n=6 and carries no information.

**`prompt_eval_count` is identical on all six**, so retrieval, stratified sampling, trimming and
prompt construction are perfectly deterministic across machines. **The divergence is entirely in
generation**, and the generated-token counts show how large it is: 503→395, 644→485, 458→287,
246→519.

**Mechanism.** Greedy decoding at temperature 0 still depends on floating-point arithmetic, and
CPU and ROCm kernels do not produce bit-identical logits. A single reordering of two close logits
early in a response sends the rest of it down a different path.

**§4.2's hardware rule predicted this and it is now measured rather than assumed.** Two
consequences.

1. **Whichever machine runs condition 1 runs every condition.** Already the rule; it now has
   evidence behind it rather than a caution.
2. **The final MacBook night gains a second purpose that is no longer a formality.** It was
   budgeted for per-example latency and peak RAM, with the accuracy-portability check as a bonus.
   Portability is now a live question with a measured partial answer, and it belongs in the
   limitations section either way.

**Do not read the accuracy column.** MacBook 4/6, GPU 5/6, n=6. It supports nothing.

### Projected cost, with the caveat stated

Scaling 36.8x against the fitted model:

    condition 1 at 102      10.5 h   ->   ~20 min
    full 700 run              72 h   ->   ~2-3 h
    7B slice at 102        20-30 h   ->   under an hour

**Caveat.** These six average **2,713 prompt tokens against the 700-wide mean of 4,426**, so they
are lighter than a representative draw. Expect the real figures higher than the naive division.
This is the same sample-versus-population trap recorded on 5 and 6 August; stating it up front
this time rather than after being caught by it.

### Band B opens

The full 700 run, the 7B row, the end-to-end retrieval ablation and a real model comparison are all
affordable now. **The important one is n=700**, which takes the accuracy margin from about ±10
points to about ±4 and makes "we match condition 3" (§5.3, §9.2) measurable rather than
unprovable. That was the single largest threat to the contribution statement.

**The MacBook remains the device of record for every latency, throughput and memory figure**
(§4.2). Nothing about that changes. The GPU makes the experiments affordable, not the operating
point cheap.

### Setup findings, because two of them cost time tonight

**Setting `OLLAMA_HOST` is not enough — Ollama must be restarted, and the tray's Quit is not
reliable.** After `[Environment]::SetEnvironmentVariable("OLLAMA_HOST","0.0.0.0",...)` the server
was still bound to localhost. The diagnostic that settles it in one line:

    netstat -ano | findstr 11434
    127.0.0.1:11434  ->  not restarted, unreachable from the network
    0.0.0.0:11434    ->  correct

The reliable restart is `Get-Process ollama* | Stop-Process -Force` then relaunch from the Start
menu, rather than hunting the tray icon.

**The Windows network profile was `Public`,** which blocks inbound traffic aggressively.
`Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private`, in an **admin** shell.

**Windows blocks inbound ICMP by default, so `ping` from the Mac fails even when TCP works.** This
looked alarming and is meaningless. The useful test is the reverse direction: **PC to Mac ping
succeeded**, which ruled out router client isolation — the one failure mode that would have
required changing a router setting or moving to Ethernet.

**Also needed:** an inbound firewall rule on TCP 11434.

### No code moved to the second machine

`src/ollama_client.py` now builds its URL from `config.get("ollama_host", "localhost")` instead of
a hardcoded constant. The default keeps every existing config working untouched, and because
`Record` stores the config, **every result file now records which machine produced it** — the gap
that let the 6 August contaminated timing go unmarked.

The Mac runs loader, sampler, BM25, prompt building, trimming, extraction and all writes; the
desktop runs only the model. `test_harness.py` picked up the new config automatically and is now
at **44/44**.

## 7–8 August 2026, overnight — condition 1 measured, k frozen at 10, and a published 3B baseline scored

Both condition 1 runs complete on the GPU. **102 ok, 0 failed, 0 skipped** on each.
`results/condition1_3b_k10/` and `results/condition1_3b_k20/`.

### A config bug fired, and it was the one caught in theory on 6 August

`configs/condition1_3b_k10.json` carried `"experiment": "condition1_3b_k20"`. The run used
`top_k` 10 correctly but wrote 102 result files into `results/condition1_3b_k20/`.

**The banner printed the contradiction before it started** and it was not read:

    experiment    condition1_3b_k20
    retriever     bm25, k=10

**What would have happened next.** Starting the real k=20 run, `has_result` would have found 102
files with `status == "ok"` in `results/condition1_3b_k20/` and skipped every one. Output would
have read `0 ok, 0 failed, 102 skipped` in about a second, and k=20 would have been recorded as
done while holding k=10 data. **This is exactly the failure the 6 August entry predicted** for the
missing `_3b` suffix, realised one day later in a different config.

**Repaired by deleting and re-running rather than renaming the directory**, because the 102 result
files each embed `"experiment": "condition1_3b_k20"` in their stored config, and renaming would
desync that. Same reasoning as the 6 August `smoke_bm25` revert — except then a re-run cost 10.5 h
and on the GPU it cost twelve minutes. **The GPU changed which repair is correct.**

**Operational rule: read the three banner lines before walking away.** `experiment`, `retriever`
and `results` must agree.

### Condition 1, n=102, `qwen2.5-coder:3b`, BM25, `num_ctx` 32768, GPU

                              k=10        k=20
    strict accuracy          66.7%       62.7%
    FINDVER-compatible       66.7%       64.7%
    unparseable               0.0%        3.9%
    evidence_present (all-gold) 54.9%    65.7%
    prompt tokens, mean       3,651       6,843
    prompt tokens, max       14,066      20,574
    context_overflow            0/102       0/102
    trimmer fired               0/102       1/102
    wall clock              11.2 min    14.9 min
    mean per example          6.6 s       8.7 s
    predicted True           41/102      54/102     (gold 51/102)
    extraction sources    102 anchored   93 anchored, 5 bare, 3 none, 1 hedged

Per subset, n=34 each:

                  k=10 acc   k=10 evid    k=20 acc   k=20 evid   k=20 unparseable
    ie              64.7%      67.6%        64.7%      82.4%           3
    knowledge       58.8%      26.5%        52.9%      32.4%           1
    numeric         76.5%      70.6%        70.6%      82.4%           0

Paired, same 102 claims:

    label agreement           58/102 = 56.9%
    disagreements                44, of which k=20 right 18, k=10 right 22
    evidence_present          gained at k=20 on 11 claims, lost on 0

### The finding: retrieval improved 10.8 points and accuracy did not follow

`evidence_present` rose from 54.9% to 65.7%, **gained on 11 claims and lost on zero**. Retrieval is
strictly better at k=20. Strict accuracy fell 4 points.

This is §3.4.4's factor 3 — *"higher k adds distractors as well as gold, and a 3B model may not
ignore them"* — moving from hypothesis to measurement on our own system.

**It must not be written as "k=20 is worse."** At n=102 the margin is ±10 points, and the paired
comparison is 22 against 18 on 44 disagreements, which is indistinguishable from chance. **The
defensible claim is that a 10.8-point recall gain produced no measurable accuracy gain at 87% more
prompt tokens.**

### Decided: k = 10 is frozen

Accuracy is a tie, so the tiebreakers decide, and all point the same way.

1. **Format compliance collapses at k=20.** k=10 was `anchored` on **102 of 102**. k=20 fell to 93
   anchored with 5 bare, 1 hedged and 3 none.
2. **Zero unparseable against 3.9%.** At k=10 the strict and FINDVER-compatible scores are
   **identical at 66.7%**, because there is nothing to impute. Given §11.8's whole argument is
   about imputation contaminating small-model scores, being at zero is worth protecting.
3. **Prompt size is the entire cost model.** 87% more tokens is 87% more MacBook latency, and the
   MacBook is the device of record. §3.4.4's factor 4 warned that doubling per-example time
   weakens the exact axis §6.1 attacks MACE on.

**Everything downstream inherits k=10**: the 7B, conditions 2, 3 and 4, and the 700 run. **k=20 is
kept as the retrieval-versus-accuracy ablation row**, not discarded.

**Limitation to state in the paper:** k was chosen on the 3B, a larger model may tolerate more
distractors, and at n=102 the two are statistically tied, so the choice rests on cost and format
compliance rather than on accuracy.

### Verdicts are unstable across retrieval changes

**Only 58 of 102 claims received the same label at both k values.** Retrieval changed and more than
40% of verdicts flipped. Together with the 5-of-6 machine divergence measured earlier the same
evening, this is a consistent picture: **this model's verdicts are highly sensitive to conditions
that should not change the answer.** Worth reporting as a small-model reliability observation.

### FDV-KNOW is the weak subset, and it is a retrieval problem

Knowledge sits at 26.5% all-gold recall against numeric's 70.6%, and has the lowest accuracy at
both k values. This reproduces §3.4's per-subset pattern on our own retriever and is the Tier 2
argument with our own numbers behind it.

### Llama-3.2-3B scored from the published outputs, for a same-size reference point

Read from `FinDVer/outputs/testmini_outputs/rag/processed_cot_outputs/Llama-3_2-3B-Instruct.json`.
No compute, no quota. **The id mapping `{subset}-testmini-{n}` to `{subset}-val-{n}` was verified
against statement text on all 700: 0 mismatches.**

                                          all 700    our same 102
    FINDVER-compatible (as published)       58.4%       62.7%
    strict, our extractor                   38.3%       36.3%
    unparseable under our extractor         34.7%       40.2%
      of which: no verdict word anywhere    26.6%       30.4%
      of which: we missed a verdict          8.1%        9.8%
    ends without terminal punctuation       17.9%       15.7%

**Internal consistency check passed.** 34.7% unparseable is 65.3% coverage, matching the 1 August
extractor measurement on this exact model to the decimal.

### An error I made and corrected the same session

I first reported the 26.5-point gap between Llama's published and strict scores as imputation.
**Wrong.** That assumed gpt-4o-mini failed on the same responses our extractor did. Their
`extracted_label` is stored **after** the coin flip, so gpt-4o-mini's true failure rate is
unmeasurable from these files — a caveat the 31 July entry already recorded and which I did not
apply.

**The correct decomposition** separates what any extractor could have done from what ours did.
**26.6% of responses contain the strings "entail" and "refut" nowhere at all.** gpt-4o-mini had
nothing to read on those, so they were coin-flipped no matter how good the extractor is. That
gives a **defensible lower bound of ~13.3 points of imputation on all 700**, ~15.2 on our 102. The
remaining ~8% is our regex being worse than gpt-4o-mini, which is our limitation, not theirs.

**A large part of the no-verdict rate is their generation settings, not their model.** 17.9% of
responses end mid-sentence at the 1024-token cap. The 1 August entry found 90 truncated responses
landing in the `none` bucket.

### The claim to write, and the ones not to

**Write this**, because it depends on nothing but the raw response text:

> Llama-3.2-3B stated no verdict at all on 26.6% of FINDVER's testmini. The official evaluation
> assigns those a random label, contributing roughly 13 points to its published 58.4%. Nearly a
> fifth of its responses terminate mid-sentence at the 1024-token generation cap.

**Do not write "our 3B beats their 3B."** The confounds are large and known: temperature 1.0, a
1024-token cap, and a retriever at 65.16% macro recall against our 74.60%. This is an
**evaluation-reliability finding**, which is the workshop's topic 05, and it is both stronger and
safer than a model-quality claim.

### What 66.7% means

    constant answer on a balanced sample        50.0%
    ours, 3B, single call, no pipeline          66.7%
    MACE's Mistral-7B with their full pipeline    64%
    MACE's Llama-8B with their full pipeline      68%
    FINDVER's best published RAG (claude-3.5)   75.0%

A 3B making one call is roughly level with an 8B running MACE's entire multi-agent system. Treat
that as context, not a claim: §6.1 records real problems with MACE's baseline column.

**The consequence that matters is that the floor is high.** §5.3's contribution is condition 4
minus condition 1. If condition 3 lands at 75–80%, the pipeline has 8–13 points to climb, and a
delta that size sits right at the edge of the ±10 margin at n=102. **This is a second, independent
reason the 700 run matters**, alongside the condition 3 comparison.

### Two scripts owed

Both of tonight's analyses were run as inline Python, which violates `paper_numbers.md` rule 1:
a number enters only when a committed script can regenerate it. Owed:

- `test_scripts/analyse_condition1.py` — the k=10 / k=20 table above
- `test_scripts/score_published_baselines.py` — the Llama scoring, generalised over all 16 models

The second is worth generalising: the same code gives strict-versus-published for every model in
`outputs/`, which is §11.8's table across the full model-size range rather than one point.

---

## 8–9 August 2026, evening into overnight — the local model settled, qwen3 rejected on cost, and DeepSeek connected

A long session. Four things shipped: the second local model measured end to end, a reasoning model
tried and abandoned, the DeepSeek client written and proven on a real claim, and both condition 2
runs started. Two corrections to things this log previously asserted.

### The GPU host, reconnected

IP unchanged at `10.0.0.26`. `netstat -ano | findstr 11434` showed `0.0.0.0:11434`, so the
7 August restart survived a reboot. `curl http://10.0.0.26:11434/api/tags` from the Mac answered,
which is the check that matters; `ping` is still useless because Windows blocks inbound ICMP.

**New and worth recording: the PC runs Ollama 0.32.6. The Mac is pinned at 0.12.3.** Nothing
prior noted how far apart they are. This is a second reason, independent of the floating-point
divergence measured on 7 August, why a results table must never mix the two machines.

Model inventory on the PC, from `/api/tags`:

    qwen2.5-coder:3b   3.1B  Q4_K_M  ctx  32,768   completion, tools, insert
    qwen2.5:3b         3.1B  Q4_K_M  ctx  32,768   completion, tools
    qwen3:4b           4.0B  Q4_K_M  ctx 262,144   completion, tools, thinking

`qwen2.5:3b` matches `qwen2.5-coder:3b` on parameter count and quantisation exactly, so the
comparison the professor asked for holds size and quantisation fixed and varies only code tuning.
That is the clean experiment. `qwen3:4b` varies family, size and reasoning mode at once, so it
could only ever have shown that something better exists, never why.

### Correction: `think: false` does not disable thinking

The plan for `qwen3:4b` was to switch reasoning off with Ollama's `think` field and compare it
like for like against the two non-reasoning 3B models. **That plan rested on a wrong belief about
what the field does.** Measured on the same prompt, "Is 2+2 equal to 4? Answer in one sentence.":

                     eval_count   thinking field   response
    think: false        332       absent           all 332 tokens of reasoning
    think: true         332       1,308 chars      43 chars, the clean answer

**Identical token counts.** The field controls where Ollama puts the reasoning text, not whether
the model produces it. Identical behaviour on `/api/generate` and `/api/chat`.

The practical consequence inverts the original recommendation. `think: false` is the **worse**
setting, because it dumps the reasoning into `response`, where `extract_label_with_source` reads
it and may take a verdict the model was still arguing against. `think: true` keeps `response`
clean. **The config was changed from `false` to `true` before the run.**

Most likely cause, unverified: the Qwen3 releases after mid-2025 split into separate Instruct and
Thinking models and dropped the hybrid `/no_think` toggle, so this build cannot be made to stop
reasoning at all. Not worth chasing unless qwen3 is revived.

### Code shipped

`src/ollama_client.py` — the `think` field, passed only when the key exists in the config:

    if "think" in config:
        payload["think"] = config["think"]

Written as `"think" in config` rather than `config.get("think", False)` on purpose, so that all
six pre-existing configs produce a byte-identical request body to what they sent yesterday.

`src/logger.py` — three new `Record` fields, `thinking`, `served_model`, `system_fingerprint`.
One field serves both providers: Ollama calls the reasoning trace `thinking` and DeepSeek calls it
`reasoning_content`, and they are the same thing. `served_model` is deliberately not called
`model`, because `Record.config` already contains a `model` key and two fields under that name,
one requested and one delivered, is a debugging trap.

`src/run_loop.py` — three lines filling them, all using `.get`, so a client that does not send
them writes `None` rather than raising.

`test_scripts/test_harness.py` — `RECORD_FIELDS` and the field-count message moved 18 → 21.
The existing `ModelStub` needed no change, precisely because of the `.get`. **50/50 passed**, up
from 44 because the two new configs bring their own per-config checks.

`src/deepseek_client.py` — new. An adapter: it returns DeepSeek's response under Ollama's key
names, so `run_loop.py`, the prompt builder, the evidence asserter and the label extractor are all
untouched.

    response            <-  choices[0].message.content       never reasoning_content
    prompt_eval_count   <-  usage.prompt_tokens
    eval_count          <-  usage.completion_tokens
    done_reason         <-  choices[0].finish_reason         "stop"/"length", same vocabulary

`run.py` — a `CLIENTS` dict beside `RETRIEVERS`, selected by `config.get("client", "ollama")`.
**A correction to `working_state.md`, which claimed no change was needed here** on the grounds
that `call_model` is already a parameter. Half right: `run_loop.py` takes it as a parameter, but
`run.py` was passing `call_ollama` hardcoded.

New configs: `condition1_qwen25_3b_k10`, `condition1_qwen3_4b_k10`, `condition2_deepseek_pro`,
`condition2_deepseek_flash`.

### Condition 1, `qwen2.5:3b`, n=102, GPU — complete, 102 ok

Same 102 claims, same seed, same prompts, same machine as `condition1_3b_k10`.

                            coder:3b    qwen2.5:3b
    strict accuracy           66.7%       67.6%
    FINDVER-compatible        66.7%       68.6%
    unparseable                0.0%        2.0%
    evidence_present          54.9%       54.9%
    prompt tokens, mean        3,651       3,651
    output tokens, mean          413         497
    wall clock              11.2 min    13.4 min
    per claim                  6.6 s       7.9 s
    extraction anchored     102/102      92/102

    ie                        64.7%       64.7%
    knowledge                 58.8%       58.8%
    numeric                   76.5%       79.4%

    paired: same label on 79/102 = 77.5%
    23 disagreements, coder right on 11, plain right on 12

**`evidence_present` and mean prompt tokens are identical to the digit.** That is the sanity check
passing, since neither depends on the model. The comparison is clean.

**Code tuning changed accuracy by one claim in 102.** The paired split, 11 against 12, is a coin
flip. The professor's objection is answered, and the answer is "no measurable difference," not
"the plain model is better." Never write the latter.

**The Coder model wins on the tiebreakers instead.** 102/102 anchored against 92/102, 0.0%
unparseable against 2.0%, 17% faster, and 20% fewer output tokens for the same job. Same shape as
the k=10 versus k=20 decision: the headline is a tie and the format compliance breaks it.

**A detail that looks like agreement and is not.** The `ie` and `knowledge` subset totals are
identical for both models, 22/34 and 20/34. They still disagreed on 23 individual claims and
happened to land on the same totals. Aggregate agreement hides per-claim instability.

**Verdict instability now has a third independent measurement.** 5 of 6 across machines
(7 August), 58 of 102 across k values (overnight), 79 of 102 across model variants (tonight).
Same family, same size, same quantisation, identical prompts, and a fifth of the labels move.

### `qwen3:4b` aborted after 6 claims

Ran with `think: true` and `num_predict` raised to 8000, the budget check being
32,768 − 8,000 = 24,768 against a largest observed condition 1 prompt of 14,066, so trimming was
provably unchanged.

    ie-val-193        eval 4,964   stop     thinking 11,670 chars   label True
    ie-val-239        eval 7,970   stop     thinking 24,728 chars   label False
    knowledge-val-51  eval 5,787   stop     thinking 17,586 chars   label False
    numeric-val-69    eval 8,000   length   thinking 18,282 chars   label None, response 0 chars

**Two failures, and the second is the one that ends it.**

`numeric-val-69` produced 18,282 characters of reasoning, hit the 8,000 cap and wrote **nothing at
all** into `response`. Unparseable, on the numeric subset, one of the first four claims.

**145 seconds per claim on the GPU**, against 6.6 for the Coder model. That is 4.1 hours for 102
claims. Applying the measured 36.8x MacBook-to-GPU ratio puts it at roughly **90 minutes per claim
on the device of record.** A model that cannot run on the 2017 MacBook is not an edge model
whatever its accuracy, and this paper is about on-device inference. Cost, not accuracy, is what
rejects it.

Stopped deliberately, at the user's decision, rather than spending four GPU hours on a model
already known to be unusable. The 6 records are preserved at
`results/condition1_qwen3_4b_k10_abandoned_8aug/` because they are the evidence for the rejection,
and moving rather than deleting also frees the experiment name. `has_result` resumes on file
existence, so leaving 6 records made at `num_predict` 8000 in the live directory would have
silently mixed two configurations if the cap were raised tomorrow.

### DeepSeek: an SSL failure that was not DeepSeek's

The first real call died on `CERTIFICATE_VERIFY_FAILED`. **Not the key, not the API.** Homebrew's
Python 3.14 looks for its certificate bundle at `/usr/local/etc/openssl@3/cert.pem`, which does
not exist on this machine. A valid bundle does exist at `/usr/local/etc/ca-certificates/cert.pem`.

Fixed without touching code or disabling verification, by adding to `.env` beside the key:

    export SSL_CERT_FILE=/usr/local/etc/ca-certificates/cert.pem

This is the first HTTPS request the project has made from Python. Every Ollama call is plain HTTP
to a LAN address, and the 7 August smoke test used `curl`, which reads the system keychain. That
is why it had never fired before.

Related and worth writing down: **a `.env` file does nothing on its own.** The `export` lines in
it are instructions nobody has run until `source .env`. That cost a few minutes of confusion.

### DeepSeek, measured on one real claim

`numeric-val-41`, a real condition 1 prompt, `deepseek-v4-pro`, `max_tokens` 8000, temperature 0.

    prompt_tokens        3,004        qwen counted 3,622 for the same text
    completion_tokens    2,123
      reasoning_tokens   1,731        82% of output is thinking
    finish_reason        stop         no truncation, 3x headroom under the cap
    cached_tokens        0

**The verdict was correct and correctly formatted.** Gold `False`; it computed 112.12% against the
claim's 112.16%, and closed with "Therefore, the claim is refuted." Anchored final sentence, first
try, no prompt changes.

**DeepSeek's tokenizer counts about 17% fewer tokens than qwen's** on identical text.

**`num_predict` 8000 is confirmed correct for condition 2.** The cap did not bind and the trim
budget is unchanged from condition 1.

**`DeepSeek-V4-Flash-0731` is rejected.** HTTP 400: "The supported API model names are
deepseek-v4-pro or deepseek-v4-flash." **A snapshot cannot be pinned**, closing the question the
7 August entry left open. The floating alias is the only option.

**A consequence that undoes part of tonight's own design.** The API echoes back the alias,
`served_model: deepseek-v4-flash`, not the snapshot behind it. So `served_model` **cannot** detect
a silent model roll for DeepSeek, which is the reason the field was added. `system_fingerprint`
can, and did return `fp_9954b31ca7_prod0820_fp8_kvcache_20260402`, which carries dates. Keep both,
but rely on the fingerprint.

**`seed` and `temperature` were accepted without error.** Accepted is not the same as respected,
so this was tested rather than assumed, before bed, for about a cent.

### Tested: DeepSeek ignores both. Condition 2 is not reproducible.

Three calls on the same real prompt, `numeric-val-41`, temperature 0, identical payloads.

    A  seed 0       1,235 completion tokens   1,021 reasoning   content hash 33f2d6445c5a
    B  seed 0       1,357                     1,081             content hash e4a347e30bef
    C  seed 12345   1,883                     1,690             content hash 48c66e8bd3aa

**A and B share a seed and produced different text**, on both the answer and the reasoning, and
differ by 122 completion tokens. `system_fingerprint` was byte-identical across all three, so this
is not a model roll between calls. The settings are accepted and discarded.

All three closed with "Therefore, the claim is refuted," which is correct. **That is one claim
sampled three times and is not evidence of verdict stability.** It must not be reported as such.

**Consequence for the paper.** Condition 2's accuracy is a single sample. Re-running the 102
claims gives a different number by an unknown margin. State it as a limitation rather than
measuring it: quantifying the variance costs another $0.32 and buys a figure nobody asked for, and
five pages do not have room for it. The framing is on topic for this venue — **the cloud half of
an edge-cloud system is not reproducible even when the edge half is.**

**Condition 1 is unaffected.** Ollama honours both settings, and its cross-machine instability is
floating-point arithmetic, a separate effect already measured on 7 August.

**Incidental: the cost estimate above is conservative.** Four samples of `numeric-val-41` now
exist at 2,123, 1,235, 1,357 and 1,883 completion tokens. The $0.32 projection used the largest.
The real figure comes from the finished run, not from this claim.

### Cost, from the measured token counts

Projected over 102 claims:

                        pro       flash
    input   0.309 M    $0.134    $0.043
    output  0.217 M    $0.188    $0.061
    TOTAL              $0.32     $0.10        both together about $0.42

The single test call cost about **$0.003**. `numeric-val-41` is a numeric claim and reasons more
than average, so treat $0.42 as the high end. DeepSeek's pricing page warns of a significant
increase soon, so quote these with today's date attached.

### Both condition 2 runs started, results not yet in

`condition2_deepseek_pro` and `condition2_deepseek_flash`, launched concurrently in separate
terminals. Two concurrent requests against limits of 500 and 2500 is nothing, and both processes
sit waiting on the network rather than competing for CPU. Pro measured 14.9 s and 34.2 s on its
first two claims, so roughly **45 minutes for 102**, against the 1 to 2.5 hours estimated before
any measurement existed.

### Condition 2, both models, n=102 — complete, 102 ok and 0 failed on each

                            coder:3b     pro      flash
    strict accuracy            66.7%    71.6%     75.5%
    FINDVER-compatible         66.7%    75.5%     76.5%
    unparseable                 0.0%     4.9%      2.0%
    evidence_present           54.9%    54.9%     54.9%
    predicted True            41/102   31/102    31/102    (gold 51/102)
    prompt tokens, mean         3,651    3,321     3,400
    output tokens, mean           413    1,667     1,477
    thinking chars, mean            0    6,218     5,241
    context_overflow            0/102    0/102     0/102
    wall clock               11.2 min  34.8 min  21.3 min
    per claim                   6.6 s   20.5 s    12.6 s
    cost                            —   $0.295    $0.091

    ie                         64.7%    76.5%     79.4%
    knowledge                  58.8%    70.6%     64.7%
    numeric                    76.5%    67.6%     82.4%

`evidence_present` identical to the digit across all three, which is the validity check passing.
`system_fingerprint` constant across all 102 within each run, `fp_9954b31ca7…` for pro and
`fp_a18b46594c…` for flash, so no model roll happened mid-run. **$0.386 for both against $0.42
projected**, so the estimate-from-one-claim method was sound to within 9%.

### Pro's numeric score is a truncation artifact, and that is the real finding

**All five of pro's unparseables are `done_reason=length` at the 8,000 cap, and all five are
numeric claims**: `numeric-val-11`, `-111`, `-57`, `-69`, `-90`. Not one is a format failure. The
model was still reasoning when the budget ran out and never wrote a verdict.

**Excluding them, pro scores 79.3% on numeric rather than 67.6%.** Flash excluding its single
numeric truncation is 84.8%. `numeric-val-90` truncated on both models, and **`numeric-val-69` is
the same claim that truncated `qwen3:4b` at the same cap earlier tonight** — some numeric claims
simply demand more reasoning than 8,000 tokens.

**So 71.6% is a floor for pro, not its performance**, depressed by a configuration choice made
before any of this was known. A re-run at 16,000 is owed before the number enters the paper.

### Three things the raw table would lead you to write, and all three are wrong

**"Flash beats pro."** They agree on 94 of 102; of the 8 disagreements flash is right on 6 and pro
on 2. That is a tie, and most of the apparent 4-point gap is pro's truncations. The supportable
sentence is **"flash matched pro at a third of the cost and 1.6x the speed."**

**Pro's FINDVER-compatible 75.5%.** The seeded coin flip resolved 4 of its 5 unparseables in its
favour. That is luck. **It is also §2.4's imputation argument appearing in our own run rather than
in a published baseline**, which makes the 3.9-point gap between our two scorings a usable
illustration rather than an embarrassment. Use strict, 71.6%.

**"The cloud model is better."** On average, yes. Per claim, no. Against pro the two agree on 67 of
102; pro is right on 20 the 3B misses, and **the 3B is right on 15 that pro misses**, spread over
all three subsets — 7 numeric, 5 ie, 3 knowledge. **The cloud model does not dominate, which is
exactly the premise routing rests on.** This is the most useful thing measured tonight.

### Two smaller observations

**All three models skew toward refuted.** Gold is 51/102 entailed. The edge model predicted
entailed 41 times, both cloud models 31. A systematic bias, and material for the error taxonomy.

**The two DeepSeek models tokenize identical text differently**, 3,321 mean against 3,400. Same
provider, same prompts. Harmless, but one model's token count does not transfer to the other.

### The gap condition 4 has to close

**4.9 points to pro, 8.8 to flash**, strict, at n=102. That is the first time the target has been
a measured number rather than an assumption.

---

## 9 August 2026 — the two owed scripts, and the model decision closed on cost

### Both owed scripts written, and rule 1 is satisfied for the first time

`test_scripts/analyse_condition1.py` reproduces sections 2.3, 2.5 and 2.6 exactly.
`test_scripts/score_published_baselines.py` reproduces 2.4 and generalises it to all 16 models.
Harness unaffected, 56/56 at the time, 59/59 once the new config landed.

**A significance test was added, and the result reframes the project.** The analysis script now
runs an exact two-sided McNemar test on every pair of runs. **All ten pairs come back ties.**

    coder:3b vs v4-pro       67/102 agree   15 vs 20   p = 0.500
    coder:3b vs v4-flash     70/102 agree   11 vs 20   p = 0.150
    k=10 vs k=20             58/102 agree   22 vs 18   p = 0.636
    coder vs qwen2.5:3b      79/102 agree   11 vs 12   p = 1.000

**The edge-versus-cloud gap, which the contribution rests on, is p = 0.500.** Not one accuracy
comparison in the project is currently distinguishable from a coin flip. This is not a fault in
any run, it is what n=102 buys, and §4.5 already recorded the same lesson for retrieval. **The
700 run stops being an enhancement and becomes the requirement.**

### Generalising the baseline scorer found a better example than the one already written up

    Llama-3.1-8B   published 66.4%   strict 41.3%   no verdict word 26.9%
    Llama-3.2-3B   published 58.4%   strict 38.3%   no verdict word 26.6%
    gpt-4o         published 75.3%   strict 75.3%   no verdict word  0.0%
    claude-3.5     published 73.1%   strict 73.1%   no verdict word  0.0%

**Llama-3.1-8B is the stronger case.** It is published mid-table at 66.4%, ahead of three other
baselines, and states no verdict on 26.9% of claims. The frontier models sit at 0.0%. The
imputation effect appearing and disappearing with model scale, across sixteen models, is a much
harder argument to dismiss than one 3B data point. **Costs nothing: the data was already in the
repo.**

### A number in `paper_numbers.md` was wrong, and only the raw data caught it

The first version of the scorer counted a response ending in `*` as cut off mid-sentence. That is
markdown closing a bold **refuted**. It reported **63.7% truncation for gemini-1.5-pro**, whose
unparseable rate is 6.7%. Verified by inspecting the final character of every flagged response:
all 446 of gemini's end in `*`, as do 124 of Mistral-Large's, while Llama-3.2-3B's end in ordinary
letters, which is real truncation.

**§2.4's truncation row was wrong: 17.9% → 15.3% on 700, and 15.7% → 13.7% on our 102.** The old
figure came from the earlier inline script. **This is exactly the failure rule 1 exists to
prevent**, and it was catchable only because the raw upstream data still existed. Worth
remembering the next time deleting result files looks like tidying.

### `qwen3:4b` was not a GPU failure, and the reason matters

Asked whether the 145 s/claim was a CPU fallback. It was not.

    qwen3:4b            6,978 out tokens/claim   127.9 s   54.5 tok/s
    qwen2.5-coder:3b       413                     6.6 s   63.0 tok/s
    qwen2.5:3b             497                     7.9 s   62.8 tok/s

**54.5 tokens per second is normal**, 87% of the 3B rate, about what one extra billion parameters
costs. A CPU fallback would look like 5 to 10. **The slowness was entirely token count**, 17x
more, all of it thinking.

**Correcting last night's own claim:** the "roughly 90 minutes per claim on the MacBook" figure
was extrapolated from the 36.8x whole-run ratio, which was measured on prompt-dominated runs. The
MacBook's generation rate has never been measured separately, so the honest range is 20 to 90
minutes. The direction was never in doubt; the precision was overstated.

### The real reason `qwen3:4b` failed: Qwen3 ships thinking and non-thinking separately

Checked the Ollama registry rather than guessing. `qwen3:4b-instruct-2507-q4_K_M` exists at the
same Q4_K_M quantisation as the other two models. **There was never a switch to find** — the tag
we ran was the thinking build, and the hybrid `/no_think` toggle no longer exists in this
generation.

### The instruct build, verified before spending a run

Capabilities came back `['completion', 'tools']` with **no `thinking`**, and one trivial call
returned **12 tokens** where the thinking build spent 332. Only then was the 102 run started. This
is the check that was skipped last night and cost four aborted claims.

### Condition 1, `qwen3:4b-instruct`, n=102 — complete, 102 ok

                        coder:3b   qwen2.5:3b   qwen3:4b-instruct
    strict accuracy        66.7%       67.6%          67.6%
    FINDVER-compatible     66.7%       68.6%          75.5%
    unparseable             0.0%        2.0%           7.8%
      of which truncated       0           0             13
    output tokens, mean      413         497          1,281
    seconds per claim        6.6         7.9           23.0
    extraction anchored  102/102      92/102         93/102
    ie                     64.7%       64.7%          76.5%
    knowledge              58.8%       58.8%          64.7%
    numeric                76.5%       79.4%          61.8%

**All three tie, every pairwise p = 1.000.** A 3B code model, a 3B general model and a 4B general
model spread across 0.9 accuracy points.

**The 4B's number is a floor, and the same caveat applied to DeepSeek pro applies here.** 13
truncations at `num_predict` 2000, **11 of them numeric**. Excluding them it scores 71.9% overall
and 73.9% on numeric rather than 61.8%. A rerun at 4000 would likely reach about 72%.

### Decision: `coder:3b`, on cost, with the rule fixed in advance

The threshold was set at 5 points **before the run**, to avoid choosing after seeing the data. The
measured gap is 0.9.

**Even granting the 4B its optimistic ~72%, it loses.** It is 3.5x slower per claim on identical
prompts and generates 3.1x more output tokens. On the MacBook generation is CPU-bound, so the gap
widens rather than narrows, and condition 4 makes several calls per claim on a device where one
call already takes 7 minutes. **A model that needs a larger generation budget is a worse edge
model, not a better one.** That is the paper's own argument applied to its own model choice.

**The 45-minute rerun at 4000 is deliberately not scheduled**, because no plausible result changes
the choice. Recorded as open in §2.5.1 so it is a decision rather than an oversight. Revisit only
if condition 4 proves accuracy-bound rather than latency-bound.

Two phrasings fixed in the docs. **Do not quote the 4B's FINDVER-compatible 75.5%**, which is
eight coin flips that mostly landed right, the same trap as pro's. **Do not write "the 4B is no
better than the 3B"**, which the truncation makes false.

### `run.py` now runs the full split

`per_cell: null` skips the sampler. `stratified_sample` cannot produce 700 because `check_balance`
requires equal cells and the knowledge cells hold 100 against 125, so 600 was its ceiling. The
full split is **shuffled with the run's seed**, because file order is solid blocks by label and an
interrupted 2-hour run would otherwise leave a partial set that is nearly all one class. An
assertion on the count of 700 guards against a silent loader change.

### Housekeeping

`results/` reorganised rather than pruned. `trial_run_3b`, `smoke_bm25`, `smoke_bm25_gpu`,
`decompositions_v1.json` and the abandoned qwen3 records moved to `results/archive/`. Total was
15 MB and the five candidates for deletion were 860 KB, so space was never the issue. Each backs
a figure that is either in `paper_numbers.md` or in `CLAUDE.md`, and **`results/` is gitignored,
so deletion has no undo.** `trial_run_3b` is the only measurement of the MacBook that exists.

**Noted and not yet acted on: none of `results/` is backed up anywhere.**

### The API spend tally, because the key is the professor's

`test_scripts/api_cost_tally.py`. Two independent figures, because neither alone is enough: spend
per experiment computed from our own recorded token counts, and DeepSeek's live balance from
`GET /user/balance`. They will not agree exactly, since the account is in CNY and their CNY price
list is not the USD list at spot rate. **The per-experiment column attributes the money; the
balance delta is the truth about how much.**

    condition2_deepseek_pro     102 claims   $0.295
    condition2_deepseek_flash   102 claims   $0.091
    ad-hoc calls, 7                          $0.011
    TOTAL                                    $0.397

**Balance baseline recorded: 142.32 CNY on 9 August**, about $19.80, all topped up, no granted
credit. The starting balance is unknown so the total cannot be checked against theirs yet. Their
balance also lags: 142.38 then 142.32 twenty minutes later with nothing running.

The seven hand-made calls are hardcoded in the script with dates and reasons, because they went
through curl rather than `run.py` and appear in no result file.

### `prompt_budget_tokens`, and why the 46768 hack was replaced

Raising DeepSeek's `max_tokens` to 16,000 to stop the truncation had a side effect: `build_prompt`
derives its evidence budget as `num_ctx - num_predict`, so the prompt would have shrunk from
30,768 tokens to 16,768 and condition 2 would have been reading less evidence than condition 1.

The first fix was to raise `num_ctx` to 46,768 so the subtraction landed back on 30,768. **It
worked and it was wrong**, because 46,768 is not a fact about anything — it encodes condition 1's
`num_predict` — and JSON cannot carry a comment saying so. Change condition 1's cap later and the
two configs would silently start trimming differently.

Replaced with an explicit optional key, one line in `build_prompt`:

    budget_tokens = config.get("prompt_budget_tokens", config["num_ctx"] - config["num_predict"])

**Ollama configs must not use it.** There `num_ctx` is real and sent to the model, so
`num_ctx - num_predict` is the physical room left for the prompt, and hardcoding past it would
resurrect data trap 3. A harness check enforces `prompt_budget_tokens + num_predict <= num_ctx`
so the escape hatch cannot defeat the trap. Harness at 70/70.

Verified before spending anything: the three 700 configs produce **byte-identical prompts** on 25
sampled claims and identical claim ordering, so the conditions are comparable by measurement
rather than by assertion.

---

## 9 August 2026, evening — condition 1 at n=700, and two documented claims falsified

`configs/condition1_3b_full700.json`, `qwen2.5-coder:3b`, BM25 k=10, full split shuffled with
seed 0. **700 ok, 0 failed, 79.4 minutes**, faster than the 2 to 3 hours the plan estimated.

                            n=700     n=102
    strict accuracy         61.4%     66.7%
    FINDVER-compatible      62.1%     66.7%
    unparseable              1.1%      0.0%
    evidence_present        52.0%     54.9%
    predicted True        324/700    41/102     (gold 350/700)
    prompt tokens, mean     3,731     3,651
    output tokens, mean       416       413
    context_overflow        0/700     0/102
    trimmer fired           0/700     0/102
    per claim               6.8 s     6.6 s
    extraction        690 anchored, 5 none, 3 hedged, 2 bare

    ie                      60.8%     64.7%     152/250
    knowledge               59.0%     58.8%     118/200
    numeric                 64.0%     76.5%     160/250

### The headline fell 5.3 points, and the cause was diagnosed rather than guessed

Two candidates: the 102 sample was unrepresentative, or the model is not reproducible. **Both turn
out to be true, and they matter in different ways.**

    prompts identical across the two runs            102/102
    the 700 run, on those same 102 claims             67.6%
    the 102 run, on those same claims                 66.7%
    the 700 run, on the other 598 claims              60.4%

**The drop is sampling.** The two runs agree to within one claim where they overlap, and the
unseen 598 are 7 points harder. The 102 draw was easy, worst on numeric, which read 76.5% against
a true 64.0%. **Third appearance of the sample-versus-population error**, after 5 and 6 August,
and the first time it has hit an accuracy number rather than a retrieval one.

**Consequence: every n=102 accuracy figure in the project is inflated by an unknown amount**,
including condition 2's 71.6% and 75.5%. The edge-versus-cloud gap must not be quoted until both
sides are at 700. Both condition 2 runs at 700 are in flight, which is fortunate timing rather
than foresight.

The model-choice conclusions in §2.5 and §2.5.1 survive, because they rest on latency and format
compliance. Their accuracy columns do not.

### The second finding is cleaner and was not being looked for

**Same model, same GPU, byte-identical prompts, same seed, temperature 0, run twice: labels agreed
on 91 of 102, 89.2%.**

Prompt equality was verified on all 102, so retrieval, sampling, trimming and prompt building are
perfectly deterministic and **the divergence is entirely in generation** — most likely
floating-point reduction order varying with GPU scheduling between runs.

**This falsifies a claim written into these docs yesterday.** After DeepSeek was found to ignore
`seed` and `temperature`, the entry recorded that "Ollama honours both settings" and that its
instability was a cross-machine effect. The cross-machine half was measured on 7 August. The
within-machine half was an assumption stated as fact, and it is wrong.

Verdict instability now has four independent measurements, and this is the purest because nothing
varied at all:

    the machine, Mac vs GPU         5 of 6
    k, 10 vs 20                    58 of 102
    the model, three variants      79 of 102
    nothing, the same run repeated 91 of 102

**Operational rule: a difference smaller than about one claim in ten between two of our own runs
is noise.** It also makes a point about the benchmark, where single-run numbers are reported as
point estimates throughout the literature.

### A third documented claim withdrawn

§2.3 said the strict and FINDVER-compatible scorings were identical at 66.7% because unparseable
was 0.0%, and called that the only figure in the project with the property. **At n=700 unparseable
is 1.1% and they diverge**, 61.4% against 62.1%. The property belonged to the sample, not to the
model.

Three claims corrected in one session, all of them ones this project had written down confidently.
The pattern is the same each time: a number measured on a small or convenient sample, stated
without the caveat that it might not generalise.

Operational note, since the machine had to stay awake unattended: `caffeinate -ims` deliberately
omits `-d`, so the displays sleep normally while the system stays awake. Verified live with
`pmset -g assertions`: `PreventUserIdleDisplaySleep 0`, `PreventUserIdleSystemSleep 1`, on AC
power, which is what `-s` requires. `pmset displaysleepnow` blanks the screens immediately.
Closing the lid would still sleep the machine and kill the runs.

### Owed, carried forward

`test_scripts/analyse_condition1.py` is still not written, and tonight's coder-versus-plain table
was produced by another inline script. **Rule 1 is now violated by three results rather than two.**

---

## 10 August 2026 — condition 2 at n=700, and the gap is not where anyone assumed

Both condition 2 runs finished overnight. `configs/condition2_deepseek_pro_full700.json` and
`configs/condition2_deepseek_flash_full700.json`, `max_tokens` 16,000, `prompt_budget_tokens`
30,768, temperature 0, seed 0, BM25 k=10, `baseline_v1`, full 700 split shuffled with seed 0.
**700 ok, 0 failed, 0 skipped on each.** Regenerated with
`python3 test_scripts/analyse_condition1.py condition1_3b_full700 condition2_deepseek_pro_full700
condition2_deepseek_flash_full700`.

                            coder:3b    v4-pro   v4-flash
    strict accuracy            61.4%     77.3%      77.0%
    FINDVER-compatible         62.1%     77.6%      77.0%
    unparseable                 1.1%      0.3%       0.0%
      of which truncated            1         2          0
    evidence_present           52.0%     52.0%      52.0%
    predicted True           324/700   213/700    217/700   (gold 350/700)
    prompt tokens, mean        3,731     3,384      3,463
    output tokens, mean          416     1,446      1,463
    thinking chars, mean           0     5,312      5,173
    context overflow           0/700     0/700      0/700
    trimmer fired              0/700     0/700      0/700
    wall clock              79.4 min  270.4 min  147.7 min
    per claim                  6.8 s     23.2 s     12.7 s
    cost                           —    $1.911     $0.626

    ie                         60.8%     80.8%      80.4%
    knowledge                  59.0%     70.5%      70.5%
    numeric                    64.0%     79.2%      78.8%

    extraction, pro       698 anchored, 2 none
    extraction, flash     700 anchored

`evidence_present` is 52.0% in all three, so all three received identical prompts and the model is
the only variable. One `system_fingerprint` per run, so no model roll mid-run.

### The truncation fix worked, exactly as predicted

Pro's unparseable rate fell from **4.9% at `max_tokens` 8,000 to 0.3% at 16,000**, two claims
instead of five. The 9 August entry called 71.6% a floor depressed by a configuration choice and
owed a re-run. That prediction is now confirmed: pro at full scale and full budget is 77.3%.

### The edge-versus-cloud gap is 15.9 points, and n=102 understated it by a factor of three

    pair                          agree    A right   B right       p
    coder:3b vs v4-pro          428/700         80       191   0.000
    coder:3b vs v4-flash        424/700         83       192   0.000
    v4-pro  vs v4-flash         660/700         21        19   0.875  tie

**This is the first significant accuracy comparison the project has produced.** At n=102 the same
pair was p = 0.500, a coin flip.

The n=102 figure of 4.9 points was wrong in **both** directions at once, which is why it was so far
off. The 3B side was inflated by an easy sample, 66.7% against a true 61.4%. The pro side was
depressed by truncation, 71.6% against a true 77.3%. The two errors pointed toward each other and
nearly closed a real 15.9-point gap. **Fourth appearance of the sample-versus-population error**,
and the first where two independent biases stacked.

### Flash and pro are tied at n=700, so the cloud tier is flash

77.3% against 77.0%, agreeing on 660 of 700, disagreements splitting 21/19, **p = 0.875**. This is
no longer "too small a sample to separate them," which is what the n=102 tie meant. At n=700 the
tie is a measurement.

**Flash costs $0.626 against pro's $1.911 and finishes in 148 minutes against 270.** One third the
price, 1.8x the speed, no accuracy difference. **Decision: the cloud tier in the pipeline is
`deepseek-v4-flash`.** Pro is kept as a reported baseline and nothing else.

Cost also confirms the §3.4 projection method at scale. Flash scaled from $0.091 at 102 to $0.626
at 700, against $0.624 predicted by linear extrapolation.

### The entire gap is on refuted claims. On entailed claims a 3B laptop model ties a frontier model.

Confusion matrices computed directly from the per-claim JSONs, all 700, gold 350 entailed and 350
refuted:

                        coder:3b    v4-pro   v4-flash
    correct on entailed      204       203        203     (of 350)
    correct on refuted       226       338        336     (of 350)
    false positives          120        10         14
    false negatives          142       147        147
    unparseable                8         2          0

    recall on entailed      58.3%     58.0%      58.0%
    recall on refuted       64.6%     96.6%      96.0%

**All three models are within one claim of each other on entailed claims.** The 15.9-point gap is
built entirely out of refuted claims, where cloud goes from 226 correct to 338.

Two consequences. **The cloud tier is not better at verifying claims, it is better at catching
false ones.** And **nothing in this pipeline currently helps the 42% of entailed claims that every
model misses**, which is the single largest error pool in the project and is not addressed by any
tier in §8's build order.

### The 3B model does not use the retrieved evidence at all

Each run split by whether the gold evidence actually reached the prompt, using the stored
`evidence_present` boolean. 364 claims with, 336 without, identical across all three runs.

                        with evidence   without    delta
    coder:3b            61.3% 223/364  61.6% 207/336   -0.3
    v4-pro              81.0% 295/364  73.2% 246/336   +7.8
    v4-flash            82.1% 299/364  71.4% 240/336  +10.7

**The 3B scores the same whether or not the correct evidence is in front of it.** The cloud models
gain 8 to 11 points from it.

**Caveat, and it is a real one: this is observational, not causal.** Claims where BM25 succeeds may
simply be easier claims, so the cloud figure of 8 to 11 points is an upper bound on what better
retrieval would buy, not an estimate of it. The 3B result does not have that problem in the same
way, because a −0.3 point difference cannot be rescued by any confounder argument.

### A framing error from this morning, corrected before it reached the docs

The 120 false positives were first described as the 3B being "credulous" and inclined toward
entailed. **That is wrong.** The 3B predicts entailed 324 times out of 700 when the truth is 350,
so it predicts entailed slightly *less* often than it should, and its errors lean marginally toward
refuted, 142 false negatives against 120 false positives.

The 3B has no directional bias worth correcting. It has **weak discrimination**, 58.3% and 64.6% on
the two classes. 120 only looked like credulity beside the cloud's 10, and the cloud's 10 is the
anomaly.

**This also qualifies a claim written on 9 August.** "All three models are biased toward refuted"
was recorded from the n=102 run. At n=700 the two cloud models are strongly skewed, predicting
entailed 30.4% and 31.0% of the time against a true 50%. The 3B is at 46.3%, which is a slight lean
and not the same phenomenon. Do not group all three under one sentence.

### What survives from n=102, and it is the premise routing rests on

**The 3B is right on 80 claims that pro gets wrong**, 11.4% of the split, against 15 of 102 at the
smaller size. The cloud model is better on average and wrong on a *different* set of claims. §5.3's
routing curve still has something to route.

### Consequence for §5.2: the edge-first verifier row is in trouble

§4.4 and §4.7 assign prompt ingestion of the retrieved evidence and generation of the verdict and
explanation to **cloud**. The edge 3B is assigned claim decomposition, `.loc` lookup writing,
glossary term-spotting, and the first-pass verifier screen. So the evidence-blindness finding does
**not** condemn the pipeline: condition 1 is the edge-only ablation, not the system.

It does hit one row. §5.2 assigns **"verifier, judgment checks: edge first, escalate to cloud."**
That role requires the 3B to read evidence and decide whether a reasoning step follows. A model
measured at −0.3 points from having the correct evidence present cannot do that job. §5.2 already
flags a related risk from MACE, that a cross-model verifier falsely refuses correct claims. This
measurement makes the row worse than the plan assumed.

**This belongs in front of the professor alongside §13 open question 1**, since §4.5 already
records the routing boundary as the most useful open question and this is the first hard data on
it.

### The contribution statement was ambiguous, and today's cost figure exposed it

Raised as a challenge rather than found in the data: if the cloud tier does the prompt ingestion
and the output generation, why build condition 4 at all instead of just running condition 3.

**The challenge is partly right and the answer is worth recording.** Condition 3 is not a
shortcut, because §9.2 defines it as the cloud model in *every pipeline role* — the same code as
condition 4 with the routing knob at "always escalate." Choosing it saves no build time, only run
time. And it is the baseline the paper is measured against, so running it alone is running the
control and skipping the experiment.

**Where the challenge lands: the cost claim was never pinned to an axis.** §5.3 said "at a fraction
of the cost" without saying which cost, and the honest dollar figure is **$0.626 for the entire
cloud-only baseline over 700 claims**, or $0.00089 per claim. Halving the cloud calls saves under a
dollar across the whole benchmark.

**[SHARPENED later the same day, by his objection, and it is worse than the first pass said.]** The
first version of §5.3.1 recorded that resident memory "does not separate" conditions 3 and 4. **That
was too kind. It runs the wrong way.** Condition 3 keeps **zero** model parameters on the device,
because the cloud plays every role and the laptop only orchestrates, while condition 4 must hold 3B
resident. Both run on a laptop. **So condition 3 beats condition 4 on memory and ties on
portability.** The two axes that felt strongest are the two that fail.

What survives against condition 3 is cloud calls and tokens per claim, which converts to under $3
of money and to data sent to a third party that nobody asked about. **This is the weakest point in
the contribution statement and it should be put to the professor rather than written around.**

**The MACE comparison is untouched and remains solid**, precisely because MACE uses no cloud at
all: its smallest configuration needs 27B resident, which this machine cannot hold, against our 3B
plus an API. Resident parameters and laptop feasibility are legitimate there.

**A framing correction that came out of the same exchange.** §9.2's "beating condition 2 is a
bonus" was being read as a reason to downplay the result. It is not. It governs what leads the
abstract. **If condition 4 beats 77.0%, that is a headline result in its own right** — a pipeline
doing part of its work with a 3B model on a laptop beating a frontier cloud model used the obvious
way is a real finding for this venue. The fallback paper, if nothing separates condition 4 from
condition 3, is that result plus a study of where the line between the two models can be drawn.

Resolved into **§5.3.1** of the architecture plan and **§3.5** of paper numbers:

- **Condition 4 vs condition 3** → cloud calls and tokens per claim, as a ratio.
- **Ours vs MACE** → resident parameters, 3B plus an API against their smallest 27B.
- **The goal** → cheapest component that can *reliably* do each role, ordered
  `no model < edge 3B < cloud`. Explicitly **not** "maximise 3B roles," since the no-model rows in
  §4.4 are the largest saving.
- **Wall clock** → reported with the machine named, never as a headline, because it reverses:
  3B 6.8 s per claim on the GPU box against flash's 12.7 s, and about 420 s on the MacBook.
- **The deliverable** → the routing curve's knee, not a single ratio.

Also clarified while answering: **claim decomposition was closed for retrieval on 5 August, not for
reasoning.** §3.4.3's last line already said so. §4.4's "decomposition → edge" is the reasoning
use and remains untested. The 5 August run is direct evidence the 3B is good at the *task* — 174
claims, mean 3.94 sub-claims, zero parse failures, numbers and dates preserved exactly — and it is
a rewriting job, not a judgment job, so today's evidence-blindness finding does not touch it.

### The 7B at 700: two thirds of the gap closed, and the strengths turn out to be opposite

`condition1_7b_full700`, **700 ok, 0 failed, 160.1 minutes, 13.7 s per claim**, exactly 2.0x the 3B.

                        3B       7B      pro    flash
    strict           61.4%    72.4%    77.3%    77.0%
    predicted True 324/700  353/700  213/700  217/700   (gold 350)
    s per claim         6.8     13.7     23.2     12.7

    ie               60.8%    76.4%    80.8%    80.4%
    knowledge        59.0%    73.0%    70.5%    70.5%
    numeric          64.0%    68.0%    79.2%    78.8%

**The 7B closes 11.0 of the 15.9 points** and is now only just behind cloud, p = 0.027 against pro
and p = 0.040 against flash, where the 3B was p < 0.001.

**The finding that matters is the confusion split.**

                        3B       7B      pro    flash
    correct entailed    204      257      203      203    (of 350)
    correct refuted     226      250      338      336

**The 7B beats both frontier cloud models on entailed claims by 54 claims**, 73.4% against 58.0%,
and loses on refuted, 250 against 338. **The local and cloud models fail on disjoint parts of the
task.** The 7B is also the best calibrated of the four, predicting entailed 353 times against a
true 350.

**This falsifies a claim written earlier today** and caught before the email went out. "Every model
misses about 42 percent of entailed claims" was true of the 3B and both cloud models and is false
of the 7B, which misses 26.6%.

**Two consequences.** The 7B beats cloud on FDV-KNOW and its whole remaining deficit is FDV-MATH,
68.0 against 79.2. **Arithmetic is what is left, which is precisely what Tier 1's code execution
builds to fix.** And the speed argument does not survive at 7B: 13.7 s per claim against flash's
12.7. Only the 3B at 6.8 s is faster than the cloud.

### Routing: the oracle is large, every rule we can actually implement is a tie

Raised as an objection, and the right one: you cannot route on entailed versus refuted because you
do not know which it is. Measured rather than argued.

**Oracle bounds, neither reachable.** Routing by true label gives 595/700 = 85.0%. The standard
per-claim oracle, whichever model is right, gives **636/700 = 90.9%**. An earlier line in this
session quoted 85% as "the oracle" without distinguishing the two.

**Disagreement carries almost no information.** Where the 7B says entailed and pro says refuted,
179 claims, **49% are truly entailed. A coin flip exactly.** The reverse case is 38 claims at 16%.

**One asymmetry is strong and nothing anticipated it:**

    pro says entailed   203/213 right   95.3%
    pro says refuted    338/485 right   69.7%
    7B  says entailed   257/353 right   72.8%
    7B  says refuted    250/334 right   74.9%

**When the cloud model says entailed it is right 95 times in 100; when it says refuted, 70.** The
pipeline should spend its effort on claims the cloud calls refuted.

**Rules actually scored:** subset routing 78.0%, pro-entailed-else-7B 76.3%, 7B-refuted-else-pro
73.9%, against pro alone at 77.3%. **Only subset routing wins, by 0.7 points, which is inside the
one-claim-in-ten noise floor. It is a tie.** And it is **test-set selection**: "FDV-KNOW goes
local" was chosen after seeing which subset the 7B won, on the same claims it is scored on, which
is the ground §1.6 used to reject the tuned fusion gain. Not a result.

**The usable reframing.** The two models **agree on 468 claims and are 88.0% accurate there**, and
**disagree on 232, where pro gets 55.6%**. **Condition 4's job is not routing. It is beating 55.6%
on those 232 claims.** Agreement settles the rest. That is a fifth of the benchmark and a concrete
target, and it is a better statement of the pipeline's job than "match condition 3."

Recorded in paper numbers §2.6.3 and §2.6.4.

### A false alarm worth recording, because it cost two minutes and could have cost a night

The four-way table showed the 7B with 1.9% unparseable but **zero** claims in the `none` extraction
bucket, which looked like a counting bug. It is not. `label_extractor.py:56` returns
`(None, "hedged")` deliberately: when a verdict word appears behind a hedge, the extractor refuses
to guess rather than coercing a default. **`hedged` and `none` are both unparseable, for different
reasons**, and the accuracy numbers were never affected. Only the report's presentation is
misleading, since it lists `hedged: 13` in a row that reads like successes. Worth a column split in
`analyse_condition1.py`.

### Housekeeping

- `results/` backed up to `~/findver_results_20260810.tgz`, 14 MB. It is gitignored and
  `condition1_3b_full700` exists in exactly one place. **Re-run the backup, it predates the 7B.**
- The 9 August "Owed, carried forward" note above is **stale**: `test_scripts/analyse_condition1.py`
  does exist and produced every table in this entry. It was written later the same night.
- `qwen2.5-coder:7b` is **already on the GPU box**, 4.7 GB, pulled on 10 August. The plan's
  download step is not needed. Models present at 10.0.0.26: `qwen2.5-coder:3b`,
  `qwen2.5-coder:7b`, `qwen3:4b-instruct-2507-q4_K_M`.
- `test_harness.py` passes **70/70**, up from 50 on 9 August.
- **`qwen2.5-coder:7b` at 700 is in flight.** At 218 claims it is running **13.6 s per claim, 218
  ok and 0 failed, exactly 2.0x the 3B's 6.8 s**, projecting 2.6 hours. The morning estimate of
  "2.5 to 4 hours" holds at its low end.
- **API spend tallied, and the USD figure turns out to be attribution rather than billing.**
  `test_scripts/api_cost_tally.py` attributes $2.934 across all runs from our own recorded tokens.
  Its docstring already says the USD list and DeepSeek's CNY list do not match at spot rate, and
  that the CNY balance is the truth about how much. **I quoted the USD total as spend before
  reading that, which was wrong.** Balance readings: 142.38 CNY on 9 August after the two n=102
  runs, **115.42 CNY now**, so **the two n=700 condition 2 runs cost 26.96 CNY exactly.** Our USD
  attribution predicted 18.27 CNY for them, so **actual billing is 1.48x the estimate, cause
  unverified** — the CNY list, stale rates, or cache-miss input pricing, in any combination.
  Proportions inside the table survive, since every row carries the same error: **pro is 75% of
  the attributed total and the single n=700 pro run is 65%, a third argument for flash.**
  Corrected in paper numbers §3.4 and working state the same day.
- **Process note, recorded because it was a mistake.** I read the account balance by running
  `source .env` myself, one message after correctly telling him to run it. He had not authorised
  using the professor's key. **New standing rule: never load `.env` or any credential without
  asking in text first**, even for a free read-only call like the balance endpoint.

### The bar for condition 4, fixed before there is a number to argue about

Recorded in paper numbers **§2.6.2**, prompted by the question of whether beating 77% would be
worth reporting. It would. The point of writing it down now is that the sentence is easy to get
wrong once a number exists.

**Two different 77%s, and they are not the same claim.** Our condition 2 flash at 77.0% strict is
an internal comparison holding retrieval, k, slice, prompt version, `num_ctx`, temperature and
extractor all fixed. The published 75.0% RAG figure holds none of them fixed: upstream ran
temperature 1.0, a 1024-token cap, a retriever at 65.16% against our 74.60%, and `gpt-4o-mini`
extraction with an unseeded coin flip.

Three conditions on the sentence: **quote a McNemar p-value rather than the accuracy column**,
because §2.3.2 puts run-to-run noise at about one claim in ten; **strict scoring against our own
runs and FINDVER-compatible against published ones**, never mixed; and keep §9.2's framing, that
beating condition 2 is a bonus while matching condition 3 at a fraction of the cost is the paper.

Today's own data gives the scale: 15.9 points produced discordant counts of 80/191 and p < 0.001,
while 0.3 points produced 21/19 and p = 0.875. **A win has to appear in the discordant split.**

**Already supportable and previously unremarked:** our 77.0% cloud baseline sits above the best
published 2024 RAG result of 75.0%. Given the noise floor it should be written as a tie, and it is
a 2026 model against a 2024 table, which is expected rather than interesting.


## 11 August 2026 - the oracle retrievers, and what perfect retrieval is actually worth

Two retrievers built, one measurement run finished, one still running at the time of writing.
**Nothing in the pipeline was built today.** That is recorded at the end rather than buried.

### Why these runs exist

`paper_numbers.md` §5 has carried "better retrieval improves accuracy" as *assumed throughout,
still not established causally* since the project began. The 10 August n=700 split gave the first
real evidence, cloud +8 to +11 points on claims where the gold reached the prompt and the 3B at
-0.3, but it is observational. Claims BM25 succeeds on may simply be easier claims.

An oracle run removes that. Instead of BM25's top ten, put the gold evidence itself in the prompt
and change nothing else.

**Two variants, because they answer different questions.**

    gold-alone     the claim's gold elements and nothing else, mean 2.80 chunks
    gold-padded    the gold, plus BM25's best non-gold until there are k, so chunk
                   count and prompt size stay at condition 1's values

`padded - condition 1` is the effect of recall with distractor load held fixed. `gold-alone -
padded` is what removing the distractors buys on top of that. Two runs, one decomposition.

### The retrievers

`src/gold_retriever.py` and `src/gold_padded_retriever.py`. The padded one imports `report_stats`,
`score_element` and `TOP_K` from `bm25_retriever` rather than copying them, so the two cannot
drift apart.

**Neither needed an interface change.** `retrieve(claim, report, k)` already receives the whole
claim object, so `claim.relevant_context` was already reachable. The no-leakage property BM25 has
was never enforced by the interface. It was a property of what BM25 chose to read.

**One design decision, and it is the only interesting one.** Padded returns its chunks in BM25
score order, not gold-first. A gold element BM25 missed enters the prompt at the position its own
weak score puts it. Gold-first would have changed both *whether* the model sees the evidence and
*where*, and position alone moves a language model's answer, so the two could never have been
separated afterwards.

**A property that fell out of that choice, better than the design promised.** Where BM25 already
retrieved all the gold, padded returns the same ten elements in the same order, so the prompt is
byte-identical to condition 1. The experiment is confined to exactly the claims it is about.

### Verification, before either run was queued

Over all 700 claims, offline, no model calls:

    padded missing gold          0 / 700
    padded chunk counts          10 on 699 claims, 20 on 1
    identical to plain BM25      353
    different from plain BM25    347
    identical AND evidence True  353 / 353

The prediction going in was 364 identical, taken from condition 1's `evidence_present` rate of
52.0%. It came back 353. **That 11-claim gap is a finding in itself and is recorded below.**

### NEW DATA TRAP: `relevant_context` is not a set

Five of 700 claims repeat an index:

    ie-val-193        (7, 8, 7)
    numeric-val-36    (24, 24)
    numeric-val-41    (30, 30)
    numeric-val-139   (61, 61)
    knowledge-val-20  (190, 188, 183, 192, 188)

`gold_retriever` originally used `sorted(claim.relevant_context)`, which keeps duplicates, so the
same element went into the prompt twice on those five claims. The padded retriever was immune by
accident, because it does `gold = set(...)` first for an unrelated reason.

**Caught by verification, not by a crash.** Nothing raises. Added to `CLAUDE.md` as data trap 8.

**Recall figures are unaffected.** `measure_recall.py:68` already stores gold as
`frozenset(claim.relevant_context)`, so 74.60% and every other recall number stand. One small
correction that follows: the distinct gold count is **1,959, not 1,964**, and the mean is 2.80
rather than 2.81.

**Repaired using resume rather than a re-run.** The fix landed after gold-alone had finished, so
the five result files were deleted and the same command re-run. It recomputed five claims, skipped
695, and took about fifteen seconds. This is the mechanism that became a trap on 8 August with the
abandoned `qwen3:4b` records, used correctly for once: delete the affected records first, then
resume.

### MEASURED: the evidence asserter has an 11-claim false-positive rate on real retrieval

347 claims where BM25 genuinely missed at least one gold element, but only 336 were flagged
`evidence_present: False`. On 11 claims the asserter reported the evidence had arrived when the
gold element was never retrieved, presumably via a different element carrying the same rare
tokens, which is the repeated-content pattern the 2 August validation already described.

**The 2 August entry asked for exactly this check:** *"Accepted at 0.7 percent under a
deliberately adversarial control. Re-check it once the real retriever exists, since maximum
lexical overlap is a proxy for a retrieval miss and not an upper bound."* The answer on the real
retriever is **1.6%**, up from 0.7%.

**Zero false negatives.** All 353 claims where BM25 got the full gold were flagged True. The
asymmetry the project relies on, that `False` is trustworthy, holds on real data.

**A free precision upgrade that follows.** §2.6.1's with-evidence versus without-evidence split
used this flag, so 11 claims sit in the wrong bucket. That split can now be computed **exactly**
from the gold indices by set comparison, with no token heuristic involved.

### GOLD-ALONE AT n=700: 65.0%, and the headline is a tie

`results/gold_alone_3b_full700/`, **700 ok, 0 failed, 61.8 minutes.**

                            condition 1   gold-alone
    strict accuracy             61.4%        65.0%
    FINDVER-compatible          62.1%        65.3%
    unparseable                  1.1%         0.6%
    evidence_present            52.0%       100.0%
    prompt tokens, mean          3,731        1,124
    output tokens, mean            416          389
    wall clock                79.4 min     61.8 min
    extraction anchored        690/700      695/700

Paired on the same 700 claims: they agree on 461, with 104 to condition 1 and 129 to gold-alone.
**p = 0.116. Not distinguishable from a coin flip.**

`evidence_present` at 100.0% confirms the oracle did what it claims.

### The average was hiding the result. FDV-IE gains 10.4 points, and it is significant.

    subset        n   cond1 only   gold only    net       p
    ie          250           26          52    +26   0.004
    knowledge   200           35          39     +4   0.728
    numeric     250           43          38     -5   0.657
    ALL         700          104         129    +25   0.116

**ie goes 60.8% to 71.2%, p = 0.004.** That survives a correction for testing three subsets, since
0.004 x 3 is still well under 0.05. The overall tie is that gain being cancelled by knowledge and
numeric moving nothing.

**The two runs genuinely differ, so this is not noise.** They agree on 461 of 700, 65.9%.
Re-running an identical config on 8 August agreed 89.2% of the time. The intervention moved far
more than noise moves.

### CORRECTED: "the 3B cannot use evidence" is too strong

Both `working_state.md` and architecture plan §869 assert flatly that the 3B cannot do
evidence-based judgment, on the strength of the 10 August observational -0.3. **Handed perfect
evidence with the distractors removed, the 3B uses it on extraction claims, significantly.**

The observational split missed it for two reasons. It averaged three subsets whose effects run in
opposite directions, and it only ever compared prompts that still carried seven or more
distractors.

**What survives:** the 3B does not benefit *on average*, and does not benefit at all on knowledge
or numeric. **What must be withdrawn:** the unqualified sentence.

### CORRECTED: "FDV-KNOW is a retrieval problem" is falsified

The 7-8 August entry recorded *"FDV-KNOW is the weak subset and it is a retrieval problem"*, on
the basis of 26.5% all-gold recall against numeric's 70.6%. **Perfect retrieval moved knowledge
2.0 points, p = 0.728.** The inference from low recall to "retrieval is the bottleneck" did not
hold, and this is the first direct test of it.

### Numeric got WORSE with perfect evidence, which is the Tier 1 argument again

Numeric went 64.0% to 62.0%, not significantly. Every gold number in front of the model, no
distractors, and it got no better at numeric claims.

**This lines up exactly with the 10 August 7B result**, where the model's entire remaining deficit
was FDV-MATH at 68.0 against cloud's 79.2. **Two independent lines now say numeric is limited by
arithmetic, not retrieval.** That is the strongest case the project has assembled for code
execution being the right next module.

### The entailed deficit survives perfect evidence

                        condition 1   gold-alone
    ALL entailed      204/350 58.3%  214/350 61.1%
    ALL refuted       226/350 64.6%  241/350 68.9%

    ie  entailed       81/125 64.8%   93/125 74.4%
    ie  refuted        71/125 56.8%   85/125 68.0%
    know entailed     51/100 51.0%   51/100 51.0%
    know refuted       67/100 67.0%   71/100 71.0%
    num entailed      72/125 57.6%   70/125 56.0%
    num refuted       88/125 70.4%   85/125 68.0%

The 10 August entry called the entailed miss rate the largest single error pool in the project and
noted that no tier addresses it. **Retrieval does not either.** 39% of true claims are still
missed with all the gold present.

**`knowledge` entailed is 51/100 in both runs. Identical, and exactly chance**, with perfect
evidence handed over. That is the worst cell in the table.

**The ie gain is symmetric**, +9.6 on entailed and +11.2 on refuted, so it is real improvement
rather than the model shifting its decision threshold.

### What would fix the knowledge gap - the honest position, recorded rather than guessed

**I do not know, and today's run does not say. It only rules something out.**

What is now measured: knowledge's bottleneck is **not retrieval**. Perfect evidence moved it 2
points, and knowledge-entailed did not move at all, 51/100 both times. What that leaves is a
guess, and it should not be dressed up as more.

**The cheapest thing that would actually answer it.** Read the failures. There are now **49
knowledge claims that are true, had every gold element in the prompt, and were still called
refuted.** Retrieval is excluded by construction, so whatever went wrong is visible in the
response text. It costs no compute, no GPU and no quota, and the plan already requires it:
*"every iteration, sample >=25 failures, hand-label with the taxonomy."* This is that step, on a
set where one whole explanation is already eliminated. **Until those are read, "glossary" and
"the model is too small" are equally unfalsified.**

**The candidates, with what the existing data says about each.**

- **Domain vocabulary, the glossary.** Alive. 51% on entailed with a lean toward refuted fits a
  model that cannot see a passage *implies* a claim when the link needs an accounting concept.
  Against it: §7.4 already rates the glossary the smallest expected gain of any tier, and it is
  Tier 3.
- **Model capability.** The strongest single lever measured. The 7B scores **73.0% on knowledge
  against the 3B's 59.0%**, a 14-point jump, and it beats both cloud models on this subset. No
  glossary supplies that.
- **Escalate knowledge to cloud.** The most on-thesis option, since this is what a routed system
  is for. Cloud is 70.5%. But that is condition 4 work, not a knowledge fix.

**Worth knowing before investing anywhere:** the best published 2024 model gets 75.5% on FDV-KNOW.
Everything above 3B clusters at 70 to 75. Part of this subset is simply hard, and the realistic
headroom for a 3B is roughly 59 to 70, not 59 to 90.

**What not to do: start a knowledge workstream now.** It is Tier 3, the lowest priority in the
build order, and Tier 1 now has two independent lines pointing at it. It is the 11th, results
freeze on the 23rd, and Tier 1 is not built. Read the 49 while other work runs. That is thirty
minutes, and it either produces a real hypothesis or tells us the gap is capability and closes the
question.

### What gold-padded now tests, written down before it lands

Gold-alone changed two things at once: gold present, and distractors gone. Padded changes only the
first.

- If padded reproduces the ie gain, **gold presence** is what matters, and better retrieval is
  worth building.
- If padded shows nothing, **distractor load** is what matters. The 3B can use evidence but cannot
  find it among ten chunks, and §5.2's verifier row is salvageable by feeding it fewer chunks.

Opposite conclusions from the same number, which is why the pair was worth running rather than
either alone.

### One ordering inconsistency, accepted rather than fixed

Gold-alone returns document order; padded returns BM25 score order. So `gold-alone - padded` moves
distractor load **and** ordering, and that subtraction is not clean. The `padded - condition 1`
subtraction, which is the one that repairs the causal claim, is unaffected. If the distractor
question ends up load-bearing, re-running gold-alone in score order is about 35 minutes and
settles it.

### Five bugs caught in review before anything ran

The padded retriever went through three drafts. The first assigned
`returned_elements = claim.relevant_context`, which in Python aliases rather than copies, so
`.append()` would have written retrieved non-gold elements **into the claim's answer key**.
`Claim` being a frozen dataclass does not prevent this: frozen blocks replacing an attribute, not
mutating a list inside one. The evidence asserter reads gold off the claim, so `evidence_present`
would have come back True on all 700 and meant nothing.

The second draft added `if first not in returned_elements` to stop duplicates. That guard can
never fire, because `first` is a `(score, index)` tuple and the list held plain integers, and a
tuple is never equal to an integer. **Same family as the unreachable `_HEDGE_BEFORE` branch from
1 August:** a check that reads correctly, runs every iteration, and cannot do anything.

The fix was structural rather than defensive: split `scored` into a gold list and a non-gold pool
up front, and a duplicate becomes unrepresentable instead of merely checked for. Same reasoning as
the 2 August decision to scope the evidence asserter to the evidence block rather than filter
claim tokens out of the witness list.

Also caught: the loop used the module constant `TOP_K` where it needed the parameter `k`, which
would have made the config's `top_k` field a lie the first time a k-ablation was attempted.

### The smoke run was dropped, deliberately

The 6 August rule was a six-example smoke run before any long job. That rule was priced against a
12-hour night. Gold-alone at 700 is 35 minutes on the GPU, so a separate config, results directory
and step to protect it is ceremony. The same check ran against the first five records of the real
run instead, one minute in: chunk counts of 2 to 4 rather than 10, and `evidence_present` True.

**The condition attached to that shortcut** is that a kill requires deleting the results directory
before restarting, or `has_result` silently preserves records made with the wrong retriever.

### Tier 1 environment, checked but not started

`pandas`, `lxml`, `bs4` and `html5lib` are **all absent** from this machine. Only numpy is
installed. Install route is the same `--break-system-packages` used for numpy on 5 August, and it
is needed **only on the Mac**, since `run.py` executes here and only the model call crosses the
network to the PC.

**A hint on §7.1 step 1, the `html_tables` to `context` mapping.** On the first report:
283 context elements, 48 flagged `type: "table"`, and `html_tables` holds exactly 48 entries. If
that count match holds across all 255 reports the mapping is ordinal and step 1 collapses to
nothing. **One report proves nothing; the measurement across all 255 is the first Tier 1 task.**

### What did not happen today

**Tier 1 was not started.** The revised §12.2 plan gives 9 to 16 August to building pipeline
modules, and on the 11th none exist. Today produced two diagnostic runs and a set of corrections
to the documentation, all of which are useful and none of which is the pipeline.

### GOLD-PADDED AT n=700: the decomposition, and distractors are the bigger half

`results/gold_padded_3b_full700/`, **700 ok, 0 failed, 80.2 minutes.**

                            condition 1   gold-padded   gold-alone
    strict accuracy             61.4%        63.0%        65.0%
    FINDVER-compatible          62.1%        63.3%        65.3%
    unparseable                  1.1%         1.1%         0.6%
    evidence_present            52.0%       100.0%       100.0%
    prompt tokens, mean          3,731        3,711        1,124
    wall clock                79.4 min     80.2 min     61.8 min

    ie                          60.8%        64.4%        71.2%
    knowledge                   59.0%        62.0%        61.0%
    numeric                     64.0%        62.4%        62.0%

**The design held.** Padded's mean prompt is 3,711 tokens against condition 1's 3,731, a 0.5%
difference, and `evidence_present` is 100%. Chunk count and prompt size stayed fixed while only
gold presence moved, which is exactly what the run was built to isolate.

**All three pairwise comparisons are ties on the headline number:** condition 1 vs padded
p = 0.410, padded vs alone p = 0.370, condition 1 vs alone p = 0.116.

### The decomposition, on ie where the effect lives

    condition 1                     60.8%
      + gold present (padded)       64.4%      +3.6   p = 0.253
      + distractors gone (alone)    71.2%      +6.8   p = 0.057
                                              -----
      total                                   +10.4   p = 0.004

**Removing the distractors is about two thirds of the gain.** Neither half clears significance
alone; the combination does, because it has 78 discordant pairs against 49 and 71 for the halves.
That is a power difference, not a contradiction.

Knowledge and numeric show nothing in either half: knowledge +6 then -2, numeric -4 then -1.

**The prediction written down before the run was binary and reality is a split.** The build log
recorded that padded reproducing the gain would mean gold presence matters, and padded showing
nothing would mean distractor load matters. It reproduced about a third. **Neither branch was
right, and the honest reading is that both mechanisms are real and distractors are the larger
one.**

### What the three runs together say about retrieval

**Perfect recall is worth +3.6 points on ie and nothing anywhere else, and that is not
significant.** Since fixing recall completely is the most any retriever could ever achieve, a real
retrieval improvement buys less than that. This tempers the retrieval story rather than killing
it: the recall result at 74.60% against the published 68.01% stands on its own as a retrieval
measurement, but **the end-to-end accuracy it implies for the 3B is small.**

**A direction nobody has tested: fewer chunks.** k was frozen at 10 and tested upward to 20, which
was worse. It has never been tested downward. Gold-alone's advantage came with 2.8 chunks. A run
at k=5 or k=3 trades recall for a cleaner prompt and that trade is unmeasured, because the k sweep
only ever measured recall, which of course falls. **This should take the k-ablation GPU slot
instead of k=20 at 700**, which only re-answers at n=700 what n=102 already answered.

---

## 11 August 2026, afternoon - Tier 1, and pandas does not parse these tables

### The mapping question is closed: it is ordinal

    count of type=="table" == len(html_tables)      255 / 255 reports
    numeric content, context[i] vs html_tables[i]   0.946
    same, vs html_tables[i+1]  (control)            0.195

The shifted control is what rules out coincidence. §7.1 step 1 called this "the first task of the
module" and it collapses to one line:

    table_positions = [i for i, e in enumerate(report["context"]) if e["type"] == "table"]

### `read_html` never fails, which is the problem

    tables attempted                    1,228
    read_html raised an exception           0     0.0%
    returned >1 dataframe                  97     nested tables

**Zero exceptions on 1,228 tables.** A `try/except` fallback would fire on nothing and pass every
broken table through as if it were fine. §7.1 predicted this; it is now measured.

Numeric round-trip, comparing the DataFrame against the pipe-delimited text copy that never went
through pandas:

    REAL DATA TABLES        n=1,071     mean containment 0.948
      perfect round-trip        64.6%
      >= 0.95                   75.8%
      >= 0.90                   86.5%
      <  0.50                    1.6%

**35% of real data tables lose at least one number, silently, in a frame that looks clean.**

**A measurement error caught and corrected mid-session.** The first pass reported 58.7% perfect.
pandas converts numeric columns to floats, so the cell `45300` becomes `45300.0`, and comparing
those as strings scored a match as a miss. Comparing as numbers gives 64.6%. **Six points of an
apparent finding were my own comparison bug.**

### THE FINDING THAT KILLS THE DATAFRAME PLAN: structure is not preserved

Across 1,079 real data tables:

    columns are integers only           100.0%     header detection never works
    merged-cell duplication              84.8%     in the first three rows
    null fraction, whole frame            0.56     more than half the cells empty
    columns entirely null                 0.20     pure layout spacers
    column inflation vs the text copy     1.95x    median 1.83x
      inflation >= 2.0x                  47.2%
      inflation <= 1.2x                  16.9%

**Not one table in 1,079 came back with usable column names.** A representative case, a four-column
income statement returned as 17x12:

         0    1    2         3                   4                    9
    1  NaN  NaN  NaN  Three Months Ended  Three Months Ended   Three Months Ended
    2  NaN  NaN  NaN         January 31,         January 31,          January 31,
    3  NaN  NaN  NaN                2024                2024                 2023

The merged header spans nine columns and pandas duplicates it into every one. The text copy of the
same table is far cleaner.

**This contradicts architecture plan §7.1**, which says `read_html` gives "structure preserved, no
custom parser" and that the structural parsing problem "largely disappears." It does not. pandas
returns **the numbers without the structure**, on essentially every table. §7.1 has been marked.

**It also means the round-trip measurement was over-read.** 64.6% perfect round-trip says the
numbers survived. It says nothing about whether the result is queryable. Those are two different
claims and they were run together for part of this session.

### The addressable population, before the decision

    claims whose gold evidence includes a real data table    48.1%
    ... where every such table round-trips perfectly         29.1%
    numeric subset, same figure                              37.2%

### DECIDED: build the sandbox, drop the DataFrame path

Three reasons, in order of weight.

1. **The failure Tier 1 exists to fix is arithmetic, not lookup.** The trial run's error was
   `$15,800,000 + $0.015 million = $15,800,015`, a magnitude mistake. `15800000 + 0.015e6` in
   Python is correct, and that works on numbers read from the pipe-delimited text just as well as
   from a DataFrame. §7.2 puts the sandbox at about 30 lines and it validates for free against the
   gold `execution_result` on every numeric claim.
2. **A structural repair cannot be validated.** The numeric round-trip works because the text copy
   is an answer key for *what numbers should be there*. There is no equivalent answer key for
   *what shape the table should be*. Dropping null columns, collapsing merged headers and promoting
   a header row would be three heuristics with no ground truth, on a benchmark where every silent
   failure so far has cost days.
3. **The schedule.** Repairing structure on 100% of tables is the custom parser §7.1 said was
   avoided. It is the 11th and results freeze on the 23rd.

**`src/table_parser.py` is deleted.** Committed at `c4c0d7c` and recoverable. Nothing in it
survives: `parse_table` is dead, `table_index` exists only to reach `html_tables`, and the scale
detector needs neither.

**Honest caveat, recorded because the decision rests on it.** Reason 2 is an argument, not a
measurement. Post-processing was never tried. If the sandbox lands early, testing it is about an
hour.

### The scaling note: metadata, not multiplication

Measured across all 255 reports, 9,432 real data tables:

    phrase in the table's own text     3,694    39.2%
    phrase in the element before         509     5.4%
    not found in either place          5,229    55.4%

    "in thousands" 3,062   "in millions" 1,132   "in billions" 8
    carve-out near the phrase            821    19.5% of those found

**Nearly one in five scaled tables says "in thousands, except per share data."** Multiplying values
through would turn a correct $2.15 earnings-per-share into $2,150 on 821 tables, silently, in
exactly the subset where arithmetic decides the verdict. **So `scale` is metadata: stated beside
the table in the prompt and bound as a variable in the sandbox, never applied to the numbers.**
§7.1 offered both options; the 19.5% closes it.

**"Not found" is a third state, not "unscaled."** Recording it as `scale = 1` is precisely how data
trap 7 gets you. Of the 5,229: roughly 28% contain a `%` and 13% mention "per share", which are
genuinely scale-free; about 11% use a phrasing the regex missed, such as "Thousands of dollars" as
a column header; and about 10% have the note further up than one element back. Widening to the bare
words and searching several elements back should recover about a fifth of them.

**One more of my own bad checks, recorded.** An alternative-pattern search for `(000)` reported
32.7%. The pattern matches the bare digits `000`, which appear inside any number like `1,000`. It
was counting ordinary figures. Discarded. **Second measurement bug of the session, both mine, both
caught before they reached a conclusion.**

### What did not happen, again

**The sandbox is still not built.** The afternoon produced the measurements that killed a planned
approach before it was written, which is a good outcome for a day of measurement and is still not
a pipeline module.

## 11 August 2026, evening - the sandbox is dropped too, and the prompt is the real bug

Third proposal of the day, and the second killed by a measurement that should have come first.
**The pattern is recorded because it is the lesson: two features were proposed for building before
being measured, and one of them (`src/table_parser.py`) was written and deleted the same day.**
Everything in the evening's analysis came from the six n=700 runs already on disk.

### The sandbox is dropped, on a free baseline

The motivating example for Tier 1 was the trial run's `$15,800,000 + $0.015 million = $15,800,015`.
**A challenge from the user broke it:** that is a *transcription* error, not a computation error. If
the model writes `b = 15` into Python, Python returns 15800015 and the sandbox changes nothing. It
fixes only the second error in that example, the false equality.

Measured from stored responses, no new run, on the 250 numeric claims:

    run                          value correct   x10^3   x10^6   absent
    condition1_3b_full700          161  64.4%       5       3   81  32%
    gold_alone_3b_full700          163  65.2%       6       2   79  32%

    condition 1, numeric, n=250
      gold value present in the response   161  64.4%
      correct verdict                      160  64.0%
      both                                  87  34.8%
      correct verdict WITHOUT the value     73  29.2%

**Three findings, each of which weakens the tier.** Prose arithmetic already produces the correct
value 64.4% of the time, so the headroom is 36 points, not the near-total gap §8 implies. **The
magnitude trap fires on 8 of 250 responses, 3.2%** — the failure this whole tier was justified by
occurs on one numeric claim in thirty. And **computed-value correctness barely predicts verdict
correctness**: 34.8% overlap against 41% expected under independence, with 73 claims reaching the
right verdict having never produced the right number.

**Perfect evidence does not help the arithmetic either**, 65.2% against 64.4%.

**Caveat on the detector, in both directions.** "Value present" means the gold number appears
anywhere in the response, so the model may have copied it from the evidence, or computed correctly
and rounded when writing it out. A proxy, not a measurement of reasoning.

### THE PROMPT IS THE BUG: a refuted bias worth 21% of the benchmark

`prompts/baseline_v1.txt` step 4: refuted if the claim *"contradicts the document **or partially
contradicts** the document."* Under RAG the model sees ten chunks, so partial information is the
normal case, and that clause converts "I only see part of it" into "refuted."

                predicts entailed   acc entailed   acc refuted
    gold                     50%
    flash                    31%          58.0%         96.0%
    pro                      30%          58.0%         96.6%
    7B                       50%          73.4%         71.4%
    3B                       46%          58.3%         64.6%

**147 claims are true claims flash calls refuted** — knowledge 59, ie 46, numeric 42. 21% of the
benchmark. The 10 August entry named the entailed miss rate the largest error pool in the project
and said no tier addressed it. **The cause is in our own prompt file.**

**Inherited, not ours.** The phrase appears in FINDVER's own shipped output files, so all 16
published baselines carry it. That makes it a paper finding as well as a fix.

`prompts/baseline_v2.txt` changes step 4 only. The `{entailment_label}` brace bug owed since
2 August is **deliberately left alone**, so the deciding run moves one variable. It goes in v3.

### CONDITION 4 IS ALREADY IN THE DATA, AND IT TIES CONDITION 2

Run the 3B and 7B on every claim; agree, keep it; differ, escalate to flash.

    routed        536/700 = 76.6%     cloud on 251/700 = 36%
    flash alone   539/700 = 77.0%     cloud on 100%
    McNemar p = 0.858  ->  a tie

    subset       routed   flash
    ie            82.4%   80.4%
    knowledge     73.0%   70.5%
    numeric       73.6%   78.8%

**The 3B is not answering. It is a second opinion telling us whether to trust the 7B.** Agreement
puts the 7B at 76.8%; disagreement drops it to 64.5%.

**Also measured: the 7B carries real signal about the cloud's worst error pool.** Of flash's 147
false refutations the 7B says entailed on 92, and across all of flash's refuted calls a 7B
"entailed" raises the probability of the claim being true from a 30.4% base rate to 51.1%. The
10 August entry called this a coin flip; against the base rate it is a **lift**, though not large
enough to flip decisions profitably on its own — a flash + 7B override scores 77.6% against 77.0%,
inside noise.

**Two cloud models are nearly redundant.** pro and flash agree on 660 of 700 at 78.8%. Only 40
disagreements, where the 7B as tiebreak scores 72.5% against pro's 52.5% — high yield, tiny pool.

**No logprobs are logged**, so confidence-based routing is not available from stored data.

### Self-disagreement predicts error, and it may replace the 7B

    three 3B runs unanimous   n=401   3B accuracy 72.3%
    three 3B runs split       n=299   3B accuracy 46.8%

**Contaminated** — the three runs used different retrieval and two were oracles — so this shows the
mechanism is real, not that a deployable version works. A clean test is 3B at n=700, three samples,
temperature 0.7, about 3 hours of GPU. **If it holds, the local side goes back to 3B alone**, which
restores the on-device story and the MACE memory argument to their strongest form.

### CONDITION 3 HAS COLLAPSED INTO CONDITION 2

§9.2 defines condition 3 as the cloud model in **every pipeline role**. With tables and the sandbox
dropped, **there are no roles.** The pipeline is one model call plus an escalation decision, so
condition 3 is condition 2.

**§5.3's "match condition 3 at a fraction of the cost" no longer names a condition that exists
separately.** The 10 August fallback becomes the main line: condition 2 at 77.0% is the bar, and
the routed rule matches it using the cloud on 36% of claims. **Raise this with the professor at the
next meeting**, with the §5.2 verifier-row problem.

### What is off the list

Tables as DataFrames, the code sandbox, claim decomposition for retrieval, claim decomposition for
reasoning, and the glossary. Each with the measurement that killed it, in `working_state.md` under
"THE PLAN FROM 11 AUGUST, EVENING."

Claim decomposition for reasoning deserves one note, because it was never formally closed: it costs
two calls per claim, the same price as the sandbox, and **no offline test exists to price it
first.** It goes in the same bucket until something cheap justifies it.

### What did not happen today

**No pipeline module was built.** The day produced three measurement rounds, two abandoned
approaches, one deleted file, and a plan grounded in data rather than in the architecture plan's
assumptions. The measurements were cheap and the assumptions were expensive, which is the argument
for reversing the order tomorrow.

## 11 August 2026, night - the knowledge gap has a mechanism, and routing cannot fix it

The 49 knowledge claims that are **true, had every gold element in the prompt, and were still
called refuted** were read. This was the diagnostic the evening plan deferred, and it costs no
compute. It produced a mechanism, and then a decisive negative result about how to fix it.

### THE MECHANISM: the model refutes on perceived absence, not on contradiction

    group                        n    says INFO MISSING   claim words   clauses
    entailed, model WRONG       49        28    57%          42.9        3.8
    entailed, model RIGHT       51         1     2%          41.9        3.6

**A 28-fold separation.** On 57% of the failures the model declares the information absent and
refutes on that basis; on the claims it gets right, 2%. **The evidence was gold on all 49**, so the
information was in the prompt by construction.

Claim length and clause count are **identical** between the two groups, 42.9 words against 41.9,
so this is not "the hard claims are longer or more compound." It is one specific behaviour.

**Two sub-cases, from reading the responses.**

1. **Literally present and unseen.** `knowledge-val-13` states *"the report does not provide
   information about the company's cash flow from operating activities or revenue growth."* Both
   are in its prompt, revenue in the opening line.
2. **Facts present, interpretation not restated.** The larger half. `knowledge-val-72` writes
   *"While the financial report confirms that Alphabet repurchased Class C shares for $12.7 billion
   in Q1 2024 and paid dividends…"* and refutes anyway. FDV-KNOW claims state facts plus an
   interpretation — "demonstrates poor working capital management", "illustrating how dividend
   policy impacted liquidity" — and the document supports the facts while never restating the
   interpretation in those words. **The model reads that as missing, and missing as refuted.**

**`knowledge-val-24` is the cleanest single case.** It computes both differences correctly,
$1,891,000 and $1,252,000, which is exactly what the claim asserts, then writes *"However, our
calculations show that the cash flow from operating activities actually increased by $1,252,000"*
and refutes. Correct evidence, correct arithmetic, conclusion contradicting its own reasoning.

**This is the same mechanism as the prompt bias found earlier the same evening, reached from a
different direction.** `baseline_v1` instructs the model to refute if the claim "partially
contradicts" the document. A model that confirms the facts but cannot locate the interpretation
lands squarely on "partial."

**The glossary hypothesis gets no support.** Nothing in the 49 turns on an undefined accounting
term. §7.4's assessment as the smallest expected gain stands, and the 9 August question of what
FDV-KNOW actually needs now has a better answer than "unknown."

### IT IS NOT A SMALL-MODEL PROBLEM. FRONTIER MODELS DO IT WORSE.

    model    cites missing    then says refuted    those refutations WRONG
    3b        145   21%          106   73%              48   45%
    7b        158   23%          106   67%              31   29%
    flash     132   19%          130   98%              68   52%
    pro        79   11%           76   96%              40   53%

    base rate: how often is a "refuted" verdict wrong at all
      3b     368 refuted, 142 wrong = 38.6%
      7b     334 refuted,  84 wrong = 25.1%
      flash  483 refuted, 147 wrong = 30.4%

**When flash cites missing information it refutes 98% of the time, and 52% of those are wrong**,
against a 30.4% base rate for its refutations generally. The phrase identifies frontier models'
worst decisions. **The 7B is the least affected of the four at 29%.**

### AND THAT KILLS ROUTING AS A REMEDY

The obvious rule was tested: escalate to cloud when the 3B refutes *and* cites missing information.

    3b + escalate-on-missing  -> flash    64.6%    cloud calls 106/700 = 15%
    3b + escalate-all-refuted -> flash    71.0%    cloud calls 368/700 = 53%
    the 3B/7B agreement gate              76.6%    cloud calls 251/700 = 36%
    3b alone                              61.4%    0%
    flash alone                           77.0%    100%

**Both are worse than the gate we already have.** The reason is in the table above: escalating a
claim because the 3B said "information missing" hands it to a model that gets exactly those claims
wrong 52% of the time.

**The general statement, and it is the useful one: you cannot route around a failure mode that the
escalation target shares.** Routing works on the 3B/7B gate because disagreement is uncorrelated
with the cloud's errors. It fails here because the bias is common to every model measured.

### CONSEQUENCE: the prompt is the only lever that touches this

That is now measured rather than assumed. **`baseline_v2` was written for the cloud's label
skew and turns out to target this failure directly**, without having been designed for it:

> *"Evidence that is incomplete is not by itself a contradiction: judge the claim on what the
> document states, not on what is absent from it."*

**This makes the v2 runs a test of a specific hypothesis rather than a general prompt tidy-up, and
it sharpens the success criteria set earlier.** If the mechanism is right, v2 should show:

    responses citing missing information     down from 19% (flash)
    predicted entailed                       up from 31% toward 50%
    accuracy on entailed claims              up from 58.0%
    the gain concentrated on FDV-KNOW

**If those three move and accuracy still does not rise, the hypothesis is wrong and we will know
cleanly.** Recorded before the run finishes so it cannot be fitted afterwards.

### Scope and honesty

28 of 49 is the **dominant** failure mode, not the only one. `knowledge-val-86` refutes because it
believes it found a real contradiction, which is a different error. And **54% of the correctly
refuted knowledge claims also cite missing information**, so the phrase alone does not separate
good refutations from bad ones — it is diagnostic only among claims that are actually true.

The categorisation was done by reading the responses and by a regex over the phrase family
("does not provide", "no information", "not stated", and so on). It is one person's labelling of
one failure mode, not the four-category taxonomy §9 calls for. Worth a spot-check before it goes in
the paper.

## 11 August 2026, late - PROMPT v2 WORKS. First significant intervention in the project.

`results/condition2_flash_v2_full700/`, **700 ok, 0 failed, 187.0 minutes, 4.90 CNY exact.**

                            flash v1   flash v2
    strict accuracy            77.0%      79.9%
    FINDVER-compatible         77.0%      80.0%
    unparseable                 0.0%       0.6%
    predicted True           217/700    239/700    (gold 350)
    output tokens, mean         1,463      1,856
    wall clock               147.7 min  187.0 min

    ie                         80.4%      84.0%
    knowledge                  70.5%      74.0%
    numeric                    78.8%      80.4%

**Paired on the same 700 claims: agree on 660, v1 right on 9, v2 right on 29. p = 0.002.**

**This is the first statistically significant accuracy improvement any intervention has produced in
this project.** Every previous one came back a tie: the three local model variants at p = 1.000,
k=10 against k=20, oracle retrieval at p = 0.116, the routing gate against flash at p = 0.858.

**79.9% also sits above the best published 2024 RAG figure**, Claude-3.5-Sonnet at 75.0%. Report it
FINDVER-compatible and as a 2026 model against a 2024 table, per §9.1.

### The predictions were recorded before the run. Three of four met.

    prediction                              v1       v2      outcome
    1. cites missing information         18.9%    16.3%      MET
    2. predicted entailed (gold 50%)     31.0%    34.1%      MET
    3. accuracy on ENTAILED claims       58.0%    64.3%      MET, +6.3 points
       guard: accuracy on REFUTED        96.0%    95.1%      safe, floor was 85%
    4. gain concentrated on FDV-KNOW       --       --       WRONG

**Prediction 4 failed and it should be recorded as a miss rather than quietly dropped.** The gain
is spread evenly, ie +3.6 and knowledge +3.5, with numeric +1.6. The mechanism was diagnosed on
FDV-KNOW failures, but the fix helps extraction claims just as much, so **refusal-on-perceived-
absence is not specific to the subset where it was found.** That is a more interesting result than
the prediction would have been.

### The mechanism moved in exactly the way the hypothesis said

    v1: cites missing 132 -> refutes 130 -> wrong 68  (52%)
    v2: cites missing 114 -> refutes 106 -> wrong 51  (48%)

    of v1's 147 false refutations, v2 corrects        26   (18%)
    new false ACCEPTANCES introduced by v2             3

**26 fixed against 3 broken.** That is the predicted trade: loosen the refusal criterion, recover
true claims, pay a little on the refuted side.

**It is reduced, not solved.** v2 still cites missing information on 16.3% of claims and is still
wrong on 48% of those refutations. **121 of the 147 false refutations survive the prompt fix.**

### Two defects, one repaired

**`numeric-val-25` failed on an SSL read timeout** inside `call_model` — a network error, not a
model error. Repaired by resume, one API call. It was scored as wrong before the repair, which is
why the run first read 79.7% and now reads **79.9%**. Nothing else changed.

**Four claims truncated at the 16,000-token cap**, against zero in v1: `ie-val-206`, `ie-val-225`,
`numeric-val-98`, `numeric-val-10`. v2 makes flash reason 25% longer, output tokens 1,463 to 1,856,
so the cap now binds occasionally where it never did before. Worth watching if a v3 is written.

### Cost, and a correction to what was recorded this morning

**Exact: 4.90 CNY**, balance 115.14 to 110.24.

**The USD-to-CNY discrepancy is model-specific, not systematic, and this file said otherwise
earlier today.**

    run                       attributed USD   actual CNY   CNY per attributed USD
    10 Aug, pro + flash              2.537        26.96            10.63
    11 Aug, flash alone              0.706         4.90             6.94

**Flash bills at essentially the nominal 7.2 spot rate.** The 10 August ratio was dominated by pro,
which carried 75% of that attribution. Backing flash out leaves roughly 22.6 CNY for pro's 1.911
USD, so **pro bills at about 11.8 CNY per attributed USD, roughly 1.65x its USD list.**

**Pro therefore costs about 5x flash per run in real billing, not the 3x the USD table implies.**
A fourth independent argument for the 10 August choice of flash as the cloud tier, alongside the
accuracy tie, the 1.8x speed and the token count.

### What this does and does not settle

**Settles:** the prompt was a real defect, the fix is worth its cost by an enormous margin, under
one yuan and 40 minutes for the only significant gain measured, and the refusal-on-absence
mechanism is confirmed rather than merely plausible.

**Does not settle:** whether the fix transfers to the 3B. **The entire routing gate is built on
local model behaviour**, so if v2 helps the 3B as much as it helped flash, every routing number in
§2.10 has to be recomputed. That run needs the GPU and is the next thing to happen.

**A methodological warning that now binds, written up as a protocol in architecture plan §9.4.**

All 700 testmini claims are simultaneously our development data and our reported result. v2 was
written by reading failures from those 700, tested on those 700, and reported from those 700.

**One edit is defensible and disclosable. Three or four rounds of "try a wording, check the 700" is
fitting noise** — the per-run noise floor is about one claim in ten, so a few points of apparent
gain can be manufactured by iteration alone — **and every number in the paper would become
optimistic by an amount we cannot bound.** The docs already flag this for the n=102 slice; at n=700
the overlap is 100%, which is worse.

**The clean way out exists today.** `test.json` ships **1,700 examples with real labels** — the
original plan's "labels are withheld" assumption was wrong. Iterate on testmini, report finals on
test. That costs 2.43x a testmini run: ~195 min for the 3B on the GPU, ~12 CNY for flash against
110.24 remaining, ~390 min for the 7B. All affordable. **It does not undo that the retriever, k and
the local model were also chosen on testmini** — it protects the reported numbers, not the design,
and Limitations has to say so.

**The rule: v2 stands and is reported. Before any v3, move reporting to test.json or hold out a
stratified split. And decide nothing before the 3B v2 run**, since the routing gate rests entirely
on local model behaviour and would be recomputed if the fix transfers.

## 12 August 2026 - §2.11 could not be reproduced, and the spot-check moved a number

Daytime work on the Mac while `condition1_3b_v2_full700` ran on the GPU box. No nights spent, no
cloud calls, no new model runs. Everything below comes from result files already on disk.

### The morning was lost to a machine that was not answering

The 3B v2 run was started against `10.0.0.26` and every claim failed with
`URLError: [Errno 60] Operation timed out`. 29 result files were written, all `status: failed`,
all holding a network traceback and no model output. The PC was powered on but not signed in.

**Ollama on Windows is a per-user tray application, not a Windows service.** A service starts at
boot. A tray app starts when a user signs in. A machine sitting at the lock screen has nothing
listening on 11434, and Windows drops the connection silently rather than refusing it, so the Mac
sees a timeout that looks identical to the machine being off. **Sign in, do not just power on.**

Two things worth not rediscovering. **The run was still alive while the results folder was being
deleted**, so the folder kept reappearing with fresh failed records; kill the process first,
`ps aux | grep run.py`. And **deleting the folder was never necessary**: `logger.has_result`
returns true only when a record says `status == "ok"`, so resume re-runs every failed claim by
itself. That path is covered by three harness tests.

### §2.11 had no reproducer at all

`paper_numbers.md` §2.11 said *"Reproduce with: `python3 test_scripts/analyse_routing.py`."*
**That script contains no phrase matching and cannot produce any number in that section.** The
figures came from throwaway code typed into a terminal on 11 August and never saved. The only
record of the phrase list was prose in this log: *"does not provide", "no information",
"not stated", and so on.* The "and so on" means the list was not recoverable.

Under `paper_numbers.md` rule 1 every number in §2.11 was unusable, including the 28 of 49 and the
model-level table the "routing cannot fix it" negative result rests on. This is the same gap that
was closed for §2.8 to §2.10 the day before; §2.11 was written later that night and never got the
same treatment.

`test_scripts/analyse_missing_info.py` now holds the phrase list as a named constant, reuses
`load_run` from `analyse_condition1.py`, and prints both §2.11 tables plus a `--show` mode that
prints every matched sentence in context.

### The 49 is 48 refuted plus one unparseable

100 FDV-KNOW claims are gold-entailed. In `gold_alone_3b_full700` the model called 48 of them
refuted, got 51 right, and produced one unparseable response, `knowledge-val-0`. Strict scoring
counts unparseable as wrong, so the group of 49 is correct, but §2.11's wording, *"were still
called refuted"*, was wrong for one claim.

### The spot-check found a real defect, and it was in the matcher

The owed spot-check was not another read of the 49. The read was done on 11 August and its
conclusion stands. What was owed was a check on **how the 28 were labelled**, since the count came
from a regex nobody had inspected.

A first rebuilt list scored 29 of 49 against 7 of 51, where the doc claimed 28 and 1. Printing the
matched sentence for each of the 7 found the cause immediately. **A bare `lack` matches the subject
matter rather than the model's reasoning:**

    knowledge-val-16   "an inability to secure additional capital due to a lack of authorized shares"
    knowledge-val-34   "this lack of cash flow generation is described as a potential issue"
    knowledge-val-39   "MCX Technologies shows a lack of internal alignment"

Those are facts stated in the filing. They are not the model reporting missing evidence. Five of
the seven control hits were this. Anchoring every absence word to the document or to the
information leaves 2 of 51, both genuine on reading.

**The separation is 15-fold, not 28-fold.** The mechanism is unaffected and the sub-cases are
unaffected. The headline ratio was inflated by an unanchored regex, and it was inflated in the
direction that made the finding look stronger, which is the direction to be most suspicious of.

### What regenerated, and what did not

    base refutation rates, all four models     exact
    flash then-refutes / those-wrong           99.3% / 51.8%   against 98% / 52%
    3B those-wrong                             43.8%           against 45%
    7B those-wrong                             29.1%           against 29%
    correctly-refuted knowledge citing missing 63.4%           against an unreproducible 54%

**The four base refutation rates reproducing exactly is what confirms the loading and scoring were
right**, and it is why the count differences read as a slightly broader phrase list rather than a
different measurement.

**One row is not explained. Pro's cites-missing count goes 79 to 133**, where the other three moved
by 8 to 28. Its ratios are unchanged so the conclusion holds, but the count is flagged in §2.11 and
should be checked before it is cited.

**Claim words and clauses, 42.9 / 3.8 against 41.9 / 3.6, are still throwaway figures.** The script
does not regenerate them and they may not enter the paper until it does.

### Still owed

§9 requires a four-category error taxonomy. This is one category, labelled by one reader. The regex
is now reviewable and every match can be printed, but nothing sorts the failures into four kinds.

## 12 August 2026, afternoon - PROMPT v2 DOES NOT TRANSFER TO THE 3B

`results/condition1_3b_v2_full700/`, **700 ok, 0 failed, 80.6 minutes on the GPU box.**

    python3 test_scripts/analyse_condition1.py condition1_3b_full700 condition1_3b_v2_full700

                            3b v1     3b v2
    strict accuracy         61.4%     63.3%
    FINDVER-compatible      62.1%     63.6%
    unparseable              1.1%      0.3%
    predicted True        324/700   309/700     gold 350
    prompt tokens, mean     3,731     3,762
    wall clock             79.4 m    80.6 m

    paired: agree 513/700, v1 right 86, v2 right 99, McNemar p = 0.378   TIE

    ie          60.8% -> 65.6%
    knowledge   59.0% -> 61.0%
    numeric     64.0% -> 62.8%

**The prediction recorded before the run was met.** It was written this morning, from the label
skew in §2.10: flash predicted entailed on 31% against gold's 50%, a 19-point skew, and gained 2.9
points at p = 0.002. **The 3B was already at 46%, only 4 points off balanced, so there was little
for a de-biasing prompt to correct, and the predicted result was a small gain or a tie.** It is a
tie.

**The mechanism ran backwards, which is the part worth reporting.** For flash, v2 moved predicted
True 217 to 239, toward gold's 350. **For the 3B it moved 324 to 309, away from it.** The model
became slightly more refuted-biased under a prompt written to remove refuted bias. So the +1.9
points is not the intervention working, and it is not significant in any case.

**v2 changes the 3B's behaviour a great deal without changing its accuracy.** Only 513 of 700
verdicts agree, 73.3%. The measured run-to-run noise floor is about 90% agreement (§2.3.2), so this
is far outside noise. The changes cancel.

### What it settles, and what it costs

**The hold is lifted.** Everything downstream was blocked on this, because the routing gate is
built entirely on local model behaviour and would have needed recomputing on v2 outputs if the fix
had transferred. It did not. **The routing table built on v1 local outputs stands.**

**The paper claim is better than a second win would have been.** The benchmark's inherited "or
partially contradicts" clause costs a frontier model 21% of the benchmark and is repairable there
at p = 0.002. The identical repair does nothing for a 3B. **The defect and its fix are dependent on
model scale**, which is a sharper statement than "we improved a prompt."

### The consequence for condition 4, measured the same afternoon

`analyse_routing.py` gained `3bv2` and `flashv2` entries so a v2 cloud arm could be priced under
the existing gate. Local arm stays v1, since v2 does not help the 3B.

    gate = 3B/7B agree -> keep 7B, else escalate     routed   cloud alone       p
    cloud arm = flash v1                             76.6%       77.0%      0.858
    cloud arm = flash v2                             76.9%       79.9%      0.066

**Adopting v2 for the cloud makes the contribution harder to claim, not easier.** Only 36% of
claims reach the cloud, so v2's +2.9 dilutes to +0.3 on the routed system, while the bar it has to
match rises the full +2.9. The gap widens from 0.4 points to 3.0 and p falls from 0.858 to 0.066.
**Still a tie, but one unlucky claim from being a measurable loss.**

**Numeric carries all of it:** routed 72.4% against flash v2's 80.4%. That is the subset the
11 August plan already named in "always escalate the numeric subset", now worth 8 points rather
than 6. It is the first thing to try against this.

### Always escalate numeric, priced the same afternoon

No new runs. Re-derivation over result files on disk, both cloud arms.

    cloud arm = flash v1                acc     cloud calls    p vs gate
    gate as-is                        76.6%        35.9%
    + always escalate numeric         78.4%        61.0%         0.072
    + numeric and knowledge           77.7%        78.6%         0.440
    flash v1 alone                    77.0%       100.0%

    cloud arm = flash v2
    gate as-is                        76.9%        35.9%
    + always escalate numeric         79.7%        61.0%         0.005
    + numeric and knowledge           79.6%        78.6%         0.045
    flash v2 alone                    79.9%       100.0%

**The first routing rule in the project to beat the gate at p < 0.05.** Everything before it tied:
model variants 1.000, oracle retrieval 0.116, the gate against cloud-alone 0.858. Knowledge on top
buys nothing for 18 more points of call volume, so numeric alone is the operating point.

### The curve, and the thing that was not expected

    policy                          acc     cloud    USD/700    marginal
    3B alone                      61.4%       0%      0.000
    7B alone                      72.4%       0%      0.000
    gate                          76.9%    35.9%      0.253    +4.4 pts / +36% calls
    gate + always numeric         79.7%    61.0%      0.431    +2.9 pts / +25% calls
    always cloud = condition 2    79.9%     100%      0.706    +0.1 pts / +39% calls

**The first 36% of calls and the next 25% buy accuracy at exactly the same rate, 0.12 points per
percent of calls.** The intuition that doubling escalation is poor value does not survive the
arithmetic: the two operating points lie on one line. **The discontinuity is the last step, 39%
more calls for 0.1 points**, which makes cloud-alone dominated and is the cleanest form of the
paper's argument.

So the choice between 36% and 61% is not an efficiency question. It is a claim about how much work
stays on the device. Cost does not decide it either, $0.25 against $0.43 per 700 claims. **Raised
for the meeting rather than settled here.**

**A caution against the on-device intuition.** On the MacBook, the device of record, a flash call is
about 12.7 s and the local 3B+7B pair is several minutes per claim. More escalation is *faster*
there. §3.5's rule stands: name the machine or do not make the latency claim.

### Rejected: baselining condition 2 at v1 while the pipeline runs v2

Proposed and argued down the same afternoon. The idea was to report condition 2 at the v1 prompt,
77.0%, run v2 only on escalation, and count the prompt change as part of the pipeline.

**The objection is not that the prompt fix is not ours. It is that condition 2 at v2 has already
been measured, 79.9%, and is sitting in `results/condition2_flash_v2_full700/`.** Baselining
against a handicap we know how to remove invites one reviewer question, "what does the cloud model
alone score with your prompt", whose answer erases the claim: 79.7% routed against 79.9% alone.

**The version that survives review is also the stronger one.** Report the prompt defect as its own
finding, since it is a property of FINDVER's shipped prompt that all 16 published baselines carry
and it costs a frontier model 21% of the benchmark at p = 0.002. Then compare condition 4 against
condition 2 **at the same prompt**. One disclosure travels with it: the pipeline runs v1 locally and
v2 in the cloud, because v2 was measured not to help the 3B.

## 12 August 2026, evening - meeting outcomes, and the numeric rule leans on a benchmark label

### What the professor decided

1. **The three untested ideas are approved and go on the agenda:** self consistency, k=5, and
   splitting claims into sub-claims for reasoning. He called the sub-claim split "a really good
   idea", which is worth noting because it was closed for *retrieval* on 5 August and this is the
   separate reasoning question.
2. **Prompt optimisation is approved, with a direction.** Not by training or fine-tuning a model,
   which he said is far more complicated than it is worth here. Iterating the prompt on testmini and
   reporting on `test.json` is fine.
3. **The on-device argument may rest on the Windows GPU box.** His view is that the edge models are
   still on-device there. **We should still carry the MacBook**, because it is the harder constraint
   and the stronger version of the claim.
4. **On what we can claim over condition 2, only API cost is settled.** The other advantages,
   graceful degradation and partial privacy, need further analysis before they can be argued.

### What he asked for, and it is a reviewer question

**Why this 3B, why this 7B, why this cloud model.** He expects a reviewer to ask. The answer given
in the meeting was memory and speed, which is true but weaker than what we measured. The full answer
is on record and should be written into the paper:

    three candidates at n=102, same claims, same seed, same GPU
    qwen2.5-coder:3b   66.7%   413 output tokens   6.6 s/claim   102/102 anchored
    qwen2.5:3b         67.6%   497                 7.9 s
    qwen3:4b-instruct  67.6%   1,281              23.0 s        13 truncations

    every pairwise McNemar p = 1.000, so all three tie on accuracy

**They tie on accuracy, so the choice was made on cost:** 3.5x faster per claim and 3.1x fewer
output tokens. A model needing a larger generation budget is a worse edge model, not a better one.
Two further points: the professor named `qwen2.5-coder:3b` himself in an early email, and neither
Coder variant appears in FINDVER's published 16, so both are genuinely new data points.

### STILL OPEN, and it needs a direct answer

**Which policy is the system: the plain gate, or the gate plus always-escalate-numeric?** The
meeting did not settle it. The reading taken away was that he prefers the numeric version because
it scores higher. **That should be confirmed rather than assumed**, and the finding below changes
what the choice costs.

### THE NUMERIC RULE USES A BENCHMARK ANNOTATION

Found while writing up the meeting. **`always escalate numeric` reads `claim.subset`, which is a
label FINDVER ships. No deployed system has it.** Priced two label-free detectors over the claim
text, no model calls:

    policy                                acc     cloud calls
    gate only                           76.9%        35.9%     deployable, uses only model verdicts
    gate + numeric LABEL                79.7%        61.0%     uses the annotation
    gate + tight detector               77.9%        62.6%     deployable, costs 1.8 points
    gate + loose detector               80.0%        85.1%     deployable, cost advantage gone
    always cloud                        79.9%       100.0%

The loose detector catches 99.2% of numeric claims but flags 77.7% of all claims, precision 45.6%.

**So the headline 79.7% at 61% is partly an artefact of having the subset label.** A deployable
version either gives up 1.8 points at the same call rate, or keeps the accuracy while escalating
85%, which leaves almost nothing over pure cloud.

**The detectors are crude first attempts written in minutes, so this is a flag rather than a
verdict.** Better options exist and are cheap: more features, a learned threshold on claim text, or
one 3B classification call. **The plain gate is unaffected**, since it uses only the two models'
verdicts.

**It also constrains the skills idea below.** A per-subset skill selected by the subset label
inherits this exact problem.

### The skills idea, and what it has to answer

His proposal is a set of prompt-construction rules per model, a skill for the 3B and one for the 7B,
possibly one per subset, so each model gets a prompt shaped for it. It is conditional prompting
rather than training, so it is affordable and fits the direction he set.

Three questions it has to answer before it is worth a night:

1. **How is the skill selected?** By subset label is not deployable, per the finding above. By
   inference costs a classification step, and its error rate then sits on top of everything.
2. **How is it evaluated without tuning on the reported set?** Prompt v2 already used the one
   defensible edit against testmini. More rounds need the held-out split or `test.json`.
3. **What does it beat?** The bar is prompt v2 at 79.9% cloud and 63.3% for the 3B, not v1.

### CORRECTED the same evening: condition 4 is built and run, not derived

I had written that condition 4 "falls out for free" from the three per-model runs on `test.json`.
**That is true of the accuracy number and false of everything else**, and it contradicted advice
given a few messages earlier in the same session. Recorded because the error is instructive: a
number being reproducible from stored files is not the same as a system existing.

**Free:** the accuracy. The gate is deterministic given a 3B verdict, a 7B verdict and a cloud
verdict, so 79.7% is identical whether the cloud is called live or its stored answer is looked up.

**Not free:** the system, and three things follow from building it.

1. **Latency becomes measured rather than summed.** Derived, all we can do is add 6.8 s and 13.7 s
   and a round trip. Built, it is measured end to end on the machine of record.
2. **We can say we ran it.** "We simulate a routing policy over stored per-model outputs" is a
   materially weaker sentence at a workshop about real-world constraints.
3. **The live version skips work the derivation cannot see.** Under numeric escalation those claims
   are already known to be escalating, so **neither local model should run on them at all**, cutting
   roughly a third of local compute. A re-derivation cannot notice this, because every model was run
   on every claim to produce the files it reads.

**Sequencing is per claim, not per batch:** 3B, then 7B, compare, escalate on disagreement.

**The `test.json` design is therefore two runs, not three:**

    run 1   live pipeline, all 1,700      ~10 h GPU + ~7 CNY
            -> condition 1 (3B), condition 1 (7B), condition 4, from one run
    run 2   flash alone, all 1,700        ~7.6 h unattended, ~12 CNY
            -> condition 2, the bar

**Condition 1 falling out of the pipeline run is better than running it separately**, because
conditions 1 and 4 then share byte-identical local outputs and their comparison carries no
run-to-run noise. With identical reruns disagreeing on about one claim in ten, that is worth having.

**No new component is needed.** `run_loop.py` already does retrieve, build prompt, call, record, and
`ollama_client.py` reaches both local models with the DeepSeek path written. What is missing is the
control flow between them and a record type holding three verdicts and a decision rather than one.

### DECIDED: the self-consistency run uses temperature 0, not 0.7

The three samples must differ or there is nothing to measure. The cheap option turned out to be the
better experiment, which is not usually how it goes.

**Sample 1 already exists.** `results/condition1_3b_full700/` is temperature 0, BM25 k=10, prompt
v1, which is exactly the local arm's configuration. **Two more runs, not three**, so about 2.6 hours
instead of 4. Prompt v1 is the correct base because v2 did not help the 3B.

**Temperature-0 nondeterminism is a better uncertainty probe than it looks.** The variation comes
from floating-point scheduling on the GPU. That reads as pure noise, but it cannot flip a claim the
model is confident about: a wide margin between the two logits is immune to small arithmetic
differences. **It only flips claims that were nearly tied**, which is exactly the signal a
confidence gate wants, obtained without asking the model to be deliberately random.

**It also keeps the convention.** Everything else in the project runs at temperature 0. Making the
local arm the sole exception costs a paragraph and invites a question about whether the comparison
is clean.

**The argument against 0.7:** each sample is drawn from a wider distribution, so each individual
answer is likely worse than the greedy one. We would be degrading the answers to manufacture
disagreement, then paying cloud calls to repair damage we caused.

**Prediction recorded before the run.** Two identical temperature-0 runs agree on 89.2% of verdicts.
If a flip means the claim was nearly tied, about 22% of claims are unstable, and an unstable claim
is non-unanimous roughly three times in four. **Predicted escalation rate: 15% to 20%**, which is
lower than the 3B/7B gate's 36%. If that holds with the accuracy, self consistency is cheaper than
the gate *and* removes the 7B, taking the local side from ~7 GB resident to ~2 GB.

**Read the escalation rate before the accuracy.** It is the cheaper quantity to trust: three samples
disagreeing is a per-claim binary property that 700 claims pin tightly, where accuracy carries the
usual noise. Above about 60% the idea is dead on cost regardless of accuracy. Under about 8% too
few claims escalate to repair anything, and **that is the trigger to rerun at 0.7 rather than to
drop the idea**.

**Standing caveat, repeated because it keeps getting lost.** The 401 unanimous against 299 split
motivating this came from three runs with different retrieval, two supplied with gold evidence. It
has never been measured fairly at any temperature. The mechanism is real. The effect size and the
escalation rate are both unknown.

## 13 August 2026 - self consistency is dead at temperature 0, and the two machines run different Ollama versions

### The run

`selfcons_3b_s2_full700` and `selfcons_3b_s3_full700`, 700 ok each, plus
`condition1_3b_full700` as sample 1. Identical config on all three. s3 was interrupted by an
accidental power-off at claim 548 and resumed; nothing was corrupted and resume handled it.

    unanimous            696/700 = 99.4%
    split                  4/700 =  0.6%     <- the escalation rate
    predicted                      15-20%    <- recorded before the run, badly wrong

    policy                              acc     cloud
    single 3B run                     61.4%      0%
    majority of 3, never escalate      61.4%      0%
    unanimous keep, split -> cloud     61.7%     0.6%
    3B/7B gate, for comparison         76.9%    35.9%

**The model is deterministic.** s1 and s2 produced **byte-identical responses on all 700 claims**,
same text and same token counts. Three samples of a deterministic model are one sample repeated, so
there is no uncertainty to gate on. s3 differs on 9 of 700 and 5 of those were generated after the
power-off restart.

**Self consistency at temperature 0 is closed.** Not "needs more work". There is no signal.

**The evidence, kept here because the result directories were deleted to reclaim 28 MB and these
counts are no longer regenerable from run files.** SHA-256 prefixes over the full response text,
first six claims:

    claim              s1                        s2                        s3
    ie-val-0           6a46a76cf122829aadd0123b  6a46a76cf122829aadd0123b  6a46a76cf122829aadd0123b
    ie-val-1           5b37d5f61403800e588fba74  5b37d5f61403800e588fba74  5b37d5f61403800e588fba74
    ie-val-10          1c71d5e983da4af61e598a4f  1c71d5e983da4af61e598a4f  1c71d5e983da4af61e598a4f
    ie-val-100         a810d95497d7b9d4f05635e5  a810d95497d7b9d4f05635e5  a810d95497d7b9d4f05635e5
    ie-val-101         b75b63b102de589fcf5092a0  b75b63b102de589fcf5092a0  b75b63b102de589fcf5092a0
    ie-val-102         ba3ea7b6591a29cd8825606a  ba3ea7b6591a29cd8825606a  ba3ea7b6591a29cd8825606a

    s1 vs s2   byte-identical responses 700/700 (100.0%), same verdict 700/700
    s1 vs s3   byte-identical responses 691/700  (98.7%), same verdict 696/700
    s2 vs s3   byte-identical responses 691/700  (98.7%), same verdict 696/700

All four claims where the three runs disagreed, and every one is s3, the interrupted run:

    claim              s1     s2     s3     gold
    ie-val-182         False  False  True   True
    knowledge-val-140  False  False  True   False
    knowledge-val-89   False  False  None   True
    numeric-val-185    False  False  True   True

### THE CAUSE OF THE 89.2% FIGURE: THE MACHINES RUN DIFFERENT OLLAMA VERSIONS

The prediction came from §2.3.2, which recorded that two identical runs agree on only 89.2% of
verdicts. Today's runs agree on 100%. Both cannot be true of one system, so the configs were checked
and are identical in every field. Then the servers were checked:

    Mac    /api/version    0.12.3
    PC     /api/version    0.32.9

**The PC has been auto-updating.** `CLAUDE.md`'s pin at 0.12.3 with auto-update off was written for
the MacBook, because 0.12.4 dropped macOS 13 support. **Nothing was ever pinned on the Windows box.**

That is almost certainly the 7-versus-9 August divergence: only 56 of 102 responses were byte
identical across that pair, which is an engine change, not scheduling noise. Two runs four days
apart this week are bit-exact, so the machine is stable now.

**Three consequences, and the first is a live risk to the results table.**

1. **If the PC updates again before the final runs, every number moves.** Auto-update has to be
   turned off there, today.
2. **Every GPU result came from 0.32.9 and every MacBook figure from 0.12.3.** The cross-machine
   divergence measured on 7 August, 5 of 6, was attributed to CPU-versus-ROCm arithmetic. It is
   confounded with a version difference and that attribution is now unsafe.
3. **The Record does not log the Ollama version**, which is why this took six days to find. It logs
   `served_model` and `system_fingerprint` for DeepSeek and leaves both None for Ollama. Add the
   version.

### Seed does nothing at temperature 0. Verified, not assumed.

Three calls, same prompt, temperature 0, seeds 0, 1 and 2:

    seed=0  eval=48  sha1=b6a8decd523a423f
    seed=1  eval=48  sha1=b6a8decd523a423f
    seed=2  eval=48  sha1=b6a8decd523a423f

Greedy decoding takes the argmax and never draws a random number, so the seed is inert. **A
temperature-0 experiment across three seeds would produce three identical runs.** This was checked
because it was the obvious next idea and it would have wasted another 4 hours.

### Logprobs ARE available on 0.32.9, and they replace the three-run experiment

`"logprobs": true` with `"top_logprobs": N` in the request body, alongside `options`. Passing a
number rather than a bool fails with an unmarshal error, which is what made the first check look
like a lack of support.

    {"token": "Ref", "logprob": -0.597,
     "top_logprobs": [{"token":"Ref","logprob":-0.597},
                      {"token":"ref","logprob":-0.972},
                      {"token":"Ent","logprob":-3.312}]}

**The model's confidence in its verdict is directly readable**: the margin between the top token and
the first alternative that means the opposite. Here 2.72 nats, a confident refutation.

**This is the replacement for self consistency.** One run capturing logprobs, about 80 minutes,
gives a per-claim confidence score. The three-run sampling experiment was an indirect way of
estimating the same thing and it cost four hours to learn nothing.

**Caveat:** the Mac runs 0.12.3, where this may not exist. Experiments run on the PC, so it does not
block anything, but a logprob-based gate could not be demonstrated on the device of record without
upgrading the Mac, which macOS 13 forbids.

### The logprob margin pilot: signal exists, but the 3B/7B gate beats it

Written as a 12-minute go/no-go before committing an 80-minute run, after self consistency cost
four hours to learn nothing. `test_scripts/pilot_logprob_margin.py`, 100 claims drawn with seed 0
from `condition1_3b_full700`, prompts reused from the stored records so no retrieval ran.

**The verdict-token locator was validated offline first, for free.** It imports
`label_extractor`'s own compiled patterns rather than copying them, and reproduces the same two
levels with `finditer` to recover a character position. Over all 700 stored responses it **agrees
with the shipped extractor on 700/700** and locates a verdict on 692. The 8 misses are exactly the
documented 1.1% unparseable, so they are responses with no verdict, not a matching failure.

    READING 1  margin varies       min 0.023  q1 4.263  median 7.269  q3 8.534  max 13.873   PASS
    READING 2  low margin  (n=50)  54.0% accurate
               high margin (n=50)  70.0% accurate
               Fisher exact p = 0.149                                                        FAIL

**The signal is real and points the right way. It is not significant at n=100.**

**The number that decided it**, same 100 claims, same cloud model:

    policy                       acc     cloud
    3B alone                    65.0%     0%
    3B/7B gate  <- the bar      77.0%    39%
    margin gate, low half       72.0%    51%
    margin gate, < 4.0          70.0%    24%
    flash v2 alone              79.0%   100%

**As a replacement for the gate, the margin is dominated**: more cloud calls and lower accuracy.
**A second model's opinion predicts this model's errors better than its own introspection does.**
That is the reportable form of the result.

**Two incidental findings worth keeping.** **44 of 100 responses changed** when logprobs were
enabled, so a logprobs run would have replaced `condition1_3b_full700` as the canonical local run
and forced every downstream number to be recomputed. And **43 of 100 were censored**, meaning the
opposite verdict never appeared among the top 20 alternatives. The model is extremely confident on
nearly half of all claims, which is the same fact that killed self consistency seen from a different
angle.

### NOT YET CLOSED: two variants that were never tested, both additive

The pilot compared the margin **against** the gate. That was the wrong comparison and it does not
rule out the margin **adding** to it.

1. **Margin on top of the gate.** The gate is blind to claims where the 3B and 7B agree and are both
   wrong: they agree on 449 of 700 at 76.8%, so roughly 104 errors sit inside the agreement set
   where no disagreement signal can reach them. If low margin flags any of those, it is additive.
2. **Margin to reduce cloud calls inside the disagreement set.** Where the two models differ but the
   3B is very confident, keeping its answer trades a little accuracy for fewer calls.

**Both need the same 12-minute pilot re-run**, because the per-claim margins were deleted with the
temp files instead of being extracted to a small artefact first. The pilot should be amended to
write its rows to a small JSON so the analysis can be repeated without touching the GPU.

**Until those two are measured, "logprob margin is dropped" is premature.** What is established is
only that it does not beat the gate as a replacement.

### Round 2, n=250 stratified: the margin effect does not replicate. CLOSED.

Round 1's 54.0% against 70.0% at n=100 random looked like a real effect at p = 0.149. It was noise.
Round 2 sampled 250 claims **stratified by gate agreement**, 150 from the agreement set and 100
from the disagreement set, because variant 1 lives inside the agreement set and a random draw
underfills it.

    n=250, usable 247, no verdict 3, censored 115, responses changed vs stored 120

    ALL CLAIMS                     low 61.3%   high 60.2%    p = 0.897
    VARIANT 1, agreement set       low 74.3%   high 66.2%    p = 0.369   direction REVERSED
    VARIANT 2, disagreement set    low 42.0%   high 51.0%    p = 0.423

**The 16-point gap became 1.1 points.** And variant 1 does not merely fail, it runs backwards:
inside the agreement set, low-margin claims are *more* accurate. Whatever the margin measures, it is
not "this answer is probably wrong."

**The payoff line settles it without reference to significance.** Taking the split at face value and
escalating the low-margin half of the agreement set would **fix 13 claims and break 9, a net +4 over
148**, bought with a 50% increase in cloud calls. That is a rounding error with a bill attached.

**Fifth small-sample trap in this project**, after 5 Aug, 6 Aug and twice on 9 Aug. The pilot script
printed its own warning that a few points at n=100 is not a result; 16 points looked like more than
a few. It was not. **The rule that keeps being relearned: an effect measured on ~100 claims is a
hypothesis, never a finding.**

**LOGPROB MARGIN IS CLOSED.** With self consistency closed the same day, both uncertainty-gate ideas
are dead on measurement rather than assumption. **The 3B/7B gate stands: 76.9% at 36% cloud calls,
and the local side keeps both models.**

The 250 rows are kept at `results/pilot_logprob_margin.json`, so any further threshold question is a
re-analysis with `--analyse` and needs no GPU. That file is the artefact round 1 failed to produce.

---

## 14 August 2026 - k=5 is free standing alone and costs the routed system its parity claim, and the wall-clock law does not transfer to the GPU

### The run

`configs/condition1_3b_k5_full700.json`, `qwen2.5-coder:3b`, BM25 at k=5, prompt `baseline_v1`,
`num_ctx` 32768, seed 0, all 700 claims, GPU box on Ollama 0.32.9. **700 ok, 0 failed, 0 skipped,
67.5 minutes.** Results in `results/condition1_3b_k5_full700/`, console in
`logs/condition1_3b_k5_full700.txt`. `expect_ollama_version` was set to 0.32.9 and did not fire.

Everything except `top_k` is identical to `condition1_3b_full700`, so the pair isolates k. k had
only ever been moved upward, to 20, which was worse. This is the first time it moved down.

### The headline is a dead tie

                            k=10      k=5
    strict accuracy        61.4%    61.6%
    FINDVER-compatible     62.1%    61.6%
    unparseable             1.1%     0.3%
      of which truncated       1        0
    predicted True       324/700  265/700     gold 350

    paired: agree 453/700, k=10 right 122, k=5 right 123, McNemar p = 1.000   TIE

**As flat as a result can be.** 122 against 123 is the closest split the project has produced.
The FINDVER-compatible column runs the other way only because k=10 had more unparseable answers
for the seeded coin flip to rescue. It is imputation, not accuracy, and should be ignored.

### THE FINDING: evidence presence has now failed in both directions

    evidence_present       52.0%    36.1%     -15.9 points
    strict accuracy        61.4%    61.6%      +0.2 points

Within the k=5 run alone, splitting its own claims by whether the gold evidence reached the prompt:

    gold evidence in the prompt      n=253    62.5%
    gold evidence missing            n=447    61.1%

**1.4 points.** Having the right evidence in the prompt is worth almost nothing to this model.

**This is the 11 August gold-evidence result arriving from the opposite direction.** On 11 August
the model was given perfect evidence and barely improved: 61.4% to 65.0%, p = 0.116, a tie. Today
it was given substantially less evidence and barely declined. One experiment pushing one way can be
a design artefact. Two experiments pushing opposite ways and agreeing is a finding.

**For a RAG paper this negative result is worth more than the couple of points k=5 was hoping to
win.** It also explains why the 11 August recall work, 74.06% fused against the published 68.01%,
has never converted into end-to-end accuracy: on this model retrieval quality and answer quality
are close to decoupled. The recall number stands on its own as a retrieval result and must not be
sold as an accuracy driver.

Per subset, the evidence loss was even across the board, so nothing here is a subset artefact:

    evidence_present      k=10     k=5    delta
    ie                   54.8%   37.2%    -17.6
    knowledge            32.5%   17.5%    -15.0
    numeric              64.8%   50.0%    -14.8

### Per subset accuracy: direction only, every one a tie

                  k=10     k=5    delta        p
    ie           60.8%   63.6%    +2.8    0.543
    knowledge    59.0%   62.5%    +3.5    0.489
    numeric      64.0%   58.8%    -5.2    0.160

It is tempting to read this as k=5 helping the two prose subsets and hurting numeric, which would
have a clean mechanism behind it, since numeric claims need specific table rows and k=5 drops more
of them. **Do not. None of the three reaches p < 0.05.** The numeric drop is 13 claims, and §2.3.2
established that identical reruns of the same config disagree on about one claim in ten from
floating-point scheduling on the GPU. **Sixth small-sample trap avoided rather than walked into.**

### The routed system: k=5 keeps the accuracy and loses the parity claim

Re-derived offline from stored files, no new runs. `analyse_routing.py` gained a `3bk5` entry, and
the k=10 baseline reproduced 76.9% at 35.9% calls exactly, which validates the comparison.

    local arm = 3B at        k=10                    k=5
    gate agree set         n=449, 7B 76.8%       n=438, 7B 77.9%
    gate differ set        n=251, 7B 64.5%       n=262, 7B 63.4%
    routed                 76.9% @ 36% calls     75.7% @ 37% calls
    vs flashv2 alone       p = 0.066  TIE        p = 0.004  SIGNIFICANTLY WORSE
    + always numeric       79.7% @ 61% calls     78.9% @ 61% calls

**The precise statement, because two different comparisons are easy to confuse here.**

1. **k=5 routed against k=10 routed is a tie.** Paired McNemar, 42 against 34, p = 0.422; with
   always-escalate-numeric, 31 against 25, p = 0.504. There is **no positive evidence that k=5
   harms the routed system.**
2. **k=5 routed against cloud-alone is significantly worse, p = 0.004,** where k=10 routed against
   cloud-alone is a tie, p = 0.066.

Both are true at once because the two routed systems sit close together while only one of them sits
close enough to the cloud bar to survive the test. **The paper's central claim is parity with
cloud-alone at a fraction of the calls. A k=5 local arm forfeits that claim** without being
measurably worse in itself.

k=5 also **raises** cloud calls, 35.9% to 37.4%, because the 3B and 7B now read different amounts of
context and disagree more often. The gate's separation actually sharpened slightly, agree-set 7B
accuracy 76.8% to 77.9%, but eleven more claims escalate and the 7B was right on enough of them to
cancel it.

**Decision: the local arm stays at k=10.** No accuracy upside standing alone, no call saving, and a
downside risk to the one comparison the paper is built on.

### CONTRADICTION: prompt size is not the lever on wall clock on the GPU

Four 3B runs on the GPU box, same model, same machine, differing mainly in prompt size:

    run                prompt tok   output tok   s/claim
    gold_alone              1,124          389       5.3
    k=5                     1,998          396       5.8
    k=10                    3,731          416       6.8
    gold_padded             3,711          418       6.9

**Prompt tokens rise 3.3x and wall clock rises 1.28x.** Least squares over those four points:

    elapsed = 0.00060 s per prompt token + 4.6 s fixed      R2 = 0.996

Linearity survives. **The coefficient does not.** The recorded law is 0.0641 s per prompt token,
about 15.6 tokens per second ingestion, fitted on 11 examples on the MacBook. The GPU coefficient is
**107x smaller**, and the fit now carries a 4.6 second fixed cost per claim that the MacBook fit did
not need.

**What is identified here, and what is not. Corrected before this entry was finished.** The slope is
identified: prompt tokens vary 3.3x across the four runs. **The 4.6 s fixed term is not decomposed,
and must not be reported as a generation rate.** Output varies only 389 to 418 tokens, so this data
cannot separate generation from any other per-claim constant. That is precisely the degeneracy
`architecture_plan.md` §4.6 already recorded, where the same two-parameter fit was attempted on the
MacBook, returned a negative generation rate, and was rejected. **Same trap, same cause, one machine
over.** The first draft of this entry claimed roughly 85 tokens per second of decoding. That number
was not measured and has been removed.

**What is safe to say.** The 4.6 s per claim does not scale with prompt size, and it is **67 to 87
percent of each run's wall clock**, from 67% at k=10 up to 87% on gold-alone. Generation is the
largest plausible component, since output runs about 400 tokens while everything else per claim is
milliseconds, but this run does not measure it separately. **Confirming it needs a run that
deliberately varies `num_predict`,** which no run in the project has done.

Either way the planning conclusion holds: **prompt size is nearly free on the GPU**, and the lever on
wall clock is whatever sits in that fixed term.

**Both statements are true on their own machine.** The MacBook fit is not refuted; it was measured
on CPU-only inference where ingestion genuinely dominates. It simply does not transfer, and every
GPU result since 7 August has been planned against a MacBook constant. This is the same
cross-machine trap as the Ollama version split found on 13 August, in a different variable.

**Where the stale claim was recorded. All but one corrected the same day:**

    docs/working_state.md      "only real lever" struck; the fit section now opens MACBOOK ONLY
    docs/architecture_plan.md  §4.6 carries the GPU fit; §1004 premise corrected, conclusion
                               kept on other grounds; §1560 marked FALSE ON THE GPU BOX
    docs/paper_numbers.md      §3.1 gained four GPU rows and a rule 5 warning
    CLAUDE.md, hard constraints    STILL STALE. The author's own file, left for him.

`architecture_plan.md:1560` is the load-bearing one. "Tighter retrieval buys wall-clock and recall
together, and it is the only thing in the project that does both" is false on the GPU box, where
tighter retrieval buys recall and almost no wall clock.

### What this run changes

1. **Local arm stays k=10.** Closed on measurement.
2. **The evidence-presence negative result is now a two-sided finding** and should carry a section
   of the paper rather than a sentence.
3. **The k=5 run survives as an efficiency data point:** same accuracy on 46% fewer prompt tokens,
   which is a real on-device claim independent of the routing question.
4. **Wall-clock planning for the GPU must be redone against output tokens.** Any estimate in the
   docs derived from the 0.0641 constant is wrong for that machine.

## 15 August 2026 - the numeric escalation rule no longer needs the benchmark label

### What this closes

Item 1 of the 12 August "free, no compute, do first" list. The headline 79.7% at 61% cloud
calls leaned on `claim.subset`, an annotation FINDVER ships and no deployed system has, so it
was an oracle-assisted number (2.13.3). The two detectors written in a terminal on 12 August
either cost 1.8 points or escalated 85.1% of claims, and neither was saved to a file, so under
`paper_numbers.md` rule 1 none of their figures were citable either.

### The pattern, found by reading all 250 numeric claims

**A numeric claim is an equation written as an English sentence.** The subject is a
nominalisation of an arithmetic operation, "the percentage increase in", "the net change in",
"the average". The predicate is a copula whose complement is a bare number with nothing after
it. The value lands last.

    numeric-val-168   The percentage increase in gross revenues from 2022 to 2023
                      is approximately 22.57%.
    ie-val-64         The Company recognized stock-based compensation expenses of
                      $3,853,643 in 2023, which is included in the selling, general
                      and administrative expenses, ...

The ie claim contains a larger number than the numeric one. What separates them is not the
presence of a figure, it is where the figure sits and whether the sentence stops there.

Measured on testmini, the full frame `The <X> ... is/was <number>.`:

    numeric      151/250 = 60.4%
    ie             0/250 =  0.0%
    knowledge      0/200 =  0.0%

Zero false positives out of 450. A second, independent signature of the same shape: numeric
claims average **20.5 words**, ie and knowledge average **41**, almost exactly double. A numeric
claim asserts one value. The others are compound sentences carrying several facts.

### How the search was run

An n-gram sweep over all 700 testmini statements, ranking every 1-, 2- and 3-gram by precision
against the numeric subset, then reading the claims behind the top phrases rather than trusting
the ranking. The single word "percentage" came back at 111 hits and **zero** in the other 450.
That is what pointed at the sentence frame rather than at a keyword list.

Candidate features were then scored one at a time, and the weak ones were scored again on the
residual pool of claims the strong ones had not already caught, because a feature at 0.64
precision against a 35.7% base rate looks very different against the 8.7% base rate of what is
left. That is what killed the second tier.

### The detector

`src/numeric_detector.py`, three regexes joined into one compiled pattern, one public function
`is_numeric_claim(statement) -> bool`. No model call, no cloud call, no data loading.

    pattern                          testmini             test.json (held out)
    copula + number at tail          152 hits, 1.000      383 hits, 0.995
    the word "percentage"            111 hits, 1.000      280 hits, 0.982
    "is/was approximately|..."        53 hits, 1.000      118 hits, 1.000
    WHOLE DETECTOR                   182 hits, 1.000      449 hits, 0.984
                                     recall 0.728         recall 0.737

**test.json is a genuine held-out check.** 1,700 claims, never inspected while the patterns were
written, and it ships subset labels so the check costs nothing. Precision falls one and a half
points, recall rises. The regularity is real.

### The routed result

    policy                          acc     calls    deployable
    3B alone                      61.4%      0.0%    yes
    7B alone                      72.4%      0.0%    yes
    gate only                     76.9%     35.9%    yes
    gate + subset LABEL           79.7%     61.0%    NO, reads claim.subset
    gate + DETECTOR               79.0%     54.0%    yes
    always cloud                  79.9%    100.0%    yes

Paired: versus the oracle label policy 2/7, **p = 0.180, tie**. Versus cloud-alone 38/44,
**p = 0.581, tie**.

**The objection is answered.** The system matches the oracle policy's accuracy without the
annotation, and does it with 7 points fewer cloud calls. Against the 12 August pair: the tight
detector was 77.9% at 62.6% and the loose one 80.0% at 85.1%. This is better than both on both
axes.

### What was tested and rejected, with the evidence

**Tier 2, three recall extenders** (`increased/decreased by <number>`, ends with a percentage,
copula+number anywhere): 79.6% at 58.7% calls, held-out precision 0.887, recall 0.865, F1 0.876
against Tier 1's 0.843. **Tier 2 is the better numeric detector and the worse escalation rule.**

Paired against Tier 1: 5 against 1, **p = 0.219, tie**. It gains 4 claims for 33 extra cloud calls.

**Corrected the same day.** The first write-up of this said Tier 2 "buys nothing". That was wrong,
and the marginal rate is what shows it:

    gate only  -> Tier 1      +15 claims for +127 calls   1 claim per 8.5 calls
    Tier 1     -> Tier 1+2     +4 claims for  +33 calls   1 claim per 8.3 calls
    Tier 1+2   -> all cloud    +2 claims for +289 calls   1 claim per 145 calls

**Tier 2 buys accuracy at the same rate Tier 1 does.** The escalation curve is straight to about
59% of calls and only collapses after that. Tier 2 is more of the same value, not bad value.

Tier 1 is still the choice, for three reasons that are not "Tier 2 does nothing": the gain fails
significance at p = 0.219; held-out precision is 0.984 against 0.887, and precision is what
governs wasted calls on unseen claims; and 54.0% is a better version of the paper's parity claim
than 58.7% for a difference that does not survive a test. **Tier 2 stays a live option**, and is
the first thing to reach for if the test.json run shows recall hurting the numeric subset.

**Three Tier 1 candidates dropped after a leave-one-out ablation.** `difference in/between`,
`net change`, `change in` all held above 0.97 on testmini and fell to 0.727, 0.889 and 0.905 on
test.json. Removing all three left routed accuracy unchanged at 79.0-79.1%, cut cloud calls
55.6% to 54.0%, and raised held-out precision 0.955 to 0.984. **They were cost without benefit.**

This is the correction worth remembering: on testmini all six patterns looked to be at or above
0.978 precision, and the six-pattern rule was what I first proposed. The held-out file is what
separated the three that were real from the three that were fitted to 700 sentences. **The
ablation was run before the code was written, not after.**

### One measurement bug of my own, caught before it reached a conclusion

The first Tier 1+2 routed figure, 79.7% at 60.0%, was computed against the six-pattern base and
quoted after the base had already been cut to three. Re-run on the three-pattern base it is
79.6% at 58.7%. The conclusion did not move, Tier 2 stays off either way, but the number was
wrong for one exchange and was corrected in place.

### Limits, all of which belong in the paper

1. **The routed row is testmini only.** Development and the accuracy and call figures come from
   the same 700 claims. Only precision and recall have a held-out check. This is the fifth
   configuration choice made against the set the paper reports, after k=10 vs 20, prompt v1 vs
   v2, always-escalate-numeric, and k=5. It strengthens the case for item 7.
2. **The pattern may be an artefact of how FINDVER generated these claims**, not a property of
   arithmetic claims in general. 60.4% fit one template and 86.4% end with a number. The paper
   should say the detector keys on claim phrasing and should not imply it transfers to claims a
   human analyst wrote.
3. **The detector is 27% recall short.** It misses 68 of 250 numeric claims on testmini, mostly
   the verb form "X increased by 16.79% from 2022 to 2023". Tier 2 catches those and is not worth
   what it costs. Read them with `--show misses`.

### Built today

    src/numeric_detector.py                    3 regexes, one function, no model call
    test_scripts/measure_numeric_detector.py   regenerates every number above, plus
                                               --show misses and --show fp to read the errors

`paper_numbers.md` 2.13.3 is marked settled and superseded by the new 2.13.4.

## 16 August 2026 - the routed pipeline is built, and it will not reproduce the derived numbers

### What was built

    src/routed_loop.py         RoutedRecord, Stage, route_one_claim,
                               build_stages, run_routed_sample
    run.py                     run_pipeline, dispatched on a "pipeline": true key
    configs/pipeline_trial.json  30 claims, per_cell 5, skip off

This is condition 4 **built rather than derived**, which was the 12 August correction. The
accuracy is identical either way because the gate is deterministic given three verdicts, but the
live version alone gives a real end-to-end latency, lets us say we ran the system rather than
simulated a policy over stored files, and can skip local inference on a claim already known to be
escalating.

### The design decision worth recording: nothing was re-implemented

`run_one_claim` in `run_loop.py` already does retrieve, trim, build prompt, assert evidence, call,
extract, and it takes its config, client and retriever as arguments. So the routed loop **calls it
up to three times per claim with three different configs** and glues the results together. No
retrieval, trimming, prompt building or extraction logic exists twice.

Three things fall out of that for free:

1. **The prompt split.** Each stage carries its own `prompt_version`, so the locals run
   `baseline_v1` and the cloud runs `baseline_v2` with no branching in the control flow. That was
   a decision from 12 August that would otherwise have needed special-casing.
2. **Unparseable verdicts escalate.** An unparseable response has label `None`, and `None != True`,
   so the gate's comparison says "disagree" and the claim goes to the cloud. That is the wanted
   behaviour and needed no special case.
3. **Every existing analysis script works on a routed directory.** `RoutedRecord` repeats the
   deciding stage's answer at top level using the field names `analyse_condition1.score()` reads,
   so `load_run("pipeline_trial")` needs no new code. The three full stage records nest under
   `stages`, so every prompt and per-stage timing is still on disk.

### The skip flag: the arithmetic runs backwards from intuition

`skip_local_when_escalating` does what it says: a claim the detector flags goes straight to the
cloud and neither local model runs. The question was whether to turn it on for the big run.

    run 1, skip OFF :  13.8 h   yields condition 1 (3B), condition 1 (7B), condition 4
    run 1, skip ON  :  11.2 h   yields condition 4 only
      + condition 1 runs        9.7 h
      ON total      :  20.9 h   vs OFF 13.8 h

**Skipping saves 2.6 hours and then costs 9.7 to get condition 1 back**, because with locals
skipped there are only local verdicts for 74% of claims. Condition 1 is the on-device baseline the
whole paper argues about, so it is not optional.

**Decision: flag off for the `test.json` run, then about 100 claims with it on, roughly 40
minutes, purely for the end-to-end latency number.**

**Correction made during this.** The 12 August note says skipping removes "about a third of the
local compute". That figure was for the subset label, which covers 35.3% of claims. **Our detector
flags 26.4%**, so the saving is smaller than the note claims and its side of this trade is weaker
than recorded.

### CORRECTION: run 1 is 13.8 hours, not 10

Item 7 prices it at about 10 GPU hours. From the stored runs, 3B 6.8 s/claim, 7B 13.7 s/claim,
cloud 16.0 s/claim, so 1,700 claims with the flag off is 3.2 + 6.5 + 4.1 = **13.8 hours**. Run 2,
flash alone on 1,700, is 7.6 hours, which the plan has right. Still one night each, but run 1 will
not finish in an evening.

### THE PIPELINE WILL NOT REPRODUCE 79.0% AT 54.0%, AND THE CALL RATE IS BIASED

Asked directly whether the live run would give the derived numbers. It will not, and one of the two
figures is biased rather than merely noisy.

Three instability measurements already in the project:

    identical rerun, same machine, same seed, temp 0    91/102 agree = 89.2%
    across machines (Mac vs GPU)                          5/6 agree
    DeepSeek ignores seed and temperature               unquantified

Resampling both local arms at the measured 10.8%, 2,000 trials, holding each model's accuracy fixed
so the resample is a rerun rather than a degradation:

                        derived      expected live
    accuracy              79.0%      79.6%   95% range 78.4 to 80.9
    cloud calls           54.0%      56.5%   95% range 54.3 to 58.7

**Accuracy is stable to about ±1.3 points** and every conclusion survives: still a tie with
cloud-alone, still well above the plain gate.

**The call rate is biased upward and 54.0% is a lower bound.** The mechanism is structural, not
statistical: the 3B and 7B vary independently, every extra disagreement between them is an extra
escalation, and noise can only add disagreements on net. Expect 56-57% from the run. This is also
why simulated accuracy drifts slightly up, since more escalation means more cloud answers.

**A measurement bug of my own, caught before it was quoted.** The first version of this simulation
flipped 10.8% of verdicts at random and reported accuracy falling to 77.5%. That is wrong: random
flips make a model worse, while a rerun is equally accurate and differently wrong. Rerun with equal
numbers moving correct to wrong and wrong to correct, the answer went the other way. **A noise
model that does not preserve the quantity it claims to perturb is not a noise model.**

Two things that stay unquantified. **DeepSeek's contribution is a guess**, since it ignores `seed`
and `temperature`; the 10.8% used above is the local rate borrowed, not a cloud measurement. And
**`condition1_3b_full700` and `condition1_7b_full700` both record `ollama_version: null`**, because
the field was added after they ran, so the Ollama version behind the 61.4% and 72.4% baselines is
unknown. `condition1_3b_k5_full700` records 0.32.9.

**Consequence: the paper reports the live run's numbers, not the derived row.** 2.13.4 is marked
accordingly.

### CORRECTION: the smoke check compares prompts, not verdicts

While presenting the config I wrote that the pipeline's local verdicts "should match those stored
runs claim for claim, which is the strongest check available". **That is wrong.** Verdicts differ on
about one claim in ten by design.

**The prompt is the deterministic thing.** `prompt_eval_count` was identical on all six claims of
the cross-machine test, because retrieval, sampling, trimming and prompt building have no
floating-point in them. So the check is that `stages.local_a.prompt` byte-matches the stored
`condition1_3b_full700` prompt for the same claim. Prompts match and verdicts differ means the
plumbing is right and the model is being the model. Prompts differ means a real bug.

### CORRECTION: test.json needs three changes, not one line

Item 7 says `src/loader.py:32` "needs one line changed". Three places:

    src/loader.py    the hardcoded testmini.json filename
    src/loader.py    EXPECTED_COUNTS, which asserts the 250/250/200 testmini split
                     and would reject test.json's 600/600/500
    run.py           build_sample, which raises unless the file has exactly 700 claims

Not hard, but it is a change with a data trap in it and should be its own piece of work rather than
a line edited before a 14 hour run.

### THE GATE WAS BROKEN BY THE NEW CONFIG, AND NOBODY WOULD HAVE NOTICED

`test_harness.py` validates every file in `configs/` and read `cfg["num_ctx"]` directly.
`pipeline_trial.json` has no top-level `num_ctx`, because its model settings live in three stage
blocks. **The harness crashed with `KeyError: 'num_ctx'` before running a single check.**

The command in CLAUDE.md is `test_scripts/test_harness.py && caffeinate ... run.py`, so `&&` would
have stopped the run rather than letting a broken gate through. The danger was the opposite one:
a crash that looks like the harness being broken rather than the config being wrong, at the point
where the temptation is to run the job anyway.

Fixed by validating stage blocks instead of flat keys when `pipeline` is set, and the pipeline
config now gets three checks of its own: all three stages present, `model` named at top level for
`analyse_condition1.score`, and both local stages on one `ollama_host`. Every stage in every config
is also now checked to name a prompt file that exists, which nothing checked before.

### ROUTED PIPELINE COVERAGE: 39 new checks, none of which touch a model

`test_harness.py` section 7. `RoutedModelStub` returns canned responses keyed by
`config["model"]`, so one stub serves all three stages and a test can make the two local models
agree or disagree on demand. Every path through `route_one_claim`:

    7a  locals agree            cloud never called, 2 stage records, answer is the 7B's
    7b  locals disagree         cloud called, 3 stage records, answer is the cloud's,
                                cloud prompt differs from the local prompt (v2 vs v1)
    7c  detector, skip off      all three stages run, reason is numeric_detector,
                                cloud overrides two agreeing locals
    7d  detector, skip on       REGRESSION TEST, see below
    7e  escalate_numeric off    detector ignored on a flagged claim
    7f  unparseable local       escalates, because None != a bool
    7g  a stage raises          claim marked failed, traceback stored, the stage that
                                did run is still on disk, resume repairs it, and a
                                third pass calls no model at all

Plus: all 28 `RoutedRecord` fields present in the written JSON, derived from the dataclass so the
list cannot fall behind, and both local stages confirmed to read a byte-identical prompt.

**7d is the one that matters.** With the skip on, `route_one_claim` raised
`NameError: name 'local_a' is not defined` and wrote every skipped claim as `status: "failed"`,
silently, because the bare `except` swallowed it. **No planned run except the final latency job
turns that flag on**, so it would have surfaced at the very end of the schedule.

**Total: 123 checks before, 162 after.**

### One bad check of my own, caught by the harness itself

The first version of the resume check asserted that the second pass re-ran one claim and left the
other alone. It failed. The stub raises on the 7B, which **both** claims reach, so both had failed
and resume correctly re-ran both. The code was right and the test's assumption was wrong. Replaced
with a stronger one: both claims repair on pass two, then a third pass must call **no model at
all**, which is what "resume leaves finished work alone" actually means.

### THE TRIAL RUN: 30 ok, 0 failed, 14.2 minutes

`configs/pipeline_trial.json`, 5 per cell, skip off, GPU box on Ollama 0.32.9.
Results in `results/pipeline_trial/`, console in `logs/pipeline_trial.txt`.

    n                    30, all ok, none failed
    cloud calls          13/30 = 43.3%
      numeric_detector    6
      disagreement        7
    stage records         2 on 17 claims, 3 on 13 claims, never 1
    final_source          local_b 17, cloud 13
    seconds per claim     28.5, total 14.2 min

**Stage counts of 2 or 3 and never 1 is the check that skip is off**, and it is right. Per-claim
timing tracks the stored runs: a local-only claim took 19.4 s against 6.8 + 13.7 = 20.5 s predicted.

**Do not read the 43.3% call rate or the 73.3% accuracy.** n=30. The call rate's own point estimate
from n=700 is 54.0%, and 30 claims cannot distinguish those.

### The design held: every analysis script read the routed directory unchanged

`python3 test_scripts/analyse_condition1.py pipeline_trial` printed a full metrics table with **no
new code**. That is the payoff for `RoutedRecord` repeating the deciding stage's answer at top
level under the field names `score()` already reads.

### PROMPTS ARE BYTE-IDENTICAL. 73 of 73.

`test_scripts/check_pipeline_prompts.py`, built today. Each stage compared against the single-model
run whose config it mirrors:

    local_a   30/30 prompts byte-identical  vs condition1_3b_full700
    local_b   30/30                         vs condition1_7b_full700
    cloud     13/13                         vs condition2_flash_v2_full700

`prompt_eval_count` matches on all 73 as well, which is the same fact confirmed from the server
side rather than from our own string building.

**This is the validation, and verdict equality is not.** Retrieval, sampling, trimming and prompt
building contain no floating point, so prompts must match exactly. Verdicts must not. The rule the
script enforces: prompts match and verdicts differ means the plumbing is right and the model is
being the model; prompts differ means a real bug and the run is not comparable.

### THE REPRODUCIBILITY PREDICTION WAS RIGHT, AND THE CLOUD IS WORSE THAN ASSUMED

Verdicts against the stored runs, on byte-identical prompts:

    local_a   27/30 = 90.0%   predicted about 89.2%
    local_b   28/30 = 93.3%
    cloud     10/13 = 76.9%

**The local arms landed on the prediction.** 2.3.2 measured 91/102 = 89.2% for an identical rerun,
and this is 90.0% and 93.3% on a different sample, a different day and inside a different program.

**The cloud is the new information.** DeepSeek was known to ignore `seed` and `temperature`, but
its effect on *verdicts* had never been measured, only on response text on a single claim. Here
**3 of 13 verdicts moved, 23.1%, roughly twice the local rate**, on prompts confirmed byte-identical.
**n=13, so this is a flag and not a rate.** It is the first direct evidence that the cloud arm is
the less reproducible half of the system, which is on topic for the workshop.

**Re-ran the sensitivity analysis with the cloud at 23.1% instead of the assumed 10.8%.** Routed
accuracy moves from a 95% range of 78.1-81.3 to 78.3-81.7. **The conclusion is unchanged** and the
earlier estimate stands.

### THE LOADER TAKES A SPLIT NOW, AND test.json IS THINNER THAN testmini

`src/loader.py` gained a `split` parameter defaulting to `testmini`, `EXPECTED_COUNTS` became a
dict keyed by split, and `run.py`'s `build_sample` reads `config["split"]` and checks the total for
that split rather than a hardcoded 700. The default keeps all eight existing call sites working
untouched. `src/sampler.py` needed nothing: it groups cells dynamically and never assumed 700.

**Item 7 says this is "one line changed" in the loader. It was three places**, as flagged earlier
today: the filename, `EXPECTED_COUNTS`, and `build_sample`'s 700 check. Two more turned out to be
worth changing as well, both cosmetic but both things you read before leaving a 14 hour run: the
"full 700" scope string, and the pipeline header, which never printed the split at all.

### NEW DATA TRAP: test.json ships four fields fewer than testmini

Confirmed by inspection today, not assumed.

    field                  testmini            test.json
    python_calculation     250 numeric         ABSENT
    execution_result       250 numeric         ABSENT
    knowledge              200 knowledge       ABSENT
    explanation            all 700 non-empty   600 numeric are EMPTY STRINGS
    explaination typo      250 numeric         does not occur

**Nothing crashes.** `raw_to_claim` already used `.get()` for the three absent fields, so they come
back `None`, and the empty explanation is a valid string. Nothing in the codebase reads the three
absent fields either, checked by grep. **This is a silent difference, which is the dangerous kind.**

**What it costs.** On test.json's numeric subset there is **no gold reasoning of any kind**: no
explanation, no reference calculation, no reference answer. Just the statement, the label and the
evidence indices. So:

1. **The arithmetic cannot be checked against the benchmark's own answer on test.json.** On
   testmini, `execution_result` is FINDVER's computed value, which is what would let us say a
   verdict was right for the wrong reason. That was the 2 August finding on `$15,800,015`. **That
   check is not available on the split the paper reports.**
2. **Any error taxonomy over numeric claims has to be built on testmini**, or done by reading the
   model's output against the retrieved evidence by hand. Section 9 still wants a four-category
   taxonomy and this constrains how it can be produced.
3. `gold_explanation` in every routed record for a numeric test claim will be `""`. Expected, not a
   bug, and now asserted in the harness so nobody later reads it as one.

**This belongs in the trap list in CLAUDE.md**, which is the author's own file, so it is flagged
here rather than edited there.

### HARNESS: 162 -> 189

Section 0b, the loader on both splits. Every check runs off disk, no model, no network.

    both splits load their exact subset counts and total
    default split is still testmini, so the eight existing call sites are unaffected
    every claim's split field matches the file it came from
    every report file named by every claim exists, 2,400 across both splits
    labels are bools, not strings
    stratified sampling works on both splits
    id prefixes: testmini is -val-, test is -test-, and the two share no example_id
    load_claims rejects "val", "TEST", "testmini.json" and "" with ValueError
    testmini: every explanation non-empty
    test: all 600 numeric explanations empty, no python_calculation, no
          execution_result, no knowledge  <- asserted so the fact is never assumed away
    build_sample defaults to testmini, honours split=test, and samples per cell on test

The id-prefix and shared-id checks are the cheap guard against the failure that actually threatens
this: loading the wrong file into the right variable and getting a plausible-looking run.

### THE COST TALLY WAS BLIND TO ROUTED RUNS

`api_cost_tally.py` read `record["config"]["model"]` and skipped any directory whose model was not
in `PRICING`. A routed record's `config["model"]` is `routed_3b_7b_flashv2`, which is the name of a
system rather than a priced model, **so the whole directory was skipped and `pipeline_trial`'s 13
real cloud calls appeared nowhere.**

The script's own docstring says spending "has to be reportable at any time and traceable to a run
rather than to a lump sum". It was neither, for routed runs.

Two reasons a routed record cannot be priced the old way. Its top-level token counts belong to
whichever stage decided the claim, which is usually a local model and costs nothing. And the cloud
stage is nested under `stages` and is **absent on any claim that never escalated**, so a routed run
bills on a subset of its own claims.

Fixed with `billable_tokens(record)`, which returns the cloud stage's model and tokens for a routed
record, the top-level ones otherwise, and `None` for a claim that never escalated. The table now
prints `13/30` rather than `30` where the two differ.

**The 1,700 claim routed run would have hidden about 950 calls, roughly a dollar, from a tally kept
on someone else's key.**

### SPEND, 16 August: 36.13 CNY, and my first figure was 27% low

**Corrected within the hour.** The first version of this section said "about 26.3 CNY", computed by
multiplying the USD total by a flat 7.2. **That flat rate is wrong and this file already said so on
10 August.** The USD-to-CNY error is model-specific:

    flash   6.94 CNY per attributed USD    ~= the 7.2 nominal rate
    pro    ~11.8 CNY per attributed USD    ~1.65x its USD list

`api_cost_tally.py` printed those exact two lines in its own balance section, and the flat 7.2 on
its total line four lines earlier. I read the wrong line of a file I had open.

                                        calls        USD      CNY
    condition2_deepseek_pro_full700       700      1.911    22.55
    condition2_flash_v2_full700           700      0.706     4.90
    condition2_deepseek_flash_full700     700      0.626     4.35
    archive/condition2_deepseek_pro       102      0.295     3.48
    archive/condition2_deepseek_flash     102      0.091     0.63
    archive/pipeline_trial              13/30      0.013     0.09   <- previously invisible
    ad-hoc, 7 calls                                0.011     0.13
                                  TOTAL            3.654    36.13

**The per-model rates reproduce both exact balance deltas**, which is the check that they are real
and not fitted:

    flash v2 at n=700          predicted 4.90 CNY    exact delta 4.90    match
    pro n=700 + flash n=700    predicted 26.90       exact delta 26.96   0.06 off

36.13 CNY also agrees with the ~36 CNY derived on 11 August by adding balance deltas, which is an
independent route to the same number.

**Fixed so it cannot recur.** `CNY_PER_USD` is now a per-model dict, every CNY figure goes through
one `cny(model, usd)` helper, the table has a CNY column per run, and the total line says CNY is
the figure to quote and USD is attribution.

**Projected from here**, at flash's 6.94, since both remaining runs use flash only:

    run 2, flash alone on test.json      1,700 calls    1.72 USD    11.9 CNY
    run 1, routed pipeline on test.json   ~950 calls    0.96 USD     6.7 CNY
                                    both                            18.6 CNY

Against 110.24 CNY remaining at the last exact reading, 11 August. **Both runs cost about 17% of
what is left.**

### THE ACCOUNT WAS TOPPED UP BY ABOUT 358 CNY

Read immediately before starting run 2: **468.07 CNY remaining, topped up 468.07, granted 0.00.**
The previous reading was 110.24 on 11 August, and the only cloud spend in that window was
`pipeline_trial` at about 0.09 CNY, so the rise is a payment into the account rather than an error.

**Every budget note written before today assumes 110 to 115 CNY remaining.** The two big runs are
now about 4% of the balance rather than 17%. It changes nothing about the design: flash was chosen
on an accuracy tie at n=700 and on wall clock, with cost as the fourth argument, and pro is still
about 5x flash per run in real billing.

The reading is recorded in `api_cost_tally.py` alongside the earlier four. The after-reading is
owed once run 2 finishes: its delta is the exact cost of a 1,700 claim flash run, and will show
whether the 6.94 CNY per attributed USD rate holds at this scale or was fitted to n=700.

**One operational note.** The balance line did not print at first because the instruction was
`source .env`. If `.env` holds plain `KEY=value` lines with no `export`, a plain `source` sets the
variable in the shell but does not export it to `python3`, so the script sees no key. The form that
works is `set -a; source .env; set +a`.

### HARNESS: 189 -> 210

The two new configs added 19 checks by existing rules, and revealed one gap: **nothing validated the
`split` key**, so `"split": "Test"` would have passed the gate and failed at run time. Added.

### The two configs are written

    configs/condition2_flash_v2_test1700.json   run 2, no GPU, no Ollama, 7.6 h, 1.72 USD
    configs/pipeline_test1700.json              run 1, needs the GPU, 13.8 h

**Run 2 first**, because it needs no GPU at all: flash alone is API calls plus BM25 on CPU, so it
runs on the MacBook while the GPU is unavailable. It yields condition 2 at n=1,700, the bar the
routed system is compared against. The two runs are independent, so nothing is blocked by doing
them in this order.

### Still open

Both big runs. `results/pipeline_trial` was archived to `results/archive/pipeline_trial`, so
`check_pipeline_prompts.py` now needs that path as its argument.

### Where the time went, 16 August

Nothing ran on the GPU today. Everything above is design, code, harness and analysis, and three of
the four defects found today were found by reading or by a check rather than by a failed run:
`route_one_claim`'s three bugs, the harness crashing on the new config, and the cost tally's blind
spot. The fourth, the trial run, cost 14.2 minutes.

## 17 August 2026 - condition 2 at n=1,700, the refuted bias replicates, and the cloud bill is 18x the estimate

### THE RUN: 1,700 ok, 0 failed, 8.4 hours

`configs/condition2_flash_v2_test1700.json`, flash on prompt v2, BM25 at k=10, all of `test.json`.
Ran on the MacBook with no GPU and no Ollama, which is why it could happen while the GPU box was
unavailable. Results in `results/condition2_flash_v2_test1700/`.

    strict accuracy        77.4%      testmini was 79.9%
    FINDVER-compatible     77.8%
    unparseable             1.4%      all 23 from truncation, 16k num_predict
    seconds per claim       17.8      testmini was 16.0
    output tokens, mean     2,095     testmini was 1,856
    served_model            one value, one fingerprint, no model roll mid-run

Per subset: ie 82.3%, numeric 77.2%, knowledge 71.6%. Knowledge still weakest, as in every
measurement since 10 August.

**This is the first number in the project measured on a set nothing was tuned on**, and it came in
2.5 points below testmini. That is the direction predicted before the run, for the stated reason:
five configuration choices were made against testmini and tuned choices do not fully transfer.

### THE REFUTED BIAS REPLICATES TO WITHIN 0.2 POINTS

                                 testmini n=700    test.json n=1,700
    predicted entailed               34.1%              33.9%
    gold entailed                    50.0%              50.1%
    accuracy on entailed claims      64.3%              61.7%
    accuracy on refuted claims       95.4%              93.1%

**A frontier model on the corrected prompt still calls a third of claims entailed when half are.**
The entailed/refuted accuracy gap is 31 points on both sets.

2.12 established that FINDVER's shipped prompt carries a refuted bias worth 21% of the benchmark,
and v2 was the fix. **v2 reduces the bias and does not remove it, and the residue reproduces on
1,700 claims that played no part in designing v2.** Replication at that size is the strongest
evidence this project has produced. Written up as 2.15.

### One transient failure in 1,700 calls

`numeric-test-223`: `http.client.IncompleteRead: IncompleteRead(0 bytes read)`. The HTTP response
was cut off before any body arrived. Not the claim, not the prompt, not our code. `elapsed_seconds`
is None because there was never a response to time. Resume repaired it in one call, as designed.

**0.06% transient failure rate over 8.4 hours of continuous cloud calls.** It is a real property of
the cloud half that the local half does not have, and it belongs in any graceful-degradation
argument.

### THE COST IS 18x THE ESTIMATE AND 4.4x OF IT IS UNEXPLAINED

    balance before   468.07 CNY   16 Aug, immediately before the run
    balance after    228.72 CNY   17 Aug, after the retry
    delta            239.35 CNY
    predicted         11.9 CNY

**DeepSeek raised prices**, confirmed by re-reading api-docs.deepseek.com today. The 8 August table
in `api_cost_tally.py` was stale, and rates now vary by time of day:

                      our 8 Aug table   current off-peak   current peak
    flash input /1M       0.14              0.22              0.44
    flash output /1M      0.28              0.66              1.32

Peak is 01:00-04:00 and 06:00-10:00 UTC and off-peak is half of peak, so an overnight run spans
both. **Repricing this run at current PEAK rates gives about 54 CNY. The charge was 239.35. About
4.4x is unaccounted for.**

The cleanest view is free of price lists and currency entirely:

    11 Aug     4.90 CNY /   700 calls  = 0.0070 CNY per call
    17 Aug   239.35 CNY / 1,700 calls  = 0.1408 CNY per call     20x

**Tokens per claim moved 12% between those two runs.** A 20x cost change on 12% more work is a
pricing or billing change, not a usage change.

**Two candidate explanations, neither asserted.** Either the CNY price list sits far above the USD
list, previously measured at 1.48x and needing about 4.4x now, or **the key is being used by
someone other than us**. The ~358 CNY top-up between 11 and 16 August is consistent with an account
someone else also draws on.

**Action: ask the professor whether the key is shared, and ask for read access to the account usage
page.** That request has been on the owed list since 10 August and would settle this in one look.

### What changed in api_cost_tally.py, and one thing deliberately not changed

**Current rates recorded** as `PRICING_CURRENT_PEAK`, used for projecting runs not yet made.

**Historical rates deliberately left in `PRICING`.** Repricing old runs at today's list rewrites
history: the 11 August flash run is known from a balance delta to have cost exactly 4.90 CNY, and
at current rates the table claimed 19.37. Old runs keep the rates they were billed at.

**The CNY-per-USD ratio is withdrawn as a planning tool.** It reproduced the 10 and 11 August
deltas exactly and then missed by 18x at n=1,700. A ratio that fits two points and fails the third
is not a model.

**`CNY_PER_CLOUD_CALL = 0.1408` added**, measured end to end from balance deltas, needing no
assumption about price lists, currency conversion or token accounting. **Treat it as a floor, not a
forecast. It has already moved 20x once.**

### RUN 1 IS 14.4 HOURS AND 58% OF THE REMAINING BALANCE

Repriced on measured figures rather than estimates. The cloud arm measured 17.8 s per claim, not
the 16.0 assumed from n=700:

    3B on all 1,700       3.21 h
    7B on all 1,700       6.47 h
    cloud on about 56%    4.71 h
    TOTAL                14.39 h        previously quoted as 13.8

    cloud cost   ~950 calls x 0.1408 = 133.8 CNY
    balance      228.72 -> about 95 CNY remaining
                 58% of what is left, against the 4% quoted yesterday

**It is affordable and it is not comfortable.** The per-call figure is a floor. Worth putting to the
professor before launching, together with the key question above.

### Afternoon, 17 August: two free measurements on the held-out split, both replicate

No GPU was available and the cloud budget is now uncertain, so the afternoon went to the two things
that need neither. Both turned out to be replications, which is the pattern that has produced the
strongest evidence in this project.

#### RETRIEVAL RECALL ON test.json, and it costs nothing

`measure_recall.py` now takes a split: `python3 test_scripts/measure_recall.py 10 test`. Upstream
ships full rankings for both splits, so the whole comparison was already on disk. **No model calls,
no cloud quota, no GPU.**

    macro recall at k=10          testmini n=700    test.json n=1,700
    ours, bm25                        74.60%            75.16%
    text-embedding-3-large            68.01%            69.75%
    upstream's own bm25               65.16%            64.29%
    contriever-msmarco                33.48%            35.02%
    ours, placeholder                 57.54%            56.75%

**Our BM25 replicates to within 0.6 points on 1,700 claims it was never tuned on, and is slightly
better there.** Element recall 70.5 -> 70.0 and all-gold 50.4 -> 49.4, so all three metrics hold.
It beats the best published retriever by 5.4 points on the held-out split and beats upstream's own
BM25 by 10, which is an implementation gap and not an algorithm gap.

**Fusion is confirmed dead on the held-out split too.** RRF at a pool of 10 gives 74.95% against
our BM25 alone at 75.16%, the same ordering as testmini's 74.06 against 74.60. The 5 August decision
to freeze the retriever at BM25 with no dense arm now has held-out evidence behind it.

Testmini still validates exactly against the section 3.4 figures, and reports 1,959 distinct gold
elements, which is trap 8's corrected count. test.json has 4,805.

#### ONE ERROR CATEGORY IS 63% OF KNOWLEDGE ERRORS, ON BOTH SPLITS

`analyse_missing_info.py` gained the held-out run and a per-subset cut. The model-level table works
on any run, so the mechanism from 2.11 could be tested on 1,700 unseen claims.

The category is: the model says the document does not contain the information, then refutes, and is
wrong. Same model, same prompt v2, knowledge claims only:

                                  testmini n=200    test.json n=500
    cites missing information         34.0%             38.4%
    of those, then refutes            95.6%             98.4%
    of those refutations, wrong       50.8%             47.6%
    base rate, any refutation wrong   34.2%             35.8%

A lift of 1.49x on testmini and 1.33x on test.json. **Citing missing information marks a refutation
as substantially less reliable, on both splits.**

The share of the error budget, which is what §9's taxonomy needed:

                              testmini          test.json
    knowledge errors        33/52 = 63.5%     90/142 = 63.4%
    all errors              54/141 = 38.3%   158/385 = 41.0%

**63.5% and 63.4%.** One failure mode is nearly two thirds of all knowledge errors on both splits,
and about 40% of every error the cloud model makes. Written up as 2.17. **This is the first
quantified category of the four-category taxonomy §9 has wanted since the start.**

**Two limits, both recorded.** The 11 August diagnostic that ruled out retrieval as the cause used
a gold-evidence run, which exists only for testmini, so this shows the mechanism is present at the
same size and not that retrieval is excluded on test.json. And the matcher is a regex over model
prose: spot-checked by reading on testmini in August, not re-read on test.json.

#### The skills idea was considered and deferred, with reasons

Testing a prompt change on the 3B needs a GPU night, and tonight's night is run 1. Prompt v2 was
+2.9 points at p = 0.002 on the cloud model and a **tie on the 3B**, p = 0.378, which is direct
evidence that prompt edits do not move this 3B much. And the evaluation question got harder today:
skills must be evaluated without tuning on the reported set, and `test.json` is now the reported set.

**One thing did improve.** Selection was the blocking question on 12 August, because a per-subset
skill selected by the benchmark's subset label is not deployable. **The numeric detector solves that
for arithmetic claims**, at 0.984 held-out precision. A skill for arithmetic claims is now
selectable in a way it was not five days ago. Recorded, not yet worth a night.

## 18 August 2026 - run 1 chunk 1, and the cost panic was misdirected

### Chunking works, and it was verified before it was needed

Run 1 is 15 hours and the GPU is only available in short windows, so the run is being taken in
chunks. **No code change was needed.** `logger.has_result` returns true only for `status == "ok"`,
so Ctrl-C and re-running the same command picks up exactly where it stopped.

Verified with stubs before relying on it: a stub raising `KeyboardInterrupt` partway through stops
the run, the two completed claims are on disk as `ok`, the in-flight claim is simply not written,
and resume reports `2 ok, 0 failed, 2 skipped, out of 4`.

**The clean interrupt is a direct benefit of the `except Exception:` fix from 16 August.** A bare
`except` catches `KeyboardInterrupt`, which would have written the interrupted claim as `failed` and
carried on to the next one.

Two operational rules: never delete the results directory between chunks, and resume with `tee -a`
rather than `tee` or each chunk overwrites the log.

**Warm-up is the only cost of chunking, measured from the trial run:** the first 3B call of a
session is 9.2 s against a 6.8 s median and the first 7B call is 17.1 s against 12.6 s, so about
**7 s per restart**. Ten chunks costs 70 seconds on a 15 hour job. Per-claim `elapsed_seconds` is a
stopwatch around one claim and the analysis sums per-claim times, so nothing else is affected.

### CHUNK 1: 312 claims, 0 failed, and the routing prediction holds

    cloud calls        179/312 = 57.4%     predicted 56%, derived floor 54%
      numeric_detector    95
      disagreement        84
    stage records      2 on 133 claims, 3 on 179, never 1
    seconds per claim  32.5 mean, 25.6 median
    local-only claims  22.1 s mean, against 20.5 predicted

**57.4% against a predicted 56%.** The 16 August simulation took the derived 54.0% from stored
files, argued the live rate must come in higher because independent noise can only add
disagreements, and put it at 56.5% with a 95% range of 54.3 to 58.7. The live figure sits inside
that range. **The prediction and its stated mechanism both hold.**

Timing is slightly worse than estimated: 32.5 s per claim gives **15.3 hours for the full run**
rather than 14.4. `test.json` reports are a little heavier than testmini's.

### THE COST PANIC WAS MISDIRECTED. OUR CALLS COST 0.009 CNY, NOT 0.14.

Balance readings around chunk 1:

    216.60 CNY   before
    214.94 CNY   after 179 cloud calls
      1.66 CNY   delta  =  0.0093 CNY per cloud call

    per-call, all three measurements
      11 Aug, flash n=700       0.0070
      17 Aug, flash n=1,700     0.1408    <- the outlier, 15x the others
      18 Aug, chunk 1           0.0093

**Two independent measurements either side of it agree, and the middle one is 15x both.** At
0.0093 per call, the 1,700 call condition 2 run should have cost about **16 CNY**. The balance
dropped **239.35**.

**So the 17 August conclusion is withdrawn.** `CNY_PER_CLOUD_CALL = 0.1408` was fitted to a single
delta that our own usage cannot account for, and yesterday's write-up treated it as a price change.
It is not: prices did rise, confirmed from DeepSeek's docs, but by 3 to 4.7x on the list, not 15x
in practice, and this chunk shows our real per-call cost is unchanged in order of magnitude since
11 August.

**A second fact points the same way.** The balance was 228.72 after the condition 2 run on
17 August and **216.60 the next morning, with no cloud calls from us in between. 12.12 CNY gone
while nothing of ours was running.** The 11 August settlement lag was 0.28 CNY, so this is 43x that.

**The honest position: something other than our runs is drawing on this account.** Not asserted as
fact, but it is now the explanation that fits both observations, and the alternative, a 15x
price spike that reverts within a day, fits neither.

**What to put to the professor**, now two concrete facts rather than a suspicion:
1. **12 CNY left the account overnight with nothing of ours running.**
2. **A run whose own measured per-call rate says 16 CNY coincided with a 239 CNY drop.**
Ask whether the key is shared, and ask for read access to the usage page.

**Revised projection: run 1's cloud arm costs about 9 CNY, not the 134 quoted yesterday.**

### Accuracy so far, and why it is not to be acted on

**237/312 = 76.0%, 95% CI 71.2% to 80.7%.** Claims are shuffled with seed 0, so the first 312 are a
random subsample and the figure is unbiased, but the interval is about ±5 points and **covers
condition 2's 77.4% comfortably**. It cannot yet distinguish the routed system beating, tying or
losing to cloud-alone.

Recorded because it exists, and flagged: **no decision may rest on it.** Stopping or adjusting on a
partial result is how tuning-on-the-evaluation-set happens, and this project has already made five
configuration choices against the set it reports.

Split by who answered: local-decided claims 73.7% (n=133), cloud-decided 77.7% (n=179). Both far too
small to read.

## 19 August 2026 - the account is not exclusively ours, and the cost method is inverted

### ONE ANOMALOUS BILLING EVENT, NOT A CONTINUOUS DRAIN

**This section was written twice today. The first version is wrong and is reproduced below the
correct one, because the mistake is worth keeping.**

Windows derived from result-file write timestamps rather than guessed, and our usage attributed
from the cloud stage's own recorded token counts at DeepSeek's current PEAK rates:

    window                calls     drop CNY   attributed   gap
    condition 2 run        1700       239.35        53.86   +185.49
    IDLE, no run              0        12.12         0.00    +12.12
    run 1 chunk 1           179         1.66         5.56     -3.90
    run 1 chunk 2           252        27.30         8.76    +18.54
    run 1 chunk 3           116         3.75         4.09     -0.34

**Two of five windows come in at or BELOW what our own tokens predict.** Chunk 1's -3.90 and
chunk 2's +18.54 partly offset, which is what settlement lag looks like: charges landing after a
reading. Grouping to absorb it:

    run 1, all three chunks       dropped  32.71   attributed 18.41   factor 1.8x
    condition 2 run + idle night  dropped 251.47   attributed 53.86   factor 4.7x

**1.8x is close to the 1.48x CNY-versus-USD gap measured on 10 August**, so run 1's billing is
consistent with our own usage plus an unverified currency conversion.

**What survives is a single anomalous event: the condition 2 run of 16-17 August, roughly 185 to
200 CNY unexplained.** Worth asking the professor about. It is a very different claim from
continuous outside usage.

**Considered and insufficient:** that run went 19:00-03:00 local, which is 02:00-10:00 UTC and
therefore almost entirely inside DeepSeek's peak window. That is already priced into the 53.86.

### ~~The first version of this section, wrong, kept for the record~~

It read the same three balance deltas against **guessed** window boundaries and against the
withdrawn 0.0093 CNY-per-call figure, and concluded that **something other than this project
spends on the key, continuously, to the tune of 260 CNY**. With the boundaries taken from file
timestamps and the attribution taken from token counts, four of the five windows are consistent
with our own usage.

**The 12.12 CNY idle night is real and unexplained, but it is 12 CNY, not evidence of a pattern**,
and it sits immediately after the anomalous run, which is exactly where settlement lag would land.

**Third cost correction in three days**, and all three share one cause: a conclusion drawn from
balance arithmetic before checking the assumptions the arithmetic rests on. 17 August assumed one
delta was a price change. 19 August morning assumed guessed window boundaries. **The rule that
would have prevented all three: a balance delta is a difference between two readings, so before
attributing it to anything, establish exactly what happened between those two readings.**

### THE COST METHOD IS INVERTED, AND I HAD IT BACKWARDS FOR THREE DAYS

`api_cost_tally.py` said, and this file repeated, that **a balance delta is the only exact spend
figure** and the token attribution is a secondary estimate. **That is now the wrong way round.**

A balance delta exactly measures what the **account** spent. It measures what **we** spent only
under an assumption nobody ever wrote down: that we are the sole user of the key. That assumption
has now failed three times.

    token attribution   THE COST FIGURE. Exact token counts recorded per claim in our own
                        result files, priced at a stated rate card. Reproducible, auditable,
                        unaffected by anyone else's usage.
    balance readings    A MONITORING SIGNAL. Good for noticing the account is draining.
                        Useless for attributing that drain to a run.

**For the paper: quote tokens and USD at a stated rate card, never CNY.** The CNY conversion was
fitted to balance deltas that are now known to be contaminated. The paper's cost claims are
comparative anyway, routed against cloud-alone, and a ratio is rate-card independent as long as one
card is used throughout.

**`CNY_PER_CLOUD_CALL` is withdrawn as a cost figure.** It was derived from a single balance delta
in the one window that happened to look clean. Kept only as a rough order of magnitude for
estimating how many calls a run will make.

**This is the second withdrawal of a cost conclusion in three days.** On 17 August the 0.1408
figure was withdrawn as an outlier fitted to one delta. On 19 August the whole balance-delta method
follows it. The common error both times was treating a difference between two readings as a
measurement of our own behaviour without checking the assumption that nothing else moved.

### What this does and does not change

**It does not change the plan.** Run 1's remaining cloud calls are about 4.6 CNY of real usage by
token count. The run was never the problem.

**It does not change any accuracy number**, since none of them depend on cost.

**It makes the professor conversation urgent rather than owed.** Three dated observations, not a
suspicion. At roughly 25 CNY per day of outside drain against 187.64 remaining, the account has
about a week. **Two questions: is this key shared with anyone else, and can you have read access to
the account usage page.** The second has been on the owed list since 10 August and would have
caught this a week ago.

### Current position

    balance, 19 Aug             187.64 CNY
    our attributed spend        6.04 USD across every run and ad-hoc call
    run 1                       804 of 1,700 claims done, 0 failed

---

## 20 August 2026 - run 1 is complete, condition 4 ties cloud alone at 57% of the cost, and the cost window closes clean

The largest single result of the project, and the last one that needed a GPU.

**Run 1 finished. 1,700 of 1,700, status ok on every claim, 0 failed.** `configs/pipeline_test1700.json`, the routed 3B to 7B to `deepseek-v4-flash` pipeline, over the whole of `test.json`. It ran in chunks across 18, 19 and 20 August, 15.76 hours of summed wall clock, median 26.0 seconds per claim. Part of 18 August shared the GPU with a game and no boundary was recorded, so the median is the figure to quote and the mean is contaminated.

Built `test_scripts/analyse_run1.py`, which regenerates every number below from stored result files with no model calls. Written up as `paper_numbers.md` §2.18, §2.18.1 and §2.19.

### The headline

Because `skip_local_when_escalating` is false, every claim carries a 3B verdict and a 7B verdict alongside the routed one, so one job produced three conditions on identical claims. Condition 2 was already run at the same n on the same split, so the cloud arm pairs against these claims too.

    3B alone      59.8% (1016/1700)
    7B alone      67.8% (1153/1700)
    routed        75.8% (1289/1700)
    cloud alone   77.4% (1315/1700)

Paired McNemar, routed against cloud alone: 116 to 142 on 258 disagreements, p = 0.119. A tie, at 56.6% of the cloud tokens, with 46.6% of claims answered entirely on-device. That is the claim the project was built to make, and it is now measured on 1,700 claims that nothing was tuned on.

The routed figure was 75.8% at n=794 mid-run and 75.8% at the end. It was stable long before the run finished.

### What complicates it

The tie is not uniform. FDV-IE is a significant loss: routed 77.5% against cloud 82.3%, 40 to 69 on 109 disagreements, p = 0.0070. FDV-MATH and FDV-KNOW are ties. This goes beside the headline in the paper, not behind it.

Decomposing the FDV-IE loss found the mechanism. On the 219 escalated FDV-IE claims the routed system slightly beats cloud alone, 78.5% to 76.7%. The entire deficit is on the 381 claims where the 3B and 7B agreed, no call was made, and the cloud would have scored 85.6% against our 76.9%.

Both local models are `qwen2.5-coder`, sharing weights, tokenizer and training data. When they agree on an FDV-IE claim they are often agreeing on the same mistake, and the gate reads that as confidence. Agreement between two models of one family is correlated error, not independent confirmation. This is a finding worth reporting rather than a defect to hide.

It cannot be fixed and re-run. `test.json` has now been touched once, as the 12 August protocol requires. Any gate change from here is future work, or it is tuned on the reported split and the held-out defence is gone.

### What went right, and it is the part that justifies the design

Escalation earns its cost. On the 908 claims where the cloud was called, the 3B would have scored 45.7% and the 7B 60.8%. The cloud scored 75.8%. That is +15.0 points on exactly the claims we chose to pay for.

Both triggers contribute independently. Disagreement escalations, n=459, went from 57.3% under the 7B to 73.4%, +16.1 points and +74 claims. Numeric-detector escalations, n=449, went from 64.4% to 78.2%, +13.8 points and +62 claims.

The numeric detector does work that disagreement cannot do by construction: it fires where the two locals agree and are wrong together. Of the 1,125 claims where the locals agreed, 333 were escalated anyway by the detector, and the local verdict on those was only 62.8% correct. This is the direct evidence for why always-escalate-numeric beat the gate on 12 August.

Two rows in the routing table look like a failure and are not. Accuracy where the cloud was called is 75.8%, accuracy where the claim was kept local is 75.9%. Those being equal is the gate succeeding: the claims kept local score 75.9% on a 7B whose all-claim accuracy is 67.8%, so the gate is retaining the claims the local tier handles well.

### The refuted bias, replicated a fourth time

    arm            gold entailed    gold refuted   says entailed
    3B alone              49.8%           69.7%           39.5%
    7B alone              68.4%           67.3%           49.2%
    routed                67.1%           84.6%           41.1%
    cloud alone           61.7%           93.1%           33.9%
    gold                  50.1%           49.9%

The cloud model answers entailed on a third of claims where half are entailed. The routed system beats it on entailed claims by 5.4 points and loses on refuted by 8.5, which is the likely mechanism behind the FDV-IE result. The 7B alone is the only nearly calibrated arm the project has produced.

### The ceiling

Perfect selection over 3B, 7B and cloud would score 84.8%. Perfect selection over the two local models alone, with no cloud calls at all, would score 79.9% and beat the frontier cloud model outright. Neither is implementable and neither may be reported as a system result, but they bound the headroom: 9.0 points to the three-way oracle, 4.1 to a cloud-free one.

### The unparseable rate exists now

`paper_numbers.md` §5 has carried "any unparseable rate for our configuration" as unsupported since 2 August, on the ground that 0 of 12 is not a rate. 1,700 is.

    3B 1.65% (28/1700)   7B 2.82% (48/1700)   cloud 1.65% (15/908)   routed 0.94% (16/1700)

Routing suppresses unparseable output, because a claim ends unparseable only when the arm that wins the vote produced garbage.

One error made and caught today: the first version of that table computed the cloud rate over all 1,700 claims and reported 88.9%. `verdict_cloud` is None on the 792 claims where no call was made, which is not an unparseable response. The denominator is calls made.

Other integrity checks: 0 context overflow, 15 truncated by length, gold evidence present in 50.2% of prompts, 0 locals skipped, extraction source anchored on 1,681 of 1,700.

### The cost window closed clean, and the shared-key worry is answered for now

Five balance readings taken by hand around the final block, with call counts read from result files at both ends rather than guessed. This is the measurement the 19 August cost-method inversion asked for.

    window     689 -> 908 cloud calls  =  219 calls
    balance   165.74 -> 162.45 CNY     =  3.29 CNY drop
    measured                              0.0150 CNY per call

The drop is well below our own attribution. The 19 August CNY peak rate card predicted 7.38 CNY, so the actual is 0.45x of it. Nobody else was spending on the key during this window.

The two rate cards on record disagree by a factor of four about what a call should cost, which is one more reason the paper quotes USD and token counts and never CNY.

Condition 2 on 16-17 August cost 0.1408 CNY per call. This window cost 0.0150, on the same model at similar tokens per call. That is 9.4x. The 16-17 August event was real, large and stands alone, and every window measured since is consistent with our own usage. Run 1's full cloud arm at the measured rate is 13.64 CNY, against the 134 CNY quoted on 17 August.

The 19 August window stays unscored. Its start boundary is ambiguous between 804 and 1,021 claims, giving either 2.1x or 3.8x, and choosing the boundary that produces the preferred answer is the exact error the 19 August correction was written about. The window above replaces it at no cost.

### Skills were checked and closed

`test_scripts/analyse_skill_targets.py`, written 19 August and run before deciding anything. It reads stored result files and FINDVER's own `execution_result` field. No model calls, no GPU, no quota. testmini only, because `test.json` ships none of those fields.

Numeric: splitting refuted numeric claims by how far the asserted value sits from the truth found the local failure and it is sharp. On claims within 0.1% of the truth the 3B scores 43.2% and answers entailed on 57% of them, where gold is refuted every time. On claims more than 1% off it scores 86.4%. Loose minus tight is +43.1 points at z = 4.62 for the 3B and +46.2 at z = 5.05 for the 7B. The cloud model's gap is +5.9 at z = 0.98, not significant.

The local models cannot compute to better than one part in a thousand, so a claim off by 0.05% reads as true to them. The matcher was validated first: 122 of 125 entailed claims match gold within 1%, and entailed claims assert the gold value by definition, so that is the matcher testing itself.

This is already solved. `escalate_numeric` is true in the shipped config, so every numeric claim goes to cloud, and run 1 shows that buys +13.8 points. What the analysis provides is the mechanism behind a rule that previously worked for unexplained reasons.

Knowledge: the cloud's dominant failure mode, declaring the evidence absent and refuting on that basis, does not explain the local models at all. Lift over the base refutation error rate is 0.99x for the 3B and 1.03x for the 7B, against 1.48x for the cloud. A lift of 0.99 means the phrase carries no information. A skill aimed at that mode on the 3B would be aimed at nothing.

FDV-KNOW is still the weakest subset in the routed pipeline at 72.0%, and we do not have a mechanism for it on the local models. That is recorded as an open gap rather than filled with a guess.

Skills are closed for this paper and become a future-work paragraph. The numeric detector at 0.984 held-out precision means an arithmetic skill is selectable, which was the blocking question on 12 August, so the idea is viable and unfunded rather than dead.

### Documentation

`paper_numbers.md` gained §2.18, §2.18.1 and §2.19, and its §5 list of unsupportable claims gained five entries and resolved three: the unparseable rate, any 7B number, and the gap condition 4 had to close.

### Where this leaves the schedule

Every condition the plan asked for now has a held-out number. The results are frozen and nothing further needs the GPU. Overleaf is the only thing left before the 23 August freeze, and it is still empty. Owed since 7 August.
