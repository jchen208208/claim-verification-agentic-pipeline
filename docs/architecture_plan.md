# FINDVER Claim Verification Project — Complete Plan & Reference Document

**Project:** An edge-cloud LLM agent with purpose-built skills for verifying financial claims against long, hybrid-content documents (FINDVER benchmark)

**Status:** Week 1 complete. Repo cloned and data structure confirmed. Ollama installed; Qwen2.5-Coder-3B and 7B benchmarked on real FINDVER examples with measured throughput. Architecture agreed: local-first (Ollama + Qwen2.5-Coder-3B) with cloud escalation (Qwen/DeepSeek, professor-provided), RAG-only. **Next:** second meeting (Wed/Thu Beijing time), then Tier 0 baseline.

> **What changed in this revision.** Sections marked **[MEASURED]** replace earlier assumptions with real numbers from week-1 testing. Sections marked **[RESOLVED]** close questions the previous version left open. Sections marked **[NEW]** did not exist before and mostly capture traps discovered by running the code rather than planning it. The architecture and contribution story are unchanged; the engineering detail underneath them is now grounded.

---

## 1. Project Overview

Unverified claims about companies' financial performance circulate online and can mislead investors. Verifying such claims requires checking them against primary sources — SEC filings such as 10-K (annual) and 10-Q (quarterly) reports. These documents are long (~41,000 words on average), dense, and *hybrid*: narrative text interleaved with ~79 tables per document.

The FINDVER benchmark (Zhao et al., EMNLP 2024, Yale NLP) tests whether LLMs can (1) classify a claim as **entailed** or **refuted** by a given financial document, and (2) generate a step-by-step **explanation** of the reasoning. At publication, the best model (Claude-3.5-Sonnet) reached **77.2%** accuracy versus **93.3%** for human financial experts (CFA holders) — a large gap.

**Our approach:** a cloud-edge collaborative agent. A small, free, locally-run model (Qwen2.5-Coder-3B via Ollama) executes the bulk of simple, mechanical subtasks; paid cloud APIs (Qwen, DeepSeek) handle the small fraction of judgment-heavy subtasks; and a surprising amount of the pipeline is plain Python with no model at all. The agent orchestrates purpose-built *skills* — structured table querying, code execution, decomposed retrieval, a finance glossary, a faithfulness verifier — each targeting a named failure category from FINDVER's own error analysis.

**Two research questions, in order of interest:**
1. Can a cheap local model with targeted cloud escalation match a cloud-only system at a fraction of the cost? (The professor's core motivation and the most deployment-realistic framing.)
2. How much of FINDVER's human-LLM gap do the skills close, and which skill fixes which error category? (The ablation story.)

### 1.1 **[SETTLED 30 Jul 2026]** The deliverable

A **5-page workshop paper**, submitted to *On-Device Intelligence: Foundation Models under Real-World Constraints*. Confirmed with the professor at the 30 July meeting (§14 item 9); this closes what was Open Question 4.

**[EXTENDED 29 Aug 2026, verified on OpenReview and on odi2026.github.io] The deadline is now 5 September 2026, 23:59 AoE.** A seven-day extension. The workshop site shows the old date struck through with the word EXTENDED. Review runs 6 to 19 September. One item on the site had never been recorded: **in-person attendance is expected**, at least one author in Sydney.

**[CORRECTED 1 Aug 2026 from the workshop site, odi2026.github.io] The deadline is 29 August, not 30.** Superseded by the extension above and kept for the record. Mechanics read directly from the call for papers, which closes Open Question 10 (§13):

| | |
|---|---|
| Venue | **NeurIPS 2026 workshop**, Sydney, Australia, 11/12 December 2026 |
| **Deadline** | **5 September 2026, 23:59 AoE** = **04:59 PDT on 6 September** = 19:59 Beijing, 6 Sept |
| ~~Deadline, original~~ | ~~29 August 2026, 23:59 AoE~~ extended 29 Aug |
| Review period | 6 to 19 September 2026 |
| Attendance | **In person expected**, at least one author in Sydney |
| Length | **5 pages excluding references** |
| Template | **NeurIPS 2026 LaTeX template** |
| Review | **Double-blind** |
| Archival | **Non-archival** |
| Submission | OpenReview |
| Notification | 29 September 2026 |
| Contact | odi.neurips2026@gmail.com |

Four consequences, in order of how much they change:

1. ~~**One day is gone from Phase 5.**~~ **[SUPERSEDED 29 Aug 2026 by the extension.]** The writing window now runs to 5 September AoE. The original text: every plan document said 30 August, the writing window is 24 to 29 August, six days not seven, and the AoE clock gives until 04:59 PDT on the 30th, which is upload buffer and not a working day. **Every date in §12 below is pre-extension and has not been rewritten.**
2. **Double-blind changes how the paper is written, not only how it is formatted.** No author names, no "our earlier work", and the repository link must be anonymised or withheld. Worth knowing now rather than during the final edit.
3. **Non-archival means this does not burn the work.** A fuller version can go to an archival venue later, so the paper does not need to be the final word on the project. That lowers the pressure on Band B (§12.3) landing in time.
4. **It is a NeurIPS workshop**, which the plan had recorded only as "a workshop in Australia". The organisers are from ETH Zurich, MPI for Intelligent Systems, and MIT.

**Topic fit, from the call for papers.** Topic 05, "Benchmarks and Evaluation for Interactive Real-World Deployment", asks for *metrics that jointly assess performance, latency, energy, memory, safety, and reliability under realistic deployment conditions*. The extraction and imputation analysis (§11.8) is squarely that: a benchmark's official scoring silently imputing a large share of a small model's reported accuracy. Topic 02, "Efficient Adaptation, Inference and Reasoning under Real-World Constraints", covers the edge-cloud pipeline itself. Both should be named in the submission.

**Authorship:** student is first author. The professor is a co-author, and he will recruit roughly two industry co-authors to strengthen the author list.

Two consequences that reach into every other section:

- **The schedule is 30 days, not eight weeks.** §12 has been replanned around this. Tiers 2 through 5 and the full 700-example run are out of scope.
- **The venue determines what counts as a contribution.** A workshop on on-device models under real-world constraints rewards findings about small-model behaviour under deployment constraints. That is a better fit for what is measurable in 30 days than a long ablation chain, and it makes the extraction and imputation analysis (§11.8) a candidate headline result rather than an engineering footnote.

---

## 2. The FINDVER Benchmark

### 2.1 Task formulation
Given a financial document *d* (text *P* + tables *T*) and a claim *c*:
1. **Entailment classification:** label ∈ {entailed, refuted} — binary, no "not enough info" class.
2. **Reasoning-process explanation:** a natural-language explanation grounded solely in the document.

### 2.2 Three subsets
| Subset | Internal name | Skill tested |
|---|---|---|
| **FDV-IE** (information extraction) | `ie` | Locating facts across text + tables in a long document |
| **FDV-MATH** (numerical reasoning) | `numeric` | Calculations/statistical analysis over document data |
| **FDV-KNOW** (knowledge-intensive) | `knowledge` | Applying external finance knowledge/regulations |

Note the subset strings in the JSON are `ie` / `numeric` / `knowledge`, not the paper's display names — filter on these.

### 2.3 **[RESOLVED]** The real data structure

Repo: `github.com/yilunzhao/FinDVer`. Clone the whole thing — it also ships the authors' own `retriever/`, `run_llm.py`, `evaluation.py`, and `outputs/`, which means our numbers can be compared against *their exact baseline implementation* rather than our reimplementation of it. That is worth more than it sounds: it removes "maybe your baseline was just weaker" as a reviewer objection.

**Claim records** (`data/testmini.json`, `data/test.json`) — actual field names, confirmed:

| Field | Type | Notes |
|---|---|---|
| `example_id` | str | e.g. `"ie-val-0"`, `"numeric-val-42"` |
| `subset` | str | `ie` / `numeric` / `knowledge` |
| `split` | str | `testmini` / `test` |
| `statement` | str | The claim to verify (**not** "claim") |
| `explanation` | str | Gold reasoning. **Spelled `explaination` in the `numeric` subset** — handle both keys |
| `entailment_label` | **bool** | `true` = entailed, `false` = refuted (not a string) |
| `relevant_context` | list[int] | Gold evidence indices (**not** "evidence") |
| `report` | str | Filename, e.g. `"NJR-2024-02-06_10-Q.json"` (**not** "doc_id") |

**Numeric subset ships two extra fields** — see §2.5, this matters more than it first appears.

**Report files** (`financial_reports/<report>.json`):

```
{
  "url":         str,
  "report_type": str,
  "context":     [ {"id": 0, "context": "..."}, ... ]   # ~304 chunks in the sample doc
  "html_tables": [ "<table>...</table>", ... ]          # ~83 tables in the sample doc
}
```

Two things to internalise:
- Each `context` element is a **dict with three keys: `id`, `context`, and `type`** — not a bare string. `type` is `"paragraph"` or `"table"` (measured across 60 reports: 10,988 vs 2,349, so ~18% tables). This is free, pre-annotated table detection — it should feed the Table Normalizer (§7.1) and table-aware chunk metadata (§8) rather than being rediscovered by parsing. A loader that assumes strings will silently produce garbage (this actually happened; see §11.9).
- Tables appear **twice**: rendered as pipe-delimited text inline in `context`, *and* separately as raw HTML in `html_tables`. The gold `relevant_context` indices point into `context`. So the pipe-delimited version is what a naive pipeline sees, and `html_tables` is the higher-fidelity source our Table Normalizer should prefer (§7.1).

### 2.4 **[NEW]** The label-ordering trap — read this before sampling anything

**The examples are grouped by label in solid contiguous blocks, and the direction is not consistent across subsets.** Verified by counting run lengths in file order:

| file | block order |
|---|---|
| `testmini.json` | `ie` False ×125, True ×125 · `numeric` False ×125, True ×125 · `knowledge` **True ×100, False ×100** |
| `test.json` | `ie` False ×300, True ×300 · `numeric` **True ×300, False ×300** · `knowledge` False ×249, True ×251 |

So `knowledge` in testmini leads with *entailed*, and `numeric` in test leads with *entailed*. Do not rely on "refuted comes first."

Consequence: **taking the first *N* examples gives a single-label sample**, on which a model that always answers that label scores 100%. This would have silently invalidated every baseline number. Every sample must be stratified by (subset × label) or shuffled with a fixed seed, and the sampling function should assert the resulting label balance before any run starts.

### 2.5 **[NEW]** The numeric subset ships gold Python — three consequences

Every `numeric` record includes:

```json
"python_calculation": "def calculate():\n    total_interest_paid = 183479\n    capitalized_interest = 2483\n    return total_interest_paid - capitalized_interest",
"execution_result": 180996
```

The annotators wrote and executed real Python for every numerical claim. This is useful three separate ways:

1. **It is third-party evidence for Pillar 2.** The benchmark's own creators concluded these claims are verified by *running code*, not by generating digits. We are not proposing an exotic technique; we are implementing the one the annotation process itself used.
2. **It gives a free intermediate evaluation signal.** We can compare our agent's *computed value* against `execution_result`, not just its final label. That cleanly separates "extracted the right numbers and applied the right operation" from "reached the right verdict" — which is exactly the extraction-vs-computation distinction the ablation needs, and it is otherwise expensive to measure.
3. **It supplies a ready-made output format.** The gold explanations follow a fixed template — numbered extraction steps, then `"We can calculate X as ... = Y"`, then `"Therefore, the statement is refuted."` Our generation prompts should imitate this rather than inventing a format.

### 2.6 Key statistics and original results

> **The released files do not match the paper's stated counts. Counted directly from the clone at commit `e8bb237`:**
>
> | | paper says | `data/*.json` actually contains |
> |---|---|---|
> | testmini | 600 (200/subset) | **700** — ie 250, numeric 250, knowledge 200 |
> | test | 1,500 (500/subset) | **1,700** — ie 600, numeric 600, knowledge 500 |
> | test labels | withheld, leaderboard only | **present and balanced** (851 True / 849 False) |
> | filings | 523 | **600 files** on disk; 539 distinct ones actually referenced (255 by testmini, 439 by test) |
>
> Note that 700 + 1,700 = 2,400, which is exactly the paper's stated total, whereas the paper's own split figures sum to 2,100. That points to the released files being correct and the paper's per-split numbers being wrong, rather than us reading a different release.
>
> **[CORROBORATED 3 Aug 2026 by a second research group.]** MACE's Table 2 lists FinDVer as **Testmini 700 claims / 517 tables** and **Test 1,700 claims / 1,262 tables**. They counted the released data rather than repeating the paper's stated 600/1,500. Two independent counts now agree, so this correction can be stated with confidence rather than hedged as "our count differs from the paper."
>
> The test-label finding is the consequential one: we can score the test split locally instead of depending on the leaderboard. Confirm on the leaderboard page before relying on it, since local test numbers are not officially comparable to published ones.

- 523 filings, 2,400 claims per the paper: **testmini** 600 (200/subset, fully labelled) and **test** 1,500 (labels withheld; leaderboard only). See the correction box above for what shipped.
- Documents first released Jan–Apr 2024, chosen to post-date 2024-era training cutoffs. That protection has expired for 2026 models — see §10, Plan C.
- ~66–71% of claims require table evidence.
- Refuted claims were made by expert perturbation of entailed claims, so the error is directly contradicted by annotated evidence.
- Best 2024 results (testmini): Claude-3.5-Sonnet 77.2% long-context / 75.0% RAG; GPT-4o 75.7 / 73.7. Human expert 93.3%; non-expert 86.7%; random 50%.

  **[TRANSCRIBED FROM TABLE 4 BY EYE, 3 Aug 2026 — the per-subset breakdown, which this document previously lacked.]** Screenshot kept at `docs/findver_baseline_accuracy.png`. Caption: *"Accuracy of entailment classification on the testmini set of FINDVER. We report results for LLMs with CoT prompting under the long-context (LongC) and RAG settings."*

  | Model | FDV-IE L/R | FDV-MATH L/R | FDV-KNOW L/R | **Avg L/R** |
  |---|---|---|---|---|
  | Random Choice | 50.0 | 50.0 | 50.0 | **50.0** |
  | Human Non-Expert | 90.0 | 85.0 | 85.0 | **86.7** |
  | Human Expert | 95.0 | 90.0 | 95.0 | **93.3** |
  | Gemini-1.5-Flash | 71.0 / 70.5 | 62.5 / 60.5 | 65.0 / 65.5 | **66.2 / 65.5** |
  | GPT-3.5-turbo | – / 79.0 | – / 64.0 | – / 70.5 | **– / 71.2** |
  | GPT-4o | 80.0 / 78.5 | 70.5 / 68.0 | 76.5 / 74.5 | **75.7 / 73.7** |
  | Claude-3.5-Sonnet | 83.5 / 80.5 | 71.0 / 69.0 | 77.0 / 75.5 | **77.2 / 75.0** |

  Open-source rows run from InternLM2-Math-7b at 55.3 average RAG up to Mixtral-8x22B at 66.3, with most mid-size models clustered in the 56–60 band and only Qwen2-72B (64.9) and Mixtral-8x22B (66.3) clearing 64. Most open-source rows report RAG only, with a dash under long-context.

  **[NEW MOTIVATION FOR TIER 1, and the strongest one available.] FDV-MATH is where the best model collapses.** Claude-3.5-Sonnet under RAG scores **80.5 on FDV-IE, 75.5 on FDV-KNOW, and 69.0 on FDV-MATH** — an 11.5-point gap between its easiest and hardest subset. The numeric subset is the frontier model's weakest, and it is exactly what Tier 1's code execution targets (§8, §7.2). Until now Tier 1 was motivated by the benchmark's error taxonomy and by our own trial-run arithmetic failure (§4.6). This is a third and harder-to-argue-with motivation: a published number showing the gap is largest precisely where we intervene.
- **Long-context beat RAG for strong models; RAG beat long-context for weak models.** Our 3B-class local setting sits firmly in the second camp — one more reason the pipeline is RAG-only.
- Chain-of-Thought adds ~5–7 points over direct labelling → all baselines use CoT.
- **The error taxonomy** (authors' manual analysis of Claude-3.5-Sonnet failures) — our organising instrument throughout:
  1. **Extraction error** — wrong/missed information pulled from context
  2. **Numerical reasoning error** — wrong mathematical approach
  3. **Domain knowledge deficiency** — missing finance knowledge
  4. **Computation error** — right reasoning, wrong arithmetic

---

## 3. Core Concepts (plain-language reference)

### 3.1 What an LLM call actually is — and why the model never "accesses" anything
An LLM API call is: send a string, receive a string. The model has no filesystem, no notion of `report`, no ability to open a document. **Every join between claim and document happens in our Python script, before any model runs:**

```python
example  = json.load(open("data/testmini.json"))[0]
report   = json.load(open(f"financial_reports/{example['report']}"))
selected = my_retriever(example["statement"], report["context"])   # RAG logic lives here
prompt   = build_prompt(example["statement"], selected)            # one big string
response = call_llm(prompt)                                        # only now does a model see anything
```

Consequences worth internalising:
- **RAG vs. long-context** is just what `selected` contains.
- **The recall ceiling (§3.4)** happens in *our script*: if the retriever misses the table, it is simply not in the prompt, and the model cannot verify a number it was never shown.
- **"Agent"** = this loop run repeatedly: send prompt → read reply → detect that the model wrote code or needs more evidence → run the code / fetch chunks in plain Python → build a new prompt containing prior context + new results → send again. The model *feels like* it is using tools; mechanically, the script is a middleman assembling strings.

### 3.2 LLM agent and LLM skill
- **Agent:** a system where the model's outputs steer, in a loop, which action happens next. For a fixed pipeline like ours, an agent is a Python script with several differently-prompted LLM calls and branching between them.
- **Skill:** a packaged, reusable capability — instructions plus optionally scripts/reference data — that makes a model reliably good at one procedure. Each pipeline module here is framed as a skill the agent orchestrates. This matches the professor's own "agents and skills" language.
- **Multi-agent (MACE-style)** = multiple *roles* (Planner/Executor/Verifier), each a system prompt plus a position in the loop. *Which model plays which role* is an independent design axis — see §5.

### 3.3 RAG — and why this project is RAG-only
**Decision (professor's explicit guidance): the pipeline is RAG-only.** Even if a full document technically *fits* in a small model's context window, that does not mean the model can *effectively use* information tens of thousands of tokens back. Fitting ≠ using. **[MEASURED]** Week-1 timings make this concrete in a second way: a ~4,000-token prompt already costs 3.5 minutes of ingestion on the 3B model (§4.6). A 41,000-token document would cost roughly ten times that per example — long-context is not merely inadvisable here, it is computationally out of reach on this hardware.

### 3.4 Recall and the recall ceiling
**Evidence recall** = of the gold evidence pieces a claim needs, what fraction did retrieval actually fetch? The published FINDVER setup (OpenAI text-embedding-3, k=10) achieves only **~68–70%** (67.91% testmini / 69.53% test, per MACE). Every published approach copied this setup rather than improving it. Because gold indices exist, retrieval can be improved and measured **in isolation, almost for free** — no LLM calls, just set comparisons — making "we raised recall from 68% to X%" a clean, self-contained reportable result that costs nothing in compute.

**[FACT-CHECKED 2 Aug 2026, and this section was wrong] The published number is a macro-average, and the "3 in 10 claims" gloss that used to sit here does not follow from it.** `FinDVer/retriever/recall_evaluation.py` computes `mean over claims of (matched / needed)`, i.e. the average *per-claim fraction*, not the fraction of claims that got everything. Those differ a lot when a claim needs several elements, and FINDVER claims need 2.8 on average (ie 3.04, knowledge 3.66, numeric 1.87). Recomputed directly from upstream's own shipped retrieval output in `outputs/testmini_outputs/retriever_output/`, all 700 testmini claims, three metrics side by side:

| retriever, k=10 | macro-avg (their metric) | element recall | **all-gold** |
|---|---|---|---|
| `text-embedding-3-large` | **68.01%** | 62.4% | **42.6%** |
| `bm25` | 65.16% | 62.8% | 38.6% |
| `contriever-msmarco` | 33.48% | 28.4% | 16.3% |
| ours, token overlap (§7.3 placeholder) | 57.54% | 53.2% | 31.6% |

Our 68.01% reproduces the cited 67.91% to within rounding, so the published figure is sound; only the interpretation was wrong. **The real claim-level statement is that for 57.4% of claims, not 30%, at least one required piece of evidence never reaches the model.** That is close to six claims in ten, and it makes the ceiling argument stronger rather than weaker. Any sentence in the paper about the ceiling should use the all-gold figure or name the metric explicitly, because "68% recall" reads as "68% of claims are fine" and that is not what it means.

**Reporting rule, decided 2 Aug.** Every recall number in the paper is reported on all three metrics, and each has one job. **Macro-average** is the comparability number: it is what upstream computes, so it is the only one that may sit in a table beside a published figure. **Element recall** is the honest retrieval measurement, since it weights every piece of evidence equally instead of favouring claims that need fewer. **All-gold** is the ceiling number, because it answers the question the ceiling argument actually asks, namely how often the model could not possibly have got it right. This mirrors the two-scorings decision for accuracy in §9: one number exists for comparison, another for truth, and mixing them silently is the failure to avoid.

**[CLARIFIED 3 Aug 2026] The ceiling is inherited, not inherent, and this distinction is the whole opportunity.** 68.01% is a property of **one configuration**: `text-embedding-3-large`, k=10, one `context` element per chunk. It is not a property of FINDVER. The evidence that it is configuration-dependent is in this section already: the same retriever drops to 54.53% at k=5 and 43.60% at k=3, and a free BM25 lands within three points at k=10.

The number has stayed at ~68% across the literature because **nobody changed the retriever**, not because 68% is hard to exceed. MACE is explicit about this: §6.1 Weakness 2 records that they state retrieval "is not our focus" and report FINDVER's own 67.91% / 69.53% unchanged. If the ceiling were a hard property of the data there would be nothing here to attack, and Tier 2 would not be the project's core (§3.3).

**Honesty caveat.** "Every published approach copied this setup" is verified for MACE, who say so in their own words. It is **not** verified generally. ~~because the leaderboard check and the citation sweep are still outstanding (§6.6, note 2). Until those are done,~~ **[UPDATED 3 Aug 2026: both are done, and the caveat survives them.]** The sweep found MACE is the only published method evaluated on FINDVER, but it was abstract-level screening across 23 citing papers rather than a full-text sweep (§6.6, note 2). So the limit is now the sweep's depth rather than its absence. Write "MACE copied it and reported the ceiling unchanged" rather than "every approach copied it."

**Two further findings from the same recomputation.** First, **BM25 reaches 65.16% against the paid embedding's 68.01%, and beats it on element recall (62.8% vs 62.4%)**. A free, local, dependency-light retriever is within three points of `text-embedding-3-large` on the metric the paper reports. For an on-device paper that is a result in itself, and it means the hybrid of §7.3 starts from a strong free baseline rather than needing an embedding API. Second, k dominates: `text-embedding-3-large` drops from 68.01% at k=10 to 54.53% at k=5 and 43.60% at k=3, so the k sweep is not a formality.

**[BUILT 4 Aug 2026] `test_scripts/measure_recall.py` is the instrument for everything in this section.** It takes one dict, `example_id -> list of element ids`, and reports all three metrics overall and per subset, so upstream's shipped rankings, our own BM25, a fusion and a reranker are all scored by identical code. No model calls; the whole script runs in seconds. It asserts the three figures above at k=10 and prints `SCORER IS WRONG, do not use` on any mismatch, so it cannot drift silently and corrupt every retrieval decision downstream. All figures below were produced by it.

One bookkeeping note. It counts **1,959 gold elements where §11 item 9 counts 1,964**. Five claims repeat an index in `relevant_context` (`numeric-val-36` is `(24, 24)`, `ie-val-193` is `(7, 8, 7)`). Deduplicating is correct for recall, since retrieving element 24 once satisfies that claim and counting it as "needed 2, matched 1" would cap the claim at 50% unreachably. Upstream deduplicates identically, at `recall_evaluation.py` line 15. Both counts are right for their own job: 1,964 raw for the asserter, which walks gold elements including repeats, and 1,959 deduplicated for recall.

**[MEASURED 4 Aug 2026] Per subset, `text-embedding-3-large` at k=10. Retrieval is strongest where the models are weakest.**

| subset | macro | element | all-gold |
|---|---|---|---|
| FDV-IE | 63.57% | 58.2% | 33.2% |
| FDV-MATH (`numeric`) | 79.17% | 79.0% | 66.8% |
| FDV-KNOW (`knowledge`) | 59.61% | 56.1% | 24.0% |

Set against FINDVER's Table 4, where Claude-3.5-Sonnet under RAG scores 69.0 on FDV-MATH and 75.5 on FDV-KNOW, this separates the two failure modes cleanly and maps them onto the two tiers. **FDV-MATH is the subset where retrieval works best (79.0% element) and the best model still scores worst**, so its difficulty is arithmetic rather than evidence supply, which is the Tier 1 argument. **FDV-KNOW is the subset where retrieval works worst (56.1% element, 24.0% all-gold)**, so a quarter of those claims could possibly be answered for the right reason, which is the Tier 2 argument. Caveat on the all-gold column: numeric claims need 1.87 elements on average against knowledge's 3.66, so all-gold structurally flatters numeric. The gap survives on element recall, which does not have that bias.

**[MEASURED 4 Aug 2026] BM25 and `text-embedding-3` are strongly complementary, and fusion captures about half of it.**

The diagnostic first, because it bounds what any fusion could achieve. Take each retriever's top 10, union the two id sets, and score the result. A merge rule can only reorder what at least one retriever already found, so the union is the ceiling.

| at k=10 | macro | element | all-gold |
|---|---|---|---|
| bm25 alone | 65.16% | 62.8% | 38.6% |
| `text-embedding-3-large` alone | 68.01% | 62.4% | 42.6% |
| **union of both (up to 20 elements)** | **80.86%** | **77.0%** | **58.9%** |

Element recall rises 14 points over either retriever alone. The two are finding substantially different evidence, which is what the lexical-versus-semantic argument predicts but had not been measured on this data. `ie-val-23` is the clean instance: gold is `[2, 3, 49]`, BM25 returns 3 and 49, the embedding returns 2 and 3, and neither alone gets the claim. Read the union as a ceiling and not a forecast, since it scores 20 candidates against 10.

Then real reciprocal rank fusion, returning exactly 10 elements so it is comparable to the single retrievers rather than to the ceiling. Each element scores `1/(60 + rank)` in each list and the scores are summed; only positions are used, because BM25 returns values near 70 and cosine similarity returns values under 1, so the two scores cannot be added. `c = 60` is the standard constant, not tuned here.

| RRF, bm25 + `text-embedding-3`, k=10 out | macro | element | all-gold |
|---|---|---|---|
| candidate pool = top 10 of each | **74.06%** | **69.0%** | **48.7%** |
| candidate pool = top 25 of each | 68.81% | 65.1% | 42.3% |
| candidate pool = top 50 of each | 69.07% | 65.4% | 42.7% |
| candidate pool = full ranking | 69.21% | 65.6% | 43.1% |

**6.05 macro points over the published 68.01%**, from two retrievers already shipped in FINDVER's own repository, with no model call and no new retrieval. That is roughly half the 12.85 points of headroom the union identified.

**A shallow candidate pool beats a deep one, which is not the obvious direction.** RRF rewards agreement between lists, so on a deep pool an element ranked 15th by both outscores an element ranked 1st by one. Truncating each list at 10 excludes the consistently-mediocre elements and lets a single retriever's strong pick survive. Convenient as well as interesting: the cheapest configuration is also the best one.

**What this does and does not license.** Hybrid BM25-plus-dense with RRF is a standard information retrieval technique with years of literature behind it; we would not be inventing it. What is unattempted is applying it **on this benchmark**, and the reason is not oversight: FINDVER's authors compared three retrievers to pick a default, which is benchmark construction, and MACE states in writing that retrieval is not their focus (§6.1). Per the citation sweep's own limits, the supportable phrasing stays "we found no other method," never "nobody has."

**This result cannot ship as our retriever.** It uses `text-embedding-3`, a paid OpenAI API for which we hold no key, and an on-device paper cannot depend on one regardless. Its job was to decide whether to pay the one-time CPU cost of a local embedding index (§11 item 11), and it decides yes.

**[DECIDED 4 Aug 2026] The retriever design, settled by the measurements above.** Two arms fused by RRF: BM25 over `context` elements, pure Python and no model; and dense retrieval with a local embedding model through Ollama, cosine similarity over a cached index. Pool of 10 per arm, `c = 60`, 10 elements out. **Chunking does not change: one `context` element is one chunk.** §7.3's requirement that tables be kept whole is already satisfied, because a table *is* a single element carrying `type: "table"` (§2.3), and keeping the mapping one-to-one is also what lets gold indices score the output directly.

Build order, each step gated on the last: our own BM25, then the embedding index with the dense arm scored alone, then the fusion.

~~validated by reproducing 65.16 exactly~~ **Wrong, corrected the same day.** Upstream's BM25 is not the same algorithm as ours and an exact match is unreachable; chasing one would mean debugging a non-bug. See the next section, which supersedes it with the achieved numbers.

~~The paper's target is beating 68.01% with a fully local, free retriever.~~ **Already met the same day, before any dense arm exists.**

### 3.4.1 **[MEASURED 4 Aug 2026] Our BM25 reaches 74.60% macro, and the gap to upstream's BM25 is fully explained**

`src/bm25_retriever.py`, scored by `test_scripts/measure_recall.py` over all 700 testmini claims at k=10:

| at k=10 | macro | element | all-gold | needs |
|---|---|---|---|---|
| **ours, bm25** | **74.60%** | **70.5%** | **50.4%** | nothing, pure Python |
| `text-embedding-3-large` | 68.01% | 62.4% | 42.6% | paid OpenAI API |
| upstream `bm25` | 65.16% | 62.8% | 38.6% | nothing |
| RRF of the two published retrievers | 74.06% | 69.0% | 48.7% | paid OpenAI API |
| ours, placeholder | 57.54% | 53.2% | 31.6% | nothing |

**A free, local, model-free retriever beats the paid embedding by 6.59 macro points**, and edges past the fusion of both published retrievers. For a paper about on-device constraints this is the strongest single result the project has produced, and it cost no compute at all.

**Why this is not a fluke, recorded in full because a 9-point jump over a published baseline is normally a bug.**

*Output shape.* Exactly 10 ids returned for all 700 claims, no duplicates within a claim, no id out of range for its report.

*No gold leakage.* `retrieve` reads `claim.statement` and `report["context"]` only. `relevant_context` is never touched on the retrieval path; it enters only inside the scorer, after retrieval has returned.

*The instrument is unchanged.* The same `aggregate` scores every row, and the three upstream rows still reproduce their 2 August figures exactly, with the script's own self-assertion passing. A scorer biased toward our retriever would have moved them.

*The setups match.* Read from `FinDVer/retriever/retriever.py`: upstream calls `prepare_context_list`, which is `[i["context"] for i in report["context"]]`, then `BM25Okapi` per report. One `context` element per chunk, corpus scoped to one report. Identical to ours, so the difference cannot be chunking or corpus scope.

*The difference is reproducible in both directions.* Applying all three of upstream's implementation choices to our own code lands at **66.72% macro against their published 65.16%**. The 1.6-point residual is the approximation of NLTK's `word_tokenize` and Porter stemming, neither of which is installed on this machine. Being able to reconstruct their number from our code is what turns "ours is better" into "ours differs for these three reasons."

**The three reasons, ablated individually.**

| variant | macro | element | all-gold |
|---|---|---|---|
| ours as written | 74.60% | 70.5% | 50.4% |
| classic IDF, no `+1`, can go negative | 72.09% | 67.5% | 47.7% |
| `rank_bm25`'s exact IDF, negatives floored at `0.25 x mean` | 73.33% | 69.4% | 48.4% |
| punctuation kept as tokens, NLTK-like | 72.58% | 68.6% | 47.3% |
| suffix stemming applied | 74.67% | 70.3% | 50.0% |
| tokenizer without inner-comma stripping | 74.78% | 70.6% | 50.9% |
| **all three upstream choices combined** | **66.72%** | **64.2%** | **40.0%** |

Two of these overturned a prediction, which is why they are recorded rather than summarised. **Stemming makes no difference** (74.67 vs 74.60), and **stripping inner commas from numbers makes no difference either** (74.78 vs 74.60) — the latter had been the leading hypothesis for our advantage and it is wrong. The effects also compound rather than sum: individually they are worth about 4.5 points, together 7.9.

**The finding worth carrying into the paper: upstream's tokenizer penalises tables.** Keeping punctuation as tokens inflates measured element length by **1.81x for tables against 1.13x for paragraphs**, because pipe-delimited table text is dense in `|`, `$`, `(`, `)` and `,`. BM25's length normalisation (`B = 0.75`) then divides table scores down disproportionately, pushing tables out of the top 10. Tables are about 18% of elements (§2.3) and carry a large share of financial evidence, so a tokenizer choice made for general text quietly suppresses exactly the evidence type this benchmark is about.

Provenance, stated accurately because it is a candidate paper sentence. The tokenizer is `src/evidence_asserter.tokenize`, written 2 August for the asserter, where the inner-comma handling was a deliberate choice for numeric tokens. Dropping punctuation was **not** chosen for retrieval reasons by anyone; it was inherited by reusing that tokenizer in BM25. What is new on 4 August is the measurement showing it matters and the mechanism explaining why. Write it as a finding, never as a designed insight.

**[MEASURED 4 Aug 2026] `k1` and `b` were swept, and the defaults are kept deliberately.**

| `k1` \ `b` | 0.00 | 0.25 | 0.50 | 0.75 | 1.00 |
|---|---|---|---|---|---|
| 0.9 | 70.37 | 72.77 | 73.95 | 74.72 | 74.91 |
| 1.2 | 70.00 | 72.84 | 73.89 | **74.97** | 74.60 |
| 1.5 | 69.56 | 72.88 | 74.42 | 74.60 | 74.68 |
| 2.0 | 69.23 | 72.84 | 74.67 | 74.69 | 74.80 |

Macro recall, all 700 claims, k=10. The best cell is `k1 = 1.2, b = 0.75` at 74.97% against the defaults' 74.60%.

**Decision: keep `k1 = 1.5, b = 0.75` and do not take the 0.37.** Eight configurations sit between 74.6 and 75.0, which at n = 700 is inside sampling noise. More seriously, the sweep ran on all 700 test claims, so taking its winner is selecting on the test set. §9 already records that the 102-example slice makes about 15% of any final number self-optimised; adopting a constant tuned on the full 700 would make it 100%. An untuned standard configuration is worth more in the paper than 0.37 points bought that way. Report the sweep as evidence the defaults are not load-bearing, not as a tuning result.

**What the sweep does show is that `b` carries the retriever and `k1` does not.** Turning length normalisation off costs about 5 points (69.56 at `b = 0` against 74.60 at 0.75), while `k1` across 0.9 to 2.0 moves under half a point. This corroborates the tokenizer finding above from an independent direction: length handling is where this retriever's accuracy lives, which is precisely why upstream's punctuation-inflated element lengths cost them so much.

One qualifier on that reading. At `b = 0`, with length normalisation entirely off and the table mechanism therefore inert, we still score 69.56% against upstream's 65.16%. So the table-length effect is a large part of our advantage but not all of it, and the IDF variant carries the remainder.

### 3.4.2 **[MEASURED 5 Aug 2026] The local dense arm: nomic is good, the fusion question is unresolved, and the slice cannot resolve it**

The 102-claim embedding index was built overnight with `test_scripts/build_embedding_index.py`: 89 reports, 20,718 elements, **137 minutes, 0 failed reports**, against a 2.5 h estimate. Vectors cached in `embeddings/`, gitignored.

Scored with `test_scripts/measure_dense_recall.py`, all rows on the same 102-claim slice at k=10:

| | macro | element | all-gold |
|---|---|---|---|
| ours, bm25 | **76.18%** | 71.0% | 53.9% |
| `nomic-embed-text` alone | 62.86% | 55.5% | 35.3% |
| RRF(bm25, nomic), equal votes | 75.57% | 70.0% | 49.0% |
| RRF(bm25 x1.1, nomic) | 76.26% | 71.0% | 52.0% |
| RRF(bm25 x1.25 and above, nomic) | 76.18% | 71.0% | 53.9% |
| **control:** RRF(bm25, `text-embedding-3`) | 76.08% | 71.0% | 53.9% |
| union, ceiling on any fusion | 83.27% | 78.6% | 61.8% |

**`nomic-embed-text` reaches 62.86%, five points below `text-embedding-3-large` and nearly twice contriever.** A free local embedding model landing that close to the paid one is a result worth a row in the paper independently of whether it is fused.

**The fusion result is not interpretable, and the control row is why.** On all 700 claims, RRF of our BM25 with `text-embedding-3` gains +2.54 macro (§3.4.1). On this 102-claim slice the same fusion gains nothing, 76.08 against 76.18. Since that fusion is known to help at full scale, a null result here measures the instrument rather than the method.

**The noise floor is the same size as the effect.** Our BM25 scores 74.60% on all 700 and 76.18% on this slice, a 1.58-point swing from sampling alone. The fusion effect under test is about 2.5 points. §9's own statement that 102 examples "cannot rank two prompts that differ by 3 points" applies exactly here.

**Recorded as a design error rather than a finding.** The slice was sized to separate 33% from 68%, a 35-point gap, which it does cleanly and which is what the contriever result made urgent. It was then used to ask whether fusion adds 2 points, a question it structurally cannot answer. The two questions needed different sample sizes and were run at one.

**A mechanical property of weighted RRF, worth knowing before tuning it.** With two lists of length k and constant `c`, a weight ratio above roughly `(c+k)/(c+1)` makes the heavier list's worst element outscore the lighter list's best, so the fusion returns the heavy list unchanged. At k=10 and c=60 that threshold is about 1.16: at weight 1.25 and above the output is our BM25 exactly, which is why those rows are identical rather than similar. Only a narrow band near 1.1 blends anything at all. Weighted RRF has a far smaller useful range than it appears to.

**Decision: keep `embeddings/`, park the dense arm, do decomposition first.** Deleting the vectors was the contriever contingency and nomic is not contriever. Finishing the index costs about 4.8 h for the remaining 166 reports, against an expected payoff of at most +2.5 points. More decisively, claim decomposition (§3.6) changes the queries for **both** arms, so any fusion settled now is invalidated by it. The order is therefore: decomposition, then BM25-plus-decomposition scored on all 700 which costs nothing, and only then the remaining index if the dense arm still looks worth it.

### 3.4.3 **[MEASURED 5 Aug 2026] Claim decomposition does not improve retrieval. Closed.**

§3.6 motivates decomposed retrieval, and §8 lists it as Tier 2 alongside hybrid retrieval. It was tested and it does not work. **The motivation in §3.6 should be read carefully: its "direct evidence this matters" is about the 7B model producing cleaner *reasoning*, not about recall.** That is a different claim and it was never evidence for decomposed retrieval.

**Test design.** Restricted to the 174 claims needing 4 or more gold elements, because that is where BM25's deficit lives:

    gold elements needed    1      2      3      4      5+
    our BM25 recall       79.8%  81.5%  78.6%  60.2%  53.6%

Recall is flat to 3 elements and collapses after. 174 claims with a 20-40 point hole is a population where a real effect shows through the noise, unlike a 2-point effect on the full set (§3.4.2).

**Cost: 36.7 minutes of 3B model time**, `prompts/decompose_v1.txt`, config `configs/decompose_v1.json`, cached to `results/decompositions_v1.json`. Mean 3.94 sub-claims per claim, 0 claims parsed to nothing, 0 errors.

**Decomposition quality was good.** Numbers, dates and entity names came through exactly, which was the main risk to BM25's exact-string matching. About a fifth of sub-claims are dependent fragments rather than self-contained facts, for example "With a $660,000 principal." Those still carry the distinctive tokens BM25 needs.

**Six merge strategies, on the 174 claims, k=10:**

| | macro | element | all-gold |
|---|---|---|---|
| **whole claim only, the bar** | **57.88%** | 56.6% | 11.5% |
| round-robin, whole + sub-claims | 56.04% | 54.3% | 10.9% |
| round-robin, whole keeps top 5 | 57.33% | 55.6% | 12.6% |
| round-robin, sub-claims only | 54.37% | 52.9% | 9.2% |
| RRF across queries | 45.27% | 44.3% | 4.0% |
| max raw BM25 score across queries | 57.53% | 56.2% | 11.5% |
| max normalised score | 56.96% | 55.2% | 9.2% |
| sum of normalised scores | 54.50% | 53.2% | 10.3% |

Nothing beats the whole claim. The baseline itself is verified: 57.88% is exactly the weighted mean of the 60.2% and 53.6% buckets above.

**A false positive was caught mid-analysis and it is worth recording.** The union of the whole claim's top 10 with every sub-claim's top 10 scores **76.14%** against 57.88%, and 101 of 174 claims contained gold that only a sub-claim found, 147 elements in total. That was read as "the information is there, only the merge is failing." **It was wrong.** The union holds 30.3 candidates against the whole claim's 10, and the correct control is the whole claim at the same budget:

    whole claim, k=30        79.37%
    decomposed union         76.14%   (mean 30.3 elements)

**At equal candidate budget, decomposition is 3.2 points worse than simply raising k.** The union's apparent advantage was entirely a k effect. Any future comparison of a multi-query retriever against a single-query one must control for candidate count, or it will produce this same illusion.

**Decision: closed for retrieval.** It costs a model call per claim, adds a component to the pipeline, and loses to a parameter change. **This does not close it for Tier 1 reasoning**, which is what §3.6's original observation was actually about, and which is a separate question measured end to end rather than on recall.

### 3.4.4 **[MEASURED 5 Aug 2026] `k` is the largest lever in retrieval, and choosing it is a four-way tradeoff**

Our BM25 over all 700 claims. Recall figures are exact; token figures use the 4.30 chars/token ratio measured directly on our own retrieved content (§3.4.5).

| k | macro | element | all-gold | est. prompt tokens |
|---|---|---|---|---|
| 5 | 62.39% | 56.9% | 34.1% | ~1,700 |
| **10** | **74.60%** | **70.5%** | **50.4%** | **~3,400** |
| 15 | 81.12% | 77.4% | 60.0% | ~5,000 |
| 20 | 84.56% | 81.7% | 66.6% | ~6,500 |
| 25 | 86.34% | 83.8% | 69.7% | ~8,000 |
| 30 | 88.51% | 86.0% | 73.3% | ~9,500 |

**k=10 to k=30 is worth 13.9 macro points.** For scale, the entire dense-fusion question was worth +2.5, and the published baseline everyone copied is 68.01%. This is by a wide margin the biggest retrieval lever found so far, and it is a parameter rather than a component.

**Four factors decide k, and only one of them is free.**

1. **Recall.** Measured, free, above. Rises monotonically with k.
2. **Ingestion cost.** k sets prompt length and prompt length is the entire cost model at R² 0.995 (§4.6). Generation barely moves: the trial run's `eval_count` ranged only 261-496 regardless of prompt size. Being measured in §3.4.5.
3. **Accuracy, and we have no data at all.** A higher k adds distractors as well as gold. Small models are not reliably good at ignoring irrelevant context, so recall may not convert to accuracy one for one, and could invert. The only evidence pointing the other way is the trial run's 4/4 correct with evidence present against 4/8 without, which is n=4 and which §9 already says not to trust. **Resolving this costs one overnight run per k value.**
4. **The deployment story, which is a paper decision rather than a measurement.** The MacBook is the device of record (§9.2 hardware rule), so whatever k is frozen, the latency reported in the paper is the MacBook figure regardless of where accuracy was measured. Doubling per-example time to buy recall weakens the exact axis §6.1 attacks MACE on, namely that their pipeline costs 2.2x to 27x more wall clock than single-pass.

**A GPU does not remove factor 4.** Accuracy and ablations may run on the server (§9.2), and a k sweep is an accuracy measurement, so that is allowed. But the deployment cost we *report* stays the MacBook number. A GPU makes the experiment affordable; it does not make the operating point cheap.

**Consequence: the honest result may be the curve rather than the maximum.** Recall against measured per-example latency across k, on the device, with a defensible operating point chosen. That is a stronger contribution than a single tuned k, it uses the R² 0.995 cost model already in hand, and it turns the cost of high k from a weakness into the finding.

**How to buy factor 3 without spending extra nights.** Do not run a standalone k experiment. **Fold it into condition 1**, the edge-only baseline §9.2 already schedules, by running that condition at two k values instead of one. Both the baseline and the k answer come out of the same work.

**One k, frozen, for everything.** §9.2 requires every condition to share the same retrieval, so k is not a per-condition knob. It is chosen once and everything downstream inherits it, which is also why it must be settled before condition 1 rather than after.

**Prompt trimming returns, for a third reason.** It was specified to prevent overflow, downgraded on 2 August when overflow did not occur, then parked behind the retriever. If the recall lives at k=20 or above, trimming is what makes that affordable. It must count tokens rather than characters, and §3.4.5 provides the ratio that makes that possible.

### 3.4.5 **[MEASURED 5 Aug 2026] Token calibration, and a live overflow defect at the current k=10**

Six real calls, `num_predict=1` so only ingestion is paid, `num_ctx` 32768 so nothing could evict during the measurement itself. This is the first clean separation of ingestion from generation; the 2 August fit rejected it as degenerate because `eval_count` barely varied.

| claim | k | chars | tokens | chars/token | seconds | tok/s |
|---|---|---|---|---|---|---|
| knowledge-val-51 | 10 | 8,002 | 1,880 | 4.26 | 81.1 | 23.2 |
| knowledge-val-51 | 30 | 26,231 | 6,043 | 4.34 | 306.5 | 19.7 |
| knowledge-val-178 | 10 | 22,907 | 5,165 | 4.44 | 300.1 | 17.2 |
| knowledge-val-178 | 30 | 53,051 | 12,635 | 4.20 | 672.5 | 18.8 |
| numeric-val-30 | 10 | 41,355 | 12,480 | **3.31** | 974.1 | 12.8 |
| numeric-val-30 | 30 | 82,932 | 24,400 | **3.40** | 1,505.5 | 16.2 |

**Measured ingestion is 12.8 to 23.2 tok/s, mean about 16.** The 15.6 tok/s "implied ingestion rate" recorded on 2 August came from total elapsed time and absorbed generation, so it was not a true ingestion figure. This is.

**The chars-per-token ratio is not a constant and must not be used as one.** 3.31 on table-heavy numeric content against 4.44 on prose, a 34% spread. §2's trial-run note already said a character budget is not a safe proxy for a token budget; this confirms it on our own retriever's output. Any trimming logic counts tokens.

**The defect: the configuration we were about to run baselines on already overflows.** Prompt-token distribution across all 700 claims, using the conservative 3.31 ratio because the tail is exactly where table-heavy content lives:

| k | mean | p90 | max | over 14,384 (`num_ctx` 16384) | over 30,768 (`num_ctx` 32768) |
|---|---|---|---|---|---|
| **10** | 4,426 | 9,490 | 19,466 | **15/700** | 0/700 |
| 15 | 6,472 | 13,627 | 29,589 | 62/700 | 0/700 |
| 20 | 8,454 | 17,734 | 36,544 | 104/700 | 6/700 |
| 25 | 10,427 | 22,326 | 43,139 | 120/700 | 25/700 |
| 30 | 12,328 | 26,885 | 52,241 | 139/700 | 53/700 |

**About 15 of 700 claims overflow at the current k=10 with `num_ctx` 16384 and `num_predict` 2000.** This is not a consequence of raising k. It was never caught because the trial run was 12 examples, and §11 item 9 already records that the overflow alarm has never fired on real data. Given that Ollama 0.12.3 evicts the oldest prompt tokens silently while reporting `done_reason: "stop"`, those examples would return confident answers over evidence that had scrolled out of view, with nothing in the output to show it.

**Three consequences.**

1. **Prompt trimming is mandatory, not an optimisation.** Fourth appearance: specified for overflow prevention, downgraded 2 August when overflow did not occur in 12 examples, reframed as wall-clock optimisation, and now correctness again with a measurement behind it. It must count tokens.
2. **k=30 is unreachable.** 53 of 700 claims exceed even `num_ctx` 32768. **k=20 is the practical ceiling**, and it requires trimming plus a larger window. This settles the high candidate for the k experiment: 20, not 30, and k=20 already captures 10.0 of the 13.9 available points.
3. **A larger `num_ctx` is necessary but not sufficient.** 32768 costs 4.4 GB against 16 GB physical (§4.3) and buys the k=15 row outright, but leaves 6 claims over at k=20 and 53 at k=30.

**One incidental positive.** Tables are a mean of 6.5 of the top 30 retrieved, against an 18% base rate in the corpus, so our BM25 slightly over-retrieves tables. That is the length-normalisation property of §3.4.1 appearing a third time, and it is the right direction for a benchmark whose evidence is table-heavy.

### 3.4.6 **[CORRECTED 5 Aug 2026] Retriever freeze order: fusion is decided before condition 1, not after**

An earlier plan this session was to decide k through condition 1 and settle the dense arm afterwards. **That is invalid.** §9.2 requires every condition to share the same retrieval, and "change retrieval and all four move." Condition 1 freezes the retriever, so adding a dense arm afterwards forces a re-run.

The circularity resolves because the two questions need different evidence:

- **Fusion or no fusion is a retriever choice and is decided on recall, which is free.** Fusion changes *which* k chunks are retrieved, not how many, so the distractor argument does not apply and no end-to-end run is warranted.
- **k is decided on recall and accuracy**, because k is precisely the knob trading gold evidence against distractors. That half needs condition 1.

**Corrected order.** Finish the embedding index for the remaining 166 reports, about 4.8 h. Score BM25 against BM25-plus-nomic fusion at k = 10, 15 and 20, all free. Freeze the retriever. Build prompt trimming, which is required at any k. Then run condition 1 at two k values, where the winner becomes the official condition 1 and the loser is a k-ablation row for the paper.

### 3.4.7 **[DECIDED 5 Aug 2026] The retriever is frozen: BM25 alone. The dense arm is dropped.**

The full index completed: 255 reports, 60,871 elements, 179 MB, 362.7 minutes, 0 failures. Fusion was then decided on recall at n=700, which is the right basis because fusion changes *which* k chunks reach the prompt rather than how many, so it carries no gold-versus-distractor tradeoff and needs no end-to-end run.

| | k=10 | k=15 | k=20 |
|---|---|---|---|
| **ours BM25 alone** | **74.60%** | **81.12%** | **84.56%** |
| `nomic-embed-text` alone | 58.66% | 66.04% | 70.59% |
| RRF(BM25, nomic), equal weights | 75.00% | 80.71% | 84.55% |
| RRF(BM25 x1.1, nomic) | 75.20% | 81.75% | 85.76% |
| union of the two, ceiling | 81.28% | 86.42% | 89.13% |

**No interaction with the k decision.** Whatever fusion does, it does at all three k, so the freeze order in §3.4.6 holds and the two choices stay independent.

**Reason 1, the deciding one: untuned fusion gains nothing.** Equal-weight RRF moves +0.40, -0.41, -0.01. The +0.6 to +1.2 appears only at weight 1.1, chosen by reading these results. §3.4.1 rejected the `k1`/`b` sweep's +0.37 on exactly that ground, and there is no held-out set to validate a weight against. Consistency requires rejecting this too.

**Reason 2: dominated by a parameter change.** BM25 alone at k=11 scores **76.29%**, beating fused retrieval at k=10's 75.20%, for 398 extra prompt tokens and no second model.

**Reason 3: the deployment story.** A second resident model, a 178 MB index, and roughly 100 s of indexing per new filing in any real deployment, for about one point, in a paper whose contribution is on-device feasibility.

**The k=20 case is closer than the k=10 case, and should be stated that way.** There, fusion's +1.20 is worth about three k steps or ~1,260 prompt tokens, so on wall-clock grounds it is nearly a wash. The tuning objection decides it, not the cost.

**The frozen retriever: `src/bm25_retriever.py`, `k1 = 1.5`, `b = 0.75`, one `context` element per chunk, Lucene IDF, punctuation dropped, no stemming, per-report corpus. k is not yet frozen and is decided by condition 1.**

**What survives as reportable.** `nomic-embed-text` alone at 58.66% / 66.04% / 70.59% is a free local embedder measured against the paid `text-embedding-3-large`'s 68.01%. We found no other work reporting a local embedding model on FINDVER. And two methodological negatives: a weak arm in an RRF actively harms a strong one, and weighted RRF has almost no usable range above a ratio of about `(c+k)/(c+1)`.

**Keep `embeddings/` until after submission.** It is derived data and deletable in principle (§11 item 11), but rebuilding costs 6 hours and it occupies 179 MB against a 1.3 GB clone already on disk. Delete it once the paper is in.

**[REVISED 4 Aug 2026] The dense arm's case is now thinner, but it survives.**

| at k=10 | macro | element | all-gold |
|---|---|---|---|
| ours bm25 alone | 74.60% | 70.5% | 50.4% |
| RRF(ours bm25, `text-embedding-3`) | **77.14%** | 72.1% | 54.3% |
| union of the two, ceiling | 82.85% | 78.9% | 62.9% |

Adding the paid embedding to our BM25 is worth **+2.54 macro**, down from the +6.05 that fusion bought over the published baseline. So the go/no-go tightened: `nomic-embed-text` is weaker than `text-embedding-3-large` and now has to preserve a 2.5-point gain rather than a 6-point one. Score the local dense arm alone first; if it lands far below 68% the fusion gain may not survive at all, and BM25 alone is already a publishable retrieval result. **The target is no longer 68.01%. It is whether a fully local hybrid can clear our own 74.60%.**

### 3.5 How retrieval mechanically works — and which model does it
Retrieval is **not** done by the generation model. It uses a separate, much smaller **embedding model** whose only job is converting text into a vector. The pipeline:
1. **Chunking** — decided by our script. FINDVER's natural units: each `context` element is one chunk.
2. **Embed all chunks** — embedding model, run **once offline**, cached.
3. **Embed the claim** (or each decomposed sub-claim) at query time.
4. **Similarity ranking + top-k** — **no model at all.** Cosine similarity is a formula; top-k is sorting numbers. Plain `numpy`.
5. Retrieved chunks get pasted into the prompt.

Local embedding model: `ollama pull nomic-embed-text`. Tiny, instant on CPU. Where a *generation* LLM enters retrieval: upstream, deciding **what to search for** (§3.6). BM25 (§3.7) needs no model at all.

### 3.6 Claim-decomposed retrieval
Embedding the whole claim as one query produces a blurry average when the claim needs multiple facts. **Decomposition:** an LLM first splits the claim into atomic facts + the connecting operation; retrieval runs **separately per fact**; results merge. Each query becomes sharp.

**[MEASURED]** Week-1 testing produced direct evidence this matters: given a compound claim, the 7B model spontaneously decomposed it into two sub-claims and evaluated each separately, producing visibly cleaner reasoning than the 3B model's single-pass attempt. The behaviour we planned to *engineer* is one a larger model performs *spontaneously* — which suggests decomposition is a real lever, and that making it explicit could let a small model imitate a large one's reasoning structure.

### 3.7 Hybrid retrieval (BM25 + embeddings)
Financial evidence hinges on exact strings — "120 days", specific dates, exact figures — which embeddings blur. **BM25** is classical keyword search (no model, no training; `rank_bm25`) rewarding exact token matches. Run both, merge via reciprocal rank fusion → typically higher recall on number-heavy domains.

### 3.8 Why "in-head" LLM arithmetic fails — and what code execution changes
An LLM is a next-token predictor. When it writes `210,600 − 145,300 =`, **no arithmetic executes anywhere** — it generates whichever digits are *statistically likely* to follow. For large or uncommon numbers this is unreliable, degrades with more digits and operands, and errors carry no signal (the model is equally confident either way).

**Code execution** changes the division of labour: the LLM *writes* a short program — a pattern task it excels at — and a real Python interpreter *executes* it deterministically. Analogy: an accountant with a calculator, not because they cannot subtract but because the calculator's error rate is zero. Established technique: **Program-of-Thought (PoT)** and **PAL** (2022–23). In a raw-API pipeline there is no sandbox — *our script* extracts the code, executes it (restricted `exec`/subprocess), and feeds results back. That loop **is** the code-execution skill.

### 3.9 Tables as data, not prose
All published FINDVER approaches hand tables to the model as flattened text, which asks the LLM to do **two-dimensional grid reasoning through sequential token pattern-matching**. A value's meaning lives at a row×column intersection, but flattening destroys the grid.

The alternative: parse each table into a **pandas DataFrame** and have the LLM write a lookup:

```python
val_2024 = df.loc["120+ days past due", "Mar 31, 2024"]   # → 210600
val_2023 = df.loc["120+ days past due", "Mar 31, 2023"]   # → 145300
print(val_2024 - val_2023)                                 # → 65300, CPU-computed
```

`.loc[row, col]` is exact addressing. Given correct labels it is *mechanically incapable* of returning the wrong cell — it returns the exact value or throws. Failure modes eliminated: adjacent similar rows, column misalignment in wide tables, position-in-context decay, and formatting noise entangled with lookup.

The key structural point: **extraction and computation errors compound** — a wrong extracted number guarantees wrong arithmetic regardless of calculator quality. Flattened text is exposed to both; the DataFrame + code path removes both at once. This is why table querying and code execution are one combined skill in practice.

Honest caveat: a hypothesis to be tested by ablation. If extraction errors barely move after adding DataFrames, that itself is informative — it would point at *which* table gets retrieved (Pillar 1) rather than how a retrieved table is read.

### 3.10 Explanation faithfulness (vs. label correctness)
Two different things a verifier can check:
- **Label correctness / internal coherence** (what MACE's Verifier does): does the verdict follow from the stated reasoning?
- **Faithfulness** (the open gap): is **every individual step grounded in the document**? Does each cited figure exist at the cited coordinates? Does each arithmetic step re-execute correctly?

**[MEASURED]** Week-1 testing produced a textbook example of why this distinction matters. On `ie-val-0`, the 3B model reached the **correct label** (refuted) with **partially incorrect reasoning**: it computed the correct $42,146 total and correctly noted it contradicts the claim's $32,253 — sufficient grounds to refute — but then pivoted to a second, invalid justification, arguing the item was not Level 2 because it was described as "other significant observable inputs," which is a paraphrase of what Level 2 *means*. A reader trusting that explanation would be misled about *why* the claim fails, even though the verdict was right. Label accuracy alone would score this a clean success.

FINDVER's authors evaluated explanations only with human raters and **explicitly call for automated explanation-error detection** in their limitations section. Nobody has answered that call. The verifier doubles as a **new evaluation metric**: "X% of explanation steps are verifiable against the document."

### 3.11 Frameworks vs. plain scripts
**Decision: plain.** The pipeline is 4–5 LLM calls with simple branching (~200 lines). Frameworks add a learning curve, hide control flow (miserable to debug), and churn their APIs. If asked: AutoGen was considered (MACE used it) but plain implementation chosen for debuggability. **One framework habit to keep regardless: log everything** — every prompt, response, retrieved chunk, and executed snippet, per example, to disk.

### 3.12 Data contamination
2026 models may have trained on the Jan–Apr 2024 filings *and possibly the public testmini set with labels*. Diagnostic: ask the model to verify claims **with the evidence withheld** — above-chance accuracy without evidence is a smoking gun. Relevant as a caveat on a high baseline and as a standalone analysis (§10, Plan C).

---

## 4. The Architecture: Cloud-Edge Collaborative Agent

### 4.1 The professor's framework
Two tiers of model, routed by subtask difficulty:
- **Edge** = a small model running locally, free and unlimited: **Qwen2.5-Coder-3B via Ollama**. The *Coder* choice is deliberate — much of the edge workload is writing small Python snippets, a code-tuned model's sweet spot.
- **Cloud** = APIs for large models (**Qwen, DeepSeek** — professor-provided), reserved for judgment-heavy subtasks.

Motivation: FINDVER documents are huge; if every subtask calls a paid model, token costs balloon. This is not a cost hack bolted on — the routing policy is itself a research variable (§5.3).

### 4.2 Hardware and scope decisions (settled)
- Machine: 2017 Intel MacBook Pro, 16 GB RAM, CPU-only inference (Radeon Pro 555 unusable — Ollama's acceleration needs Metal/CUDA/ROCm). **[MEASURED]** Both 3B and 7B fit comfortably in RAM (§4.6); the binding constraint is CPU throughput, not memory.
- Professor's call: **do not upgrade hardware now**; revisit only if the local model proves a demonstrated bottleneck. Fallbacks: Google Colab free GPU tier; possible lab server.
- **[UPDATED 3 Aug 2026]** The lab server is no longer hypothetical — he has offered one with a GPU (§13 item 11). **This does not change the machine of record.** Accuracy and ablations may run on the server; every latency, throughput and memory figure in the paper is measured on this MacBook. Full rule, including the prohibition on printing a server-derived number under a MacBook label, in §13 item 11.
- **RAG-only** (§3.3). No long-context experiments.

### 4.3 Local setup reference — **[MEASURED]** including the config trap
```
ollama pull qwen2.5-coder:3b     # edge generation model
ollama pull nomic-embed-text     # edge embedding model
ollama run qwen2.5-coder:3b --verbose
```

**The two caps, framed once.** A model call has two ends and each has a limit. `num_ctx` caps what goes in, `num_predict` caps what comes out. Both truncate with no error, no warning, and no marker in the output, and both make you blame the model for something you configured:

| cap too small | what breaks | what it looks like | what it actually is |
|---|---|---|---|
| `num_ctx` | evidence missing from the prompt | the model hallucinated | we truncated the input |
| `num_predict` | verdict missing from the response | the model ignored the format | we truncated the output |

`num_predict` bites harder than it sounds, because chain-of-thought reasons first and concludes last, so an output cap removes precisely the sentence the extractor needs. Get either wrong inside an 8-hour run and you get 8 hours of results that are wrong for a reason invisible in the outputs.

**The fix is not "raise both", and that is not even a coherent setting.** Three reasons.

1. **They share one budget.** In llama.cpp, which Ollama sits on, `num_ctx` is the *total* window: prompt tokens and generated tokens both live in it. With `num_ctx` 8192 and a 4,000-token prompt there is room for roughly 4,000 generated tokens, full stop. Raising `num_predict` beyond that only changes which limit is hit first.
2. **Uncapped output is a hazard.** A small model at temperature 0 can fall into a repetition loop and generate indefinitely. On an unattended 8-hour run, one such example consumes the night. The cap is a safety valve and we want it.
3. **Larger `num_ctx` costs RAM up front**, because it sizes the KV cache at load time whether or not the tokens are used. **[MEASURED 1 Aug, and cheaper than assumed]** For `qwen2.5-coder:3b` on this machine: 4096 → 2.4 GB, 8192 → 2.6 GB, 16384 → 3.2 GB, 32768 → 4.4 GB, against 16 GB physical. Roughly 0.07 GB per additional 1k of window. An earlier draft of this section claimed 16 GB was no place for a 32k window; that was wrong, and RAM is not the binding constraint for the 3B. Re-measure before assuming the same for the 7B, whose KV cache is larger.

**Settings.** An *unused* window costs only that RAM, not time. What costs time is actual prompt tokens, at 19.1 tok/s ingestion on the 3B (§4.6), so a generous window is cheap insurance while a bigger prompt is not.

    num_ctx      16384     ~3.2 GB; double today's headroom, so a larger retrieval k
                           does not require re-tuning this
    num_predict   1500-2000  upstream's 1024 truncated a verbose 3B mid-reasoning.
                           Llama-3.2-3B's cleanly-ending responses ran a median of
                           354 words and a max of 827, so ~1,100 tokens covers the
                           longest observed. Confirm on our own model in the trial run.

That leaves `16384 > ~4,500 prompt + 2,000 generation` with roughly 9,800 tokens of slack, so overflow is arithmetically impossible rather than merely unlikely.

**[ESTIMATED 2 Aug 2026, pre-flight — superseded by the measurement below, kept because the error is instructive] Real RAG prompts are about twice the assumed size, and two of twelve overflow.** The ~4,500 figure came from one filled sample built by hand in week 1. Building the 12 trial prompts for real, with the placeholder retriever at *k*=10, and converting characters to tokens at 3.6 chars/token, predicted:

    mean prompt   ~8,000 tokens        assumed ~4,500
    range         ~3,000 to ~15,500    budget is 16384 - 2000 = 14,384
    over budget   2 of 12              ie-val-222 ~15,078, knowledge-val-65 ~15,514
    at 12,000+    5 of 12

**[MEASURED 2 Aug 2026, trial run — the prediction above overshot by ~17% and no example overflowed.]** Real `prompt_eval_count` values from all 12:

    mean prompt      6,610 tokens      predicted ~8,000
    median           7,110
    range            2,283 - 11,134    predicted ~3,000 - ~15,500
    over budget      0 of 12           predicted 2 of 12
    ie-val-222       11,134            predicted ~15,078   (-26%)
    knowledge-val-65 10,770            predicted ~15,514   (-31%)

    largest prompt + its actual generation    11,630  vs num_ctx 16384
    largest prompt + a full num_predict       13,134  vs num_ctx 16384

**The error was entirely in the chars-per-token conversion.** Character counts were exact; 3.6 chars/token was not. **The measured ratio over 12 real prompts is 4.36 chars/token**, and it ranges 2.46 to 5.19 *across examples*. Financial filing prose tokenises more efficiently than assumed. So the paragraph before last is still wrong about ~4,500 being the mean, but right that overflow does not occur — for a different reason than it gave.

Two things follow that matter more than the corrected number.

**The ratio is content-dependent by a factor of 2, so a character budget is not a safe proxy for a token budget on this data.** `numeric-val-242` sits at 2.46 chars/token and `knowledge-val-65` at 5.19. The low end is table-heavy content, where pipe delimiters and digit strings fragment; the high end is prose. Any trimming logic must count tokens, not characters.

**The overflow alarm has still never fired on real data.** It passes in the harness against fabricated counts, and that is the entire evidence for it. It stays, since it costs nothing and guards the eviction behaviour measured below, but it is unvalidated in production.

The residual risk this section named, a single oversized table chunk, did not materialise at *k*=10. **The prescribed mitigation, "count tokens before sending and trim or drop the lowest-ranked chunk until it fits", was never built, and is no longer urgent.** Its justification has changed from correctness to wall-clock: prompt size is the sole driver of runtime (§4.6), so trimming is now an efficiency measure competing against building a real retriever, which cuts prompt size and raises recall at once. It must still exist before any run at a larger *k*.

**Do not fix prompt size by raising `num_ctx`.** That trades a bounded problem for an unbounded one. §4.6 measures prompt ingestion as essentially the entire cost of a call, so window size costs wall-clock rather than RAM, and wall-clock is the binding constraint (§12.1). A larger window also cannot rule out a pathological single chunk. Trimming bounds prompt size, bounds runtime, and degrades gracefully by dropping the least relevant chunk first.

**Second consequence, and it survives the correction: every RAG run costs more than §4.6's week-1 figures imply.** Not because prompts are 8,000 tokens, they are 6,610, but because sustained ingestion runs at 15.6 tok/s rather than 19.1. Measured: 419 s per example, 11.9 h for 102, 81.6 h for 700. See §4.6 and §12.1, both corrected.

**`num_predict` 2000 is roughly 4× larger than our model needs.** Measured across 12 real responses: mean 394 tokens, max 496, max 354 words. The 1,100-token estimate above was derived from Llama-3.2-3B and is conservative for Qwen2.5-Coder-3B, which is markedly less verbose. The cap costs nothing, being a ceiling rather than a reservation, but it is what the prompt budget subtracts: at `num_predict` 800 the budget rises from 14,384 to 15,584. Not urgent. Twelve examples is a thin basis for a tail bound, so re-check against the 102-example run before changing it.

**There is no input-token parameter.** `num_ctx` is the total window, so prompt size is entirely ours to manage. This is safe only because the pipeline is RAG-only (§3.3): we never pass a filing, we pass *k* retrieved chunks, so prompt length is set by *k* and chunk size rather than by document length. The residual risk is a single oversized table chunk blowing the budget alone. Mitigation: count tokens before sending and trim or drop the lowest-ranked chunk until it fits.

**The defence that actually holds is the assertion, not the number.** Log both counts on every call and alarm when either sits at its ceiling. That catches the failure whatever the settings are, including the case where a prompt grows later and quietly crosses a line that used to be fine.

**[MEASURED 1 Aug 2026] What Ollama 0.12.3 does when generation fills the window: it shifts context and destroys the oldest prompt tokens, silently.** Tested directly against the local server rather than read from documentation, because this behaviour has changed across Ollama versions and we are pinned. A canary string was placed at the very start of a 74-token prompt, with a long generation requested, and only `num_ctx` varied:

    num_ctx  192 | prompt  74 | eval 268 | total 342 | done=stop | canary LOST
    num_ctx  256 | prompt  74 | eval 339 | total 413 | done=stop | canary LOST
    num_ctx  512 | prompt  74 | eval 286 | total 360 | done=stop | canary OK
    num_ctx  512 | prompt 512 | eval 277 | total 789 | done=stop | canary LOST, confabulated

Three results. **Generation is not stopped by the window**: totals reached 342 and 413 against windows of 192 and 256, so decoding continues and the oldest tokens are evicted to make room. **`done_reason` is `"stop"` in every case, never `"length"`**, so the API reports a clean normal completion while data is being destroyed. **The model confabulates rather than reporting the loss**: in the overflow run it stated the secret code was "double entry", and it also silently dropped the trailing instruction to state the code at all, because that had scrolled out of view too.

**The consequence for §11.9.** A prompt that fits perfectly at ingestion can still have its evidence scrolled out *mid-generation* if the response is long. The evidence assertion checks that gold tokens are present in the prompt *string*, so it passes while this happens and cannot catch it. The alarm condition is therefore not `prompt_eval_count == num_ctx`, which only catches input-side truncation. It is:

    prompt_eval_count + eval_count  >=  num_ctx     ->  evidence may have been evicted

Log both counts on every call and check the sum. This is the only signal available, since the response text and `done_reason` both look healthy.

**Critical: Ollama's default context window is 4,096 tokens and it truncates silently.** A realistic RAG prompt for this benchmark runs ~3,900–4,500 tokens, so the default clips real evidence with no warning, no error, and no indication in the output. In week-1 testing this produced confident hallucinated figures that looked exactly like a genuine extraction failure. Every run must set the window explicitly:

```
/set parameter num_ctx 8192          # interactive
{"options": {"num_ctx": 8192}}       # REST API
```

Sanity check after every run: `prompt eval count` should be comfortably *below* the configured window. A value sitting exactly at the ceiling means truncation.

**[NEW 1 Aug 2026] `num_predict` is the output-side twin, and it is the one we had not thought about.** `num_ctx` caps the input and silently drops evidence. `num_predict` caps generation and silently cuts the response off mid-reasoning, before the model ever states a verdict. The example then lands in the `unparseable` bucket and looks like a model that cannot follow the output format, when in fact it was interrupted.

This is not hypothetical. The upstream FINDVER runs used vLLM `max_tokens = 1024` (`run_llm.py:47`, and `scripts/inference/main_vllm.sh` passes no override). Measured on their Llama-3.2-3B outputs, 108 of 700 responses end with no terminal punctuation, and their word counts pile against a hard ceiling (p90 863, max 916) that cleanly-ending responses never approach (max 827). A ceiling in one group and not the other is the signature of a generation cap. **90 of those truncated responses land in the `none` bucket, which is 39% of that bucket and about 13% of all 700 examples.**

Actions: set `num_predict` explicitly in every API call, log the eval count for generation as well as for the prompt, and treat a response ending without terminal punctuation as a distinct failure mode in the error taxonomy rather than as a format failure. Ollama's default `num_predict` has not been verified on v0.12.3 and must be checked before the first batch run, not after.

**Note:** the local MacBook runs macOS 13 Ventura, which Ollama dropped support for in v0.12.4. **v0.12.3 (Sept 2025) is the last compatible release** and is pinned. Auto-update must stay off, or the toolchain breaks mid-project.

### 4.4 Full subtask → component assignment
The central design table. Note how much is **no model at all**:

| Subtask | Component | Why |
|---|---|---|
| Chunk/claim → vectors | Embedding model (local) | One forward pass; no reasoning |
| Similarity ranking, top-k | **No model** — `numpy` | Pure math |
| BM25 keyword search | **No model** | Classical algorithm |
| Claim decomposition into atomic facts | **Edge** (3B) | Structured, templated; pattern-following |
| Writing `.loc` lookups given real labels | **Edge** (3B) | Mechanical translation; code model's specialty |
| Table → DataFrame parsing | **No model** — Python, offline, once/doc | Deterministic |
| Executing generated code | **No model** — sandboxed interpreter | The whole point |
| Planning: what evidence, what operation | **Cloud** | Judgment; errors poison everything downstream |
| Multi-evidence synthesis (most of FDV-KNOW) | **Cloud** | Beyond 3B capability |
| Final explanation generation | **Cloud** | Quality and correctness both matter |
| Glossary term-spotting | **Edge** or plain string match | Low-stakes pattern recognition |
| Verify: cited number exists at cited cell; re-run arithmetic | **No model** — Python | Exact comparison |
| Verify: does a reasoning step logically follow | **Edge first, escalate on failure** | Cheap screen, expensive confirm |
| Retry/re-plan control flow | **No model** — `if`/`while` | Orchestration, not intelligence |
| Filling the final output template | **Edge** (3B) — *default flipped, see below* | Formatting after reasoning is done |

**Open, 1 Aug 2026 — the last row is provisionally reassigned to cloud.** The cloud tier already generates the explanation, so it is already emitting text. Passing that text to a 3B model purely to wrap it in the required sentence adds a second model call, a second failure mode, and local wall-clock, and the label extractor (§11.8) has to read the *3B's* formatting rather than the cloud model's. Extrapolating from the §4.6 rates, a ~500-token reformat prompt plus a ~60-token sentence is roughly 35 s per example on the 3B, so about an hour added to a 102-example run. It buys nothing the cloud call did not already produce.

**Provisional decision:** the cloud model emits the verdict sentence directly, and edge template-filling becomes an optional ablation rather than the default path. This costs the contribution nothing. Role-to-model assignment across decomposition, `.loc` generation, glossary spotting, and the first-pass verifier screen is untouched, and template-filling is the most trivial row in this table. Moving it because measurement says to is §4.5's method working, not a retreat from it. Not settled: it belongs to the professor alongside open question 1 (§13). Nothing on the current critical path depends on it, since the edge-only baseline is 3B-formatted end to end regardless.

### 4.5 **[MEASURED]** The routing boundary is now an open empirical question

The table above encodes an *assumption*: that a 3B model handles only mechanical subtasks and everything judgment-like escalates. Week-1 testing complicates that usefully.

Given the **entire end-to-end task** — full retrieved context, find the evidence, do the arithmetic, interpret an accounting concept, reach a verdict — with no cloud model involved at all, **the 3B model got it right**. It located the correct table, summed four line items correctly ($9,893 + $29,056 + $86 + $3,111 = $42,146), noticed the contradiction with the claim's $32,253, and returned the correct label. That is a task §4.4 assumed would need cloud escalation.

This does not mean the cloud tier is unnecessary — the same run showed the 3B model's *explanation* contained an invalid supporting argument (§3.10), and the 7B model's reasoning was visibly more structured. But it does mean the edge/cloud line should be **drawn from data rather than assumed**, and it strengthens the case for making the routing threshold a swept parameter (Tier 5) rather than a fixed design choice. **This is the single most useful open question to put to the professor at the next meeting.**

### 4.6 **[MEASURED]** Local model performance — the numbers that constrain everything

Measured on the real pipeline: one `ie-val-0` prompt, ~3,945 tokens of retrieved FINDVER context, `num_ctx` 8192, no other applications running.

| | Qwen2.5-Coder-3B | Qwen2.5-Coder-7B |
|---|---:|---:|
| Prompt ingestion rate | 19.1 tok/s | 7.8 tok/s |
| Prompt ingestion time | 3 m 27 s | 8 m 27 s |
| Generation rate | 6.7 tok/s | 3.2 tok/s |
| Generation time | 1 m 16 s | 3 m 11 s |
| **Total per example** | **4 m 45 s** | **11 m 46 s** |
| Peak RAM | ~2.5 GB | ~5 GB |
| Memory pressure | green throughout | green throughout |
| Verdict on `ie-val-0` (gold: refuted) | correct | correct |
| Reasoning quality | correct arithmetic, one invalid supporting argument | correct, decomposed into sub-claims |
| Followed required output format | yes, provisional — see correction | yes, provisional — see correction |

**Correction, 1 Aug 2026.** This row previously read "no" for both models, and that was wrong. The "no" described the *first* test round, which ran before `num_ctx` was set explicitly and whose prompt was corrupted by the loader bug in §2.3. On the re-run with `num_ctx` 8192 both models did produce the required concluding sentence, in the "therefore, this claim is entailed/refuted" form. Two things follow. First, the table as originally committed mixed the two rounds, since the caption above already states `num_ctx` 8192 while this row did not come from that run. Second, the corrected value is from recollection of the session and not from a preserved output artifact, so it is **not yet a logged measurement**. Re-running both models on `ie-val-0` costs about 17 minutes and would settle it. Until then, do not cite this row as evidence either way about small-model format compliance. The format-failure rates that *are* measured come from the 16 upstream output files (§11.8), not from our own runs.

**[MEASURED 2 Aug 2026, trial run — this row is now backed by logged artifacts, for the 3B.] `qwen2.5-coder:3b` at temperature 0 produced a usable verdict on 12 of 12 examples. Zero unparseable.** 11 at the `anchored` extractor level, 1 at `bare`. This does not literally replace the row above, which describes `ie-val-0` at `num_ctx` 8192, whereas the trial run used `baseline_v1` at 16384 on a different 12 examples. The 7B row remains recollection.

Twelve examples cannot establish a rate. The defensible claim is that our `none` rate is **not** the 33% seen for upstream's Llama-3.2-3B, and probably not near it, which is what §11.8's temperature-0 caveat predicted. The 102-example run gives the first figure with a usable interval.

**But format compliance is looser than "yes" suggests, and the detail matters for the extractor.** Reading the 12 response texts:

- **The verdict is often not the final sentence, despite the prompt demanding it.** Three responses continue writing after it; `knowledge-val-105` states it mid-response with ~400 characters following, in a 2,084-character response. Four of twelve. **Only §11.8's whole-response `anchored` search caught these** — a last-line or last-300-character rule would have failed on a third of the sample. The level-1 design is now justified by data rather than by argument.
- **Markdown emphasis inside the verdict sentence**, "the claim is \*\*entailed\*\*", in four responses. Qwen2.5-Coder is code-tuned and formats in markdown by habit. The pattern tolerates it.
- **The model echoes the prompt's own template placeholder.** `knowledge-val-33` ended with, literally, `Therefore, the claim is {refuted}.` — braces included, copied from the instruction `"Therefore, the claim is {entailment_label}."` This is the single example that required the `bare` level. **It is a prompt bug, not a model bug:** showing a model a literal `{entailment_label}` invites it to echo the braces. Fill the placeholder in the format example in the next prompt version.
- **Two responses state the verdict twice** in different phrasings. Both agreed, so the "last match wins inside a level" rule was not stressed, but it is now exercised on real data.

All 12 responses ended with terminal punctuation and `done_reason` was `stop` on all 12. No generation was truncated.

**Batch runtime implications — these drive the schedule:**

| Run size | 3B | 7B |
|---|---:|---:|
| 100 examples (one ablation round) | ~7.9 h | ~19.6 h |
| Full testmini, **700** examples | ~55 h (≈2.3 days) | ~137 h (≈5.7 days) |

**[SUPERSEDED for the 3B, 2 Aug 2026 — measured on the trial run. The table above is optimistic; use the numbers below.]** Twelve real examples, fitted over the 11 after the first, which carries the 5.3 s model load:

    elapsed = 0.0641 s per prompt token        R² = 0.995
    implied sustained ingestion                15.6 tok/s   (week-1 single example: 19.1)
    mean per example, at our mean prompt of 6,610 tokens     419 s = 7.0 min
    102 examples                               11.9 h       (this table implies ~8 h)
    700 examples                               81.6 h       (this table implies ~55 h)

| Run size | 3B **measured** | 7B (still an estimate) |
|---|---:|---:|
| 102 examples (one ablation round) | **11.9 h** | ~20 h |
| Full testmini, **700** examples | **81.6 h (≈3.4 days)** | ~137 h (≈5.7 days) |

**[GPU CORRECTION 14 Aug 2026 — this whole subsection is MacBook-only.]** Every figure above is CPU-only inference on the 2017 MacBook. Measured across four 3B runs on the GPU box (`gold_alone`, `k=5`, `k=10`, `gold_padded`; prompt 1,124 to 3,731 tokens, output 389 to 418):

    elapsed = 0.00060 s per prompt token + 4.6 s fixed       R² = 0.996   n=4 runs, 700 claims each

Prompt tokens rise 3.3x, wall clock rises 1.28x. **The GPU ingestion coefficient is 107x smaller than the MacBook's 0.0641**, and the fit carries a 4.6 s per-claim constant the MacBook fit did not need. That constant is **67 to 87 percent of wall clock** and does not scale with prompt size. **It is not decomposed** — output varies only 389 to 418 tokens, the same degeneracy described in the next paragraph, so no generation rate may be quoted from it. **Consequence: on the GPU box, prompt size is nearly free and is not the lever on wall clock.** Do not plan a GPU run with the numbers above. See `build_log.md`, 14 August.

**A two-parameter fit separating ingestion from generation was attempted and rejected as degenerate.** `eval_count` varies only from 261 to 496 across the sample, so the generation term is unidentifiable and returned a negative rate. That is a property of the sample, not a finding about the model. Do not report separated rates from this run; the 7B row above has not been re-measured at all.

Four conclusions:
1. **Prompt ingestion does not merely dominate, it is the whole cost model.** At R² = 0.995 against prompt tokens alone, generation is not separately visible. Retrieval tightness (*k*) is a **performance** parameter at least as much as an accuracy one, and the two point the same way. At the fitted rate, cutting the mean prompt from 6,610 to 3,000 tokens takes a 102-example run from 11.9 h to ~5.4 h. This is an argument for claim-decomposed retrieval on efficiency grounds *in addition to* recall grounds, now with a number attached.
2. **A 102-example round on 3B is a full night, not a comfortable one.** 11.9 h started at 9pm finishes at 9am. Iteration cadence is one configuration per day and a late start spills into the next.
3. **7B is for spot-checks, not batches**, unchanged.
4. **The sustained rate is 18% below the single-example week-1 rate.** Consistent with thermal throttling over a longer run, a larger working set, or both. Expect further degradation over a 12-hour job rather than better.

### 4.7 Pipeline shape
```
claim ─► [Decomposer: edge] ─► atomic facts + operation
      ─► [Retriever: embedding model + BM25 + numpy] ─► candidate chunks   (per fact)
      ─► [ASSERT: gold/expected evidence actually present in prompt]        ◄── §11.9
      ─► [cached DataFrames loaded for table chunks; df.index/df.columns into prompt]
      ─► [Planner: cloud] ─► which lookups, which operation
      ─► [Executor: edge writes code] ─► [Sandbox: runs it] ─► exact values
              ▲                                │ error/traceback fed back → retry
      ─► [Reasoner/Explainer: cloud] ─► verdict + step-by-step, evidence-cited explanation
      ─► [Verifier: python checks + edge/cloud judgment] ─► pass, or one retry
      ─► [Label extractor: regex + fallback]                                ◄── §11.8
```

---

## 5. Relationship to MACE — and the Sharpened Contribution

### 5.1 "Multi-agent" and "edge-cloud" are independent axes
An "agent" in MACE is a **role**: one system prompt plus a position in the loop. MACE sent all three roles to the same large model. Our architecture asks the question MACE never asked: **which model should play each role?** Role assignment = the multi-agent axis; model assignment = the edge-cloud axis. We keep MACE's role structure and vary the second.

### 5.2 Role to model mapping

| Role | Assignment | Why |
|---|---|---|
| Planner | Cloud | The step needs judgment, and an error here poisons everything downstream. |
| Executor, mechanical parts | Edge (3B) | Decomposing a claim, writing lookups, and filling templates are pattern work. |
| Executor, hard parts | Cloud | Combining several pieces of evidence, and FDV-KNOW reasoning, need a stronger model. |
| Verifier, arithmetic | No model (Python) | Re-running a calculation is free and deterministic. |
| Verifier, value comparison | Python plus a tolerance | Filings round, so an exact comparison produces false refutations. See below. |
| Verifier, judgment checks | Edge first, escalate to cloud | Cheap screening, costly confirmation. Carries a known risk. See below. |
| Feedback loops | Script control flow | Retrying is control flow, not intelligence. |

Per §4.5, treat this as the starting hypothesis to be tested rather than a settled allocation.

**Exactness is the wrong target for the value comparison.** The arithmetic check and the value comparison are two different jobs, and the previous version of this table collapsed them. Re-running `460 + 269.2` and getting `729.2` is exact, and it should be. Deciding whether `729.2` matches a claim of "$750 million" is a judgment about rounding, and Python's `==` gets that wrong every time. The comparison needs a tolerance. Choosing the tolerance is a design decision we have to make, record, and defend. Open question: whether one tolerance covers everything, or whether percentages, dollar totals, and share counts need separate ones.

**The verifier may refuse correct claims, and the edge-first design makes that more likely.** MACE reports that a verifier running a different model from the one that produced the answer rejects numerical claims a same-model verifier accepts. Our screening verifier is the 3B while the answer often comes from cloud, so we are in that configuration by design. We should measure the verifier's false-refutation rate separately from overall accuracy. Without that split we cannot tell whether the verifier is catching errors or creating them.

### 5.3 The contribution statement
MACE: "three specialized roles beat one undifferentiated pass" (one big model throughout). Ours: **"three specialized roles, each assigned to the cheapest component that can reliably do it — including free non-model steps — matches or beats the all-big-model version at a fraction of the cost."** Direct comparison against published SOTA, same role structure, different and more deployable resource allocation.

The **routing policy** — when does edge escalate to cloud? — is a knob, not a rule, and varying it yields a reportable curve: *always escalate* ≈ MACE's design; *never escalate* = edge-only floor; the interesting result lives between. Cheap to run once the pipeline exists.

### 5.3.1 **[CLARIFIED 10 Aug 2026] Which cost, exactly — the phrase "a fraction of the cost" was ambiguous and the n=700 numbers exposed it**

"A fraction of the cost" was never pinned to an axis. With condition 2 measured at 700 it has to be, because the honest dollar figure is small enough to be embarrassing: **the entire cloud-only baseline over all 700 claims cost $0.626 on flash.** No paper is carried by saving two dollars.

**There are two different comparisons in this project and they need different axes. Conflating them is what made the phrase feel empty.**

**Comparison A — condition 4 against condition 3** (our pipeline against the all-cloud pipeline). **[SHARPENED 10 Aug 2026, and this is a problem, not a clarification.]** Resident memory does not merely fail to separate them, **it runs the wrong way. Condition 3 keeps zero model parameters on the device**, since the cloud plays every role and the laptop only orchestrates. Condition 4 must hold 3B resident. **On memory, condition 3 beats condition 4. On "runs on a laptop," they tie, because both do.**

What is left is **how much cloud each consumes per claim**: calls, and tokens sent. That converts to money, which is under $3 across the whole project, and to data sent to a third party, which nobody has asked us about. **This is thin, and it is the weakest point in the contribution statement.** It is open question material for the professor, not something to write around.

**Comparison B — our approach against MACE** (§6.1). **This one is solid and is unaffected by the above.** MACE self-hosts every role, and its *smallest* configuration needs **27B of weights resident**. Ours is 3B plus an API call. Their smallest configuration cannot run on this machine; ours does. **Resident parameters and laptop feasibility are legitimate claims here precisely because MACE uses no cloud at all.** This is the on-device claim and it survives everything in Comparison A.

These are separate sentences in the paper. Neither is "we spent less money."

**The fallback, if Comparison A stays empty.** If nothing meaningful separates condition 4 from condition 3, the honest paper reports **beating condition 2 at 77.0% as a headline result in its own right** — a pipeline doing part of its work with a 3B model on a laptop beating a frontier cloud model used the obvious way — and presents the rest as a study of **where the line between the two models can be drawn**. §9.2's "beating condition 2 is a bonus" governs what leads the abstract. **It is not a reason to omit the result**, and an earlier reading of it in this document treated it that way.

#### The goal, stated so it does not drift again

**Assign every role to the cheapest component that can *reliably* do it, and escalate only what genuinely needs it.** The ordering is:

    no model  <  edge 3B  <  cloud

**It is not "maximise the number of 3B roles."** The largest savings in §4.4 are the **no-model** rows: BM25 search, top-k ranking, table parsing, executing generated code, re-checking arithmetic, retry control flow. All free, all deterministic, all faster than either model. A pipeline that pushed work onto the 3B *instead of* onto plain Python would be worse on every axis at once.

**[MEASURED 10 Aug 2026] The word "reliably" is now load-bearing rather than decorative.** Condition 1 at n=700 shows the 3B scores 61.3% with the gold evidence in its prompt and 61.6% without it. It cannot do evidence-based judgment, whatever §5.2's verifier row assumes.

#### Wall clock cannot carry the claim, because it reverses with the machine

**[MEASURED 10 Aug 2026, n=700.]** Per claim: **3B on the GPU box 6.8 s, `v4-flash` 12.7 s, `v4-pro` 23.2 s.** The local model is the *fastest* of the three, because the cloud models generate ~1,450 output tokens against the 3B's 416, most of it reasoning.

**On the hardware the paper is actually about, this reverses completely.** On the 2017 MacBook the 3B runs at roughly 7 minutes per claim, which is 420 s against flash's 12.7 s, about 33x slower. **Any latency sentence must name the machine.** Wall clock is a reported measurement, never the headline.

#### The curve is a better deliverable than any single ratio

The routing sweep above already commits to producing it. Condition 3 is always-escalate, condition 1 is never-escalate, and the sweep fills in between. **The knee of that curve — how much work can be moved off cloud before accuracy falls — is the result**, and it answers the "which cost" question better than any single number, because it shows the tradeoff instead of asserting a saving.

---

## 6. Related Work Since FINDVER — What Exists, and Its Weaknesses

### 6.1 MACE (Saha, Lakshmanan & Ng, UBC — arXiv 2604.17225, 2026) — the main competitor
- **What:** Planner/Executor/Verifier multi-agent framework on AutoGen with constrained speaker transitions and feedback loops. **Zero-shot CoT only — no training.** Evaluated directly on FINDVER testmini and test; claims SOTA/parity; smaller open models (27–92B) reach 80–100% of a 235B model's performance.

**[RESOLVED 3 Aug 2026 — the accuracy figure this document was missing.]**

**Their stated goal:** claim verification on tabular documents with no pre-training or fine-tuning, interpretable reasoning, and smaller models. Four datasets. Their own summary sentence: *"MACE achieves SOTA performance on two closed-domain datasets and performs on par with the best models on two others, while achieving 80–100% of best performance with substantially smaller models."*

**FINDVER is one of the two "on par" datasets, not one of the SOTA ones.** They did not beat the best models on our benchmark. They matched them. This is their characterisation, not our inference.

| Dataset | MACE result | Their claim |
|---|---|---|
| SciTab | 0.71 macro F1 | SOTA |
| SEM-TAB-FACTS | 0.90 micro F1 | SOTA |
| **FINDVER** | **0.76 accuracy** | **parity only** |
| SciTab-OD | 0.76 macro F1 | parity only |

**Table 8 is the FINDVER table. [VERIFIED 3 Aug 2026 against the paper by eye.]** TM = testmini, T = test. Their caption: *"All baseline models are sourced from Zhao et al. (2024b)."*

    baselines                        TM     T
    DeepSeek-V2-Lite                0.60   0.58
    Qwen-2.5                        0.72   0.70
    Llama-3.1 70B                   0.75   0.75
    Qwen-2.5 72B                    0.76   0.75
    Mistral-Large 123B              0.75   0.76
    Claude-3.5-Sonnet               0.73   0.70     <- see discrepancy below
    Gemini-1.5-Pro                  0.71   0.73
    GPT-4o                          0.75   0.76

    MACE
    Mt-7B   (Pm+Em+Vm')             0.64   0.65
    Ll-8B   (Pm+Em+Vm')             0.68   0.71
    Qw-72B  (Pm+Em+Vm)              0.75   0.74
    Qw-235B (Pm+Em)                 0.76   0.76     <- their headline FINDVER number

**[DISCREPANCY, unresolved — and MACE is our main comparison, so this matters]**

**MACE did not run their own baselines.** Their caption states *"All baseline models are sourced from Zhao et al. (2024b)"*, so these are FINDVER's published numbers copied across, not re-measurements. That makes a mismatch harder to explain, not easier: a copied number should match its source.

**Their Claude-3.5-Sonnet baseline matches neither FINDVER column.**

    MACE Table 8, Claude-3.5-Sonnet      0.73 TM / 0.70 T
    FINDVER Table 4, Claude-3.5-Sonnet   77.2 long-context / 75.0 RAG

It sits 2–4 points low against either setting. **The effect is that MACE's table demotes Claude-3.5-Sonnet below GPT-4o (0.73 against 0.75), while FINDVER's own table places Claude above GPT-4o (75.0 against 73.7 under RAG).** The strongest model in the source table is not the strongest model in theirs, and the ordering is reversed.

**[DECIDED 3 Aug] State the mismatch and its effect. Do not speculate about the cause, in either direction.**

The two facts are verifiable from the two published tables and need no interpretation:

1. MACE's Claude-3.5-Sonnet baseline is **0.73**, matching neither FINDVER's long-context (77.2) nor its RAG (75.0) figure.
2. **MACE's table places Claude below GPT-4o (0.73 against 0.75). FINDVER's table places Claude above GPT-4o (75.0 against 73.7 under RAG).** The ordering of the two strongest baselines is reversed.

That is the whole claim, and it is enough. **Do not write that MACE swapped two rows, and do not write that they demoted the baseline.** The first is an unverifiable mechanism; the second is a claim about intent. Neither is supported by two mismatched numbers, only two models overlap between the tables at all, and review is double-blind at a venue where a MACE author is a plausible reviewer. An unsupported accusation about a competitor's conduct would be treated as such, and it would put every other number in our paper under suspicion.

**Which figure we use: FINDVER's.** We evaluate on FINDVER, so its published number is the reference throughout. **Claude-3.5-Sonnet 75.0% RAG** (§2.6, §9.3). MACE's baseline column is not used as a source for any model FINDVER already published.

**[SETTLED DEFINITIVELY, 3 Aug, from their Retrieval Mechanism paragraph. An earlier note in this section claimed they never describe their retrieval setup; that was wrong. They do, in a separate section from the results.]**

Their exact words:

> **"Retrieval Mechanism. Since retrieval is not our primary focus, we adopt existing strategies.** For FinDVer, Zhao et al. (2024b) compared three retrievers: BM25, Contriever, and OpenAI's text-embedding-3 across retrieval sizes *k* = 3, 5, 10, finding text-embedding-3 with *k* = 10 optimal. **We adopt this configuration, achieving 67.91% and 69.53% recall for evidence retrieval on Testmini and Test sets.** For SciTab-OD, we retrieve top-2 tables using text-embedding-3, achieving 68.43% recall."

**Three consequences, all favourable.**

1. **MACE runs RAG with `text-embedding-3` at *k* = 10 — identical to FINDVER's published setup and to our Tier 0 baseline.** Their accuracy numbers are therefore directly comparable to ours with no setting caveat. The long-context-versus-RAG question is closed.
2. **Weakness 2's quote is verbatim, not a paraphrase.** "Since retrieval is not our primary focus, we adopt existing strategies" is their own sentence. This is the strongest available support for §6.6's gap statement: the leading approach on this benchmark states in writing that it declined to work on retrieval, and reports the ceiling unchanged.
3. **Their reported recall is 67.91% / 69.53%**, matching §3.4's record from the FINDVER paper. Our recomputation of 68.01% on the same metric reproduces it to within rounding, so all three sources agree.

Note they never use the term "RAG" anywhere in the paper; they describe the mechanism without the acronym. Searching for the acronym alone finds only `TableRAG` in their related work.

**[NOTED 3 Aug] Their body text overstates what their own numbers show, and their abstract does not.**

> *"Mace achieves **SOTA** performance on both TM and T splits with Qw-235B reaching 0.76 accuracy, **matching the best baseline results**."* (§4.4.2)

The two clauses contradict each other and the numbers side with the second. On TM, 0.76 ties Qwen-2.5 72B. On T, 0.76 ties both Mistral-Large 123B and GPT-4o. **Ties on both splits, not wins.** Their abstract's "on par with the best models on two others" is the accurate phrasing. **When citing MACE's FINDVER result, use the abstract's wording, not §4.4.2's.** State the tie plainly; do not editorialise about the discrepancy between their two descriptions.

**This is settleable for free and should be settled before the paper cites either number.** `outputs/` holds 700 records for both `claude-3-5-sonnet-20241022.json` and `gpt-4o.json`, each with the gpt-4o-mini extracted label, and `testmini.json` holds the gold labels. Recomputing accuracy for those two models is a set comparison with **no model calls and no cloud quota**. It would establish which figure is correct and whether the swap pattern is real. Until then, treat both MACE's Claude row and any ordering claim built on it as unconfirmed.

**[MATERIAL PROBLEM FOR CITING THEM] Table 8 does not state whether its baselines are long-context or RAG.** FINDVER reports both and they differ by about 2 points. Since this project is RAG-only (§3.3), a single undifferentiated MACE number cannot be placed beside our results without knowing its setting. **Check the text around Table 8 before putting any MACE baseline in our tables.** Their own MACE rows are presumably RAG, since they copy FINDVER's retrieval setup, but that is inference rather than something they state here.

**[NOTED] MACE's baseline list is broader than the FINDVER paper's Table 4.** DeepSeek-V2-Lite, Llama-3.1 70B, Qwen-2.5 72B, Mistral-Large 123B and Gemini-1.5-Pro do not appear in that table, but **all of them are in our `outputs/` directory**. So the FINDVER *release* covers more models than the FINDVER *paper*, and MACE sourced from the release. `outputs/` is therefore the authoritative baseline set for us, not the paper's printed table.

**The row that matters most to us is Llama-8B at 0.68.** That is a small model running the *full* multi-agent pipeline, and it lands below FINDVER's own 2024 Claude-3.5-Sonnet RAG figure of 75.0%. Mistral-7B is worse at 0.64. The published evidence says small models in a multi-agent pipeline do not approach the large-model number, which is both the opportunity and the risk for our 3B-plus-routing design.

- **[NEW 3 Aug, then CORRECTED the same evening once Tables 4 and 5 were read.] Weakness 5: they report efficiency, but never on FINDVER, and their runtime is a cost rather than a saving.**

  An earlier note in this section claimed their efficiency reporting narrowed our novelty. That was an overcorrection. The tables say otherwise.

  **Table 4 is memory, and its caption restricts it: *"Memory efficiency analysis for closed-domain datasets."*** SciTab and SemTab only. **Table 5 is runtime**, covering SciTab, SciTab-OD and SemTab. **Neither reports memory or runtime on FINDVER.** On our benchmark, deployment cost is unreported by anyone.

  **Table 5, runtime in minutes per 300 claims, is the important one:**

      Mt-7B  w CoT       4        Mt-7B  MACE    110       27x slower
      Qw-72B w CoT      23        Qw-72B MACE    123      5.3x slower
      Qw-235B w CoT   55.07       Ll-8B  MACE  121.83     2.21x slower (their ratio)
                                                          2.71x on SemTab

  **MACE's pipeline costs 2.2x to 27x more wall-clock than single-pass CoT.** Their efficiency claim is about *memory*, and they are explicit that runtime is the price paid for it. For a venue about latency under real-world constraints (§1.1, topic 05), that is an opening rather than a closed door: we have a fitted cost model at R² 0.995 (§4.6), and the strongest competing approach ships a large slowdown with no FINDVER timing at all.

  **Table 4 also gives their floor: total parameters across all agents.** Mt-7B with an independent verifier is **27B total** at 11.5% of the 235B baseline's memory; Ll-8B is 28B at 11.9%. Their *smallest* configuration needs 27B of weights resident. Ours is 3B local plus a cloud API. That is an order-of-magnitude difference in operating point, now stated against their own published number rather than asserted.

  §5.3's "fraction of the cost" framing should therefore say **which** cost. Memory: they already claim it, on other datasets. Wall-clock and on-device feasibility: unclaimed, on FINDVER, by anyone.

  **[WARNING, recorded 3 Aug because it was nearly written the wrong way round.] MACE is far FASTER than us in absolute terms, not slower.**

      MACE Ll-8B    121.83 min / 300 claims  =  ~24 s per claim   (server GPUs)
      Ours, 3B      7.0 min per example      =  420 s per claim   (2017 CPU laptop)

  That is roughly **17x slower on our side**, and it compares our *single-pass baseline* against their *full pipeline*. Our finished pipeline will be slower still. **Nothing in the paper may imply we are faster than MACE.** The 2.2x–27x figures are their pipeline against their own single-pass CoT on their own hardware; they say nothing about us.

  **The comparable metric is overhead ratio, not absolute seconds.** Their hardware, documents and pipeline stages all differ from ours, so seconds-against-seconds is meaningless. What *is* comparable is how much the pipeline costs over a single pass **on the same machine**:

      MACE          2.21x / 2.71x / 5.3x / 27x   (their Table 5)
      Ours          condition 1 vs condition 4   (§9.2, same machine, not yet measured)

  §9.2 already schedules both runs, so this number falls out of work that is happening anyway. If our routed design adds less relative overhead than their all-agents design, that is a real architectural result stated on their own metric.

  **What is defensibly ours, in descending strength.** (1) **The hardware floor** — their smallest configuration needs 27B of weights resident, ours needs ~2.5 GB for a 3B model (§4.6). That is a claim about what hardware is required, not how fast it runs, and it survives every objection. (2) **Feasibility on genuinely constrained hardware**, which is a deployment claim rather than a speed claim and is exactly topic 05's territory. (3) **First to report deployment cost on FINDVER** — true as far as the 3 Aug sweep goes, so phrase it "we found no other," never "nobody has" (§6.6).

  **No new optimisation workstream.** ~~§12.1 already established that prompt size is the only real lever on wall-clock, and tighter retrieval cuts runtime and raises recall at once. The retriever in Tier 2 **is** the speed work.~~ **[PREMISE CORRECTED 14 Aug 2026]** That reasoning holds only on the MacBook. On the GPU box prompt tokens cost 107x less and tighter retrieval buys recall with almost no wall-clock (§4.6). **The conclusion survives on different grounds:** there are no spare nights for a speed workstream, and speed is not what the paper claims. A separate speed effort would still compete for the same nights.

  **Do not let this displace the core.** §12.3 names retrieval recall and the extraction/imputation analysis as the two results that carry the paper, **joined on 14 Aug 2026 by the evidence-presence finding (§12.3, `paper_numbers.md` §2.8.2)**. Deployment cost is a supporting leg, not a replacement for any of them.
- **Weakness 1 — no code execution.** The Executor performs computations inside its natural-language output; their own published example sums seven six-digit figures in prose and contains an apparent transcription slip (1,099,107 vs 1,999,107 two lines apart). The computation-error category is unaddressed by the current best approach.
- **Weakness 2 — retrieval untouched.** **[QUOTE VERIFIED VERBATIM 3 Aug 2026]** Their exact sentence is *"Since retrieval is not our primary focus, we adopt existing strategies."* They then adopt FINDVER's own configuration, `text-embedding-3` at *k* = 10, and report 67.91% / 69.53% recall — the ceiling sits unattacked, by their own written admission. This is the single most useful sentence in their paper for us (§6.6).
- **Weakness 3 — tables still prose** (converted to HTML *text*; no structured querying).
- **Weakness 4 — nothing targets FDV-KNOW.**
- **What it proves for us:** zero-shot, prompt-only, no-training work is publishable on this benchmark — exactly our resource profile.

### 6.2 TART (Lu et al., NAACL 2025 Findings)
Tool-augmented table reasoning: table formatter, tool maker (generates executable code), explanation generator. Our closest ancestor for tables-as-data. **But:** all modules are **fine-tuned** — out of reach without training compute — and it was evaluated on **single-table, closed-domain** benchmarks, never long hybrid documents. We borrow the insight, not the method.

### 6.3 FISCAL (2025)
Synthetic-data framework that **trains** a lightweight numerical-claim verifier. Requires training → not our lane; also classification-only, no explanations.

### 6.4 FinVerBench (2026)
Positions FINDVER/FISCAL as classification-framed. Useful for related-work positioning; different task.

### 6.5 Adjacent methods (citations to know)
**PoT / PAL** (2022–23): canonical code-execution-for-math papers. **ProTrix**: plan-then-reason, routes steps to program vs. text execution. **OpenTab**: BM25 + SQL over tables. **GraphOTTER**: graph representations for merged/nested tables.

### 6.6 The gap statement
> No published FINDVER approach executes code for arithmetic, parses tables into queryable structures, attacks the ~68% retrieval-recall ceiling, targets FDV-KNOW with a knowledge component, or evaluates explanation faithfulness — despite the benchmark's own error analysis and limitations section pointing at exactly these gaps.

**Honesty requirements when using it:**
1. Never claim "first to use Python for arithmetic" — PoT/PAL standardised the technique years ago. Correct framing: *an established technique that no published approach has applied to FINDVER, whose own error analysis shows it is needed.* "Known technique, new setting, careful analysis" is a respectable contribution class.
2. The search behind this section is not exhaustive. ~~**Outstanding week-1 task:** check the FINDVER leaderboard for recent entries and run a Google Scholar cited-by sweep before repeating any "nobody has done X" claim.~~ **DONE 3 Aug 2026.**

   **The leaderboard does not exist as a submission target.** The paper promised one: *"we will develop and maintain an online evaluation platform where researchers can test their models and participate in a public leaderboard."* No URL appears in the paper or the repository, and there is no evidence it ever launched. What did exist was email submission, and the repository has retired it: *"Since the test set ground truth is now publicly released, the test split can be evaluated locally with the same procedure as `testmini`. Submitting results by email is no longer required."* (README, update July 2026). **So there are no leaderboard entries to check, now or previously.** This also explains §2.6's finding that test labels are present on disk.

   **Citation sweep, via the Semantic Scholar citation graph for arXiv:2411.05764: 23 citing papers. MACE is the only published method found evaluated on FINDVER.** Everything else either cites it as related work or is a competing benchmark: FinVerBench, AuditFraudBench, ClaimDB, TSVer, SciVer, FinTrust, FinLFQA, FinMRAGBench, FinReflectKG-MultiHop, and several financial-misinformation benchmarks.

   **Limits of this sweep, stated so the claim is not overread.** It is abstract-level screening across 23 citing papers plus keyword search, not a full-text sweep. It supports **"we found no other method evaluated on FINDVER"** and does **not** support "nobody has." Use the first phrasing. One paper worth a later look for technique rather than numbers: *Rethinking Reasoning-Intensive Retrieval: Evaluating and Advancing Retrievers in Agentic Search Systems* (2026), which did not evaluate on FINDVER, so its recall figures are not comparable to our 68.01%.
3. Sit with "why has nobody done the obvious thing?" Likely: niche benchmark, ~18 months old, field moved fast. Possible: someone tried and gains were small. The ablation reveals which — either outcome is a finding.

---

## 7. The Skills, in Implementation Detail

### 7.1 **[RESOLVED]** Table Normalizer — much cheaper than planned

> **[CONTRADICTED BY MEASUREMENT 11 Aug 2026 — read this before the section below.]**
>
> This section's central claim, that `read_html` gives "structure preserved, no custom parser" and
> that the structural parsing problem "largely disappears", **is false on this corpus.** Measured
> across 1,079 real data tables from 30 reports:
>
>     columns are integers only           100.0%     header detection never works
>     merged-cell duplication              84.8%     in the first three rows
>     null fraction, whole frame            0.56
>     columns entirely null                 0.20     layout spacers
>     column inflation vs the text copy     1.95x    median 1.83x
>
> **Not one table in 1,079 returned usable column names**, so the `.loc` lookup this tier is for is
> impossible on every table without a custom post-processor. pandas returns **the numbers without
> the structure**. A four-column income statement comes back as 17x12 with the merged header
> duplicated across nine columns and half the cells NaN.
>
> Also measured: **`read_html` raised on 0 of 1,228 tables**, so step 3's `try/except` fallback
> trigger fires on nothing and must be the numeric round-trip instead. And only **64.6% of real
> data tables round-trip their numbers perfectly**, so about a third lose data silently.
>
> **Step 1 is confirmed and is trivial.** The mapping is ordinal: the table count equals
> `len(html_tables)` on 255/255 reports, and numeric content aligns at 0.946 against 0.195 for the
> neighbouring table. One line, not a task.
>
> **Step 2's scaling trap is confirmed and its remedy is decided.** The phrase is findable on 44.6%
> of data tables, but **19.5% of those carry a carve-out** ("in thousands, except per share data"),
> so "multiply through" would corrupt per-share rows on 821 tables. **Store a `scale` attribute,
> never mutate the numbers.** "Not found" stays unknown and must not become `scale = 1`.
>
> **Consequence: Tier 1 is the code sandbox (§7.2), and tables-as-DataFrames is dropped.** The
> failure this tier exists to fix is arithmetic, not lookup, and code execution fixes it on numbers
> read from the pipe-delimited text. `src/table_parser.py` was written and deleted the same day,
> committed at `c4c0d7c`. Full detail in the build log entry for 11 August, afternoon.
>
> **Honest caveat:** post-processing the frames was never attempted. The argument against it is
> that a structural repair has no ground truth to validate against, unlike the numeric round-trip.
> That is reasoning, not evidence.


The previous version of this plan budgeted heavily for a custom parser, because the paper describes tables as flattened pipe-delimited text. **The repository stores them as HTML** in a separate `html_tables` array (~83 per document). pandas parses HTML natively:

```python
df = pd.read_html(html_string)[0]      # structure preserved, no custom parser
```

The structural parsing problem — the part that was expected to consume most of weeks 3–4 — largely disappears. What remains is real but bounded:

**Step 1 — map `html_tables` to `context` indices.** Gold evidence points into `context`, but the high-fidelity table lives in `html_tables`. Establishing that correspondence is now the first task of the module, and it is a data-inspection job, not a parsing one.

**Step 2 — clean cell values.** Cells are strings that *look* like numbers: `"$1,204,500"`, `"(45,300)"` (accounting negative), `"—"`, `"65,300 *"`. Without cleaning, arithmetic silently fails on strings.

```python
import re, pandas as pd

def clean_cell(val):
    if pd.isna(val): return None
    s = str(val).strip()
    if s in ("—", "-", "", "N/A"): return None
    negative = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d.]", "", s)
    if s == "": return None
    return -float(s) if negative else float(s)
```

**The silent-corruption trap: scaling notes.** "(in thousands)" means the cell `210,600` is really 210,600,000. This produces no error — just numbers off by 10³ or 10⁶ that corrupt every downstream check. Detect the phrase near each table; multiply through or store a `scale` attribute.

**Step 3 — the fallback, from day one.** Some tables will still break (merged multi-row headers, ragged rows, nested subtotals). `try/except`: on failure, pass that table to the LLM as raw text — exactly what all prior approaches did for *every* table — so the worst case equals the published status quo, and every parsed table is pure upside. The parse success rate is itself a reportable stat.

**Schedule effect:** this module's estimate drops materially. Time freed should go to Tier 2 (retrieval), which is the harder and more novel pillar.

**[MEASURED 5 Aug 2026] The `type: "table"` flag overstates the real table workload by about a quarter.** Counted across all 255 reports referenced by testmini, 60,871 elements:

| | count | share |
|---|---|---|
| `type == "table"` | 10,991 | 18.1% of elements |
| of those, numeric cells < 10% | 1,843 | 16.8% of tables |
| of those, numeric cells < 25% | 2,967 | 27.0% of tables |
| of those, containing a bullet glyph | 820 | 7.5% of tables |
| **looks like a real data table** (>=2 rows, >=2 cols, >=25% numeric cells) | **8,023** | **73.0% of tables, 13.2% of all elements** |

Filings use HTML tables for layout constantly. A representative non-table "table":

    | ● | Existing Hotel Property Design. Our Gaylord Hotels properties focus on
    the large group meetings and regional leisure transient markets...

That is a bulleted list, and a DataFrame buys nothing for it. **State the Tier 1 table payoff against 13.2% of elements, not 18.1%.** The numeric-cell fraction has p10 0.00, so at least a tenth of flagged tables contain no numbers at all.

**[NOTED 5 Aug 2026] Parsing successfully is not the same as parsing correctly, and the fallback trigger cannot be "did it throw."** `pandas.read_html` returns a DataFrame with headers in the wrong row, merged cells silently duplicated or dropped, footnote rows as data, and spacer columns as all-NaN, and it raises nothing. That is the same silent-failure class as the week-1 loader bug and the Ollama eviction.

**The validation to use, because the data is redundant by construction.** Each table exists twice: as HTML in `html_tables` and as pipe-delimited text in `context`. Extract every numeric token from the text version and every numeric value from the parsed DataFrame; if the DataFrame is missing numbers present in the text, the parse dropped data and the element falls back to raw text. Plus cheap structural checks: at least 2x2, column names not all `Unnamed: n`, non-null density above a threshold. This mirrors the evidence asserter's rare-token approach and `tokenize` already exists.

**Two separate risks, both measurable offline with no model calls**, and both should be measured before this tier is built:

1. **Mapping.** Can a `context` element be matched to the right `html_tables` entry? Gold indices point into `context`, not `html_tables` (data trap 6), so the mapping has to be built explicitly.
2. **Parsing.** Does that entry survive `read_html` with correct headers, judged by the numeric round-trip above?

**Nothing needed for this is installed.** `pandas`, `lxml`, `bs4` and `html5lib` are all absent; `read_html` needs pandas plus at least one parser backend.

**One thing a schema cannot carry.** Row and column labels do not encode magnitude. A nearby "(in thousands)" changes the true value by 10^3 and produces no error (data trap 7), so units and period must be captured as table metadata alongside the schema, which is what §7.3's "header/unit/period metadata" means.

### 7.2 Code Sandbox

> **[DROPPED ON MEASUREMENT 11 Aug 2026.]** This skill is not being built. Measured from stored
> responses on the 250 numeric claims, no new run:
>
>     gold value present in the response   161  64.4%
>     correct verdict                      160  64.0%
>     both                                  87  34.8%     (41% expected under independence)
>     correct verdict WITHOUT the value     73  29.2%
>     magnitude errors (x10^3 or x10^6)      8   3.2%
>
> Three things kill it. **Prose arithmetic already produces the correct value 64.4% of the time**,
> so the headroom is 36 points, not the near-total gap §8 implies. **The magnitude trap fires on
> 3.2% of numeric claims**, so the `numeric-val-242` example this section is built on is a one-in-
> thirty event. And **computed-value correctness barely predicts verdict correctness**, which
> breaks the tier's premise that fixing computation fixes verdicts.
>
> **A correction to this section's own argument.** `numeric-val-242`'s first error, treating
> $0.015 million as $15, is a *transcription* error. A model that writes `b = 15` into Python gets
> the same wrong answer. The sandbox fixes only the second error, the false equality. This section
> claimed it fixed both.
>
> Full detail in the build log for 11 August, evening.

Extract fenced Python from model output; execute with whitelisted builtins (pandas/math only), no filesystem/network, ~10 s timeout; return stdout **or the traceback** to the model; retry on exceptions (feeding the error back lets the model self-correct). ~30 lines. Never execute model code unrestricted.

**[NEW]** Validate against `execution_result` (§2.5): for every `numeric` example, the sandbox's computed value can be compared directly to the gold figure. This is a free correctness signal on the code-execution skill in isolation, independent of the final label.

**[MEASURED 2 Aug 2026] The trial run produced a worked instance of exactly what this skill exists to prevent, and it scored as a success.** `numeric-val-242`, gold entailed, predicted entailed, gold evidence fully retrieved, counted correct. Its reasoning contains two independent errors:

    Total Net Loss = $15,800,000 + $0.015 million = $15,800,015
    The calculated total net loss ($15,800,015) matches the claimed total ($15.815 million).

The first line treats `$0.015 million` as $15 rather than $15,000, a factor of 1,000 — the magnitude trap of §2.3 and §3.9, occurring in our own pipeline for the first time. The second then declares two numbers equal that differ by about $15,000. The errors happen to leave the verdict unchanged, so nothing automated flags it.

Three consequences, all of which land outside this section:

1. **A model computing `15800000 + 0.015e6` in Python cannot make either error.** This is the strongest concrete argument for the sandbox so far, and it is a real example rather than an argument from first principles. It is a candidate figure for the paper.
2. **Label accuracy overstates reasoning quality on the `numeric` subset**, and we now have an instance rather than a concern. This is the per-error-category analysis in §5.3 justifying itself.
3. **The error taxonomy in §9 needs a "correct label, invalid reasoning" category.** Without it this failure is invisible: it is not a format failure, not a retrieval failure, and not a label error, and the only automated signal — the label — says the example passed. Detecting it requires checking the explanation, which is the faithfulness verifier in §7.5, currently in the stretch band (§12.3).

Whether this is common or a one-off is unknown. The `numeric` subset was 4 of the 12 trial examples.

### 7.3 Retriever
Local embedding model + BM25, merged by reciprocal rank fusion; per-sub-claim queries once decomposition lands; tables kept whole as chunks with header/unit/period metadata. Evaluated standalone against gold `relevant_context` indices before any end-to-end run. **[MEASURED]** Also sweep *k* — §4.6 shows it is a wall-clock multiplier as well as a recall lever.

**[MEASURED 2 Aug 2026] The placeholder retriever fails by ranking, not by capacity, so *k* is the wrong lever.** Over the 12 trial examples, 36 gold elements:

    fully present (3/3 witnesses)    22 / 36    61%
    partially present               1  / 36
    absent (0/3 witnesses)          13 / 36
    claim-level, all gold present    4 / 12    33%   (offline over all 700: 31.6%)

**Of the 14 gold elements not fully retrieved, 13 scored `0/3` and one was partial.** A `0/3` element was never retrieved at all; a `2/3` pattern would have meant retrieval found the element and *k* cut it off. Almost none of the misses are the second kind. Raising *k* therefore buys very little recall while costing wall-clock linearly (§4.6), which is the opposite of the trade this section assumed when it listed the *k* sweep. Sweep *k* for the paper's completeness, but do not expect it to move recall much, and do not treat it as a substitute for a better ranker.

The claim-level 33% lands within 1.4 points of the 31.6% measured offline over all 700 claims, so the 12-example stratified sample is representative on this axis.

### 7.4 Glossary Lookup — and an honest assessment
**Not a model.** A data file (finance terms → plain-English definitions) plus a lookup, feeding whichever model is reasoning. Build by seeding from **FDV-KNOW dev-set failures** — add the specific concepts the baseline got wrong, rather than writing a finance dictionary from scratch. At runtime a cheap step spots glossary terms and pastes matched definitions into the reasoning prompt.

**Will it move accuracy? Honestly: the most speculative of the five skills.** Big cloud models likely already *know* common finance definitions; their FDV-KNOW failures may be *application* failures, which a glossary does not fix. Where it more plausibly helps: the **edge 3B model**, which genuinely lacks memorised domain knowledge — injected definitions could let it handle cases it would otherwise escalate, serving the **cost story** more than the accuracy story.

**[MEASURED]** Week-1 testing gives a concrete candidate term: the 3B model mishandled the meaning of "Level 2" in the fair-value hierarchy, treating a definitional paraphrase as contradicting evidence (§3.10). Fair-value hierarchy levels are exactly the kind of entry this glossary should contain, and this is a real observed failure rather than a hypothetical one.

### 7.5 Faithfulness Verifier
Post-hoc pass over the generated explanation: (a) does each cited figure exist at the cited coordinates? (deterministic Python where DataFrames exist); (b) re-execute each arithmetic step; (c) check the final comparison; (d) judgment-level "does this step follow" — edge screen, cloud confirm on failure. Outputs per-step grounded/ungrounded; can trigger one retry. **Doubles as the new metric** (§3.10) — valuable even if the retry loop is cut for time.

**[MEASURED]** We already have a real test case: the 3B model's `ie-val-0` explanation, where step-level checking would flag the invalid Level-2 argument while passing the correct arithmetic step.

### 7.6 Priority structure: three pillars + a foundation + a bonus
- **Foundation:** Table Normalizer — enables both pillars below. *Cost revised down (§7.1).*
- **Pillar 1 — retrieval** (recall ceiling): the hard cap nothing downstream can fix.
- **Pillar 2 — code execution** (computation error): deterministic arithmetic. *Independently validated by the benchmark's own gold Python (§2.5).*
- **Pillar 3 — faithfulness verifier** (explanation trustworthiness + new metric).
- **Bonus — glossary:** worth building and measuring; not load-bearing.

### Explicit non-goals
No fine-tuning or pretraining (no compute; MACE proves it unnecessary). No agent-framework dependency. No long-context experiments. No hardware purchases at this stage.

---

## 8. Build Order — One Module at a Time (the ablation IS the paper)

> **[REVISED ON MEASUREMENT 11 Aug 2026.]** **Tier 1 is not being built.** Both halves were
> measured and both failed: `read_html` loses table structure on 100% of tables (§7.1), and prose
> arithmetic already produces the correct value on 64.4% of numeric claims with computed value
> barely predicting verdict (§7.2). **Tier 2 retrieval is measured and its end-to-end value is
> small** — perfect recall is worth +3.6 points on FDV-IE alone and nothing elsewhere. **Tier 3
> glossary is unmotivated** until the 49 knowledge failures are read.
>
> **What replaces them, in priority order:** (1) fix the refuted bias in the prompt, worth up to
> 21% of the benchmark; (2) the 3B/7B agreement gate, which already ties condition 2 at 36% of the
> cloud calls; (3) always escalate numeric; (4) test self-consistency as a cheaper gate; (5) test
> k=5. Full list, with the evidence for each, in `working_state.md` under "THE PLAN FROM 11 AUGUST,
> EVENING."


Rationale: (a) build everything at once and you cannot attribute any change; (b) "baseline 71% → +code exec 76% → +decomposed retrieval 79% → +glossary 80%" is a publishable result structure — one undifferentiated system is not; (c) each module maps to a named FINDVER error category, so the ablations align with the original taxonomy.

| Tier | Module(s) | Error category attacked | Status | Payoff / risk |
|---|---|---|---|---|
| — | Harness: loader, stratified sampler, logging, label extractor, evidence assertion, **run loop** | — | **in progress** · loader + sampler done 31 Jul; label extractor and logger done 1 Aug; evidence assertion, run loop and placeholder retriever all done 2 Aug, with a committed 26-check harness test | **done** | Prerequisite for everything; small but non-optional (§11.8–11.9). The run loop was missing from the original list of five and is not optional. Remaining before the first run: Ollama client, config file, entry point |
| 0 | **Baseline:** plain CoT, RAG, ~100 stratified testmini examples — (i) edge-only, (ii) cloud-only | reference point | pending keys | Mandatory; answers "has 2026 closed the gap?" and sets both ends of the routing curve |
| 1 | **Code execution + tables-as-DataFrames** | Computation + extraction | ready to start | Highest-certainty gain; foundation cost revised down (§7.1) |
| 2 | **Claim-decomposed + hybrid retrieval** | Recall ceiling | — | Clean standalone metric; nobody has attacked it; also cuts runtime (§4.6) |
| 3 | **Glossary** | Domain knowledge | — | Smallest expected gain; one real failure case already observed |
| 4 | **Faithfulness verifier** | Explanation quality (new metric) | — | Stretch; becomes centrepiece under Backup Plan A; one real test case already observed |
| 5 | **Routing-policy sweep** | Cost | — | Cheap once the pipeline exists; produces the cost-accuracy curve |

Working principles: iterate on a ~100-example **stratified** slice (§2.4); hand-label ≥25 failures with the four-category taxonomy every round; keep full traces of every prompt/response/chunk/snippet.

---

## 9. Evaluation Plan

**Metrics**
- Entailment accuracy: overall + per subset; testmini (700) during development; final numbers on the test split (1,700 examples), which ships with labels, so scoring can be local as well as via the leaderboard.
- **[NEW 31 Jul] Every accuracy is reported twice, from the same stored predictions.** *Strict:* `unparseable` is its own bucket, counted as wrong for the headline figure, with its rate reported alongside. *FINDVER-compatible:* `unparseable` is coin-flipped with a fixed seed, used only when placing our number beside a published one. The official evaluation silently imputes these (§11.8), so the two are not the same measurement. The **gap between them quantifies how much of a small model's official score is imputation rather than reasoning**, which is itself a reportable result. Scoring is cheap and re-runnable, so both come from one 8-hour run.
- **[NEW 1 Aug] Strict is the working number, not merely the honest one.** Every internal comparison is strict against strict: edge-only vs cloud-only vs routed, *k*=4 vs *k*=10, prompt v1 vs v2. Strict has no random component, so a difference between two runs is a real difference. FINDVER-compatible cannot do that job, for two reasons. It injects a coin flip, which puts noise in every cell. Worse, the flip **inflates weak configurations more than strong ones**, because a configuration with more unparseables has more examples to guess on, so an ablation table scored that way would misreport which change helped. Its only legitimate use is the cross-table comparison in §9.1. Worked example, 100 examples with 50 correct, 20 wrong, 30 unparseable: strict reports **50%** beside "unparseable 30%"; FINDVER-compatible reports about **65%**. Same run, same stored outputs, 15 points apart, and all 15 are imputation rather than reasoning. That gap is the reportable result; the strict number is what the paper claims the system does.
- Evidence recall vs. gold `relevant_context`, per retrieval variant (whole-claim dense / +BM25 / +decomposition / varying *k*).
- **[NEW]** Computation accuracy on the `numeric` subset: agent's computed value vs. gold `execution_result` — isolates arithmetic correctness from verdict correctness (§2.5).
- Faithfulness: % of explanation steps verifiable against the document (new metric).
- **[NEW 2 Aug] The error taxonomy needs a `correct label, invalid reasoning` category, and it cannot be detected from the label.** Found in the trial run: `numeric-val-242` scored correct with gold evidence fully present, on reasoning containing a 1,000× unit error and an equality assertion between two numbers differing by ~$15,000 (§7.2). It is not a format failure, not a retrieval failure, and not a label error, so every automated signal we currently compute says it passed. Two things follow. **Any per-category error analysis based only on labels systematically undercounts this category to zero**, which matters because §5.3 names that analysis as part of the contribution. And on the `numeric` subset the gold `execution_result` (§2.5) gives a cheap partial detector with no model calls, since the agent's computed value can be compared to the gold figure even when the verdict is right. Full detection on the other two subsets needs the faithfulness verifier (§7.5).
- Cost: tokens and $ per example, per configuration — the currency of the routing curve.
- **[NEW]** Wall-clock per example, per configuration — a real constraint at these throughputs, and part of the deployment story.

**Comparisons**
- FINDVER 2024 originals (77.2 / 75.7; humans 93.3 / 86.7) and MACE's published numbers. **[GAP FLAGGED 3 Aug 2026] MACE's actual accuracy figure is nowhere in this document.** §6.1 records only "claims SOTA/parity" and the 27–92B scaling remark, yet §5.3 states the contribution as matching the all-big-model design, and §9.2 condition 3 is built to compare against it. The number we are trying to match is therefore unrecorded. Pull it from arXiv 2604.17225 and put it here. **Also note: since the project is RAG-only (§3.3), the comparable Claude-3.5-Sonnet figure is 75.0% RAG, not 77.2% long-context.** Do not quote the long-context column anywhere.
- **[REVISED 3 Aug]** Edge-only vs. cloud-only vs. **all-big-model pipeline** vs. routed, at each ablation tier. The three-condition version of this line was missing the condition §5.3's claim is actually stated against. Full design in **§9.2**.
- Cheap models + skills vs. expensive model without skills.
- **[NEW]** Our retrieval vs. the authors' own `retriever/` implementation, which ships in the repo — an apples-to-apples baseline rather than a reimplementation.

### 9.1 **[SETTLED 30 Jul 2026]** Baseline strategy: reuse the paper's numbers, extend with new models

Agreed with the professor at the 30 July meeting. Re-running the 16 models the authors already evaluated is not affordable in 30 days (§12.1) and adds nothing, since their outputs and scores ship in the repo.

1. **The paper's published results are the historical baseline, used as-is.** They are dated, and saying so is part of the framing rather than a weakness.
2. **Extend the cloud row with two models released after the paper** (2025–2026). Provider flexible; the professor indicated Anthropic keys can be provided alongside DeepSeek and Qwen. Cloud runs cost hours, not nights, so this is cheap.
3. **Extend the edge row with local models the paper did not evaluate**, run on this machine. This is where the wall-clock goes, and it is the row the venue actually cares about.

**The comparability constraint this creates.** The published numbers were produced with `gpt-4o-mini` extraction **and coin-flip imputation of unparseable outputs** (§11.8). Scoring our new models strictly and placing them beside those numbers would compare two different measurements, and would understate our models precisely where they fail the output format, which at 3B is ~45% of the time. **Any table that mixes our numbers with published ones must use the FINDVER-compatible scoring.** The strict numbers are reported separately, alongside the unparseable rate. This is no longer an optional second view; the professor's baseline strategy makes it load-bearing.

**The reusable asset this creates.** `outputs/testmini_outputs/rag/processed_cot_outputs/` ships 700 records for each of 16 models with both raw responses and extracted labels — 11,200 pairs. Any analysis of *output behaviour* rather than accuracy (format compliance, verdict placement, response length, refusal patterns) can be run across all 16 models at zero compute cost, and our new models slot into the same analysis. This is the cheapest source of paper-grade evidence available and it is already on disk.

**Error analysis protocol:** every iteration, sample ≥25 failures, hand-label with the taxonomy, track the distribution over time — the evidence for "module X fixed category Y."

### 9.2 **[NEW 3 Aug 2026]** The baseline design: four conditions, not three

> **[CONDITION 3 HAS COLLAPSED INTO CONDITION 2, 11 Aug 2026.]** Condition 3 is defined below as
> the cloud model in **every pipeline role**. With tables-as-DataFrames (§7.1) and the code sandbox
> (§7.2) both dropped on measurement, **the pipeline has no roles left**: it is one model call plus
> an escalation decision. Condition 3 is therefore condition 2, already measured at 77.0% (flash)
> and 77.3% (pro).
>
> **Consequence for §5.3.** "Match condition 3 at a fraction of the cost" no longer names a
> condition that exists separately. The replacement is the fallback §5.3.1 recorded on 10 August:
> **condition 2 at 77.0% is the bar**, and the routed rule matches it (76.6%, p = 0.858) while
> calling the cloud on 36% of claims.
>
> **This is a live question for the professor, not a settled rewrite.** Raise it with the §5.2
> verifier-row problem at the next meeting.


The obvious three-condition design — edge alone, cloud alone, ours — has a hole in it. It cannot support the claim in §5.3.

| # | Condition | Runs on | What it establishes |
|---|---|---|---|
| 1 | 3B, RAG, one call, no pipeline | local | edge-only floor |
| 2 | Cloud model, RAG, one call, no pipeline | cloud | single big call |
| 3 | Cloud model in **every** pipeline role | cloud | all-big-model, ≈ MACE |
| 4 | 3B + cloud routed | local + cloud | ours |

**Condition 3 is a baseline that *does* run through the pipeline, and it is mandatory.** §5.3 claims we "match or beat the all-big-model version at a fraction of the cost," and that claim cannot be made without measuring the all-big-model version. The instinct to keep every baseline outside the pipeline is correct for 1 and 2 and wrong for 3.

**§5.3 already encodes this** and it was missed on first reading: *"always escalate ≈ MACE's design; never escalate = edge-only floor; the interesting result lives between."* Condition 3 is always-escalate, condition 1 is never-escalate, and ours is a point on a curve the plan already committed to producing. Tier 5's routing sweep fills in the curve between them.

**The objection that condition 3 unfairly favours the stronger model is backwards.** That is the number the paper needs. If 3 ≈ 4, the cost claim is proven. If 3 crushes 4, the claim is weaker and that has to be discovered here rather than by a reviewer.

**"No pipeline" does not mean no RAG.** The pipeline is RAG-only by the professor's decision and the filings are far too long to pass whole. Every condition uses the **same retrieval, same *k*, same slice, same prompt version, same `num_ctx`, temperature 0, same label extractor.** Only the pipeline machinery varies, or the delta is not attributable to anything.

**Framing, recorded so it does not drift.** "We beat the cloud model" is not the headline. If 4 beats 2, report it, but a reviewer answers it with "you beat a single-prompt use of a cloud model, which nobody deploys." Beating condition 2 is a bonus; **matching condition 3 at a fraction of the cost is the paper.**

**Cost.** Conditions 1 and 4 are local, ~12 h each at 102 examples, so two nights. Conditions 2 and 3 are cloud, hours not nights. Affordable before any GPU arrives.

**Scoring.** All four are internal comparisons, so all four are **strict versus strict** (§9). FINDVER-compatible scoring is only for the one table where our numbers sit beside published ones (§9.1); its coin flip inflates weak configurations more than strong ones and would misreport which change helped.

#### **[NEW 3 Aug 2026]** When each condition is measured, and what invalidates it

The four conditions are **not** all measured at the same point in the schedule. They split by what they depend on, and getting this wrong wastes nights.

| Condition | Depends on | Can be measured | Invalidated by |
|---|---|---|---|
| 1, edge-only | retrieval only | as soon as retrieval is frozen | a retrieval change |
| 2, single big call | retrieval only | as soon as retrieval is frozen | a retrieval change |
| 3, all-big-model pipeline | retrieval **and** the pipeline | only once the pipeline exists | a retrieval change **or** a pipeline change |
| 4, ours | retrieval **and** the pipeline | only once the pipeline exists | a retrieval change **or** a pipeline change |

**So the order is: conditions 1 and 2 early, conditions 3 and 4 late, all four together at 700.** It is neither "all four at the start" nor "all four at the end."

This preserves what the professor asked for at the 30 July meeting, namely that both ends be measured before the routed system is built (§14 item 9). Conditions 1 and 2 **are** those two ends, and neither needs the pipeline to exist.

**[CORRECTION 3 Aug] Condition 3 is not a static reference point.** An earlier framing treated conditions 1, 2 and 3 alike as fixed baselines measured once. That is wrong for condition 3. It runs the cloud model in *every pipeline role*, so it moves whenever the pipeline moves, exactly like condition 4. Only conditions 1 and 2 are stable across pipeline changes.

**The module-by-module comparison is condition 4 only.** The result structure in §8 — baseline, then plus code execution, then plus better retrieval — is a claim about which module contributed what **inside our system**. There is no claim attached to "condition 3 with only Tier 1 built," so it is never measured. Condition 3 is run **once, against the frozen final pipeline**, which is where §5.3's claim actually lives.

**Retrieval is the variable that invalidates everything.** Change a pipeline module and only conditions 3 and 4 move. Change retrieval and **all four** move, because §9.2 requires every condition to share the same retrieval. This is the structural reason retrieval is settled first.

**And settling it costs no nights**, because the retriever is chosen on **recall alone**, which needs no model calls (§3.4, §12.1). Pick the retriever for free, freeze it, and only then start paying for runs. Any condition measured before retrieval is frozen is a throwaway number.

**Machine choice is part of the freeze.** Per §13 item 11, results from different machines cannot sit in one table. So the decision of *where* conditions 1–4 run must be made **before condition 1 starts**, not discovered afterwards. Running condition 1 on the MacBook and condition 4 on the server means re-running condition 1.

#### **[NEW 3 Aug 2026]** Which conditions run at 700, and which stay at 102

**The governing rule: a 700-run cannot be compared against a 102-run.** Both sides of any comparison need the same *n*. This decides the whole allocation.

| Condition | At 700? | Why |
|---|---|---|
| 3, all-big-model pipeline | **mandatory** | The close comparison. The ±10-point margin at n=102 makes "4 matches 3" unprovable, and this pair is the only reason full-700 is worth buying at all. |
| 4, ours | **mandatory** | Other half of the same comparison. |
| 1, edge-only floor | **include** | Nearly free on the GPU, and it pins the floor precisely. |
| 2, single big call | **drop first** | The bonus comparison, not the claim. First thing to cut if cloud quota is tight. |

**Ablations stay at 102.** Running every tier at 700 multiplies cost for no benefit, since ablations compare against each other and only need internal consistency. The sequence is: iterate at 102, freeze the winning configuration, then run the final comparison at 700.

**Cloud quota is the binding constraint here, not wall-clock.** Condition 3 runs the cloud model in *every* pipeline role, so at 700 examples it is by far the largest quota consumer: roughly (roles per example × 700) calls, against 700 for condition 2 and only the escalations for condition 4. Cloud access is provided by the professor and is not unlimited (§11.2), so **confirm the quota with him before committing to conditions 2 and 3 at full scale.** If quota is short, the fallback that preserves the claim is conditions 3 and 4 at 700 with condition 2 left at 102, clearly labelled as such.

**Sample size.** At n=102 the margin is ±10 points, so "4 matches 3" is **unprovable** — a tie and a 5-point loss are indistinguishable. This is the concrete reason the full-700 run is the first thing GPU compute buys (§12.3, §13 item 11).

#### Two results tables, one variable each

Holding retrieval constant across conditions 1–4 does **not** defeat the purpose of building a good retriever. It is what makes the comparison mean anything: giving the cloud model a worse retriever would make any win attributable to retrieval rather than to architecture.

- **Pipeline table.** Retrieval fixed, architecture varies across conditions 1–4. Isolates routing.
- **Retrieval table.** Architecture fixed, retrieval varies: whole-claim dense, +BM25, +decomposition, *k* sweep. Isolates the retriever.

The retrieval table splits into two halves that answer different questions and cost wildly different amounts.

**Half one, the recall table, asks: did the retriever fetch the right chunks?** Retrieved chunk indices are scored against gold `relevant_context`. **No architecture column at all**, because retrieval runs before any model call — minutes, no LLM involved (§12.1). Report all three metrics per the §3.4 rule. The measured starting points are in §3.4: `text-embedding-3-large` 68.01% macro-average, `bm25` 65.16%, our token-overlap placeholder 57.54%.

**Half two, the end-to-end delta table, asks: did better retrieval actually change any verdicts?** Run the full pipeline twice, once with the old retriever and once with the new one, holding everything else fixed, and compare final accuracy. Shape of the result:

    pipeline + retriever A     __._% accuracy
    pipeline + retriever B     __._% accuracy
                               delta = __._ points

**Why half one is not enough.** Recall is a *proxy*. A higher recall number does not automatically mean better answers: the model may already have been right without the gold chunk, or still wrong with it in the prompt. Without the delta table the paper can only say "we raised recall by N points," and a reviewer is entitled to ask whether that changed anything. The delta table is what converts a retrieval improvement into an accuracy claim.

**Why the architecture must be fixed, and to what.** Retrieval is the variable under test, so architecture cannot also move or the cause of any accuracy change is unattributable. It is fixed to **our edge-cloud pipeline**, because that is the system the paper claims. Measuring whether better retrieval helps a bare 3B would characterise a system we are not proposing.

**Cost.** Every retrieval variant needs a **full run**: about 12 h per variant at 102 examples on the MacBook, so comparing two retrievers is two nights. Cheap on the GPU server. This is why it sits in Band B while half one sits in Band A.

**The risk this split manages.** §12.3 names the recall table as one of the results that carry the paper if Band B never opens. **[14 Aug 2026] The delta half is now measured and it is close to zero** (§2.8.1, §2.8.2), so the recall table carries the paper as a retrieval result and the delta table is a negative result rather than the stronger one. The delta table is the stronger result and the one that depends on compute we do not yet have. Build and report half one first regardless of what happens with the server.

**There is no configuration in which the cloud model retrieves its own evidence.** A model behind an API has no access to the filing. Retrieval here is BM25 plus embeddings plus plain Python (§3.7), a mechanical step that runs before any model call.

---

### 9.3 **[NEW 3 Aug 2026]** Which number are we actually trying to beat?

Written because the question was asked and could not be answered cleanly from the existing sections. Three different targets on three different axes, and they are routinely blended.

| Axis | Target | Where we stand | Band |
|---|---|---|---|
| **Evidence recall** | **68.01%** macro-avg (`text-embedding-3-large`, k=10) | placeholder retriever at **57.54%** — currently *below* baseline | A |
| **Retrieval → accuracy delta** | **no target exists** | not measured | B |
| **Entailment accuracy** | our own condition 3 (§9.2), *matched* not beaten | not measured | A/B |

**[UPDATED 3 Aug 2026] The external accuracy reference points now exist.** They are context for the table, not the claim.

    FINDVER 2024 best, RAG        Claude-3.5-Sonnet  75.0%     verified against the PDF, 3 Aug
    FINDVER 2024 best, long-ctx   Claude-3.5-Sonnet  77.2%     NOT a comparison target, RAG-only project
    MACE best on FINDVER          Qwen-235B          0.76      verified against Table 8, 3 Aug
    MACE with an 8B model         Llama-8B           0.68      verified against Table 8, 3 Aug

So MACE's headline sits about one point above the 2024 RAG best, which is what "on par with the best models" means in their own words. **Nobody has moved FINDVER accuracy far, and nobody has touched retrieval at all.**

**Recall: 68.01%.** This is the setup every published FINDVER approach copied, and the only one of the three with a published number to clear. Report all three metrics per §3.4; the macro-average is the one that may sit beside a published figure. Note the first job is passing 68.01%, not passing our own placeholder's 57.54%.

**The delta: there is nothing to beat, and that is not a problem.** No published delta exists because nobody has attacked FINDVER retrieval (§6.1, Weakness 2). It is a number we *produce* — "our retrieval change was worth N accuracy points" — not a bar we clear. Measured by running the full pipeline twice with only the retriever swapped.

**Accuracy: primarily our own conditions. We are not trying to beat MACE.** §5.3's claim is about **cost**, not accuracy. MACE runs 27–92B models; we run 3B plus cloud. Matching at a fraction of the cost is the result. Beating it outright is neither the goal nor likely, and writing the paper as though it were invites the reviewer to score us on the axis where we are structurally weakest (see also §13 item 4 on the leaderboard).

Three comparisons, in descending order of rigour:

1. **Internal, and this is the actual claim.** Condition 4 against conditions 1–3 (§9.2). All run by us, strict against strict, same slice, same prompt, same *k*. Beat condition 1 clearly; match condition 3. The only comparison where every variable is controlled.
2. **Condition 3 is a stand-in for MACE, not MACE.** We cannot run MACE — AutoGen, different models, different infrastructure. Condition 3 reproduces its *design principle*, the big model in every role, inside our system. Say so explicitly in the paper rather than implying we ran their method.
3. **Cross-paper, which is context rather than proof.** Our numbers beside 75.0% and MACE's published figure, one table, **FINDVER-compatible scoring** per §9.1, with the model and retrieval differences stated.

**Two recurring mistakes this section exists to prevent.** MACE's 67.91% recall is **not a target** — it is FINDVER's own retrieval copied unchanged, listed in §6.1 as Weakness 2. And the comparable Claude-3.5-Sonnet accuracy is **75.0% RAG, not 77.2% long-context**, because the project is RAG-only (§3.3).

---

### 9.4 **[NEW 11 Aug 2026] THE OVERFITTING LIMIT, and the split that fixes it**

> **[PARTLY OVERRIDDEN 27 Aug 2026 by the professor.]** The develop-on-testmini, report-on-`test.json`
> protocol below stands and produced every reported number. What is void from 27 August is the rule
> that a component motivated by reading `test.json` output may not be built. His reasoning: the
> system has **no trained parameters**, and FINDVER **ships test splits only**, so there is no
> training split any method could have used. The accepted cost is that our design is now optimised
> for FINDVER, which is why a second benchmark is on the after-workshop list. See
> `working_state.md`, 27 August. The statistical warning below is untouched and still binds: several
> rounds of "try a wording, check the split" fits noise regardless of who approves it.

**This became a live constraint the moment prompt v2 worked.** It is a protocol decision, not a status note, and it should be settled before any further prompt iteration.

#### The problem, stated plainly

**All 700 testmini claims are simultaneously our development data and our reported result.** Prompt v2 was written by reading failures drawn from those 700 (§2.11), tested on those 700, and its 79.9% is reported from those 700.

**One edit is defensible and disclosable.** It was motivated by a mechanism found in the data and it changed one clause; the result stands with a sentence in Limitations saying the prompt was developed on the evaluation set.

**Three or four rounds of "try a wording, check the 700" is not.** That fits noise. With a per-run noise floor of roughly one claim in ten (§2.3.2) and 700 claims, a few points of apparent gain can be manufactured by iteration alone, and **every number in the paper becomes optimistic by an unknown amount that we cannot estimate or bound.**

**This is a sharper version of a limit already recorded.** The plan already notes that the 102-claim slice functions as a development set and that ~15% of any final 700 number comes from examples we optimised against. **Doing it at n=700 is worse, because the overlap is 100%.**

#### The way out, and it is available today

**`test.json` ships 1,700 examples WITH REAL LABELS.** The original plan's assumption that test labels are withheld is wrong and was corrected on 29 July (§2.6); two independent counts, ours and MACE's Table 2, agree on the size.

    testmini    700 claims     development. Read failures here, iterate prompts here.
    test      1,700 claims     report here. Touched once, at the end.

**That makes the paper substantially harder to attack**, and it costs one larger run at the end rather than any change to how we work now.

**Cost, from measured throughput.** 1,700 claims is 2.43x a testmini run: about 195 minutes for the 3B on the GPU, and roughly 12 CNY for flash against the 110.24 remaining. Both are affordable. The 7B at 1,700 is about 390 minutes, which is one overnight job.

**What it does not fix.** The retriever, `k`, and the local model were all chosen against testmini too. Reporting on test does not undo that; it only protects the numbers reported. Say so in Limitations rather than implying the whole pipeline is untouched by the development set.

#### The decision rule

1. **v2 stands as-is and is reported.** One motivated edit, disclosed.
2. **Before any v3**, either move final reporting to `test.json`, or hold out a stratified split of testmini and iterate only on the remainder. **Do not iterate further against the same 700 that the paper reports.**
3. **Nothing is decided before the 3B v2 run.** The routing gate is built entirely on local model behaviour (§2.10), so if v2 helps the 3B as it helped flash, every routing number is recomputed on v2 outputs. **Iterating the prompt before that is optimising against half the picture.**

---

## 10. What If the 2026 Baseline Is Already Very High? (Backup Plans)

Why full saturation is unlikely: (1) the recall ceiling caps RAG accuracy regardless of model intelligence; (2) FDV-KNOW needs niche accounting knowledge; (3) our headline setting uses a 3B local model, which will certainly not saturate anything.

If the cloud baseline nevertheless comes back ~90%+ (in order of preference):

**A. Pivot the metric: accuracy → faithfulness.** Labels can saturate while explanations remain unreliable. Nobody has measured faithfulness on FINDVER; the authors requested it. **[MEASURED]** We already hold a documented instance of right-label/wrong-reasoning from week-1 testing — this plan is no longer hypothetical.

**B. Pivot the question: accuracy → cost.** Already half-built into the core design (§5.3): can 3B-local + targeted escalation match the frontier at a fraction of the cost? **[MEASURED]** Also now measurable in wall-clock, not just tokens.

**C. Contamination analysis.** Evidence-withheld probing (§3.12); a respected genre; strengthens any result even as a short section.

**D. Characterise residual errors.** Even 90% leaves ~150 test-set failures; if they cluster (multi-table aggregation, fiscal-vs-calendar year, unit scaling), documenting the cluster plus one targeted skill is a tight contribution.

**E. (Last resort) Benchmark extension.** Adversarial/compositional claim variants. Most work; fallback only.

**Structural point:** all five plans reuse the same infrastructure. The baseline experiment is not a gamble but a fork with both directions paved.

---

## 11. Practical & Engineering Notes

1. **Compute:** edge model + embeddings run locally, free, unlimited. Cloud keys professor-provided.
2. **[NEW] Cloud API endpoints.** **DeepSeek** runs a single global API (`api.deepseek.com`), OpenAI-SDK-compatible — one key, no regional configuration, expected to work from Canada with no setup. ~~**Qwen** runs on Alibaba's DashScope, which is split into separate regional deployments whose keys are not interchangeable.~~ **[VERIFIED 7 Aug 2026.]** `deepseek-v4-pro` answers at `https://api.deepseek.com/chat/completions`, OpenAI-compatible, `temperature: 0` accepted. **The DashScope regional question is moot: no Qwen key was ever issued, and both cloud models are DeepSeek** (§13 item 7). **V4 Pro is a reasoning model** — it returns a separate `reasoning_content` field and counts `reasoning_tokens` inside `completion_tokens` (32 of 34 on a trivial prompt). Three consequences: feed `extract_label` the `content` field **only**, never `content` plus `reasoning_content`, since the extractor takes the last match within a level and the reasoning may weigh the opposite verdict before concluding; re-measure every cloud cost estimate on a real 4,426-token claim, because no output-token figure from a non-reasoning model transfers; and log the response's `model` and `system_fingerprint`, which report what actually served the request.
3. **Dataset:** full repo cloned. ~~Leaderboard + Scholar sweep still outstanding.~~ **Both done 3 Aug (§6.6 note 2):** no leaderboard exists, email submission retired July 2026, and a 23-paper citation sweep found **MACE is the only published method evaluated on FINDVER**. Abstract-level screening only, so write "we found no other", never "nobody has".
4. **Table parsing:** HTML via pandas (§7.1); ship imperfect with a raw-text fallback rather than blocking on perfection.
5. **Sandbox safety:** whitelisted builtins, no imports beyond pandas/math, timeout; never unrestricted exec.
6. **Determinism:** temperature 0 everywhere; fixed seeds; prompts versioned in git.
7. **Reproducibility:** one config file per experiment; per-example JSON results; one script regenerates every results table.
8. **[REVISED 31 Jul] Verdict extraction — the fixed-final-line assumption failed, and the official scoring hides the failure.** The previous plan assumed enforcing `"Therefore, the claim is {entailed|refuted}."` in the prompt would make post-processing unnecessary. ~~In week-1 testing neither the 3B nor the 7B model produced the required sentence.~~ **Corrected 1 Aug 2026:** that claim came from the first test round, whose prompt was corrupted by the loader bug in item 9 below and which ran before `num_ctx` was set. On the re-run at `num_ctx` 8192 both models did produce the required sentence. See the correction in §4.6; the corrected value is from recollection, not a preserved artifact, and is provisional until the first trial run logs it. **The case for the extractor does not rest on that datapoint.** It rests on the 11,200 upstream responses measured below, where format compliance falls to ~55% at 3B, and on the fact that the edge-only baseline runs a 3B model end to end regardless of where the routing line lands. Label extraction therefore needs: (a) regex for the canonical sentence; (b) fallback patterns for common paraphrases; (c) an explicit `unparseable` bucket that is counted and reported rather than silently coerced.

   **What the official evaluation actually does** (read from `FinDVer/evaluation.py` and `utils/evaluation_utils.py`, 31 Jul). It extracts the verdict with a **`gpt-4o-mini` call per example**, asking for `entailed` / `refuted` / `none`. When the answer is `none` it assigns `random.choice(["entailed", "refuted"])`: the example is scored as a guess, and is never counted, reported, or excluded. No `random.seed` appears anywhere in the repo, so the official score is not reproducible on identical predictions. Separately, the *direct*-prompting path tests `"entail" in output` before `"refut"`, and "entail" is a substring of "not entailed", so that path mislabels negated conclusions; CoT does not use it, so it does not affect our comparison baseline.

   **Why this matters at our scale.** For the paper's models, unparseable outputs are rare and coin-flipping them moves the score by well under a point. At 3B they are not rare. A model failing the format on 30% of examples receives roughly 15 accuracy points of imputation rather than reasoning. This is not a flaw in the benchmark; it is an assumption that does not hold in our regime, which is a more defensible and more interesting claim.

   **[MEASURED 31 Jul] A deterministic regex is nearly as accurate as the cloud extractor; the gap is coverage.** `outputs/testmini_outputs/rag/processed_cot_outputs/` ships 700 examples for each of 16 models, storing both the raw response and the `gpt-4o-mini` label. Across all 11,200 pairs, a first-pass regex fires on **81.7%** and, where it fires, agrees with `gpt-4o-mini` on **98.9%**. Coverage tracks model size: claude-3-5-sonnet 100%, gpt-4o 99.7%, Qwen2.5-7B 91.3%, Llama-3.2-3B **54.9%**, Llama-3.1-8B 52.9%. Two caveats. `extracted_label` is stored *after* the coin flip, so imputed labels are indistinguishable from real ones, and the ~45% miss at 3B is an unseparated mix of "no verdict stated" and "verdict phrased differently." The 98.9% agreement is also measured only where a clean sentence exists, i.e. on the easy subset.

   **Decision.** Build the extractor deterministically and develop it against those 11,200 stored responses, which needs no model run and no quota. Defer any model-based fallback until widened patterns have been measured. Replicating the official extractor is impossible regardless: it uses `gpt-4o-mini`, and the available cloud keys are DeepSeek and Qwen, so the model route costs quota without buying comparability.

   **[BUILT + MEASURED 1 Aug 2026] `src/label_extractor.py` is finished. Widening stopped, and the model-based fallback is rejected.** Three levels, tried in order of precision, last match winning within a level: an anchored concluding sentence searched over the whole response; then, only within the last 300 characters, a bare `entailed`/`refuted`, guarded so that a hedge (`partially entailed`) returns `None` and a direct negation (`not entailed`) returns the opposite label. `extract_label_with_source()` also returns which level fired, so a run can report where its verdicts came from. Coverage across all 11,200 rose from **81.7% to 87.8%**, agreement fell from 98.9% to 98.3%. On Llama-3.2-3B that is 54.9% → 65.3% coverage, or in absolute terms 373 → 437 correct extractions against 11 → 20 wrong. Level breakdown over 11,200: anchored 81.7%, bare 5.8%, negated 0.3%, hedged 2.3%, none 9.9%.

   **Why widening stopped.** Of Llama-3.2-3B's 231 remaining `none` responses, **81% contain the strings "entail" or "refut" nowhere in the response at all**. There is no verdict in the text to find. That closes the deferred fallback question with a number: an LLM-based fallback could not extract those either, it would have to read the reasoning and form its own judgment, which is imputation wearing a parser's clothes and is strictly worse than the coin flip because it does not look random. Only 15% of the residual has a verdict word in the body but outside the tail window, and reaching it means widening `TAIL_CHARS` into the reasoning and trading precision for a handful of examples.

   **[IMPORTANT CAVEAT 1 Aug 2026] Every coverage figure in this section is measured at temperature 1.0 with `max_tokens = 1024`.** Confirmed by reading `run_llm.py:44-47` and `scripts/inference/main_vllm.sh`, which passes no sampling overrides, so the argparse defaults reached vLLM at `run_llm.py:125`. Two consequences. **First, 39% of the 3B residual is the generation cap, not model incapacity** (§4.3): those responses were cut off mid-reasoning before a verdict could be stated. **Second, these numbers are not a forecast of our own rate.** Our runs use temperature 0 (§11.6) and set `num_predict` ourselves, and greedy decoding follows an instructed format far more reliably than sampling at 1.0. Do not write "3B models fail the output format 45% of the time" into the paper on the strength of this table. The first honest measurement of *our* rate comes from the trial run on our own model. Separately, this means the published FINDVER baselines are non-reproducible on **two** axes rather than one: sampled generation at temperature 1.0, and then the unseeded coin flip at scoring time.

   The token soup and near-empty generations in the upstream files are *consistent with* temperature 1.0 but that is unverified, since testing it would mean re-running their models.
9. **[NEW] Assert evidence presence before every model call.** Week-1 testing lost one test round, roughly 15 minutes, to a silent data bug. It was caught during single-example testing, which is the only reason it was cheap; the same bug inside a 100-example overnight run costs ~8 h. Report `context` elements are dicts (§2.3), a loader assumed strings, and the fallback serialised raw dicts into the prompt while truncating each to 2,000 characters. Both models then produced confident figures that appear nowhere in the source document — a failure indistinguishable, from the output alone, from a genuine extraction error. Had this reached the ablation, it would have been mislabelled "extraction error" or "domain knowledge deficiency" and corrupted the error analysis. **Mitigation, cheap and permanent:** after building each prompt, assert that the gold evidence string (or a distinctive numeric token from it) is literally present; log a warning and flag the example otherwise. Also log `prompt_eval_count` **and `eval_count`** per call. **[REVISED 1 Aug 2026]** Alarming on `prompt_eval_count == num_ctx` alone is not enough: it catches only input-side truncation. Measured on v0.12.3 (§4.3), Ollama shifts context during generation and evicts the oldest prompt tokens, so evidence that was present at ingestion can be destroyed mid-response while `done_reason` still reports `"stop"`. The string-presence assertion above passes in that case and cannot detect it. Alarm on `prompt_eval_count + eval_count >= num_ctx`.

**[BUILT AND MEASURED 2 Aug 2026] `src/evidence_asserter.py`.** The check is not "is the gold string in the prompt". It is: for each gold context element, take its three **rarest** tokens, rarity counted against the whole report, and look for them in the **evidence block**. A token with report count 1 appears nowhere in the filing outside that element, so finding it proves the element reached the prompt. Rarity is computed, not guessed, which handles paragraphs, tables and number-free prose with one rule instead of three branches.

**The evidence block, not the prompt.** The prompt contains the claim, and FINDVER claims are built by copying figures out of the evidence, so the naturally strongest witnesses are exactly the tokens the claim also supplies. Measured: **178 of 700 claims (25%) contain at least one witness token from their own gold evidence.** Checking the whole prompt would therefore inflate the flag on a quarter of the benchmark, worst on the examples that matter most. `build_prompt` returns the evidence block alongside the prompt, and the run loop asserts `evidence_block in prompt` to cover the substitution. Parsing the block back out of the prompt was rejected: it would couple the asserter to a template that changes every tier, and a delimiter that stopped matching would fail silently, which is the failure class this module exists to catch.

**Validation, all 700 claims, offline, no model calls** (`test_scripts/validate_evidence_asserter.py`, ~1 m 45 s). Gold elements as the block: **700/700** flagged present. Three random non-gold elements: **0/700**. The claim statement alone: **0/700**. Non-gold elements with maximum token overlap with the claim, a proxy for a retrieval miss: **5/700**, a 0.7% false-positive rate. **False negatives are 0/700**, which is the direction that matters, since a false negative would excuse a real model failure as a retrieval miss.

**The residual limit, and it should be stated in the paper if the flag is cited.** Only **59.4%** of the 1,964 gold elements have all three witnesses unique; **80.4%** have a unique top witness. For roughly a fifth of elements a full match is strong evidence rather than proof, and that fifth produces all five false positives: their gold elements have no unique token because filings repeat themselves (`ie-val-61`'s witnesses `direction`, `acquired`, `resigned` each occur five times; `numeric-val-84`'s occur twice, the standard 10-K pattern of legal proceedings text appearing in two sections). Raising the witness count from 3 to 7 removes one of the five, so this is repeated content, not a tuning knob. The lexical-overlap control is a proxy, not an upper bound; re-measure once the hybrid dense + BM25 retriever of §7.3 exists.
10. **[NEW] Config gotchas that bite silently:** Ollama `num_ctx` defaults to 4096 and truncates the *input* without warning (§4.3); **`num_predict` caps the *output* and cuts the verdict off mid-sentence, sending the example to the `unparseable` bucket disguised as a format failure — set it explicitly and verify Ollama's default (§4.3)**; Ollama auto-update must stay disabled to preserve v0.12.3 macOS-13 compatibility; interactive `/set parameter` does not persist across sessions — the REST harness must set it per call.
11. **[NEW 4 Aug 2026] What can be deleted when the project is over, and what cannot.** The untracked directories are not equally disposable, and they look identical from the outside: all large, all gitignored.

    **Safe to delete, because they are re-obtainable by download or by script.** `FinDVer/`, 1.3 GB, re-clonable from GitHub. `README.md` records the pin at commit `e8bb237`, which is what makes a later re-clone return the same data rather than whatever HEAD has become; the repo did change in July 2026 when email submission was retired. The embedding index (§7.3) is derived data: delete it, re-run the embedding script, and it rebuilds identically given the same model and chunking. At 768 dims and float32 it is 60,871 elements x 768 x 4 bytes = **about 178 MB**, or 238 MB for a 1024-dim model such as BGE-M3. Store it as a numpy `.npy` of raw bytes and gitignore it. **Storing vectors as JSON instead costs roughly 0.9 GB**, because a float written as text is about 20 characters rather than 4 bytes, and it slows the load on every experiment that reads it.

    **Not safe to delete.** `results/` holds per-example JSON from real model runs, and each experiment directory is roughly 12 h of overnight compute (§12.1) that cannot be regenerated for free. `logs/` likewise. The rule: derived from a download or from a script is disposable, derived from a model run is not.

---

## 12. Timeline

> **[REPLANNED 31 Jul 2026] The eight-week schedule is void.** The 30 July meeting set a hard deliverable: a 5-page workshop paper (§1.1, §14 item 9). Submission deadline **29 August 2026 AoE**, corrected on 1 Aug from the workshop site; the professor's 30 August was a day late. That is **29 days from 31 July**, not eight weeks.
>
> **Nothing is cut outright.** Scope is banded by what compute is available (§12.3), because faster hardware may become available and would move the bands. Retrieval in particular stays in scope: it is the project's core (§3.3), and its recall measurement needs no model runs at all.

### 12.1 The binding constraint is local wall-clock

Measured throughput (§4.6) converts directly into nights, and the machine runs one job at a time.

**[CORRECTED 2 Aug 2026 from the trial run's real timings. The 3B rows were optimistic.]**

| run | examples | wall-clock | nights |
|---|---|---|---|
| 3B, stratified slice | 102 | **~12 h** (was ~8) | 1, a full one |
| 7B, stratified slice | 102 | ~20 h, still an estimate | 2–3 |
| 3B, full testmini | 700 | **~82 h** (was ~55) | **~10** (was ~7) |
| cloud model, slice | 102 | API-bound, hours not nights | ~0 |

Between 3 August and 23 August there are roughly **20 usable nights**, and results must freeze before writing. On *this machine* a full-700 run would now consume **half** that budget on one number, up from a third, which is why it sits in the conditional band (§12.3) rather than the committed one. That gap widened; it did not close.

**A 102-example slice is no longer a comfortable overnight job.** At ~12 h a run started at 9pm finishes at 9am. Starting late costs the following day, not just the night.

**The corrective lever is prompt size, not scheduling.** §4.6 measures runtime as linear in prompt tokens at R² = 0.995, so halving the mean prompt roughly halves every local run. Tighter retrieval buys wall-clock and recall together, and it is the only thing in the project that does both.

> **[FALSE ON THE GPU BOX — corrected 14 Aug 2026.]** The paragraph above is true of the MacBook only. Measured on the GPU (§4.6), halving the prompt does **not** halve the run: the k=5 run cut prompt tokens 46% and wall clock 15%, and gold-alone cut them 70% for 22%. **On that machine tighter retrieval buys recall and almost no wall-clock, so it is no longer the thing that does both.** Every night-budget figure in this section is a MacBook figure and stays valid for the MacBook.

**Two asymmetries decide what is affordable, and neither is about the tier number.**

- **Cloud runs are nearly free in wall-clock.** API-bound, hours not nights. Local runs are the scarce resource; cloud runs are not.
- **Retrieval recall is free in wall-clock.** It scores retrieved chunk indices against gold `relevant_context` (§9) using embeddings and plain Python, with **no LLM calls**. A *k* sweep, a BM25 comparison, and a decomposition comparison are all minutes, not nights, and they can run during the day while an overnight job holds the evening. Only the *end-to-end accuracy delta* from better retrieval needs a night.

So "Tier 2 is expensive" is false as stated. Its measurement half is one of the cheapest things in the project, and it is the half most on-topic for a RAG-focused paper.

**[OPEN] Faster hardware may become available.** If it does, the night budget stops binding and the conditional band opens: full-700 runs, end-to-end retrieval ablations, and 7B slice comparisons all become affordable. Specs and availability date are unknown as of 31 July (§13 item 11). Until they are known, plan against this machine and treat anything faster as upside rather than assumption.

~~**[UPDATED 3 Aug 2026] The professor has offered a GPU server, so Band B is now likely rather than hypothetical.**~~ **[WITHDRAWN 7 Aug 2026. The server is unavailable and will not be available before the deadline.]** He has several dozen RTX 4090 units, but they sit on a local network with no public IP address and his students have not been able to obtain one. He expects a fix only after the semester starts in September, which is after 29 August. **The night budget above is now the binding constraint, not a placeholder.** Two fallbacks were offered and neither is scheduled: he will try to find a machine that can bridge access, and failing that he is willing to pay for a rented third-party GPU server. **[RESOLVED the same evening. The brother's desktop works and Band B is open.]** AMD **RX 7600 XT** (gfx1102, 16 GB), Windows, Ollama over LAN. **36.8x measured** on the six-claim smoke sample: 23.2 min → 37.7 s. A 102-example run drops from 10.5 h to roughly 20 minutes and the full 700 run from 72 h to a few hours, so **the night budget above stops binding.** See §13 item 11 for the numbers and the caveats. Two things do *not* change. The MacBook remains the device of record for all latency and memory figures (§4.2, §13 item 11). And prompt size remains the right lever on *this* machine, so the retrieval work keeps its efficiency motive for the deployment story even after wall-clock stops binding for experiments.

### 12.2 The 30-day plan

**Phase 1 · 31 Jul – 2 Aug · Finish the harness.**
Label extractor (§11.8), per-example logging, evidence assertion (§11.9). Loader and sampler are done and committed. None of this is blocked on cloud keys. The label extractor is developed offline against the 11,200 stored responses in `outputs/`, at zero compute cost.

**[UPDATED 1 Aug 2026]** The extractor and the logger are both done and verified. `src/logger.py` holds a 17-field `Record` dataclass, `write_result()` writing one JSON file per claim into `results/<experiment>/`, and `has_result()` giving resume by skipping ids that already completed. Resume tests `status == "ok"` rather than file existence, because a failed example still writes a file, and a truncated JSON file returns `False` rather than raising. **The phase is one item longer than this line says: the run loop was never in the list of five and the trial run cannot happen without it.** Remaining: evidence assertion, then the run loop, then the 12-example trial run.

**Phase 2 · 3 – 10 Aug · Baselines.**
Edge-only on the 102-example slice, 3B and 7B. Two new cloud models on the same slice, once keys arrive. **Published FINDVER numbers are reused as the historical baseline rather than re-run** (§9), which is what makes this phase fit at all. Hand-label ~25 failures per configuration. Deliverable: the baseline table plus error distributions.

> **[REVISED 3 Aug 2026] The retriever moves ahead of the baselines, and nothing ran on 3 August.**
>
> Phase 2 as written above starts the edge-only baselines on 3 August. That is no longer the right order, for three independent reasons, each of which alone would make a run that night a throwaway.
>
> 1. **The retriever is still the placeholder at 57.54% recall** (§3.4). §9.2 requires every condition to share the same retrieval, so any baseline measured now is invalidated the moment the real retriever lands. The 2 Aug build log already reached this conclusion: *"the retriever is the better next investment."*
> 2. **A 102-example 3B run is ~12 h**, so a late start finishes the following afternoon and costs the next day too (§12.1).
> 3. **Machine choice is not settled.** Results from the MacBook and the offered GPU server cannot sit in one table (§13 item 11), so anything run locally now is re-run once the server arrives.
>
> **The retriever is cheap to settle**, because it is chosen on **recall alone**, which needs no model calls. It costs daytime work, not nights. So moving it first delays the baselines by a few days and costs zero nights.
>
> **Revised dated plan, 3–29 Aug.**
>
> | Dates | Work | Cost |
> |---|---|---|
> | **3 Aug** | Leaderboard check, citation sweep, pull MACE's accuracy figure (§9.3). Reading only. | none |
> | **4–7 Aug** | Build the retriever (§7.3). Choose on recall, no model calls. **Freeze retrieval.** | no nights |
> | **7–9 Aug** | Conditions 1 (3B and 7B) and 2 at 102. These are the two ends the professor asked for. | local nights + cloud hours |
> | **9–16 Aug** | Build pipeline modules one at a time, code execution and tables first (§8 Tier 1). Run condition 4 at 102 after each, recording what that module was worth. | most of the nights |
> | **15 Aug** | Decision point, unchanged. Whatever is not working is dropped, not debugged. | — |
> | **17–20 Aug** | **Freeze the pipeline.** Conditions 3 and 4 at 102. Produces the full four-condition table. | cloud hours + local nights |
> | **20–23 Aug** | Full 700 run: conditions 1, 3, 4, plus 2 if quota allows (§9.2). **Only happens if the server arrives.** | GPU |
> | **23 Aug** | Results freeze. Hard stop. | — |
> | **24–29 Aug** | Write. | — |
>
> **The machine decision has a deadline of roughly 7 August**, since that is when condition 1 starts and it cannot be split across machines. If there is no server access by then, start on the MacBook at ~12 h per run and accept re-running if the server arrives later.
>
> **Separately, and regardless of where the accuracy runs live:** one MacBook night at the very end, after the pipeline freezes, for real per-example latency and peak RAM on the actual device (§13 item 11).
>
> **Honest caveat.** This is tighter than the phasing above, because moving the retriever first pushes everything right by several days. Without the server, the 700 run does not happen and "we match condition 3" stays unprovable at ±10 points. §12.3's Band A results still carry the paper in that case.

**Phase 3 · 11 – 20 Aug · Ablations, cheap-measurement work first.**
Two strands run in parallel, because they compete for different resources.

*Daytime, no model runs.* **Tier 2 retrieval recall**: claim decomposition, BM25 plus dense fusion, table-aware chunk metadata, *k* sweep, all scored against gold indices (§7.3, §9). This is the project's core question (§3.3) and it costs minutes. Target: meaningfully above the 68–70% recall ceiling. **[REVISED 2 Aug]** The starting point is better understood than it was: BM25 alone already reaches 65.16% on their metric (§3.4), so the fusion has to beat 68.01% rather than 68% being far away, and every recall number must be reported on all three metrics because the published one is a macro-average that reads as something else. **[REVISED AGAIN 4 Aug]** The 68.01% target is met and superseded. Our own BM25 reaches **74.60%** with no model and no API (§3.4.1), so the open question is now whether a fully local hybrid can clear 74.60%, not whether anything can clear 68.01%.

*Overnight, one configuration per night.* **Tier 1 code execution and tables-as-DataFrames**, the highest-certainty accuracy gain, validated against gold `execution_result` (§2.5) before touching end-to-end runs. Then the end-to-end delta from whichever retrieval variant won on recall, if nights remain.

**Decision point 15 Aug:** whatever is not working by then is dropped from the paper, not debugged. Recall numbers stand on their own even if the end-to-end delta never gets measured, which is the reason to front-load them.

**Phase 4 · 21 – 23 Aug · Freeze.**
No new configurations. Final numbers, both scorings (§9), final taxonomy distribution before versus after.

**Phase 5 · 24 – 29 Aug · Write.** **[CORRECTED 1 Aug: six days, not seven.](#)** The deadline is 29 August AoE (§1.1). The AoE clock runs to 04:59 PDT on the 30th, which is upload buffer rather than a working day. Double-blind, so no author names and no identifying repository link in the submitted PDF. Anonymity is for review only: the camera-ready version after notification on 29 September carries full author names, so there is no second permanent version to maintain.

**On the submission form, name topics 05 and 02** (§1.1). Topic 05 is benchmarks and evaluation for real-world deployment, which is what the extraction and imputation analysis is. Topic 02 is efficient inference and reasoning under real-world constraints, which is the pipeline. Framing the paper against topic 05 rather than as a generic RAG-accuracy result is the difference between an on-topic submission and an adjacent one.
Five pages. Intro, related work, method, results, analysis, limitations. Writing cannot start later than 24 August and stay honest, so Phase 4 is a hard stop.

### 12.3 Scope bands, not cuts

**[REVISED 31 Jul]** An earlier draft of this section cut Tiers 2–5, the full-700 run, and the leaderboard submission outright. That was wrong on two counts: it cut retrieval, which is the project's core (§3.3), and it priced Tier 2 as if all of it needed overnight runs when its recall half needs none (§12.1). Scope is banded instead. Nothing is abandoned; each band states what it costs and what would unlock it.

**Band A — committed. Fits on this machine, in these 30 days.**
Harness. Tier 0 baselines, edge and cloud, on the 102-example slice. Tier 1 code execution. **Tier 2 retrieval recall**, standalone, measured against gold indices with no model runs. The extraction and imputation analysis (§11.8), already measured. Error taxonomy on ~25 hand-labelled failures per configuration.

**Band B — ~~conditional on faster hardware, or on Band A finishing early~~. [OPEN as of 7 Aug 2026, evening.]**
End-to-end accuracy delta from the winning retrieval variant. Full 700-example testmini run. 7B slice comparisons. Leaderboard submission. Each of these is a night or several on the current machine; on faster hardware they are cheap. ~~**Do not design the paper to require them, and do not design it to preclude them.**~~ Note the full-700 run has an independent motive beyond precision: the ±10-point margin at n=102 (§9) makes any close comparison unresolvable, so if compute appears, this is the first thing it buys.

**The compute appeared.** The brother's desktop measured **36.8x** faster than the MacBook on 7 August (§13 item 11), taking a 102-example run to ~20 min and the full 700 run to ~2–3 h. **Band B is now affordable and the paper may be designed to include it** — with two conditions. First, **everything compared must run on the same machine**, since verdicts were measured to diverge across CPU and ROCm at 5 of 6. Second, the **leaderboard submission stays out** for the unrelated reason in §13 item 4: there is nothing to submit to.

**Band A does not become less important.** Retrieval recall and the extraction/imputation analysis still carry the paper if the desktop becomes unavailable — it is a family machine, not a guaranteed resource.

> **[14 Aug 2026] A THIRD CARRYING RESULT, and it reframes the first.** The evidence-presence finding is now measured from both directions and belongs in its own results section, not a sentence in analysis. §2.8.1 gave the 3B *perfect* evidence: +3.6 on FDV-IE, p = 0.253, and a tie overall at p = 0.116. §2.8.2 then *removed* a third of its evidence via k=5: accuracy moved +0.2, p = 1.000, and within that run claims whose gold evidence reached the prompt beat claims whose did not by 1.4 points. **Retrieval quality and answer quality are close to decoupled for this model on this benchmark.**
>
> Either experiment alone is a design artefact. Two pushing opposite ways and agreeing is a finding, and it is the kind of negative result a workshop on real-world constraints should want: **the standard assumption that better retrieval yields better verification does not hold at 3B here.**
>
> **It also constrains how the recall result is written.** The 74.06% fused figure against the published 68.01% is a *retrieval* result and stands on its own. It may not be presented as raising verification accuracy, because our own data says it does not. See `paper_numbers.md` §1, §2.8.1 and §2.8.2.

**Band C — stretch, only if Bands A and B land early.**
Tier 3 glossary, Tier 4 faithfulness verifier, Tier 5 routing sweep. The faithfulness metric is the most novel piece in the plan and the natural centrepiece if accuracy saturates (§7.5), so it is the first thing to promote out of Band C if the schedule loosens.

**What carries the paper if Band B never opens.** Two results that do not depend on a long run chain. **Retrieval recall**, which is standalone, cheap, and the project's stated focus. And **the extraction and imputation analysis** (§11.8): 11,200 upstream responses, no compute, directly on-venue, showing format compliance collapsing from 100% at frontier scale to ~55% at 3B while the benchmark's official scoring converts that collapse into roughly 15 points of imputed accuracy. Both are robust in a way a 102-example accuracy delta is not.

### 12.4 Risk buffers

Table parsing overruns, cut Tier 1's retry loop before cutting Tier 1. Cloud keys arrive late, Phase 2 runs edge-only first and cloud slots in whenever keys land, since cloud runs cost hours not nights. Local throughput proves worse than measured, drop the 7B slice runs first, they cost 2 to 3 nights each for a comparison the paper can live without. Edge model too weak for a subtask, that subtask escalates to cloud, which is a data point for the routing analysis rather than a failure.

---

## 13. Open Questions for the Next Meeting

1. **Where should the edge/cloud line actually sit?** §4.5 — the 3B model handled a full end-to-end verification correctly, which the original allocation did not anticipate. Options: keep the conservative allocation; move more to edge and escalate only on verifier failure; or treat the threshold as a swept parameter from the start. **Sub-question added 1 Aug:** should the edge tier fill the final output template at all? §4.4 provisionally reassigns that row to cloud, because the cloud model is already generating the explanation and a second 3B call to reformat it adds cost and a failure mode without adding anything. Cheap to reverse, so it is a default rather than a commitment.
2. **Cloud API keys** — DeepSeek and/or Qwen, plus which DashScope region for Qwen (§11.2).
3. **Is ~8 h per 100-example round acceptable**, or should batch runs move to Colab / a lab server now rather than as a fallback?
4. ~~**Target venue and rigour level.**~~ **ANSWERED 30 Jul:** ~5-page workshop paper, *On-Device Intelligence: Foundation Models under Real-World Constraints*, deadline 29 Aug 2026 AoE (§1.1, corrected 1 Aug).

   **[CORRECTED 3 Aug 2026 — this item was wrong twice over.]** It previously ended "Leaderboard submission and the full 700-example run are consequently **out of scope**." Two problems with that clause.

   **It was not his ruling.** He settled the venue and the deadline. The "consequently out of scope" was our own inference from the deadline, written as though he had decided it. That is an attribution error, and it matters, because he may actually want a leaderboard submission.

   **It is also superseded.** §12.3 was revised on 31 July and explicitly overturns it: *"An earlier draft of this section cut Tiers 2–5, the full-700 run, and the leaderboard submission outright. That was wrong on two counts."* Band B holds all three as conditional. OQ9 carries the identical correction dated 1 Aug; this item was missed.

   **Current position.** The full-700 run is affordable once the GPU server (item 11) is real, and §12.3 names it as the first thing compute buys.

   **[CLOSED 3 Aug 2026] The leaderboard question is moot: there is nothing to submit to.** The paper promised an online evaluation platform and public leaderboard, but no URL exists in the paper or the repository and there is no evidence it launched. Email submission did exist and was retired in July 2026 once the test labels went public (§6.6). So the whole debate about whether to chase a leaderboard rank is void, and no earlier sentence in this plan should be read as ruling one out on strategic grounds. The structural argument still holds if a platform ever appears: a leaderboard ranks accuracy only, our contribution is cost-accuracy (§5.3), and a 3B edge model plus routing will not top a board of frontier models.

   **A useful consequence:** the test split ships with labels, so the 1,700-example split can be scored locally with the same procedure as testmini. That is now an available option rather than a leaderboard-gated one.
5. **Does the faithfulness metric interest him as a contribution in its own right?** It is the most novel piece and the natural centrepiece if accuracy saturates (§7.5). Now in **Band C** (§12.3), and the first thing to promote if the schedule loosens or faster hardware arrives, so his appetite for it is worth knowing *before* that decision rather than after.
6. **Confirm plain-script implementation** over AutoGen (§3.11), with the debuggability rationale.

**Opened by the 30 July meeting and the 31 July measurements:**

7. **Which two cloud models, and which provider?** He said newer models generally, and separately that Anthropic keys can be provided. Anthropic is the tighter comparison, since `claude-3-5-sonnet` is the paper's top scorer and a newer Claude extends that exact row. DeepSeek and Qwen match the cloud-edge framing in §4.1. Needs a decision before Phase 2 (3 Aug).

   **[PARTLY ANSWERED 3 Aug 2026.]** He named **DeepSeek**, citing a recently released model as nearly comparable to Claude. He did **not** name the model, so the exact model string and endpoint still have to be asked for. Do not guess a model ID.

   **He did not address the Anthropic argument.** "Nearly comparable to Claude" is a claim about model strength; the argument put to him was about *published-row continuity*, not strength. The published model list was checked directly (`outputs/testmini_outputs/rag/processed_cot_outputs/`, 16 files): `claude-3-5-sonnet-20241022.json` is the paper's top scorer, and DeepSeek appears only as `DeepSeek-V2-Lite-Chat.json`, a small MoE model. A new frontier DeepSeek therefore extends a row whose only predecessor is weak enough that the comparison carries no information, while a newer Claude extends the strongest row directly.

   **This is coupled to §9.1 and is not a preference.** §9.1 makes reuse of published numbers load-bearing for the entire 30-day timeline. Models with no meaningful published predecessor weaken that.

   ~~**Decided:** DeepSeek is primary, settled, key already in hand. Ask **once** for an Anthropic key as the second cloud model.~~

   **[CLOSED 7 Aug 2026.] Both cloud models are DeepSeek: `deepseek-v4-pro` and `deepseek-v4-flash`.** This is the chat-versus-reasoning fallback the entry already named, so the requirement for two cloud models is met without Anthropic.

   **The Anthropic answer was about money, not merit, and this item previously misread it.** He said there is no reason not to use Anthropic. He does not want me buying a key myself, and he cannot buy one for me: he is in China and Anthropic does not serve China. He can pay for DeepSeek. **Nothing in his answer disputes the published-row-continuity argument** — it was never rejected on the merits. Scale: condition 2 at 102 examples is roughly 0.45M input and 0.05M output tokens, which is single-digit dollars at current Anthropic rates. If the Claude row is wanted later it is a personal expense of about that size, decided unilaterally, not a request to him.

   **Verified live 7 Aug.** `deepseek-v4-pro` answers at `https://api.deepseek.com/chat/completions`, OpenAI-compatible, `temperature` 0 accepted. **It is a reasoning model** — separate `reasoning_content` field, `reasoning_tokens` counted inside `completion_tokens`, 32 of 34 output tokens on a trivial prompt. Consequences for the extractor, cost estimates and logging are in §11 and the build log entry for 7 August.

   **`deepseek-v4-flash` is a floating alias** routing to `DeepSeek-V4-Flash-0731`. Pin the dated snapshot in configs if the endpoint accepts it, for the same reason two machines cannot share a results table. Untested.

   **Which model goes where.** Pro for conditions 2 and 3, so both the single-call cloud baseline and the all-cloud upper bound use the strong model. Flash is a cheaper extra row and the natural escalation target to test inside condition 4. **Putting flash in condition 3 would lower the bar §5.3 claims to match**, by our own choice.
8. **Which edge models to add?** The paper already covers Llama-3.2-3B, Llama-3.1-8B, Qwen2.5-7B, Mistral-7B and others (full list in `outputs/`). Ours must be models it did **not** evaluate, and each 7B-class slice run costs 2–3 nights (§12.1). Two is realistic; three is not.

   **[STILL OPEN 3 Aug 2026. He was asked this directly and did not answer it.]** The server offer reads as an implicit "you will have compute so it matters less," but it names no models. This is the item that gates the schedule, since Phase 2 starts 3 Aug.

   **Proceeding as a decision unless he objects:** `Qwen2.5-Coder-3B` primary, `Qwen2.5-Coder-7B` second. Verified against the file list that neither Coder variant is in the published 16; the closest is `Qwen2_5-7B-Instruct`, a different model. Same family means 3B→7B is a clean scaling comparison with everything else fixed, §4.6's 7B numbers need settling regardless, and the code tuning is load-bearing for Tier 1.

   **[CONTRADICTION FLAGGED 3 Aug — this item may be written for the wrong objective.]** Requiring models FINDVER did *not* evaluate optimises for adding new table rows. But the paper's claim (§5.3) is that the **pipeline** improves a small model, and the cleanest evidence for that is the **same model, published baseline versus ours**, with the pipeline as the only variable. `Llama-3_2-3B-Instruct` is published, with 700 stored responses already on disk at zero compute cost. This item disqualifies it; a pipeline-contribution framing makes it the single best candidate available. The confound is real — upstream's RAG setup is not ours, so it is not fully controlled — but it is far closer than a brand-new model. ~~**Not resolved. Raise with him.**~~

   **[DOWNGRADED 7 Aug 2026. The Llama argument is much weaker than written above, and the entry overstated the confound as merely "real".]** Upstream ran **temperature 1.0**, a **1024-token generation cap**, a retriever at **65.16% recall against our 74.60%**, and **`gpt-4o-mini` extraction with an unseeded coin flip**. "Same model" holds one variable fixed while four others move. **Condition 1 against condition 4 holds model, retriever, k, prompt version, `num_ctx`, temperature and extractor all fixed**, so it is strictly better evidence for the pipeline claim, and it exists at n=102 without needing the 700 run. Separately, the published Llama number is free from disk as **historical context** in the baseline table — adopting the model was never required to cite it. **Not a live tension. Reopen only if the model question reopens.**

   **[REOPENED BY HIM 7 Aug 2026, on a different axis.]** He questioned whether a **Coder** model suits reading comprehension rather than coding, and left the choice to us. His criteria: the strongest model that is still light, ideally around 3B for the on-device framing, chosen to give the best chance of matching condition 3.

   **He named `Qwen2.5-Coder-3B` himself** (§14 item 5). The 7B second model was ours. **His objection holds for condition 1**, which contains no code at all and is the floor everything is measured against; the Coder choice is defensible for Tier 1, where the model writes Python for the arithmetic. **The risk of keeping it:** a model that reads badly but codes well makes the condition 4 minus condition 1 delta look large for the wrong reason.

   **His criterion contradicts this item's own reasoning and the contradiction is not resolved.** He says pick the strongest model that fits the on-device story; this item says 3B stays primary because a bigger model eats the contribution. His maximises the headline claim, ours maximises the measured value of the pipeline. **Record it as a stated limitation rather than picking silently.**

   **A framing error corrected while answering him.** "Matching condition 3" does not require a local model that rivals DeepSeek. Condition 4 is the 3B *plus* DeepSeek on judgment-heavy steps, so the local model only has to be good enough at the mechanical work that we do not escalate everything — escalating everything is condition 3 at condition 3's cost. The criterion is therefore *good enough at tables and output format, small enough to be credible on-device*, not *strongest available*.

   **Candidates if it changes, none yet verified on ollama.com:** `Qwen3-4B` is the current recommendation, because the paper already tested `Qwen2_5-7B-Instruct` and a newer, smaller Qwen beating an older, larger one is exactly this venue's story. Gemma 3 4B and Phi-4-mini are the alternatives. **Switching is free until condition 1 starts and costs a re-run afterwards**, so the decision is dated to the machine test, not deferred.

   **[DECISION RULE, 7 Aug 2026. The machine decides the model, not the reverse.]** The GPU smoke test runs first and must use `qwen2.5-coder:3b`, because the comparison baseline is `configs/smoke_bm25.json` at **23.2 min for six claims** on that exact model, sample and seed — a different model leaves nothing to divide by.

   **4B is comfortably on-device.** §4.2's rule already allows ≤8B, FINDVER's own baselines include 7B and 8B models, and a 4B at 4-bit is ~2.5 GB. The argument only starts above 8B.

   **Separate the measured from the guessed.** That a 4B is more accurate *on this task* is plausible and **unverified**. The tradeoff direction is real — a stronger base raises condition 4 and shrinks condition 4 minus condition 1 — but its size is unknown. **Only the wall clock is measured:** a 4B is ~⅓ larger, so ingestion falls from 12.4 tok/s to roughly 9–10, moving a 102-example run from 10.5 h to ~13–14 h. Material on the MacBook with ~16 nights left; irrelevant on a GPU.

   - **GPU works** → run condition 1 at 102 on both models, ~1 h each. Decide on measured accuracy; the loser becomes a results row rather than a limitations sentence.
   - **GPU fails** → **stay on `qwen2.5-coder:3b`.** One shot per night; it is already proven end to end at 6/6 with a fitted cost model; the professor chose it himself (§14 item 5); and his objection cuts the way this item wants, since condition 1 is a *floor* and a weaker floor makes the pipeline's delta more visible.

   **What a working GPU additionally buys:** `qwen2.5-coder:3b` vs `qwen2.5:3b` vs `qwen3:4b` at 102 each is ~3 h on a GPU and **answers his Coder objection with data** — size held fixed, code-tuned against general instruct — rather than with an argument. On the MacBook that is three nights and does not happen.

   **[3B stays primary. 7B is a row, not a switch.]** Considered promoting 7B to primary once the GPU removes the wall-clock objection, and rejected. A bigger model **eats the contribution**: the pipeline's delta is largest where the base model is weakest, so if 7B handles the arithmetic and tables unaided the ablation shows less and the paper says less. Secondary reasons: every measured number in the project is 3B, and the venue rewards the smaller model. This is what §12.3 already encodes — Band A is 3B, Band B holds "7B slice comparisons."
9. **Is the extraction/imputation finding acceptable as a headline contribution?** §11.8, measured on 11,200 responses at zero compute cost. The paper needs at least one result that does not depend on a long run chain, since Band B is conditional (§12.3). Worth confirming he agrees before building the paper around it. *(Corrected 1 Aug: this item previously read "with Tiers 2–5 cut", which contradicts §12.3. Nothing is cut; scope is banded.)*

   **[NEW 1 Aug] The call for papers argues this case for us.** Topic 05 is "Benchmarks and Evaluation for Interactive Real-World Deployment", asking for *metrics that jointly assess performance, latency, energy, memory, safety, and reliability under realistic deployment conditions*. A benchmark whose official scoring silently imputes a large share of a small model's reported accuracy is exactly a reliability-of-evaluation finding, and it is the workshop's own listed topic rather than our stretch of one. That is a strong argument to put to him alongside the question. Topic 02, "Efficient Adaptation, Inference and Reasoning under Real-World Constraints", covers the edge-cloud pipeline. **Name both topics on the submission.**
10. ~~**Workshop submission mechanics.**~~ **ANSWERED 1 Aug 2026** from the workshop site (odi2026.github.io), not from the professor. Full table in §1.1. Headlines: the deadline is **29 August AoE, not 30**, the review is **double-blind**, the venue is **non-archival**, 5 pages excluding references, NeurIPS 2026 LaTeX template, submitted via OpenReview.
11. **What faster hardware is actually available, and when?** Specs, access method, and date. This decides whether Band B (§12.3) opens: full-700 runs, end-to-end retrieval ablations, 7B comparisons. Two sub-questions matter. Does it have a usable GPU, which changes throughput by a large factor rather than a small one? And is Ollama's pinned-0.12.3 macOS-13 constraint (§11.10) even relevant there, or does a different machine mean a different and unpinned runtime? Until this is answered, plan against the current machine and treat anything faster as upside.

    ~~**[PARTLY ANSWERED 3 Aug 2026.]** He has offered a server, described as an **"NVIDIA RTX 4090 Ti"**. Band B is now likely rather than hypothetical.~~

    **[ANSWERED 7 Aug 2026, and the answer is no.]** The hardware is real — **several dozen RTX 4090 units** — but it is **on a local area network with no public IP address**. Several of his students have worked on obtaining one without success. He cannot grant access, and expects it "might get sorted out after the semester starts in September," which he himself calls "much too late." September is after the 29 August deadline.

    **Treat the server as unavailable, not delayed. Band B does not open from this source.**

    Two fallbacks were offered at the 7 August meeting, neither scheduled: he will try to find a machine that can bridge access to the LAN, and failing that he is **willing to pay for a rented third-party GPU server**. If the rental materialises, everything in the hardware rule below still applies unchanged.

    **[ANSWERED 7 Aug 2026, evening. The brother's desktop works. This is the machine.]**

    The card is an **RX 7600 XT** (Navi 33 / **gfx1102**, 16 GB VRAM, driver 32.0.31035.1003), **not the RX 7800 XT** every earlier document said — roughly half the bandwidth and compute of the assumed card. It did not matter. `ollama ps` reports `100% GPU`, and the model digest `f72c60cabf62` is identical to the MacBook's, so weights and quantisation match and the comparison is valid.

    **36.8x, measured on the same six claims, same sample, same seed:** 1389.4 s → 37.7 s, i.e. **23.2 min → 0.6 min**. Per-example ratios ranged 21.6x to 69.3x.

    | run | MacBook | GPU |
    |---|---|---|
    | condition 1 at 102 | 10.5 h | **~20 min** |
    | full 700 | 72 h | **~2–3 h** |
    | 7B slice at 102 | 20–30 h | **under an hour** |

    **Caveat on those projections:** the six smoke claims average 2,713 prompt tokens against the 700-wide mean of 4,426, so they are lighter than a representative draw and the real figures will land above the naive division.

    **Band B is open.** The full 700 run is the one that matters: it takes the accuracy margin from ~±10 points to ~±4 and makes §5.3's "we match condition 3" measurable rather than unprovable.

    **[MEASURED, not assumed: verdicts do not fully reproduce across machines. 5 of 6.]** `ie-val-174` came back `False` on the MacBook and `True` on the GPU. `prompt_eval_count` was identical on all six, so retrieval, sampling, trimming and prompt building are perfectly deterministic across machines — **the divergence is entirely in generation** (generated tokens moved 503→395, 644→485, 458→287, 246→519). Greedy decoding at temperature 0 still depends on floating-point arithmetic, and CPU and ROCm kernels do not produce bit-identical logits. This is exactly what the hardware rule below anticipated, so **the rule stands and now has evidence**: whichever machine runs condition 1 runs every condition, and the final MacBook night's portability check is a real measurement rather than a formality.

    **No code moved to that machine.** `src/ollama_client.py` builds its URL from `config.get("ollama_host", "localhost")`, so the Mac runs loader, sampler, BM25, prompt building, trimming, extraction and all writes, while the desktop runs only the model. Every result file now records which machine produced it.

    **The concrete reason to accept.** §9 puts the margin at ±10 points at n=102, which makes "matches the all-big-model pipeline" (§5.3, and condition 3 in §9.2) **unprovable** at that sample size, since a tie and a 5-point loss are indistinguishable. The full-700 run is the only fix, and §12.3 already names it as the first thing compute buys. This is the single biggest threat to the contribution statement.

    **[HARDWARE RULE, DECIDED 3 Aug. The GPU changes where experiments run, not what the paper claims about hardware.]**
    - Accuracy and ablations run on the GPU.
    - **The MacBook is the device of record** for every latency, throughput and memory figure in the paper.
    - **Never print a GPU-derived number under a MacBook label.** A run on the 4090 cannot produce a MacBook runtime, and substituting one would be fabricated data. This was raised explicitly and rejected. The honest version costs almost nothing, because §4.6's fitted cost model already exists from one 80-minute run.
    - **Never mix machines inside one results table.** Temperature 0 does not guarantee identical tokens across a CPU backend and CUDA, and quantisation may differ. If one configuration moves to the server, everything it is compared against moves too. The 2 Aug trial-run numbers are MacBook-only.
    - Keep the edge tier at **≤8B** whatever the VRAM allows. A 14B or 32B model called "on-device" would not survive review at this venue.
    - **Budget one MacBook night at the end**, after the pipeline freezes, to measure the final configuration's per-example latency and peak RAM on the real device. That run doubles as an **accuracy-portability check**, confirming verdicts reproduce off CUDA, which converts an assumption into a measurement.

    **[THREE LATENCY QUANTITIES ARE UNMEASURED, recorded 3 Aug so they are not discovered during writing.]**
    1. **7B latency on the MacBook.** The 11 m 46 s figure is one week-1 example and recollection (§4.6). Re-measure it or label it an estimate.
    2. **Pipeline latency, as opposed to baseline latency.** The measured 7.0 min/example is `baseline_v1`, placeholder retriever, *k*=10, no code execution, no table parsing, no cloud round-trip. The finished system is a different number. **This gap exists whether or not a GPU is involved**, because the system does not exist yet.
    3. **Cloud round-trip latency.** Calls per example times API latency. Part of the edge-cloud story and entirely unmeasured, since no key has been used yet.

---

## 14. Correspondence Log & Current Status

1. **Professor (initial):** two-month remote internship; FINDVER dataset; goals include reproducing/analysing the setup, a retrieval-and-verification pipeline, designing LLM "skills," and evaluating explanation quality. Tasks: (1) analyse dataset value and difficulties; (2) learn agents/skills and propose solutions. Student leads; professor refines.
2. **Student:** summarised both tasks (analysis + MACE/TART landscape + agent-with-skills proposal + backup plans); requested a meeting; asked about API access.
3. **Professor:** proposed the **cloud-edge collaborative framework** — local models ≤7–8B for the bulk of simple subtasks, cloud Qwen/DeepSeek for the complex minority.
4. **Student:** confirmed understanding; flagged the Intel Mac constraint honestly; offered Colab/lab-server fallbacks; proposed times with PDT↔China conversions.
5. **Professor:** do not upgrade hardware; **Qwen2.5-Coder-3B via Ollama** is capable as the local skill executor. **Long-context ruled out** — fitting ≠ effectively using — so the project **fully focuses on RAG**. Get familiar with Ollama, then lock a meeting.
6. **Student:** installed Ollama and models; proposed a concrete time.
7. **Student:** reported week-1 benchmark results — both models correct on a real example, 3B's reasoning internally inconsistent, 7B's cleaner; full throughput numbers; disclosed and explained the prompt-construction bug and its fix; requested API keys and flagged the DashScope region question.
8. **Professor:** away at a conference in Hangzhou; reviewed the analysis and responded positively to its thoroughness. Available **Wednesday or Thursday Beijing time**; busy Tuesday finishing an AAAI 2026 submission. Requested the visual build plan.

9. **Meeting held, 30 July 2026.** Three decisions, all of which reshape the project.
   - **Deliverable settled:** a ~5-page workshop paper for *On-Device Intelligence: Foundation Models under Real-World Constraints* (Australia), **deadline 30 August 2026**. Student first author; professor co-author; he will recruit ~2 industry co-authors. See §1.1. This closes Open Question 4 and voids the eight-week schedule (§12).
   - **Baselines will not be re-run.** Use the paper's published numbers as the historical baseline, extend the cloud row with two post-publication models, and extend the edge row with local models the paper did not evaluate. See §9.1. He independently reached the same edge-only / cloud-only framing already in the plan.
   - **Confirmed** that establishing both ends before building the routed system is the right order.

   *(The "30 August" above records what he said in the meeting. It was wrong by one day and corrected on 1 Aug from the workshop site. The real deadline is 29 August AoE, §1.1.)*

10. **Student, 3 August 2026.** Reported that the harness was nearly finished, that the loader, stratified sampler and label extractor were built and tested, and that the retriever was next. Described the Ollama context-eviction finding and the fix. Asked two questions: which two cloud models and from which provider, and which two local models. Made the case for Anthropic on published-row-continuity grounds. Mentioned a DeepSeek key was already in hand, and that a family desktop with a GPU and 32 GB RAM might become available.

11. **Professor, 3 August 2026.** Three things. He has a server with an **"NVIDIA RTX 4090 Ti"** and asked whether it would be useful. He recommends **DeepSeek**, noting a recently released model whose performance seems nearly comparable to Claude. He called the Ollama finding **"a very valuable finding."**

    **He answered one of the two questions.** Cloud is settled as DeepSeek, though he did not name the model. **The edge-model question went unanswered entirely** (§13 item 8), and it is the one that gates the schedule. He also did not engage the Anthropic argument, which was about published-row continuity rather than model strength (§13 item 7).

    Consequences recorded in §13 items 7, 8 and 11, the hardware rule in §4.2, the four-condition baseline design in §9.2, and the OQ4 attribution correction in §13 item 4. Full session detail in the build log entry for 3 August.

12. **Professor, 7 August 2026 (email).** The GPU is **not available**. He has several dozen RTX 4090 units, but they are reachable only over a local area network and neither he nor his students have been able to obtain a public IP address for them. He cannot grant access, and expects a possible fix "after the semester starts in September", which he calls "much too late." He asked for a meeting within two days, before experiments start officially.

    Consequences in §12.1, §12.3 and §13 item 11. **Band B does not open from this source.**

13. **Meeting held, 7 August 2026.** Five outcomes.

    - **The local model choice is ours.** His criteria: the strongest model that is still light, ideally around 3B to keep the on-device framing honest, chosen for the best chance of matching condition 3. He separately questioned whether a **Coder** model suits reading comprehension. See §13 item 8, which this reopens and does not close.
    - **Cloud models are `deepseek-v4-pro` and `deepseek-v4-flash`.** On Anthropic he said there is no reason not to, but he will not have me buying a key myself and he cannot buy one: he is in China, Anthropic does not serve China, and he can pay for DeepSeek. **This is a payments constraint, not a scientific objection**, and §13 item 7 previously recorded it as a preference on merit. Corrected there.
    - **GPU, as item 12.** Two fallbacks offered, neither scheduled: he will try to find a machine that can bridge access, and failing that he is **willing to pay for a rented third-party GPU server**. The brother's desktop stays first choice because it exists today.
    - **Write the paper on Overleaf.** Create a project, load the existing findings and progress into it, begin writing, and share it with him. No project exists yet.
    - **Next week's meeting is about pipeline design**, closing the gap between condition 4 and condition 3 (§9.2). Conditions 1 and 2 should be finished by then.

    Full session detail, including the live DeepSeek smoke test and the reasoning-model finding, in the build log entry for 7 August.

**Immediate next actions (sprint, deadline 29 Aug AoE):**
- [x] Install Ollama; pull models; benchmark; note throughput
- [x] Clone the repo; confirm the real data and table formats
- [x] Produce the visual build plan
- [x] Meeting held 30 Jul; venue, deadline, authorship, and baseline strategy settled
- [x] Build the harness — loader and stratified sampler done 31 Jul; label extractor and logger done and verified 1 Aug; evidence assertion, run loop and placeholder retriever done 2 Aug, with `test_scripts/test_harness.py` committed and passing 26 checks. Remaining before the first run: the Ollama client, one config file, and the entry point script.
- [x] Confirm workshop mechanics: page limit, template, anonymity, AoE deadline (§13 item 10) — done 1 Aug from the workshop site
- [x] **Decide the two cloud models** (§13 item 7) — **done 7 Aug.** Both are DeepSeek: `deepseek-v4-pro` and `deepseek-v4-flash`. Anthropic is out on payment grounds, not merit
- [ ] **Decide the local model** (§13 item 8) — **reopened by him 7 Aug and still open.** Qwen2.5-Coder-3B was his own original choice; he now questions whether a Coder model suits reading comprehension. Free to change until condition 1 starts
- [x] ~~Reply to him.~~ **Superseded by the 7 Aug meeting**, which answered the hardware, cloud-model and Anthropic questions and handed the local-model question back to us
- [x] Smoke-test the DeepSeek key — **done 7 Aug.** `deepseek-v4-pro` verified live; it is a reasoning model. DashScope/Qwen is moot, no Qwen key was issued
- [x] **Run the GPU smoke test on the brother's desktop** — **done 7 Aug, evening. 36.8x, it works.** That machine is now where every accuracy run happens (§13 item 11). The procedure file has been deleted; the setup traps are recorded in the build log entry for 7 August, evening
- [ ] **Add `"ollama_host": "10.0.0.26"` to both condition 1 configs** before running them, or they execute on the MacBook at 10.5 h each instead of ~20 min
- [ ] **Run condition 1 at k=10 and k=20**, then freeze k for every downstream condition (§9.2)
- [ ] **Create the Overleaf project and share it with him** (§14 item 13)
- [ ] Test whether `DeepSeek-V4-Flash-0731` is accepted as a model string, so the config can pin a snapshot rather than a floating alias
- [ ] Add `model` and `system_fingerprint` fields to `Record`, **with the harness update**, when the DeepSeek client is built — not before
- [x] Check the FINDVER leaderboard + cited-by sweep — **done 3 Aug** (§6.6 note 2). No leaderboard exists and email submission was retired July 2026. 23 citing papers swept; **MACE is the only published method evaluated on FINDVER.** Abstract-level screening, so the supportable phrasing is "we found no other method evaluated on FINDVER", never "nobody has"
- [ ] Confirm with the professor that the extraction/imputation finding can carry a contribution slot (§13 item 9)

---

## 15. Key Numbers Cheat Sheet

**The three targets, disambiguated in §9.3.** Recall: beat **68.01%** (we are at 57.54%). Retrieval→accuracy delta: **no target exists**, it is a number we produce. Entailment accuracy: **match our own condition 3**, not MACE — §5.3's claim is cost, not accuracy. MACE's 67.91% recall is not a target. Use **75.0% RAG**, never 77.2% long-context.

| Fact | Number |
|---|---|
| Benchmark size **(as released, counted)** | **2,400 (testmini 700 / test 1,700)** — paper says 600/1,500; see §2.6 |
| Documents | **600 files on disk, 539 referenced** (paper says 523); ~41K words avg; ~79 tables/doc (sample doc: 304 context chunks, 83 tables) |
| Best 2024 model (Claude-3.5-Sonnet, testmini) | 77.2% long-context / 75.0% RAG. **Per subset, RAG: FDV-IE 80.5, FDV-KNOW 75.5, FDV-MATH 69.0** — the numeric subset is the frontier model's weakest by 11.5 points, and it is what Tier 1 attacks (§2.6) |
| Human expert / non-expert | 93.3% / 86.7% |
| CoT gain over direct output | ~5–7 pts |
| Published evidence recall (dense, k=10) | 67.91% testmini / 69.53% test — **macro-average of per-claim fractions**, not claim completeness (§3.4) |
| Claims getting *all* gold evidence (dense, k=10, recomputed 2 Aug) | **42.6%** testmini — so 57.4% of claims are missing at least one piece |
| BM25 at k=10, same data (recomputed 2 Aug) | 65.16% macro / 62.8% element / 38.6% all-gold — free and local, within 3 points of the paid embedding |
| **Our placeholder retriever, k=10** | **57.54% macro** / 53.2% element / 31.6% all-gold — **below the 68.01% baseline**, this is the starting point to beat |
| **MACE accuracy on FINDVER** | **0.76** testmini (Qwen-235B), and **0.68** with an 8B model. *Parity, not SOTA* — FINDVER is one of the two datasets where they claim only "on par." **Verified against Table 8, 3 Aug.** Their Claude baseline disagrees with FINDVER's own table, and Table 8 never says long-context or RAG (§6.1) |
| Published methods evaluated on FINDVER | **MACE only**, from a 23-paper citation sweep on 3 Aug (§6.6). Phrase as "we found no other," not "nobody has" |
| MACE's runtime cost | **2.2×–27× slower than single-pass CoT** (their Table 5). Their efficiency claim is memory, not time, and **none of it is measured on FINDVER** (§6.1) |
| MACE's smallest configuration | **27B total parameters** across agents, 11.5% of the 235B baseline's memory (their Table 4). Ours is 3B local + cloud API |
| Deployment cost on FINDVER | **Unreported by anyone.** MACE's memory and runtime tables cover SciTab / SemTab / SciTab-OD only |
| FINDVER leaderboard | **Does not exist as a submission target.** Promised in the paper, never launched, no URL. Email submission retired July 2026 once test labels went public (§6.6) |
| Claims requiring table evidence | 66–71% |
| **Local 3B: total per example** | **7 m 0 s** measured over 12 real RAG examples, 2 Aug (week-1 single-example figure was 4 m 45 s) |
| **Local 3B: cost model** | **0.0641 s per prompt token, R² = 0.995**; sustained ingestion 15.6 tok/s |
| **Local 7B: total per example** | 11 m 46 s (7.8 tok/s in, 3.2 tok/s out) — week-1 estimate, **not re-measured** |
| **102-example round** | **~11.9 h (3B, measured)** / ~20 h (7B, estimate) |
| **Full testmini (700)** | **~81.6 h (3B, measured)** / ~137 h (7B, estimate) |
| Peak RAM | 2.5 GB (3B) / 5 GB (7B) — of 16 GB |
| Realistic RAG prompt size, *k*=10 | **2,283–11,134 tokens, mean 6,610, median 7,110** (measured 2 Aug; the old ~3,900–4,500 came from one hand-built week-1 sample) |
| Prompt chars per token, this data | **4.36 mean, 2.46–5.19 across examples** (tables low, prose high) — never budget in characters |
| 3B response length, temp 0 | mean 394 tokens, max 496, max 354 words — `num_predict` 2000 is ~4× larger than needed |
| **3B unparseable rate, our config** | **0 of 12** (upstream Llama-3.2-3B at temp 1.0: 33%) — 12 examples, not yet a rate |
| Trial-run accuracy, 3B + placeholder retriever | 8/12; 4/4 with gold evidence present, 4/8 without — **too small to cite** |
| Ollama default `num_ctx` (must override) | 4,096 |
| Pinned Ollama version (macOS 13) | v0.12.3 |
| Timezone | China = PDT + 15 h (Tue 7pm PDT = Wed 10am Beijing) |

## 16. References

- Zhao et al., 2024. *FINDVER: Explainable Claim Verification over Long and Hybrid-Content Financial Documents.* EMNLP 2024. github.com/yilunzhao/FinDVer
- Saha, Lakshmanan, Ng, 2026. *MACE: A Multi-Agent Approach for Claim Verification from Tabular Data Documents.* arXiv:2604.17225
- Lu et al., 2025. *TART: An Open-Source Tool-Augmented Framework for Explainable Table-based Reasoning.* Findings of NAACL 2025
- Sharma et al., 2025. *FISCAL* (synthetic-data financial claim verifier)
- Chen et al., 2022. *Program of Thoughts*; Gao et al., 2022. *PAL: Program-Aided Language Models*
- Wu & Feng, 2024. *ProTrix*; Kong et al., 2024. *OpenTab*; Li et al., 2024. *GraphOTTER*
- **[ADDED 3 Aug 2026, from MACE's related work] Chen et al., 2024. *TableRAG* — retrieval-augmented generation for large-table context limits.** Not previously in this list, and retrieval-plus-tables is our core, so it should be read and probably cited (§6.5). Also named there: Su et al., 2024, *TableGPT2*, trained on 593.8K tables; Zhu et al., 2024, *TAT*, which decomposes reasoning into extraction, reasoning and execution steps. Both are training-based and therefore out of our lane (§4.2), but TAT's decomposition mirrors our Tier 1 split and is worth a positioning sentence.
- Wei et al., 2022. *Chain-of-Thought Prompting*
