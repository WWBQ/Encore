"""Tests for local Markdown adapter."""

import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from encore.adapters.local import LocalAdapter


def test_slugify():
    assert LocalAdapter._slugify("Hello World") == "Hello-World"
    assert LocalAdapter._slugify("飞书测试") == "飞书测试"
    assert LocalAdapter._slugify("a" * 100) == ("a" * 80)
    assert LocalAdapter._slugify("!!!special###") == "special"


def test_save_and_read():
    with tempfile.TemporaryDirectory() as d:
        ad = LocalAdapter(Path(d))
        note = {
            "title": "Test Note",
            "intent": "bug_fix",
            "status": "resolved",
            "tags": ["test", "adapter"],
            "context_digest": "test context",
            "payload": {
                "symptom": "Broken",
                "root_cause": "Bug",
                "solution_summary": "Fixed",
            },
        }
        path = ad.save(note)
        assert path.endswith(".md")

        read = ad.read_note(Path(path).name)
        assert read is not None
        assert read["title"] == "Test Note"
        assert read["intent"] == "bug_fix"
        assert read["status"] == "resolved"
        assert read["tags"] == ["test", "adapter"]
        assert "test context" in read.get("context_digest", "")


def test_list_notes():
    with tempfile.TemporaryDirectory() as d:
        ad = LocalAdapter(Path(d))
        ad.save({"title": "A", "intent": "learning", "payload": {}, "tags": []})
        ad.save({"title": "B", "intent": "bug_fix", "payload": {}, "tags": []})

        all_notes = ad.list_notes()
        assert len(all_notes) == 2

        filtered = ad.list_notes("learning")
        assert len(filtered) == 1
        assert filtered[0]["title"] == "A"


def test_search():
    with tempfile.TemporaryDirectory() as d:
        ad = LocalAdapter(Path(d))
        ad.save({"title": "飞书bug修复", "intent": "bug_fix", "payload": {}, "tags": ["feishu", "oauth"]})
        ad.save({"title": "学习笔记", "intent": "learning", "payload": {}, "tags": ["learning"]})

        results = ad.search("飞书")
        assert len(results) == 1
        assert results[0]["title"] == "飞书bug修复"

        results = ad.search("oauth")
        assert len(results) == 1

        results = ad.search("nonexistent")
        assert len(results) == 0


def test_delete():
    with tempfile.TemporaryDirectory() as d:
        ad = LocalAdapter(Path(d))
        path = ad.save({"title": "X", "intent": "learning", "payload": {}, "tags": []})
        name = Path(path).name
        assert ad.delete(name)
        assert ad.read_note(name) is None
        assert not ad.delete("nonexistent.md")
