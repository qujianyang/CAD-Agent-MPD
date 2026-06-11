"""Offline tests for the granular mobility tools (no LLM, no API key).
Run: .\\mpd\\Scripts\\python.exe -m pytest tests/test_mobility_tools.py
"""
from mobility_import import vehicle_measured
from mobility_tools import (
    get_vehicle_baseline,
    derive_cg_from_wheel_loads,
    evaluate_mass_change,
)

# Real measured-E2 wheel readings: front 7,975 kg / rear 9,875 kg -> GW 17,850.
WHEELS = {"fl_kg": 4000, "fr_kg": 3975, "rl_kg": 4750, "rr_kg": 5125}


class TestGetVehicleBaseline:
    def test_default_returns_both_variants(self):
        out = get_vehicle_baseline.invoke({})
        assert "MEASURED CG" in out and "THEORY CG" in out
        assert "17,850" in out                       # measured GW
        assert "Xcg" in out and "Zcg" in out
        assert "Delta (theory - measured)" in out
        assert "limit 8,000" in out and "limit 10,600" in out

    def test_single_variant(self):
        out = get_vehicle_baseline.invoke({"variant": "measured"})
        assert "MEASURED CG" in out
        assert "THEORY CG" not in out
        assert "Delta" not in out

    def test_no_stability_results(self):
        out = get_vehicle_baseline.invoke({})
        assert "SF=" not in out and "cornering" not in out.lower()


class TestDeriveCgFromWheelLoads:
    def test_moment_balance_matches_engine(self):
        out = derive_cg_from_wheel_loads.invoke(dict(WHEELS))
        v = vehicle_measured()
        assert "17,850.0 kg" in out
        assert f"{v.wheelbase_mm * 9875 / 17850:,.1f} mm" in out   # Xcg hand-check
        assert "7,975.0 kg" in out and "9,875.0 kg" in out          # axles = sums

    def test_zcg_not_derivable_message(self):
        out = derive_cg_from_wheel_loads.invoke(dict(WHEELS))
        assert "Zcg NOT determined" in out
        assert "tilt test" in out

    def test_zcg_without_source_is_error(self):
        out = derive_cg_from_wheel_loads.invoke({**WHEELS, "zcg_mm": 1700})
        assert out.startswith("ERROR") and "source" in out.lower()

    def test_zcg_with_source_builds_full_vehicle(self):
        out = derive_cg_from_wheel_loads.invoke(
            {**WHEELS, "zcg_mm": 1700, "zcg_source": "tilt test"})
        assert "1,700.0 mm" in out and "tilt test" in out
        assert "full slope/cornering analysis" in out

    def test_nonpositive_load_is_error(self):
        out = derive_cg_from_wheel_loads.invoke({**WHEELS, "fl_kg": 0})
        assert out.startswith("ERROR")


class TestEvaluateMassChange:
    def test_rear_overload_detected(self):
        out = evaluate_mass_change.invoke(
            {"action": "add", "mass_kg": 3000, "x_mm": 5000, "z_mm": 1500})
        assert "20,850" in out                       # new GW
        assert "13,000.0" in out and "[OVER]" in out  # rear axle over 10,600
        assert "LIMIT EXCEEDED" in out
        assert "baseline" in out and "modified" in out

    def test_zero_mass_is_error(self):
        out = evaluate_mass_change.invoke({"action": "add", "mass_kg": 0})
        assert out.startswith("ERROR") and "ASK" in out

    def test_missing_z_is_error_not_crash(self):
        out = evaluate_mass_change.invoke(
            {"action": "add", "mass_kg": 500, "x_mm": 3000})
        assert out.startswith("ERROR") and "Z" in out

    def test_bad_action_is_error(self):
        out = evaluate_mass_change.invoke({"action": "swap", "mass_kg": 100})
        assert out.startswith("ERROR")

    def test_relocate_keeps_gw(self):
        out = evaluate_mass_change.invoke(
            {"action": "relocate", "mass_kg": 500,
             "x_mm": 3000, "y_mm": 0, "z_mm": 1500,
             "new_x_mm": 2500, "new_y_mm": 0, "new_z_mm": 1500})
        assert "+0" in out                            # GW change is zero
        assert "Governing slope" in out


def _run():
    import sys
    classes = [v for k, v in sorted(globals().items()) if k.startswith("Test")]
    failed = 0
    for cls in classes:
        inst = cls()
        for name in sorted(dir(inst)):
            if not name.startswith("test_"):
                continue
            try:
                getattr(inst, name)(); print(f"[PASS] {cls.__name__}.{name}")
            except AssertionError as e:
                failed += 1; print(f"[FAIL] {cls.__name__}.{name}: {e}")
            except Exception as e:
                failed += 1; print(f"[ERROR] {cls.__name__}.{name}: {type(e).__name__}: {e}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
