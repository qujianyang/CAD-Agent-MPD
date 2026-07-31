# Project Overview

## One-line description
A Streamlit web app that pulls live mass / CG / bbox from a SolidWorks assembly, runs validated shock-isolation physics on it, and lets the user chat with an LLM agent that has tool access to all of it plus a hierarchical RAG over engineering references.

## The two real pillars

1. **Physics** — Reproduces a hand-validated Excel sheet (4 load cases, transmissibility + deflection per case) to 4 decimal places. Picks the softest valid spring K from a real VMC catalog.
2. **AI / RAG** — LangChain 1.x agent (LangGraph CompiledStateGraph) with 7 deterministic Python tools, hierarchical RAG with `parent_topic` / `child_name` metadata, anti-hallucination safety nets.

## The thin pillar (be honest about this)

**CAD (SolidWorks COM)** — Only extracts mass, CG (X/Y/Z), and bounding box. Not parametric optimization, not feature manipulation. SolidWorks Education Edition blocks most useful APIs (see gotchas).

This is why the FYP framing leans on the physics + AI/RAG sides for methodology, literature review, validation, and benchmarks.

## Tech stack

- Python 3.10.8, Streamlit 1.57.0
- LangChain 1.3.1 + langchain-nvidia-ai-endpoints 1.3.0 (uses `create_agent`, not the removed `create_tool_calling_agent`)
- NVIDIA Llama 3.1 70B (hosted endpoint, `parallel_tool_calls=False` required)
- pywin32 311 for SolidWorks COM
- sentence-transformers 5.5.0, NVIDIA NV-Embed-QA (via hosted endpoint)
- No FAISS / Chroma — `JSONVectorStore` with direct cosine similarity in `nvidia_embedder.py`

## Target user / origin

Mech eng FYP student at ST Engineering. The boss originally asked for a **"Combined CG Calculator"** (Phase 1, still skipped). The project pivoted toward a fuller agentic shock-isolator selection system after Phase 1 turned out to be too narrow to justify the work.
