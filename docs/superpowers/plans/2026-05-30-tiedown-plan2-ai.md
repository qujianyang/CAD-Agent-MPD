# Tie-Down Provision Calculator — Plan 2: AI Integration (tab-routed specialist)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tie-down specialist agent on top of the validated Plan-1 engine — deterministic LangChain tools + a `knowledge/tiedown/` RAG corpus — by refactoring `agent.py` into a `build_agent(domain)` factory that keeps the existing shock-mount agent byte-for-byte unchanged.

**Architecture:** Tab-routed specialists. A `DOMAINS` registry maps each domain to `{prompt, tools}`; `build_agent(domain, api_key)` constructs a `DomainAgent` (the generalized former `ShockMountAgent`). Tie-down tools are thin, deterministic wrappers over `tiedown_engine`/`fastener_catalog`/`tiedown_import` (all numbers come from those validated modules, never the LLM). RAG reuses the existing `JSONVectorStore` with `parent_topic="tiedown"`.

**Tech Stack:** Python 3.10 venv (`mpd\Scripts\python.exe`), LangChain 1.x (`create_agent`), `langchain-nvidia-ai-endpoints` (`ChatNVIDIA`, `parallel_tool_calls=False`), existing `nvidia_embedder.JSONVectorStore`. No new dependencies.

---

## Plan series context

This is **Plan 2 of 3** (spec: `docs/superpowers/specs/2026-05-29-tiedown-replicator-design.md`, §8-9). Plan 1 (engine/catalog/sizing/validator) is committed on branch `tiedown-replicator`. Plan 3 (Streamlit tab) follows. **Continue on the `tiedown-replicator` branch.**

## Conventions (match the repo)

- Interpreter: `.\mpd\Scripts\python.exe`, run from repo root.
- ASCII only in source. Tests are standalone `test_*.py` scripts with `assert` + a `_run()` runner (catch `AssertionError` -> `[FAIL]`, other `Exception` -> `[ERROR]`).
- OMIT rule on every tool ("OMIT this parameter unless the user explicitly specifies it") + NOTE injection when a default is substituted (mirror `select_isolator`).
- Secrets via `.env` (`NVIDIA_API_KEY`); the reference workbook stays in `Downloads` (not committed).

## File structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `knowledge/tiedown/design_loads.md` | Create | RAG: the 4G/2G/1.5G basis |
| `knowledge/tiedown/force_types.md` | Create | RAG: mount-face -> tension/shear rule |
| `knowledge/tiedown/fastener_data.md` | Create | RAG: fastener capacities |
| `knowledge/tiedown/selection_rules.md` | Create | RAG: SF pass rule + sizing rule |
| `tiedown_tools.py` | Create | 3 deterministic `@tool`s + `_TIEDOWN_PROMPT` |
| `agent.py` | Modify | `DOMAINS` registry + `DomainAgent` + `build_agent`; keep `ShockMountAgent` (back-compat) |
| `test_tiedown_knowledge.py` | Create | assert the 4 tiedown chunks are discovered |
| `test_tiedown_tools.py` | Create | deterministic tool-output checks |
| `test_build_agent.py` | Create | no-regression: shock domain unchanged; tiedown wired |
| `knowledge_embeddings.json` | Regenerate | re-run `setup_knowledge.py` (NVIDIA) — manual/online step |

---

### Task 1: Knowledge docs (`knowledge/tiedown/`)

**Files:** Create the 4 `.md` files below; Test: `test_tiedown_knowledge.py`

- [ ] **Step 1: Write the failing test**

Create `test_tiedown_knowledge.py`:
```python
"""Run: .\\mpd\\Scripts\\python.exe test_tiedown_knowledge.py"""
from setup_knowledge import collect_chunks, KNOWLEDGE_DIR


def test_tiedown_topic_has_four_titled_chunks():
    chunks = collect_chunks(KNOWLEDGE_DIR)
    td = [c for c in chunks if c["parent_topic"] == "tiedown"]
    names = sorted(c["child_name"] for c in td)
    assert names == ["design_loads", "fastener_data", "force_types", "selection_rules"], names
    assert all(c["title"].strip() for c in td)   # every doc has an H1 title


def _run():
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"[FAIL] {fn.__name__}: {e}")
        except Exception as e:
            failed += 1; print(f"[ERROR] {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.\mpd\Scripts\python.exe test_tiedown_knowledge.py`
Expected: `[FAIL] ... names == [] != [...]` (no tiedown topic yet).

- [ ] **Step 3: Create the 4 markdown files**

`knowledge/tiedown/design_loads.md`:
```markdown
# Tie-Down Design Loads (Transport Inertia)

**Source of truth:** `MCDLL Tie-Down Provision_20-8-2023.xlsx` ("Matrix 2 MCD(S) Tie-down Transportation Mode").
External standard (MIL-STD-209 / Def Stan / DSTA) to be confirmed with supervisor.

Each secured item must withstand inertial loads in three axes, applied as multiples of its weight:

| Axis | Direction | Design factor | Physical cause |
|---|---|---|---|
| Longitudinal (X) | fore / aft | 4 G | braking / acceleration |
| Vertical (Z) | up / down | 2 G | road bumps |
| Lateral (Y) | side | 1.5 G | cornering |

Design force per axis: `F_axis = weight_kg * G_axis * g`, with g = 9.81 m/s^2.
Example: a 14 kg item -> longitudinal 549.36 N, vertical 274.68 N, lateral 206.01 N.
```

`knowledge/tiedown/force_types.md`:
```markdown
# Mount Face -> Tension vs Shear

The face an item is fastened to decides, per load axis, whether each fastener is
loaded in TENSION (pulled straight out) or SHEAR (sideways). Tensile capacity is
`sigma_t * area`; shear capacity is `sigma_s * area`.

| Mount face (normal) | Longitudinal (X) | Vertical (Z) | Lateral (Y) |
|---|---|---|---|
| Front / rear wall (X) | Tensile | Shear | Shear |
| Floor / ceiling / top / base (Z) | Shear | Tensile | Shear |
| Left / right side wall (Y) | Shear | Shear | Tensile |

Rule: the load axis whose direction is normal to the mounting face is the TENSILE
axis; the other two axes are SHEAR.
```

`knowledge/tiedown/fastener_data.md`:
```markdown
# Fastener Capacities

**Source:** the 'Fastener Data' sheet of the tie-down workbook.

Yield force = stress * area. Shear stress is half the tensile stress for bolts and
latches; equal to the tensile (rated) load for straps and ratchets.

Bolt property class -> tensile allowable (MPa): 4.6=240, 4.8=340, 5.8=420, 8.8=640,
9.8=720, 10.9=940, 12.9=1100, A2-70=450. Shear allowable = half of these.

Bolt minor-diameter area (mm^2): M6=17.894, M8=32.841, M10=52.292, M12=76.247,
1/4-20=21.712 (table also covers M1.6 .. M36).

Straps / latches (area = 1, value is a rated load in N, shear = tensile):
Camlock 1"=2500, Camlock 1.5"=18000, Ratchet 1"=5000, Ratchet 1.5"=30000,
Strap (Net)=3500, D-Ring=8896. Spring Latch: area 113.097, sigma_t 165, sigma_s 82.5.
Locking Pin: area 28.274, sigma_t 250, sigma_s 125.
```

`knowledge/tiedown/selection_rules.md`:
```markdown
# Tie-Down Selection and Pass Rules

Per fastener, per axis: `SF = yield_force(force_type) / (design_force_axis / qty)`,
where the force type (tension or shear) comes from the mount face.

An item PASSES when its minimum SF across the three axes is >= the target
(default 1.0 = no yield at the ultimate transport load).

Active sizing ("smallest valid fastener"): for a target SF, the minimum quantity is
`ceil( max over axes of [ target_SF * design_axis / yield_force(force_type) ] )`.
Among options meeting the target, prefer the fewest fasteners, then the smallest real
bolt (straps carry a sentinel area = 1 and must not count as the "smallest").

The reference workbook is conservative: many items are bolted far above SF = 1
(e.g. the 1269 kg generator uses 10 x M12 giving SF 4.9, where 3 x M10 already
meets SF 1.0).
```

- [ ] **Step 4: Run to verify it passes**

Run: `.\mpd\Scripts\python.exe test_tiedown_knowledge.py`
Expected: `1/1 passed`.

- [ ] **Step 5: Commit**
```bash
git add knowledge/tiedown/ test_tiedown_knowledge.py
git commit -m "feat(tiedown): knowledge/tiedown RAG docs (design loads, force types, fasteners, rules)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Tie-down tools + prompt (`tiedown_tools.py`)

**Files:** Create `tiedown_tools.py`; Test: `test_tiedown_tools.py`

- [ ] **Step 1: Write the failing test**

Create `test_tiedown_tools.py`:
```python
"""Run: .\\mpd\\Scripts\\python.exe test_tiedown_tools.py  (deterministic; reads the workbook)"""
from tiedown_tools import run_tiedown_check, recommend_fasteners, flag_critical_items


def test_run_tiedown_check_generator():
    out = run_tiedown_check.invoke({
        "weight_kg": 1269.0, "mount_face": "floor",
        "fastener": "8.8", "fastener_size": "M12", "qty": 10,
    })
    assert "4.9" in out                 # long-axis SF ~4.9
    assert "Tensile" in out and "Shear" in out
    assert "PASS" in out


def test_run_tiedown_check_bad_face():
    out = run_tiedown_check.invoke({
        "weight_kg": 10.0, "mount_face": "nonsense",
        "fastener": "8.8", "fastener_size": "M6", "qty": 4,
    })
    assert out.startswith("ERROR")


def test_recommend_fasteners_prefers_bolt():
    out = recommend_fasteners.invoke({
        "weight_kg": 1269.0, "mount_face": "floor", "target_SF": 1.0,
    })
    assert "M10" in out                 # smallest valid bolt at SF 1.0
    assert "RECOMMENDED" in out


def test_flag_critical_items_lists_water_cans():
    out = flag_critical_items.invoke({"target_SF": 2.0})
    assert "Water Jerry Cans" in out    # min SF 1.06 < 2.0


def _run():
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"[FAIL] {fn.__name__}: {e}")
        except Exception as e:
            failed += 1; print(f"[ERROR] {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.\mpd\Scripts\python.exe test_tiedown_tools.py`
Expected: `ModuleNotFoundError: No module named 'tiedown_tools'`.

- [ ] **Step 3: Write the implementation**

Create `tiedown_tools.py`:
```python
"""
Tie-down agent tools (deterministic) + the tie-down specialist system prompt.
These wrap the validated tiedown_engine / fastener_catalog / tiedown_import modules;
every number comes from those modules, never from the LLM.
"""
from langchain_core.tools import tool

from tiedown_engine import MountFace, Item, analyze_item, run_tiedown_analysis, format_item_detail
from fastener_catalog import make_fastener, size_fasteners as _size_fasteners
from tiedown_import import import_workbook, WB_DEFAULT

_FACE_ALIASES = {
    "wall_x": MountFace.WALL_X, "x": MountFace.WALL_X, "front": MountFace.WALL_X,
    "front wall": MountFace.WALL_X, "rear": MountFace.WALL_X, "rear wall": MountFace.WALL_X,
    "floor_z": MountFace.FLOOR_Z, "z": MountFace.FLOOR_Z, "floor": MountFace.FLOOR_Z,
    "ceiling": MountFace.FLOOR_Z, "top": MountFace.FLOOR_Z, "base": MountFace.FLOOR_Z,
    "wall_y": MountFace.WALL_Y, "y": MountFace.WALL_Y, "side": MountFace.WALL_Y,
    "side wall": MountFace.WALL_Y, "left": MountFace.WALL_Y, "right": MountFace.WALL_Y,
}


def _parse_face(s: str):
    return _FACE_ALIASES.get((s or "").strip().lower())


_FACE_HELP = ("mount_face must be one of: front/rear wall (WALL_X), "
              "floor/ceiling/top/base (FLOOR_Z), or left/right side wall (WALL_Y).")


@tool
def run_tiedown_check(weight_kg: float, mount_face: str, fastener: str,
                      qty: int, fastener_size: str = "", target_SF: float = 1.0) -> str:
    """
    Check whether a secured item's fasteners survive the transport design loads
    (4G longitudinal, 2G vertical, 1.5G lateral). Returns per-axis safety factors
    (tension vs shear set by the mount face) and a PASS/FAIL verdict.

    OMIT target_SF unless the user gives a required margin (default 1.0 = no yield).

    Args:
        weight_kg     : REQUIRED. Item weight in kg.
        mount_face    : REQUIRED. front/rear wall, floor/ceiling/top/base, or side wall.
        fastener      : REQUIRED. Bolt class ("8.8") OR a strap/latch name
                        ('Camlock Strap (1")', 'Spring Latch', 'Ratchet (1")').
        qty           : REQUIRED. Number of fasteners installed.
        fastener_size : Bolt size ("M6".."M12", "1/4-20"). Required for bolts; leave empty for straps.
        target_SF     : Pass threshold. Default 1.0. OMIT unless the user specifies.
    """
    notes = []
    face = _parse_face(mount_face)
    if face is None:
        return f"ERROR: unknown mount_face {mount_face!r}. {_FACE_HELP}"
    if weight_kg <= 0:
        return "ERROR: weight_kg must be positive."
    if qty <= 0:
        return "ERROR: qty must be a positive integer."
    if target_SF is None or target_SF <= 0:
        notes.append(f"NOTE: target_SF was {target_SF!r} (invalid); substituted default 1.0")
        target_SF = 1.0
    try:
        spec = make_fastener(fastener, fastener_size or None)
    except KeyError as e:
        return (f"ERROR: unknown fastener {e}. Bolts need a class (e.g. 8.8) + size "
                f"(e.g. M6); straps/latches use their name e.g. 'Camlock Strap (1\")'.")
    res = analyze_item(Item(spec.name, weight_kg, face, spec, int(qty)))
    verdict = "PASS" if res.min_SF >= target_SF else "FAIL"
    head = ("\n".join(notes) + "\n") if notes else ""
    return head + format_item_detail(res) + f"\n  target SF = {target_SF}  ->  {verdict}"


@tool
def recommend_fasteners(weight_kg: float, mount_face: str, target_SF: float = 1.0) -> str:
    """
    Recommend the smallest fastener + quantity that achieves the target safety factor
    for a secured item (the tie-down analog of choosing the softest valid isolator).
    Returns the best option plus alternatives.

    OMIT target_SF unless the user gives a required margin (default 1.0).

    Args:
        weight_kg  : REQUIRED. Item weight in kg.
        mount_face : REQUIRED. front/rear wall, floor/ceiling/top/base, or side wall.
        target_SF  : Required safety factor. Default 1.0. OMIT unless the user specifies.
    """
    notes = []
    face = _parse_face(mount_face)
    if face is None:
        return f"ERROR: unknown mount_face {mount_face!r}. {_FACE_HELP}"
    if weight_kg <= 0:
        return "ERROR: weight_kg must be positive."
    if target_SF is None or target_SF <= 0:
        notes.append(f"NOTE: target_SF was {target_SF!r} (invalid); substituted default 1.0")
        target_SF = 1.0
    opts = _size_fasteners(weight_kg, face, target_SF=target_SF)
    best = opts[0]
    lines = notes + [
        f"=== FASTENER SIZING (weight {weight_kg} kg, {face.value}, target SF {target_SF}) ===",
        f"RECOMMENDED: {best.fastener.name} x{best.qty}  (achieved min SF {best.min_SF:.2f})",
        "Alternatives (fewest fasteners first):",
    ]
    for o in opts[1:5]:
        lines.append(f"  {o.fastener.name:<22} x{o.qty:<3} min SF {o.min_SF:.2f}")
    return "\n".join(lines)


@tool
def flag_critical_items(target_SF: float = 2.0, workbook_path: str = "") -> str:
    """
    Import the tie-down provision workbook and list the items whose minimum safety
    factor falls below a target margin (the marginal / at-risk items).

    OMIT both parameters to use the defaults (target_SF=2.0, the configured workbook).

    Args:
        target_SF     : Margin to flag against. Default 2.0. OMIT unless the user specifies.
        workbook_path : Path to a tie-down .xlsx. OMIT to use the configured default.
    """
    notes = []
    if target_SF is None or target_SF <= 0:
        notes.append(f"NOTE: target_SF was {target_SF!r} (invalid); substituted default 2.0")
        target_SF = 2.0
    path = workbook_path or WB_DEFAULT
    try:
        items = import_workbook(path)
    except Exception as e:
        return f"ERROR: could not read workbook at {path}: {e}"
    report = run_tiedown_analysis(items, target_SF=target_SF)
    crit = sorted(report.critical_items(), key=lambda r: r.min_SF)
    lines = notes + [
        f"=== CRITICAL ITEMS (min SF < {target_SF}) ===",
        f"Workbook: {path}",
        f"{len(crit)} of {len(items)} items below target:",
    ]
    for r in crit:
        lines.append(f"  {r.item.name[:40]:<40} min SF {r.min_SF:>7.3f} ({r.limiting_axis.axis})")
    if not crit:
        lines.append("  (none -- all items meet the target)")
    return "\n".join(lines)


_TIEDOWN_PROMPT = """\
You are a mechanical engineering assistant specializing in TIE-DOWN / cargo securing
for transported military shelter equipment.

Act as an engineering judge: interpret the safety factors the tools compute, cite the
rule you applied, and flag marginal items. NEVER invent safety-factor or force numbers
-- always call a tool to compute them.

Design loads (multiples of item weight): 4G longitudinal, 2G vertical, 1.5G lateral
(g=9.81). Per fastener, per axis: SF = yield_force(type) / (design force / qty). The
mount face decides tension vs shear. An item passes when its minimum SF across the
three axes is >= the target (default 1.0).

CRITICAL parameter rule for ALL tools:
- Only pass values the user explicitly mentions. OMIT every other parameter so the
  project default applies. Never pass 0 for target_SF.

Tool guide:
- run_tiedown_check  : verify a specific item + fastener + quantity.
- recommend_fasteners: size the smallest fastener + quantity for a target SF.
- flag_critical_items: list items below a margin (default SF 2.0) from the workbook.
- lookup_knowledge   : ALWAYS pass parent_topic="tiedown". Use it to cite the design
  loads, the mount-face tension/shear rule, fastener capacities, or the selection rule.

When you give a recommendation or verdict, cite one sentence from lookup_knowledge
tagged [source: <file>.md]. If the knowledge base is not built, say so and continue.
"""
```

- [ ] **Step 4: Run to verify it passes**

Run: `.\mpd\Scripts\python.exe test_tiedown_tools.py`
Expected: `4/4 passed`.

- [ ] **Step 5: Commit**
```bash
git add tiedown_tools.py test_tiedown_tools.py
git commit -m "feat(tiedown): deterministic agent tools + specialist prompt" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `build_agent` factory in `agent.py` (no-regression refactor)

**Files:** Modify `agent.py`; Test: `test_build_agent.py`

- [ ] **Step 1: Write the failing test**

Create `test_build_agent.py`:
```python
"""Run: .\\mpd\\Scripts\\python.exe test_build_agent.py  (offline; inspects the registry only)"""
SHOCK_7 = sorted([
    "extract_cad_data", "select_isolator", "run_shock_analysis",
    "find_capacity_limit", "filter_by_deflection", "lookup_knowledge", "list_cad_files",
])


def test_shock_domain_unchanged():
    from agent import DOMAINS, _SYSTEM_PROMPT
    shock = DOMAINS["shock_mount"]
    assert sorted(t.name for t in shock["tools"]) == SHOCK_7
    assert shock["prompt"] is _SYSTEM_PROMPT      # exact same prompt object


def test_tiedown_domain_wired():
    from agent import DOMAINS
    names = sorted(t.name for t in DOMAINS["tiedown"]["tools"])
    assert "run_tiedown_check" in names
    assert "recommend_fasteners" in names
    assert "flag_critical_items" in names
    assert "lookup_knowledge" in names            # shared, scoped via prompt


def test_build_agent_unknown_domain():
    from agent import build_agent
    try:
        build_agent("nope", api_key="x")
        assert False, "expected KeyError"
    except KeyError:
        pass


def _run():
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"[FAIL] {fn.__name__}: {e}")
        except Exception as e:
            failed += 1; print(f"[ERROR] {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.\mpd\Scripts\python.exe test_build_agent.py`
Expected: `[FAIL]/[ERROR] ... cannot import name 'DOMAINS' from 'agent'`.

- [ ] **Step 3: Modify `agent.py`**

**3a.** Add this import after the existing `from cad_compliance_checker import ...` line (top of file):
```python
from tiedown_tools import (
    run_tiedown_check, recommend_fasteners, flag_critical_items, _TIEDOWN_PROMPT,
)
```

**3b.** Replace the entire `class ShockMountAgent:` block (from `class ShockMountAgent:` down to the end of its `stream(...)` method, i.e. everything between the `# Agent` section and the `# CLI entry point` section) with the following. The `invoke`/`stream` bodies are copied verbatim from the original `ShockMountAgent` — only the class is generalized:
```python
# ---------------------------------------------------------------------------
# Domain registry + agent factory (tab-routed specialists)
# ---------------------------------------------------------------------------

_SHOCK_TOOLS = [
    extract_cad_data,
    select_isolator,
    run_shock_analysis,
    find_capacity_limit,
    filter_by_deflection,
    lookup_knowledge,
    list_cad_files,
]

_TIEDOWN_TOOLS = [
    run_tiedown_check,
    recommend_fasteners,
    flag_critical_items,
    lookup_knowledge,           # shared retriever; tiedown prompt scopes it to parent_topic="tiedown"
]

DOMAINS = {
    "shock_mount": {"prompt": _SYSTEM_PROMPT,  "tools": _SHOCK_TOOLS},
    "tiedown":     {"prompt": _TIEDOWN_PROMPT, "tools": _TIEDOWN_TOOLS},
}


class DomainAgent:
    """LangChain tool-calling agent for one engineering domain (focused prompt + tools)."""

    def __init__(self, api_key: str, system_prompt: str, tools: list):
        global _api_key
        _api_key = api_key
        self.system_prompt = system_prompt
        self.tools = tools

        llm = ChatNVIDIA(
            model="meta/llama-3.1-70b-instruct",
            api_key=api_key,
            temperature=0.1,
            max_tokens=2048,
            # NVIDIA's hosted Llama 3.1 70B only allows ONE tool call per turn.
            parallel_tool_calls=False,
        )
        self._agent = create_agent(llm, tools, system_prompt=system_prompt)

    def invoke(self, question: str, chat_history: list | None = None) -> str:
        messages = list(chat_history) if chat_history else []
        messages.append(("human", question))
        result = self._agent.invoke({"messages": messages})
        last = result["messages"][-1]
        return last.content if hasattr(last, "content") else str(last)

    def stream(self, question: str, chat_history: list | None = None):
        """
        Stream structured events as the agent works (for Streamlit st.status).
        Yields dicts: reasoning | tool_call | tool_result | final.
        """
        messages = list(chat_history) if chat_history else []
        messages.append(("human", question))

        seen_tool_call_ids: set[str] = set()
        last_ai_content: str = ""

        for update in self._agent.stream({"messages": messages}, stream_mode="updates"):
            for _node, node_state in update.items():
                new_messages = node_state.get("messages", []) if isinstance(node_state, dict) else []
                for msg in new_messages:
                    tool_call_id = getattr(msg, "tool_call_id", None)
                    if tool_call_id is not None:
                        yield {
                            "type": "tool_result",
                            "name": getattr(msg, "name", "?"),
                            "content": str(getattr(msg, "content", "")),
                            "id": tool_call_id,
                        }
                        continue

                    tool_calls = getattr(msg, "tool_calls", None) or []
                    content = getattr(msg, "content", "") or ""

                    if tool_calls:
                        if content.strip():
                            yield {"type": "reasoning", "content": content}
                        for tc in tool_calls:
                            tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
                            if tc_id in seen_tool_call_ids:
                                continue
                            seen_tool_call_ids.add(tc_id)
                            yield {
                                "type": "tool_call",
                                "name": tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?"),
                                "args": tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {}),
                                "id": tc_id,
                            }
                    elif content.strip():
                        last_ai_content = content

        if last_ai_content:
            yield {"type": "final", "content": last_ai_content}


def build_agent(domain: str, api_key: str) -> DomainAgent:
    """Construct the specialist agent for a domain ('shock_mount' or 'tiedown')."""
    if domain not in DOMAINS:
        raise KeyError(f"Unknown domain {domain!r}. Available: {list(DOMAINS)}")
    cfg = DOMAINS[domain]
    return DomainAgent(api_key, cfg["prompt"], cfg["tools"])


class ShockMountAgent(DomainAgent):
    """Back-compat: the original shock-mount agent is now a 'shock_mount' DomainAgent."""
    _TOOLS = _SHOCK_TOOLS

    def __init__(self, api_key: str):
        cfg = DOMAINS["shock_mount"]
        super().__init__(api_key, cfg["prompt"], cfg["tools"])
```

- [ ] **Step 4: Run to verify it passes**

Run: `.\mpd\Scripts\python.exe test_build_agent.py`
Expected: `3/3 passed`.

- [ ] **Step 5: Commit**
```bash
git add agent.py test_build_agent.py
git commit -m "refactor(agent): build_agent(domain) factory + tiedown specialist; shock agent unchanged" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: CLI domain switch (manual smoke entry point)

**Files:** Modify `agent.py` (the `if __name__ == "__main__":` block)

- [ ] **Step 1: Replace the `__main__` block** with this (adds an optional domain argument; `ShockMountAgent` still works for any other caller):
```python
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: Set NVIDIA_API_KEY in your .env file or environment.")

    domain = sys.argv[1] if len(sys.argv) > 1 else "shock_mount"
    if domain not in DOMAINS:
        raise SystemExit(f"Unknown domain {domain!r}. Available: {list(DOMAINS)}")

    agent = build_agent(domain, api_key)
    print(f"{domain} agent ready. Type 'quit' to exit.\n")
    history: list = []

    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() in ("quit", "exit", "q"):
            break
        response = agent.invoke(q, chat_history=history if history else None)
        print(f"\nAgent: {response}\n")
        history.append(("human", q))
        history.append(("ai", response))
        if len(history) > 6:
            history = history[-6:]
```

- [ ] **Step 2: Verify the module still imports cleanly (offline)**

Run: `.\mpd\Scripts\python.exe -c "import agent; print(sorted(agent.DOMAINS))"`
Expected: `['shock_mount', 'tiedown']`

- [ ] **Step 3: Commit**
```bash
git add agent.py
git commit -m "feat(agent): CLI domain switch (python agent.py tiedown)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Embed the knowledge base + manual verification (online; needs NVIDIA_API_KEY)

**Files:** Regenerate `knowledge_embeddings.json`

- [ ] **Step 1: Re-embed all knowledge (shock_mount + tiedown) with the NVIDIA model**

The agent embeds queries with the NVIDIA model, so the store must be built with the same model (not `--local`).
Run: `.\mpd\Scripts\python.exe setup_knowledge.py`
Expected: output lists `tiedown/ -> design_loads, fastener_data, force_types, selection_rules` and `DONE. 8 chunks across 2 parent topics.`

- [ ] **Step 2: Manual RAG check (tiedown retrieval)**

Run:
```bash
.\mpd\Scripts\python.exe -c "from agent import lookup_knowledge; print(lookup_knowledge.invoke({'query':'mount face tension or shear','parent_topic':'tiedown'}))"
```
Expected: a hit from `tiedown/force_types` (the mount-face table). Confirms the new corpus is retrievable.

- [ ] **Step 3: Manual no-regression smoke (shock agent still answers)**

Run `.\mpd\Scripts\python.exe agent.py` and ask: `select an isolator for an 850 kg rack`.
Expected: it recommends a CB-series part with the 4 load cases and a [source: ...] citation (unchanged behavior).
Then run `.\mpd\Scripts\python.exe agent.py tiedown` and ask: `how many M12 bolts to floor-mount a 1269 kg generator at SF 2`.
Expected: it calls recommend_fasteners and answers with a bolt + quantity and a [source: selection_rules.md] citation.

- [ ] **Step 4: Commit the regenerated store (only if not git-ignored and not sensitive)**

Check first: `git check-ignore knowledge_embeddings.json` (if it prints the path, it is ignored — skip the commit).
If not ignored:
```bash
git add knowledge_embeddings.json
git commit -m "chore(tiedown): re-embed knowledge base with tiedown topic (8 chunks)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (vs §8-9 of the design spec):**
- §8 `build_agent(domain)` factory + `DOMAINS` registry -> Task 3. [covered]
- §8 shock agent reproduced verbatim (same 7 tools + prompt) -> Task 3 `test_shock_domain_unchanged`. [covered]
- §8 tie-down specialist ~5 focused tools -> Tasks 2-3 (`run_tiedown_check`, `recommend_fasteners`, `flag_critical_items`, shared `lookup_knowledge`). [covered]
- §8 1-tool-per-turn preserved -> `parallel_tool_calls=False` kept in `DomainAgent`. [covered]
- §9 `knowledge/tiedown/` 4 docs + embed -> Tasks 1, 5. [covered]
- §8 OMIT rule + NOTE injection on tools -> Task 2 (each tool clamps target_SF with a NOTE). [covered]
- Spec §8 "no-regression gate" originally said re-run Tier 1-6; **no such benchmark file exists in the repo**, so the gate is implemented as the deterministic registry test (Task 3) + a manual CLI smoke (Task 5 Step 3). [covered, adapted — noted]

**2. Placeholder scan:** No TBD/TODO; every code step has complete code; every run step has an exact command + expected output. The two LLM-behavior steps (Task 5 Steps 2-3) are explicitly manual/online because they need `NVIDIA_API_KEY` and are non-deterministic. [clean]

**3. Type consistency:** `build_agent(domain, api_key)`, `DomainAgent(api_key, system_prompt, tools)`, `DOMAINS[d]["prompt"|"tools"]`, tool names `run_tiedown_check` / `recommend_fasteners` / `flag_critical_items`, `_TIEDOWN_PROMPT`, `make_fastener(class_or_name, size)`, `size_fasteners(weight_kg, mount_face, target_SF=...)`, `import_workbook`, `run_tiedown_analysis(..., target_SF=...)`, `ItemResult.min_SF`/`.limiting_axis`/`.critical_items` — all match Plan 1's definitions and are used consistently across Tasks 1-5. The tie-down tool is named `recommend_fasteners` (not `size_fasteners`) to avoid colliding with the catalog function it wraps. [consistent]

**Out of scope (Plan 3):** the Streamlit "Tie-Down" tab, per-domain `chat_history` in session state, and UI wiring of `build_agent("tiedown")`.
