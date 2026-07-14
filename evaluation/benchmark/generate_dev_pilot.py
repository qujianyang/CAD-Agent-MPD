"""Generate the first 10 shock-mount development cases from Python oracles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from catalog import (  # noqa: E402
    ALL_CATALOGS,
    AUTO_SELECT_CATALOGS,
    CB1400_CATALOG,
    CB1500_CATALOG,
    CB1700_CATALOG,
    CB61400_CATALOG,
    CatalogEntry,
    select_and_analyze,
)
from physics_engine import ShockEnv, run_analysis  # noqa: E402


LB_TO_KG = 0.45359237
SOURCE_VERSION = "dev-pilot-2026-07-13"
CATALOGS = {
    "AUTO": AUTO_SELECT_CATALOGS,
    "ALL": ALL_CATALOGS,
    "CB61400": CB61400_CATALOG,
    "CB1400": CB1400_CATALOG,
    "CB1500": CB1500_CATALOG,
    "CB1700": CB1700_CATALOG,
}


def _find_entry(part_no: str) -> CatalogEntry:
    return next(entry for entry in ALL_CATALOGS if entry.part_no == part_no)


def _static_ok(entry: CatalogEntry, mass_kg: float, n_bottom: int) -> bool | None:
    if entry.max_static_comp_daN is None:
        return None
    static_load_daN = (mass_kg / n_bottom) * 9.81 / 10.0
    return static_load_daN <= entry.max_static_comp_daN


def _report_summary(report, entry: CatalogEntry) -> dict[str, Any]:
    directions = []
    for direction in report.directions:
        utilization = max(
            direction.GT_G / direction.GT_limit,
            direction.delta_mm / direction.delta_limit_mm,
        )
        directions.append(
            {
                "label": direction.label,
                "GT_G": round(direction.GT_G, 6),
                "delta_mm": round(direction.delta_mm, 6),
                "utilization": round(utilization, 6),
                "passed": direction.passed,
            }
        )

    static_load_daN = (report.mass_kg / report.n_bottom) * 9.81 / 10.0
    static_ok = _static_ok(entry, report.mass_kg, report.n_bottom)
    governing = max(directions, key=lambda row: row["utilization"])
    if entry.max_static_comp_daN:
        static_utilization = static_load_daN / entry.max_static_comp_daN
        if static_utilization > governing["utilization"]:
            governing_check = "Static compression load"
        else:
            governing_check = governing["label"]
    else:
        static_utilization = None
        governing_check = governing["label"]

    passed = report.all_passed and static_ok is not False
    return {
        "verdict": "PASS" if passed else "FAIL",
        "governing_check": governing_check,
        "key_numbers": {
            "part_no": entry.part_no,
            "worst_GT_G": round(max(row["GT_G"] for row in directions), 6),
            "worst_delta_mm": round(max(row["delta_mm"] for row in directions), 6),
            "static_load_daN": round(static_load_daN, 6),
            "static_rating_daN": entry.max_static_comp_daN,
        },
        "units": {
            "worst_GT_G": "G",
            "worst_delta_mm": "mm",
            "static_load_daN": "daN",
            "static_rating_daN": "daN",
        },
        "directions": directions,
        "static_ok": static_ok,
        "static_utilization": (
            round(static_utilization, 6) if static_utilization is not None else None
        ),
    }


def _selection_gold(
    *,
    mass_kg: float,
    n_bottom: int = 6,
    n_wall: int = 4,
    Ao_G: float = 20.0,
    to_ms: float = 11.0,
    GT_limit_G: float = 10.0,
    pulse_shape: str = "sawtooth",
    series: str = "AUTO",
    objective: str = "max_clearance",
) -> dict[str, Any]:
    environment = ShockEnv(
        Ao_G=Ao_G,
        to_s=to_ms / 1000.0,
        GT_limit_G=GT_limit_G,
        pulse_shape=pulse_shape,
    )
    report, candidates = select_and_analyze(
        mass_kg=mass_kg,
        n_bottom=n_bottom,
        n_wall=n_wall,
        shock_env=environment,
        catalog=CATALOGS[series],
        objective=objective,
    )
    best = next((candidate for candidate in candidates if candidate.valid), None)
    if best is None:
        return {
            "verdict": "FAIL",
            "governing_check": "No catalogue candidate passes all gates",
            "key_numbers": {"selected_part_no": None},
            "units": {},
            "directions": [],
            "static_ok": None,
            "static_utilization": None,
        }
    summary = _report_summary(report, best.entry)
    summary["key_numbers"]["selected_part_no"] = best.entry.part_no
    return summary


def _verification_gold(
    *,
    part_no: str,
    mass_kg: float,
    n_bottom: int = 6,
    n_wall: int = 4,
    Ao_G: float = 20.0,
    to_ms: float = 11.0,
    GT_limit_G: float = 10.0,
    pulse_shape: str = "sawtooth",
) -> dict[str, Any]:
    entry = _find_entry(part_no)
    report = run_analysis(
        mass_kg=mass_kg,
        n_bottom=n_bottom,
        n_wall=n_wall,
        shock_env=ShockEnv(
            Ao_G=Ao_G,
            to_s=to_ms / 1000.0,
            GT_limit_G=GT_limit_G,
            pulse_shape=pulse_shape,
        ),
        isolator=entry.to_isolator_spec(),
    )
    return _report_summary(report, entry)


def _tool_call(name: str, args: dict[str, Any], tolerances=None) -> dict[str, Any]:
    return {"name": name, "args": args, "tolerances": tolerances or {}}


def _case(
    *,
    case_id: str,
    category: str,
    question: str,
    provided_inputs: dict[str, Any],
    gold_summary: dict[str, Any],
    tool_calls: list[dict[str, Any]],
    missing_inputs: list[str] | None = None,
    oracle_function: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "benchmark_version": "dev-v0.1",
        "domain": "shock_mount",
        "category": category,
        "question": question,
        "provided_inputs": provided_inputs,
        "gold": {
            "verdict": gold_summary.get("verdict"),
            "governing_check": gold_summary.get("governing_check"),
            "key_numbers": gold_summary.get("key_numbers", {}),
            "units": gold_summary.get("units", {}),
            "tool_calls": tool_calls,
            "missing_inputs": missing_inputs or [],
            "required_chunk_ids": [],
        },
        "oracle": {
            "function": oracle_function,
            "source_version": SOURCE_VERSION,
            "details": {
                "directions": gold_summary.get("directions", []),
                "static_ok": gold_summary.get("static_ok"),
                "static_utilization": gold_summary.get("static_utilization"),
            },
        },
    }


def build_cases() -> list[dict[str, Any]]:
    lb_mass_kg = 1870.0 * LB_TO_KG
    info_entry = _find_entry("CB1400-30")
    info_summary = {
        "verdict": None,
        "governing_check": None,
        "key_numbers": {
            "part_no": info_entry.part_no,
            "k_comp_lbin": info_entry.k_comp_lbin,
            "k_shear_lbin": info_entry.k_shear_lbin,
            "d_max_comp_mm": info_entry.d_max_comp_mm,
            "d_max_shear_mm": info_entry.d_max_shear_mm,
        },
        "units": {
            "k_comp_lbin": "lb/in",
            "k_shear_lbin": "lb/in",
            "d_max_comp_mm": "mm",
            "d_max_shear_mm": "mm",
        },
    }

    missing_summary = {
        "verdict": "ASK",
        "governing_check": None,
        "key_numbers": {},
        "units": {},
    }

    cases = [
        _case(
            case_id="shock_dev_001_select_defaults",
            category="tool_routing",
            question="Select an isolator for a 1,200 kg equipment rack using the project defaults.",
            provided_inputs={"mass_kg": 1200.0},
            gold_summary=_selection_gold(mass_kg=1200.0),
            tool_calls=[_tool_call("select_isolator", {"mass_kg": 1200.0})],
            oracle_function="catalog.select_and_analyze",
        ),
        _case(
            case_id="shock_dev_002_select_mounts",
            category="argument_extraction",
            question="Select an isolator for an 850 kg rack with 4 bottom mounts and 2 wall mounts.",
            provided_inputs={"mass_kg": 850.0, "n_bottom": 4, "n_wall": 2},
            gold_summary=_selection_gold(mass_kg=850.0, n_bottom=4, n_wall=2),
            tool_calls=[
                _tool_call(
                    "select_isolator",
                    {"mass_kg": 850.0, "n_bottom": 4, "n_wall": 2},
                )
            ],
            oracle_function="catalog.select_and_analyze",
        ),
        _case(
            case_id="shock_dev_003_select_softest",
            category="argument_extraction",
            question=(
                "Find the softest passing isolator for a 1,500 kg rack with 6 bottom "
                "and 4 wall mounts under a 20 G, 11 ms saw-tooth shock with a 10 G "
                "transmitted limit."
            ),
            provided_inputs={
                "mass_kg": 1500.0,
                "n_bottom": 6,
                "n_wall": 4,
                "Ao_G": 20.0,
                "to_ms": 11.0,
                "GT_limit_G": 10.0,
                "pulse_shape": "sawtooth",
                "objective": "best_isolation",
            },
            gold_summary=_selection_gold(
                mass_kg=1500.0,
                n_bottom=6,
                n_wall=4,
                Ao_G=20.0,
                to_ms=11.0,
                GT_limit_G=10.0,
                pulse_shape="sawtooth",
                objective="best_isolation",
            ),
            tool_calls=[
                _tool_call(
                    "select_isolator",
                    {
                        "mass_kg": 1500.0,
                        "n_bottom": 6,
                        "n_wall": 4,
                        "Ao_G": 20.0,
                        "to_ms": 11.0,
                        "GT_limit_G": 10.0,
                        "pulse_shape": "sawtooth",
                        "objective": "best_isolation",
                    },
                )
            ],
            oracle_function="catalog.select_and_analyze",
        ),
        _case(
            case_id="shock_dev_004_select_pounds",
            category="unit_conversion",
            question="A rack weighs 1,870 lb and uses 6 bottom and 4 wall mounts. Select an isolator.",
            provided_inputs={"mass_lb": 1870.0, "n_bottom": 6, "n_wall": 4},
            gold_summary=_selection_gold(
                mass_kg=lb_mass_kg, n_bottom=6, n_wall=4
            ),
            tool_calls=[
                _tool_call(
                    "select_isolator",
                    {"mass_kg": lb_mass_kg, "n_bottom": 6, "n_wall": 4},
                    {"mass_kg": {"relative": 0.001, "absolute": 0.05}},
                )
            ],
            oracle_function="catalog.select_and_analyze",
        ),
        _case(
            case_id="shock_dev_005_verify_pass",
            category="tool_routing",
            question=(
                "Verify CB1400-15 for an 850 kg rack using 6 bottom and 4 wall "
                "mounts under the project-default shock."
            ),
            provided_inputs={
                "part_no": "CB1400-15",
                "mass_kg": 850.0,
                "n_bottom": 6,
                "n_wall": 4,
            },
            gold_summary=_verification_gold(
                part_no="CB1400-15", mass_kg=850.0, n_bottom=6, n_wall=4
            ),
            tool_calls=[
                _tool_call(
                    "run_shock_analysis",
                    {
                        "part_no": "CB1400-15",
                        "mass_kg": 850.0,
                        "n_bottom": 6,
                        "n_wall": 4,
                    },
                )
            ],
            oracle_function="physics_engine.run_analysis",
        ),
        _case(
            case_id="shock_dev_006_verify_static_fail",
            category="safety_failure",
            question="Verify CB1400-60 for a 3,000 kg rack with 6 bottom and 4 wall mounts.",
            provided_inputs={
                "part_no": "CB1400-60",
                "mass_kg": 3000.0,
                "n_bottom": 6,
                "n_wall": 4,
            },
            gold_summary=_verification_gold(
                part_no="CB1400-60", mass_kg=3000.0, n_bottom=6, n_wall=4
            ),
            tool_calls=[
                _tool_call(
                    "run_shock_analysis",
                    {
                        "part_no": "CB1400-60",
                        "mass_kg": 3000.0,
                        "n_bottom": 6,
                        "n_wall": 4,
                    },
                )
            ],
            oracle_function="physics_engine.run_analysis plus catalog static gate",
        ),
        _case(
            case_id="shock_dev_007_verify_half_sine",
            category="argument_extraction",
            question=(
                "Does CB1400-12 pass for a 900 kg rack with 6 bottom and 4 wall "
                "mounts under a 15 G, 11 ms half-sine shock and a 10 G transmitted limit?"
            ),
            provided_inputs={
                "part_no": "CB1400-12",
                "mass_kg": 900.0,
                "n_bottom": 6,
                "n_wall": 4,
                "Ao_G": 15.0,
                "to_ms": 11.0,
                "GT_limit_G": 10.0,
                "pulse_shape": "half_sine",
            },
            gold_summary=_verification_gold(
                part_no="CB1400-12",
                mass_kg=900.0,
                n_bottom=6,
                n_wall=4,
                Ao_G=15.0,
                to_ms=11.0,
                GT_limit_G=10.0,
                pulse_shape="half_sine",
            ),
            tool_calls=[
                _tool_call(
                    "run_shock_analysis",
                    {
                        "part_no": "CB1400-12",
                        "mass_kg": 900.0,
                        "n_bottom": 6,
                        "n_wall": 4,
                        "Ao_G": 15.0,
                        "to_ms": 11.0,
                        "GT_limit_G": 10.0,
                        "pulse_shape": "half_sine",
                    },
                )
            ],
            oracle_function="physics_engine.run_analysis",
        ),
        _case(
            case_id="shock_dev_008_catalog_lookup",
            category="tool_routing",
            question=(
                "What are the compression stiffness, shear stiffness, and rated "
                "travel of CB1400-30?"
            ),
            provided_inputs={"part_no": "CB1400-30"},
            gold_summary=info_summary,
            tool_calls=[_tool_call("get_isolator_data", {"part_no": "CB1400-30"})],
            oracle_function="catalog.CB1400_CATALOG lookup",
        ),
        _case(
            case_id="shock_dev_009_missing_mass",
            category="missing_input",
            question=(
                "Select an isolator using 6 bottom and 4 wall mounts under a 20 G, "
                "11 ms saw-tooth shock."
            ),
            provided_inputs={
                "n_bottom": 6,
                "n_wall": 4,
                "Ao_G": 20.0,
                "to_ms": 11.0,
                "pulse_shape": "sawtooth",
            },
            gold_summary=missing_summary,
            tool_calls=[],
            missing_inputs=["mass_kg"],
            oracle_function="case-construction missing-input rule",
        ),
        _case(
            case_id="shock_dev_010_data_then_verify",
            category="multi_tool",
            question=(
                "Give me the catalogue data for CB1500-30, then verify whether it "
                "passes for a 1,500 kg rack with 6 bottom and 4 wall mounts."
            ),
            provided_inputs={
                "part_no": "CB1500-30",
                "mass_kg": 1500.0,
                "n_bottom": 6,
                "n_wall": 4,
            },
            gold_summary=_verification_gold(
                part_no="CB1500-30", mass_kg=1500.0, n_bottom=6, n_wall=4
            ),
            tool_calls=[
                _tool_call("get_isolator_data", {"part_no": "CB1500-30"}),
                _tool_call(
                    "run_shock_analysis",
                    {
                        "part_no": "CB1500-30",
                        "mass_kg": 1500.0,
                        "n_bottom": 6,
                        "n_wall": 4,
                    },
                ),
            ],
            oracle_function="catalog lookup plus physics_engine.run_analysis",
        ),
    ]

    ids = [case["case_id"] for case in cases]
    if len(cases) != 10 or len(set(ids)) != len(ids):
        raise AssertionError("Development pilot must contain exactly 10 unique cases.")
    return cases


def write_cases(path: Path, cases: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=True, separators=(",", ":")))
            handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).with_name("dev.jsonl"),
    )
    args = parser.parse_args(argv)
    cases = build_cases()
    write_cases(args.out, cases)
    verdict_counts: dict[str, int] = {}
    for case in cases:
        key = str(case["gold"]["verdict"])
        verdict_counts[key] = verdict_counts.get(key, 0) + 1
    print(f"Wrote {len(cases)} cases to {args.out}")
    print(f"Gold verdict counts: {verdict_counts}")
    for case in cases:
        tools = [call["name"] for call in case["gold"]["tool_calls"]]
        print(
            f"{case['case_id']}: verdict={case['gold']['verdict']} "
            f"tools={tools}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

