# Local Embedding Model Screening Progress Report

**Project:** CAD-Aware AI Assistant - Shock Isolator Selection  
**Report date:** 2026-07-14  
**Status:** Exploratory local embedding comparison completed; `bge-m3` selected provisionally for the shock-mount RAG index  
**Scope:** Dense retrieval only. This is a development-stage model-selection record, not final FYP performance evidence.

## 1. Purpose

The project uses two different AI components that must not be confused:

1. The **language model** interprets the request, selects tools, supplies tool
   arguments, and writes the final explanation.
2. The **embedding model** converts a RAG query and the reference passages into
   vectors. Cosine similarity ranks passages so the language model can cite or
   explain engineering material.

This experiment evaluates the second component only. It does not test shock
physics, tool calling, final answer quality, or citation formatting. The Python
engineering tools remain the numerical authority.

The question addressed here is:

> Which locally served dense embedding model most reliably retrieves the
> required shock-mount engineering reference within the top three passages?

The top-three criterion is important because `lookup_knowledge` returns the
top three matching pages to the language model.

## 2. Controlled experiment design

### 2.1 Fixed corpus and retrieval method

All candidates used exactly the same conditions:

| Item | Fixed value |
|---|---|
| Corpus | 38 Markdown chunks from `knowledge/shock_mount/` |
| Chunking | One focused Markdown file per chunk |
| Chunk IDs | Stable `shock_mount/<filename-stem>` IDs |
| Search method | Exact dense cosine similarity in `JSONVectorStore` |
| Metadata filter | `parent_topic="shock_mount"` |
| Ranking depths | Top 1, top 3, and top 5 |
| Ground truth | `evaluation/retrieval_qrels_shock_v1.jsonl` |
| Hardware and serving | Same Windows laptop and local Ollama server |

No FAISS, sparse retrieval, reranking, hybrid retrieval, query expansion, or
LLM-as-a-judge was used. This deliberately isolates the dense embedding model
as the changing variable.

### 2.2 Development query set

The qrels file contains 18 queries:

| Query class | Count | Purpose |
|---|---:|---|
| Standards and tailoring | 5 | MIL-STD-810H Method 516.8 scope, tailoring, pulses, and field data |
| Catalogue | 3 | Vendor data and static-load provenance |
| Physics | 2 | Shock-pulse and transmissibility explanations |
| Workflow | 3 | Selection and verification procedures |
| Limitations | 2 | Model and qualification boundaries |
| Scope boundary | 1 | A Method 514.8 vibration-procedure request should retrieve the scope limitation |
| Out-of-scope adversarial | 2 | CFD and bolt-torque questions with no relevant shock-mount passage |

The first six categories give **16 in-scope queries**. The two out-of-scope
queries are reported separately because their expected relevant set is empty.

This is a development set. It was used to select an embedding configuration and
must not be reused as final evidence for the B/C/D benchmark.

### 2.3 Candidate-specific query handling

Each candidate used its documented or model-appropriate query convention. The
passage text was not prefixed.

| Candidate | Ollama model tag | Query handling |
|---|---|---|
| BGE-M3 | `bge-m3` | No query prefix |
| Qwen3 Embedding 8B | `qwen3-embedding:8b` | `Instruct: Given a technical engineering question, retrieve relevant shock-mount reference passages that answer the question\nQuery: ` |
| Mixedbread Embed Large v1 | `hf.co/mixedbread-ai/mxbai-embed-large-v1:F16` | `Represent this sentence for searching relevant passages: ` |

Using model-recommended query formatting is not an uncontrolled advantage. It
is part of a model's intended retrieval interface and is recorded so the
selected configuration can be reproduced.

## 3. Metrics

For a query with one or more required chunk IDs:

- **Hit@k:** at least one required chunk appears in the first `k` retrieved
  results.
- **Recall@k:** fraction of all required chunk IDs recovered in the first `k`
  results. This is stricter where a query has two relevant passages.
- **MRR:** reciprocal rank of the first required passage. A value of 1 means a
  required reference was ranked first; 0.5 means it first appeared second.

Raw cosine similarity values are not compared between embedding models. Each
model creates a different vector space and scale. Retrieval ranks and outcome
metrics are the meaningful comparison.

## 4. Results

### 4.1 Overall in-scope retrieval results

| Metric (16 in-scope queries) | BGE-M3 | Qwen3 Embedding 8B | Mixedbread Embed Large v1 |
|---|---:|---:|---:|
| Hit@1 | **81.25%** | 75.00% | 62.50% |
| Recall@1 | **62.50%** | 56.25% | 46.88% |
| Hit@3 | **100.00%** | 93.75% | **100.00%** |
| Recall@3 | 87.50% | 87.50% | **90.62%** |
| Hit@5 | **100.00%** | **100.00%** | **100.00%** |
| Recall@5 | 90.62% | 90.62% | **93.75%** |
| MRR | **0.9062** | 0.8458 | 0.7812 |

The primary deployment metric is Hit@3 because the current RAG tool supplies
three passages to the language model. BGE-M3 was the only candidate with both
perfect Hit@3 and the highest MRR, meaning it retrieved a required chunk for
every in-scope question and placed it nearest the top on average.

Mixedbread recovered slightly more of multi-reference queries by top 3 and top
5, but its much lower Hit@1 and MRR show that it often ranked less relevant
material above the required workflow or physics reference. The current tool
does not need to retrieve every relevant chunk to be useful; it needs a
reliable, well-ranked grounding passage within its three-passage budget.

### 4.2 Hit@1 by content category

| Category | Queries | BGE-M3 | Qwen3 Embedding 8B | Mixedbread |
|---|---:|---:|---:|---:|
| Standards | 5 | **80.0%** | 40.0% | 60.0% |
| Catalogue | 3 | **100.0%** | **100.0%** | **100.0%** |
| Physics | 2 | 50.0% | **100.0%** | 50.0% |
| Workflow | 3 | **100.0%** | **100.0%** | 33.3% |
| Limitations | 2 | **100.0%** | **100.0%** | **100.0%** |
| Scope boundary | 1 | 0.0% | 0.0% | 0.0% |

All three candidates retrieved the scope-boundary page within the top three,
but none ranked it first. This is acceptable for the current three-passage RAG
tool, but the query will remain useful when testing scope-aware final answers.

### 4.3 Out-of-scope probes

| Measure | BGE-M3 | Qwen3 Embedding 8B | Mixedbread |
|---|---:|---:|---:|
| Adversarial queries | 2 | 2 | 2 |
| Mean top-1 similarity | 0.5219 | 0.5498 | 0.6024 |
| Mean top-1 similarity for in-scope queries | 0.6263 | 0.7615 | 0.7492 |

Each candidate gave lower average similarity to the two out-of-scope queries
than to in-scope queries. However, two adversarial examples are far too few to
derive a safe numerical rejection threshold. The application must continue to
use its explicit scope instructions and language-model judgment rather than
treating a cosine score as a safety decision.

## 5. Per-model error analysis

### 5.1 BGE-M3

BGE-M3 missed top-1 on three queries, but recovered a required reference in the
top three in every case:

- `rag03`: ranked `pulse_sawtooth` first; the required classical-pulse and
  half-sine pages were ranked second and third.
- `rag10`: ranked a related travel-limit page first; transmitted-acceleration
  and dynamic-deflection pages were available within the top four.
- `rag18`: ranked the general MIL-STD basis page first; the required
  `standard_scope` limitation page was second.

These are near-neighbour confusions within the same engineering subject area,
not unrelated retrieval. They are compatible with the present top-three design.

### 5.2 Qwen3 Embedding 8B

Qwen3 Embedding 8B was strongest on the two physics questions but weaker on the
standards/tailoring subset. It failed top-1 on `rag01`, `rag03`, `rag05`, and
`rag18`; `rag05` placed the required project-requirements page fifth, causing
the only Hit@3 failure among the 16 in-scope queries. This is material because
the project needs dependable reference retrieval for Method 516.8 interpretation
and test-tailoring caveats.

### 5.3 Mixedbread Embed Large v1

Mixedbread achieved Hit@3 of 100%, but its ranking was less precise. It failed
top-1 on six queries, including two of the three workflow questions. In
particular, `rag12` ranked the general formulas page above the required
selection workflow, while `rag13` ranked selection rules above verification
workflow/governing-check references. This lower workflow precision makes it a
weaker match for an engineering assistant that must explain the correct process
as well as formulas.

## 6. Selection decision

**Selected local embedding model: `bge-m3`**

The selection is based on the following pre-final development evidence:

1. It achieved the highest Hit@1 and MRR across the 16 in-scope questions.
2. It was the only candidate with perfect Hit@3, matching the application's
   three-passage retrieval budget.
3. It achieved perfect top-1 retrieval for catalogue, workflow, and limitation
   questions, and strong results for standards questions.
4. It is a smaller embedding model than the Qwen 8B candidate, making it the
   more practical local companion to the selected Qwen3.5 9B language model.
5. Its misses were all related pages and still yielded a required chunk in the
   three retrieved passages.

This does **not** prove BGE-M3 is universally the best embedding model. It is
the best of the three tested candidates for this fixed shock-mount corpus,
qrels set, cosine-search implementation, and top-three retrieval policy.

## 7. Reproducibility evidence

| Candidate | Vector-store artifact | Retrieval result |
|---|---|---|
| BGE-M3 | `artifacts/embedding_candidates/bge_m3.json` | `evaluation/results/bge_m3_retrieval.json` |
| Qwen3 Embedding 8B | `artifacts/embedding_candidates/qwen3_embedding_8b.json` | `evaluation/results/qwen3_embedding_8b_retrieval.json` |
| Mixedbread Embed Large v1 | `artifacts/embedding_candidates/hf.co/mixedbread-ai/mxbai-embed-large-v1:F16.json` | `evaluation/results/mxbai_embed_large_v1_retrieval.json` |

The shared development qrels are retained at
`evaluation/retrieval_qrels_shock_v1.jsonl`. The index-building script records
the provider, model tag, local endpoint, query prefix, corpus topic filter, and
chunk count in each index's metadata.

## 8. System D end-to-end development pilot

After selecting BGE-M3, the complete System D path was tested with four
development-only reference questions: standards tailoring, the
stiffness/deflection trade-off, selection inputs, and a Method 514.8 scope
boundary. The fixed configuration was Qwen3.5 9B at 8K context, deterministic
tools enabled, BGE-M3 through Ollama, and the selected shock-mount index.

The first two pilot attempts exposed development issues in the evaluation
contract and RAG payload size. The evaluation-only prompt was clarified to
require literal JSON `null` and stable chunk IDs (not `.md` filenames). The
retrieval tool was also given a 1,400-character per-passage output budget. This
keeps three retrieved excerpts plus tool schemas inside the fixed 8K context;
the full source text remains stored in the index.

The final development rerun, `D_rag_dev_pilot_v3.jsonl`, produced:

| Check | Result |
|---|---:|
| Cases completed without runtime error | 4/4 |
| `lookup_knowledge` first-tool route | 4/4 |
| At least one required chunk retrieved | 4/4 |
| Parseable information-only envelope | 4/4 |
| Citation IDs matching retrieved stable IDs | 4/4 |
| End-to-end latency range | 7.9 to 26.1 s |

The physics trade-off case retrieved and cited
`shock_mount/transmitted_acceleration`, which is required, but not the second
qrels reference `shock_mount/dynamic_deflection` within its three-passage
budget. The explanation remained grounded in the retrieved travel-limit page.
This pilot therefore establishes wiring, context handling, and citation-ID
formatting; it is not a final retrieval/citation precision-recall result.

## 9. Limitations and next steps

This comparison does not yet establish final RAG effectiveness because:

- It contains only 16 in-scope and two out-of-scope development queries.
- The same corpus and qrels were used for model selection, so they cannot also
  serve as final held-out evidence.
- It measures retrieval, not whether Qwen3.5 uses retrieved passages correctly,
  cites them accurately, or remains safe on numerical questions.
- No concurrent LLM-plus-embedder peak-GPU-memory measurement has yet been
  recorded.

The next controlled steps are:

1. Define and generate the disjoint final benchmark, including shock-mount
   reference/citation cases that do not reuse these qrels questions.
2. Manually verify, hash, and freeze the final benchmark together with the
   selected model, BGE index, prompt, tools, runner, and scorer.
3. Run Systems B, C, and D three times per frozen case, then score safety,
   tool use, retrieval/citations, latency, and consistency.

Until that final freeze, source documents and the retrieval configuration may
still be improved, but every change must rebuild the BGE-M3 index and rerun this
development retrieval evaluation.
