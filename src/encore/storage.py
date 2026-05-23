"""Multi-adapter storage — dispatches across all enabled backends."""

from .config import load_config, get_enabled_adapters
from .adapters.base import BaseAdapter
from .adapters.local import LocalAdapter
from .adapters.feishu import FeishuAdapter
from .adapters.github import GitHubAdapter
from .adapters.notion import NotionAdapter

ADAPTER_CLASSES = {
    "local": LocalAdapter,
    "feishu": FeishuAdapter,
    "github": GitHubAdapter,
    "notion": NotionAdapter,
}


def _init_adapters() -> list[BaseAdapter]:
    config = load_config()
    enabled = get_enabled_adapters(config)
    adapters = []
    for name, cfg in enabled.items():
        cls = ADAPTER_CLASSES.get(name)
        if cls:
            adapters.append(cls())
    return adapters


def save(note: dict) -> str:
    results = []
    for ad in _init_adapters():
        results.append(ad.save(note))
    return results[0] if results else ""


def list_notes(intent_filter: str = None) -> list[dict]:
    seen = set()
    notes = []
    for ad in _init_adapters():
        for n in ad.list_notes(intent_filter):
            key = n.get("title", "")
            if key not in seen:
                seen.add(key)
                notes.append(n)
    notes.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return notes


def search(keyword: str) -> list[dict]:
    seen = set()
    results = []
    for ad in _init_adapters():
        for n in ad.search(keyword):
            key = n.get("title", "")
            if key not in seen:
                seen.add(key)
                results.append(n)
    return results


def read_note(identifier: str) -> dict | None:
    for ad in _init_adapters():
        note = ad.read_note(identifier)
        if note:
            return note
    return None


def delete(identifier: str) -> bool:
    success = False
    for ad in _init_adapters():
        if ad.delete(identifier):
            success = True
    return success
