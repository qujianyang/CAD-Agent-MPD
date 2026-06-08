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
    assert "lookup_knowledge" in names


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
