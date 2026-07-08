# Shock Mount Tab — Complete Reference (for teaching)

This document describes the shock-isolator selection feature of a mechanical-safety
assistant: the engineering physics, the catalog, the selection logic, the software
architecture, and its limitations. It is written so a language model can use it to
**teach the reader** the subject and the tool. Ask it to explain any section, walk a
worked example, quiz you, or critique the design.

---

## 1. The problem this solves

Electronic equipment racks mounted on vehicles, ships, or shelters experience
**mechanical shock** (a short, violent acceleration pulse — e.g. a wheel hitting a
crater, a hull slam, an air-drop impact). Rigidly bolted equipment would receive the
full shock and its circuit boards, connectors, and hard drives could fail.

The fix is **shock isolators** (here, wire-rope isolators — loops of steel cable that
flex and dissipate energy). They sit between the rack and the vehicle. A softer
isolator lets the rack move more but transmits *less* acceleration to the equipment.

The engineering task: **pick an isolator that transmits little enough shock to protect
the equipment, without needing more sway space than is available, and without being
statically overloaded by the rack's own weight.** That is a trade-off, and this tool
automates it against a validated physics model and a real vendor catalog.

Key idea for the whole tool: **softer = better isolation, up to the point where the
rack sways too far or the mounts can't carry the static weight.** Selection walks the
catalog from softest to stiffest and picks the first part that passes every check.

---

## 2. The physics (four formulas)

A shock isolator + rack behaves like a single-degree-of-freedom spring–mass system.
Under a short pulse the response is governed by four equations. All SI internally.

| Quantity | Symbol | Formula | Meaning |
|---|---|---|---|
| Velocity change | V | `V = C · g · Ao · to` | The pulse's "kick", as a velocity step (m/s) |
| Natural frequency | fn | `fn = (1/2π) · √(K/m)` | How fast the isolated rack bounces (Hz) |
| Transmitted acceleration | GT | `GT = (2π · fn · V) / g` | The shock the equipment actually feels (in g) |
| Peak dynamic deflection | ΔD | `ΔD = V / (2π · fn)` | How far the rack sways at peak (m → mm) |

Where:
- `g = 9.81 m/s²`
- `Ao` = input shock magnitude, in g (e.g. 20 g)
- `to` = pulse duration, in seconds (e.g. 0.011 s = 11 ms)
- `C` = pulse-shape coefficient: **sawtooth = 0.5**, **half-sine = 2/π ≈ 0.637**
  (a half-sine of the same Ao/to is ~27% harsher because it delivers more impulse)
- `K` = isolator stiffness in that direction (N/m)
- `m` = mass carried by one isolator in that load case (kg)

### What the formulas *say* physically
- Stiffer spring (higher K) → higher fn → **higher GT** (worse isolation) but **smaller
  ΔD** (less sway). Softer spring → the opposite. This is the core trade-off.
- GT does not depend on mass directly, but fn does (through K/m), so heavier load per
  mount lowers fn and *reduces* GT while *increasing* ΔD. Distributing load over more
  mounts raises fn per mount.
- A longer or harsher pulse (bigger V) raises **both** GT and ΔD proportionally.

### Worked example (the validation anchor — memorize this one)
Part **CB1400-15**, rack mass **850 kg**, **6 bottom + 4 wall** mounts, shock **20 g /
11 ms sawtooth**. Compression-Bottom case:
- Mass per bottom mount: `m = 850 / 6 = 141.67 kg`
- `K_comp = 2650 lb/in = 464,086 N/m`
- `fn = (1/2π)·√(464086 / 141.67) = 9.11 Hz`
- `V = 0.5 · 9.81 · 20 · 0.011 = 1.079 m/s`
- `GT = (2π · 9.11 · 1.079) / 9.81 = 6.296 g`
- `ΔD = 1.079 / (2π · 9.11) = 0.01885 m = 18.85 mm`

**GT = 6.296 g, ΔD = 18.85 mm.** These match a hand-validated Excel sheet to 4 decimal
places; any change to the engine must still reproduce them.

---

## 3. The four load cases (and the /2 rule)

A shock can come from any direction, and the rack is held by bottom mounts (on the
floor) and wall mounts (on a vertical face). The tool evaluates **four** cases; a part
must pass **all four**. Each case has its own load-per-mount and uses either the
compression stiffness or the shear stiffness of the isolator.

| Case | Direction | Mass per mount | Stiffness used | Travel limit |
|---|---|---|---|---|
| **Comp-Bottom** | Z (vertical) | `M / n_bottom` | K_comp | d_max_comp |
| **Comp-Wall** | Y (lateral) | `M / n_wall / 2` | K_comp | d_max_comp |
| **Roll-Wall** | X,Z (shear) | `M / n_wall / 2` | K_shear | d_max_shear |
| **Roll-Bottom** | X,Y (shear) | `M / n_bottom / 2` | K_shear | d_max_shear |

**The /2 rule:** every case divides the load by 2 **except Comp-Bottom**. Reason:
gravity is one-directional, so under vertical compression all bottom mounts carry the
full weight together (`M / n_bottom`). In the lateral/roll cases the load is shared
between two opposing faces, so each side sees half. This asymmetry is transcribed
verbatim from the validated Excel (`=E8/E21/2` for wall/roll, `=M/n` for Comp-Bottom)
and is **intentional — do not "fix" it.**

`M` = total rack mass, `n_bottom` / `n_wall` = number of mounts of each type.

---

## 4. The isolator's five numbers (`IsolatorSpec`)

The physics engine is **vendor-agnostic**. It knows nothing about brands. Every
isolator — catalog or custom — is reduced to exactly five numbers, and every formula
above runs on these and nothing else:

```
IsolatorSpec(
    name,                 # label only
    k_comp_Nm,            # compression stiffness  [N/m]
    k_shear_Nm,           # shear / roll stiffness [N/m]
    d_max_comp_mm,        # max rated dynamic travel, compression [mm]
    d_max_shear_mm,       # max rated dynamic travel, shear       [mm]
    max_static_comp_daN,  # vendor max static load, compression [daN] (optional)
)
```

This is the clean boundary of the whole system: **anything that can be expressed as
these five numbers can be analyzed.** Getting from a vendor's published data to these
five numbers is the *only* vendor-specific work (see §8).

---

## 5. The catalog (real parts)

The default catalog is the **VMC / Helical CB wire-rope isolator** families. Stiffness
values are published as **Shock Average K** in lb/in; travels in inches; static loads
in daN. Softer parts have higher dash numbers.

| Family | Wire rope | Role | Stiffness range (comp, lb/in) |
|---|---|---|---|
| **CB1400** | 1/2" | light–mid racks | 3515 (−10, stiffest) → 265 (−60, softest) |
| **CB1500** | 5/8" | mid racks | 5375 (−12) → 795 (−50) |
| **CB1700** | 7/8" | heavy racks | 7565 (−15) → 1285 (−40) |
| **CB61400** | 1/2", 6-strand | ~25% softer than CB1400; **opt-in only** | 1990 (−15) → 200 (−60) |

- **Default selection pool (`AUTO`)** = CB1400 + CB1500 + CB1700. This matches the
  supervisor's stated range and covers practical 19" rack masses.
- **CB61400 is excluded by default** because it is so soft it produces 60–80 mm
  deflections at typical rack masses — usually impractical. It is opt-in (`series="ALL"`
  or `"CB61400"`).
- Sample row for reference: `CB1400-15` → K_comp 2650 lb/in, K_shear 1080 lb/in,
  travel comp 1.40", shear 1.60", max static comp 416 daN.

Each part also stores an optional **Vibration Average K** (2–3× the shock K) used by a
separate road-vibration/PSD check — *not* the shock K. Do not confuse the two.

---

## 6. Selection logic ("softest valid K")

Given a rack (mass, mount counts) and a shock environment (Ao, to, pulse, GT limit),
the selector:

1. Evaluates every catalog part through all four load cases.
2. Marks a part **valid** only if it passes **every** gate (below).
3. Sorts valid parts and returns the **softest** one (lowest K → lowest transmitted G →
   best isolation). This default objective is `best_isolation`.

Alternative objectives:
- `max_clearance` — pick the **stiffest** valid part (smallest deflection / most sway
  margin), for tight installations.
- `balanced` — furthest from any limit.

### The pass/fail gates
A part is valid only if, in all four cases:
1. **Transmitted-G gate:** `GT < GT_limit` (the equipment's shock tolerance, in g).
2. **Deflection gate:** `ΔD < d_max` where `d_max = min(mount rated travel, installation
   clearance)` for that axis (§7).
3. **Static-load gate:** the static weight on a bottom mount,
   `static_load_daN = (M / n_bottom) · g / 10`, must not exceed the part's
   `max_static_comp_daN`. If the vendor did not publish a static rating, this becomes a
   **warning**, not a hard fail.
4. **Impulse-validity guard:** the impulse approximation is only valid when `fn · to` is
   small (roughly, the pulse is short relative to the natural period). If violated, the
   GT/ΔD figures for that part are flagged unreliable.

If no part passes, the tool reports it and suggests relaxing the GT limit or adding
mounts (more mounts → less load per mount → different fn → often lets a softer part
pass).

---

## 7. Installation clearance (per axis)

"Clearance" is the physical gap to neighbouring equipment — how far the rack is allowed
to sway before it hits something. It is entered per axis (X, Y, Z, in mm). The
effective deflection limit for a case becomes `min(mount's own rated travel, mapped
clearance)`. Axis→case mapping:
- Z clearance → Comp-Bottom
- Y clearance → Comp-Wall
- X and Z → Roll-Wall
- X and Y → Roll-Bottom

A clearance of 0 means "no clearance limit" (only the mount's own travel constrains it).
So tight clearance can disqualify an otherwise-passing soft part and push selection
toward a stiffer one.

---

## 8. Vendor-agnostic custom isolators

Any isolator that is **not** in the CB catalog — a Vibratec part, a Socitec part, a
hand-typed prototype — can still be analyzed, because the engine only needs the five
numbers. The custom path converts vendor data into an `IsolatorSpec` and runs the
*same* validated engine.

### The rule that governs the design
> **The LLM decides the workflow. Python owns the calculation.**

The language model must **never** convert units or derive stiffness in its head — it
will eventually mix units, misread "@ 10 Hz", or swap compression/shear. Instead:
- The model (or a form) extracts the vendor row into a structured input.
- **Python** validates required fields, converts units, derives K, and runs the physics.
- The model only reports the result and relays the caveats.

### Three ways stiffness can be given (each with a provenance stamp)
| Input method | How K is obtained | `stiffness_source` | Validation level |
|---|---|---|---|
| **Direct shock K** (e.g. VMC lb/in, N/mm, N/m) | used directly | `published_shock_k` | **validated** |
| **Rated load @ frequency** (e.g. Vibratec 30 kg @ 10 Hz) | `K = m·(2π·f)²` | `derived_from_vibration_frequency` | **screening_only** |
| **Shock force / deflection pair** (e.g. Socitec) | `K = F / δ` (secant) | `derived_from_shock_load_deflection` | **screening_only** |

**Why "screening_only" matters:** wire-rope stiffness is amplitude-dependent, so a K
derived from small-amplitude vibration data under-represents true shock behaviour. The
result is a preliminary screen, not a validated verdict. The assistant says so
explicitly: *"CB1400-15: validated shock stiffness"* vs *"A070146-061: screening
estimate — K derived from vibration data; request shock K before committing."*

### Validation-first (fail before physics)
Missing shear data, a zero/negative frequency, or an unknown unit are **rejected**
(the assistant asks for the missing value) rather than defaulted. The physics never
runs on invented numbers.

Worked derivation (Vibratec A070146-061, compression 30 kg @ 10 Hz):
`K = 30 · (2π·10)² = 30 · 3947.8 = 118,435 N/m`, stamped screening-only.

---

## 9. The agent tools

The chat assistant is given a fixed set of deterministic Python tools; it chooses which
to call and explains the results. It cannot compute engineering numbers itself.

| Tool | Purpose |
|---|---|
| `select_isolator(mass_kg, …)` | Pick the softest passing catalog part for a rack + shock config. |
| `run_shock_analysis(mass_kg, part_no, …)` | Verify one named part: GT / fn / ΔD for all four cases. |
| `get_isolator_data(part_no / series)` | Look up stiffness, travel, size of a part or family. |
| `find_capacity_limit(part_no, …)` | Binary-search the mass range a given part can support. |
| `filter_by_deflection(max_dD_mm, …)` | Categorize parts: qualifying / over-clearance / fails-shock. |
| `analyze_custom_isolator(vendor, part_no, …)` | Analyze a non-catalog/vendor part from supplied data (§8). |
| `lookup_knowledge(query)` | Retrieve formulas / rules / catalog notes to cite (explanations only). |

Design conventions:
- **OMIT rule:** each tool's docstring tells the model to *omit* any parameter the user
  did not state, so project defaults apply instead of invented values.
- **Pulse duration is `to_ms` (milliseconds), not seconds** at the model interface,
  because the model kept truncating `0.011` to `0`; the tool converts to seconds
  internally. This is an architecture-level anti-hallucination fix, not a prompt plea.
- Default shock environment when unstated: 20 g, 11 ms, sawtooth, 10 g GT limit,
  6 bottom + 4 wall.

---

## 10. The UI (three modes) and the layout drawing

The shock tab offers three selection modes:
1. **Auto** — enter rack mass + mounts + shock; get the recommended softest passing part.
2. **Manual** — verify a specific named part you already have in mind.
3. **Custom vendor data** — key in a non-catalog part's stiffness/travel/static with unit
   dropdowns; get its four-case verdict with the validation-level caveat (§8).

Mass, CG, and bounding box can also be pulled live from a SolidWorks assembly (CAD
extraction) instead of typed.

After a selection, a **deterministic 3D layout drawing** shows the equipment box, the
mount positions (bottom + wall, placed corners-first around the base), the coordinate
axes, the **shock movement envelope** (the rack's computed sway, per axis), and the
**clearance envelope**. If the sway exceeds the clearance on any axis, that axis is
flagged red. Every element is computed from the physics result — no AI drawing, so mount
counts and dimensions are always exact.

---

## 11. Design principles worth understanding

- **Deterministic core, AI as orchestrator.** All engineering math is validated Python.
  The LLM interprets intent, picks tools, and explains — it never calculates. This is
  the reliability backbone.
- **Vendor-neutral interface.** The engine consumes five numbers; brand adapters only
  normalize into them. Adding a vendor never touches the physics.
- **Provenance is first-class.** Every result carries how trustworthy its stiffness
  source is (validated vs screening) and propagates warnings to the user.
- **Fail loudly, never silently default a safety input.** Missing/impossible inputs
  produce an explicit ask, not a guess.

---

## 12. What the tool does NOT do (limitations — important)

Be honest about these when learning or demoing:
- **It verifies/selects given a mounting config; it does not yet *size the config from
  scratch.*** The number of mounts (`n_bottom`, `n_wall`) is a required *input*, not a
  recommended *output*. A user who only has "rack dimensions + weight" still has to
  decide (or guess) how many isolators to use. A true step-by-step sizer would derive
  the mount count from the static rating and iterate the selection — that capability is
  not built yet.
- **Single-mass model.** It analyzes one lumped rack mass with the load-sharing `/2`
  rule. It is not a multi-bay / multi-body model, even though real installations can be
  "bayed" (several racks on a shared raft).
- **CG is currently informational.** Mass distribution follows the Excel reference; the
  CG height only drives an overturning *warning*, not the load split.
- **Single linear stiffness per direction.** Real wire-rope isolators are non-linear
  (amplitude-dependent); the model uses one representative K — exact for published shock
  K, approximate (screening) for derived K.
- **File upload of datasheets is not wired yet.** Custom parts are entered via the form
  or the chat tool; parsing an uploaded Excel/PDF into the form is a planned next step.

---

## 13. Good questions to ask the teacher LLM

- "Walk me through why more mounts can let a *softer* isolator pass."
- "Recompute the 850 kg / CB1400-15 example for a 15 g / 6 ms half-sine pulse."
- "Why is Comp-Bottom the only case without the /2, physically?"
- "If my equipment tolerates 8 g and I have 40 mm of clearance, how does that change the
  choice?"
- "Explain why a vibration-derived K is only 'screening' for shock."
- "Design a step-by-step flow that would size the mount count from rack weight and
  dimensions — what's the missing calculation?"
- "Quiz me on the four load cases and which stiffness/travel each uses."
