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
