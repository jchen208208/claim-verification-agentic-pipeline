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

**[CORRECTED 1 Aug 2026 from the workshop site, odi2026.github.io] The deadline is 29 August, not 30.** Mechanics read directly from the call for papers, which closes Open Question 10 (§13):

| | |
|---|---|
| Venue | **NeurIPS 2026 workshop**, Sydney, Australia, 11/12 December 2026 |
| **Deadline** | **29 August 2026, 23:59 AoE** = **04:59 PDT on 30 August** = 19:59 Beijing, 30 Aug |
| Length | **5 pages excluding references** |
| Template | **NeurIPS 2026 LaTeX template** |
| Review | **Double-blind** |
| Archival | **Non-archival** |
| Submission | OpenReview |
| Notification | 29 September 2026 |
| Contact | odi.neurips2026@gmail.com |

Four consequences, in order of how much they change:

1. **One day is gone from Phase 5.** Every plan document said 30 August. The writing window is 24 to 29 August, six days, not seven. The AoE clock gives until 04:59 PDT on the 30th, which is a buffer for the upload and not a working day.
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
> The test-label finding is the consequential one: we can score the test split locally instead of depending on the leaderboard. Confirm on the leaderboard page before relying on it, since local test numbers are not officially comparable to published ones.

- 523 filings, 2,400 claims per the paper: **testmini** 600 (200/subset, fully labelled) and **test** 1,500 (labels withheld; leaderboard only). See the correction box above for what shipped.
- Documents first released Jan–Apr 2024, chosen to post-date 2024-era training cutoffs. That protection has expired for 2026 models — see §10, Plan C.
- ~66–71% of claims require table evidence.
- Refuted claims were made by expert perturbation of entailed claims, so the error is directly contradicted by annotated evidence.
- Best 2024 results (testmini): Claude-3.5-Sonnet 77.2% long-context / 75.0% RAG; GPT-4o 75.7 / 73.7. Human expert 93.3%; non-expert 86.7%; random 50%.
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

**Two further findings from the same recomputation.** First, **BM25 reaches 65.16% against the paid embedding's 68.01%, and beats it on element recall (62.8% vs 62.4%)**. A free, local, dependency-light retriever is within three points of `text-embedding-3-large` on the metric the paper reports. For an on-device paper that is a result in itself, and it means the hybrid of §7.3 starts from a strong free baseline rather than needing an embedding API. Second, k dominates: `text-embedding-3-large` drops from 68.01% at k=10 to 54.53% at k=5 and 43.60% at k=3, so the k sweep is not a formality.

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

---

## 6. Related Work Since FINDVER — What Exists, and Its Weaknesses

### 6.1 MACE (Saha, Lakshmanan & Ng, UBC — arXiv 2604.17225, 2026) — the main competitor
- **What:** Planner/Executor/Verifier multi-agent framework on AutoGen with constrained speaker transitions and feedback loops. **Zero-shot CoT only — no training.** Evaluated directly on FINDVER testmini and test; claims SOTA/parity; smaller open models (27–92B) reach 80–100% of a 235B model's performance.
- **Weakness 1 — no code execution.** The Executor performs computations inside its natural-language output; their own published example sums seven six-digit figures in prose and contains an apparent transcription slip (1,099,107 vs 1,999,107 two lines apart). The computation-error category is unaddressed by the current best approach.
- **Weakness 2 — retrieval untouched.** They state retrieval "is not our focus" and copy FINDVER's setup, reporting 67.91% / 69.53% recall — the ceiling sits unattacked.
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
2. The search behind this section is not exhaustive. **Outstanding week-1 task:** check the FINDVER leaderboard for recent entries and run a Google Scholar cited-by sweep before repeating any "nobody has done X" claim. *(Still open — carry into week 2.)*
3. Sit with "why has nobody done the obvious thing?" Likely: niche benchmark, ~18 months old, field moved fast. Possible: someone tried and gains were small. The ablation reveals which — either outcome is a finding.

---

## 7. The Skills, in Implementation Detail

### 7.1 **[RESOLVED]** Table Normalizer — much cheaper than planned

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

### 7.2 Code Sandbox
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
- FINDVER 2024 originals (77.2 / 75.7; humans 93.3 / 86.7) and MACE's published numbers.
- Edge-only vs. cloud-only vs. routed, at each ablation tier.
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
2. **[NEW] Cloud API endpoints.** **DeepSeek** runs a single global API (`api.deepseek.com`), OpenAI-SDK-compatible — one key, no regional configuration, expected to work from Canada with no setup. **Qwen** runs on Alibaba's DashScope, which is split into **separate regional deployments (China / Singapore / US) whose keys are not interchangeable** — a key issued in one region returns 401 against another. A China-region key is reachable from outside China (no VPN needed), just with higher latency. Action on receipt: run a one-call smoke test; a 401 identifies a region mismatch rather than a bad key, and only the `base_url` changes.
3. **Dataset:** full repo cloned. Leaderboard + Scholar sweep still outstanding.
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

**Two asymmetries decide what is affordable, and neither is about the tier number.**

- **Cloud runs are nearly free in wall-clock.** API-bound, hours not nights. Local runs are the scarce resource; cloud runs are not.
- **Retrieval recall is free in wall-clock.** It scores retrieved chunk indices against gold `relevant_context` (§9) using embeddings and plain Python, with **no LLM calls**. A *k* sweep, a BM25 comparison, and a decomposition comparison are all minutes, not nights, and they can run during the day while an overnight job holds the evening. Only the *end-to-end accuracy delta* from better retrieval needs a night.

So "Tier 2 is expensive" is false as stated. Its measurement half is one of the cheapest things in the project, and it is the half most on-topic for a RAG-focused paper.

**[OPEN] Faster hardware may become available.** If it does, the night budget stops binding and the conditional band opens: full-700 runs, end-to-end retrieval ablations, and 7B slice comparisons all become affordable. Specs and availability date are unknown as of 31 July (§13 item 11). Until they are known, plan against this machine and treat anything faster as upside rather than assumption.

### 12.2 The 30-day plan

**Phase 1 · 31 Jul – 2 Aug · Finish the harness.**
Label extractor (§11.8), per-example logging, evidence assertion (§11.9). Loader and sampler are done and committed. None of this is blocked on cloud keys. The label extractor is developed offline against the 11,200 stored responses in `outputs/`, at zero compute cost.

**[UPDATED 1 Aug 2026]** The extractor and the logger are both done and verified. `src/logger.py` holds a 17-field `Record` dataclass, `write_result()` writing one JSON file per claim into `results/<experiment>/`, and `has_result()` giving resume by skipping ids that already completed. Resume tests `status == "ok"` rather than file existence, because a failed example still writes a file, and a truncated JSON file returns `False` rather than raising. **The phase is one item longer than this line says: the run loop was never in the list of five and the trial run cannot happen without it.** Remaining: evidence assertion, then the run loop, then the 12-example trial run.

**Phase 2 · 3 – 10 Aug · Baselines.**
Edge-only on the 102-example slice, 3B and 7B. Two new cloud models on the same slice, once keys arrive. **Published FINDVER numbers are reused as the historical baseline rather than re-run** (§9), which is what makes this phase fit at all. Hand-label ~25 failures per configuration. Deliverable: the baseline table plus error distributions.

**Phase 3 · 11 – 20 Aug · Ablations, cheap-measurement work first.**
Two strands run in parallel, because they compete for different resources.

*Daytime, no model runs.* **Tier 2 retrieval recall**: claim decomposition, BM25 plus dense fusion, table-aware chunk metadata, *k* sweep, all scored against gold indices (§7.3, §9). This is the project's core question (§3.3) and it costs minutes. Target: meaningfully above the 68–70% recall ceiling. **[REVISED 2 Aug]** The starting point is better understood than it was: BM25 alone already reaches 65.16% on their metric (§3.4), so the fusion has to beat 68.01% rather than 68% being far away, and every recall number must be reported on all three metrics because the published one is a macro-average that reads as something else.

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

**Band B — conditional on faster hardware, or on Band A finishing early.**
End-to-end accuracy delta from the winning retrieval variant. Full 700-example testmini run. 7B slice comparisons. Leaderboard submission. Each of these is a night or several on the current machine; on faster hardware they are cheap. **Do not design the paper to require them, and do not design it to preclude them.** Note the full-700 run has an independent motive beyond precision: the ±10-point margin at n=102 (§9) makes any close comparison unresolvable, so if compute appears, this is the first thing it buys.

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
4. ~~**Target venue and rigour level.**~~ **ANSWERED 30 Jul:** ~5-page workshop paper, *On-Device Intelligence: Foundation Models under Real-World Constraints*, deadline 29 Aug 2026 AoE (§1.1, corrected 1 Aug). Leaderboard submission and the full 700-example run are consequently **out of scope** (§12.1).
5. **Does the faithfulness metric interest him as a contribution in its own right?** It is the most novel piece and the natural centrepiece if accuracy saturates (§7.5). Now in **Band C** (§12.3), and the first thing to promote if the schedule loosens or faster hardware arrives, so his appetite for it is worth knowing *before* that decision rather than after.
6. **Confirm plain-script implementation** over AutoGen (§3.11), with the debuggability rationale.

**Opened by the 30 July meeting and the 31 July measurements:**

7. **Which two cloud models, and which provider?** He said newer models generally, and separately that Anthropic keys can be provided. Anthropic is the tighter comparison, since `claude-3-5-sonnet` is the paper's top scorer and a newer Claude extends that exact row. DeepSeek and Qwen match the cloud-edge framing in §4.1. Needs a decision before Phase 2 (3 Aug).
8. **Which edge models to add?** The paper already covers Llama-3.2-3B, Llama-3.1-8B, Qwen2.5-7B, Mistral-7B and others (full list in `outputs/`). Ours must be models it did **not** evaluate, and each 7B-class slice run costs 2–3 nights (§12.1). Two is realistic; three is not.
9. **Is the extraction/imputation finding acceptable as a headline contribution?** §11.8, measured on 11,200 responses at zero compute cost. The paper needs at least one result that does not depend on a long run chain, since Band B is conditional (§12.3). Worth confirming he agrees before building the paper around it. *(Corrected 1 Aug: this item previously read "with Tiers 2–5 cut", which contradicts §12.3. Nothing is cut; scope is banded.)*

   **[NEW 1 Aug] The call for papers argues this case for us.** Topic 05 is "Benchmarks and Evaluation for Interactive Real-World Deployment", asking for *metrics that jointly assess performance, latency, energy, memory, safety, and reliability under realistic deployment conditions*. A benchmark whose official scoring silently imputes a large share of a small model's reported accuracy is exactly a reliability-of-evaluation finding, and it is the workshop's own listed topic rather than our stretch of one. That is a strong argument to put to him alongside the question. Topic 02, "Efficient Adaptation, Inference and Reasoning under Real-World Constraints", covers the edge-cloud pipeline. **Name both topics on the submission.**
10. ~~**Workshop submission mechanics.**~~ **ANSWERED 1 Aug 2026** from the workshop site (odi2026.github.io), not from the professor. Full table in §1.1. Headlines: the deadline is **29 August AoE, not 30**, the review is **double-blind**, the venue is **non-archival**, 5 pages excluding references, NeurIPS 2026 LaTeX template, submitted via OpenReview.
11. **What faster hardware is actually available, and when?** Specs, access method, and date. This decides whether Band B (§12.3) opens: full-700 runs, end-to-end retrieval ablations, 7B comparisons. Two sub-questions matter. Does it have a usable GPU, which changes throughput by a large factor rather than a small one? And is Ollama's pinned-0.12.3 macOS-13 constraint (§11.10) even relevant there, or does a different machine mean a different and unpinned runtime? Until this is answered, plan against the current machine and treat anything faster as upside.

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

**Immediate next actions (sprint, deadline 29 Aug AoE):**
- [x] Install Ollama; pull models; benchmark; note throughput
- [x] Clone the repo; confirm the real data and table formats
- [x] Produce the visual build plan
- [x] Meeting held 30 Jul; venue, deadline, authorship, and baseline strategy settled
- [x] Build the harness — loader and stratified sampler done 31 Jul; label extractor and logger done and verified 1 Aug; evidence assertion, run loop and placeholder retriever done 2 Aug, with `test_scripts/test_harness.py` committed and passing 26 checks. Remaining before the first run: the Ollama client, one config file, and the entry point script.
- [ ] Confirm workshop mechanics: page limit, template, anonymity, AoE deadline (§13 item 10)
- [ ] Decide the two cloud models and the two added edge models (§13 items 7–8) — **needed before 3 Aug**
- [ ] Smoke-test cloud keys on arrival; confirm DashScope region
- [ ] Check the FINDVER leaderboard + Scholar cited-by sweep — still outstanding from week 1, and now also needed for the related-work section
- [ ] Confirm with the professor that the extraction/imputation finding can carry a contribution slot (§13 item 9)

---

## 15. Key Numbers Cheat Sheet

| Fact | Number |
|---|---|
| Benchmark size **(as released, counted)** | **2,400 (testmini 700 / test 1,700)** — paper says 600/1,500; see §2.6 |
| Documents | **600 files on disk, 539 referenced** (paper says 523); ~41K words avg; ~79 tables/doc (sample doc: 304 context chunks, 83 tables) |
| Best 2024 model (Claude-3.5-Sonnet, testmini) | 77.2% long-context / 75.0% RAG |
| Human expert / non-expert | 93.3% / 86.7% |
| CoT gain over direct output | ~5–7 pts |
| Published evidence recall (dense, k=10) | 67.91% testmini / 69.53% test — **macro-average of per-claim fractions**, not claim completeness (§3.4) |
| Claims getting *all* gold evidence (dense, k=10, recomputed 2 Aug) | **42.6%** testmini — so 57.4% of claims are missing at least one piece |
| BM25 at k=10, same data (recomputed 2 Aug) | 65.16% macro / 62.8% element / 38.6% all-gold — free and local, within 3 points of the paid embedding |
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
- Wei et al., 2022. *Chain-of-Thought Prompting*
