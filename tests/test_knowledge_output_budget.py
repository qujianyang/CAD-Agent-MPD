import agent


def test_knowledge_excerpt_is_capped_without_affecting_short_content(monkeypatch):
    monkeypatch.setattr(agent, "KNOWLEDGE_MAX_CHARS_PER_HIT", 20)

    assert agent._truncate_knowledge_content("short") == "short"
    excerpt = agent._truncate_knowledge_content("x" * 50)
    assert excerpt.startswith("x" * 20)
    assert "Excerpt truncated" in excerpt
