# Conventions

## LLM tool design — the OMIT rule

Tool docstrings must say: **"OMIT this parameter unless the user explicitly specifies it."** Otherwise the LLM invents values (e.g. `dD_mm=30`, `to_s=0`).

Tool functions must clamp invented / missing values to safe defaults and inject a NOTE in the return string when they substitute. Pattern from `select_isolator` / `run_shock_analysis`:

```python
if to_ms is None or to_ms <= 0:
    notes.append("NOTE: to_ms was 0/None, substituted default 11.0 ms")
    to_ms = 11.0
to_s = to_ms / 1000.0   # engine works in SI seconds
```

The note travels back to the LLM so it can flag the substitution to the user.

**Pulse duration is model-facing as `to_ms` (milliseconds), not `to_s`.** The LLM kept truncating the decimal `0.011` to `0`; an integer-scale ms value avoids that. Convert to seconds inside the tool; `ShockEnv.to_s` stays SI.

## LLM provider quirk — NVIDIA single-tool-call

**NVIDIA Llama 3.1 70B (hosted endpoint) only supports ONE tool call per turn.** Always construct `ChatNVIDIA` with `parallel_tool_calls=False` or you'll get a 400 ("single tool-calls at once" error).

## LangChain 1.x API

LangChain 1.3.1 removed `create_tool_calling_agent`. Use:
```python
from langchain.agents import create_agent
agent = create_agent(model, tools, system_prompt=...)
result = agent.invoke({"messages": [HumanMessage(content="...")]})
```
Returned object is a `CompiledStateGraph` from LangGraph.

## SolidWorks COM

- Always `win32com.client.gencache.EnsureDispatch("SldWorks.Application")` — late binding hides methods.
- Use **direct attribute access** (`model.Extension`, `feat.Name`) rather than a `safe_call` wrapper. Wrappers silently swallow real failures and you'll spend hours debugging why a feature walk returns None.
- Document resolution order: `--file` arg > active doc > error. **No hardcoded fallback path** — that's what bit Phase 1.

## Streamlit subprocess pattern

`run_solidworks_extraction` returns a 4-tuple: `(props, stdout, stderr, returncode)`. Errors must surface as a red banner + stderr expander, **never silently swallowed**. If a click does nothing, that's the bug.

## Environment

- `.env` stores secrets and local runtime selection (`LLM_PROVIDER`, model name,
  and local base URL). Never commit it and never print API-key values.
- `NVIDIA_API_KEY` is required for NVIDIA chat and the current hosted RAG
  embedder. It is not required for tools-only local Ollama screening with RAG off.
- Do not commit `mil_std_embeddings.json` if it ever contains anything user-specific.
- **Python venv**: use the repo-relative `.\mpd\Scripts\python.exe` from the
  repository root. Do not record a laptop-specific absolute repo path.
  - Verified Python version on the current laptop: 3.10.8.
  - All project deps (langchain, streamlit, provider clients, pywin32, etc.) live here.
  - Example: `.\mpd\Scripts\python.exe setup_knowledge.py`.
  - Use `requirements-dev.txt` when running the pytest suite.
  - Do not use bare system Python for project scripts.

## Streaming

Agent exposes `stream(messages)` yielding events. UI persists events into `chat_history` so reruns show past tool calls. Don't reach for callbacks or LangChain's `AsyncIteratorCallbackHandler` — `stream_mode="updates"` on the LangGraph object is the supported path.

## Chat-history policy (LLM input vs. visible transcript)

`DomainAgent.stream()` is the single chokepoint for history. Two caps live there, and both touch ONLY the LLM input — the visible transcript + exports (`st.session_state[hist_key]`) are untouched:
- **Stateless** (`ui_guide_*`): history dropped entirely (`_is_stateless`).
- **Stateful** (shock/tiedown/mobility): keep only the last `_MAX_HISTORY_TURNS` (3) turns via `_limit_history`, so long chats don't grow the prompt and slow every turn.

## No emojis or non-ASCII symbols in source files

Unless the user explicitly asks for them.
Never use `✓ ✗ ⚠` or any Unicode symbol in `print()` statements — Windows terminals default to cp1252 which can't encode them, causing `UnicodeEncodeError` at runtime. Use plain ASCII: `[OK]` `[FAIL]` `[WARN]`.

## Anti-hallucination — defense layers (for to_ms / shock params)

0. **Interface fix (primary):** model-facing pulse duration is `to_ms` (ms, default 11.0), converted to seconds inside the tool — avoids the `0.011 -> 0` truncation entirely.
1. System prompt rule: "never zero out a parameter you didn't receive"
2. Tool docstring: OMIT unless user specifies
3. Tool-level clamp with NOTE injection

If you change a tool signature, double-check all layers are still in sync.

## Test → tool gap

If the agent fails a benchmark by inventing a parameter name, **add a new tool with the right param name** rather than telling the LLM "stop doing that." The `filter_by_deflection(max_dD_mm=...)` tool exists because of T6.3 (`dD_mm` invention).
