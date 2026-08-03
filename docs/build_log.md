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
