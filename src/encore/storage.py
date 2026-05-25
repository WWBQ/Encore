"""Multi-adapter storage — dispatches across all enabled backends."""

import json
import urllib.request
from pathlib import Path

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

FEISHU_HOST = "https://open.feishu.cn"


def _init_adapters() -> list[BaseAdapter]:
    config = load_config()
    enabled = get_enabled_adapters(config)
    adapters = []
    for name, cfg in enabled.items():
        cls = ADAPTER_CLASSES.get(name)
        if cls:
            adapters.append(cls())
    return adapters


def _index_to_bitable(note: dict, feishu_cfg: dict, feishu_url: str, local_file: str) -> None:
    app_token = feishu_cfg.get("index_table_token", "")
    table_id = feishu_cfg.get("index_table_id", "")
    if not app_token or not table_id:
        return

    try:
        from .adapters.feishu import FeishuAdapter
        ad = FeishuAdapter()
        token = ad._get_token()

        record = {"fields": {
            "标题": note.get("title", "")[:100],
            "意图": note.get("intent", ""),
            "标签": ", ".join(note.get("tags", [])),
            "创建时间": note.get("created_at", ""),
            "本地文件": local_file or "",
            "飞书文档": feishu_url or "",
            "原始JSON": json.dumps(note, ensure_ascii=False),
        }}

        body = json.dumps({"records": [record]}).encode()
        url = f"{FEISHU_HOST}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=30)
    except Exception:
        pass


def save(note: dict) -> dict[str, str | None]:
    results = {}
    for ad in _init_adapters():
        try:
            results[ad.name] = ad.save(note)
        except Exception:
            results[ad.name] = None

    config = load_config()
    feishu_cfg = config.get("adapters", {}).get("feishu", {})
    feishu_url = results.get("feishu", "")
    local_file = results.get("local", "")
    _index_to_bitable(note, feishu_cfg, feishu_url, local_file)

    return results


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
