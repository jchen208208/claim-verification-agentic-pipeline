# Working state

Fast changing information only. For anything stable, including the architecture, the build order, the schedule, the data schema, and the related work, see the architecture plan. For a dated record of what was built in each session, see `build_log.md`.

Last updated: 4 August 2026.

---

## The deadline

The paper is due **29 August 2026, 23:59 anywhere on earth**. That is 04:59 Pacific on 30 August, and 19:59 Beijing on 30 August.

**Corrected 1 August.** Every document said 30 August, taken from the professor at the 30 July meeting. The workshop site says 29 August. One day of the writing phase is gone.

The deliverable is a paper of about five pages, submitted to a workshop in Australia called *On-Device Intelligence: Foundation Models under Real-World Constraints*. I am first author. My professor is a co-author and will recruit about two industry co-authors.

This voids the eight-week schedule. Section 12 of the architecture plan has been replanned around 30 days.

**Nothing is cut.** Scope is banded by what compute is available, in section 12.3. Band A is committed and fits on this machine. Band B is conditional on faster hardware and holds the full 700 run, the end to end retrieval ablation, and the 7B comparisons. Band C is stretch and holds the glossary, the faithfulness verifier, and the routing sweep.

An earlier draft of the replan cut tiers 2 through 5 outright. That was wrong. It cut retrieval, which is the core of the project, and it priced the whole of tier 2 as if it needed overnight runs. It does not. **Retrieval recall is scored against the gold `relevant_context` indices with no model calls at all**, so a k sweep, a BM25 comparison, and a decomposition comparison are minutes of work, not nights. Only the end to end accuracy delta from better retrieval needs a night. The cheap half is also the half most on topic for a RAG focused paper, so it goes early rather than last.

Read section 12.1 of the plan before scheduling anything that runs locally. The short version: between 3 and 23 August there are about 20 usable nights, one 3B slice run costs one night, one 7B slice run costs two to three, and a full 700 run would cost seven on this machine. Results have to freeze by 23 August so that writing can start on the 24th.

If a faster machine materialises the night budget stops binding and Band B opens. **Updated 3 August: the professor has offered a GPU server.** Specs, access method and date are still unknown, so plan against this machine until the server is real, but Band B is now likely rather than hypothetical. See the 3 August section below and open question 11 in the plan.

## Where the project stands

Week 1 is done. The repository is cloned, the data structure is confirmed, both local models are installed and benchmarked on a real example, and the visual build plan has been sent to my professor.

**Everything needed to run an experiment exists, and the first trial run is complete.** The harness is complete: loader, stratified sampler, label extractor, per example logging, evidence assertion, and the run loop that the original list of five never named. Alongside it, a placeholder retriever, an Ollama client, a config file, an entry point at `run.py`, and a committed 26 check harness test that already caught one silent bug.

**The trial run finished on 2 August. 12 of 12 completed, no failures, 80.7 minutes.** Results in `results/trial_run_3b/`, console output in `logs/trial_run_3b.txt`. The pipeline works end to end. Full analysis in the build log entry for 2 August, late; the summary and everything it changes are in the section below.

The defect that was carried into the run deliberately, the expected context overflow on two examples, **did not occur.** The prompt size estimate was too pessimistic. Prompt trimming is therefore no longer urgent, and its justification has changed from correctness to wall clock. See the trial run section below.

## What the professor decided on 30 July

He independently reached the same conclusion already in the plan: run edge only and cloud only baselines first, then build the routed system, because you cannot claim the routed system beats either end without measuring both ends.

Three decisions came out of the meeting.

1. **Do not re-run the paper's baselines.** Use the published numbers as the historical baseline. They are somewhat dated and saying so is part of the framing.
2. **Extend the cloud side with two models released after the paper**, from 2025 or 2026. Provider is not fixed. He said he can provide Anthropic keys as well as DeepSeek and Qwen. Anthropic is the tighter comparison because `claude-3-5-sonnet` is the paper's top scorer, so a newer Claude extends that exact row. This needs deciding before 3 August.
3. **Extend the edge side with local models the paper did not evaluate.** The paper already covers Llama-3.2-3B, Llama-3.1-8B, Qwen2.5-7B, Mistral-7B and twelve others. Ours have to be different ones. Two is realistic in the time available. Three is not.

This is a good fit for the compressed schedule, because cloud runs cost hours rather than nights and reusing published numbers removes 16 runs we cannot afford.

**One consequence that is easy to miss.** The published numbers were produced with `gpt-4o-mini` extraction and coin flip imputation of unparseable outputs. Putting our strictly scored numbers in the same table as theirs would compare two different measurements, and would understate our models exactly where they fail the output format, which at 3B is about 45 percent of the time. Any table mixing our numbers with published ones has to use the FINDVER compatible scoring. The strict numbers go in a separate table with the unparseable rate beside them. The two number reporting decided below is therefore no longer optional.

## What the professor said on 3 August, and what he did not

He replied to the progress email with three things. He has a server with an **"NVIDIA RTX 4090 Ti"** and asked whether it would be useful. He recommends **DeepSeek**, mentioning a recently released model that seems nearly comparable to Claude. He called the Ollama eviction finding **"a very valuable finding."**

**He answered one of the two questions asked.** The cloud model question is answered: DeepSeek. **The local model question was not answered at all.** Open question 8 is still open and it gates the schedule.

**He did not address the Anthropic argument.** "Nearly comparable to Claude" is about model strength, and the argument put to him was not about strength. The published model list was checked: `claude-3-5-sonnet-20241022.json` is the paper's top scorer, and DeepSeek appears only as `DeepSeek-V2-Lite-Chat.json`, a small MoE model. So a new frontier DeepSeek extends a row whose only predecessor is weak, while a newer Claude extends the strongest row directly. This matters because section 9.1 makes reuse of published numbers load-bearing for the whole timeline.

**Decided:** DeepSeek is the primary cloud model. Ask once for an Anthropic key as the second, with that one specific reason. If he declines, use two DeepSeek models split on chat versus reasoning rather than two correlated versions. Get the exact model strings and endpoint from him; the model was not named and should not be guessed.

**Decided, pending his objection:** the second edge model is **Qwen2.5-Coder-7B**. Neither Coder variant appears in the published list, so both satisfy open question 8.

**Note that "RTX 4090 Ti" is not a product that shipped.** There is a 4090 at 24 GB and a 5090 at 32 GB. Confirm the real card, the VRAM, the access method, and whether jobs can run for days before planning against it.

## What happened on 4 August: the retriever is designed, and fusion is measured

He has not answered on the GPU. Nothing today was blocked by it, because the retriever is
chosen on recall alone and that is machine-independent daytime work.

**`test_scripts/measure_recall.py` is built and validated.** It takes one dict,
`example_id -> list of element ids`, so every retriever we will ever try is scored by the same
code. It reproduces all twelve figures from 2 August and self-asserts them at k=10. Full
detail in §3.4 of the plan and the build log entry for 4 August.

**Fusion beats the published number by 6 points, and it cost nothing.**

    bm25 alone                65.16%   62.8%   38.6%
    text-embedding-3 alone    68.01%   62.4%   42.6%
    RRF of both, pool 10      74.06%   69.0%   48.7%
    union ceiling             80.86%   77.0%   58.9%

FINDVER shipped both retrievers' full rankings, and recall scoring needs only element ids, so
combining what they already produced is arithmetic over files on disk. **74.06% against the
68.01% FINDVER published and MACE adopted unchanged.** A shallow candidate pool of 10 per arm
beats deeper pools, because RRF rewards agreement and a deep pool promotes consistently
mediocre elements over one retriever's strong pick.

**This is a measurement, not our retriever.** It uses `text-embedding-3`, a paid API we have
no key for. Its job was deciding whether a local embedding index is worth its one-time CPU
cost, and it says yes.

**Per subset, and it maps onto the two tiers.** `text-embedding-3-large` element recall is
79.0% on FDV-MATH, 58.2% on FDV-IE, 56.1% on FDV-KNOW. Retrieval works best on MATH, which is
where the best model scores worst, so MATH's difficulty is arithmetic — the Tier 1 argument.
Retrieval works worst on KNOW — the Tier 2 argument.

**Decided: the design.** BM25 plus a local Ollama embedding arm, fused by RRF, pool 10 per
arm, `c = 60`, k = 10 out. **Chunking does not change**, one `context` element is one chunk,
and §7.3's "keep tables whole" is already satisfied because a table is one element.

## Our BM25 is built, and it beats the paid embedding

`src/bm25_retriever.py`, over all 700 claims at k=10:

    ours, bm25                        74.60%   70.5%   50.4%   free, no model
    text-embedding-3-large            68.01%   62.4%   42.6%   paid API
    upstream bm25                     65.16%   62.8%   38.6%
    RRF of the two published ones     74.06%   69.0%   48.7%   paid API
    ours, placeholder                 57.54%   53.2%   31.6%

**A free local retriever with no model in it beats the paid embedding by 6.59 points** and
edges past the fusion of both published retrievers. For an on-device paper this is the
strongest result the project has produced, and it cost nothing to run.

**Two things written here yesterday are now wrong.** ~~Validate our BM25 by reproducing 65.16
exactly~~ is unreachable, because upstream's BM25 is a different algorithm; chasing it would
be debugging a non-bug. ~~Target: beat 68.01% with a fully local retriever~~ is already met,
the same day, before any dense arm exists.

**Why it is not a fluke.** Exactly 10 distinct in-range ids for all 700 claims. No gold
leakage: the retrieval path reads only `claim.statement` and `report["context"]`. The scorer
is unchanged and still reproduces all twelve upstream figures. Upstream's chunking and corpus
scope were read from their code and are identical to ours. And the difference reconstructs in
both directions: applying their three implementation choices to our code gives 66.72% against
their published 65.16%, the residual being our approximation of NLTK and Porter.

**The three causes, and two dead hypotheses.** Lucene IDF instead of classic-plus-epsilon is
worth about 2.5 points, dropping punctuation about 2.0, stemming nothing. They compound to 7.9
rather than summing to 4.5. **Stemming makes no difference and neither does stripping inner
commas from numbers** — the second had been the leading explanation for our advantage and it
is wrong.

**The finding for the paper: upstream's tokenizer penalises tables.** Punctuation inflates
measured element length 1.81x for tables against 1.13x for paragraphs, because pipe-delimited
table text is dense in `|`, `$`, `(`, `)`. Length normalisation then divides table scores down
and pushes them out of the top 10. Tables are 18% of elements and carry much of the evidence.
Provenance, stated accurately: the tokenizer is `evidence_asserter.tokenize`, written 2 August
for the asserter. Dropping punctuation was inherited, not chosen for retrieval. What is new is
the measurement and the mechanism. Write it as a finding, not a designed insight.

**The dense arm survives but its case is thinner.** RRF(ours bm25, `text-embedding-3`) is
77.14%, so the paid embedding still adds +2.54 on top of us, down from +6.05 over the
published baseline. Union ceiling is 82.85%. `nomic-embed-text` now has to preserve a
2.5-point gain rather than a 6-point one. Score it alone first. **The target is no longer
68.01%, it is whether a fully local hybrid clears our own 74.60%.**

## The hardware rule, decided 3 August

The GPU changes where experiments run. It does not change what the paper claims about hardware.

- Accuracy and ablations run on the GPU.
- **The MacBook is the device of record** for every latency, throughput and memory number in the paper.
- **Never print a GPU derived number under a MacBook label.** A run on the 4090 cannot produce a MacBook runtime, and substituting one would be fabricated data. This was considered explicitly and rejected.
- **Never mix machines inside one results table.** Temperature 0 does not guarantee identical tokens across CPU and CUDA. If one configuration moves to the server, everything it is compared against moves too. The 2 August trial numbers are MacBook only.
- Keep the edge model at **8B or below** whatever the VRAM allows.

**3B stays the paper's primary model. 7B is a row, not a switch.** A bigger model eats the contribution, because the pipeline's delta is largest where the base model is weakest. If 7B handles the arithmetic unaided, the ablation shows less.

**Budget one MacBook night at the end**, after the pipeline is frozen, to measure the final configuration's per example latency and peak RAM on the real device. That run doubles as the accuracy portability check, confirming verdicts reproduce off CUDA.

## The baseline design, settled 3 August

Four conditions, not three. The three condition version has a hole in it.

    1  3B, RAG, one call, no pipeline           local          edge only floor
    2  DeepSeek, RAG, one call, no pipeline     cloud          single big call
    3  DeepSeek in every pipeline role          cloud          all big model, approx MACE
    4  3B + DeepSeek routed                     local + cloud  ours

**Condition 3 is a baseline that does run through the pipeline, and it is mandatory.** Section 5.3 claims we match the all big model version at a fraction of the cost, and that cannot be claimed without measuring it. Section 5.3 already said so: always escalate is MACE's design, never escalate is the edge only floor, the interesting result lives between.

**"No pipeline" does not mean no RAG.** Every condition uses the same retrieval, same k, same slice, same prompt version, same `num_ctx`, temperature 0, and the same label extractor. Only the pipeline machinery varies.

**The claim is matching condition 3 cheaply, not beating condition 2.** If we beat condition 2, report it, but leading with it invites the answer that nobody deploys a cloud model as a single prompt.

Cost: conditions 1 and 4 are local, about 12 h each at 102 examples, so two nights. Conditions 2 and 3 are cloud, hours. All four are internal comparisons, so all four are scored strict against strict.

**Two results tables, one variable each.** Pipeline table: retrieval fixed, architecture varies across the four conditions. Retrieval table: architecture fixed, retrieval varies. Holding retrieval constant is what makes the pipeline comparison mean anything, rather than defeating the point of building a retriever. The recall half of the retrieval table has no architecture column at all, because retrieval runs before any model call, and it costs minutes. The end to end delta half is fixed to our pipeline and costs a night.

There is no configuration where the cloud model retrieves its own evidence. It has no access to the filing.

**n = 102 cannot support the central claim.** At ±10 points a tie and a 5 point loss are indistinguishable, so "matches condition 3" is unprovable at that sample size. The full 700 run is the only fix, and it is the first thing the server buys.

**When each condition is measured.** The four are not all run at the same point. Conditions 1 and 2 are a single model call with no pipeline, so they depend only on retrieval and can run as soon as retrieval is frozen. Conditions 3 and 4 both go through the pipeline, so they cannot be measured until it exists. **The order is 1 and 2 early, 3 and 4 late, then all four together at 700.** This still gives the professor what he asked for on 30 July, since conditions 1 and 2 are the two ends he wanted measured first.

**Correction to an earlier framing.** Condition 3 is not a fixed reference point. It runs the cloud model in every pipeline role, so it moves whenever the pipeline moves, exactly like condition 4. Only conditions 1 and 2 are stable across pipeline changes.

**The module by module comparison is condition 4 only.** Baseline, then plus code execution, then plus better retrieval, is a claim about our own system. Nothing is claimed about condition 3 with only part of the pipeline built, so it is never measured that way. Condition 3 is run once against the frozen final pipeline.

**Retrieval invalidates everything.** Change a module and only conditions 3 and 4 move. Change retrieval and all four move, because every condition must share the same retrieval. This is why retrieval is settled first, and settling it costs no nights because the retriever is chosen on recall alone with no model calls.

**Machine choice is part of the freeze.** Results from different machines cannot sit in one table, so where conditions 1 to 4 run must be decided **before condition 1 starts**. Running condition 1 on the Mac and condition 4 on the server means re-running condition 1.

**Which conditions run at 700.** A 700 run cannot be compared against a 102 run, so both sides of any comparison need the same n. Conditions 3 and 4 at 700 are mandatory, because that pair is the whole reason to buy the full run. Condition 1 is nearly free on the GPU so include it. Condition 2 is the bonus comparison and is the first to drop. **Ablations stay at 102.** Iterate at 102, freeze the winner, then run the final comparison at 700.

**Cloud quota, not wall clock, is the constraint on the 700 run.** Condition 3 puts the cloud model in every pipeline role, so at 700 examples it is by far the largest consumer of calls. Ask the professor about quota before committing to conditions 2 and 3 at full scale.

## The plan from here, revised 3 August

**Nothing ran on 3 August, and that was deliberate.** Phase 2 in the plan starts the edge only baselines that day. Three separate things each made a run that night a throwaway. The retriever is still the placeholder at 57.5% recall, and every condition has to share the same retrieval, so any baseline measured now dies when the real retriever lands. A 102 example run is about 12 hours, so a late start eats the next day too. And the machine question is not settled, so a Mac run gets repeated if the server arrives.

**The retriever moved ahead of the baselines.** This is a change from section 12.2, which puts baselines first. It costs nothing, because the retriever is chosen on recall alone, with no model calls. Daytime work, not nights.

    3 Aug        leaderboard check, citation sweep, MACE accuracy number    reading only
    4-7 Aug      build the retriever, choose on recall, freeze retrieval    no nights
    7-9 Aug      conditions 1 (3B and 7B) and 2 at 102                      nights + cloud hours
    9-16 Aug     pipeline modules one at a time, code execution and tables
                 first, condition 4 at 102 after each                       most of the nights
    15 Aug       decision point, drop what is not working
    17-20 Aug    freeze pipeline, conditions 3 and 4 at 102, full table     cloud + nights
    20-23 Aug    700 run, conditions 1, 3, 4, plus 2 if quota allows        GPU only
    23 Aug       results freeze, hard stop
    24-29 Aug    write

**The machine decision has a deadline of about 7 August**, because that is when condition 1 starts and it cannot be split across two machines. If there is no server access by then, start on the Mac at 12 hours per run and accept re-running later.

**Separately, and whatever happens with the server:** one Mac night at the very end, after the pipeline freezes, for real latency and peak RAM on the actual device.

**Honest caveat.** This is tighter than the original phasing, because moving the retriever first pushes everything right by several days. Without the server the 700 run does not happen, and the claim that we match condition 3 stays unprovable at plus or minus 10 points.

## What is built

    src/loader.py            load_raw, Claim, raw_to_claim, load_claims
    src/sampler.py           group_by_cell, stratified_sample, check_balance
    src/label_extractor.py   extract_label, extract_label_with_source
    src/logger.py            Record, write_result, has_result
    src/evidence_asserter.py tokenize, count_report_tokens, pick_tokens,
                             assert_evidence, check_overflow
    src/run_loop.py          load_prompt_template, read_report, build_prompt,
                             run_one_claim, run_sample
    src/placeholder_retriever.py   retrieve, top-k by token overlap
    src/ollama_client.py     call_ollama, POST to localhost:11434
    run.py                   entry point, at the repo root
    configs/trial_run_3b.json      one config file per experiment
    prompts/                 baseline_v1.txt, samples/ie-val-0_filled.txt
    test_scripts/measure_extractor_baseline.py     regenerates the extractor table
    test_scripts/validate_evidence_asserter.py     validates the asserter, delete when trusted
    test_scripts/test_harness.py                   26 checks on the run loop, committed, run before every overnight job

`results/` and `logs/` are both gitignored. `results/<experiment>/` holds one JSON
per claim and is the real record; `logs/` holds console output captured with `tee`.

`scripts/` was renamed to `test_scripts/` on 2 August. The "Where things live"
section of `CLAUDE.md` still says `scripts/`, does not mention `run_loop.py`,
`evidence_asserter.py`, `placeholder_retriever.py`, `ollama_client.py`, `run.py`,
`configs/` or `logs/`, and needs updating.

The command to run an experiment:

    python3 test_scripts/test_harness.py && \
    caffeinate -ims python3 run.py configs/<name>.json 2>&1 | tee logs/<name>.txt

`caffeinate -ims` blocks idle, disk and system sleep, the last only on AC power, so
stay plugged in. Keep the lid open, since caffeinate cannot override a clamshell
close. Close Chrome and VS Code: RAM is not the constraint at 2.5 GB peak on a 16 GB
machine, but this is CPU-only inference on a 2017 Intel chip and competing processes
take cores from Ollama.

`load_claims()` returns all 700 testmini records as `Claim` objects. Every object has the same 11 fields no matter which subset it came from, so no code downstream has to know about the `explaination` misspelling or about which subsets carry extra fields. `Claim` is a frozen dataclass, so nothing in the pipeline can write into a record and corrupt later iterations.

`stratified_sample(claims, per_cell)` returns a shuffled, balanced sample drawn from the six subset by label cells. The default seed is 0 and it must stay fixed, because every configuration we compare has to run on the same examples. The balance check runs inside the function, so an unchecked sample cannot exist. Use 2 per cell for trial runs, which gives 12 examples, and 17 per cell for measured runs, which gives 102.

`Record` is an 18 field dataclass holding everything about one example: the prompt, the raw response, the config used, both token counts, `done_reason`, the extracted label and which extractor level produced it, the gold label, timing, and a status and traceback slot. `write_result(record, results_dir)` writes it to `results/<experiment>/<example_id>.json` the moment the example finishes, and creates the directory itself. `has_result(example_id, results_dir)` is the resume check.

Two details of the logger that are easy to get wrong later. Resume tests `status == "ok"` rather than file existence, because a failed example still writes a file and existence alone would skip it forever. And a truncated JSON file, which is what a crash mid write leaves behind, returns `False` rather than raising, so the run recovers instead of dying on startup.

Unlike `Claim`, `Record` is not frozen. A claim is input and nothing should write into it. A record is output filled in three stages, before the call, after the call, and by the asserter.

The loader returns report filenames, not report contents. Reports are read one at a time inside the run loop. Re-reading all 700 costs about 5 seconds total, measured, so there is no cache and no reason for one.

## Sample size decision

17 per cell, 102 examples. **Measured cost, from the trial run: about 12 hours on the 3B model, not 8.** That is still one configuration per overnight run, but it is a full night rather than a comfortable one, so a run has to start in the evening rather than late.

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

**Resolved 1 August. See the next section.** The widening was done and measured, the fallback was rejected, and the caveat above about not being able to separate the two kinds of miss is now resolved with numbers.

## The extractor is built. Final numbers, 1 August

`src/label_extractor.py` is finished and verified. Three levels, tried in order of precision, with the last match winning inside a level.

1. **anchored**, the concluding sentence such as "the claim is entailed", searched over the whole response.
2. **bare**, a standalone `entailed` or `refuted`, searched only in the last 300 characters. The window is the precision guard, because both words appear all through the reasoning and in the prompt's own instructions.
3. **guards on level 2.** A hedge, such as "partially entailed", returns `None`, because that is not a binary verdict and inventing one is the thing we are avoiding. A direct negation, such as "not entailed", returns the opposite label, which is safe because the label space is binary.

`extract_label(response)` returns the verdict for the pipeline. `extract_label_with_source(response)` also returns which level fired, which is what the results table needs.

Coverage across all 11,200 upstream responses went from 81.7 percent to 87.8 percent. Agreement fell from 98.9 to 98.3. On Llama-3.2-3B, the closest available analogue to our model, coverage went from 54.9 to 65.3 percent. In whole examples that is 373 correct extractions rising to 437, against 11 wrong rising to 20. Sixty four more right answers for nine more wrong ones.

Level breakdown over all 11,200:

    anchored   81.7%
    bare        5.8%
    negated     0.3%
    hedged      2.3%
    none        9.9%

Per model, the two failure buckets separate models in a useful way. `gemini-1.5-pro` is 6.3 percent hedged but only 0.4 percent none. `Meta-Llama-3.1-8B` is 1.9 percent hedged and 40.3 percent none. Those are opposite behaviours. One model always concludes and then qualifies it, the other frequently never concludes. Folding both into a single unparseable number would hide that, which is why the two buckets stay separate.

## Why we stopped widening, and why there is no model fallback

Of Llama-3.2-3B's 231 remaining `none` responses, **81 percent contain the strings "entail" or "refut" nowhere in the response at all.** Not in the tail, not in the body, nowhere. There is no verdict in the text to extract.

That settles the fallback question that was deferred on 31 July. **No model based fallback.** A DeepSeek or Qwen call on those responses would not be extracting anything. It would read the reasoning and form its own judgment, which is imputation wearing a parser's clothes, and it is worse than the coin flip because it does not look random. It would also cost quota per unparseable example.

Only 15 percent of the residual has a verdict word in the body but outside the 300 character tail window. Reaching those means widening the window into the reasoning and trading precision for a handful of examples. Not worth it. The extractor is done.

The remedy for a high `none` rate is at the prompt and generation end, not the extractor end. That belongs to the harness work.

## The upstream numbers were produced at temperature 1.0. Ours will not be.

This is the most important thing learned today and it changes how the 33 percent should be read.

Read from `run_llm.py` lines 44 to 47 and `scripts/inference/main_vllm.sh`, which passes no sampling overrides, so the argparse defaults reached vLLM at `run_llm.py:125`:

    temperature = 1.0        top_p = 1.0        max_tokens = 1024

None of that is an error on the authors' part. All three are ordinary defaults. But they are not our settings, and two of them are doing real damage to the small models.

**The 1024 token cap is provably biting.** On Llama-3.2-3B, 108 of 700 responses end with no terminal punctuation. Their word counts pile against a hard ceiling, p90 863 and max 916, that cleanly ending responses never approach, max 827. A ceiling in one group and not the other is the signature of a generation cap. Ninety of those truncated responses land in the `none` bucket, which is 39 percent of that bucket and about 13 percent of all 700 examples. Those were cut off mid reasoning, not incapable of concluding.

**Do not treat 33 percent as a forecast of our own rate.** Our runs use temperature 0 and we set `num_predict` ourselves. Greedy decoding follows an instructed format far more reliably than sampling at 1.0, and we control the cap. Both mechanisms most likely driving that 33 percent are ones we have already turned off. Do not write "3B models fail the output format 45 percent of the time" into the paper on the strength of the upstream table. The first honest measurement of our own rate comes from running our own model.

One thing that follows for the framing: the published FINDVER baselines are non reproducible on two axes, not one. Sampled generation at temperature 1.0, and then the unseeded coin flip at scoring time. Section 11.8 previously recorded only the second.

The token soup and near empty generations in the upstream files are consistent with temperature 1.0, but that is unverified. Testing it would mean re-running their models, which we cannot do.

## New trap: `num_predict` is the twin of `num_ctx`

A model call has two ends and each has a limit. `num_ctx` caps what goes in, `num_predict` caps what comes out. Both truncate with no error, no warning, and nothing visible in the output, and both make me blame the model for something I configured.

    cap too small   what breaks              what it looks like        what it is
    num_ctx         evidence gone from       the model hallucinated    I truncated
                    the prompt                                         the input
    num_predict     verdict gone from        the model ignored         I truncated
                    the response             the format                the output

`num_predict` bites harder than it sounds, because chain of thought reasons first and concludes last, so an output cap removes exactly the sentence the extractor needs.

The fix is not to raise both. They share one budget, since `num_ctx` is the total window and prompt plus generated tokens both live in it. Uncapped output is also a hazard, because a small model at temperature 0 can loop forever and eat a whole night on one example.

Measured 1 August, the RAM cost of a bigger window is smaller than I assumed. For `qwen2.5-coder:3b`: 4096 gives 2.4 GB, 8192 gives 2.6, 16384 gives 3.2, 32768 gives 4.4, against 16 GB physical. About 0.07 GB per extra 1k of window, so RAM is not the binding constraint for the 3B. Re-measure for the 7B, whose cache is larger.

Settings to use, therefore:

    num_ctx      16384       about 3.2 GB, double today's headroom, so a larger
                             retrieval k later does not need this re-tuned
    num_predict  1500-2000   upstream's 1024 cut a verbose 3B off mid reasoning.
                             Llama-3.2-3B's cleanly ending responses ran a median
                             354 words and a max of 827, so roughly 1100 tokens
                             covers the longest seen. Confirm on our own model.

That gives 16384 against about 4500 prompt plus 2000 generation, roughly 9800 tokens of slack, so overflow is arithmetically impossible rather than merely unlikely.

There is no input token parameter. `num_ctx` is the total window, so prompt size is ours to manage. That is only safe because the pipeline is RAG only: we never pass a filing, we pass k retrieved chunks, so prompt length is set by k and chunk size rather than by document length. The one residual risk is a single oversized table chunk blowing the budget by itself. Count tokens before sending and trim or drop the lowest ranked chunk until it fits.

## Measured 1 August: Ollama 0.12.3 destroys prompt tokens during generation

Tested on the local server rather than looked up, because this behaviour has changed across Ollama versions and we are pinned. A canary string was put at the very start of a 74 token prompt, a long generation was requested, and only `num_ctx` was varied.

    num_ctx  192 | prompt  74 | eval 268 | total 342 | done=stop | canary LOST
    num_ctx  256 | prompt  74 | eval 339 | total 413 | done=stop | canary LOST
    num_ctx  512 | prompt  74 | eval 286 | total 360 | done=stop | canary OK
    num_ctx  512 | prompt 512 | eval 277 | total 789 | done=stop | canary LOST, confabulated

Generation is not stopped by the window. Totals reached 342 and 413 against windows of 192 and 256, so decoding carries on and the oldest tokens are evicted to make room. `done_reason` came back as `stop` every single time, never `length`, so the API reports a clean normal completion while data is being destroyed. And the model confabulates rather than reporting the loss. In the overflow run it announced the secret code was "double entry", and it also silently dropped the instruction to state the code at all, because that had scrolled out of view too.

**This changes the evidence assertion.** A prompt that fits perfectly at ingestion can still have its evidence scrolled out mid generation if the response is long. Checking that gold tokens are present in the prompt string passes while this happens, so it cannot catch it. The alarm condition is not `prompt_eval_count == num_ctx`, which only catches input side truncation. It is:

    prompt_eval_count + eval_count >= num_ctx

Log both counts on every call and check the sum. It is the only signal available, because the response text and `done_reason` both look healthy.

Set it explicitly in every API call. Log the generation eval count as well as the prompt eval count. Treat a response ending without terminal punctuation as its own failure category in the error taxonomy, separate from a format failure. **Ollama's default `num_predict` on v0.12.3 has not been checked yet and must be, before the first batch run rather than after one.**

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

**Updated 1 August: the DeepSeek key has arrived.** DeepSeek runs a single global API at `api.deepseek.com` and is OpenAI SDK compatible, so there is no regional configuration to get wrong. The cloud half is no longer fully blocked.

Qwen is still outstanding. For Qwen I also need to know which Alibaba Cloud region the account belongs to, because keys are not interchangeable between regions and the wrong endpoint returns a 401. Run a one call smoke test on receipt: a 401 identifies a region mismatch rather than a bad key, and only the `base_url` changes.

Not yet done with the DeepSeek key: a smoke test confirming it works.

Note that the label extractor is not blocked. It is deterministic and it can be developed and validated entirely against the 11,200 stored responses in the upstream clone.

## Done 3 August: the leaderboard check, the citation sweep, and MACE's number

Carried since week 1, slipped three times, all three finished in one evening by web research.

**MACE scores 0.76 on FINDVER**, with the Qwen-235B setup. Their smaller runs: Llama-8B 0.68, Mistral-7B 0.64. **Verified by eye against their Table 8 the same evening.** Full table in section 6.1.

**Three problems appeared only when the real table was read.**

**One, their Claude baseline does not match its own source, and it reverses the ranking.** MACE did not re-run any baseline. Their caption says the numbers come from the FINDVER paper. Yet their Claude-3.5-Sonnet is 0.73, and FINDVER gives 77.2 long context and 75.0 RAG. Neither matches. The effect is that **their table puts Claude below GPT-4o, 0.73 against 0.75, while FINDVER puts Claude above GPT-4o, 75.0 against 73.7 under RAG.** The two strongest baselines change places.

**Decided 3 August: state the mismatch and the effect, and say nothing about the cause.** Both facts above are checkable from the two published tables. Do not write that they swapped rows, which is an unverifiable mechanism, and do not write that they demoted the baseline, which is a claim about intent. Only two models overlap between the tables, review is double blind, and a MACE author is a plausible reviewer. An unsupported claim about a competitor's conduct would put every other number we report under suspicion.

**Which number we use: FINDVER's.** We are evaluating on their benchmark, so their published figure is the reference. Claude-3.5-Sonnet 75.0% RAG. MACE's baseline column is not a source for any model FINDVER already published.

**We can still settle the discrepancy for free** by recomputing accuracy for both models from `outputs/` against the gold labels in `testmini.json`. No model calls, no quota. Worth doing for our own certainty, not for anything that goes in the paper.

**Two, their Table 8 never says whether the baselines are long context or RAG.** The two differ by about 2 points, and we are RAG only, so no MACE baseline can go in our tables until that is settled from their text. **Partly answered by reading FINDVER's Table 4:** MACE's baseline magnitudes track the RAG column, not long context. Strong inference, not something they state.

**Three, their baseline list is broader than FINDVER's printed table**, covering five models that appear only in our `outputs/` directory. **That makes `outputs/` the authoritative baseline set, not the paper's table.**

**FINDVER is a parity result for MACE, not a best-in-class one.** Their own sentence says they reach the top on two datasets and are level with the best models on two others. FINDVER is one of the two where they only drew level.

**The row that matters to us is Llama-8B at 0.68.** A small model running their whole pipeline lands below the 2024 Claude-3.5-Sonnet RAG figure of 75.0%. That is both the opening for our design and the warning about it.

**MACE reports memory and runtime, but never on FINDVER, and their runtime is a cost rather than a saving.** Their table 4 is restricted by its own caption to closed domain datasets, meaning SciTab and SemTab. Their table 5 covers SciTab, SciTab-OD and SemTab. **Neither touches FINDVER.** On our benchmark nobody has reported deployment cost at all.

**Their table 5 runs against them.** Minutes per 300 claims: Mistral-7B goes from 4 with plain CoT to 110 with MACE, which is 27 times slower. Qwen-72B goes from 23 to 123. Their own stated ratio for Llama-8B against the 235B baseline is 2.21 times on SciTab and 2.71 on SemTab. **Their pipeline costs between 2.2 and 27 times more wall clock than a single pass.** Their efficiency claim is about memory, with runtime as the price. For a venue about latency under real constraints, that is an opening. We have a fitted cost model at R squared 0.995 and the strongest competing approach has no FINDVER timing at all.

**Their smallest configuration is 27B of total parameters.** Table 4 counts parameters across all agents, so Mistral-7B with an independent verifier is 27B resident at 11.5% of the 235B baseline's memory. Ours is 3B local plus a cloud API. Section 5.3's phrase "fraction of the cost" should say which cost. Memory is already claimed by them, on other datasets. Wall clock and on device feasibility on FINDVER are unclaimed by anyone.

**Do not write that we are faster than MACE. We are not.** Their Llama-8B run is 121.83 minutes for 300 claims, about 24 seconds per claim on server GPUs. Ours is 7.0 minutes per example, 420 seconds per claim, on a 2017 CPU laptop. **We are roughly 17 times slower**, and that compares our single pass baseline against their full pipeline. Ours will be slower still once the pipeline is built. The 2.2 to 27 times figures are their pipeline against their own single pass on their own hardware. They say nothing about us.

**The comparable number is overhead ratio, not seconds.** Different hardware and different documents make absolute times meaningless. What compares is how much the pipeline costs over a single pass on the same machine. Theirs is 2.21, 2.71, 5.3 and 27 times. Ours is condition 1 against condition 4, which section 9.2 already schedules, so the number falls out of work that is happening anyway.

**What is defensibly ours, strongest first.** The hardware floor, since their smallest setup needs 27B resident and ours needs about 2.5 GB. Feasibility on genuinely constrained hardware, which is a deployment claim and not a speed claim. And being first to report deployment cost on FINDVER, phrased as "we found no other" rather than "nobody has."

**No new speed workstream.** Prompt size is the only real lever on wall clock, and tighter retrieval cuts runtime and raises recall together. The retriever is the speed work. A separate effort would compete for the same nights and buy the same thing twice.

**This does not replace the core.** Retrieval recall and the extraction and imputation analysis are still the two results that carry the paper. Deployment cost is a third supporting leg.

**Their table 2 confirms our split sizes.** They list testmini at 700 claims and test at 1,700, not the paper's 600 and 1,500. Two independent counts now agree, so section 2.6's correction can be stated plainly rather than hedged.

**There is no leaderboard.** The paper promised an online platform, but no address appears anywhere and there is no sign it launched. Email submission did exist and the repository retired it in July 2026, once the test labels were made public. So the question of whether to chase a leaderboard is dead rather than decided.

**The citation sweep found 23 papers citing FINDVER, and MACE is the only method among them evaluated on it.** The rest cite it as background or are competing benchmarks. This was abstract level screening, not full text, so the honest phrasing is "we found no other method evaluated on FINDVER," never "nobody has."

**A wrong number was caught, and the reason matters.** The web fetch reported FINDVER's best model as GPT-4o at 76.2%. That is wrong. The real figures are Claude-3.5-Sonnet 77.2% long context and 75.0% RAG, GPT-4o 75.7 and 73.7, exactly as section 2.6 already had them. The same fetch also called the results table Table 3 when it is Table 4. The fetch tool answers questions about a page using a small summarising model, so a misread table produces a confident wrong figure with a real link attached. **A citation is not verification.**

The failure was not uniform, which is the real lesson. Two pages were fetched. The MACE numbers came back correct and survived checking. The FINDVER numbers came back wrong twice. There is no way to tell a good fetch from a bad one without checking, so every fetched figure stays unverified until someone reads it.

Note also that this machine cannot read PDFs. `pdftotext` is missing and no Python PDF library is installed. Installing poppler would remove the need to route our own PDFs through the web.

**FINDVER Table 4 has now been read by eye**, from a screenshot kept at `docs/findver_baseline_accuracy.png`. Section 2.6's averages are confirmed exactly, and the per subset breakdown is now recorded there for the first time.

**The finding worth carrying into the paper: FDV-MATH is where the best model collapses.** Claude-3.5-Sonnet under RAG scores 80.5 on FDV-IE, 75.5 on FDV-KNOW, and **69.0 on FDV-MATH**. That is an 11.5 point spread between the strongest model's easiest and hardest subset, and the hardest one is exactly what tier 1 code execution attacks. Tier 1 previously rested on the benchmark's error taxonomy and on our own arithmetic failure in the trial run. This is a third motivation and the hardest to argue with, because it is a published number showing the gap is widest where we intervene.

**Everything from MACE has now been read.** Tables 2, 4, 5 and 8, plus the section 4.4.2 body text.

**Settled: MACE runs RAG on FINDVER, with FINDVER's own configuration.** Their Retrieval Mechanism paragraph says it directly: *"Since retrieval is not our primary focus, we adopt existing strategies."* They then take text-embedding-3 at k equals 10, the same configuration FINDVER found optimal, and report 67.91% and 69.53% recall.

Three things follow, all good for us. **Their setup is identical to ours at tier 0**, so their accuracy numbers compare to ours with no caveat about the setting. **The quote behind their retrieval weakness is verbatim, not our paraphrase**, which is the strongest support we have for the gap statement: the leading approach on this benchmark says in writing that it declined to work on retrieval. And **their 67.91% agrees with our recomputed 68.01% to within rounding**, so three sources now agree on the ceiling.

They never use the word RAG anywhere in the paper. They describe the mechanism without the acronym.

**A citation we are missing: TableRAG, Chen et al. 2024**, found in their related work. Retrieval plus tables is our core, so it should be read and probably cited. Added to the reference list along with TableGPT2 and TAT, both of which are training based and out of our lane.

**Their body text overstates their own numbers.** Section 4.4.2 says Mace "achieves SOTA performance on both TM and T splits with Qw-235B reaching 0.76 accuracy, matching the best baseline results." The two halves conflict, and the numbers agree with the second. On testmini 0.76 ties Qwen-2.5 72B. On test 0.76 ties both Mistral-Large 123B and GPT-4o. Ties on both. **Cite the abstract's "on par with the best models," not section 4.4.2's "SOTA."** State the tie plainly and say nothing about the gap between their two descriptions, for the same reason we say nothing about the Claude discrepancy.

## Where I left off on 1 August

The label extractor is finished, verified, and committed across `9b09cfc`, `95da412`, and `5128a21`. `scripts/measure_extractor_baseline.py` now imports the real extractor rather than holding its own copy of the regex, so the measurement always describes the thing being shipped.

Two bugs were hit while writing it, both silent, and both worth remembering.

An `if` block was written one indentation level short, so it sat outside the `for` loop instead of inside it. The loop ran 700 times doing nothing but rebinding a variable, and the body then ran once on whatever the last record left behind. Coverage read 0.1 percent. No error of any kind. In Python, indentation is the block structure, so this is a complete change of meaning that the interpreter cannot object to.

A counter was incremented with `agrees ++ 1` instead of `agrees += 1`. Python has no `++` operator. That line parses as `agrees + (+1)`, a legal expression whose value is discarded, so the counter never moved and the column read 0.0 percent. No error, no warning.

Later, the same guard condition was pasted twice, so the second branch tested `_HEDGE_BEFORE` where it should have tested `_NEGATION_BEFORE`. Because the first branch already returned on that condition, the second was unreachable, and the 30 negated responses silently came back with the label reversed. Coverage looked perfect and only the agreement column moved, by 0.2 points.

All three are the same shape: plausible looking output, no exception. This is why the verification step for each block was "reproduce this exact number", not "check it looks reasonable".

## Where I left off on 1 August, evening

`src/logger.py` is finished and verified. It was chosen over the evidence assertion deliberately, because the dependency between the two runs one way. The assertion's second check reads `prompt_eval_count` and `eval_count` off the Ollama response and has to store them per example, and the place it stores them is the log record. Building the assertion first would have meant inventing the record shape implicitly and reworking it. The assertion's second check is also untestable without a live model call, and the logger is fully testable with fabricated inputs.

15 checks passed, against fabricated `Record` objects and a scratch directory outside the repo, so `results/` was never touched. The script was throwaway and is deleted; the checks are listed in the build log. The two that matter: a truncated JSON file returns `False` instead of raising, which is the state a crash mid write leaves behind and the one case that would otherwise kill resume on startup; and three writes of the same id leave one file rather than three.

Both bugs hit this session raised exceptions, unlike the afternoon's three. `mkdir(parent=True)` for `parents=True`, and calling `.mkdir()` on `results_dir` before coercing it with `Path()`, which left `write_result` rejecting a string argument that `has_result` accepted.

One thing recorded because it is silent if it ever breaks. A two line `_result_path()` helper was written and then removed as too small to justify a function. The `.json` suffix and the naming scheme now appear in both `write_result` and `has_result`. If those two ever disagree, `has_result` returns `False` for every example, the run repeats a whole night of work, and nothing raises.

Storage was checked before committing to logging full prompts. About 23 KB per record, 2.3 MB for a 102 example run, 16 MB for a full 700. Estimated from one real filled prompt of 15,017 characters plus an assumed response length, so the real figure arrives with the trial run. Storage is not a reason to log less.

Also checked: all 700 `example_id` values are unique and filename safe, so they can name result files with no sanitising.

## Where I left off on 2 August

`src/evidence_asserter.py` is finished and validated against all 700 claims offline, with no model calls and no cloud quota. The harness is complete. Only the run loop remains.

**How the check works.** For each gold context element, take its three rarest tokens, where rarity is counted against the whole report, and look for them in the evidence block. A token with report count 1 appears nowhere in the filing outside that element, so finding it proves the element reached the prompt. Rejected first idea: check for a key sentence. Nothing can pick the key sentence automatically across 700 examples, and a sentence is the fragile size, long enough that any reformatting or chunk boundary breaks the match. Rarity is computable, a token is short enough to survive table normalisation, and a prose element with no numbers still yields rare words.

**The design decision that matters.** The check searches the evidence block only, never the whole prompt. Testing on `ie-val-0` before writing the code showed the natural witnesses for two of its three gold elements were `278.4` and `32253`, both figures the claim itself quotes. Since the prompt contains the claim, those would be found whether or not retrieval returned anything.

The first fix was to filter out every token that also appears in the claim statement. That was built and it worked. The better fix, which came as a suggestion and replaced it, is structural: we control the prompt format, so search only the evidence block and the claim is out of scope by construction. This also keeps the strongest witnesses, which are exactly the numbers the claim copies, instead of discarding them. `claim_tokens` was then removed as redundant.

Parsing the evidence block back out of the finished prompt was considered and rejected, because it would couple the asserter to a template that changes at every tier, and a delimiter that silently stopped matching would break the asserter silently. Instead `build_prompt` returns the evidence block alongside the prompt.

**Validation, `test_scripts/validate_evidence_asserter.py`, about 1 m 45 s.** Four controls over all 700 claims:

    gold   the gold elements                          700/700 present   correct
    decoy  3 random non-gold elements, same report       0/700 present   correct
    hard   non-gold elements sharing the most tokens     5/700 present   0.7%, see below
           with the claim
    claim  the claim statement alone                     0/700 present   correct

False negatives are 0 out of 700. That is the dangerous direction, because it would excuse real model failures as retrieval misses.

**178 of 700 claims, 25 percent, contain at least one witness from their own gold evidence.** That is the measurement justifying the scoping decision. Under a whole prompt check with an "any witness" rule they would all have been false positives.

**The five false positives are structural.** Those gold elements have no unique witness. `ie-val-61`'s three are `direction`, `acquired` and `resigned`, five occurrences each. Raising the witness count from 3 to 7 removes only one of the five, so it is repeated content in the filing, not a tuning problem. Accepted at 0.7 percent under a deliberately adversarial control. Re-check it once the real hybrid retriever exists, since maximum lexical overlap is a proxy for a retrieval miss and not an upper bound.

**Only 59.4 percent of gold elements have all three witnesses unique.** For roughly a fifth of elements a full match is strong evidence rather than proof, and that fifth is where the five false positives come from. `MIN_TOKEN_LEN` was swept and barely matters: 81.0, 80.4, 78.5 and 73.0 percent top witness uniqueness at lengths 2, 3, 4 and 5. Kept at 3, now measured rather than guessed.

**Checked, not assumed:** `id` equals list position for all 137,045 context elements across all 600 reports, so gold indices can index `report["context"]` directly. No testmini claim has an empty `relevant_context` and no gold index is out of range. `test.json` was not checked.

**No cache.** Tokenising and counting a whole report is a median 12.5 ms against a 285,000 ms model call.

## The recall ceiling was being read wrong, corrected 2 August

The published ~68 to 70 percent recall is a **macro average of per claim fractions**, computed by `FinDVer/retriever/recall_evaluation.py` as the mean over claims of matched divided by needed. It is not the fraction of claims that received all their evidence. Section 3.4 of the plan used to gloss it as "3 in 10 claims are missing a piece". That does not follow, and it is wrong.

Recomputed from upstream's own shipped retrieval output, all 700 testmini claims:

    retriever, k=10                macro    element   all-gold
    text-embedding-3-large         68.01%    62.4%     42.6%
    bm25                           65.16%    62.8%     38.6%
    contriever-msmarco             33.48%    28.4%     16.3%
    ours, placeholder              57.54%    53.2%     31.6%

68.01 reproduces the cited 67.91, so the published number is fine and only the reading was wrong. **The correct statement is that 57.4 percent of claims are missing at least one required piece, not 30 percent.** Use the all gold figure in the paper, or name the metric, because "68 percent recall" reads as "68 percent of claims are fine".

**BM25 gets 65.16 percent against the paid embedding's 68.01, and beats it on element recall.** A free local retriever is within three points of `text-embedding-3-large`. Good for an on device paper, and it means the hybrid in section 7.3 has to clear 68.01 rather than treating 68 as far away.

## The trial run, completed 2 August

**12 of 12 completed, 0 failed, 0 skipped, 80.7 minutes.** The pipeline works end to end.
Config: `qwen2.5-coder:3b`, temperature 0, `num_ctx` 16384, `num_predict` 2000, placeholder
token overlap retriever at k=10, prompt `baseline_v1`, 12 examples, 2 per cell, seed 0.

    accuracy                    8 / 12   (67%)
    unparseable                 0 / 12
    evidence present (strict)   4 / 12   (33%)
    prompt tokens               2,283 - 11,134, mean 6,610
    response tokens             261 - 496, mean 394
    done_reason                 "stop" on all 12
    context_overflow            False on all 12

Per subset: ie 4/4 correct, numeric 2/4, knowledge 2/4. Gold is 6 True and 6 False,
predictions are 6 True and 6 False, so nothing degenerate.

Full analysis in the build log, entry for 2 August, late. The five things that change
what happens next are below.

### 1. Zero unparseable. Our own model states a verdict.

11 of 12 fired at the `anchored` level, 1 at `bare`. **The upstream 33 percent none rate is
not our rate.** Twelve examples cannot establish a rate, so the honest claim is only that it
is not 33 percent and probably not near it. The 1 August prediction was that temperature 0
and a generous `num_predict` would remove both mechanisms driving that figure, and the
result is consistent with it. Do not write "3B models fail the output format 45 percent of
the time" into the paper. The 102 example run gives the first number with a real interval.

**Four format behaviours found by reading the actual response texts.** The verdict is
frequently not the last sentence: four of twelve continue writing after it, and one puts it
mid response with 400 characters following. Only the whole response `anchored` search caught
those, so the level 1 design is now justified by data rather than by argument. The model
writes markdown bold inside the verdict sentence. Two responses state the verdict twice.
And `knowledge-val-33` copied the prompt's own placeholder braces, ending with
`Therefore, the claim is {refuted}.` literally. That last one is a prompt bug, not a model
bug, and it is the only example that needed the `bare` level. Fill the placeholder in the
format example in the next prompt version.

### 2. Context overflow did not happen. The estimate was wrong, not the plan.

**0 of 12 overflowed.** The two examples predicted to overflow came in 26 and 31 percent
below prediction. The cause is the 3.6 characters per token conversion, which was taken from
one hand built week 1 sample. **The measured ratio is 4.36 characters per token**, ranging
2.46 to 5.19 across examples.

    largest prompt + its generation      11,630  vs  16,384
    largest prompt + full num_predict    13,134  vs  16,384

Overflow is comfortably out of reach at k=10. Two consequences. **The overflow alarm has
still never fired on real data**, so it is validated only against fabricated counts in the
harness. And because the ratio swings by 2x with content type, table heavy chunks at the low
end and prose at the high end, **a character budget is not a safe proxy for a token budget on
this data.** Any trimming logic must count tokens.

### 3. Runtime is linear in prompt tokens, and the schedule number is worse than thought

Fitted over the 11 examples after the first, which carries the 5.3 s model load:

    elapsed = 0.0641 s per prompt token       R2 = 0.995
    implied ingestion rate                    15.6 tok/s
    mean per example                          419 s (7.0 min)

A fit separating ingestion from generation was attempted and **rejected as degenerate**,
because `eval_count` only varies 261 to 496 so the generation term is unidentifiable. Do not
report separated rates from this run.

    run                  plan says   measured
    102 example slice        ~8 h      11.9 h
    full testmini, 700      ~55 h      81.6 h

**Section 12.1's night budget needs correcting.** A 102 example slice is still one night but
a full one, 9pm to 9am. The full 700 run is now about 10 nights of the roughly 20 remaining,
up from 7, which pushes it further into the conditional band.

**Prompt size is the whole cost model, so it is the whole lever.** At the fitted rate,
cutting the mean prompt from 6,610 to 3,000 tokens takes a 102 example run from 11.9 hours
to about 5.4. That is an efficiency argument for tighter retrieval standing on its own,
separate from the recall argument, and it points at the same work.

### 4. The retriever misses entirely, it does not run out of room

    claim level, all gold present     4 / 12    33%   (offline over 700: 31.6%)
    element level, fully present     22 / 36    61%
    element level, partial            1 / 36
    element level, absent            13 / 36

The claim level figure lands within 1.4 points of the placeholder retriever's measured 31.6
percent over all 700 claims, so the stratified sample behaves.

**This answers the question the 2 August log posed.** Of the 14 gold elements not fully
retrieved, 13 scored `0/3` witnesses and one was partial. `0/3` means never retrieved at all.
A column of `2/3` would have meant retrieval worked and k was too small. This is a ranking
problem, so raising k does not fix it and costs wall clock linearly.

**How solid is `evidence_present = True` on these four claims?** Checked individually rather
than resting on the 700 claim average, because the accuracy split below depends on them. Of
the 10 gold elements across the 4 claims, **8 have all three witnesses unique in the report**,
which makes presence conclusive, since those tokens appear nowhere in the filing outside that
element. Two do not: `ie-val-108` element 19, whose witnesses appear twice each, and
`numeric-val-242` element 258, whose witnesses are short numeric strings appearing up to three
times. The second is the one place in the trial run where True is meaningfully softer than
proof. The asymmetry from 2 August still holds and is the one that matters: **False is
reliable**, because false negatives are 0 in 700.

### 5. Accuracy split by retrieval, and why not to trust it yet

    overall                  8 / 12   (67%)
    evidence present         4 / 4    (100%)
    evidence absent          4 / 8    (50%, exactly chance)

This is the shape the retrieval ceiling argument predicts and the first end to end evidence
for it. **It is also four examples against eight, and 4/4 is entirely consistent with luck.**
At n=4 the 95 percent interval on 100 percent runs down to roughly 40 percent. Do not put it
in the paper and do not treat it as confirmation. It is a reason to prioritise retrieval,
which was already the priority, and a hypothesis the 102 example run can actually test.

One note on the other half. 50 percent is what a coin flip gives, but the model is not
flipping a coin. It reasons confidently over the wrong chunks to a decisive wrong answer,
which is a different failure with the same score.

### A correct label from broken arithmetic

`numeric-val-242` scores correct, with evidence fully present, and its reasoning contains two
separate errors. It computed `$15,800,000 + $0.015 million = $15,800,015`, treating $0.015
million as $15 rather than $15,000, then declared $15,800,015 equal to $15.815 million, which
is off by about $15,000. Both errors happen to leave the verdict unchanged.

That is **data trap 7 in `CLAUDE.md`, the magnitude trap, appearing live in our own pipeline
for the first time.** Three consequences. Label accuracy overstates reasoning quality on the
numeric subset, and we now have a concrete instance rather than a worry, which is exactly
what the per error category analysis in section 5.3 is for. It is a direct argument for the
code sandbox in section 7.2, since a model computing in Python cannot make either error. And
**the error taxonomy needs a category for "correct label, invalid reasoning"**, which is
otherwise invisible because the only automated signal, the label, says the example passed.
Detecting it needs the faithfulness verifier in section 7.5, currently in the stretch band.

Whether this is common is unknown. The numeric subset was 4 of the 12.

### Two small operational things

The first invocation of `run.py` was pasted across two lines, so zsh ran it with no argument
and then tried to execute the config path as a command, giving `permission denied`. Nothing
ran, `run.py` printed usage and exited. **Requiring the config argument is what made this
harmless**, and it stays that way. A default config would have silently run the wrong
experiment overnight.

`evidences_found` does not round trip through JSON. In Python it is `{14: (3, 3)}`, an int
key mapping to a tuple. Read back from the result file it is `{'14': [3, 3]}`, a string key
mapping to a list, because JSON has neither integer keys nor tuples. Analysis code that
indexes it with an integer gets a `KeyError`. Coerce with `int(k)` on read.

### What the trial run settled, against the four jobs it was given

1. **The provisional output format row in section 4.6.** Settled with a logged artifact
   instead of recollection. Our model does produce a usable verdict, though frequently not as
   the final sentence. Caveat: measured on `baseline_v1` at `num_ctx` 16384, not on
   `ie-val-0` at 8192, so it does not literally replace that row's measurement.
2. **First responses from our own model at temperature 0.** Done, 12 logged.
3. **First honest none rate for our configuration.** 0 of 12.
4. **`num_predict` against our own model's reasoning lengths.** Done. Longest response was
   496 tokens and 354 words against a 2,000 cap, so the cap is about 4x larger than needed.
   It costs nothing, being a ceiling and not a reservation, but it is subtracted from the
   prompt budget in section 4.3. Leave it until the 102 run gives a better tail estimate.

Plus three it was not given: the real chars per token ratio, the real cost model, and the
first end to end evidence present split.

### Prompt trimming: still not built, and the reason for it has changed

It was specified to prevent overflow. **Overflow does not occur**, so it is now a wall clock
optimisation rather than a correctness fix. It competes against building a real retriever,
which would cut prompt size and raise recall at once. Given that runtime is linear in prompt
tokens and the placeholder misses entirely rather than partially, **the retriever is the
better next investment and trimming should probably wait behind it.** Trimming still has to
exist before any run at a larger k, and it must count tokens rather than characters.

### Also still open from 31 July

The FINDVER leaderboard check and the citation sweep. Neither has been done, and both are
needed before repeating any claim that nobody has attempted something.

## Outstanding, not yet done

~~Decide the two cloud models and the two added edge models before 3 August.~~ **Partly done 3 August.** Cloud: DeepSeek is primary, decided by him. Still need the exact model string and endpoint, and an answer on whether an Anthropic key is available for the second slot. Edge: he did not answer, so Qwen2.5-Coder-3B and Qwen2.5-Coder-7B proceed as a decision unless he objects. Open questions 7 and 8 both remain formally open.

~~Answer open question 11: what faster machine is available, with what specs, and when.~~ **Partly done 3 August.** A GPU server exists and he has offered it. Still need the real card and VRAM, the access method, whether it is shared, and whether jobs can run for days. Note "RTX 4090 Ti" is not a product that shipped.

**Reply to him.** Confirm the server and ask the four questions above. State the two edge models as a decision rather than a question, since Phase 2 starts now and cannot wait on his inbox. Make the Anthropic case in one sentence. Raise the open question 8 contradiction below.

**Raise the open question 8 contradiction with him.** OQ8 requires edge models FINDVER did not evaluate, which optimises for new table rows. But the paper's claim is that the pipeline improves a small model, and the cleanest evidence for that is the same model, published baseline against ours, with the pipeline as the only variable. `Llama-3_2-3B-Instruct` is published with 700 stored responses already on disk. OQ8 disqualifies it; a pipeline contribution framing makes it the best candidate. The confound is that upstream's RAG setup is not ours. Not resolved.

**MACE's accuracy number is not written down anywhere.** Section 6.1 records its weaknesses and the 27 to 92B scaling remark, but not the headline figure. Section 5.3 states our contribution as matching the all big model design and section 9.2 builds condition 3 to compare against it, so the number we are trying to match is currently unknown. Pull it from arXiv 2604.17225. Related: since the project is RAG only, the comparable Claude-3.5-Sonnet figure is **75.0% RAG, not 77.2% long context**. MACE's recall of 67.91% is not a target, it is FINDVER's own setup copied unchanged.

**Three latency quantities are not measured and must be, before writing.**

1. 7B latency on the MacBook. The 11 m 46 s figure is one week 1 example and recollection. Re-measure it or label it an estimate.
2. Pipeline latency as opposed to baseline latency. The measured 7.0 min is `baseline_v1` with the placeholder retriever at k=10, no code execution, no table parsing, no cloud round trip. The finished system is a different number. This gap exists whether or not a GPU is involved, because the system does not exist yet.
3. Cloud round trip latency. Calls per example times API latency. Entirely unmeasured, no key used yet.

All three are covered by the one MacBook night budgeted at the end, after the pipeline freezes.

~~Confirm the workshop mechanics.~~ **Done 1 August, from the workshop site rather than the professor.** It is a NeurIPS 2026 workshop in Sydney, 11 or 12 December. Five pages excluding references, NeurIPS 2026 LaTeX template, submitted through OpenReview. Review is **double blind**, so no author names and no identifying repository link in the PDF. The venue is **non archival**, so a fuller version can go elsewhere later and this paper does not have to be the final word. Deadline 29 August AoE. Full table in section 1.1 of the plan.

## Measured performance, for planning purposes

**Superseded for the 3B model by the trial run, 2 August. Use these numbers.**

Runtime on the 3B model is linear in prompt tokens, fitted over 11 real examples at
R squared 0.995:

    elapsed = 0.0641 s per prompt token, about 15.6 tokens per second ingestion
    mean per example, at our current mean prompt of 6,610 tokens:  419 s, 7.0 min
    102 examples   11.9 h
    700 examples   81.6 h

The week 1 figures below were measured on one example with a roughly 4,000 token prompt and
are what the plan was built on. The 3B row is now known to be optimistic, because real RAG
prompts are larger than that sample and the sustained ingestion rate is 15.6 tokens per
second rather than 19.1. The 7B row has not been re measured and is still an estimate.

    3B   4 m 45 s per example,  ~8 h per 100,  ~55 h for 700   superseded, see above
    7B  11 m 46 s per example, ~20 h per 100, ~137 h for 700   not re measured

Memory peaked at 2.5 GB and 5 GB respectively, so RAM is not the constraint. CPU speed is.

Because cost is linear in prompt tokens, prompt size is the only real lever on wall clock.
Cutting the mean prompt from 6,610 to 3,000 tokens would take a 102 example run from 11.9
hours to about 5.4.

Reading a report file from disk takes about 7 milliseconds, so re-reading one per claim across all 700 costs about 5 seconds in total. That is 0.02 percent of an 8 hour run and is why the loader does not cache.
