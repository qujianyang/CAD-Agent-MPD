# Tie-Down Provision Calculator — Plan 1: Validated Engine + Catalog + Sizing

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-Python tie-down engine + fastener catalog + active fastener-sizing that reproduces `MCDLL Tie-Down Provision_20-8-2023.xlsx` per-item safety factors to machine precision (proven: 177/177, max diff 9e-13).

**Architecture:** Mirrors the shock-mount tool (`physics_engine.py` + `catalog.py`): immutable-ish dataclasses, a `run_*` public API, `format_report()` for CLI/LLM output, `__main__` smoke tests, and a standalone Excel-validation script. No AI and no UI in this plan — those are Plans 2 and 3.

**Tech Stack:** Python 3.11 (project venv `mpd\Scripts\python.exe`), pandas (already installed) for the Excel importer/validator. No new dependencies. No pytest — tests are standalone `test_*.py` scripts with `assert` + a `__main__` runner, matching the repo's `test_part.py` / `test_assembly.py` style.

---

## Plan series context

This is **Plan 1 of 3** for the tie-down domain (spec: `docs/superpowers/specs/2026-05-29-tiedown-replicator-design.md`):
- **Plan 1 (this):** Engine + catalog + sizing + Excel validation. Produces a working, CLI-testable, validated calculator.
- **Plan 2 (later):** AI integration — refactor `agent.py` to a `build_agent(domain)` factory, add tie-down tools, add `knowledge/tiedown/` RAG docs. Depends on Plan 1's public API.
- **Plan 3 (later):** Streamlit "Tie-Down" tab (structured input + import + results + domain chat). Depends on Plans 1-2.

## Conventions (match the repo — do not deviate)

- **Interpreter:** always `.\mpd\Scripts\python.exe` (system Python lacks the deps). Run from the repo root.
- **ASCII only in source.** No non-ASCII symbols in any `.py` (Windows cp1252 `print` crashes). Use `[OK]`/`[FAIL]`/`[WARN]`, `sigma`, `->`.
- **No hardcoded secrets / paths that leak.** The reference workbook stays in `Downloads` (sensitive defence data — **do NOT commit it**). Tests/validator read it via the `WB_DEFAULT` constant; override with the `TIEDOWN_XLSX` env var.
- **dataclass + property pattern** exactly like `physics_engine.py`.

## File structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `tiedown_engine.py` | Create | Dataclasses (`DesignLoads`, `MountFace`, `FastenerSpec`, `Item`, `AxisResult`, `ItemResult`, `TiedownReport`), `analyze_item`, `run_tiedown_analysis`, `format_report` |
| `fastener_catalog.py` | Create | Fastener tables transcribed from the *Fastener Data* sheet + `bolt`/`non_bolt`/`make_fastener` + active sizing (`min_qty_for_target`, `size_fasteners`, `DEFAULT_POOL`) |
| `tiedown_import.py` | Create | Parse the *Workings* sheet into `Item` objects (reads sigma/area from the sheet's own cells for exact replication) |
| `validate_tiedown_excel.py` | Create | Recompute every item, diff vs the sheet SF columns, assert 177/177 to <1e-6 |
| `test_tiedown_engine.py` | Create | Engine unit checks (incl. Generator anchor SF) |
| `test_fastener_catalog.py` | Create | Catalog transcription + sizing checks |
| `test_tiedown_import.py` | Create | Import checks (count, item 1, item-49 override) |

---

### Task 0: Branch

- [ ] **Step 1: Create a feature branch off the current HEAD**

Run:
```bash
git checkout -b tiedown-replicator
```
Expected: `Switched to a new branch 'tiedown-replicator'`. (Keeps tie-down work off `1.3-shock-mount-evaluable-`.)

---

### Task 1: Engine core types (`tiedown_engine.py`)

**Files:**
- Create: `tiedown_engine.py`
- Test: `test_tiedown_engine.py`

- [ ] **Step 1: Write the failing test**

Create `test_tiedown_engine.py`:
```python
"""Standalone checks for tiedown_engine. Run: .\\mpd\\Scripts\\python.exe test_tiedown_engine.py"""
from tiedown_engine import DesignLoads, MountFace, FastenerSpec, Item


def test_fastener_forces():
    m6 = FastenerSpec("8.8 M6", "BOLT", 640.0, 320.0, 17.894)
    assert abs(m6.tensile_force_N - 11452.16) < 1e-6
    assert abs(m6.shear_force_N - 5726.08) < 1e-6
    assert abs(m6.yield_force_N("Tensile") - 11452.16) < 1e-6
    assert abs(m6.yield_force_N("Shear") - 5726.08) < 1e-6


def test_mount_face_force_types():
    assert MountFace.WALL_X.force_type("long") == "Tensile"
    assert MountFace.WALL_X.force_type("vert") == "Shear"
    assert MountFace.WALL_X.force_type("lat") == "Shear"
    assert MountFace.FLOOR_Z.force_type("vert") == "Tensile"
    assert MountFace.FLOOR_Z.force_type("long") == "Shear"
    assert MountFace.WALL_Y.force_type("lat") == "Tensile"
    assert MountFace.WALL_Y.force_type("long") == "Shear"


def test_design_loads_defaults():
    L = DesignLoads()
    assert (L.g, L.long_G, L.vert_G, L.lat_G) == (9.81, 4.0, 2.0, 1.5)


def test_item_design_kg_override():
    f = FastenerSpec("x", "BOLT", 640.0, 320.0, 17.894)
    assert Item("a", 59.0, MountFace.FLOOR_Z, f, 2, design_override_kg=60.0).design_kg == 60.0
    assert Item("b", 14.0, MountFace.WALL_X, f, 6).design_kg == 14.0


def _run():
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"[FAIL] {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\mpd\Scripts\python.exe test_tiedown_engine.py`
Expected: `ModuleNotFoundError: No module named 'tiedown_engine'`.

- [ ] **Step 3: Write minimal implementation**

Create `tiedown_engine.py`:
```python
"""
Tie-down provision physics engine.
Transcribed from: MCDLL Tie-Down Provision_20-8-2023.xlsx
Verified: reproduces all 59 items' safety factors to machine precision (177/177, max diff 9e-13).

Design forces per axis = weight * G_axis * g   (g=9.81; long=4G, vert=2G, lat=1.5G).
Fastener yield force    = sigma * area         (tensile uses sigma_t; shear uses sigma_s).
Mount face decides, per axis, whether the fastener sees tension or shear (see MountFace).
SF_axis = yield_force(force_type) / (design_force_axis / qty).
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# (axis label, DesignLoads attribute) — single source of axis order
AXES = (("long", "long_G"), ("vert", "vert_G"), ("lat", "lat_G"))


@dataclass
class DesignLoads:
    g: float = 9.81
    long_G: float = 4.0
    vert_G: float = 2.0
    lat_G: float = 1.5


class MountFace(Enum):
    """Face the item is fastened to; determines tension-vs-shear per load axis."""
    WALL_X = "WALL_X"    # front/rear wall (normal = longitudinal X): long load is Tensile
    FLOOR_Z = "FLOOR_Z"  # floor/ceiling/top frame/base (normal = vertical Z): vert load is Tensile
    WALL_Y = "WALL_Y"    # left/right side wall (normal = lateral Y): lat load is Tensile

    def force_type(self, axis: str) -> str:
        """axis in {'long','vert','lat'} -> 'Tensile' or 'Shear'."""
        tensile_axis = {
            MountFace.WALL_X: "long",
            MountFace.FLOOR_Z: "vert",
            MountFace.WALL_Y: "lat",
        }[self]
        return "Tensile" if axis == tensile_axis else "Shear"


@dataclass
class FastenerSpec:
    name: str
    kind: str            # BOLT, SPRING_LATCH, LOCKING_PIN, STRAP, RATCHET, CAMLOCK, DRING
    sigma_t_MPa: float   # tensile allowable (for straps: rated load in N, with area=1)
    sigma_s_MPa: float   # shear allowable (bolts/latches: sigma_t/2; straps: == sigma_t)
    area_mm2: float      # minor-diameter area (straps: 1.0)

    @property
    def tensile_force_N(self) -> float:
        return self.sigma_t_MPa * self.area_mm2

    @property
    def shear_force_N(self) -> float:
        return self.sigma_s_MPa * self.area_mm2

    def yield_force_N(self, force_type: str) -> float:
        return self.tensile_force_N if force_type == "Tensile" else self.shear_force_N


@dataclass
class Item:
    name: str
    weight_kg: float
    mount_face: MountFace
    fastener: FastenerSpec
    qty: int
    design_override_kg: Optional[float] = None  # item-49 quirk: design force based on a different kg

    @property
    def design_kg(self) -> float:
        return self.design_override_kg if self.design_override_kg is not None else self.weight_kg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\mpd\Scripts\python.exe test_tiedown_engine.py`
Expected: `4/4 passed`.

- [ ] **Step 5: Commit**

```bash
git add tiedown_engine.py test_tiedown_engine.py
git commit -m "feat(tiedown): engine core types (loads, mount-face, fastener, item)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Per-item analysis (`analyze_item`)

**Files:**
- Modify: `tiedown_engine.py` (append)
- Test: `test_tiedown_engine.py` (append)

- [ ] **Step 1: Write the failing test** — append to `test_tiedown_engine.py` (before `_run`):
```python
def test_generator_anchor():
    from tiedown_engine import analyze_item
    m12 = FastenerSpec("8.8 M12", "BOLT", 640.0, 320.0, 76.247)
    gen = Item("Generator", 1269.0, MountFace.FLOOR_Z, m12, 10)
    res = analyze_item(gen)
    by = {a.axis: a for a in res.axes}
    assert abs(by["long"].SF - 4.9) < 1e-2, by["long"].SF
    assert abs(by["vert"].SF - 19.599) < 1e-2, by["vert"].SF
    assert abs(by["lat"].SF - 13.066) < 1e-2, by["lat"].SF
    assert by["long"].force_type == "Shear"
    assert by["vert"].force_type == "Tensile"
    assert abs(res.min_SF - 4.9) < 1e-2


def test_water_jerry_can_marginal():
    from tiedown_engine import analyze_item
    camlock = FastenerSpec('Camlock Strap (1")', "CAMLOCK", 2500.0, 2500.0, 1.0)
    res = analyze_item(Item("Water Jerry Cans", 60.0, MountFace.FLOOR_Z, camlock, 1))
    assert abs(res.min_SF - 1.062) < 1e-2, res.min_SF
    assert res.limiting_axis.axis == "long"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.\mpd\Scripts\python.exe test_tiedown_engine.py`
Expected: `[FAIL] test_generator_anchor: cannot import name 'analyze_item'` (or AttributeError).

- [ ] **Step 3: Write minimal implementation** — append to `tiedown_engine.py`:
```python
@dataclass
class AxisResult:
    axis: str
    design_force_N: float
    force_type: str
    exp_force_N: float
    yield_force_N: float
    SF: float


@dataclass
class ItemResult:
    item: Item
    axes: list  # list[AxisResult], order = AXES

    @property
    def min_SF(self) -> float:
        return min(a.SF for a in self.axes)

    @property
    def limiting_axis(self) -> AxisResult:
        return min(self.axes, key=lambda a: a.SF)

    def passed(self, target_SF: float = 1.0) -> bool:
        return self.min_SF >= target_SF


def analyze_item(item: Item, loads: Optional[DesignLoads] = None) -> ItemResult:
    L = loads or DesignLoads()
    if item.qty <= 0:
        raise ValueError(f"{item.name}: qty must be > 0")
    axes = []
    for axis, gattr in AXES:
        design = item.design_kg * getattr(L, gattr) * L.g
        ftype = item.mount_face.force_type(axis)
        exp = design / item.qty
        yf = item.fastener.yield_force_N(ftype)
        axes.append(AxisResult(axis, design, ftype, exp, yf, yf / exp))
    return ItemResult(item, axes)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.\mpd\Scripts\python.exe test_tiedown_engine.py`
Expected: `6/6 passed`.

- [ ] **Step 5: Commit**
```bash
git add tiedown_engine.py test_tiedown_engine.py
git commit -m "feat(tiedown): per-item analysis with axis safety factors

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Report + formatting + smoke test

**Files:**
- Modify: `tiedown_engine.py` (append)
- Test: `test_tiedown_engine.py` (append)

- [ ] **Step 1: Write the failing test** — append to `test_tiedown_engine.py` (before `_run`):
```python
def test_report_and_critical_items():
    from tiedown_engine import run_tiedown_analysis, format_report
    f8 = FastenerSpec("8.8 M6", "BOLT", 640.0, 320.0, 17.894)
    camlock = FastenerSpec('Camlock Strap (1")', "CAMLOCK", 2500.0, 2500.0, 1.0)
    items = [
        Item("Bolted box", 14.0, MountFace.WALL_X, f8, 6),
        Item("Water Jerry Cans", 60.0, MountFace.FLOOR_Z, camlock, 1),
    ]
    rep = run_tiedown_analysis(items, target_SF=2.0)
    assert not rep.all_passed                       # water cans min_SF 1.06 < 2.0
    crit = rep.critical_items()
    assert len(crit) == 1 and crit[0].item.name == "Water Jerry Cans"
    assert "TIE-DOWN PROVISION ANALYSIS" in format_report(rep)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.\mpd\Scripts\python.exe test_tiedown_engine.py`
Expected: `[FAIL] test_report_and_critical_items: cannot import name 'run_tiedown_analysis'`.

- [ ] **Step 3: Write minimal implementation** — append to `tiedown_engine.py`:
```python
@dataclass
class TiedownReport:
    items: list           # list[ItemResult]
    loads: DesignLoads
    target_SF: float = 1.0

    @property
    def all_passed(self) -> bool:
        return all(r.passed(self.target_SF) for r in self.items)

    def critical_items(self, target_SF: Optional[float] = None) -> list:
        t = self.target_SF if target_SF is None else target_SF
        return [r for r in self.items if r.min_SF < t]


def run_tiedown_analysis(items: list, loads: Optional[DesignLoads] = None,
                         target_SF: float = 1.0) -> TiedownReport:
    L = loads or DesignLoads()
    return TiedownReport([analyze_item(it, L) for it in items], L, target_SF)


def format_report(report: TiedownReport) -> str:
    L = report.loads
    lines = [
        "=" * 70,
        "TIE-DOWN PROVISION ANALYSIS",
        f"  Design loads : long={L.long_G}G  vert={L.vert_G}G  lat={L.lat_G}G   (g={L.g})",
        f"  Items        : {len(report.items)}    target SF: {report.target_SF}",
        "=" * 70,
        f"{'Item':<34}{'min SF':>9}{'limit':>8}{'verdict':>10}",
        "-" * 70,
    ]
    for r in report.items:
        verdict = "PASS" if r.passed(report.target_SF) else "FAIL"
        lines.append(f"{r.item.name[:34]:<34}{r.min_SF:>9.3f}{r.limiting_axis.axis:>8}{verdict:>10}")
    crit = report.critical_items()
    lines.append("-" * 70)
    lines.append("Overall: " + ("ALL PASS" if report.all_passed
                                 else f"{len(crit)} item(s) below target SF {report.target_SF}"))
    lines.append("=" * 70)
    return "\n".join(lines)


if __name__ == "__main__":
    m12 = FastenerSpec("8.8 M12", "BOLT", 640.0, 320.0, 76.247)
    camlock = FastenerSpec('Camlock Strap (1")', "CAMLOCK", 2500.0, 2500.0, 1.0)
    demo = [
        Item("Generator", 1269.0, MountFace.FLOOR_Z, m12, 10),
        Item("Water Jerry Cans", 60.0, MountFace.FLOOR_Z, camlock, 1),
    ]
    rep = run_tiedown_analysis(demo, target_SF=2.0)
    print(format_report(rep))
    gen = rep.items[0]
    assert abs(gen.min_SF - 4.9) < 1e-2, gen.min_SF   # anchor (matches Excel)
    print("\n[OK] Generator anchor min SF = 4.9")
```

- [ ] **Step 4: Run to verify it passes**

Run: `.\mpd\Scripts\python.exe test_tiedown_engine.py`
Expected: `7/7 passed`.

Then run the smoke test: `.\mpd\Scripts\python.exe tiedown_engine.py`
Expected: a printed table ending with `[OK] Generator anchor min SF = 4.9`.

- [ ] **Step 5: Commit**
```bash
git add tiedown_engine.py test_tiedown_engine.py
git commit -m "feat(tiedown): report aggregation, formatter, smoke test

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Fastener catalog (`fastener_catalog.py`)

**Files:**
- Create: `fastener_catalog.py`
- Test: `test_fastener_catalog.py`

- [ ] **Step 1: Write the failing test**

Create `test_fastener_catalog.py`:
```python
"""Run: .\\mpd\\Scripts\\python.exe test_fastener_catalog.py"""
from fastener_catalog import bolt, non_bolt, make_fastener


def test_bolt_8p8_m6():
    f = bolt("8.8", "M6")
    assert abs(f.area_mm2 - 17.894) < 1e-9
    assert f.sigma_t_MPa == 640 and f.sigma_s_MPa == 320
    assert abs(f.tensile_force_N - 11452.16) < 1e-6
    assert abs(f.shear_force_N - 5726.08) < 1e-6


def test_bolt_m12():
    f = bolt("8.8", "M12")
    assert abs(f.area_mm2 - 76.247) < 1e-9
    assert abs(f.shear_force_N - 24399.04) < 1e-6


def test_camlock_strap():
    f = non_bolt('Camlock Strap (1")')
    assert f.sigma_t_MPa == 2500 and f.sigma_s_MPa == 2500 and f.area_mm2 == 1.0
    assert f.kind == "CAMLOCK"


def test_spring_latch_full_precision():
    f = non_bolt("Spring Latch")
    assert abs(f.area_mm2 - 113.09733552923255) < 1e-9
    assert f.sigma_t_MPa == 165 and f.sigma_s_MPa == 82.5
    assert abs(f.tensile_force_N - 18661.06) < 1e-2   # matches sheet item 12


def test_make_fastener_dispatch():
    assert make_fastener("8.8", "M8").kind == "BOLT"
    assert make_fastener('Ratchet (1")').kind == "RATCHET"


def _run():
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"[PASS] {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"[FAIL] {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.\mpd\Scripts\python.exe test_fastener_catalog.py`
Expected: `ModuleNotFoundError: No module named 'fastener_catalog'`.

- [ ] **Step 3: Write minimal implementation**

Create `fastener_catalog.py` (values transcribed at full precision from the *Fastener Data* sheet):
```python
"""
Fastener catalog for tie-down sizing.
Transcribed verbatim from the 'Fastener Data' sheet of
MCDLL Tie-Down Provision_20-8-2023.xlsx.

Bolts: sigma_s = sigma_t / 2.  Straps/ratchets: sigma_s = sigma_t, area = 1
(the value is a rated load in N).  Spring latch / locking pin: real area, sigma_s = sigma_t/2.
"""
import math
from dataclasses import dataclass
from typing import Optional

from tiedown_engine import DesignLoads, MountFace, FastenerSpec, Item, AXES, analyze_item

# Property class -> tensile allowable stress (MPa); shear taken as half.
BOLT_CLASSES = {
    "A2-70": 450.0, "4.6": 240.0, "4.8": 340.0, "5.8": 420.0,
    "8.8": 640.0, "9.8": 720.0, "10.9": 940.0, "12.9": 1100.0,
}

# Bolt size -> minor-diameter area (mm^2). Full precision from the sheet.
BOLT_SIZES = {
    "M1.6": 1.0762, "M2": 1.789, "M2.5": 2.9801, "M3": 4.4734, "M3.5": 5.9997,
    "M4": 7.7496, "M5": 12.683, "M6": 17.894, "M8": 32.841, "M10": 52.292,
    "M12": 76.247, "M14": 104.71, "M16": 144.12, "M20": 225.19, "M22": 281.53,
    "M24": 324.27, "M27": 427.09, "M30": 518.99, "M33": 647.19, "M36": 759.28,
    "1/4-20": 21.711908771848677,
}

# Non-bolt fasteners -> (kind, sigma_t, sigma_s, area).
NON_BOLTS = {
    'Camlock Strap (1")': ("CAMLOCK", 2500.0, 2500.0, 1.0),
    'Camlock Strap (1.5")': ("CAMLOCK", 18000.0, 18000.0, 1.0),
    'Ratchet (1")': ("RATCHET", 5000.0, 5000.0, 1.0),
    'Ratchet (1.5")': ("RATCHET", 30000.0, 30000.0, 1.0),
    "Strap (Net)": ("STRAP", 3500.0, 3500.0, 1.0),
    "DRing": ("DRING", 8896.0, 8896.0, 1.0),
    "Spring Latch": ("SPRING_LATCH", 165.0, 82.5, 113.09733552923255),
    "Locking Pin": ("LOCKING_PIN", 250.0, 125.0, 28.274333882308138),
}


def bolt(class_name: str, size: str) -> FastenerSpec:
    st = BOLT_CLASSES[class_name]
    return FastenerSpec(f"{class_name} {size}", "BOLT", st, st / 2.0, BOLT_SIZES[size])


def non_bolt(name: str) -> FastenerSpec:
    kind, st, ss, area = NON_BOLTS[name]
    return FastenerSpec(name, kind, st, ss, area)


def make_fastener(class_or_name: str, size: Optional[str] = None) -> FastenerSpec:
    if size is not None and size in BOLT_SIZES and class_or_name in BOLT_CLASSES:
        return bolt(class_or_name, size)
    if class_or_name in NON_BOLTS:
        return non_bolt(class_or_name)
    raise KeyError(f"Unknown fastener: class_or_name={class_or_name!r} size={size!r}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `.\mpd\Scripts\python.exe test_fastener_catalog.py`
Expected: `5/5 passed`.

- [ ] **Step 5: Commit**
```bash
git add fastener_catalog.py test_fastener_catalog.py
git commit -m "feat(tiedown): fastener catalog transcribed from Fastener Data sheet

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Active fastener sizing (closed form)

**Files:**
- Modify: `fastener_catalog.py` (append)
- Test: `test_fastener_catalog.py` (append)

- [ ] **Step 1: Write the failing test** — append to `test_fastener_catalog.py` (before `_run`):
```python
def test_min_qty_generator():
    from fastener_catalog import min_qty_for_target
    q = min_qty_for_target(1269.0, MountFace.FLOOR_Z, bolt("8.8", "M12"), target_SF=1.0)
    assert q == 3, q   # long axis governs: 49795.56 / 24399.04 = 2.04 -> ceil 3


def test_size_fasteners_meets_target():
    from fastener_catalog import size_fasteners
    opts = size_fasteners(60.0, MountFace.FLOOR_Z, target_SF=2.0)
    assert len(opts) >= 1
    assert opts[0].min_SF >= 2.0          # top option actually meets the target
    assert opts[0].qty >= 1
    # options are sorted by fewest fasteners, then smallest area
    assert all(opts[i].qty <= opts[i + 1].qty for i in range(len(opts) - 1))
```

Note these need `from tiedown_engine import MountFace` — already imported at top of the test file? Add this import line at the top of `test_fastener_catalog.py` in this step:
```python
from tiedown_engine import MountFace
```

- [ ] **Step 2: Run to verify it fails**

Run: `.\mpd\Scripts\python.exe test_fastener_catalog.py`
Expected: `[FAIL] ... cannot import name 'min_qty_for_target'`.

- [ ] **Step 3: Write minimal implementation** — append to `fastener_catalog.py`:
```python
@dataclass
class SizingOption:
    fastener: FastenerSpec
    qty: int
    min_SF: float


def min_qty_for_target(weight_kg: float, mount_face: MountFace, fastener: FastenerSpec,
                       target_SF: float = 1.0, loads: Optional[DesignLoads] = None) -> int:
    """Closed form: SF_axis = qty * yield(type) / design_axis, so
    min qty = ceil(max over axes of target_SF * design_axis / yield(type))."""
    L = loads or DesignLoads()
    need = 0.0
    for axis, gattr in AXES:
        design = weight_kg * getattr(L, gattr) * L.g
        yf = fastener.yield_force_N(mount_face.force_type(axis))
        need = max(need, target_SF * design / yf)
    return max(1, math.ceil(need))


# Default search pool for the sizing tool: common 8.8 bolts + the rated straps/latch.
DEFAULT_POOL = [
    bolt("8.8", "M6"), bolt("8.8", "M8"), bolt("8.8", "M10"), bolt("8.8", "M12"),
    non_bolt('Camlock Strap (1")'), non_bolt('Camlock Strap (1.5")'),
    non_bolt('Ratchet (1")'), non_bolt("Spring Latch"),
]


def size_fasteners(weight_kg: float, mount_face: MountFace, target_SF: float = 1.0,
                   pool: Optional[list] = None, loads: Optional[DesignLoads] = None) -> list:
    """Return sizing options (smallest valid first): fewest fasteners, then smallest area."""
    pool = pool if pool is not None else DEFAULT_POOL
    L = loads or DesignLoads()
    opts = []
    for spec in pool:
        q = min_qty_for_target(weight_kg, mount_face, spec, target_SF, L)
        res = analyze_item(Item(spec.name, weight_kg, mount_face, spec, q), L)
        opts.append(SizingOption(spec, q, res.min_SF))
    opts.sort(key=lambda o: (o.qty, o.fastener.area_mm2))
    return opts
```

- [ ] **Step 4: Run to verify it passes**

Run: `.\mpd\Scripts\python.exe test_fastener_catalog.py`
Expected: `7/7 passed`.

- [ ] **Step 5: Commit**
```bash
git add fastener_catalog.py test_fastener_catalog.py
git commit -m "feat(tiedown): active fastener sizing (closed-form min qty + ranked options)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Excel importer (`tiedown_import.py`)

**Files:**
- Create: `tiedown_import.py`
- Test: `test_tiedown_import.py`

**Design note:** the importer reads `sigma_t`/`sigma_s`/`area` directly from the *Workings* sheet's own cells (cols 11/12/10) — NOT from the catalog. This guarantees the validation matches the sheet to machine precision regardless of any catalog rounding, and keeps the importer independent of the catalog. Mount face is derived from which qty column (15/16/17) is populated (proven 0 multi-face rows). The item-49 design override is detected by comparing the sheet's longitudinal design-force cell to `weight * 4 * g`.

- [ ] **Step 1: Write the failing test**

Create `test_tiedown_import.py`:
```python
"""Run: .\\mpd\\Scripts\\python.exe test_tiedown_import.py  (reads the local reference workbook)"""
from tiedown_import import import_workbook, WB_DEFAULT


def test_import_count():
    items = import_workbook(WB_DEFAULT)
    assert len(items) == 59, len(items)


def test_import_item1():
    it = import_workbook(WB_DEFAULT)[0]
    assert "Air-Con" in it.name
    assert abs(it.weight_kg - 14.0) < 1e-9
    assert it.mount_face.value == "WALL_X"
    assert it.qty == 6
    assert abs(it.fastener.tensile_force_N - 11452.16) < 1e-3


def test_import_item49_override():
    it = import_workbook(WB_DEFAULT)[48]   # item 49, row index 48
    assert abs(it.weight_kg - 59.0) < 1e-9
    assert it.design_override_kg is not None
    assert abs(it.design_kg - 60.0) < 1e-3


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
            failed += 1; print(f"[ERROR] {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.\mpd\Scripts\python.exe test_tiedown_import.py`
Expected: `ModuleNotFoundError: No module named 'tiedown_import'`.

- [ ] **Step 3: Write minimal implementation**

Create `tiedown_import.py`:
```python
"""
Import the MCDLL Tie-Down Provision 'Workings' sheet into Item objects.
Reads sigma/area straight from the sheet cells (cols 10/11/12) for exact replication.

NOTE: the reference workbook is sensitive defence data and is NOT committed.
Keep it local; override the path with the TIEDOWN_XLSX env var if needed.
"""
import os
import math
import pandas as pd

from tiedown_engine import Item, MountFace, FastenerSpec

WORKINGS_SHEET = "Tie-Down Provision Workings"
WB_DEFAULT = os.environ.get(
    "TIEDOWN_XLSX",
    r"C:\Users\qujia\Downloads\MCDLL Tie-Down Provision_20-8-2023.xlsx",
)
FIRST_ROW, LAST_ROW = 9, 67   # 0-based row indices for items 1..59 (inclusive)
_G = 9.81

# 0-based column indices (verified against the workbook)
C_NAME, C_WEIGHT, C_LONG = 2, 3, 4
C_AREA, C_SIGMA_T, C_SIGMA_S = 10, 11, 12
C_CLASS, C_SIZE = 8, 9
C_QTY_LONG, C_QTY_VERT, C_QTY_LAT, C_QTY_TOTAL = 15, 16, 17, 18


def _num(x) -> float:
    return 0.0 if pd.isna(x) else float(x)


def _infer_kind(size_label: str) -> str:
    s = (size_label or "").strip().lower()
    if s.startswith("m") or s.startswith("1/4"):
        return "BOLT"
    if "camlock" in s:
        return "CAMLOCK"
    if "ratchet" in s:
        return "RATCHET"
    if "spring latch" in s:
        return "SPRING_LATCH"
    if "locking pin" in s:
        return "LOCKING_PIN"
    if "dring" in s or "d-ring" in s:
        return "DRING"
    if "strap" in s:
        return "STRAP"
    return "BOLT"


def item_from_row(df, r):
    """Build one Item from sheet row r, or None if the row has no weight."""
    w = df.iat[r, C_WEIGHT]
    if pd.isna(w):
        return None
    area = _num(df.iat[r, C_AREA])
    st = _num(df.iat[r, C_SIGMA_T])
    ss = _num(df.iat[r, C_SIGMA_S])
    ql, qv, qla = _num(df.iat[r, C_QTY_LONG]), _num(df.iat[r, C_QTY_VERT]), _num(df.iat[r, C_QTY_LAT])
    qty = int(_num(df.iat[r, C_QTY_TOTAL]))
    face = MountFace.WALL_X if ql > 0 else (MountFace.FLOOR_Z if qv > 0 else MountFace.WALL_Y)
    size_label = "" if pd.isna(df.iat[r, C_SIZE]) else str(df.iat[r, C_SIZE])
    cls_label = "" if pd.isna(df.iat[r, C_CLASS]) else str(df.iat[r, C_CLASS])
    name = str(df.iat[r, C_NAME]) if pd.notna(df.iat[r, C_NAME]) else f"item_row{r}"
    fastener = FastenerSpec(f"{cls_label} {size_label}".strip(), _infer_kind(size_label), st, ss, area)
    # item-49 quirk: design force based on a different kg than the weight cell
    design_kg = df.iat[r, C_LONG] / (4.0 * _G)
    override = round(design_kg, 6) if abs(design_kg - float(w)) > 1e-6 else None
    return Item(name=name, weight_kg=float(w), mount_face=face, fastener=fastener,
                qty=qty, design_override_kg=override)


def import_workbook(path: str = WB_DEFAULT, sheet: str = WORKINGS_SHEET) -> list:
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    items = []
    for r in range(FIRST_ROW, LAST_ROW + 1):
        it = item_from_row(df, r)
        if it is not None:
            items.append(it)
    return items
```

- [ ] **Step 4: Run to verify it passes**

Run: `.\mpd\Scripts\python.exe test_tiedown_import.py`
Expected: `3/3 passed`.

- [ ] **Step 5: Commit**
```bash
git add tiedown_import.py test_tiedown_import.py
git commit -m "feat(tiedown): workbook importer (sheet-exact sigma/area, face from qty col, item-49 override)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Excel validation harness (the headline 177/177 proof)

**Files:**
- Create: `validate_tiedown_excel.py`

- [ ] **Step 1: Write the validation script (this IS the test)**

Create `validate_tiedown_excel.py`:
```python
"""
Validate that tiedown_engine reproduces the workbook's safety factors.
Run: .\\mpd\\Scripts\\python.exe validate_tiedown_excel.py
Exit 0 = all 177 SFs match to < 1e-6; exit 1 = mismatch.
"""
import sys
import pandas as pd

from tiedown_import import item_from_row, WORKINGS_SHEET, WB_DEFAULT, FIRST_ROW, LAST_ROW
from tiedown_engine import analyze_item

C_SF = (43, 44, 45)   # sheet SF columns: long, vert, lat


def main(path: str = WB_DEFAULT) -> bool:
    df = pd.read_excel(path, sheet_name=WORKINGS_SHEET, header=None)
    items = 0
    compared = 0
    max_diff = 0.0
    worst = None
    for r in range(FIRST_ROW, LAST_ROW + 1):
        it = item_from_row(df, r)
        if it is None:
            continue
        items += 1
        res = analyze_item(it)
        for a, col in zip(res.axes, C_SF):
            sheet_sf = float(df.iat[r, col])
            compared += 1
            d = abs(a.SF - sheet_sf)
            if d > max_diff:
                max_diff = d
                worst = (r, a.axis, round(a.SF, 6), sheet_sf)
    ok = (items == 59 and compared == 177 and max_diff < 1e-6)
    print(f"items compared   : {items}")
    print(f"SFs compared     : {compared}")
    print(f"max abs diff     : {max_diff:.3e}")
    print(f"worst case       : {worst}")
    print("[PASS] engine reproduces all 177 safety factors to < 1e-6"
          if ok else "[FAIL] mismatch -- investigate the worst case above")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
```

- [ ] **Step 2: Run it**

Run: `.\mpd\Scripts\python.exe validate_tiedown_excel.py`
Expected:
```
items compared   : 59
SFs compared     : 177
max abs diff     : 9.095e-13
[PASS] engine reproduces all 177 safety factors to < 1e-6
```

- [ ] **Step 3: Commit**
```bash
git add validate_tiedown_excel.py
git commit -m "test(tiedown): Excel validation harness (177/177 SFs to <1e-6)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (vs `2026-05-29-tiedown-replicator-design.md`):**
- §3 verified physics model -> Tasks 1-3 (engine), Task 7 (177/177 proof). [covered]
- §4 module layout (`tiedown_engine`, `fastener_catalog`, `tiedown_import`) -> Tasks 1-6. [covered] (`agent.py`, `app.py`, `knowledge/tiedown` are Plans 2-3, out of scope here.)
- §5 data model -> Tasks 1-3 (all dataclasses + props present, names match). [covered]
- §6 fastener catalog -> Task 4 (full-precision transcription). [covered]
- §7 active sizing closed form + `size_fasteners` -> Task 5. [covered] (`run_tiedown_check`/`flag_critical_items`/`find_min_fasteners` are agent *tools* — Plan 2 — but their engine backing exists: `run_tiedown_analysis`, `critical_items`, `min_qty_for_target`.)
- §11 validation (177/177, Generator anchor 4.9/19.599/13.066) -> Tasks 2, 3, 7. [covered]
- §3.5 item-49 quirk -> Task 6 override logic + test. [covered]

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; every run step shows the exact command + expected output. [clean]

**3. Type consistency:** `FastenerSpec(name, kind, sigma_t_MPa, sigma_s_MPa, area_mm2)`, `MountFace.force_type(axis)`, `Item(... design_override_kg)`, `analyze_item`, `run_tiedown_analysis`, `min_qty_for_target`, `size_fasteners`, `import_workbook`, `item_from_row` — names/signatures are identical everywhere they appear across Tasks 1-7. `AXES` order (long, vert, lat) is the single source of truth used by the engine, sizing, and validator. [consistent]

**Out-of-scope (deferred to Plans 2-3, intentionally not here):** agent factory, agent tools, RAG knowledge docs, Streamlit tab, shock no-regression run.
