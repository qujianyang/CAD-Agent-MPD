# Conventions

## LLM tool design — the OMIT rule

Tool docstrings must say: **"OMIT this parameter unless the user explicitly specifies it."** Otherwise the LLM invents values (e.g. `dD_mm=30`, `to_s=0`).

Tool functions must clamp invented / missing values to safe defaults and inject a NOTE in the return string when they substitute. Pattern from `select_isolator` / `run_shock_analysis`:

```python
if to_s == 0 or to_s is None:
    to_s = DEFAULT_TO_S  # 0.011
    notes.append("NOTE: to_s was 0/None, substituted with default 0.011 s")
```

The note travels back to the LLM so it can flag the substitution to the user.

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

- `.env` only for API keys. **No hardcoded fallbacks anywhere** — they leak into git history.
- Required: `NVIDIA_API_KEY`
- Do not commit `mil_std_embeddings.json` if it ever contains anything user-specific.

## Streaming

Agent exposes `stream(messages)` yielding events. UI persists events into `chat_history` so reruns show past tool calls. Don't reach for callbacks or LangChain's `AsyncIteratorCallbackHandler` — `stream_mode="updates"` on the LangGraph object is the supported path.

## No emojis in source files

Unless the user explicitly asks for them.

## Anti-hallucination — three-layer defense (for to_s=0)

1. System prompt rule: "never zero out a parameter you didn't receive"
2. Tool docstring: OMIT unless user specifies
3. Tool-level clamp with NOTE injection

If you change a tool signature, double-check all three layers are still in sync.

## Test → tool gap

If the agent fails a benchmark by inventing a parameter name, **add a new tool with the right param name** rather than telling the LLM "stop doing that." The `filter_by_deflection(max_dD_mm=...)` tool exists because of T6.3 (`dD_mm` invention).
