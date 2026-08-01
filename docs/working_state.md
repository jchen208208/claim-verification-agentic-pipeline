# Working state

Fast changing information only. For anything stable, including the architecture, the build order, the schedule, the data schema, and the related work, see the architecture plan. For a dated record of what was built in each session, see `build_log.md`.

Last updated: 31 July 2026.

---

## The deadline

The paper is due **30 August 2026**. That is 30 days from today. Settled at the professor meeting on 30 July.

The deliverable is a paper of about five pages, submitted to a workshop in Australia called *On-Device Intelligence: Foundation Models under Real-World Constraints*. I am first author. My professor is a co-author and will recruit about two industry co-authors.

This voids the eight-week schedule. Section 12 of the architecture plan has been replanned around 30 days.

**Nothing is cut.** Scope is banded by what compute is available, in section 12.3. Band A is committed and fits on this machine. Band B is conditional on faster hardware and holds the full 700 run, the end to end retrieval ablation, and the 7B comparisons. Band C is stretch and holds the glossary, the faithfulness verifier, and the routing sweep.

An earlier draft of the replan cut tiers 2 through 5 outright. That was wrong. It cut retrieval, which is the core of the project, and it priced the whole of tier 2 as if it needed overnight runs. It does not. **Retrieval recall is scored against the gold `relevant_context` indices with no model calls at all**, so a k sweep, a BM25 comparison, and a decomposition comparison are minutes of work, not nights. Only the end to end accuracy delta from better retrieval needs a night. The cheap half is also the half most on topic for a RAG focused paper, so it goes early rather than last.

Read section 12.1 of the plan before scheduling anything that runs locally. The short version: between 3 and 23 August there are about 20 usable nights, one 3B slice run costs one night, one 7B slice run costs two to three, and a full 700 run would cost seven on this machine. Results have to freeze by 23 August so that writing can start on the 24th.

If a faster machine materialises the night budget stops binding and Band B opens. Specs and availability are unknown as of 31 July. See open question 11 in the plan. Until it is real, plan against this machine and treat anything faster as upside.

## Where the project stands

Week 1 is done. The repository is cloned, the data structure is confirmed, both local models are installed and benchmarked on a real example, and the visual build plan has been sent to my professor.

Two of the five harness pieces are built, verified, and committed: the loader and the stratified sampler. The remaining three are logging, the label extractor, and the evidence assertion. They are due 2 August.

## What the professor decided on 30 July

He independently reached the same conclusion already in the plan: run edge only and cloud only baselines first, then build the routed system, because you cannot claim the routed system beats either end without measuring both ends.

Three decisions came out of the meeting.

1. **Do not re-run the paper's baselines.** Use the published numbers as the historical baseline. They are somewhat dated and saying so is part of the framing.
2. **Extend the cloud side with two models released after the paper**, from 2025 or 2026. Provider is not fixed. He said he can provide Anthropic keys as well as DeepSeek and Qwen. Anthropic is the tighter comparison because `claude-3-5-sonnet` is the paper's top scorer, so a newer Claude extends that exact row. This needs deciding before 3 August.
3. **Extend the edge side with local models the paper did not evaluate.** The paper already covers Llama-3.2-3B, Llama-3.1-8B, Qwen2.5-7B, Mistral-7B and twelve others. Ours have to be different ones. Two is realistic in the time available. Three is not.

This is a good fit for the compressed schedule, because cloud runs cost hours rather than nights and reusing published numbers removes 16 runs we cannot afford.

**One consequence that is easy to miss.** The published numbers were produced with `gpt-4o-mini` extraction and coin flip imputation of unparseable outputs. Putting our strictly scored numbers in the same table as theirs would compare two different measurements, and would understate our models exactly where they fail the output format, which at 3B is about 45 percent of the time. Any table mixing our numbers with published ones has to use the FINDVER compatible scoring. The strict numbers go in a separate table with the unparseable rate beside them. The two number reporting decided below is therefore no longer optional.

## What is built

    src/loader.py     load_raw, Claim, raw_to_claim, load_claims
    src/sampler.py    group_by_cell, stratified_sample, check_balance
    prompts/          baseline_v1.txt, samples/ie-val-0_filled.txt

`load_claims()` returns all 700 testmini records as `Claim` objects. Every object has the same 11 fields no matter which subset it came from, so no code downstream has to know about the `explaination` misspelling or about which subsets carry extra fields. `Claim` is a frozen dataclass, so nothing in the pipeline can write into a record and corrupt later iterations.

`stratified_sample(claims, per_cell)` returns a shuffled, balanced sample drawn from the six subset by label cells. The default seed is 0 and it must stay fixed, because every configuration we compare has to run on the same examples. The balance check runs inside the function, so an unchecked sample cannot exist. Use 2 per cell for smoke tests, which gives 12 examples, and 17 per cell for measured runs, which gives 102.

The loader returns report filenames, not report contents. Reports are read one at a time inside the run loop. Re-reading all 700 costs about 5 seconds total, measured, so there is no cache and no reason for one.

## Sample size decision

17 per cell, 102 examples, about 8 hours on the 3B model. That is one configuration per overnight run.

At 102 examples the margin of error on accuracy is roughly plus or minus 10 points. The slice can show that retrieval is broken or that the cloud model is much better. It cannot rank two prompts that differ by 3 points. The full 700 run is for final numbers.

The 102 examples are inside the 700. Since prompts and retrieval will be tuned against them, they function as a development set, and about 15 percent of any final 700 number comes from examples we optimised against. Say so plainly in the write up.

## How FINDVER actually scores, and why it matters here

Read from `FinDVer/evaluation.py` and `FinDVer/utils/evaluation_utils.py` on 31 July. This was not known before today.

1. The official evaluation extracts the verdict with a **`gpt-4o-mini` call per example**, not with a regex. It asks for `entailed`, `refuted`, or `none`.
2. When the answer is `none`, meaning the model never stated a verdict, the script assigns `random.choice(["entailed", "refuted"])`. The example is scored as a guess. It is not counted, not reported, and not excluded.
3. There is no `random.seed` anywhere in the repository, so re-running the official evaluation on identical predictions gives a different score.
4. The direct prompting path uses substring matching and checks `"entail" in output` before `"refut"`. The string "entail" appears inside "not entailed", so that path mislabels negations. This affects direct prompting only, not chain of thought, so it does not affect the numbers we compare against.

Point 2 is the one that matters. For the strong models in the paper, unparseable outputs are rare, so coin flipping them moves the score by well under a point. Our models are 3B and 7B. If a model fails the format on 30 percent of examples, roughly 15 accuracy points of its official score are imputation rather than reasoning. The assumption behind the shortcut breaks at our model scale.

This is not a flaw in the benchmark. It is an assumption that does not hold in our regime, which is a more defensible and more interesting thing to write.

**Decision.** Report two numbers from the same run. Strict, where unparseable is its own bucket, counted as wrong for the headline figure, and its rate reported separately. FINDVER compatible, where unparseable is coin flipped with a fixed seed. Use the second only when placing our number beside a published one. The gap between the two quantifies how much of a small model's official score is imputation.

## Measured: a plain regex is nearly as good as the cloud extractor

`FinDVer/outputs/testmini_outputs/rag/processed_cot_outputs/` holds 700 examples for each of 16 models. Each record stores both the raw model response and the label `gpt-4o-mini` extracted from it. That is 11,200 real response and label pairs, available offline at no cost.

A first pass regex looking for "the claim is entailed" or "the claim is refuted" was measured against them on 31 July:

    model                                  regex fires    agrees with gpt-4o-mini
    claude-3-5-sonnet-20241022                 100.0%              100.0%
    gpt-4o                                      99.7%              100.0%
    Mistral-Large-Instruct-2407-AWQ             98.3%               99.4%
    Qwen2_5-7B-Instruct                         91.3%               99.5%
    Qwen2-7B-Instruct                           80.0%               99.1%
    Llama-3_2-3B-Instruct                       54.9%               96.9%
    Meta-Llama-3_1-8B-Instruct                  52.9%               97.6%
    mathstral-7B-v0_1                           54.1%               95.3%
    TOTAL, 16 models, 11,200 examples           81.7%               98.9%

Two readings. Where the regex fires it agrees with the cloud extractor 98.9 percent of the time, so accuracy is not the problem. Coverage is, and coverage falls with model size. At 3B roughly 45 percent of responses do not contain the sentence in its simple form.

One honest caveat. `extracted_label` in these files is stored **after** the coin flip, so a coin flipped label is indistinguishable from a real one. That means the 45 percent miss rate is a mix of two different things: responses where the model genuinely stated no verdict, and responses where it concluded clearly but phrased it in a way the first pass regex does not match. These files cannot separate the two. Widening the patterns will reduce the miss rate by some unknown amount, and the leftover is the true unparseable rate.

The agreement figure is also measured only on the subset where a clean sentence exists, which is the easy subset. It is not evidence that a regex matches `gpt-4o-mini` on hard cases.

**Decision.** Build a deterministic regex extractor. Do not add a model based fallback until we have measured how far widened patterns get us. We cannot replicate the official extractor anyway, because it uses `gpt-4o-mini` and we have DeepSeek and Qwen keys, so the model route buys no comparability while costing quota.

## Machine and environment

The work machine is a 2017 Intel MacBook Pro running macOS 13 Ventura, with 16 GB RAM. There is no usable GPU for inference, so everything runs on CPU.

Ollama is pinned at version 0.12.3. This matters: version 0.12.4 dropped support for macOS 12 and 13, and this Mac cannot upgrade past Ventura because 2017 hardware is not supported by later macOS releases. Automatic updates must stay off or the whole local setup breaks.

Models pulled locally:

    qwen2.5-coder:3b        the main working model
    qwen2.5-coder:7b        kept for quality comparison, too slow for batch runs
    nomic-embed-text        for the search step, not yet used

## Running overnight

An 8 hour run needs three things set up, and the first is not optional.

1. macOS will sleep and suspend the process. Start the run with `caffeinate -i python3 ...`, keep it plugged in, and leave the lid open. Closing the lid sleeps the machine regardless.
2. Write each example's result to disk as it finishes, not at the end. A crash at example 90 then costs one example instead of the whole night. Skipping example ids that already have a result file gives resume for free.
3. Wrap each example in try/except. One malformed table should not end the run. Log the traceback into that example's result file, mark it failed, and continue.

Expect the real runtime to exceed the per example estimate. A 2017 Intel machine thermally throttles over 8 hours of pinned CPU.

## Things that cost time and should not be rediscovered

Ollama defaults to a 4096 token context window and truncates anything longer without warning, without an error, and without any sign in the output. A realistic prompt for this benchmark runs close to 4000 tokens, so the default silently clips real evidence. Every run needs the window set explicitly, either with `/set parameter num_ctx 8192` in an interactive session or by passing `num_ctx` in the API options. Interactive settings do not persist between sessions.

Each element of a report's `context` array is a dictionary with three keys, `id`, `context`, and `type`, not a plain string. `type` is `paragraph` or `table`, so it is free table detection and the loader should carry it through. A loader that assumes strings will silently produce garbage rather than failing loudly. This caused the week 1 benchmarking failure.

The examples in the dataset are grouped by answer in solid blocks, and the direction changes between subsets. In testmini, ie and numeric put the false claims first, but knowledge puts the true ones first. Any sampling that does not shuffle or stratify will produce a wildly misleading result. Confirmed again on 31 July by counting: the six subset by label cells hold 125, 125, 125, 125, 100, 100, and the smallest cell is 100, which caps `per_cell`.

The dataset is bigger than the paper says. Testmini holds 700 examples, not 600, and test holds 1,700, not 1,500. The test file also ships with real labels, so the whole "labels are withheld" assumption in the plan is wrong. Counted directly from the files on 29 July. See section 2.6 of the architecture plan.

The numeric subset spells the explanation field `explaination`. The other two subsets spell it correctly. Handle both. The loader now does this, so nothing downstream needs to.

## Currently blocked on

Cloud API keys from my professor, for DeepSeek and Qwen. Nothing involving the cloud half of the architecture can start without them. For Qwen specifically I also need to know which Alibaba Cloud region the account belongs to, because keys are not interchangeable between regions and the wrong endpoint returns a 401.

Note that the label extractor is not blocked. It is deterministic and it can be developed and validated entirely against the 11,200 stored responses in the upstream clone.

## Still outstanding from week 1

Checking the FINDVER leaderboard for recent submissions, and running a citation search for papers published since the benchmark. Both are needed before repeating any claim that nobody has attempted something. Neither has been done yet.

## Where I left off on 31 July

The loader and the sampler are finished, verified, and committed. The design of the label extractor is settled but no code is written.

Settled design for the extractor:

- Input is the model's raw response string. Output is `"entailed"`, `"refuted"`, or `None`.
- `None` is a real answer and is never guessed at. It is the bucket that gets counted and reported.
- Search the end of the response first. The words "entailed" and "refuted" appear throughout the reasoning and in the prompt's own instructions, so the first match in the text is not the conclusion.
- Match the whole sentence pattern, not a fragment. A substring test for "entail" matches "not entailed" and gets the answer backwards. That is the exact bug in the upstream direct prompting path.
- The two number reporting, strict and FINDVER compatible, belongs to the scorer, not to the extractor. The extractor does one thing: text in, verdict out.
- Expect roughly 25 lines.

## Next session

Build `src/label_extractor.py`.

Development data is already on disk and needs no model run. Use `FinDVer/outputs/testmini_outputs/rag/processed_cot_outputs/Llama-3_2-3B-Instruct.json`, which is the closest available analogue to our 3B model, plus `Qwen2_5-7B-Instruct.json` for the 7B comparison. Each record has `output`, which is a list whose first element is the response text, and `extracted_label`, which is what `gpt-4o-mini` returned.

The measurement script already exists: `scripts/measure_extractor_baseline.py`. It reproduces the table above in under a second and is the loop for widening the regex. Edit the pattern, rerun, watch the coverage column move.

Order of work:

0. The script currently holds its own copy of the regex, in a constant called `PATTERN`, because it was written before `label_extractor.py` existed. Change it to import the real extractor instead. Two copies of one regex will drift apart, and then the measurement stops describing the thing being shipped.
1. Write the strict regex for the canonical sentence. Measure how often it fires on the Llama 3B file. The first pass measured 54.9 percent.
2. Read a sample of the responses where it does not fire. Sort them into two piles: no verdict stated, and verdict stated in a form the pattern missed.
3. Widen the patterns to cover the second pile only. Re-measure. Do not widen to cover the first pile, because those are genuinely unparseable and inventing a guess for them is exactly what we are trying not to do.
4. Report the final coverage and the residual unparseable rate. That residual is a result worth writing down.

Do not add a model based fallback in this session. Decide on it after step 4, with a measured number in hand.

The harness is due 2 August, which leaves the label extractor, per example logging, and the evidence assertion in about two days. None of the three is blocked on cloud keys.

**Why this piece matters more than it looks.** The edge only baseline is the run I can start first, because it needs no keys, and in it the 3B model produces every verdict. A 45 percent miss rate there is not a detail, it is most of the first result. The extractor is also the thing that turns today's measurement into a paper section, so it is on the critical path twice.

## Outstanding, not yet done

Decide the two cloud models and the two added edge models before 3 August. See open questions 7 and 8 in the architecture plan.

Answer open question 11: what faster machine is available, with what specs, and when. This decides whether Band B opens.

Confirm the workshop mechanics: page limit, template, whether submissions are anonymous, and whether the 30 August deadline is anywhere on earth. None of this is known and all of it changes the writing schedule.

## Measured performance, for planning purposes

On a roughly 4000 token prompt, the 3B model takes about four minutes forty five seconds end to end and the 7B model takes about eleven minutes forty five. Memory use peaked at 2.5 GB and 5 GB respectively, so RAM is not the constraint. CPU speed is.

That works out to roughly eight hours for a hundred examples on the 3B model, or about fifty five hours for the full seven hundred example development set. Any plan involving repeated full runs needs to account for that.

Reading a report file from disk takes about 7 milliseconds, so re-reading one per claim across all 700 costs about 5 seconds in total. That is 0.02 percent of an 8 hour run and is why the loader does not cache.
