"""Run: .\\mpd\\Scripts\\python.exe test_build_agent.py  (offline; inspects the registry only)"""
SHOCK_8 = sorted([
    "extract_cad_data", "select_isolator", "run_shock_analysis",
    "find_capacity_limit", "filter_by_deflection", "get_isolator_data",
    "lookup_knowledge", "list_cad_files",
])


def test_shock_domain_unchanged():
    from agent import DOMAINS, _SYSTEM_PROMPT
    shock = DOMAINS["shock_mount"]
    assert sorted(t.name for t in shock["tools"]) == SHOCK_8
    assert shock["prompt"] is _SYSTEM_PROMPT      # exact same prompt object


TIEDOWN_5 = sorted([
    "run_tiedown_check", "recommend_fasteners", "get_fastener_data",
    "check_workbook_item", "lookup_knowledge",
])


def test_tiedown_domain_wired():
    from agent import DOMAINS
    names = sorted(t.name for t in DOMAINS["tiedown"]["tools"])
    assert names == TIEDOWN_5   # exact lock; flag_critical_items stays retired


def test_every_tiedown_tool_is_documented():
    """Every registered tie-down tool must appear in the user-facing capability guide."""
    from agent import DOMAINS
    from tiedown_tools import TIEDOWN_CAPABILITIES
    registered = {t.name for t in DOMAINS["tiedown"]["tools"]}
    documented = {c["tool"] for c in TIEDOWN_CAPABILITIES}
    missing = registered - documented
    assert not missing, f"Tie-down tools missing from capability guide: {missing}"


MOBILITY_9 = sorted([
    "run_mobility_check", "get_vehicle_baseline", "evaluate_mass_change",
    "derive_cg_from_wheel_loads", "derive_zcg_from_tilt_tests",
    "slope_limit", "cornering_check", "flag_unstable", "lookup_knowledge",
])


def test_mobility_domain_wired():
    from agent import DOMAINS
    assert sorted(t.name for t in DOMAINS["mobility"]["tools"]) == MOBILITY_9


def test_every_mobility_tool_is_documented():
    """Every registered mobility tool must appear in the user-facing capability guide,
    so the guide can't silently fall out of sync with _MOBILITY_TOOLS."""
    from agent import DOMAINS
    from mobility_tools import MOBILITY_CAPABILITIES
    registered = {t.name for t in DOMAINS["mobility"]["tools"]}
    documented = {c["tool"] for c in MOBILITY_CAPABILITIES}
    missing = registered - documented
    assert not missing, f"Mobility tools missing from capability guide: {missing}"


def test_every_shock_tool_is_documented():
    """Every registered shock-mount tool must appear in the user-facing capability guide."""
    from agent import DOMAINS, SHOCK_CAPABILITIES
    registered = {t.name for t in DOMAINS["shock_mount"]["tools"]}
    documented = {c["tool"] for c in SHOCK_CAPABILITIES}
    missing = registered - documented
    assert not missing, f"Shock tools missing from capability guide: {missing}"


def test_ui_guide_domains_wired():
    """Each tab's UI-guide is a calculation-free RAG assistant: only lookup_knowledge,
    and its prompt enforces its own parent_topic scoping. Old 'ui_guide' name retired."""
    from agent import DOMAINS
    for domain in ("ui_guide_mobility", "ui_guide_shock", "ui_guide_tiedown"):
        cfg = DOMAINS[domain]
        names = [t.name for t in cfg["tools"]]
        assert names == ["lookup_knowledge"], domain    # RAG only — no engineering tools
        assert f'parent_topic="{domain}"' in cfg["prompt"], domain   # scoped retrieval
    assert "ui_guide" not in DOMAINS            # renamed to ui_guide_mobility


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
