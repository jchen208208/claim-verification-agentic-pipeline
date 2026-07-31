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

A **~5-page workshop paper**, submitted to *On-Device Intelligence: Foundation Models under Real-World Constraints* (workshop, Australia). **Submission deadline: 30 August 2026.** Confirmed with the professor at the 30 July meeting (§14 item 9); this closes what was Open Question 4.

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
**Evidence recall** = of the gold evidence pieces a claim needs, what fraction did retrieval actually fetch? The published FINDVER setup (OpenAI text-embedding-3, k=10) achieves only **~68–70%** (67.91% testmini / 69.53% test, per MACE). So for roughly **3 in 10 claims, at least one required piece of evidence never reaches the model** — a hard accuracy ceiling that no downstream reasoning improvement can break. Every published approach copied this setup rather than improving it. Because gold indices exist, retrieval can be improved and measured **in isolation, almost for free** — no LLM calls, just set comparisons — making "we raised recall from 68% to X%" a clean, self-contained reportable result that costs nothing in compute.

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

**Critical: Ollama's default context window is 4,096 tokens and it truncates silently.** A realistic RAG prompt for this benchmark runs ~3,900–4,500 tokens, so the default clips real evidence with no warning, no error, and no indication in the output. In week-1 testing this produced confident hallucinated figures that looked exactly like a genuine extraction failure. Every run must set the window explicitly:

```
/set parameter num_ctx 8192          # interactive
{"options": {"num_ctx": 8192}}       # REST API
```

Sanity check after every run: `prompt eval count` should be comfortably *below* the configured window. A value sitting exactly at the ceiling means truncation.

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
| Filling the final output template | **Edge** (3B) | Formatting after reasoning is done |

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
| Followed required output format | no | no |

**Batch runtime implications — these drive the schedule:**

| Run size | 3B | 7B |
|---|---:|---:|
| 100 examples (one ablation round) | ~7.9 h | ~19.6 h |
| Full testmini, **700** examples | ~55 h (≈2.3 days) | ~137 h (≈5.7 days) |

Three conclusions follow directly:
1. **Prompt ingestion dominates**, not generation — roughly 3–4× the cost of producing the answer. Retrieval tightness (*k*) is therefore a **performance** parameter, not only an accuracy one. Retrieving 10 chunks where 4 suffice is a direct multiplier on every experiment's wall-clock time. This is an argument for claim-decomposed retrieval on efficiency grounds *in addition to* recall grounds.
2. **A 100-example round on 3B is an overnight job.** Iteration cadence is roughly one ablation configuration per day. The 8-week plan must respect that.
3. **7B is for spot-checks, not batches.** At ~5.7 days per full testmini pass it cannot sit in the ablation loop, but it remains valuable for qualitative comparison on small samples.

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

### 7.3 Retriever
Local embedding model + BM25, merged by reciprocal rank fusion; per-sub-claim queries once decomposition lands; tables kept whole as chunks with header/unit/period metadata. Evaluated standalone against gold `relevant_context` indices before any end-to-end run. **[MEASURED]** Also sweep *k* — §4.6 shows it is a wall-clock multiplier as well as a recall lever.

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
| — | Harness: loader, stratified sampler, logging, label extractor, evidence assertion | — | **in progress** · loader + sampler done and committed 31 Jul; label extractor next | Prerequisite for everything; small but non-optional (§11.8–11.9) |
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
- Evidence recall vs. gold `relevant_context`, per retrieval variant (whole-claim dense / +BM25 / +decomposition / varying *k*).
- **[NEW]** Computation accuracy on the `numeric` subset: agent's computed value vs. gold `execution_result` — isolates arithmetic correctness from verdict correctness (§2.5).
- Faithfulness: % of explanation steps verifiable against the document (new metric).
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
8. **[REVISED 31 Jul] Verdict extraction — the fixed-final-line assumption failed, and the official scoring hides the failure.** The previous plan assumed enforcing `"Therefore, the claim is {entailed|refuted}."` in the prompt would make post-processing unnecessary. **In week-1 testing neither the 3B nor the 7B model produced the required sentence**, despite explicit instruction; both wrote discursive conclusions instead. Label extraction therefore needs: (a) regex for the canonical sentence; (b) fallback patterns for common paraphrases; (c) an explicit `unparseable` bucket that is counted and reported rather than silently coerced.

   **What the official evaluation actually does** (read from `FinDVer/evaluation.py` and `utils/evaluation_utils.py`, 31 Jul). It extracts the verdict with a **`gpt-4o-mini` call per example**, asking for `entailed` / `refuted` / `none`. When the answer is `none` it assigns `random.choice(["entailed", "refuted"])`: the example is scored as a guess, and is never counted, reported, or excluded. No `random.seed` appears anywhere in the repo, so the official score is not reproducible on identical predictions. Separately, the *direct*-prompting path tests `"entail" in output` before `"refut"`, and "entail" is a substring of "not entailed", so that path mislabels negated conclusions; CoT does not use it, so it does not affect our comparison baseline.

   **Why this matters at our scale.** For the paper's models, unparseable outputs are rare and coin-flipping them moves the score by well under a point. At 3B they are not rare. A model failing the format on 30% of examples receives roughly 15 accuracy points of imputation rather than reasoning. This is not a flaw in the benchmark; it is an assumption that does not hold in our regime, which is a more defensible and more interesting claim.

   **[MEASURED 31 Jul] A deterministic regex is nearly as accurate as the cloud extractor; the gap is coverage.** `outputs/testmini_outputs/rag/processed_cot_outputs/` ships 700 examples for each of 16 models, storing both the raw response and the `gpt-4o-mini` label. Across all 11,200 pairs, a first-pass regex fires on **81.7%** and, where it fires, agrees with `gpt-4o-mini` on **98.9%**. Coverage tracks model size: claude-3-5-sonnet 100%, gpt-4o 99.7%, Qwen2.5-7B 91.3%, Llama-3.2-3B **54.9%**, Llama-3.1-8B 52.9%. Two caveats. `extracted_label` is stored *after* the coin flip, so imputed labels are indistinguishable from real ones, and the ~45% miss at 3B is an unseparated mix of "no verdict stated" and "verdict phrased differently." The 98.9% agreement is also measured only where a clean sentence exists, i.e. on the easy subset.

   **Decision.** Build the extractor deterministically and develop it against those 11,200 stored responses, which needs no model run and no quota. Defer any model-based fallback until widened patterns have been measured. Replicating the official extractor is impossible regardless: it uses `gpt-4o-mini`, and the available cloud keys are DeepSeek and Qwen, so the model route costs quota without buying comparability.
9. **[NEW] Assert evidence presence before every model call.** Week-1 testing lost one test round, roughly 15 minutes, to a silent data bug. It was caught during single-example testing, which is the only reason it was cheap; the same bug inside a 100-example overnight run costs ~8 h. Report `context` elements are dicts (§2.3), a loader assumed strings, and the fallback serialised raw dicts into the prompt while truncating each to 2,000 characters. Both models then produced confident figures that appear nowhere in the source document — a failure indistinguishable, from the output alone, from a genuine extraction error. Had this reached the ablation, it would have been mislabelled "extraction error" or "domain knowledge deficiency" and corrupted the error analysis. **Mitigation, cheap and permanent:** after building each prompt, assert that the gold evidence string (or a distinctive numeric token from it) is literally present; log a warning and flag the example otherwise. Also log `prompt eval count` per call and alarm if it equals the configured context window (truncation signature).
10. **[NEW] Config gotchas that bite silently:** Ollama `num_ctx` defaults to 4096 and truncates without warning (§4.3); Ollama auto-update must stay disabled to preserve v0.12.3 macOS-13 compatibility; interactive `/set parameter` does not persist across sessions — the REST harness must set it per call.

---

## 12. Timeline

> **[REPLANNED 31 Jul 2026] The eight-week schedule is void.** The 30 July meeting set a hard deliverable: a ~5-page workshop paper, submission deadline **30 August 2026** (§1.1, §14 item 9). That is **30 days from 31 July**, not eight weeks.
>
> **Nothing is cut outright.** Scope is banded by what compute is available (§12.3), because faster hardware may become available and would move the bands. Retrieval in particular stays in scope: it is the project's core (§3.3), and its recall measurement needs no model runs at all.

### 12.1 The binding constraint is local wall-clock

Measured throughput (§4.6) converts directly into nights, and the machine runs one job at a time:

| run | examples | wall-clock | nights |
|---|---|---|---|
| 3B, stratified slice | 102 | ~8 h | 1 |
| 7B, stratified slice | 102 | ~20 h | 2–3 |
| 3B, full testmini | 700 | ~55 h | ~7 |
| cloud model, slice | 102 | API-bound, hours not nights | ~0 |

Between 3 August and 23 August there are roughly **20 usable nights**, and results must freeze before writing. On *this machine* a full-700 run would consume a third of that budget on one number, which is why it sits in the conditional band (§12.3) rather than the committed one.

**Two asymmetries decide what is affordable, and neither is about the tier number.**

- **Cloud runs are nearly free in wall-clock.** API-bound, hours not nights. Local runs are the scarce resource; cloud runs are not.
- **Retrieval recall is free in wall-clock.** It scores retrieved chunk indices against gold `relevant_context` (§9) using embeddings and plain Python, with **no LLM calls**. A *k* sweep, a BM25 comparison, and a decomposition comparison are all minutes, not nights, and they can run during the day while an overnight job holds the evening. Only the *end-to-end accuracy delta* from better retrieval needs a night.

So "Tier 2 is expensive" is false as stated. Its measurement half is one of the cheapest things in the project, and it is the half most on-topic for a RAG-focused paper.

**[OPEN] Faster hardware may become available.** If it does, the night budget stops binding and the conditional band opens: full-700 runs, end-to-end retrieval ablations, and 7B slice comparisons all become affordable. Specs and availability date are unknown as of 31 July (§13 item 11). Until they are known, plan against this machine and treat anything faster as upside rather than assumption.

### 12.2 The 30-day plan

**Phase 1 · 31 Jul – 2 Aug · Finish the harness.**
Label extractor (§11.8), per-example logging, evidence assertion (§11.9). Loader and sampler are done and committed. None of this is blocked on cloud keys. The label extractor is developed offline against the 11,200 stored responses in `outputs/`, at zero compute cost.

**Phase 2 · 3 – 10 Aug · Baselines.**
Edge-only on the 102-example slice, 3B and 7B. Two new cloud models on the same slice, once keys arrive. **Published FINDVER numbers are reused as the historical baseline rather than re-run** (§9), which is what makes this phase fit at all. Hand-label ~25 failures per configuration. Deliverable: the baseline table plus error distributions.

**Phase 3 · 11 – 20 Aug · Ablations, cheap-measurement work first.**
Two strands run in parallel, because they compete for different resources.

*Daytime, no model runs.* **Tier 2 retrieval recall**: claim decomposition, BM25 plus dense fusion, table-aware chunk metadata, *k* sweep, all scored against gold indices (§7.3, §9). This is the project's core question (§3.3) and it costs minutes. Target: meaningfully above the 68–70% recall ceiling.

*Overnight, one configuration per night.* **Tier 1 code execution and tables-as-DataFrames**, the highest-certainty accuracy gain, validated against gold `execution_result` (§2.5) before touching end-to-end runs. Then the end-to-end delta from whichever retrieval variant won on recall, if nights remain.

**Decision point 15 Aug:** whatever is not working by then is dropped from the paper, not debugged. Recall numbers stand on their own even if the end-to-end delta never gets measured, which is the reason to front-load them.

**Phase 4 · 21 – 23 Aug · Freeze.**
No new configurations. Final numbers, both scorings (§9), final taxonomy distribution before versus after.

**Phase 5 · 24 – 30 Aug · Write.**
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

1. **Where should the edge/cloud line actually sit?** §4.5 — the 3B model handled a full end-to-end verification correctly, which the original allocation did not anticipate. Options: keep the conservative allocation; move more to edge and escalate only on verifier failure; or treat the threshold as a swept parameter from the start.
2. **Cloud API keys** — DeepSeek and/or Qwen, plus which DashScope region for Qwen (§11.2).
3. **Is ~8 h per 100-example round acceptable**, or should batch runs move to Colab / a lab server now rather than as a fallback?
4. ~~**Target venue and rigour level.**~~ **ANSWERED 30 Jul:** ~5-page workshop paper, *On-Device Intelligence: Foundation Models under Real-World Constraints*, deadline 30 Aug 2026 (§1.1). Leaderboard submission and the full 700-example run are consequently **out of scope** (§12.1).
5. **Does the faithfulness metric interest him as a contribution in its own right?** It is the most novel piece and the natural centrepiece if accuracy saturates (§7.5). Now in **Band C** (§12.3), and the first thing to promote if the schedule loosens or faster hardware arrives, so his appetite for it is worth knowing *before* that decision rather than after.
6. **Confirm plain-script implementation** over AutoGen (§3.11), with the debuggability rationale.

**Opened by the 30 July meeting and the 31 July measurements:**

7. **Which two cloud models, and which provider?** He said newer models generally, and separately that Anthropic keys can be provided. Anthropic is the tighter comparison, since `claude-3-5-sonnet` is the paper's top scorer and a newer Claude extends that exact row. DeepSeek and Qwen match the cloud-edge framing in §4.1. Needs a decision before Phase 2 (3 Aug).
8. **Which edge models to add?** The paper already covers Llama-3.2-3B, Llama-3.1-8B, Qwen2.5-7B, Mistral-7B and others (full list in `outputs/`). Ours must be models it did **not** evaluate, and each 7B-class slice run costs 2–3 nights (§12.1). Two is realistic; three is not.
9. **Is the extraction/imputation finding acceptable as a headline contribution?** §11.8, measured on 11,200 responses at zero compute cost, and squarely on-venue. With Tiers 2–5 cut, the paper needs a result that does not depend on a long run chain. Worth confirming he agrees before building the paper around it.
10. **Workshop submission mechanics** — exact page limit, template, anonymity requirement, and whether the 30 Aug deadline is anywhere-on-earth. These change the writing schedule in Phase 5 and none of them are known yet.
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

**Immediate next actions (30-day sprint, deadline 30 Aug):**
- [x] Install Ollama; pull models; benchmark; note throughput
- [x] Clone the repo; confirm the real data and table formats
- [x] Produce the visual build plan
- [x] Meeting held 30 Jul; venue, deadline, authorship, and baseline strategy settled
- [~] Build the harness — loader and stratified sampler done and committed 31 Jul; logger, label extractor, evidence assertion remain. Next session builds the label extractor against the 11,200 stored responses in `outputs/` (§11.8); it needs no cloud keys and is not blocked. **Due 2 Aug.**
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
| Published evidence recall (dense, k=10) | 67.91% testmini / 69.53% test |
| Claims requiring table evidence | 66–71% |
| **Local 3B: total per example** | **4 m 45 s** (19.1 tok/s in, 6.7 tok/s out) |
| **Local 7B: total per example** | **11 m 46 s** (7.8 tok/s in, 3.2 tok/s out) |
| **100-example round** | **~7.9 h (3B) / ~19.6 h (7B)** |
| **Full testmini (700)** | **~55 h (3B) / ~137 h (7B)** |
| Peak RAM | 2.5 GB (3B) / 5 GB (7B) — of 16 GB |
| Realistic RAG prompt size | ~3,900–4,500 tokens |
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
