# Architecture

## File map

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI. 3 tabs: Quick Selector / CAD + Shock / Agent Chat. Subprocess-launches `test_assembly.py`. |
| `agent.py` | LangChain `create_agent` + 7 tool definitions + `stream()` method for UI live tool calls. |
| `physics_engine.py` | 4-case shock analysis (Comp-Bottom, Comp-Wall, Roll-Wall, Roll-Bottom). Validated vs the Excel sheet. |
| `catalog.py` | VMC catalog (CB1400 / CB1500 / CB1800) + `select_isolator` (softest valid K). |
| `test_assembly.py` | SolidWorks COM script. Accepts `--file` arg. Extracts mass, CG (raw + base-relative), bbox, coord-sys-used. |
| `cad_compliance_checker.py` | Bridge: subprocess `test_assembly.py`, parse stdout into a dict. |
| `nvidia_embedder.py` | `JSONVectorStore` with cosine similarity + `parent_topic` filter. |
| `setup_knowledge.py` | Walks `knowledge/` folder, makes one chunk per `.md`, writes `knowledge_embeddings.json`. |
| `mil_std_rag.py` | (Older) MIL-STD-810H RAG. Still used for the larger corpus. |
| `mil_std_chunker.py`, `setup_rag.py` | MIL-STD chunking + embedding setup. |

## Knowledge structure

```
knowledge/
  shock_mount/
    formulas.md         # V, fn, GT, ΔD with units
    load_cases.md       # 4-case table + /2 rule
    selection_rules.md  # "softest valid K" rule
    catalog_overview.md # CB1400 / CB1500 / CB1800 K and dmax tables
```

Each `.md` file becomes one chunk. `parent_topic` = folder name, `child_name` = file stem, `title` = first H1.

## Agent tools (7)

| Tool | Purpose |
|---|---|
| `extract_cad_data(cad_file_path?)` | Subprocess `test_assembly.py`. Returns dict with mass / CG / bbox. |
| `select_isolator(...)` | Pick softest K passing 4 cases. **Takes 4 mass values** (comp_bottom, comp_wall, roll_wall, roll_bottom). |
| `run_shock_analysis(...)` | Full report for a chosen K — all 4 cases with GT and ΔD. |
| `find_capacity_limit(...)` | Binary search M_min / M_max where a part passes all cases. Added after T6.2 gap. |
| `filter_by_deflection(max_dD_mm, ...)` | Categorize parts: qualifying / over_clearance / fails_shock. Added after T6.3 fake-param failure. |
| `lookup_knowledge(query, parent_topic?)` | Hierarchical RAG retrieval over `knowledge/`. |
| `list_cad_files()` | List candidate CAD paths so the agent can self-discover. |

## Data flow

```
SolidWorks
  ↓ COM (pywin32, gencache.EnsureDispatch)
test_assembly.py (subprocess, --file arg)
  ↓ stdout text
cad_compliance_checker._parse_cad_output()
  ↓ dict {mass, cg_x/y/z, cg_*_base, bbox_*, coord_sys_used}
physics_engine.run_analysis()
  ↓ 4 DirectionResults
catalog.select_isolator()
  ↓ CatalogCandidate (softest valid K)
Streamlit UI tabs   OR   Agent tool result → LLM response
```

## Streaming

`agent.py` exposes `stream(messages)` yielding events of shape `{type, name, args, content, id}`.
`app.py` renders these via `st.status` + a `_render_trace` helper, and persists events into `chat_history` so reruns show past tool calls.

## Session state (Streamlit)

Key keys: `cad_props`, `raw_output`, `raw_stderr`, `extract_attempted`, `extract_returncode`, `agent`, `chat_history`.
