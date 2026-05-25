"""Tests for schema validation."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from encore.schema import validate


def _base_note(**overrides):
    note = {
        "encore_version": "0.1",
        "intent": "bug_fix",
        "title": "Test",
        "context_digest": "test",
        "created_at": "2026-01-01T00:00:00Z",
        "payload": {
            "symptom": "s",
            "root_cause": "r",
            "solution_summary": "ss",
        },
    }
    note.update(overrides)
    return note


def test_valid_bug_fix():
    assert validate(_base_note()) == []


def test_missing_required():
    errs = validate({"title": "x"})
    assert any("encore_version" in e for e in errs)
    assert any("intent" in e for e in errs)


def test_invalid_intent():
    errs = validate(_base_note(intent="bogus"))
    assert any("无效意图" in e for e in errs)


def test_invalid_status():
    errs = validate(_base_note(status="bogus"))
    assert any("无效状态" in e for e in errs)


def test_payload_missing_required():
    errs = validate(_base_note(payload={"symptom": "s"}))
    assert any("root_cause" in e for e in errs)
    assert any("solution_summary" in e for e in errs)


def test_payload_unknown_field():
    errs = validate(_base_note(payload={
        "symptom": "s", "root_cause": "r", "solution_summary": "ss", "bogus": "x",
    }))
    assert any("bogus" in e for e in errs)


def test_valid_learning():
    note = _base_note(
        intent="learning",
        payload={"core_concept": "c", "feynman_summary": "f"},
    )
    assert validate(note) == []


def test_learning_missing_field():
    note = _base_note(
        intent="learning",
        payload={"core_concept": "c"},
    )
    errs = validate(note)
    assert any("feynman_summary" in e for e in errs)


def test_validation_passes_without_payload():
    note = _base_note()
    del note["payload"]
    assert validate(note) == []
