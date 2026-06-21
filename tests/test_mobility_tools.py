"""Offline tests for the granular mobility tools (no LLM, no API key).
Run: .\\mpd\\Scripts\\python.exe -m pytest tests/test_mobility_tools.py
"""
from mobility_import import vehicle_measured
from mobility_tools import (
    get_vehicle_baseline,
    derive_cg_from_wheel_loads,
    derive_zcg_from_tilt_tests,
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
        assert "FAIL structural limits" in out
        assert "baseline" in out and "modified" in out

    def test_final_modified_block_is_source_of_truth(self):
        # 3,200 kg shelter add: front/rear/GVW over, steer still OK. Regression for
        # the agent quoting the baseline side of the "->" arrow instead of modified.
        out = evaluate_mass_change.invoke(
            {"action": "add", "mass_kg": 3200, "x_mm": 4000, "z_mm": 1800,
             "description": "shelter"})
        assert "FINAL MODIFIED RESULT" in out
        assert "Modified vehicle: FAIL structural limits" in out
        # per-check lines restate the MODIFIED value + verdict (no baseline adjacent)
        assert "Front axle: 8,508.3 kg [OVER]" in out
        assert "Rear axle: 12,541.7 kg [OVER]" in out
        assert "GVW: 21,050 kg [OVER]" in out
        assert "Steer (front): 40.42% [OK]" in out
        assert "Failed checks: Front axle, Rear axle, GVW" in out
        assert "Passed checks: Steer" in out
        assert "Modified governing slope: ascending 60% SF=1.9651" in out
        assert "Modified cornering SF: 3.1831" in out
        # old misleading wording must be gone
        assert "fails axle/GVW/steer" not in out

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


class TestDeriveZcgFromTiltTests:
    # E2 tilt-test data: F_level = RL+RR = 9875 kg, GW = 17850 kg, WB = 4800 mm
    E2 = {"f_level_kg": 9875, "gw_kg": 17850,
          "tilt_angles_deg": "10.2, 12.3, 8.2, 6.2",
          "rear_loads_kg": "10550, 10700, 10450, 10300"}

    def test_reproduces_e2_zcg_values_and_average(self):
        out = derive_zcg_from_tilt_tests.invoke(dict(self.E2))
        assert "1,588.8" in out and "1,597.5" in out
        assert "1,653.0" in out and "1,632.0" in out
        assert "1,617.8" in out                       # average
        assert "tilt test" in out                     # usable zcg_source hint

    def test_explicit_wheelbase_matches_workbook_default(self):
        out_default = derive_zcg_from_tilt_tests.invoke(dict(self.E2))
        out_explicit = derive_zcg_from_tilt_tests.invoke(
            {**self.E2, "wheelbase_mm": 4800})
        assert "1,617.8" in out_default and "1,617.8" in out_explicit

    def test_mismatched_list_lengths_is_error(self):
        out = derive_zcg_from_tilt_tests.invoke(
            {**self.E2, "rear_loads_kg": "10550, 10700"})
        assert out.startswith("ERROR")

    def test_unparseable_list_is_error(self):
        out = derive_zcg_from_tilt_tests.invoke(
            {**self.E2, "tilt_angles_deg": "ten, twelve, eight, six"})
        assert out.startswith("ERROR")

    def test_bad_angle_is_error(self):
        out = derive_zcg_from_tilt_tests.invoke(
            {**self.E2, "tilt_angles_deg": "0, 12.3, 8.2, 6.2"})
        assert out.startswith("ERROR")

    def test_nonpositive_f_level_is_error(self):
        out = derive_zcg_from_tilt_tests.invoke({**self.E2, "f_level_kg": 0})
        assert out.startswith("ERROR")


class TestEvaluateMassChangeIsoDatum:
    def test_iso_datum_equals_axle_datum_shifted_1450(self):
        """X entered from the front ISO plane must give the same physics as the
        equivalent front-axle X (X_axle = X_ISO + 1450)."""
        out_axle = evaluate_mass_change.invoke(
            {"action": "add", "mass_kg": 500, "x_mm": 4450, "z_mm": 1500})
        out_iso = evaluate_mass_change.invoke(
            {"action": "add", "mass_kg": 500, "x_mm": 3000, "z_mm": 1500,
             "x_datum": "front_iso"})
        # Same modified CG/axle numbers in both outputs (compare the table body
        # after the header, which echoes the differing input position).
        body_axle = out_axle.split("===", 2)[-1]
        body_iso = out_iso.split("===", 2)[-1]
        assert body_axle == body_iso

    def test_iso_output_reports_both_datums(self):
        out = evaluate_mass_change.invoke(
            {"action": "add", "mass_kg": 500, "x_mm": 3000, "z_mm": 1500,
             "x_datum": "front_iso"})
        assert "front ISO" in out and "front axle" in out

    def test_bad_datum_is_error(self):
        out = evaluate_mass_change.invoke(
            {"action": "add", "mass_kg": 500, "x_mm": 3000, "z_mm": 1500,
             "x_datum": "rear_bumper"})
        assert out.startswith("ERROR")


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
