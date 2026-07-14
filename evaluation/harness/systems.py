"""Model and agent configurations used by the evaluation harness."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import os
from typing import Iterator


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
SELECTED_LOCAL_MODEL = "cad-eval-qwen35-9b:8k"
SELECTED_LOCAL_BASE_MODEL = "qwen3.5:9b"
SELECTED_EMBEDDING_PROVIDER = "ollama"
SELECTED_EMBEDDING_MODEL = "bge-m3"
SELECTED_EMBEDDING_BASE_URL = "http://127.0.0.1:11434"
SELECTED_KNOWLEDGE_STORE_PATH = "artifacts/embedding_candidates/bge_m3.json"
SELECTED_KNOWLEDGE_MAX_CHARS_PER_HIT = 1400


@dataclass(frozen=True)
class SystemConfig:
    """One controlled model/backend configuration.

    Candidate comparison keeps ``tools=True`` and ``rag=False``. The B/C/D
    configs use the selected model and vary only tools and RAG.
    """

    id: str
    provider: str
    model: str
    base_model: str | None = None
    base_url: str | None = None
    tools: bool = True
    rag: bool = False
    context_length: int = 8192
    temperature: float = 0.0
    max_tokens: int = 2048
    seed: int = 42
    reasoning_effort: str = "none"
    top_p: float = 0.95
    presence_penalty: float = 0.0
    embedding_provider: str = SELECTED_EMBEDDING_PROVIDER
    embedding_model: str = SELECTED_EMBEDDING_MODEL
    embedding_base_url: str = SELECTED_EMBEDDING_BASE_URL
    knowledge_store_path: str = SELECTED_KNOWLEDGE_STORE_PATH
    knowledge_max_chars_per_hit: int = SELECTED_KNOWLEDGE_MAX_CHARS_PER_HIT

    def public_record(self) -> dict:
        """Return serializable, non-secret metadata for each raw run."""
        return asdict(self)


SYSTEMS: dict[str, SystemConfig] = {
    "B": SystemConfig(
        id="B",
        provider="ollama",
        model=SELECTED_LOCAL_MODEL,
        base_model=SELECTED_LOCAL_BASE_MODEL,
        base_url=DEFAULT_OLLAMA_BASE_URL,
        tools=False,
        rag=False,
    ),
    "C": SystemConfig(
        id="C",
        provider="ollama",
        model=SELECTED_LOCAL_MODEL,
        base_model=SELECTED_LOCAL_BASE_MODEL,
        base_url=DEFAULT_OLLAMA_BASE_URL,
        tools=True,
        rag=False,
    ),
    "D": SystemConfig(
        id="D",
        provider="ollama",
        model=SELECTED_LOCAL_MODEL,
        base_model=SELECTED_LOCAL_BASE_MODEL,
        base_url=DEFAULT_OLLAMA_BASE_URL,
        tools=True,
        rag=True,
    ),
    "qwen3_14b": SystemConfig(
        id="qwen3_14b",
        provider="ollama",
        model="cad-eval-qwen3-14b:8k",
        base_model="qwen3:14b",
        base_url=DEFAULT_OLLAMA_BASE_URL,
    ),
    "qwen35_9b": SystemConfig(
        id="qwen35_9b",
        provider="ollama",
        model="cad-eval-qwen35-9b:8k",
        base_model="qwen3.5:9b",
        base_url=DEFAULT_OLLAMA_BASE_URL,
    ),
    "gemma4_12b": SystemConfig(
        id="gemma4_12b",
        provider="ollama",
        model="cad-eval-gemma4-12b:8k",
        base_model="gemma4:12b",
        base_url=DEFAULT_OLLAMA_BASE_URL,
    ),
}


def get_system(system_id: str) -> SystemConfig:
    try:
        return SYSTEMS[system_id]
    except KeyError as exc:
        available = ", ".join(sorted(SYSTEMS))
        raise KeyError(f"Unknown system {system_id!r}. Available: {available}") from exc


def _environment_updates(config: SystemConfig) -> dict[str, str]:
    updates = {
        "LLM_PROVIDER": config.provider,
        "LLM_TEMPERATURE": str(config.temperature),
        "LLM_MAX_TOKENS": str(config.max_tokens),
        "LLM_SEED": str(config.seed),
        "LLM_REASONING_EFFORT": config.reasoning_effort,
        "LLM_TOP_P": str(config.top_p),
        "LLM_PRESENCE_PENALTY": str(config.presence_penalty),
        "EMBEDDING_PROVIDER": config.embedding_provider,
        "OLLAMA_EMBEDDING_MODEL": config.embedding_model,
        "OLLAMA_EMBEDDING_BASE_URL": config.embedding_base_url,
        "KNOWLEDGE_STORE_PATH": config.knowledge_store_path,
        "KNOWLEDGE_MAX_CHARS_PER_HIT": str(config.knowledge_max_chars_per_hit),
    }
    if config.provider == "ollama":
        updates["OLLAMA_MODEL"] = config.model
        updates["OLLAMA_BASE_URL"] = config.base_url or DEFAULT_OLLAMA_BASE_URL
    elif config.provider == "nvidia":
        updates["NVIDIA_MODEL"] = config.model
    elif config.provider == "openai":
        updates["OPENAI_MODEL"] = config.model
        if config.base_url:
            updates["OPENAI_BASE_URL"] = config.base_url
    return updates


@contextmanager
def activated_system(config: SystemConfig) -> Iterator[None]:
    """Apply one system to process environment and restore it afterwards."""
    updates = _environment_updates(config)
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _tool_name(tool: object) -> str:
    return str(getattr(tool, "name", getattr(tool, "__name__", "")))


_NO_TOOLS_SUFFIX = """

EVALUATION CONFIGURATION: No external tools are available in this system.
Do not claim that a tool or database was consulted. Use only the inputs in the
question, ask for missing required inputs, and follow the required final-answer
contract. This tool-free configuration is an experimental baseline, not the
deployed engineering system.
"""


_NO_RAG_SUFFIX = """

EVALUATION CONFIGURATION: RAG is disabled and lookup_knowledge is not available.
Do not request that tool, claim that documents were retrieved, or invent
citations. For a reference-only question, answer from the model context and
state that no external reference was retrieved. Numerical engineering claims
must still use the available deterministic tools.
"""


_VERDICT_ENVELOPE_SUFFIX = """

EVALUATION OUTPUT CONTRACT: At the end of every answer, include exactly one
fenced JSON object with this structure:
{
  "verdict": null,
  "governing_check": "string or null",
  "key_numbers": {},
  "units": {},
  "missing_inputs": [],
  "citations": []
}
Use ASK only when required input is missing or contradictory. Use the literal
JSON value null (without quotation marks) for a catalogue lookup or reference
question that has no engineering safety decision. Never write "null" as a
string. Citation values must be the exact chunk IDs printed in the
lookup_knowledge result headers, for example "shock_mount/selection_workflow".
Do not use source filenames such as "shock_mount/selection_workflow.md".
Do not place any additional JSON object elsewhere in the answer. The prose
answer may appear before this final envelope.

For every information-only question, end with this exact shape after a concise
answer (replace the citation IDs with the retrieved IDs that support the answer):
```json
{
  "verdict": null,
  "governing_check": null,
  "key_numbers": {},
  "units": {},
  "missing_inputs": [],
  "citations": ["shock_mount/example_chunk"]
}
```

For a missing-input response, asking the user a question is not sufficient:
you MUST still append the final JSON envelope. For example, if mass is missing,
end with exactly this shape (with the appropriate missing field names):
```json
{
  "verdict": "ASK",
  "governing_check": "Cannot make an engineering selection until the required input is supplied.",
  "key_numbers": {},
  "units": {},
  "missing_inputs": ["mass_kg"],
  "citations": []
}
```
"""


def build_evaluation_agent(config: SystemConfig, domain: str):
    """Build the existing domain agent with only the configured component change."""
    import agent as agent_module

    if domain not in agent_module.DOMAINS:
        available = ", ".join(sorted(agent_module.DOMAINS))
        raise KeyError(f"Unknown domain {domain!r}. Available: {available}")

    domain_config = agent_module.DOMAINS[domain]
    prompt = domain_config["prompt"]
    tools = list(domain_config["tools"])
    effective_domain = domain

    if not config.rag:
        tools = [tool for tool in tools if _tool_name(tool) != "lookup_knowledge"]
        prompt = f"{prompt.rstrip()}\n{_NO_RAG_SUFFIX}"

    if not config.tools:
        tools = []
        prompt = f"{prompt.rstrip()}\n{_NO_TOOLS_SUFFIX}"
        # The production shock guard requires a tool for technical claims. It is
        # intentionally bypassed only for the explicitly tool-free B baseline.
        effective_domain = f"evaluation_no_tools_{domain}"

    prompt = f"{prompt.rstrip()}\n{_VERDICT_ENVELOPE_SUFFIX}"

    api_key = ""
    if config.provider == "nvidia":
        api_key = os.environ.get("NVIDIA_API_KEY", "")
    elif config.provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
    elif config.provider == "ollama":
        api_key = os.environ.get("OLLAMA_API_KEY", "ollama")

    return agent_module.DomainAgent(
        api_key=api_key,
        system_prompt=prompt,
        tools=tools,
        domain=effective_domain,
    )
