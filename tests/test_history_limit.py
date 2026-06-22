"""Offline tests for the engineering-assistant chat-history cap.
Run: .\\mpd\\Scripts\\python.exe -m pytest tests/test_history_limit.py

No LLM / API key: we exercise the pure _limit_history helper and verify that
DomainAgent.stream() applies it (via a monkeypatched _drive that captures the
messages it would have sent to the model).
"""
from agent import _limit_history, _MAX_HISTORY_TURNS, DomainAgent


def _make_history(n: int) -> list:
    """n alternating (human, ai) messages, starting with human."""
    return [("human" if i % 2 == 0 else "ai", f"m{i}") for i in range(n)]


class TestLimitHistoryPure:
    def test_none_passes_through(self):
        assert _limit_history(None) is None

    def test_empty_passes_through(self):
        assert _limit_history([]) == []

    def test_short_unchanged(self):
        h = _make_history(4)            # 2 turns, under the cap
        assert _limit_history(h) == h

    def test_long_keeps_last_three_turns(self):
        h = _make_history(10)           # 5 turns
        out = _limit_history(h)
        assert len(out) == 2 * _MAX_HISTORY_TURNS      # 6 messages
        assert out == h[-6:]                            # the LAST 6, in order
        assert out[0][0] == "human"                     # still starts on a user turn


class _Capture:
    """Stand-in DomainAgent whose _drive records the messages it receives."""
    def __init__(self, domain: str):
        self._domain = domain
        self.seen_messages = None

    def _drive(self, messages, seen_tool_call_ids):
        self.seen_messages = list(messages)
        yield {"type": "_final", "content": "ok"}

    # Borrow the real stream() implementation unchanged.
    stream = DomainAgent.stream


class TestStreamAppliesCap:
    def test_stateful_domain_capped(self):
        # "mobility" is stateful but NOT in _ENFORCE_TOOLUSE_DOMAINS, so the
        # tool-use retry path never fires and seen_messages reflects the first call.
        agent = _Capture("mobility")
        long_hist = _make_history(10)
        list(agent.stream("current q", chat_history=long_hist))
        assert agent.seen_messages == long_hist[-6:] + [("human", "current q")]

    def test_stateless_domain_drops_history(self):
        agent = _Capture("ui_guide_shock")
        list(agent.stream("current q", chat_history=_make_history(10)))
        assert agent.seen_messages == [("human", "current q")]


def _run():
    import sys
    fns = []
    for cls_name, cls in sorted(globals().items()):
        if isinstance(cls, type) and cls_name.startswith("Test"):
            inst = cls.__new__(cls)
            for m in sorted(dir(cls)):
                if m.startswith("test_"):
                    fns.append((f"{cls_name}.{m}", getattr(inst, m)))
    failed = 0
    for name, fn in fns:
        try:
            fn(); print(f"[PASS] {name}")
        except AssertionError as e:
            failed += 1; print(f"[FAIL] {name}: {e}")
        except Exception as e:
            failed += 1; print(f"[ERROR] {name}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _run()
