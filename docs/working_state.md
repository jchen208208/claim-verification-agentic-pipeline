# Working state

Fast changing information only. For anything stable, including the architecture, the build order, the schedule, the data schema, and the related work, see the architecture plan. For a dated record of what was built in each session, see `build_log.md`.

Last updated: 18 August 2026.

---

## The deadline

The paper is due **29 August 2026, 23:59 anywhere on earth**. That is 04:59 Pacific on 30 August, and 19:59 Beijing on 30 August.

**Corrected 1 August.** Every document said 30 August, taken from the professor at the 30 July meeting. The workshop site says 29 August. One day of the writing phase is gone.

The deliverable is a paper of about five pages, submitted to a workshop in Australia called *On-Device Intelligence: Foundation Models under Real-World Constraints*. I am first author. My professor is a co-author and will recruit about two industry co-authors.

This voids the eight-week schedule. Section 12 of the architecture plan has been replanned around 30 days.

**Nothing is cut.** Scope is banded by what compute is available, in section 12.3. Band A is committed and fits on this machine. Band B is conditional on faster hardware and holds the full 700 run, the end to end retrieval ablation, and the 7B comparisons. Band C is stretch and holds the glossary, the faithfulness verifier, and the routing sweep.

An earlier draft of the replan cut tiers 2 through 5 outright. That was wrong. It cut retrieval, which is the core of the project, and it priced the whole of tier 2 as if it needed overnight runs. It does not. **Retrieval recall is scored against the gold `relevant_context` indices with no model calls at all**, so a k sweep, a BM25 comparison, and a decomposition comparison are minutes of work, not nights. Only the end to end accuracy delta from better retrieval needs a night. The cheap half is also the half most on topic for a RAG focused paper, so it goes early rather than last.

Read section 12.1 of the plan before scheduling anything that runs locally. The short version: between 3 and 23 August there are about 20 usable nights, one 3B slice run costs one night, one 7B slice run costs two to three, and a full 700 run would cost seven on this machine. Results have to freeze by 23 August so that writing can start on the 24th.

If a faster machine materialises the night budget stops binding and Band B opens. ~~**Updated 3 August: the professor has offered a GPU server.** Band B is now likely rather than hypothetical.~~ **Withdrawn 7 August. The professor's GPU server is unavailable and will not be available before the deadline.** He has several dozen RTX 4090 units, but they sit on a local network with no public IP address, and his students have not been able to obtain one. He expects it might be resolved after the semester starts in September, which is after 29 August. Plan against this machine. The only remaining path to Band B is the brother's desktop, which is untested. See the 7 August section below and open question 11 in the plan.

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

## Where things stand, 5 August

**The embedding index built cleanly overnight.** 89 reports, 20,718 elements, 137 minutes,
0 failures, against a 2.5 h estimate. Cached in `embeddings/`, gitignored. numpy is now
installed, via `pip3 install --break-system-packages numpy`, because this machine runs
Homebrew Python 3.14 marked `EXTERNALLY-MANAGED`. The raw float32 files read straight back
with `np.fromfile(path, dtype="float32").reshape(-1, 768)`.

**The dense arm go/no-go ran and came back ambiguous, for a reason that is our fault.**
All rows on the 102-claim slice, k=10:

    ours, bm25                          76.18%   71.0%   53.9%
    nomic-embed-text alone              62.86%   55.5%   35.3%
    RRF(bm25, nomic) equal votes        75.57%   70.0%   49.0%
    control: RRF(bm25, text-embed-3)    76.08%   71.0%   53.9%
    union, ceiling                      83.27%   78.6%   61.8%

**nomic is good**, 62.86%, five points below the paid embedding and nearly double contriever.
A free local embedder landing that close is worth a paper row on its own.

**The fusion rows are not interpretable.** The control fuses our BM25 with the *paid*
embedding, which is known to gain +2.54 on all 700, and it gains nothing here. A null result
on a fusion known to work at full scale measures the instrument, not the method. The noise
floor proves it: our BM25 is 74.60% on all 700 and 76.18% on this slice, a 1.58-point swing
from sampling alone, against a 2.5-point effect under test.

**Recorded as a design error.** The slice was sized to separate 33% from 68%, which it does
cleanly, then used to ask whether fusion adds 2 points, which it cannot answer. Two questions,
two required sample sizes, one run.

**Also learned: weighted RRF has almost no useful range.** At k=10 and c=60, any weight ratio
above about 1.16 makes the heavy list's worst element outrank the light list's best, so the
fusion returns the heavy list unchanged. Weights of 1.25, 1.5, 2 and 3 all return our BM25
exactly. Only about 1.1 blends anything.

## What happens next, in order

### Claim decomposition is closed. It does not help retrieval.

**Tested and negative, 5 August.** 174 claims needing 4 or more gold elements, which is where
BM25's deficit lives, 36.7 minutes of 3B model time, six merge strategies. Full detail in
§3.4.3 of the plan.

    whole claim only, the bar     57.88%
    best decomposed variant       57.53%   max raw score across queries
    worst                         45.27%   RRF across queries

**The decompositions themselves were good.** Numbers, dates and names came through exactly,
which was the main risk to BM25's exact-string matching. About a fifth of sub-claims are
fragments rather than self-contained facts, but they still carry the tokens BM25 needs. The
failure is not decomposition quality.

**A false positive was caught mid-analysis.** The union of whole-claim and sub-claim results
scores 76.14%, and 101 of 174 claims had gold that only sub-claims found. That was read as
"the merge is failing, not the split." It was wrong: the union holds 30.3 candidates against
10, and the whole claim at k=30 scores **79.37%**, better than the union. Any multi-query
comparison must control for candidate count or it produces this same illusion.

**No further decomposition testing on other samples is needed.** The test already ran on the
population where the mechanism had the most to fix. On easier claims there is less room, not
more. **This does not close decomposition for Tier 1 reasoning**, which is what §3.6's original
observation was actually about and which is measured end to end, not on recall.

### The real finding: k is the biggest lever we have

Our BM25 over all 700 claims:

    k=5    62.39%      k=20   84.56%
    k=10   74.60%      k=25   86.34%
    k=15   81.12%      k=30   88.51%

**k=10 to k=30 is worth 13.9 macro points.** The whole dense-fusion question was worth +2.5,
and the published baseline everyone copied is 68.01%. This is a parameter, not a component.

### Four factors decide k, and only one is free

1. **Recall.** Free, measured, above.
2. **Ingestion cost.** k sets prompt length, and prompt length is the entire cost model at
   R² 0.995. Generation barely moves: trial-run `eval_count` ranged only 261-496. Being
   measured now.
3. **Accuracy. No data at all.** Higher k adds distractors as well as gold, and a 3B model may
   not ignore them. The only contrary evidence is the trial run's 4/4 with evidence present
   against 4/8 without, which is n=4 and already flagged as untrustworthy. **Costs one
   overnight run per k value.**
4. **The deployment story**, a paper decision rather than a measurement. The MacBook is the
   device of record, so the latency reported is the MacBook number no matter where accuracy was
   measured. Doubling per-example time weakens the exact axis §6.1 attacks MACE on.

**A GPU does not remove factor 4.** Accuracy and ablations may run on the server, and a k sweep
qualifies. But reported deployment cost stays the MacBook figure. A GPU makes the experiment
affordable, not the operating point cheap.

**Likely paper framing: the curve, not the maximum.** Recall against measured per-example
latency across k, on the device, with a defensible operating point chosen. Stronger than a
single tuned k, and it turns the cost of high k into the finding.

### The current configuration has a live overflow defect

Token calibration done, 6 real calls. **Measured ingestion is 12.8-23.2 tok/s, mean about 16**,
the first clean figure; the old 15.6 absorbed generation. **Chars per token is 3.31 on
table-heavy content against 4.44 on prose**, so it is not a constant and a character budget is
not a safe proxy.

Prompt tokens across all 700 at the conservative 3.31 ratio:

    k     mean     p90      max   over 14384   over 30768
    10    4426    9490    19466      15/700       0/700
    15    6472   13627    29589      62/700       0/700
    20    8454   17734    36544     104/700       6/700
    30   12328   26885    52241     139/700      53/700

**About 15 of 700 claims overflow at the current k=10 with `num_ctx` 16384.** Not caused by
raising k. Never caught because the trial run was 12 examples. Ollama 0.12.3 evicts the oldest
prompt tokens silently and still reports `done_reason: "stop"`, so those examples would return
confident answers over evidence that had scrolled out of view.

**Prompt trimming is now mandatory, not an optimisation**, and it counts tokens. **k=30 is
unreachable** with 53 of 700 over even at `num_ctx` 32768, so **k=20 is the practical ceiling**
and is the high candidate for the k experiment.

### Corrected: fusion is decided BEFORE condition 1

The earlier plan, to decide k through condition 1 and settle the dense arm afterwards, is
invalid. §9.2 requires every condition to share the same retrieval and says changing retrieval
moves all four conditions. Condition 1 freezes the retriever, so adding a dense arm afterwards
forces a re-run.

The two questions need different evidence, which is what dissolves the circularity. **Fusion or
no fusion is a retriever choice decided on recall, which is free**, since fusion changes which k
chunks are retrieved rather than how many, so the distractor argument does not apply. **k is
decided on recall and accuracy**, since k is exactly the knob trading gold against distractors.

## THE RETRIEVER IS FROZEN: BM25 alone, no dense arm

Full index built, 255 reports, 60,871 elements, 179 MB, 362.7 minutes, 0 failures. Fusion then
decided on recall at n=700 by `test_scripts/decide_fusion.py`.

                                   k=10     k=15     k=20
    ours BM25 alone               74.60%   81.12%   84.56%
    nomic-embed-text alone        58.66%   66.04%   70.59%
    RRF(BM25, nomic) equal        75.00%   80.71%   84.55%
    RRF(BM25 x1.1, nomic)         75.20%   81.75%   85.76%
    union of the two, ceiling     81.28%   86.42%   89.13%

**Dropped, for three reasons.** Untuned fusion gains nothing: +0.40, -0.41, -0.01. The +0.6 to
+1.2 appears only at weight 1.1, chosen by reading these results, which is the same test-set
selection we rejected for the `k1`/`b` sweep's +0.37. It is also dominated by a parameter:
**BM25 alone at k=11 scores 76.29%, beating fused retrieval at k=10's 75.20%**, for 398 extra
prompt tokens and no second model. And it costs a second resident model plus a 179 MB index for
about one point in a paper about on-device feasibility.

**Honest caveat:** at k=20 fusion's +1.20 is worth roughly three k steps, so on wall clock it is
nearly a wash there. The tuning objection decides it, not the cost.

**The frozen retriever.** `src/bm25_retriever.py`, `k1 = 1.5`, `b = 0.75`, one `context` element
per chunk, Lucene IDF, punctuation dropped, no stemming, per-report corpus. **k is not frozen
and is decided by condition 1.**

**Keep `embeddings/` until after submission.** Derived data and deletable in principle, but
rebuilding costs 6 hours and it is 179 MB against a 1.3 GB clone already on disk.

### DECIDED 5 Aug: `num_ctx` goes to 32768 in every config from here

`num_ctx` 16384 is no longer safe. At the current k=10 it already leaves ~15 of 700 claims
overflowing, and at k=20 it leaves 104 of 700.

    num_ctx    k=10 over    k=20 over    RAM (of 16 GB)
    16384        15/700       104/700        3.2 GB
    32768         0/700         6/700        4.4 GB

**An unused window costs RAM, not time** (§4.3), so the only price is 1.2 GB against a machine
where peak usage is 2.5 GB. Without this change prompt trimming would be discarding real
evidence on 104 claims at k=20 rather than 6.

**Every config file from here uses `num_ctx` 32768.** `configs/trial_run_3b.json` keeps 16384
because it records what actually produced the 2 August trial results and must not be edited.
Re-measure the RAM figure before assuming it holds for the 7B, whose KV cache is larger.

### Prompt trimming is built and verified

`src/prompt_trimmer.py` exists, `build_prompt` and `Record` are updated, and all checks pass.

    test harness                              26/26
    k=10, 40 random claims                    kept == 10, prompt byte-identical to untrimmed
    k=20, the six predicted trim cases        6/6 exact
    k=20, all 700                             exactly 6 trimmed, 0 raised
    k=20, recall through the trimmer          84.56% / 81.7% / 66.6%, unchanged

**Trimming costs no recall at k=20.** 15 chunks dropped across 6 claims and none held gold,
because trimming drops from the bottom of the BM25 ranking and gold sits high. Scope that to
this configuration: 6 claims and 15 chunks is an observed result, not a guarantee, and it needs
re-checking at a higher k or a tighter budget.

**The module may never run.** At `num_ctx` 32768 and k=10 it fires on 0 of 700. If condition 1
picks k=10 it is dormant insurance, by design and not dead code.

### What happens next, in order

1. ~~**Build prompt trimming.**~~ **Done 5 August, see above.**
2. ~~**Write the condition 1 configs and close the harness drift item.**~~ **Done 6 August**,
   see the section below.
3. **Condition 1 at two k values**, 10 and 20. The winner becomes the official condition 1, the
   loser is a k-ablation row. **Machine must be decided before this starts**, and whichever
   machine is chosen carries the whole results table.

Steps 1 and 2 need no GPU. Step 3 is the one blocked on the machine question.

## Where things stand, 6 August

Daytime work only, no nights spent. Full detail in the build log entry for 6 August.

**Everything before condition 1 is now built and tested.** `configs/condition1_3b_k10.json` and
`configs/condition1_3b_k20.json` exist, `run.py` selects its retriever from the config, and the
harness is at 38/38 with the config files themselves now under test.

**Two silent-failure bugs were caught before anything ran.** `run.py` read the `retriever` key
only to print it, so a config saying bm25 would have run the placeholder for twelve hours with
no error. And the `experiment` key was missing `_3b`, which would have made the 7B run resume
into the 3B's results directory and skip all 102 claims in about a second. Both are the same
shape as the loader bug and the `num_ctx` truncation: a wrong answer rather than a crash.

**The order for condition 1, confirmed.** Run the 3B at k=10 and k=20. Pick k on accuracy, since
recall is already measured and rises 13.9 points from k=10 to k=30 with distractors as the
counterweight. **Freeze k there, and everything downstream inherits it**, including the 7B,
conditions 2, 3 and 4, and the 700 run. §9.2 requires every condition to share the same
retrieval, so k is not a per-condition knob.

**Two caveats on that, neither of which changes the plan.** The frozen k is chosen on the 3B, and
a larger model may tolerate more distractors, so k=20 could in principle suit the 7B better. It
is still frozen at the 3B's answer, because a k that moves per model makes the comparison
meaningless, and the 3B is the paper's primary model. Say this as a limitation rather than
letting it pass unnoticed. Separately, if the two k values land within a point or two of each
other, do not treat the winner as settled: temperature 0 does not guarantee identical tokens
across CPU and CUDA, so a near-tie could flip on a different machine.

**The 7B is still conditional**, not scheduled. It is a row and not a switch, per the 3 August
hardware rule, and a 7B slice run costs two to three nights against the 3B's one.

### The BM25 smoke run, 6 August evening

Six examples, `configs/smoke_bm25.json`, BM25 at k=10, `num_ctx` 32768. **6 ok, 0 failed,
23.2 minutes.** Full detail in the build log entry for 6 August, evening.

**It validated the one path the harness cannot reach.** BM25 now runs through `run.py` end to
end. Also 0 of 6 unparseable with all six caught by the extractor's strongest level, 0 of 6
overflow, 10/10 chunks kept so the trimmer stayed dormant, and the resume logic confirmed live.

**Runtime, measured on our own retriever:**

    time = 0.0808 * prompt_tokens + 0.0317 * generated_tokens     R^2 0.904, n=6
    ingestion 12.4 tok/s, generation 31.6 tok/s

**Projected on BM25's 700-wide mean prompt of 4,426 tokens: 371 s per example, so about 10.5 h
for 102 and 72 h for 700**, against 12 h and 82 h in the plan. About 12% better. **The schedule
does not change.** Do not use the older 419 s per example figure for BM25 runs; it was the
placeholder at `num_ctx` 16384.

**Two errors made and corrected the same evening, both worth remembering.**

1. **A claim that BM25 halved prompt size, 6,610 to 2,875 tokens. Wrong.** Those are a 12-example
   sample and a 6-example sample of different retrievers. The population figures are 4,737 and
   4,426 over all 700, a 7% difference. Small samples read low because the distribution is
   right-skewed. **This is the same sample-versus-population error the 5 August entry already
   recorded**, repeated one entry later.
2. **A contaminated timing.** `ie-val-108` returned 33.6 s because the same command had been run
   and killed 45 seconds earlier while debugging, leaving that prompt resident in Ollama. Re-run
   cold it took 168.7 s. **Nothing in the result file marks a contaminated example**, so never
   run the pipeline to debug it while a real run is pending on the same claims.

**`num_ctx` 32768 was questioned and the 5 August decision stands.** The apparent slowdown came
from comparing against a superseded 2 August figure. A clean measurement at 32768 already exists
at 12.8-23.2 tok/s and today's 12.4 sits inside it. No A/B is being run, because 16384 trims 15
of 700 claims at k=10 and 104 at k=20, so it cannot change a decision until k is frozen.

**Recall on the six was macro 61.9% and all-gold 2/6.** Both are inside what n=6 produces by
chance against the true 74.60% and 50.4%. Accuracy was 4 of 6, which supports no claim.

### Open going into 7 August

- **The machine.** An Instagram message went to the professor asking the exact GPU model and the
  access method, with the deadline stated. If there is no answer by the 7th, choose between the
  MacBook and the brother's desktop and start.
- **The brother's desktop needs a 30-minute smoke test before it can be chosen.** AMD Radeon
  RX 7800 XT, 16 GB VRAM, available any night. VRAM is not the constraint. **AMD is**, because
  Ollama uses ROCm rather than CUDA there and falls back to CPU silently if it does not engage.
  Install Ollama, pull the 3B, confirm from the server log that it loaded onto the GPU, and time
  3 to 5 real examples. We have no measured throughput for that card and the 700 run would be
  planned against it.
- **BM25 has never run through `run.py`.** Every end-to-end run so far used the placeholder, and
  the harness injects retrieval stubs. A 6-example smoke run at `per_cell` 1 costs about 40
  minutes and retires that risk before a 12-hour night is committed.
- **A progress email is owed**, separate from the hardware request: the retriever freeze, the
  three rejected approaches, the second local model, and the cloud quota.
- **`evidence_asserter.py:83`**, the `check_overflow` docstring still says `num_ctx` 16384.

## Where things stand, 7 August

**No nights spent, nothing ran locally, and the two blocking items did not move.** The machine
test and the local model decision are both still open at the end of the day. Full detail in the
build log entry for 7 August.

### The GPU server is gone

Several dozen RTX 4090 units exist. They are on a local network with no public IP address, his
students have not solved it, and he expects a fix only after the semester starts in September.
That is after the deadline. **Treat it as unavailable, not delayed.**

Two fallbacks he offered, neither scheduled: he will try to find a machine that can bridge access,
and failing that he is **willing to pay for a rented third-party GPU server**. The brother's
desktop stays first choice because it exists today and costs nothing.

**Consequence.** The 700 run is ~72 h on this MacBook, 7 to 10 of the ~16 nights before the
23 August freeze. It does not happen. n stays 102, the margin stays ±10 points, and "we match
condition 3" stays unprovable. Band A carries the paper, as §12.3 already planned.

### What the meeting settled, 7 August

1. **The local model is our call.** His criteria: strongest but light, ideally around 3B for the
   on-device framing, chosen to give the best chance of matching condition 3.
2. **Cloud is `deepseek-v4-pro` and `deepseek-v4-flash`.** On Anthropic he said there is no reason
   not to, but will not have me paying for a key myself, and he cannot pay for it because he is in
   China and Anthropic does not serve China. **This is a payments constraint, not a scientific
   objection.** It was previously recorded as though he preferred DeepSeek on merit.
3. **Write the paper on Overleaf**, load the existing findings into a project, start writing, share
   it with him.
4. **Next week's meeting is about pipeline design**, closing the gap between condition 4 and
   condition 3. Conditions 1 and 2 should be done by then.

### The local model question, reopened by him and not yet answered

He questioned whether a Coder model suits reading comprehension. **Checked: he named
`Qwen2.5-Coder-3B` himself** in the early email recorded at §14 item 5. The 7B second model was
ours.

**His objection is right for condition 1**, which has no code in it anywhere and is the floor
everything is measured against. It is defensible for Tier 1, where the model writes Python for the
arithmetic. **The risk if it stays:** a model that reads badly but codes well makes the condition 4
minus condition 1 delta look large for the wrong reason.

**A contradiction, unresolved.** His criterion says pick the strongest model that still fits the
on-device story. OQ8 says 3B stays primary because a bigger model eats the contribution, since the
delta is largest where the base model is weakest. These optimise different things. Write it as a
stated limitation.

**A framing error corrected.** "Matching condition 3" does not require a local model that rivals
DeepSeek. Condition 4 is the 3B *plus* DeepSeek on the judgment-heavy steps, so the local model
only has to be good enough at the mechanical work that we do not escalate everything. Escalating
everything would be condition 3 at condition 3's cost.

**Candidates if it changes:** Qwen3-4B is the current recommendation, because the paper already
tested `Qwen2_5-7B-Instruct`, so a newer and smaller Qwen beating an older and larger one is
exactly the on-device story. Gemma 3 4B and Phi-4-mini are the alternatives. **Verify availability
and tags on ollama.com before committing; none of these has been checked.** Switching is free
today and costs a re-run once condition 1 starts.

### The model decision is keyed to the machine, and the ordering matters

**The GPU test comes first. It does not wait on the model decision, it decides how much the model
decision costs.** And the test has to run `qwen2.5-coder:3b` for a mechanical reason: the
comparison baseline is `configs/smoke_bm25.json` at 23.2 minutes for six claims on that exact
model, sample and seed. A different model leaves nothing to divide by.

**Is 4B still on-device? Yes, comfortably.** The hardware rule already allows 8B or below, the
FINDVER paper's own baselines include 7B and 8B models, and a 4B at 4-bit quantisation is about
2.5 GB. The argument only starts above 8B.

**What actually differs, separating the measured from the guessed.** That a 4B is more accurate
here is plausible — newer generation, general instruct rather than code-tuned, more parameters —
and **completely unverified on this task**. The tradeoff direction is real: a stronger base model
raises condition 4 and shrinks condition 4 minus condition 1. **The only part that is not a guess
is wall clock.** A 4B is about a third larger, so ingestion drops from the measured 12.4 tokens
per second to roughly 9 or 10, taking a 102-example run from 10.5 hours to about 13 or 14. On the
MacBook with ~16 nights left that is material. On a working GPU it is nothing.

**If the GPU works:** run condition 1 at 102 on both models, about an hour each. Pick on measured
accuracy rather than argument, and the loser becomes a paper row instead of a limitations
sentence.

**If the GPU fails: stay on `qwen2.5-coder:3b`.** Four reasons, in order of weight.

1. **One shot per night, ~16 left.** Switching costs a pull, a fresh throughput measurement, a
   6-example smoke run, and then a 13-hour run instead of 10.5.
2. **It is already proven end to end** through `run.py`, 6 of 6, with a fitted cost model.
3. **The professor chose it himself** (§14 item 5), so keeping it needs no justification to him.
4. **His objection cuts the way we want.** Condition 1 is a *floor*. A weaker floor makes the
   pipeline's contribution more visible, which is what OQ8 says to optimise for.

**One extra thing a working GPU buys.** Running `qwen2.5-coder:3b`, `qwen2.5:3b` and `qwen3:4b` at
102 each is about three hours on a GPU. That **answers the professor's Coder objection with data**
— same size, code-tuned against general instruct — instead of with an argument, and it is a
defensible ablation row. On the MacBook it is three nights and does not happen.

### DeepSeek works, and V4 Pro is a reasoning model

One live `curl` against `https://api.deepseek.com/chat/completions`, OpenAI-compatible, model
`deepseek-v4-pro`, `temperature` 0. It returned normally. **Condition 2's external blocker is
closed.**

**32 of 34 completion tokens were reasoning**, on the input "Say OK". The response carries a
separate `reasoning_content` field and a `reasoning_tokens` count.

    content              the final answer
    reasoning_content    the model's reasoning, billed, returned separately
    model                echoes what actually served the request
    system_fingerprint   fp_9954b31ca7_prod0820_fp8_kvcache_20260402

Three consequences. **The extractor must read `content` only**, never `content` plus
`reasoning_content`, because `extract_label` takes the last match within a level and the reasoning
may weigh the opposite verdict before the final answer. Log `reasoning_content` anyway, it is free
evidence for the error taxonomy. **Every cloud cost estimate needs re-measuring** on one real
4,426-token claim, because reasoning tokens are billed and no figure from a non-reasoning model
transfers. And **`model` and `system_fingerprint` should be logged**, so a silent model roll shows
up in the result files rather than as unexplained variance.

**`deepseek-v4-flash` is a floating alias** routing to `DeepSeek-V4-Flash-0731`. Pin the dated
string if the endpoint accepts it. Untested.

**Which model goes where: pro for conditions 2 and 3.** Flash is a cheaper extra row and the
natural escalation target inside condition 4. Putting flash in condition 3 would lower the bar we
claim to match.

**`Record` needs two new fields for this and they were deliberately not added.** `logger.py:19` is
`response: str`, the text only, so `model` and `system_fingerprint` are not captured. Nothing in
condition 1 touches DeepSeek, and the harness asserts all 18 `Record` fields are present, so adding
fields means editing the logger and the harness on the day a ten-hour run starts. Deferred to the
DeepSeek client work.

## THE GPU WORKS: 36.8x, and Band B is open

`configs/smoke_bm25_gpu.json`, six claims, same sample and seed as the MacBook baseline.
**6 ok, 0 failed, 37.7 seconds total against 23.2 minutes.** Full detail in the build log entry
for 7 August, evening.

**The card is an RX 7600 XT, not the RX 7800 XT every document said.** Navi 33 / gfx1102, 16 GB
VRAM, driver 32.0.31035.1003. Roughly half the bandwidth and compute of the assumed card. **It did
not matter** — ROCm engages on gfx1102 and the speedup is enormous regardless. Do not read "7800
XT" anywhere and expect these numbers from that card.

    example              mac_s   gpu_s   ratio    mac_lbl  gpu_lbl   gold
    ie-val-108           168.7     7.8   21.6x      False    False  False
    ie-val-174           199.7     5.7   34.9x      False     True   True
    knowledge-val-197    188.5     6.6   28.7x      False    False  False
    knowledge-val-53     342.0     4.9   69.3x       True     True   True
    numeric-val-158      271.9     5.4   50.4x       True     True   True
    numeric-val-5        218.7     7.3   30.0x       True     True  False
    TOTAL               1389.4    37.7   36.8x

Model digest `f72c60cabf62` identical to the Mac's, so weights and quantisation match.
`done_reason` was `stop` on all twelve records.

### Verdicts do not fully reproduce across machines. 5 of 6.

**`ie-val-174` diverged:** MacBook `False`, GPU `True`, gold `True`. The GPU was right, which is
luck at n=6 and means nothing.

**`prompt_eval_count` is identical on all six**, so retrieval, sampling, trimming and prompt
building are perfectly deterministic across machines. **The divergence is entirely in generation.**
Generated-token counts moved a lot: 503→395, 644→485, 458→287, 246→519. Greedy decoding at
temperature 0 still depends on floating-point arithmetic, and CPU and ROCm kernels do not produce
bit-identical logits.

**The hardware rule predicted this and it is now measured, not assumed.** Two consequences.
**Whichever machine runs condition 1 runs every condition** — no table may mix them. And **the
final MacBook night is no longer a formality**: it was budgeted for latency and peak RAM with
portability as a bonus, and portability is now a live question that belongs in the limitations
section.

Do not read the accuracy column. MacBook 4/6, GPU 5/6, n=6, supports nothing.

### What it costs now

    condition 1 at 102      10.5 h   ->   ~20 min
    full 700 run              72 h   ->   ~2-3 h
    7B slice at 102        20-30 h   ->   under an hour

**Caveat, stated up front rather than after being caught by it:** these six average 2,713 prompt
tokens against the 700-wide mean of 4,426, so they are lighter than a representative draw. Expect
the real figures above the naive division. Same sample-versus-population trap as 5 and 6 August.

**Band B is open.** The 700 run, the 7B row, the end-to-end retrieval ablation and a real model
comparison are all affordable. **The one that matters is n=700**, which takes the accuracy margin
from about ±10 points to about ±4 and makes "we match condition 3" measurable instead of
unprovable. That was the largest threat to the contribution statement.

**The MacBook remains the device of record** for every latency, throughput and memory figure. The
GPU makes the experiments affordable, not the operating point cheap.

### Setup findings worth not rediscovering

**Setting `OLLAMA_HOST` is not enough; Ollama must be restarted, and the tray's Quit is
unreliable.** One line settles it:

    netstat -ano | findstr 11434
    127.0.0.1:11434  ->  not restarted, unreachable from the network
    0.0.0.0:11434    ->  correct

Reliable restart is `Get-Process ollama* | Stop-Process -Force`, then relaunch from the Start menu.

**The Windows network profile was `Public`** and had to be set to `Private` in an admin shell.
**Windows blocks inbound ICMP by default**, so `ping` from the Mac fails even when TCP works —
alarming and meaningless. The useful test is the reverse: **PC to Mac ping succeeded**, which ruled
out router client isolation, the one failure mode that would have needed a router change or
Ethernet.

**No code moved to the second machine.** `src/ollama_client.py` builds its URL from
`config.get("ollama_host", "localhost")`, so every existing config is untouched and every result
file now records which machine produced it. Harness picked up the new config automatically: 44/44.

## CONDITION 1 IS MEASURED. k IS FROZEN AT 10.

Both runs complete on the GPU, **102 ok / 0 failed** each. Full detail and the caveats in the build
log entry for 7–8 August, overnight. Figures in `paper_numbers.md` §2.3.

                              k=10        k=20
    strict accuracy          66.7%       62.7%
    FINDVER-compatible       66.7%       64.7%
    unparseable               0.0%        3.9%
    evidence_present         54.9%       65.7%
    prompt tokens, mean       3,651       6,843
    context overflow          0/102       0/102
    wall clock              11.2 min    14.9 min

**The finding: retrieval improved 10.8 points and accuracy did not follow.** `evidence_present`
gained on 11 claims and lost on 0, and strict accuracy fell 4 points. That is §3.4.4's distractor
hypothesis, measured.

**It is not significant and must not be written as "k=20 is worse."** Paired on the same claims:
44 disagreements, 18 to k=20, 22 to k=10. **Write "a 10.8-point recall gain produced no measurable
accuracy gain at 87% more prompt tokens."**

**k=10 wins on the tiebreakers, all of which point the same way.** Format compliance was
`anchored` on 102 of 102 at k=10 against 93 at k=20; unparseable is 0.0% against 3.9%, so the
strict and FINDVER-compatible scores **coincide exactly at 66.7%**; and 87% fewer prompt tokens is
87% less MacBook latency on the device of record.

**k=20 is kept as the retrieval-versus-accuracy ablation row**, not discarded.

**Also measured: verdicts are unstable.** Only **58 of 102** claims got the same label at both k
values. With the 5-of-6 machine divergence from earlier the same evening, the picture is
consistent — this model's verdicts move under conditions that should not change the answer.

**FDV-KNOW is the weak subset and it is a retrieval problem:** 26.5% all-gold recall against
numeric's 70.6%, and the lowest accuracy at both k values.

### What 66.7% means

    constant answer                              50.0%
    ours, 3B, single call, no pipeline           66.7%
    MACE's Mistral-7B, their full pipeline         64%
    MACE's Llama-8B, their full pipeline           68%
    FINDVER's best published RAG (claude-3.5)    75.0%

A good number. **And a high floor, which is the part that matters.** The contribution is condition
4 minus condition 1. If condition 3 lands at 75–80%, the pipeline has 8–13 points to climb, and a
delta that size sits at the edge of the ±10 margin at n=102. **A second independent reason the 700
run matters.**

### A published 3B baseline, scored both ways

From `outputs/` with no compute. `paper_numbers.md` §2.4.

                                            all 700   our 102
    Llama-3.2-3B, FINDVER-compatible          58.4%     62.7%
    Llama-3.2-3B, strict                      38.3%     36.3%
    stated no verdict at all                  26.6%     30.4%
    ends mid-sentence (1024-token cap)        17.9%     15.7%
    ours, both scorings                          —      66.7%

**The only defensible imputation figure is the no-verdict-word row**, ~13.3 points of their
published 58.4%, because a response containing neither "entail" nor "refut" cannot be extracted by
anything, `gpt-4o-mini` included. **An earlier framing attributing the whole 58.4→38.3 gap to
imputation was wrong and was withdrawn**: their labels are stored after the coin flip, so
`gpt-4o-mini`'s real failure rate is unmeasurable from these files.

**Do not write "our 3B beats their 3B."** Temperature 1.0, a 1024-token cap, and a weaker retriever
are all confounded in. **Write the evaluation-reliability claim**, which is the workshop's topic 05
and much harder to argue with.

**Band A now holds two results needing no further compute and no working pipeline:** retrieval
recall, and this. If everything downstream failed tomorrow there is still a paper.

---

## CONDITION 1 IS MEASURED AT n=700. The headline is 61.4%, not 66.7%.

`results/condition1_3b_full700/`, **700 ok, 0 failed, 79.4 minutes on the GPU.**

                            n=700     n=102
    strict accuracy         61.4%     66.7%
    FINDVER-compatible      62.1%     66.7%
    unparseable              1.1%      0.0%
    evidence_present        52.0%     54.9%
    prompt tokens, mean     3,731     3,651
    wall clock           79.4 min  11.2 min

    ie                      60.8%     64.7%
    knowledge               59.0%     58.8%
    numeric                 64.0%     76.5%

**The 5.3-point drop is sampling, and it was diagnosed, not assumed:**

    prompts identical across the two runs            102/102
    the 700 run scored, on those same 102 claims      67.6%
    the 102 run scored, on those same claims          66.7%
    the 700 run scored, on the other 598 claims       60.4%

The two runs agree to within one claim where they overlap. **The 102 sample was an easy draw**,
worst on numeric, which read 76.5% against a true 64.0%. Third appearance of the
sample-versus-population error, after 5 and 6 August, and the first on accuracy.

**EVERY n=102 ACCURACY NUMBER IN THIS PROJECT IS INFLATED BY AN UNKNOWN AMOUNT.** That includes
condition 2's 71.6% and 75.5%. Both 700 runs of condition 2 are in flight. **Do not quote the
edge-versus-cloud gap until both sides are at 700.**

The model-choice conclusions survive, because they rest on latency and format compliance rather
than on accuracy. Their accuracy columns do not.

### Condition 1 is NOT reproducible run to run, on the same machine

Same model, same GPU, same byte-identical prompts, same seed, temperature 0, run twice.
**Labels agreed on 91 of 102, 89.2%.** Retrieval, sampling, trimming and prompt building are
perfectly deterministic, so the divergence is entirely in generation. Likely floating-point
reduction order varying with GPU scheduling.

**This corrects what this file said yesterday.** After DeepSeek was found to ignore `seed` and
`temperature`, it recorded that "Ollama honours both settings" and that its instability was
cross-machine only. The cross-machine part was measured. The within-machine part was an
assumption and is now falsified.

Fourth measurement of verdict instability, and the cleanest, because nothing varied:

    the machine (Mac vs GPU)        5 of 6
    k, 10 vs 20                    58 of 102
    the model, three variants      79 of 102
    nothing at all, rerun          91 of 102

**A difference smaller than about one claim in ten, between two of our own runs, is noise.**

### Also withdrawn: "strict and FINDVER-compatible coincide"

§2.3 claimed the two scorings were identical at 66.7% because unparseable was 0.0%, and called it
the only figure in the project with that property. **At 700 unparseable is 1.1%, so they diverge**,
61.4% against 62.1%. The property was an artefact of the small sample.

## Where things stand, 9 August

Full narrative in the build log entry for 8–9 August. The short version.

### MODEL DECISION CLOSED, 9 Aug: `qwen2.5-coder:3b`. Three candidates, all tied.

`qwen3:4b-instruct-2507-q4_K_M` is the non-thinking Qwen3 build. Verified not thinking before the
run: capabilities are `['completion','tools']` with no `thinking`, and it answered "Is 2+2 equal
to 4?" in **12 tokens** where the thinking build spent 332.

                        coder:3b   qwen2.5:3b   qwen3:4b-instruct
    strict accuracy        66.7%       67.6%          67.6%
    unparseable             0.0%        2.0%           7.8%
      of which truncated       0           0             13
    output tokens, mean      413         497          1,281
    seconds per claim        6.6         7.9           23.0
    extraction anchored  102/102      92/102         93/102
    numeric                76.5%       79.4%          61.8%

**All three tie. Every pairwise McNemar p = 1.000.** The spread across a 3B code model, a 3B
general model and a 4B general model is 0.9 points.

**The 4B's 67.6% is a floor.** It truncated 13 times at `num_predict` 2000, **11 of them
numeric**, the same pattern as DeepSeek pro. Excluding truncations it scores 71.9%, and its
numeric goes 61.8% → 73.9%. A rerun at 4000 would likely reach ~72%.

**`coder:3b` is kept on cost, not accuracy.** 3.5x faster per claim on identical prompts, 3.1x
fewer output tokens. On the MacBook generation is CPU-bound so that gap widens, and condition 4
makes several calls per claim on a device where one call already takes 7 minutes. **A model
needing a larger generation budget is a worse edge model, not a better one.**

**The 45-minute rerun at `num_predict` 4000 is deliberately not scheduled**, because no plausible
result changes the choice. Revisit only if condition 4 turns out to be accuracy-bound rather than
latency-bound.

**Do not quote the 4B's FINDVER-compatible 75.5%** — eight coin flips, mostly lucky. **Do not
write "the 4B is no better than the 3B"** — the truncation makes that false. Write **"the 4B
matched the 3B on accuracy at 3.5x the generation cost."**

**Keep both other models installed on the PC until the paper is submitted.** GPU access is not
guaranteed to persist, and re-pulling requires the machine to be available.

### The professor's Coder objection, answered

`qwen2.5:3b` ran condition 1 on the same 102 claims, same seed, same GPU. **102 ok, 0 failed.**

                            coder:3b    qwen2.5:3b
    strict accuracy           66.7%       67.6%
    FINDVER-compatible        66.7%       68.6%
    unparseable                0.0%        2.0%
    evidence_present          54.9%       54.9%
    prompt tokens, mean        3,651       3,651
    wall clock              11.2 min    13.4 min
    extraction anchored     102/102      92/102

**The professor's Coder objection is answered, and the answer is "no measurable difference."**
67.6% against 66.7% is one claim in 102, and the paired split is 11 to the Coder model against 12
to the plain one. **Never write "the plain model is better."** Write *"holding size and
quantisation fixed and varying only code tuning changed accuracy by one claim in 102."*

**The Coder model is kept on the tiebreakers**, which all point one way: 102/102 anchored against
92/102, 0.0% unparseable against 2.0%, 17% faster, 20% fewer output tokens.

`evidence_present` and mean prompt tokens are **identical to the digit**, which is the sanity check
passing, since neither depends on the model.

### Verdict instability, now measured three independent ways

    across machines, 7 Aug      5 of 6 agree
    across k values, overnight  58 of 102 agree
    across model variants       79 of 102 agree

Same family, same size, same quantisation, identical prompts, and a fifth of the labels move.
This is a real finding and belongs in the paper.

### `qwen3:4b` IS REJECTED ON COST, and troubleshooting is optional

Aborted after 6 claims. **145 s per claim on the GPU** against 6.6 for the Coder model, which is
4.1 hours for 102, and roughly **90 minutes per claim on the MacBook** at the measured 36.8x
ratio. A model that cannot run on the device of record is not an edge model.

Also, `numeric-val-69` produced 18,282 characters of reasoning, hit the 8,000 cap with
`done_reason=length`, and wrote **zero characters** into `response`. Unparseable, on the numeric
subset, within the first four claims.

Records preserved at `results/condition1_qwen3_4b_k10_abandoned_8aug/`, which is the evidence for
the rejection row. **If it is revived, delete or rename that directory first** — `has_result`
resumes on file existence, so 6 records made at `num_predict` 8000 would silently mix with a run
at a different cap.

**Correction, and it inverts what this file said this morning: `think: false` does not disable
thinking.** Measured, same prompt, same eval_count of 332 either way. The field controls where
Ollama puts the reasoning, not whether the model produces it. `think: false` dumps it into
`response`, where the extractor reads it. **`think: true` is the correct setting**, because it
keeps `response` clean.

### DeepSeek works on a real claim, and condition 2 is running

`numeric-val-41`, `deepseek-v4-pro`: **correct verdict, anchored final sentence, first try.**

    prompt_tokens        3,004        qwen counted 3,622 for the same text
    completion_tokens    2,123
      reasoning_tokens   1,731        82% of output is thinking
    finish_reason        stop         3x headroom under the 8,000 cap

**Cost, from measured tokens: pro $0.32, flash $0.10, about $0.42 for both.** The test call cost
$0.003. Treat $0.42 as the high end, since numeric claims reason more than average. DeepSeek warns
of a significant price rise soon.

**`DeepSeek-V4-Flash-0731` is rejected by the API**, HTTP 400. Only `deepseek-v4-pro` and
`deepseek-v4-flash` are accepted, so **a snapshot cannot be pinned.** That closes the 7 August
open question with a no.

**`served_model` cannot detect a silent model roll for DeepSeek**, which was the reason it was
added tonight. The API echoes the alias, not the snapshot. **`system_fingerprint` is the field to
watch**, and it returned `fp_9954b31ca7_prod0820_fp8_kvcache_20260402`.

### MEASURED 9 Aug: DeepSeek is NOT reproducible. `seed` and `temperature` are ignored.

Three calls on `numeric-val-41`, `deepseek-v4-pro`, temperature 0, identical payloads.

    A  seed 0       1,235 completion tokens   1,021 reasoning
    B  seed 0       1,357                     1,081
    C  seed 12345   1,883                     1,690

    A == B ?   False, on both the answer text and the reasoning text

**Two identical requests with the same seed produced structurally different responses.**
`system_fingerprint` was identical on all three, so this is not a model roll. The settings are
accepted and ignored.

All three reached the same, correct, verdict. That is one claim sampled three times and says
nothing about verdict stability in general. **Do not report it as such.**

**Consequence: condition 2's accuracy is a single sample, not a reproducible measurement.**
Re-running the 102 claims would give a different number, and by an unknown amount. This is a
limitation to state plainly. It is also on topic for this workshop: the cloud half of an
edge-cloud system is not reproducible even when the edge half is.

**Condition 1 is unaffected.** Ollama honours both settings; its instability comes from
floating-point differences across machines, which is a separate and already-measured thing.

### API spend on the professor's key, and how to check it

`test_scripts/api_cost_tally.py` prints spend per experiment from our own recorded token counts,
plus DeepSeek's live balance. Run it before any message to him.

    condition2_deepseek_pro     102 claims   $0.295
    condition2_deepseek_flash   102 claims   $0.091
    ad-hoc probe calls, 7                    $0.011
    TOTAL so far                             $0.397   about 2.86 CNY

**Balance baseline, 9 August 2026: 142.32 CNY remaining**, topped up, no granted credit, about
$19.80. The starting balance is unknown, so the total above is our own estimate and cannot be
checked against theirs yet. **From now on the delta between two balance readings is the only
exact figure.** Their balance lags: it read 142.38 and then 142.32 twenty minutes later with
nothing running, so wait a few minutes after a run before recording.

The seven ad-hoc calls are hardcoded in the script with dates and reasons, because they went
through curl and Python rather than `run.py` and appear in no result file.

Projected: pro at 700 is about $2.02, flash at 700 about $0.62, taking the running total to
roughly $3.04, or 22 of the 142 CNY.

### CONDITION 2 IS MEASURED. Both runs 102 ok, 0 failed.

                        coder:3b     pro      flash
    strict accuracy        66.7%    71.6%     75.5%
    FINDVER-compatible     66.7%    75.5%     76.5%
    unparseable             0.0%     4.9%      2.0%
    evidence_present       54.9%    54.9%     54.9%
    predicted True        41/102   31/102    31/102    (gold 51/102)
    output tokens, mean       413    1,667     1,477
    wall clock           11.2 min  34.8 min  21.3 min
    cost                        —   $0.295    $0.091

    ie                     64.7%    76.5%     79.4%
    knowledge              58.8%    70.6%     64.7%
    numeric                76.5%    67.6%     82.4%

`evidence_present` identical across all three confirms all three saw identical prompts.
Fingerprints were constant across all 102 in each run, so no model roll mid-run.
**$0.386 for both, against $0.42 projected.**

**Pro's numeric score is a truncation artifact.** All five of its unparseables are
`done_reason=length` at the 8,000 cap, and **all five are numeric claims**: `numeric-val-11`,
`-111`, `-57`, `-69`, `-90`. **Excluding them pro scores 79.3% on numeric, not 67.6%.**
`numeric-val-69` is the same claim that truncated `qwen3:4b` tonight. **71.6% is a floor, not
pro's performance.**

**Do not write "flash beats pro."** They agree on 94 of 102; of the 8 disagreements flash is
right on 6 and pro on 2. That is a tie. **Write "flash matched pro at a third of the cost and
1.6x the speed."**

**Do not quote pro's FINDVER-compatible 75.5%.** The coin flip resolved 4 of its 5 unparseables in
its favour. Luck from the seed. **Use strict, 71.6%.**

**The edge model is not strictly worse, and this is the premise routing rests on.** Against pro
they agree on 67 of 102; pro is right on 20 the 3B misses, but **the 3B is right on 15 that pro
misses**, spread over all three subsets (7 numeric, 5 ie, 3 knowledge).

**All three models are biased toward refuted.** Gold is 51/102 entailed; the edge model said
entailed 41 times, both cloud models 31. Belongs in the error analysis.

**The gap condition 4 must close is now measured: 4.9 points to pro, 8.8 to flash.**

### New environment fact: Python HTTPS needed a certificate bundle

Homebrew Python 3.14 looks for `/usr/local/etc/openssl@3/cert.pem`, which does not exist here.
`.env` now carries, beside the key:

    export SSL_CERT_FILE=/usr/local/etc/ca-certificates/cert.pem

Every Ollama call is plain HTTP to a LAN address and the 7 August smoke test used `curl`, so this
had never fired before. **A `.env` file does nothing until `source .env` is run**, and it does not
carry between terminal windows.

### Built tonight

- `src/deepseek_client.py`, an adapter returning DeepSeek's response under Ollama's key names, so
  `run_loop.py` and everything downstream is untouched.
- `src/ollama_client.py`, the `think` field, passed only when the key exists so all six older
  configs send byte-identical requests.
- `Record` gained `thinking`, `served_model`, `system_fingerprint`. One field serves both
  providers: Ollama's `thinking` and DeepSeek's `reasoning_content` are the same thing.
- `run.py` gained a `CLIENTS` dict, selected by `config.get("client", "ollama")`.
  **A correction: this file previously said `run.py` needed no change. It did.** `run_loop.py`
  takes the model call as a parameter, but `run.py` was passing `call_ollama` hardcoded.
- `test_harness.py` moved 18 → 21 `Record` fields. **50/50 passing**, up from 44.
- Configs: `condition1_qwen25_3b_k10`, `condition1_qwen3_4b_k10`, `condition2_deepseek_pro`,
  `condition2_deepseek_flash`.

### The PC runs Ollama 0.32.6, the Mac 0.12.3

Never noted before. A second reason, independent of the floating-point divergence measured on
7 August, why a results table must never mix the two machines.

---

## Where things stand, 10 August

## CONDITION 2 IS MEASURED AT n=700. The gap is 15.9 points, and it is significant.

Both runs `max_tokens` 16,000, temperature 0, seed 0, BM25 k=10, same 700 claims as condition 1.
**700 ok, 0 failed on each.**

                            coder:3b    v4-pro   v4-flash
    strict accuracy            61.4%     77.3%      77.0%
    FINDVER-compatible         62.1%     77.6%      77.0%
    unparseable                 1.1%      0.3%       0.0%
    evidence_present           52.0%     52.0%      52.0%
    predicted True           324/700   213/700    217/700   (gold 350/700)
    output tokens, mean          416     1,446      1,463
    wall clock              79.4 min  270.4 min  147.7 min
    cost                           —    $1.911     $0.626

    ie                         60.8%     80.8%      80.4%
    knowledge                  59.0%     70.5%      70.5%
    numeric                    64.0%     79.2%      78.8%

**This is the first significant accuracy comparison in the project.** Edge versus cloud is
p < 0.001 at n=700, against p = 0.500 at n=102.

### The n=102 gap was wrong by a factor of three, and wrong in both directions at once

The old figure was 4.9 points to pro. The real figure is 15.9. The 3B side was inflated by an easy
sample, 66.7% against 61.4%, and the pro side was depressed by truncation, 71.6% against 77.3%.
Two independent biases pointing at each other nearly erased a real gap. **Fourth appearance of the
sample-versus-population error.** The `max_tokens` 16,000 re-run owed on 9 August is delivered:
pro's unparseable rate fell from 4.9% to 0.3%.

### DECIDED 10 Aug: the cloud tier is `deepseek-v4-flash`

77.3% against 77.0%, agreeing on 660 of 700, **p = 0.875**. At n=102 the tie meant "too small to
separate them." At n=700 it is a measurement. **Flash is one third the price and 1.8x the speed for
the same accuracy.** Pro stays as a reported baseline and nothing more.

### The whole gap is on refuted claims. On entailed claims the 3B ties a frontier model.

                        coder:3b    v4-pro   v4-flash
    correct on entailed      204       203        203     (of 350)
    correct on refuted       226       338        336     (of 350)
    recall on entailed      58.3%     58.0%      58.0%
    recall on refuted       64.6%     96.6%      96.0%

Cloud is not better at verifying claims. It is better at catching false ones. **Every model, local
and cloud, misses about 42% of entailed claims, and no tier in the build order addresses that.**
It is now the largest single error pool in the project.

### The 3B does not use the retrieved evidence

                        with evidence   without    delta
    coder:3b            61.3% 223/364  61.6% 207/336   -0.3
    v4-pro              81.0% 295/364  73.2% 246/336   +7.8
    v4-flash            82.1% 299/364  71.4% 240/336  +10.7

**Observational, not causal.** Claims where BM25 succeeds may be easier claims, so 8 to 11 points
is an upper bound on what better retrieval buys the cloud tier, not an estimate. The 3B's −0.3 does
not have that problem, since no confounder rescues a null result.

**Retrieval work is now justified by measurement rather than by the plan, but only for the cloud
tier.** Do not expect a retrieval improvement to move the edge-only baseline.

### Withdrawn: "all three models are biased toward refuted"

Written on 9 August from n=102. At n=700 the cloud models predict entailed 30.4% and 31.0% against
a true 50%, a strong skew. The 3B is at 46.3%, a slight lean the other way from its 120 false
positives. **The 3B has no directional bias worth fixing by prompting. It has weak discrimination**,
58.3% and 64.6% on the two classes. Do not group all three under one sentence.

### Survives: the edge model is not strictly worse

**The 3B is right on 80 claims pro gets wrong**, 11.4% of the split. Routing still has something to
route, which is the premise §5.3 rests on.

### The evidence finding hits §5.2, not the pipeline as a whole

§4.4 and §4.7 put prompt ingestion and verdict generation on **cloud**. The edge 3B does claim
decomposition, `.loc` lookups, glossary spotting, and the first-pass verifier screen. Condition 1
is the edge-only ablation, not the system, so evidence-blindness there is a property of the floor.

**The one row it damages is §5.2's "verifier, judgment checks: edge first, escalate to cloud."**
That job needs the 3B to read evidence and judge whether a step follows, and the 3B cannot. §5.2
already flags MACE's cross-model false-refutation risk on the same row. **Take this to the
professor with §13 open question 1.**

### CLARIFIED 10 Aug: what "a fraction of the cost" means, and what the goal actually is

The phrase in §5.3 was never pinned to an axis, and the n=700 numbers made that a problem. **The
whole cloud-only baseline over 700 claims cost $0.626.** No paper is carried by saving two dollars.
Full statement now in architecture plan **§5.3.1** and paper numbers **§3.5**.

**Two comparisons. One axis is solid, the other is a hole.**

- **Ours vs MACE. SOLID.** MACE self-hosts every role and its smallest configuration needs **27B
  resident**, which this machine cannot hold. Ours is **3B plus an API**. Resident parameters and
  laptop feasibility are both legitimate here, precisely because MACE uses no cloud at all.
- **Condition 4 vs condition 3. A HOLE, found 10 Aug.** Memory does not merely fail to separate
  them, **it runs the wrong way. Condition 3 keeps ZERO parameters on the device**, since the cloud
  plays every role and the laptop only orchestrates. Condition 4 must hold 3B resident. Both run on
  a laptop. **Condition 3 wins on memory and ties on portability.** What is left is cloud calls and
  tokens per claim, which is under $3 of money and some data sent to a third party. **This is the
  weakest point in the contribution statement. Take it to the professor, do not write around it.**

**Fallback if that stays empty.** Report **beating condition 2 at 77.0% as a headline result in its
own right**, then present the rest as a study of where the line between the two models can be
drawn. §9.2's "beating condition 2 is a bonus" governs what leads the abstract. **It is not a
reason to omit the result**, and these docs previously read it that way.

**The goal, stated so it stops drifting:**

    assign every role to the cheapest component that can RELIABLY do it
    no model  <  edge 3B  <  cloud

**It is not "maximise 3B roles."** The biggest savings in §4.4 are the no-model rows: BM25, top-k
ranking, table parsing, running the generated code, re-checking arithmetic, retry control flow.
A pipeline that pushed work onto the 3B instead of onto plain Python would be worse on every axis.
**"Reliably" is now load-bearing**, because the 3B cannot do evidence-based judgment.

**Wall clock cannot be the headline, because it reverses with the machine.** Per claim at n=700:
3B on the GPU box **6.8 s**, flash **12.7 s**, pro **23.2 s**, and the same 3B on the MacBook about
**420 s**. The local model is the fastest of the three on the GPU and 33x slower than flash on the
laptop. Name the machine or do not make the claim.

**The deliverable is the routing curve, not a single ratio.** Condition 1 is never-escalate,
condition 3 is always-escalate, Tier 5 sweeps between. **The knee of that curve is the result.**

## THE 7B IS MEASURED AT n=700: 72.4%. The strengths are opposite to cloud.

`condition1_7b_full700`, **700 ok, 0 failed, 160.1 min, 13.7 s per claim**, 2.0x the 3B.

                        3B       7B      pro    flash
    strict           61.4%    72.4%    77.3%    77.0%
    predicted True 324/700  353/700  213/700  217/700   (gold 350)
    s per claim         6.8     13.7     23.2     12.7

    ie               60.8%    76.4%    80.8%    80.4%
    knowledge        59.0%    73.0%    70.5%    70.5%
    numeric          64.0%    68.0%    79.2%    78.8%

    correct entailed    204      257      203      203   (of 350)
    correct refuted     226      250      338      336

**The 7B closes 11.0 of the 15.9 points**, and is now only just behind cloud, p = 0.027 vs pro.

**It beats both frontier cloud models on entailed claims by 54 claims**, 73.4% against 58.0%, and
loses on refuted. **The local and cloud models fail on disjoint parts of the task.** The 7B is also
the best calibrated of the four.

**WITHDRAWN, written earlier today:** "every model misses about 42% of entailed claims." True of
the 3B and both cloud models, **false of the 7B**, which misses 26.6%. Caught before the email went.

**The 7B beats cloud on FDV-KNOW and its whole remaining deficit is FDV-MATH**, 68.0 against 79.2.
**Arithmetic is what is left, which is what Tier 1's code execution builds to fix.** Strongest
argument the project has produced for the pipeline being worth building.

**The 7B also uses the evidence and the 3B does not:** 75.3% with against 69.3% without, a gain of
6.0 points, where the 3B is −0.3. **Evidence use appears somewhere between 3B and 7B.**

**The speed argument dies at 7B.** 13.7 s per claim against flash's 12.7. Only the 3B at 6.8 s is
faster than the cloud, so any latency claim is a 3B claim.

### ROUTING: the oracle is big, every rule we can implement is a tie

Full version in paper numbers **§2.6.4**. You cannot route on entailed versus refuted, because you
do not know which it is. Measured instead of argued.

    per-claim oracle, whichever model is right      90.9%
    route by subset, FDV-KNOW local                 78.0%   <- test-set selection, not a result
    pro alone                                       77.3%
    trust pro's entailed verdict, else 7B           76.3%
    trust the 7B's refuted verdict, else pro        73.9%

**Disagreement carries no information.** Where the 7B says entailed and pro says refuted, 179
claims, **49% are truly entailed. A coin flip.**

**One strong asymmetry, unanticipated:** pro is **95.3% right when it says entailed** and only
69.7% when it says refuted. **The pipeline should spend its effort on claims the cloud calls
refuted.**

**THE REFRAMING, and it is the usable finding.** The two models **agree on 468 claims and are 88.0%
accurate there**, and **disagree on 232, where pro gets 55.6%**. **Condition 4's job is not routing.
It is beating 55.6% on those 232 claims.** A fifth of the benchmark, a concrete target, and a
better statement of the job than "match condition 3."

### The bar condition 4 has to clear, and the API spend so far

Full version in paper numbers **§2.6.2**. Beating 77.0% **is** worth reporting. Two different bars,
not the same claim:

    our condition 2, flash, strict, n=700     77.0%   internal, every variable controlled
    our condition 2, pro,   strict, n=700     77.3%   internal
    best published 2024, Claude RAG           75.0%   external, four variables uncontrolled
    our condition 1, coder:3b, n=700          61.4%   the floor
    condition 3                            not run    THE ONE THAT MATTERS

Three conditions on any such sentence. **Quote a McNemar p-value, not the accuracy column**, since
one claim in ten moves as noise. **Strict against our own runs, FINDVER-compatible against
published ones**, never mixed. And keep §9.2's framing: beating condition 2 is a bonus, matching
condition 3 at a fraction of the cost is the paper.

**Already supportable at no further cost:** our 77.0% cloud baseline sits above the best published
2024 RAG figure of 75.0%. **Write it as a tie**, given the noise floor, and note it is a 2026 model
against a 2024 table.

**[TALLIED 10 Aug] The USD tally is attribution, not billing. Do not quote it as spend.** The
account is in CNY and `api_cost_tally.py`'s own docstring says DeepSeek's CNY list is not the USD
list at spot rate. **Proportions inside the table hold, absolute dollars do not.**

    exact, from balance readings
      9 Aug, after the two n=102 runs        142.38 CNY
      10 Aug, after both n=700 runs          115.42 CNY
      11 Aug, before the v2 run              115.14 CNY   (the 0.28 is settlement lag)
      11 Aug, after flash v2 at n=700        110.24 CNY   delta 4.90, exact

    TOTAL SPEND, updated 11 Aug after the v2 run:
      exact, 9 Aug onward                     32.14 CNY   ~4.5 USD
      estimated, before 9 Aug                 ~4    CNY   ~0.6 USD   NOT RECOVERABLE
      estimated total                        ~36    CNY   ~5.0 USD
      remaining, exact                       110.24 CNY   ~15.3 USD

    CORRECTED: the USD-to-CNY discrepancy is MODEL-SPECIFIC, not systematic.
      flash   6.94 CNY per attributed USD    ~= the 7.2 nominal spot rate
      pro    ~11.8 CNY per attributed USD    ~1.65x its USD list
    Pro is roughly 5x flash per run in real billing, not the 3x the USD table
    implies. A fourth argument for flash as the cloud tier.

    The starting balance was never recorded, so everything before 9 August is
    attribution and can never be measured. Label it as an estimate wherever it appears.
      the two n=700 condition 2 runs          26.96 CNY   <- the only exact figure
      remaining on the professor's key       115.42 CNY

**Our USD attribution predicted 18.27 CNY for those two runs. Actual is 26.96, or 1.48x. Cause
unverified**: the CNY list not tracking the USD list, stale rates, or cache-miss input pricing.

**Pro is 75% of the attributed total and the single n=700 pro run is 65%.** A third argument for
flash, beside the accuracy tie and the wall clock. **Rough planning figure:** condition 3 at four
cloud calls per claim is about 27 CNY on flash and about 81 CNY on pro, against 115.42 remaining.

**Owed, cheap:** record a balance reading before and after every cloud run; add the 115.42 reading
to `api_cost_tally.py:147`; check DeepSeek's current CNY list; ask the professor for read access to
the account usage page, which would replace all three.

## What to do on 10 August, in order

1. ~~**Read both condition 2 results at 700.**~~ **DONE 10 Aug.** See above.
2. ~~**Back up `results/`.**~~ **DONE 10 Aug**, `~/findver_results_20260810.tgz`, 14 MB.
3. ~~**RUN `qwen2.5-coder:7b` AT 700.**~~ **DONE 10 Aug. 72.4%, 700 ok, 160.1 min.** No pull was
   needed. See the 7B section above. **It answers the objection the professor was most likely to
   open with, and the answer is more interesting than expected:** a bigger local model closes two
   thirds of the gap, beats cloud on entailed claims and on FDV-KNOW, and its whole remaining
   deficit is arithmetic, which is what Tier 1 builds to fix.
4. ~~**Email the professor.**~~ **DONE 10 Aug**, plus a same-day follow-up carrying the 7B result
   and correcting one sentence in the first email. The withdrawn sentence was "every model misses
   about 42 percent of entailed claims," which the 7B falsified hours after it was sent.
5. ~~**Create the Overleaf project and share it**~~ **DONE 10 Aug**, NeurIPS 2026 template,
   `\usepackage[dblblindworkshop]{neurips_2026}` (option 6, workshop with double-blind review, not
   the default `main`). Shared with him and the link went out in the first email. **Two things
   still owed inside it:** `\@workshoptitle` is unset, and `checklist.tex` is the main-conference
   questionnaire, which the workshop probably does not require.
6. ~~**Update the docs with condition 2 at 700.**~~ **DONE 10 Aug**, this section plus
   `build_log.md` and `paper_numbers.md` §2.6.1, §2.7, §3.4.
7. Optional if the GPU is idle later: `qwen2.5:3b` at 700, about 90 minutes, to settle the Coder
   objection at full scale rather than on the n=102 sample now known to be easy.

### Still open, carried

- `evidence_asserter.py:83`, the `check_overflow` docstring, still says `num_ctx` 16384.
- ~~A DHCP reservation for the brother's PC would stop the IP moving.~~ **DECLINED 10 Aug.** If the
  IP moves, edit `ollama_host` in the affected configs. The address held all day on 10 August. The
  risk accepted is losing one overnight run to a silent failure at claim 1.
- `run.py` prints the `client` line after the blank line that ends the banner. Cosmetic.
- ~~**No tier addresses the 42% of entailed claims every model misses.**~~ **ANSWERED 11 Aug,
  night.** The mechanism is now measured: models declare information absent, with the evidence
  present, and refute on that basis. It is universal across all four models and **routing cannot
  repair it**, because the escalation target shares the bias. `baseline_v2` is the only lever
  identified that touches it. See "THE KNOWLEDGE GAP HAS A MECHANISM" above and
  `paper_numbers.md` §2.11.
- **Cloud spend is only exactly knowable from balance deltas.** Record a reading before and after
  every cloud run. Add the 10 Aug reading of 115.42 CNY to `api_cost_tally.py:147`. Check
  DeepSeek's current CNY price list. Ask the professor for read access to the account usage page,
  which would replace all three.

## Where things stand, 11 August

Full narrative in the build log entry for 11 August. Two oracle retrievers built, one run
finished, one running. **No pipeline module was built today**, which is the thing that matters
against the 23 August freeze.

### THE CAUSAL RETRIEVAL QUESTION IS ANSWERED, AND THE ANSWER IS PER SUBSET

`paper_numbers.md` §5 has carried "better retrieval improves accuracy" as unestablished since the
project began. Two oracle runs test it directly: put the gold evidence in the prompt instead of
BM25's top ten.

`results/gold_alone_3b_full700/`, **700 ok, 0 failed, 61.8 minutes.**

                            condition 1   gold-alone
    strict accuracy             61.4%        65.0%
    FINDVER-compatible          62.1%        65.3%
    unparseable                  1.1%         0.6%
    evidence_present            52.0%       100.0%
    prompt tokens, mean          3,731        1,124
    wall clock                79.4 min     61.8 min

**Overall it is a tie: +3.6 points, p = 0.116.** Do not write it as an improvement.

**The average hides the result. Per subset, paired on the same claims:**

    subset        n   cond1 only   gold only    net       p
    ie          250           26          52    +26   0.004
    knowledge   200           35          39     +4   0.728
    numeric     250           43          38     -5   0.657
    ALL         700          104         129    +25   0.116

**FDV-IE gains 10.4 points, 60.8% to 71.2%, at p = 0.004**, which survives correcting for three
subset tests. Knowledge and numeric move nothing and cancel it out.

### Two documented claims are corrected by this

**"The 3B cannot use evidence" is too strong and must be requalified.** This file and architecture
plan §869 both assert it flatly from the 10 August observational -0.3. Given perfect evidence with
distractors removed, the 3B uses it on extraction claims, significantly. **What survives:** no
benefit on average, none at all on knowledge or numeric. **What is withdrawn:** the unqualified
sentence, and with it the unqualified version of §5.2's "the 3B cannot do evidence-based
judgment."

**"FDV-KNOW is a retrieval problem" is falsified.** The 7-8 August entry inferred it from 26.5%
all-gold recall. Perfect retrieval moved knowledge 2.0 points, p = 0.728. Low recall did not mean
retrieval was the bottleneck.

### Numeric got worse with perfect evidence. Second independent line for Tier 1.

64.0% to 62.0%, not significant. Every gold number present, no distractors, no improvement. This
agrees with the 10 August 7B result, where the entire remaining deficit was FDV-MATH.
**Numeric is limited by arithmetic, not retrieval**, now measured two independent ways. Strongest
case the project has for code execution being the right next module.

### The entailed deficit survives perfect evidence

                        condition 1   gold-alone
    ALL entailed      204/350 58.3%  214/350 61.1%
    ALL refuted       226/350 64.6%  241/350 68.9%
    know entailed     51/100 51.0%   51/100 51.0%

**`knowledge` entailed is 51/100 in both runs, exactly chance, with perfect evidence in hand.**
The 10 August entry called the entailed miss rate the largest error pool in the project. Retrieval
does not address it.

### The knowledge gap: the honest position

**Unknown, and today's run does not say. It only rules retrieval out.**

**The cheapest thing that would answer it: read the 49 knowledge claims that are true, had every
gold element in the prompt, and were still called refuted.** Retrieval is excluded by
construction, so the failure is visible in the response text. No compute, no quota. The plan
already requires >=25 hand-labelled failures per iteration. **Until they are read, "glossary" and
"the model is too small" are equally unfalsified.**

Candidates, with what the data says. **Glossary:** alive, since 51% on entailed with a refuted
lean fits a model that cannot see implication without an accounting concept; against it, §7.4
rates it the smallest expected gain of any tier. **Model capability:** strongest lever measured,
the 7B scores 73.0% against the 3B's 59.0% and beats both cloud models here. **Escalate to
cloud:** most on-thesis, cloud is 70.5%, but that is condition 4 work rather than a fix.

**Headroom is bounded.** The best published 2024 model gets 75.5% on FDV-KNOW and everything above
3B clusters at 70 to 75. Realistic target for a 3B is roughly 59 to 70, not 59 to 90.

**Do not start a knowledge workstream now.** Tier 3, lowest priority, and Tier 1 has two
independent lines pointing at it with 12 days to the freeze.

### Gold-padded is running, and what it tests was written down first

Gold-alone changed two things: gold present, and distractors gone. Padded changes only the first,
holding chunk count and prompt size at condition 1's values.

- If padded reproduces the ie gain, **gold presence** matters and better retrieval is worth
  building.
- If padded shows nothing, **distractor load** matters. The 3B can use evidence but cannot find it
  among ten chunks, and §5.2's verifier row is salvageable by feeding it fewer chunks.

**One inconsistency, accepted.** Gold-alone returns document order, padded returns score order, so
`gold-alone - padded` moves ordering as well as distractor load. The `padded - condition 1`
subtraction is unaffected. Re-running gold-alone in score order is 35 minutes if that becomes
load-bearing.

### NEW DATA TRAP 8: `relevant_context` is not a set

Five of 700 claims repeat an index: `ie-val-193` (7, 8, 7), `numeric-val-36` (24, 24),
`numeric-val-41` (30, 30), `numeric-val-139` (61, 61), `knowledge-val-20`
(190, 188, 183, 192, 188). A retriever using `sorted(claim.relevant_context)` puts the same
element in the prompt twice. Added to `CLAUDE.md`.

**Recall figures are unaffected**, because `measure_recall.py:68` already stores gold as a
`frozenset`. The distinct gold count is **1,959, not 1,964**, mean 2.80 rather than 2.81.

**Repaired via resume**, by deleting the five affected result files and re-running: 5 recomputed,
695 skipped, about fifteen seconds. The 8 August `qwen3:4b` trap used correctly for once.

### MEASURED: the evidence asserter's false-positive rate on real retrieval is 1.6%

347 claims where BM25 genuinely missed gold, but only 336 flagged `evidence_present: False`. On 11
claims the asserter said the evidence arrived when the gold element was never retrieved.

**The 2 August entry asked for this re-check**, having only the 0.7% adversarial-control figure.
The real-retriever answer is **1.6%**.

**Zero false negatives**, 353/353. The asymmetry the project relies on, that `False` is
trustworthy, holds on real data.

**Free precision upgrade:** §2.6.1's with-evidence split used this flag, so 11 claims are in the
wrong bucket. That split can now be computed exactly from gold indices by set comparison.

### Built today

- `src/gold_retriever.py`, `src/gold_padded_retriever.py`, two entries in `run.py`'s `RETRIEVERS`,
  and configs `gold_alone_3b_full700.json` and `gold_padded_3b_full700.json`.
- Neither needed an interface change: `retrieve(claim, report, k)` already receives the claim.
- **Five bugs caught in review before anything ran**, including a list alias that would have
  written retrieved elements into the claim's answer key, and a duplicate guard that could never
  fire because it compared a tuple to an integer. Full detail in the build log.

### Tier 1 environment, checked not started

**`pandas`, `lxml`, `bs4` and `html5lib` are all missing.** Only numpy is installed. Install with
`pip3 install --break-system-packages pandas lxml`, **on the Mac only**, since `run.py` runs here
and only the model call crosses the network.

**Hint on §7.1 step 1.** First report: 283 context elements, 48 flagged `type: "table"`,
`html_tables` holds exactly 48. If that count match holds across all 255 reports the mapping is
ordinal and step 1 disappears. **One report proves nothing.** Measuring all 255 is the first Tier 1
task and needs no model.

### What to do next, in order

1. **Read gold-padded when it finishes**, against the prediction above.
2. **Install pandas and lxml.**
3. **Measure the `html_tables` to `context` mapping across all 255 reports.** No model calls.
4. **Then Tier 1 proper**, code execution and tables as DataFrames.
5. Optional, GPU: k=20 at n=700, about 2.5 hours, to move the k ablation off the known-easy n=102.
6. Deferred, no compute: read the 49 knowledge failures.

### Still open, carried forward

- `evidence_asserter.py:83`, the `check_overflow` docstring, still says `num_ctx` 16384.
- Per-subset McNemar and the entailed/refuted split were computed by throwaway scripts.
  `paper_numbers.md` rule 1 says a number enters the paper only when a committed script
  reproduces it. **These need folding into `analyse_condition1.py` before they are cited.**
- The 42% entailed miss rate still has no tier addressing it, and retrieval is now ruled out.

---

### GOLD-PADDED IS MEASURED, n=700. Distractors are the bigger half.

`results/gold_padded_3b_full700/`, **700 ok, 0 failed, 80.2 minutes.**

                            condition 1   gold-padded   gold-alone
    strict accuracy             61.4%        63.0%        65.0%
    evidence_present            52.0%       100.0%       100.0%
    prompt tokens, mean          3,731        3,711        1,124
    ie                          60.8%        64.4%        71.2%
    knowledge                   59.0%        62.0%        61.0%
    numeric                     64.0%        62.4%        62.0%

**All three pairwise comparisons are ties**: cond1 vs padded p = 0.410, padded vs alone p = 0.370,
cond1 vs alone p = 0.116. **The design held** — padded's prompt is 3,711 tokens against 3,731, so
only gold presence moved.

**The decomposition, on ie:**

    condition 1                     60.8%
      + gold present (padded)       64.4%      +3.6   p = 0.253
      + distractors gone (alone)    71.2%      +6.8   p = 0.057
      total                                   +10.4   p = 0.004

**Removing distractors is about two thirds of the gain.** The prediction recorded before the run
was binary — padded reproduces the gain, or shows nothing — and **neither branch was right.** Both
mechanisms are real and distractors are the larger one.

**What this does to the retrieval story.** Perfect recall is worth +3.6 on ie and nothing
elsewhere, not significant. Since perfect recall is the ceiling for any retriever, **a real
retrieval improvement buys less than that end to end.** The standalone recall result, 74.60%
against the published 68.01%, is unaffected and still carries its own section of the paper.

**NEW DIRECTION, untested: fewer chunks.** k was frozen at 10 and tested upward to 20, which was
worse. **It has never been tested downward.** Gold-alone's advantage came with 2.8 chunks. k=5 or
k=3 trades recall for a cleaner prompt and nobody has measured that trade, because the k sweep only
measured recall. **Spend the k-ablation GPU slot on k=5, not on k=20 at 700.**

### TIER 1 REDIRECTED: build the sandbox, drop tables-as-DataFrames

**Architecture plan §7.1 is contradicted by measurement and has been marked.** It says
`read_html` gives "structure preserved, no custom parser." Across 1,079 real data tables:

    columns are integers only           100.0%     header detection never works
    merged-cell duplication              84.8%
    null fraction, whole frame            0.56
    columns entirely null                 0.20     layout spacers
    column inflation vs the text copy     1.95x    median 1.83x

**Not one table in 1,079 came back with usable column names**, so `.loc["Net income", "2024"]` is
impossible everywhere without a custom post-processor. pandas returns **the numbers without the
structure.**

Also measured: **`read_html` raised on 0 of 1,228 tables**, so a try/except fallback fires on
nothing. And only **64.6% of real data tables round-trip their numbers perfectly**, so a third lose
data silently in a frame that looks clean.

**The decision.** The failure Tier 1 exists to fix is arithmetic, not lookup: the trial run's
`$15,800,000 + $0.015 million = $15,800,015`. Python cannot make that error, on numbers from the
text just as well as from a DataFrame. A structural repair cannot be validated, because the text
copy is an answer key for *which numbers* should be present but not for *what shape* the table
should be. And it is the 11th with a freeze on the 23rd.

**`src/table_parser.py` is deleted**, committed at `c4c0d7c` and recoverable.

**Caveat, because the decision rests on it:** reason 2 is an argument, not a measurement.
Post-processing was never tried. About an hour to find out, if the sandbox lands early.

### The mapping question is closed, and the scale rule is decided

**Ordinal.** Table count equals `len(html_tables)` on 255/255 reports, and numeric content aligns
at 0.946 against 0.195 for the neighbouring table. §7.1 step 1 is one line.

**Scale is metadata, never multiplication.** Across 9,432 real data tables the phrase is findable
44.6% of the time, almost always inside the table itself. **19.5% of those carry a carve-out**,
"in thousands, except per share data", so multiplying through would corrupt per-share rows on 821
tables. The scale is stated beside the table in the prompt and bound as a variable in the sandbox.
**"Not found" stays unknown and never becomes `scale = 1`.**

**Addressable population for any table work:** 48.1% of claims have a real data table in their gold
evidence, 29.1% have one that round-trips perfectly, 37.2% on the numeric subset.

### Two measurement bugs of my own, both caught before they reached a conclusion

The parse-fidelity figure first read 58.7% because pandas turns `45300` into `45300.0` and the
comparison was on strings. Comparing as numbers gives 64.6%. And an alternative scale-phrase check
for `(000)` reported 32.7% while actually matching the digits inside any number like `1,000`.
Discarded.

### ~~What to do next, revised~~ — SUPERSEDED the same evening, see the section below

Item 4 was "build the code sandbox." **That is withdrawn.** A free baseline measured an hour
later showed prose arithmetic already produces the correct value on 64.4% of numeric claims, the
magnitude trap fires on 3.2%, and computed-value correctness barely predicts verdict correctness.
The current plan is in **"THE PLAN FROM 11 AUGUST, EVENING"** below.


---

## THE PLAN FROM 11 AUGUST, EVENING — what actually raises condition 4

Written after a day in which two proposals, table parsing and the code sandbox, were proposed for
building and then killed by measurement. **The order was wrong both times: build first, measure
second.** Everything below was measured first, from the six n=700 runs already on disk. No new run
produced any number in this section.

### 1. THE PROMPT CARRIES A REFUTED BIAS, AND IT COSTS 21% OF THE BENCHMARK

`prompts/baseline_v1.txt` step 4 tells the model to answer refuted if the claim *"contradicts the
document **or partially contradicts** the document."* Under RAG the model sees ten chunks, so
partial information is the normal case, and that clause turns "I only see part of it" into
"refuted."

                predicts entailed   acc entailed   acc refuted
    gold                     50%
    flash                    31%          58.0%         96.0%
    pro                      30%          58.0%         96.6%
    7B                       50%          73.4%         71.4%
    3B                       46%          58.3%         64.6%

**147 claims, 21% of the benchmark, are true claims flash calls refuted** — knowledge 59, ie 46,
numeric 42. This is the largest single error pool in the project, and the 10 August entry already
noted no tier addresses it. **The cause was found in our own prompt file, not in the models.**

**It is inherited, not our bug.** The phrase appears in FINDVER's own shipped output files, so all
16 published baselines carry it. **That makes the fix a paper finding as well as an accuracy
lever:** the benchmark's standard prompt induces a refuted bias that costs frontier models a fifth
of the benchmark.

**Action: `prompts/baseline_v2.txt`**, one intervention — drop the "partially contradicts" clause,
state the criterion symmetrically, and add that incomplete evidence is not by itself a
contradiction. **The `{entailment_label}` brace bug is deliberately NOT fixed in v2**, so the run
that decides this moves one variable. It goes in v3.

**Test order: flash first** (~2.5 h, ~10 CNY of the 115.42 remaining), then the 3B (~80 min GPU).

**Success criteria, fixed in advance:** predicted-entailed moving from 31% toward 50%, accuracy on
entailed rising from 58.0%, refuted accuracy not falling below ~85%, and a McNemar p against the v1
run. **DeepSeek ignores `seed` and `temperature`**, so the entailed-rate shift is the trustworthy
signal — a 20-point swing cannot be resampling noise.

### 2. CONDITION 4 ALREADY EXISTS IN THE DATA, AND IT MATCHES CONDITION 2

Run the 3B and the 7B on every claim. Agree, keep it. Differ, escalate to flash.

    routed        536/700 = 76.6%     cloud on 251/700 = 36% of claims
    flash alone   539/700 = 77.0%     cloud on 100%
    McNemar p = 0.858  ->  a tie

    subset       routed   flash
    ie            82.4%   80.4%
    knowledge     73.0%   70.5%
    numeric       73.6%   78.8%   <- the only loss

**The 3B is not answering. It is a second opinion that says whether to trust the 7B.** When they
agree the 7B is 76.8% right; when they differ, 64.5%.

**No new run is needed to report this.** It requires only that the analysis be folded into a
committed script.

**Caveats for the paper.** It holds 3B and 7B resident, about 7.5 GB, and runs both on every claim,
20.5 s local per claim on the GPU box. **The saving is cloud calls, not local compute.**

### 3. ALWAYS ESCALATE THE NUMERIC SUBSET

The one subset the rule loses on. Three independent measurements say numeric is arithmetic-bound
and local models cannot fix it: the 7B's entire remaining deficit is FDV-MATH; perfect evidence
made 3B numeric *worse*, 64.0% to 62.0%; and prose arithmetic already gets the value right 64.4% of
the time. **A principled prior backed by three measurements, not a threshold tuned on the test
set.**

### 4. SELF-CONSISTENCY AS THE GATE — one run needed

    three 3B runs unanimous   n=401   3B accuracy 72.3%
    three 3B runs split       n=299   3B accuracy 46.8%   <- worse than chance

Local self-disagreement predicts local error hard. If it survives a clean test it **replaces the
7B**, taking the local side back to 3B alone: lighter, cheaper, and a far better on-device story.

**This measurement is contaminated** — the three runs used different retrieval, two of them oracle.
It shows the mechanism is real, not that a deployable version works.

**Test: 3B at n=700, three samples, temperature 0.7, ~3 h GPU, no cloud cost.** After items 1 to 3.

### 5. k=5 — the direction never tried

k was frozen at 10 and tested upward to 20, which was worse. Never downward. Today's decomposition
put **two thirds** of the oracle gain on removing distractors, and gold-alone's advantage came with
2.8 chunks. ~~**Test: condition 1 at k=5, n=700, ~1 h GPU.**~~ **DONE 14 Aug and CLOSED. The prediction failed: 61.4% to 61.6%, p = 1.000. Fewer chunks neither helped nor hurt, and evidence presence turned out not to matter in either direction.**

### WHAT IS OFF THE LIST, WITH THE EVIDENCE THAT KILLED IT

| dropped | evidence |
|---|---|
| Tables as DataFrames | `read_html` loses headers on 100% of 1,079 tables, inflates columns 1.95x, 35% silently lose numbers. 11 Aug. |
| Code sandbox | Prose arithmetic already correct on 64.4% of numeric claims; magnitude trap 3.2%; value correctness barely predicts verdict correctness, 34.8% overlap against 41% under independence. 11 Aug. |
| Claim decomposition, retrieval | Closed 5 Aug. Best variant 57.53% against a 57.88% bar. |
| Claim decomposition, reasoning | `prompts/decompose_v1.txt` exists, never tested end to end. Two calls per claim, the same price as the sandbox, and **no offline test exists to price it first.** Same bucket as the sandbox. |
| Glossary, Tier 3 | ~~cause unknown, read the 49 failures first~~ **CAUSE FOUND 11 Aug, night, and it is not vocabulary.** Knowledge is not retrieval-bound (p = 0.728) and **nothing in the 49 failures turns on an undefined accounting term.** The failure is refusal-on-perceived-absence (§2.11). The glossary does not address it. |

### CONDITION 3 HAS COLLAPSED INTO CONDITION 2 — take this to the professor

Condition 3 is defined in §9.2 as "the cloud model in **every pipeline role**." With tables and the
sandbox dropped, **the pipeline has no roles left.** It is one model call plus an escalation
decision, so condition 3 is condition 2.

**§5.3's contribution statement, "match condition 3 at a fraction of the cost", no longer names a
condition that exists separately.** The 10 August entry already recorded the fallback and it is now
the main line: **condition 2 at 77.0% is the bar, and we match it using the cloud on 36% of
claims.**

This is the first thing to raise at the next meeting, alongside the §5.2 verifier-row problem
already carried from 10 August.

### MACE, restated against the new numbers

**Memory still favours us and the argument survives, weakened.** Their smallest configuration needs
27B resident; the routed rule needs 3B + 7B, about 10B. Still far below. **Another reason item 4
matters** — self-consistency would take the local side back to 3B alone.

**Accuracy is parity, and must be written carefully.** MACE reports 0.76 on FINDVER with Qwen-235B.
Our routed rule is 76.6% strict. **Those are two different scorings and may not sit in one table**
(§9.1). Report FINDVER-compatible or not at all.

**Speed: still do not claim it.** The 3 August finding stands — we are slower.


### THE KNOWLEDGE GAP HAS A MECHANISM, AND ROUTING CANNOT FIX IT

The 49 knowledge claims that are true, had perfect gold evidence, and were still refuted were read
tonight. Full detail in the build log for 11 August, night, and `paper_numbers.md` §2.11.

    group                        n    says INFO MISSING
    entailed, model WRONG       49        28    57%
    entailed, model RIGHT       51         1     2%

**The model declares the information absent, with the gold evidence in front of it, and refutes on
that basis.** Claim length and clause count are identical between the groups, so it is not claim
complexity. Two sub-cases: information literally present and unseen, and — more often — the facts
present but the interpretation not restated, which the model reads as missing.

**This closes the 9 August question about FDV-KNOW.** It is not a retrieval problem (measured this
morning), and it is not a vocabulary problem — **nothing in the 49 turns on an undefined accounting
term, so the glossary hypothesis gets no support.**

**It is not a small-model problem.** All four models do it, and the cloud does it worse:

    model    cites missing    then refutes    those refutations WRONG
    3b        145   21%        106   73%           48   45%
    7b        158   23%        106   67%           31   29%
    flash     132   19%        130   98%           68   52%
    pro        79   11%         76   96%           40   53%

**ROUTING CANNOT REPAIR IT, and this is a reportable negative result.**

    3b + escalate when it refutes AND cites missing info    64.6%   15% cloud
    3b + escalate on any refuted verdict                    71.0%   53% cloud
    the 3B/7B agreement gate we already have                76.6%   36% cloud

Both targeted rules are worse than the existing gate, because escalating hands the claim to a model
that gets those same claims wrong 52% of the time. **You cannot route around a failure mode the
escalation target shares.** The 3B/7B gate works because local disagreement is uncorrelated with
cloud error; this fails because the bias is universal.

**So the prompt is the only lever that touches this, and that is measured rather than assumed.**

**`baseline_v2` targets it directly without having been designed for it.** Predictions recorded
before the runs finish, so they cannot be fitted afterwards:

    responses citing missing information   down from 19% (flash)
    predicted entailed                     up from 31% toward 50%
    accuracy on entailed claims            up from 58.0%
    the gain concentrated on FDV-KNOW

**If those move and accuracy still does not rise, the hypothesis is wrong and we learn that
cleanly.**

**Scope:** 28 of 49 is the dominant mode, not the only one. 54% of *correctly* refuted knowledge
claims also cite missing information, so the phrase is diagnostic only among claims that are true.
The labelling is one reader's over one failure mode and needs a spot-check before the paper.

### Both reproducibility blockers are cleared

`test_scripts/analyse_routing.py` and `test_scripts/measure_table_parse.py` exist and every number
in §2.8, §2.8.1, §2.9, §2.10 and the model-level table of §2.11 regenerates from them. Both import
`load_run` and `two_sided_binomial` from `analyse_condition1.py` rather than copying them.

**One figure moved when the throwaway code was replaced.** The mapping alignment is **0.946 against
0.195**, not 0.940 / 0.191. Same cause as the parse-fidelity correction earlier today: the
throwaway compared numbers as strings, the committed script compares them as floats. Docs updated.



### PROMPT v2 WORKS: 77.0% -> 79.9%, p = 0.002. First significant intervention.

`results/condition2_flash_v2_full700/`, **700 ok, 0 failed, 187.0 min, 4.90 CNY exact.**
Full detail in the build log for 11 August, late, and `paper_numbers.md` §2.12.

                            flash v1   flash v2
    strict accuracy            77.0%      79.9%
    predicted True           217/700    239/700    (gold 350)
    entailed accuracy          58.0%      64.3%
    refuted accuracy           96.0%      95.1%
    ie / knowledge / numeric   80.4 / 70.5 / 78.8   ->   84.0 / 74.0 / 80.4

**Every previous intervention was a tie.** Model variants p = 1.000, oracle retrieval p = 0.116,
the routing gate p = 0.858. **This one is p = 0.002.**

**79.9% is above the best published 2024 RAG figure of 75.0%.** Report FINDVER-compatible, and as a
2026 model against a 2024 table.

**Three of four pre-recorded predictions met. The fourth was wrong and is reported as a miss:** the
gain is NOT concentrated on FDV-KNOW, it is spread evenly across ie and knowledge. The mechanism
was diagnosed on knowledge failures but is not specific to that subset.

**Reduced, not solved.** 26 of v1's 147 false refutations corrected, 3 new false acceptances
introduced, **121 false refutations survive**, and v2 still cites missing information on 16.3% of
claims.

**Costs of the fix:** output tokens +25%, wall clock 147.7 to 187.0 min, and four claims truncated
at the 16,000 cap against zero in v1. **Worth it by an enormous margin** — under one yuan and 40
minutes for the only significant gain measured.

**One network failure**, `numeric-val-25`, an SSL read timeout repaired by resume. The run read
79.7% with it scored wrong and 79.9% after.

### NEXT: the 3B on v2, and it gates everything downstream

**The routing gate is built entirely on local model behaviour.** If v2 helps the 3B the way it
helped flash, every number in §2.10 has to be recomputed. `configs/condition1_3b_v2_full700.json`
is the run, ~80 min GPU, no cloud cost. **Nothing else should be decided before it.**

### WE ARE NOW TUNING ON THE EVALUATION SET. Read this before writing a v3.

Full protocol version in architecture plan **§9.4**, which is where the decision belongs.

**All 700 testmini claims are both our development data and our reported result.** Prompt v2 was
written by reading failures from those 700, tested on those 700, and its 79.9% is reported from
those 700.

**One prompt edit is defensible and disclosable.** It was motivated by a mechanism found in the
data, it changed one clause, and it stands with a sentence in Limitations.

**Three or four rounds of "try a wording, check the 700" is not.** That is fitting noise. With a
per-run noise floor of about one claim in ten and 700 claims, a few points of apparent gain can be
manufactured by iteration alone, and **every number in the paper becomes optimistic by an amount we
cannot estimate or bound.**

**The docs already flag this for the n=102 slice — roughly 15% of any final 700 number comes from
examples we optimised against. Doing it at n=700 is worse, because the overlap is 100%.**

### THE CLEAN WAY OUT, and it exists today

**`test.json` ships 1,700 examples WITH REAL LABELS.** The original plan's "labels are withheld"
assumption is wrong and was corrected on 29 July; our count and MACE's Table 2 agree on the size.

    testmini    700 claims     development. Read failures here, iterate prompts here.
    test      1,700 claims     report here. Touched once, at the end.

**That makes the paper substantially harder to attack**, and it costs one larger run at the end
rather than any change to how we work now. From measured throughput, 1,700 is 2.43x a testmini run:
about **195 min for the 3B on the GPU**, roughly **12 CNY for flash** against the 110.24 remaining,
and about **390 min for the 7B**, which is one overnight job. All affordable.

**What it does not fix:** the retriever, k, and the local model were all chosen against testmini
too. Reporting on test protects the reported numbers, not the pipeline's design. Say that in
Limitations rather than implying otherwise.

### THE DECISION RULE

1. **v2 stands as-is and is reported.** One motivated edit, disclosed.
2. **Before any v3**, either move final reporting to `test.json`, or hold out a stratified split of
   testmini and iterate only on the remainder. **Do not iterate further against the same 700 the
   paper reports.**
3. **Nothing is decided before the 3B v2 run.** The routing gate is built entirely on local model
   behaviour, so if v2 helps the 3B as it helped flash, every routing number is recomputed on v2
   outputs. **Iterating the prompt before that is optimising against half the picture.**

**So: run the 3B on v2 tomorrow, then decide.** If the fix transfers, rebuild the routing table on
v2 and that is a strong result. If a v3 still looks worth trying afterwards, run it against a
held-out split rather than the 700 being reported.


### ORDER OF WORK, revised 12 August after the meeting

**Compute is no longer the constraint.** Everything outstanding is about 14 GPU hours, which is two
nights of the ~11 left before the 23 August freeze. **Design work and writing are the constraint
now.** Order accordingly.

**A. Free, no compute, do first**

1. **Build a better numeric detector.** The headline 79.7% currently leans on a benchmark label
   (§2.13.3). A serious detector either recovers the result or tells us the honest number. No model
   calls, and it de-risks the main claim.
2. **Confirm the policy with the professor:** plain gate, or gate plus numeric escalation. He did not
   give a direct answer and the label finding changes what it costs.
3. **Write the model-choice justification** into the paper notes, using the measured version: three
   candidates tie on accuracy, p = 1.000 pairwise, chosen on 3.5x speed.
4. **Start the Overleaf project.** Owed since 7 August. This is now the schedule risk, not compute.

**B. One GPU night, both fit together**

5. **Self consistency, 3 samples of the 3B at TEMPERATURE 0, n=700, ~2.6 h.** Decided 12 Aug, see
   the section below for why 0 rather than 0.7. **Sample 1 already exists**, so this is two more
   runs, not three. The analysis yields three policies as free re-derivations: majority vote with no
   escalation, escalate on any disagreement, and majority vote with escalation. **Read all three,
   they cost nothing extra, and read the escalation rate before the accuracy.**
6. ~~**k=5, n=700, ~1.5 h.** k was frozen at 10 and only ever tested upward.~~ **DONE 14 Aug, 67.5 min. Tie standing alone, 61.4% to 61.6%, p = 1.000. The local arm stays at k=10 because a k=5 arm forfeits the routed parity claim. See 14 August below.**

**C. One GPU night plus an unattended cloud job**

7. **`test.json`, 1,700 claims, as TWO runs and not three.** See the correction below: condition 4
   is built and run, not derived.

       run 1   the live pipeline on all 1,700, ~10 h GPU + ~7 CNY
               logs the 3B verdict, the 7B verdict, the escalation decision, the cloud answer
               and per-claim timings
               -> yields condition 1 (3B), condition 1 (7B) and condition 4 from one run
       run 2   flash alone on all 1,700, ~7.6 h unattended, ~12 CNY
               -> yields condition 2, the bar

   **Condition 1 comes out of the pipeline run**, because the gate has to compute both local
   verdicts anyway. That is better than a separate condition 1: conditions 1 and 4 then share
   byte-identical local outputs, so the comparison between them carries no run-to-run noise. Given
   that identical reruns disagree on about one claim in ten (§2.3.2), that matters.

   `src/loader.py:32` hardcodes `testmini.json` and needs one line changed. Verified 12 Aug that
   test.json has 1,700 real labels, 439 filings all present locally, and no `explaination` typo.

**D. Needs design before it is worth a night**

8. **Sub-claim decomposition for reasoning.** He likes it. **It is the riskiest item**, because
   unlike every other idea there is no offline way to price it first, which is exactly what killed
   the code sandbox and the table parser. Design an offline proxy before committing a night.
9. **Prompt skills.** Conditional prompting per model and possibly per subset. Blocked on how the
   skill gets selected, since selection by subset label is not deployable.

**E. If time**

10. **Build condition 4 as a live pipeline** rather than an offline re-derivation. Accuracy is
    identical either way, but it gives a real latency measurement and lets the system skip local
    inference entirely on claims it already knows will escalate.

### ~~ORDER OF WORK~~ superseded, kept for the record

1. `baseline_v2`, then flash at n=700, then the 3B at n=700.
2. Fold the routing rule, the per-subset McNemar, the entailed/refuted split and the
   table-parsing measurements into committed scripts. **None of those numbers may be cited until
   this exists** (`paper_numbers.md` rule 1).
3. Rebuild the routing table on whichever prompt wins.
4. If time: self-consistency gate (~3 h), k=5 (~1 h).
5. ~~Deferred, no compute: read the 49 knowledge failures.~~ **Read 11 Aug night; the labelling was
   spot-checked 12 Aug, see below.**

---

## Where things stand, 12 August

### PROMPT v2 DOES NOT TRANSFER TO THE 3B. It is a tie, and the hold is lifted.

`results/condition1_3b_v2_full700/`, **700 ok, 0 failed, 80.6 min on the GPU.**

                            3b v1     3b v2
    strict accuracy         61.4%     63.3%
    unparseable              1.1%      0.3%
    predicted True        324/700   309/700     gold 350

    paired: agree 513/700, v1 right 86, v2 right 99, McNemar p = 0.378   TIE

**The prediction recorded before the run was met.** Flash was 19 points off balanced and gained 2.9
at p = 0.002. The 3B was only 4 points off, so there was little for a de-biasing prompt to fix.

**The mechanism ran backwards.** Flash moved predicted True 217 to 239, toward gold's 350. **The 3B
moved 324 to 309, away from it.** So the +1.9 is not the intervention working, and it is not
significant regardless.

**"Nothing is decided before the 3B v2 run" is now discharged. The routing table built on v1 local
outputs stands and does not need recomputing.**

**The paper claim is stronger this way:** the benchmark's inherited clause costs a frontier model
21% of the benchmark and is repairable there at p = 0.002, and the same repair does nothing at 3B.
The defect and its fix depend on model scale.

### CONDITION 4 WITH A v2 CLOUD ARM IS HARDER, NOT EASIER

Local arm stays v1. Cloud arm goes to v2. Priced under the existing gate from files already on disk:

    gate = 3B/7B agree -> keep 7B, else escalate     routed   cloud alone       p
    cloud arm = flash v1                             76.6%       77.0%      0.858
    cloud arm = flash v2                             76.9%       79.9%      0.066

**Only 36% of claims reach the cloud, so v2's +2.9 dilutes to +0.3 on the routed system while the
bar rises the full +2.9.** The gap goes 0.4 to 3.0 points and p goes 0.858 to 0.066. Still a tie,
one unlucky claim from a measurable loss.

**Numeric carries all of it: routed 72.4% against 80.4%.** "Always escalate numeric" is now worth 8
points rather than 6, and is the first thing to try.

### ALWAYS ESCALATE NUMERIC WORKS. First rule in the project to beat the gate at p < 0.05.

Priced from files on disk, no new runs. Full detail in `paper_numbers.md` §2.13.2.

    cloud arm = flash v2              acc     cloud calls    p vs gate
    gate as-is                      76.9%        35.9%
    + always escalate numeric       79.7%        61.0%         0.005
    + numeric and knowledge         79.6%        78.6%         0.045
    flash v2 alone                  79.9%       100.0%

**79.7% against cloud-alone's 79.9% is parity at 61% of the calls.** Everything tried before this
tied: model variants p = 1.000, oracle retrieval 0.116, the gate against cloud-alone 0.858. Adding
knowledge buys nothing for 18 more points of call volume, so **numeric alone is the operating
point.**

### THE CURVE, and the intuition that did not survive it

    policy                          acc     cloud    USD/700    marginal
    3B alone                      61.4%       0%      0.000
    7B alone                      72.4%       0%      0.000
    gate                          76.9%    35.9%      0.253    +4.4 pts / +36% calls
    gate + always numeric         79.7%    61.0%      0.431    +2.9 pts / +25% calls
    always cloud = condition 2    79.9%     100%      0.706    +0.1 pts / +39% calls

**The first 36% of calls and the next 25% buy accuracy at an identical rate, 0.12 points per percent
of calls.** "Doubling escalation for 3 points is poor value" does not survive the arithmetic: both
points lie on one line. **The discontinuity is the last step, 39% more calls for 0.1 points**, which
makes cloud-alone dominated.

So 36% versus 61% is not an efficiency question. It is a claim about how much stays on the device.
Cost does not decide it, $0.25 against $0.43 per 700. **OPEN, for today's meeting.**

**Cuts against the on-device intuition:** on the MacBook a flash call is ~12.7 s and the local
3B+7B pair is several minutes per claim, so more escalation is *faster* there. §3.5's rule: name the
machine or do not make the latency claim.

### 13 AUGUST: SELF CONSISTENCY IS DEAD AT TEMPERATURE 0, AND THE MACHINES RUN DIFFERENT OLLAMA VERSIONS

    unanimous     696/700 = 99.4%
    split           4/700 =  0.6%     <- escalation rate, against a predicted 15-20%

**The model is deterministic.** Two runs produced byte-identical responses on all 700 claims. Three
samples of a deterministic model are one sample repeated. **Closed, not "needs more work".**

Evidence, including the response hashes, is in the build log entry for 13 August; the two result
directories were deleted to reclaim 28 MB and the counts are not regenerable from run files.

### LOGPROB MARGIN: signal is real, but the 3B/7B gate beats it. NOT fully closed.

12-minute pilot before committing an 80-minute run. Full detail in `paper_numbers.md` §2.14.

    margin varies       min 0.023  median 7.269  max 13.873          PASS
    low  margin  n=50   54.0% accurate
    high margin  n=50   70.0% accurate     Fisher p = 0.149          NOT SIGNIFICANT

    policy, same 100 claims        acc     cloud
    3B alone                      65.0%      0%
    3B/7B gate  <- the bar        77.0%     39%
    margin gate, low half         72.0%     51%
    margin gate, < 4.0            70.0%     24%
    flash v2 alone                79.0%    100%

**As a replacement the margin is dominated**: more calls, less accuracy. **A second model's opinion
predicts this model's errors better than its own introspection does.**

**Also: enabling logprobs changed 44 of 100 responses**, so a logprobs run could not have reused
`condition1_3b_full700` and would have forced a full downstream recompute.

**CLOSED 13 Aug, round 2 at n=250 stratified.** Both additive variants tested and neither works.

    ALL CLAIMS                  low 61.3%  high 60.2%   p = 0.897
    VARIANT 1, agreement set    low 74.3%  high 66.2%   p = 0.369   direction REVERSED
    VARIANT 2, disagreement set low 42.0%  high 51.0%   p = 0.423

**Round 1's 16-point gap became 1.1 points**, so it was noise at n=100. Variant 1 runs backwards:
inside the agreement set, low-margin claims are *more* accurate. Escalating the low-margin half
would fix 13 and break 9, net +4 over 148 claims, for 50% more cloud calls.

**Both uncertainty gates are now closed on measurement. The 3B/7B gate stands and the 7B stays.**

### THE MACHINES RUN DIFFERENT OLLAMA VERSIONS. Act on this today.

    Mac   0.12.3      pinned, because 0.12.4 dropped macOS 13
    PC    0.32.9      never pinned, has been auto-updating

**`CLAUDE.md`'s auto-update rule was written for the MacBook only.** This is very likely the
7-versus-9 August divergence that produced §2.3.2's 89.2%: only 56 of 102 responses were
byte-identical across that pair, which is an engine change, not scheduling noise.

1. ~~**Turn auto-update off on the PC today.**~~ **DONE 13 Aug.** The PC is pinned at **0.32.9**,
   which is the version every GPU result so far was produced with. The version assertion in `run.py`
   is now a safety net rather than the only defence, but it stays: a setting that was turned off by
   hand can be turned back on by an installer.
2. **The 7 August cross-machine result, 5 of 6, is confounded.** It was attributed to CPU versus
   ROCm arithmetic. It is also a version difference, so that attribution is unsafe.
3. **`Record` does not log the Ollama version.** That is why this took six days to find. Add it
   before the next run.

**§2.3.2's 89.2% is withdrawn as a noise floor.** The rule "a difference smaller than one claim in
ten is noise" was too conservative, and ties dismissed on that basis may deserve rechecking.

### Two things checked so they are not guessed at again

**Seed is inert at temperature 0.** Verified with three calls at seeds 0, 1, 2: identical output,
identical token counts. Greedy decoding never draws a random number. **A three-seed temperature-0
experiment would produce three identical runs.**

**Logprobs work on 0.32.9 and replace the self-consistency experiment.** Pass `"logprobs": true` and
`"top_logprobs": 3` beside `options`; passing a number instead of a bool fails with an unmarshal
error, which is what made the first check look like a lack of support. The response carries each
token's logprob and its top alternatives, so **the model's confidence in its verdict is directly
readable** as the margin between the top token and the first alternative meaning the opposite.

**One run of about 80 minutes replaces the four-hour three-run experiment.** Caveat: 0.12.3 on the
Mac may not support it, so a logprob gate could not be demonstrated on the device of record.

### DECIDED 12 Aug: the self-consistency run uses TEMPERATURE 0, not 0.7

The three samples have to differ from each other or there is nothing to measure. Two ways to get
that, and the cheap one is also the better experiment.

**1. Sample 1 already exists.** `results/condition1_3b_full700/` is temperature 0, BM25 k=10,
prompt v1, which is exactly the local arm's configuration. **So this is two more runs, not three**,
about 2.6 h rather than 4. Prompt v1 is the right base because v2 did not help the 3B (§2.13).

**2. Temperature-0 nondeterminism is a better uncertainty probe than it appears.** The variation
comes from floating-point scheduling on the GPU (§2.3.2). That sounds like pure noise, but it
**cannot flip a claim the model is confident about**: a wide margin between the two logits is immune
to small arithmetic differences. It only flips claims that were nearly tied. That is exactly the
signal the gate needs, obtained without asking the model to be deliberately random.

**3. It keeps the convention.** Everything in this project runs at temperature 0. Making the local
arm the one exception costs a paragraph and invites a question about whether the comparison is
clean.

**The argument against 0.7, stated plainly:** at 0.7 each sample is drawn from a wider distribution,
so each individual answer is likely worse than the greedy one. **We would be degrading the answers
to manufacture disagreement, then paying cloud calls to repair the degradation we introduced.**

#### Prediction recorded BEFORE the run, so it cannot be fitted afterwards

Two identical temperature-0 runs agree on 89.2% of verdicts (§2.3.2). If a flip means a claim was
nearly tied, roughly 22% of claims are unstable, and an unstable claim comes out non-unanimous about
three times in four.

    predicted escalation rate    15% to 20%

**That is LOWER than the 3B/7B gate's 36%, not higher.** If it holds and the accuracy holds with it,
self consistency is cheaper than the gate on cloud calls *and* removes the 7B, taking the local side
from ~7 GB resident to ~2 GB. That is the good outcome.

**Read the escalation rate first, before the accuracy.** It is the cheaper quantity to trust: "how
often do three samples disagree" is a per-claim binary property and 700 claims pin it tightly, where
accuracy carries the usual noise. **If the rate comes back above about 60% the idea is dead on cost
whatever the accuracy says.**

**The failure mode, and what to do about it.** If the rate is under about 8%, too few claims escalate
for the cloud to repair anything and the result collapses toward the 3B alone at 61.4%. **That is not
a reason to drop the idea. It is the reason to rerun at 0.7.** Cheap version first; it tells you
whether the expensive version is worth a night.

**Standing caveat.** The 401 unanimous against 299 split that motivates all of this came from three
runs with different retrieval, two of them supplied with gold evidence. **It has never been measured
fairly at any temperature.** The mechanism is real; the effect size and the escalation rate are both
unknown.

### CORRECTED 12 Aug: condition 4 is BUILT AND RUN, not derived from three separate runs

An earlier note in this file said condition 4 "falls out for free" from the three per-model runs.
**That is true of the accuracy number and false of everything else, and it contradicted advice given
the same afternoon.**

**What is free:** the accuracy. 79.7% is mathematically identical whether the cloud is called live at
the moment of disagreement or its stored answer is looked up afterwards, because the gate is
deterministic given three verdicts.

**What is not free: the system.** Three reasons to build it, and the third exists only in the live
version.

1. **A real latency measurement.** Derived, we can only add per-model numbers together. Built, it is
   measured end to end.
2. **We can say we ran it**, rather than that we simulated a policy over stored files. At a workshop
   about real-world constraints that is not a cosmetic difference.
3. **The live version can skip work the derivation cannot see.** Under numeric escalation those
   claims are already known to be going to the cloud, so **neither local model should run on them.**
   That removes about a third of the local compute. It is invisible in a re-derivation because
   everything was run on everything.

**Sequencing, per claim and not per batch:** 3B first, then 7B, compare the two verdicts, escalate on
disagreement.

**What it needs in code, which is not a new component.** `run_loop.py` already does retrieve, build
prompt, call, record. `ollama_client.py` talks to both local models and the DeepSeek path is written.
Missing is the control flow between them, and a record type storing three verdicts and a decision
rather than one verdict. It lives in `src/`, so it is written block by block in chat.

### THREE THINGS TO PUT TO HIM NEXT WEEK

1. **The policy question is still open and must not be treated as settled.** The reading taken from
   the meeting was that he prefers numeric escalation on accuracy. **That was before we knew the
   79.7% uses a benchmark annotation** (§2.13.3).
2. **"Only API cost is settled" is worth pushing on.** Graceful degradation is measurable now with no
   compute: remove the network and the routed system still answers every claim at **72.4%**, where
   pure cloud returns nothing. That is a stronger argument than cost and it is one afternoon of
   analysis.
3. **Keep the MacBook.** He is content for the Windows GPU box to carry the on-device claim. The
   MacBook is what makes this a constraints paper rather than a small-model paper, so the final
   latency night belongs on it.

### MEETING, 12 AUGUST. What was decided, and the one thing still open.

**Approved and now the agenda:** self consistency, k=5, and splitting claims into sub-claims for
reasoning. He called the sub-claim split "a really good idea". Note it was closed for *retrieval* on
5 August; this is the separate reasoning question.

**Prompt optimisation approved, with a direction.** Not by training or fine-tuning a model. Iterate
on testmini, report on `test.json`. His suggestion is a set of prompt-construction "skills", one per
model and possibly one per subset.

**On-device:** he is content for the Windows GPU box to carry it, since the edge models still run
locally there. **Keep the MacBook anyway.** It is the harder constraint and the stronger claim.

**On what we may claim over condition 2, only API cost is settled.** Graceful degradation and
partial privacy need analysis before they can be argued.

**He wants the model-choice justification written down**, expecting a reviewer to ask why this 3B,
this 7B, this cloud model. The measured answer is stronger than the one given in the meeting: three
3B-class candidates tie on accuracy at n=102, every pairwise McNemar p = 1.000, so the choice was
made on cost. `coder:3b` is 3.5x faster per claim with 3.1x fewer output tokens. Also the professor
named it himself, and neither Coder variant is in FINDVER's published 16.

### STILL OPEN: which policy is the system?

**Plain gate, or gate plus always-escalate-numeric?** The meeting did not settle it. The reading
taken away was that he prefers the numeric version on accuracy. **Confirm rather than assume**, and
the finding below changes what that choice costs.

### THE NUMERIC RULE USES A BENCHMARK LABEL. The headline needs re-labelling.

`always escalate numeric` reads `claim.subset`, an annotation FINDVER ships. **No deployed system
has it.** Full detail in `paper_numbers.md` §2.13.3.

    policy                          acc     cloud     deployable
    gate only                     76.9%     35.9%     yes, model verdicts only
    gate + numeric LABEL          79.7%     61.0%     NO, uses the annotation
    gate + tight detector         77.9%     62.6%     yes, costs 1.8 points
    gate + loose detector         80.0%     85.1%     yes, cost advantage gone
    always cloud                  79.9%    100.0%     yes

**79.7% at 61% is an oracle-assisted number.** Removing the label costs either 1.8 points or most of
the call saving. Both detectors were written in minutes, so this is a flag rather than a verdict,
and a better one is cheap.

**The plain gate is unaffected and needs no annotation.** If the paper needs one number beyond this
objection, that is the one.

**It also constrains the skills idea:** a per-subset skill selected by the subset label inherits the
same problem.

### REJECTED: baselining condition 2 at v1 while the pipeline runs v2

The objection is not that the prompt fix is not ours. **Condition 2 at v2 is already measured at
79.9% and sits in `results/condition2_flash_v2_full700/`.** Baselining against a handicap we know
how to remove invites the question "what does the cloud model alone score with your prompt", and the
answer erases the claim.

**Report the prompt defect as its own finding** — a property of FINDVER's shipped prompt carried by
all 16 published baselines, costing a frontier model 21% of the benchmark at p = 0.002 — **and
compare condition 4 against condition 2 at the same prompt.** Disclose that the pipeline runs v1
locally and v2 in the cloud, because v2 was measured not to help the 3B.

---

Everything below is Mac daytime work off result files already on disk. No nights spent, no cloud
calls. Full detail in the build log for 12 August.

### The morning was lost to a machine that was not signed in

The run failed on every claim with `URLError: [Errno 60] Operation timed out`. The PC was powered
on but sitting at the lock screen. **Ollama on Windows is a per-user tray app, not a service**, so
it does not start until someone signs in, and Windows drops the connection silently instead of
refusing it. From the Mac that looks identical to the machine being switched off.

Two things not to rediscover. **Kill the run before deleting its results folder** — it was still
alive and kept recreating the folder with fresh failed records. And **deleting was never needed**:
`logger.has_result` returns true only for `status == "ok"`, so resume re-runs failed claims by
itself, which three harness tests already cover.

### §2.11 HAD NO REPRODUCER, AND THE SPOT-CHECK MOVED A NUMBER

§2.11 pointed at `analyse_routing.py`, which has no phrase matching in it and cannot produce any
number in that section. The figures came from throwaway code never saved, and the phrase list
survived only as prose ending in "and so on". **Under rule 1 every §2.11 number was unusable**,
including the model-level table the "routing cannot fix it" negative result rests on.

`test_scripts/analyse_missing_info.py` is the reproducer. **Built and verified 12 Aug**: it
regenerates both §2.11 tables, and `--show wrong|right` prints every matched sentence in context so
the regex is checked by reading rather than trusted.

**The spot-check found a defect in the matcher, not in the reading.** A bare `lack` matches the
subject matter rather than the model's reasoning: "a lack of authorized shares" is a fact in the
filing, not the model reporting absent evidence. Five of seven control-group hits were this.
Anchoring absence words to the document leaves 2 of 51, both genuine.

    separation, entailed-wrong vs entailed-right     28-fold  ->  15-fold
    diagnostic set, cites missing                    28/49    ->  29/49  (59.2%)
    control group                                     1/51    ->   2/51  (3.9%)

**The 11 August read and its conclusion stand.** The mechanism is unaffected. What moved is a
headline ratio, and it moved in the direction that had made the finding look stronger.

**The four base refutation rates reproduce exactly**, which is what confirms the loading and scoring
were right. **One row is unexplained: pro's cites-missing count goes 79 to 133.** Its ratios hold,
so the conclusion holds, but the count is flagged and should not be cited yet.

**Also corrected: the 49 is 48 refuted plus one unparseable**, `knowledge-val-0`.

### Still owed

§9 wants a four-category error taxonomy. This is one category, labelled by one reader. And claim
words and clauses, 42.9 / 3.8 against 41.9 / 3.6, are still throwaway figures the script does not
regenerate.

---

## Where things stand, 14 August

### k=5 IS CLOSED. Free standing alone, but it forfeits the routed parity claim.

`results/condition1_3b_k5_full700/`, **700 ok, 0 failed, 67.5 min on the GPU.** Everything except
`top_k` matches `condition1_3b_full700`, so the pair isolates k.

                            k=10      k=5
    strict accuracy        61.4%    61.6%
    unparseable             1.1%     0.3%
    prompt tokens, mean     3,731    1,998
    seconds per claim         6.8      5.8

    paired: agree 453/700, 122 against 123, McNemar p = 1.000   TIE

Per subset the deltas are +2.8 ie, +3.5 knowledge, -5.2 numeric, and **all three are ties**,
p = 0.543, 0.489, 0.160. The numeric drop is 13 claims against a rerun noise floor of about one
claim in ten, so it is a hypothesis at best. Sixth small-sample trap, avoided this time.

**The routed re-derivation is what decided it.** From stored files, no new runs:

    local arm = 3B at        k=10                    k=5
    routed                 76.9% @ 36% calls     75.7% @ 37% calls
    vs flashv2 alone       p = 0.066  TIE        p = 0.004  WORSE
    + always numeric       79.7% @ 61% calls     78.9% @ 61% calls

Two comparisons that are easy to confuse, both true. **k=5 routed against k=10 routed is a tie**,
p = 0.422, so there is no evidence k=5 is worse in itself. **k=5 routed against cloud-alone is
significantly worse**, where k=10 routed is a tie with it. The paper's central claim is parity with
cloud-alone at a fraction of the calls, and a k=5 local arm loses that claim. k=5 also raises cloud
calls, 35.9% to 37.4%, because the two local models now read different context and disagree more.

**Decision: the local arm stays at k=10.** No standalone upside, no call saving, real risk to the
one comparison the paper rests on.

### THE REAL RESULT: evidence presence has now failed in both directions

    evidence_present       52.0%    36.1%     -15.9 points
    strict accuracy        61.4%    61.6%      +0.2 points

And inside the k=5 run alone, claims where the gold evidence reached the prompt scored 62.5%
against 61.1% for claims where it did not. **1.4 points.**

On 11 August the model was handed perfect evidence and gained almost nothing, p = 0.116. Today it
lost a third of its evidence and gave up almost nothing. **Two experiments pushing opposite ways
and agreeing is a finding, where either alone could be a design artefact.**

This is why the 74.06% fused recall has never converted into accuracy. On this model retrieval
quality and answer quality are close to decoupled. **Report the recall number as a retrieval
result. Do not sell it as an accuracy driver.** The negative result deserves a section of the paper
rather than a sentence.

### CONTRADICTION: prompt size is not the lever on wall clock on the GPU

Four 3B runs, same model, same GPU box:

    run                prompt tok   output tok   s/claim
    gold_alone              1,124          389       5.3
    k=5                     1,998          396       5.8
    k=10                    3,731          416       6.8
    gold_padded             3,711          418       6.9

Prompt tokens rise 3.3x, wall clock rises 1.28x. Least squares over the four:

    elapsed = 0.00060 s per prompt token + 4.6 s fixed      R2 = 0.996

Linearity holds. The coefficient does not. The recorded law is **0.0641 s per prompt token**, fitted
on 11 MacBook examples. **The GPU coefficient is 107x smaller.**

**The 4.6 s fixed term is not decomposed and must not be quoted as a generation rate.** Output varies
only 389 to 418 tokens across the four runs, so this data cannot separate generation from any other
per-claim constant. `architecture_plan.md` §4.6 already hit that exact degeneracy on the MacBook and
rejected the fit. What is safe: **4.6 s per claim does not scale with prompt size and is 67 to 87
percent of wall clock.** Generation is the largest plausible component but is not measured here.
Confirming it needs a run that varies `num_predict`, which has never been done.

**The planning conclusion is unaffected: prompt size is nearly free on the GPU.**

**Neither fit is wrong on its own machine.** The MacBook is CPU-only, where ingestion genuinely
dominates. It simply does not transfer, and GPU runs have been planned against a MacBook constant
since 7 August. Same cross-machine trap as the Ollama version split found on 13 August, different
variable.

Marked in place above at the fit and at the "only real lever" claim. **Still to fix:**
`architecture_plan.md` lines 782, 1004 and 1560, and the hard constraints in `CLAUDE.md`, which is
the author's own file. Line 1560 is load-bearing: "tighter retrieval buys wall-clock and recall
together, and it is the only thing in the project that does both" is false on the GPU box.

### What is still open after today

Item 6 of the 12 August agenda is closed. **Item 7, `test.json` at 1,700 claims, is now the
priority**, and today added to its case: k=5 is the fourth configuration choice made against the
same 700 the paper reports, after k=10 versus 20, prompt v1 versus v2, and always-escalate-numeric.

---


## Where things stand, 15 August

### THE NUMERIC RULE IS DEPLOYABLE. The benchmark label is gone.

`src/numeric_detector.py`, three regexes, no model call, no cloud call. Full detail in
`paper_numbers.md` 2.13.4 and the build log for 15 August.

**The pattern: a numeric claim is an equation written as an English sentence.** A computed
quantity as the subject, a copula, the value last. `The <X> ... is/was <number>.` matches
**151 of 250 numeric claims and 0 of the other 450.** Numeric claims average 20.5 words, the
other two subsets 41.

                              acc     calls    deployable
    gate only               76.9%     35.9%    yes
    gate + subset LABEL     79.7%     61.0%    NO, reads claim.subset
    gate + DETECTOR         79.0%     54.0%    yes
    always cloud            79.9%    100.0%    yes

Paired: vs the oracle label policy p = 0.180, **tie**. Vs cloud-alone p = 0.581, **tie**.

**The 12 August objection is answered.** The headline no longer needs an annotation, and it
costs 7 points fewer cloud calls than the label policy rather than the 1.8 accuracy points the
tight detector cost. Item 1 of the 12 August "do first" list is closed.

### The held-out check is the reason to believe it

`test.json` is 1,700 claims that were never inspected while the patterns were written, and it
ships subset labels, so checking costs nothing.

    whole detector    testmini  182 flags, precision 1.000, recall 0.728
                      test.json 449 flags, precision 0.984, recall 0.737

**This also caught a real error before it shipped.** The rule I first proposed had six patterns,
all at or above 0.978 precision on testmini. Three of them fell to 0.727, 0.889 and 0.905 on the
held-out file. Dropping them left routed accuracy unchanged, cut calls 55.6% to 54.0%, and
raised held-out precision to 0.984. **On testmini alone the six-pattern rule looked better than
the three-pattern one. It was not.**

### Three limits, carried into the paper

1. **The routed row is testmini only, and derived rather than run.** Precision and recall are held
   out, accuracy and calls are not. This is the **fifth** configuration choice made against the 700
   claims the paper reports, after k=10 vs 20, prompt v1 vs v2, always-escalate-numeric, and k=5.

   **The live pipeline will not reproduce 79.0% at 54.0%.** Reruns move 10.8% of local verdicts.
   Resampling both local arms at that rate, accuracy lands at 79.6% (95%: 78.4-80.9) but cloud
   calls land at **56.5% (95%: 54.3-58.7)**. The call rate is biased upward, not just noisy: extra
   disagreement can only add escalations. **54.0% is a lower bound. The paper reports the run.**
2. **It may be a generation artefact.** 60.4% of numeric claims fit one template, 86.4% end with
   a number. Say the detector keys on claim phrasing. Do not imply it transfers to human-written
   claims.
3. **27% of numeric claims are missed**, mostly the verb form "X increased by 16.79% from 2022 to
   2023". Tier 2 catches them: 79.6% at 58.7% calls, held-out precision 0.887. It is the better
   detector by F1 and gains 4 claims, but **p = 0.219, a tie**, and it costs 33 extra cloud calls
   and 10 points of held-out precision. **Set aside, not killed** — reach for it first if the
   test.json run shows recall hurting the numeric subset.

### What is still open

Item 7, **`test.json` at 1,700 claims**, is still the priority and today added a fifth item to
its case. The routed pipeline in `src/` does not exist yet: `run_loop.py` handles one model per
run, and nothing sequences 3B then 7B then the escalation decision. That has to be built before
run 1 can happen.

**Overleaf is still not started.** Owed since 7 August. Today is 15 August, the freeze is
23 August.

---


## Where things stand, 16 August

### THE ROUTED PIPELINE IS BUILT AND UNDER TEST. Not yet run.

`src/routed_loop.py`, `run_pipeline` in `run.py`, `configs/pipeline_trial.json`. This is condition
4 built rather than derived. Detail in the build log for 16 August.

Per claim: the detector decides first and costs nothing, then 3B, then 7B, keep the shared verdict
when they agree, cloud when they differ. Nothing was re-implemented, because `run_one_claim`
already does one model end to end and gets called up to three times with three configs. The
prompt split falls out of that for free, locals on v1 and cloud on v2.

### THE SKIP FLAG IS ON EXACTLY ONE RUN

    run 1, skip OFF :  13.8 h   yields condition 1 (3B), condition 1 (7B), condition 4
    run 1, skip ON  :  11.2 h   yields condition 4 only
      + condition 1 runs        9.7 h

Skipping saves 2.6 h and costs 9.7 h to get condition 1 back. **Flag off for the 1,700 run, on for
a ~100 claim latency run afterwards, about 40 minutes.** That second run is the only reason the
flag exists.

**Corrected:** the 12 August note says skipping removes "about a third of the local compute". That
was the subset label at 35.3%. Our detector flags **26.4%**.

**Corrected:** run 1 is **13.8 hours, not the 10 in item 7**. Run 2 at 7.6 h is right.

### THE HARNESS NOW COVERS THE ROUTED PATH: 123 checks -> 162

`pipeline_trial.json` **broke the gate**: `test_harness.py` read `cfg["num_ctx"]` on every config
and a pipeline config has no such key, so it died with `KeyError` before running any check. Fixed,
and stage blocks are now validated instead, including that every `prompt_version` in every config
names a file that exists.

39 new checks drive every path through `route_one_claim` with stubs, no model and no network.
**The one that matters is the skip path**, which raised `NameError` and silently wrote every
skipped claim as failed. That flag is only on for the final latency run, so the bug would have
surfaced at the very end of the schedule.

### THE TRIAL RUN PASSED. 30 ok, 0 failed, 14.2 minutes.

`results/pipeline_trial/`. 13 cloud calls of 30, six from the detector and seven from disagreement.
Stage records were 2 or 3 and never 1, which is the check that skip is off. **Ignore the 43.3% call
rate and the 73.3% accuracy, n=30.**

**Every analysis script read the routed directory with no new code**, which is what `RoutedRecord`
repeating the answer at top level was for.

**Prompts are byte-identical, 73 of 73**, across all three stages, and `prompt_eval_count` agrees
too. `test_scripts/check_pipeline_prompts.py` is the reproducer. This is the validation that the
plumbing is right; verdict equality is not and never could be.

### THE CLOUD IS THE LESS REPRODUCIBLE HALF, first direct measurement

Verdicts against the stored runs, on prompts confirmed byte-identical:

    local_a   27/30 = 90.0%    predicted about 89.2%
    local_b   28/30 = 93.3%
    cloud     10/13 = 76.9%

The local arms hit the prediction from 2.3.2 on a different sample and a different day. **The cloud
moved 23.1%, about twice the local rate.** DeepSeek was known to ignore `seed` and `temperature`,
but the effect on verdicts had never been measured. **n=13, a flag not a rate.** Re-running the
sensitivity analysis with the cloud at 23.1% leaves every conclusion unchanged.

### What to do next, in order
1. **RUN 2 FIRST, and it needs no GPU.** `configs/condition2_flash_v2_test1700.json`, flash alone
   on all 1,700 claims: API calls plus BM25 on CPU, so it runs on the MacBook. **7.6 h, 1.72 USD.**
   It yields condition 2 at n=1,700, the bar. The two runs are independent, so the cloud half can
   finish while the GPU is unavailable.

       python3 test_scripts/test_harness.py && \
       caffeinate -ims python3 run.py configs/condition2_flash_v2_test1700.json 2>&1 \
         | tee logs/condition2_flash_v2_test1700.txt

   Check the header says `sample 1700 examples, full test` before leaving it.

2. **Run 1 when the GPU is back.** `configs/pipeline_test1700.json`, 13.8 h, about 0.96 USD of
   cloud. Yields conditions 1 (3B), 1 (7B) and 4 from one job.

### API SPEND, 16 August: 36.13 CNY

Two defects in `api_cost_tally.py`, both fixed today.

**1. It was blind to routed runs.** A routed record's `config["model"]` names the system rather
than a priced model, so the whole directory was skipped and `pipeline_trial`'s 13 cloud calls
appeared nowhere. The 1,700 claim routed run would have hidden about 950. Now the cloud stage is
priced out of `stages`, and the table prints `13/30` where billed calls and claims differ.

**2. Its total line used a flat 7.2 CNY/USD**, which §"TALLIED 10 Aug" already recorded as wrong.
The error is model-specific: flash bills at 6.94 per attributed USD, pro at about 11.8. `CNY_PER_USD`
is now a per-model dict and every CNY figure goes through one helper.

    TOTAL   3.654 USD    36.13 CNY

**The rates reproduce both exact balance deltas**, which is what makes them trustworthy: flash v2
at n=700 predicts 4.90 against an exact 4.90, and pro700 + flash700 predicts 26.90 against an exact
26.96.

**Projected**, both remaining runs being flash only: run 2 is 11.9 CNY, run 1's cloud is 6.7 CNY,
**18.6 CNY for both**.

### THE ACCOUNT WAS TOPPED UP. 110.24 -> 468.07 CNY.

Read 16 August immediately before starting `condition2_flash_v2_test1700`. The previous reading was
110.24 on 11 August. **The only cloud spend in that window was `pipeline_trial`, about 0.09 CNY**,
so roughly **358 CNY was paid into the account** between 11 and 16 August. `granted 0.00`, so it is
a top-up and not promotional credit. That is the professor's money and he should be thanked for it,
and told what it is being spent on.

**Every budget note in this file written before today assumes 110 to 115 CNY remaining and should
be read with that in mind.** The two big runs are now about **4% of the balance, not 17%**.

**This does not licence switching to pro.** Pro is still roughly 5x flash per run in real billing,
and the reason flash won was an accuracy tie at n=700, not affordability. Cost was the fourth
argument, not the first.

    balance readings, CNY
      9 Aug  142.38   after the two n=102 runs
     10 Aug  115.42   after both n=700 runs, delta 26.96
     11 Aug  115.14   settlement lag
     11 Aug  110.24   after flash v2 at n=700, delta 4.90
     16 Aug  468.07   BEFORE condition2_flash_v2_test1700, after a ~358 top-up

**Still owed:** the after-reading once run 2 finishes. Its delta gives the exact cost of a
1,700-claim flash run, and will show whether 6.94 CNY per attributed USD holds at this scale or was
fitted to n=700.

### Harness is at 210 checks

189 -> 210 today. The two new configs added 19 by existing rules and exposed one gap: nothing
validated the `split` key, so a typo would have passed the gate and failed at run time.

### DONE 16 Aug: the loader takes a split

`load_claims(split="testmini")`, `EXPECTED_COUNTS` keyed by split, `build_sample` reading
`config["split"]`. The default keeps all eight existing call sites untouched. Harness 162 -> 189.

### NEW DATA TRAP: test.json ships four fields fewer than testmini

    field                  testmini            test.json
    python_calculation     250 numeric         ABSENT
    execution_result       250 numeric         ABSENT
    knowledge              200 knowledge       ABSENT
    explanation            all 700 non-empty   600 numeric are EMPTY STRINGS
    explaination typo      250 numeric         does not occur

Nothing crashes and nothing in the codebase reads the missing fields, so this is silent.

**What it costs: test.json's numeric subset has no gold reasoning at all.** No explanation, no
reference calculation, no reference answer. **The arithmetic cannot be checked against FINDVER's
own computed value on the split the paper reports**, which is exactly the check that caught the
`$15,800,015` error on 2 August. Any numeric error taxonomy has to be built on testmini or read by
hand. **This belongs in the CLAUDE.md trap list, which is your file.**

**Overleaf is still not started.** Owed since 7 August. Today is 16 August, the freeze is
23 August.

---


## Where things stand, 17 August

### CONDITION 2 IS MEASURED AT n=1,700. 77.4%. First number tuned on nothing.

`results/condition2_flash_v2_test1700/`, **1,700 ok, 0 failed, 8.4 hours** on the MacBook with no
GPU. Full detail in `paper_numbers.md` 2.15 and the build log for 17 August.

    strict accuracy      77.4%     testmini was 79.9%
    unparseable           1.4%     all 23 from truncation at num_predict 16k
    per subset            ie 82.3%   numeric 77.2%   knowledge 71.6%

**2.5 points below testmini, which is the direction predicted before the run**, because five
configuration choices were made against testmini and tuned choices do not fully transfer.

### THE REFUTED BIAS REPLICATES ON 1,700 HELD-OUT CLAIMS

                                 testmini n=700    test.json n=1,700
    predicted entailed               34.1%              33.9%
    gold entailed                    50.0%              50.1%
    accuracy on entailed             64.3%              61.7%
    accuracy on refuted              95.4%              93.1%

**Prompt v2 reduces the refuted bias and does not remove it, and the residue reproduces to within
0.2 points on claims that played no part in designing v2.** A 31 point entailed/refuted gap on both
sets. **This is the strongest evidence in the project**, because replication at n=1,700 on a
held-out set is worth more than any single-set effect.

### THE CLOUD BILL IS 18x THE ESTIMATE. ASK THE PROFESSOR BEFORE RUN 1.

    balance before   468.07 CNY
    balance after    228.72 CNY
    delta            239.35 CNY      predicted 11.9

**DeepSeek raised prices**, confirmed from their docs today: flash went from 0.14/0.28 to
0.22/0.66 off-peak and 0.44/1.32 peak. **Even at peak this run should have cost about 54 CNY.**
About 4.4x of the charge is unexplained.

    11 Aug     4.90 CNY /   700 calls  = 0.0070 CNY per call
    17 Aug   239.35 CNY / 1,700 calls  = 0.1408 CNY per call     20x

Tokens per claim moved 12%, so this is pricing or billing, not usage. **Either the CNY list is far
above the USD list, or the key is being used by someone else.** The ~358 CNY top-up between 11 and
16 August is consistent with a shared account.

**Two things to ask him, and the second has been owed since 10 August:**
1. Is this key shared with anyone else?
2. Read access to the account usage page, which settles it in one look.

### RUN 1: 14.4 HOURS, 134 CNY, 58% OF THE BALANCE

Repriced on measured figures. The cloud arm measured 17.8 s per claim, not the assumed 16.0.

    3B on all 1,700       3.21 h
    7B on all 1,700       6.47 h
    cloud on about 56%    4.71 h
    TOTAL                14.39 h      previously quoted as 13.8 h

    cloud cost   ~950 calls x 0.1408 = 133.8 CNY
    remaining after                    about 95 CNY

**Affordable, not comfortable, and 0.1408 is a floor rather than a forecast.** Put it to the
professor before launching.

### DONE 17 Aug, free, no GPU: two held-out measurements, both replicate

**Retrieval recall on test.json.** `python3 test_scripts/measure_recall.py 10 test`. Upstream ships
rankings for both splits, so this cost nothing but CPU.

    macro recall at k=10       testmini      test.json
    ours, bm25                  74.60%        75.16%
    text-embedding-3-large      68.01%        69.75%
    upstream's own bm25         65.16%        64.29%

**Our BM25 replicates within 0.6 points on 1,700 claims it was never tuned on and beats the best
published retriever by 5.4 points there.** All three metrics hold. **Fusion is dead on the held-out
split too**: RRF 74.95% against BM25 alone 75.16%, the same ordering as testmini. The 5 August
freeze on BM25 with no dense arm now has held-out evidence. Full detail in `paper_numbers.md` 2.16.

**The knowledge error mechanism replicates, and it is 63% of knowledge errors.**

                              testmini          test.json
    knowledge errors        33/52 = 63.5%     90/142 = 63.4%
    all errors              54/141 = 38.3%   158/385 = 41.0%

The category: the model declares the evidence absent, refutes on that basis, and is wrong. **One
failure mode is nearly two thirds of all knowledge errors on both splits.** This is the first
quantified category of the four-category taxonomy §9 has wanted since the start. `paper_numbers.md`
2.17.

### SKILLS: deferred, with the reason written down

Testing a 3B prompt needs a GPU night and tonight's is run 1. Prompt v2 was +2.9 points at
p = 0.002 on the cloud model and a **tie on the 3B, p = 0.378**. And skills must be evaluated
without tuning on the reported set, which `test.json` now is.

**What did change: the numeric detector solves the selection problem** for arithmetic claims, at
0.984 held-out precision. That was the blocking question on 12 August. A skill for arithmetic
claims is now selectable. Recorded, not yet worth a night.

### What to do next, in order

1. **Ask the professor the two questions above.** Free, and it gates how much the rest costs.
2. **Run 1**, `configs/pipeline_test1700.json`, when the GPU is back. 14.4 h. Yields conditions
   1 (3B), 1 (7B) and 4 from one job.
3. **Overleaf.** Owed since 7 August. Today is 17 August, the freeze is 23 August. **Six days.**

### Cost bookkeeping changes

`api_cost_tally.py`: current rates added as `PRICING_CURRENT_PEAK`; **historical rates deliberately
kept in `PRICING`**, because repricing old runs at today's list rewrites history and the 11 August
run is known to have cost exactly 4.90 CNY; the CNY-per-USD ratio **withdrawn** as a planning tool
after fitting two points and missing the third by 18x; `CNY_PER_CLOUD_CALL = 0.1408` added as the
measured planning figure.

    balance readings, CNY
      9 Aug  142.38   after the two n=102 runs
     10 Aug  115.42   after both n=700 runs, delta 26.96
     11 Aug  115.14   settlement lag
     11 Aug  110.24   after flash v2 at n=700, delta 4.90
     16 Aug  468.07   after a ~358 top-up, before condition 2 at n=1,700
     17 Aug  228.72   after it, delta 239.35

---


## Where things stand, 18 August

### RUN 1 IS UNDER WAY, IN CHUNKS. 312 of 1,700 done, 0 failed.

`results/condition4_pipeline_test1700/`. The GPU is only available in short windows, so the run is
being taken in chunks. **No code change was needed**: `has_result` is true only for `status == "ok"`,
so Ctrl-C and re-running the same command resumes exactly where it stopped. Verified with stubs
before relying on it.

    resume:  set -a; source .env; set +a
             caffeinate -ims python3 run.py configs/pipeline_test1700.json 2>&1 \
               | tee -a logs/pipeline_test1700.txt

**Never delete the results directory between chunks. Always `tee -a`, never `tee`.**

Chunking costs about **7 seconds of model warm-up per restart**, measured. Nothing else: per-claim
timing is a stopwatch around one claim.

### THE ROUTING PREDICTION HOLDS AT 57.4%

    cloud calls        179/312 = 57.4%    predicted 56%, derived floor 54%
      numeric_detector    95
      disagreement        84
    stage records      2 on 133, 3 on 179, never 1
    seconds per claim  32.5 mean  ->  15.3 h for the full run, not 14.4

The 16 August simulation predicted 56.5% with a 95% range of 54.3 to 58.7, and argued the live rate
must exceed the derived 54.0% because independent noise can only add disagreements. **The live
figure is inside that range and the mechanism holds.**

### THE COST PANIC WAS MISDIRECTED. WITHDRAWN.

    216.60 CNY  before chunk 1
    214.94 CNY  after 179 cloud calls
      1.66 CNY  delta = 0.0093 CNY per call

    11 Aug   0.0070 per call
    17 Aug   0.1408 per call   <- OUTLIER, 15x the two either side
    18 Aug   0.0093 per call

**At 0.0093 per call the 1,700 call condition 2 run should have cost about 16 CNY. The balance
dropped 239.35.** Our usage cannot account for it. Yesterday's conclusion that prices had risen 15x
is withdrawn: prices did rise, confirmed from DeepSeek's docs, but 3 to 4.7x on the list, not 15x in
practice.

**Second fact pointing the same way: the balance fell 228.72 to 216.60 overnight with no calls from
us at all.** 12.12 CNY. The 11 August settlement lag was 0.28.

**Two concrete things to put to the professor**, no longer a suspicion:
1. **12 CNY left the account overnight with nothing of ours running.**
2. **A run whose own measured per-call rate says 16 CNY coincided with a 239 CNY drop.**

Ask whether the key is shared, and ask for read access to the usage page.

**Revised: run 1's cloud arm costs about 9 CNY, not the 134 quoted on 17 August.**

### Accuracy so far: 76.0%, and NOT to be acted on

237/312, **95% CI 71.2% to 80.7%**. Claims are shuffled with seed 0 so the subsample is unbiased,
but the interval covers condition 2's 77.4% comfortably. **It cannot yet distinguish beating, tying
or losing to cloud-alone.** No decision may rest on it: stopping or adjusting on a partial result is
how tuning-on-the-evaluation-set happens, and five configuration choices have already been made
against the set this paper reports.

### What to do next, in order

1. **Finish run 1.** 1,388 claims left, about 12.5 h, in whatever chunks the GPU allows.
2. **Ask the professor the two cost questions.** Free, and it is now specific.
3. **Overleaf.** Owed since 7 August. Today is 18 August, the freeze is 23 August. **Five days.**

---


## ~~What to do on 9 August, in order~~ — DONE, superseded by the 10 August list above

1. ~~**Read both condition 2 results.**~~ **DONE 9 Aug, before bed. See the section above.**
   Replaced by: **re-run pro at `max_tokens` 16,000**, about $0.35 and 35 minutes unattended.
   Five truncated numeric claims are potentially 4.9 points, and the current headline is depressed
   by a configuration choice rather than by the model. **Confirm the trim budget first**:
   32,768 − 16,000 = 16,768 against a largest observed prompt of 14,066, so no prompt should trim
   differently, but the margin is thin enough to check rather than assume.
   **This run also delivers the reproducibility measurement**, since it re-answers the same 102
   claims — verdict agreement against the first pro run is the noise floor for every cloud
   comparison in the paper. Two results, one job. Keep the first run's directory.
2. **Write `test_scripts/analyse_condition1.py`.** Rule 1 is now violated by **three** results:
   the k=10/k=20 table, the published-baseline scoring, and tonight's coder-versus-plain table.
   Make it take a list of result directories and print the comparison, so it covers all of them.

   The definitions the scratch version used, so the committed script reproduces the same numbers:
   **strict** counts `extracted_label is None` as wrong; **FINDVER-compatible** replaces `None`
   with `random.Random(0).choice([True, False])` per record, in sorted-id order so it is stable;
   **evidence_present** is the stored boolean, unmodified; **paired agreement** compares
   `extracted_label` across two directories on the intersection of example ids. Per-subset tables
   are strict accuracy only. Wall clock is the sum of `elapsed_seconds`, which excludes retrieval.
3. ~~**Prove or disprove `seed` and `temperature` on DeepSeek.**~~ **DONE 9 Aug, before bed. They
   are ignored and condition 2 is not reproducible.** See the section above. What remains is a
   decision, not a test: whether to quantify the variance by re-running a subset of condition 2,
   or to state it as a limitation and move on. **Stating it is enough for a 5-page workshop
   paper**; measuring it costs another $0.32 and buys a number nobody asked for.
4. ~~**Decide whether `qwen3:4b` is worth any more time.**~~ **DONE 9 Aug. Closed on cost.**
   The thinking build was the wrong tag; `qwen3:4b-instruct-2507-q4_K_M` was run properly and
   ties the 3B at 3.5x the latency. See the model decision section above.
5. ~~**Write `test_scripts/score_published_baselines.py`**~~ **DONE 9 Aug**, generalised over all
   16 models. Also corrected a wrong figure in §2.4.
6. ~~**Write `test_scripts/analyse_condition1.py`**~~ **DONE 9 Aug.** It now also runs an exact
   McNemar test on every pair, which found that **no accuracy comparison in the project is
   significant at n=102**, including edge versus cloud at p = 0.500. See §2.7.
7. **RUN CONDITION 1 ON ALL 700.** `configs/condition1_3b_full700.json`, `qwen2.5-coder:3b`,
   2 to 3 hours on the GPU. `run.py` now supports `per_cell: null`. **This is the highest-value
   job in the project**, because the central claim is currently a coin flip.
6. **Create the Overleaf project and share it** (§14 item 13).

### Still open, carried

- `evidence_asserter.py:83`, the `check_overflow` docstring, still says `num_ctx` 16384.
- A DHCP reservation for the brother's PC would stop the IP moving. Ten minutes in the router.
- `run.py` prints the `client` line after the blank line that ends the banner, so it sits apart
  from the block it belongs to. Cosmetic.

---

## ~~What to do on 8 August, in order~~ — DONE, superseded by the 9 August list above

**Two tracks that do not conflict — one needs the GPU, one does not.**

### Track 1, Mac, daytime, no GPU needed

1. **Build `src/deepseek_client.py`.** Mirror `ollama_client.py`: `call_deepseek(prompt, config)`
   returning the raw dict. `run.py:53` already injects `call_model` as a parameter, so no change
   to the run loop — only a config key selecting which client to use.
   **Read `content` only for extraction, never `content` plus `reasoning_content`** (§11 item 2).
   Log `reasoning_content`, `model` and `system_fingerprint`, which means adding `Record` fields
   **and updating `test_harness.py`'s 18-field assertion in the same change.**
2. **Run condition 2** (DeepSeek `deepseek-v4-pro`, single call, no pipeline, k=10, same 102
   claims). Cloud, so hours not nights. This is the second of the two ends the professor asked for
   on 30 July, and next week's meeting expects it done.
3. **Test whether `DeepSeek-V4-Flash-0731` is accepted** as a model string, so configs can pin a
   snapshot rather than a floating alias.

### Track 2, GPU session, about 40 minutes

**Check the PC's IP first** — `ipconfig` on his machine. `10.0.0.26` is DHCP-assigned and may have
changed. Every config hardcodes it.

4. `ollama pull qwen3:4b` and `ollama pull qwen2.5:3b` on his PC.
5. **Run condition 1 at k=10 on both**, ~15 min each. This settles the local model on evidence and
   **answers the professor's Coder objection with data** — `qwen2.5:3b` against
   `qwen2.5-coder:3b` holds size fixed and varies only code-tuning.

### Track 3, whenever

6. **Write the two owed scripts**, because `paper_numbers.md` rule 1 is currently violated by both
   of last night's results: `test_scripts/analyse_condition1.py` and
   `test_scripts/score_published_baselines.py`. Generalise the second over all 16 models in
   `outputs/` — the same code gives §11.8's imputation table across the whole model-size range
   instead of one point.
7. **Create the Overleaf project and share it with him** (§14 item 13).

### Still open, carried

- `evidence_asserter.py:83`, the `check_overflow` docstring, still says `num_ctx` 16384.
- A DHCP reservation for the brother's PC would stop the IP moving. Ten minutes in the router.
- ~~`docs/gpu_smoke_test.md`~~ **deleted 7 August**; content survives in the build log.

### Three things tried and rejected, all of which belong in the paper

    claim decomposition   57.53% best vs 57.88% bar, n=174    no merge beat the whole claim
    dense fusion          +0.00 untuned, n=700                beaten by k=11
    k1/b tuning           74.97% vs 74.60%, n=700             inside noise, tuned on test

Each was expected to help. Full detail and framing in §4.5 of `paper_numbers.md`.

### New document: `docs/paper_numbers.md`

Every figure that could appear in the PDF, with what it measures, its `n`, the script that
regenerates it, and **what it may legitimately sit beside**. Also carries a closing list of
claims that are not yet supported, so they are not written by accident. The build log stays a
dated narrative including wrong turns; the new file is the lookup table.

**No `src/dense_retriever.py` exists and none should yet.** `embed()` and `load_index()` live
in `test_scripts/measure_dense_recall.py` deliberately, so that no pipeline code is written for
a component that may still be dropped.

**Still unanswered by the professor:** the GPU. The machine decision has a deadline of about
7 August, because condition 1 cannot be split across two machines.

## The hardware rule, decided 3 August

The GPU changes where experiments run. It does not change what the paper claims about hardware.

- Accuracy and ablations run on the GPU.
- **The MacBook is the device of record** for every latency, throughput and memory number in the paper.
- **Never print a GPU derived number under a MacBook label.** A run on the 4090 cannot produce a MacBook runtime, and substituting one would be fabricated data. This was considered explicitly and rejected.
- **Never mix machines inside one results table.** Temperature 0 does not guarantee identical tokens across CPU and CUDA. If one configuration moves to the server, everything it is compared against moves too. The 2 August trial numbers are MacBook only.
- Keep the edge model at **8B or below** whatever the VRAM allows.

**3B stays the paper's primary model. 7B is a row, not a switch.** A bigger model eats the contribution, because the pipeline's delta is largest where the base model is weakest. If 7B handles the arithmetic unaided, the ablation shows less.

**Budget one MacBook night at the end**, after the pipeline is frozen, to measure the final configuration's per example latency and peak RAM on the real device. That run doubles as the accuracy portability check, confirming verdicts reproduce off CUDA.

**Added 4 August: cached model outputs used as pipeline inputs are not covered by the mixing rule.** The rule above is about measured numbers. Claim decomposition (§4.4, assigned to the edge 3B) produces sub-claims that are then used as retrieval queries, and retrieval recall is scored by comparing element ids against gold, with no timing and no model-accuracy claim in it. So generating decompositions on the server and scoring recall from them does not mix machines in any table. The same holds for the embedding index.

Two places it does bite. **The final MacBook latency night must run decomposition on the MacBook**, or the pipeline latency figure silently omits a real pipeline step. And **temperature 0 does not guarantee identical tokens across CPU and CUDA**, so sub-claims generated on the server may not regenerate byte-identically here. A recall number measured from them is therefore reproducible from the cached file, not from a re-run on a different machine. Cache the sub-claims to disk and treat that file as the artifact of record.

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

**No new speed workstream.** ~~Prompt size is the only real lever on wall clock, and tighter retrieval cuts runtime and raises recall together.~~ **The premise is false on the GPU box, corrected 14 August: prompt tokens are ~107x cheaper there and generation is 70 to 85 percent of wall clock. Tighter retrieval buys recall and almost no wall clock on that machine. The conclusion, no separate speed workstream, still holds, but not for this reason.** The retriever is the speed work. A separate effort would compete for the same nights and buy the same thing twice.

**This does not replace the core.** Retrieval recall and the extraction and imputation analysis are still the two results that carry the paper, **joined 14 August by the evidence-presence finding, which is now measured in both directions and gets its own section**. Deployment cost is a supporting leg.

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

~~The FINDVER leaderboard check and the citation sweep. Neither has been done, and both are
needed before repeating any claim that nobody has attempted something.~~ **Both done 3 August,
see the section above and §6.6 of the plan.** There is no leaderboard to check, and email
submission was retired in July 2026. The sweep covered 23 citing papers and **MACE is the only
published method found evaluated on FINDVER.** It was abstract-level screening, so the supportable
phrasing is **"we found no other method evaluated on FINDVER"**, never "nobody has."

## Outstanding, not yet done

~~Decide the two cloud models and the two added edge models before 3 August.~~ **Cloud closed 7 August.** Both cloud models are DeepSeek: `deepseek-v4-pro` and `deepseek-v4-flash`. The key is verified live. Anthropic is out because he cannot pay for it from China, not on merit. **Edge is still open**, reopened by him on 7 August over whether a Coder model suits reading comprehension. Open question 7 is closed; open question 8 is open.

~~Answer open question 11: what faster machine is available, with what specs, and when.~~ **Answered 7 August, and the answer is no.** Several dozen RTX 4090 units exist but are LAN-only with no public IP, and access will not happen before the deadline. The brother's desktop is the only remaining path to Band B and is untested.

~~**Reply to him.**~~ **Superseded by the 7 August meeting**, which answered the hardware, the cloud models and the Anthropic question, and handed the local model question back to us.

~~**Raise the open question 8 contradiction with him.**~~ **Downgraded 7 August, not raised.** The Llama-3.2-3B comparison is not controlled: upstream ran temperature 1.0, a 1024-token cap, a retriever at 65.16% recall against our 74.60%, and `gpt-4o-mini` extraction with an unseeded coin flip. "Same model" holds one variable fixed while four move. **Condition 1 against condition 4 holds everything fixed** and is strictly better evidence, at n=102, without the 700 run. The published Llama number is free from disk as historical context either way. Not a live tension.

**MACE's accuracy number is not written down anywhere.** Section 6.1 records its weaknesses and the 27 to 92B scaling remark, but not the headline figure. Section 5.3 states our contribution as matching the all big model design and section 9.2 builds condition 3 to compare against it, so the number we are trying to match is currently unknown. Pull it from arXiv 2604.17225. Related: since the project is RAG only, the comparable Claude-3.5-Sonnet figure is **75.0% RAG, not 77.2% long context**. MACE's recall of 67.91% is not a target, it is FINDVER's own setup copied unchanged.

**Three latency quantities are not measured and must be, before writing.**

1. 7B latency on the MacBook. The 11 m 46 s figure is one week 1 example and recollection. Re-measure it or label it an estimate.
2. Pipeline latency as opposed to baseline latency. The measured 7.0 min is `baseline_v1` with the placeholder retriever at k=10, no code execution, no table parsing, no cloud round trip. The finished system is a different number. This gap exists whether or not a GPU is involved, because the system does not exist yet.
3. Cloud round trip latency. Calls per example times API latency. Entirely unmeasured, no key used yet.

All three are covered by the one MacBook night budgeted at the end, after the pipeline freezes.

~~Confirm the workshop mechanics.~~ **Done 1 August, from the workshop site rather than the professor.** It is a NeurIPS 2026 workshop in Sydney, 11 or 12 December. Five pages excluding references, NeurIPS 2026 LaTeX template, submitted through OpenReview. Review is **double blind**, so no author names and no identifying repository link in the PDF. The venue is **non archival**, so a fuller version can go elsewhere later and this paper does not have to be the final word. Deadline 29 August AoE. Full table in section 1.1 of the plan.

## Measured performance, for planning purposes

**MACBOOK ONLY. Corrected 14 August, see "Where things stand, 14 August" above.** Everything in this section describes CPU-only inference on the MacBook. On the GPU box the coefficient is 0.00060 s per prompt token, **107x smaller**, plus a 4.6 s fixed generation cost per claim, so generation dominates and prompt size is nearly free. **Do not plan a GPU run with anything below.**

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
