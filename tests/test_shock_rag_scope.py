from pathlib import Path

from setup_knowledge import collect_chunks


def test_shock_topic_filter_collects_only_shock_chunks(tmp_path: Path):
    (tmp_path / "shock_mount").mkdir()
    (tmp_path / "mobility").mkdir()
    (tmp_path / "shock_mount" / "basis.md").write_text("# Shock basis", encoding="utf-8")
    (tmp_path / "mobility" / "guide.md").write_text("# Mobility guide", encoding="utf-8")

    chunks = collect_chunks(tmp_path, topic="shock_mount")

    assert [chunk["id"] for chunk in chunks] == ["shock_mount/basis"]
    assert chunks[0]["title"] == "Shock basis"
