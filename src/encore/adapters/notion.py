"""Notion adapter — stores notes as pages in a Notion database.

Config fields in ~/.encore/config.yaml:
  notion:
    enabled: true
    token: ntn_xxx         # Notion integration secret
    database_id: xxx        # ID of the target Notion database
"""

import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone

from .base import BaseAdapter
from ..config import load_config

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
def _get_notion_config() -> dict:
    config = load_config()
    return config.get("adapters", {}).get("notion", {})
class NotionAdapter(BaseAdapter):
    name = "notion"

    def __init__(self):
        cfg = _get_notion_config()
        self.token = cfg.get("token", "")
        self.database_id = cfg.get("database_id", "")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    def _api(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{NOTION_API}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in self._headers().items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            raise RuntimeError(f"Notion API {path} failed: {e.code} — {body}")

    # ---- BaseAdapter interface ----

    def save(self, note: dict) -> str:
        now = datetime.now(timezone.utc).isoformat()
        note.setdefault("created_at", now)

        properties = {
            "Title": {"title": [{"text": {"content": note.get("title", "")}}]},
            "Intent": {"select": {"name": note.get("intent", "")}},
            "Status": {"select": {"name": note.get("status", "resolved")}},
            "Tags": {"multi_select": [{"name": t} for t in note.get("tags", [])]},
            "Created At": {"date": {"start": note.get("created_at", now)}},
            "Source": {"select": {"name": note.get("source_environment", "claude_code")}},
        }
        if note.get("key_decision"):
            properties["Key Decision"] = {"rich_text": [{"text": {"content": note["key_decision"]}}]}
        if note.get("open_questions"):
            qs = "\n".join(f"- {q}" for q in note["open_questions"])
            properties["Open Questions"] = {"rich_text": [{"text": {"content": qs}}]}

        page = self._api("POST", "/pages", {
            "parent": {"database_id": self.database_id},
            "properties": properties,
        })
        page_id = page.get("id", "")

        # Append body blocks
        self._append_blocks(page_id, note)
        return page_id

    def list_notes(self, intent_filter: str | None = None) -> list[dict]:
        body = {"sorts": [{"property": "Created At", "direction": "descending"}]}
        if intent_filter:
            body["filter"] = {
                "property": "Intent",
                "select": {"equals": intent_filter},
            }

        result = self._api("POST", f"/databases/{self.database_id}/query", body)
        notes = []
        for page in result.get("results", []):
            meta = self._page_to_meta(page)
            if meta:
                notes.append(meta)
        return notes

    def search(self, keyword: str) -> list[dict]:
        body = {
            "sorts": [{"property": "Created At", "direction": "descending"}],
        }
        result = self._api("POST", f"/databases/{self.database_id}/query", body)
        results = []
        kw = keyword.lower()
        for page in result.get("results", []):
            meta = self._page_to_meta(page)
            if not meta:
                continue
            title = meta.get("title", "").lower()
            tags = " ".join(meta.get("tags", [])).lower()
            if kw in title or kw in tags:
                results.append(meta)
        return results

    def read_note(self, identifier: str) -> dict | None:
        try:
            page = self._api("GET", f"/pages/{identifier}")
            blocks = self._api("GET", f"/blocks/{identifier}/children")
        except Exception:
            return None

        props = page.get("properties", {})
        meta = {
            "_file": identifier,
            "title": _get_title(props.get("Title", {})),
            "intent": _get_select(props.get("Intent", {})),
            "status": _get_select(props.get("Status", {})),
            "tags": _get_multi_select(props.get("Tags", {})),
            "created_at": _get_date(props.get("Created At", {})),
            "key_decision": _get_rich_text(props.get("Key Decision", {})),
            "open_questions": _get_rich_text(props.get("Open Questions", {})),
        }
        body_text = _blocks_to_text(blocks.get("results", []))
        meta["_body"] = body_text

        # Extract context_digest from body
        m = re.search(r"(?:AI 上下文摘要|context_digest|Context)[^\n]*\n\n(.+)", body_text, re.DOTALL)
        if m:
            meta["context_digest"] = m.group(1).strip()
        elif "context_digest" not in meta:
            meta["context_digest"] = ""

        return meta

    def delete(self, identifier: str) -> bool:
        try:
            # Archive the page
            self._api("PATCH", f"/pages/{identifier}", {
                "archived": True,
            })
            return True
        except Exception:
            return False

    # ---- internal helpers ----

    def _append_blocks(self, page_id: str, note: dict) -> None:
        blocks = _note_to_blocks(note)
        if not blocks:
            return
        # Split into chunks (Notion limit: 100 blocks per request)
        for i in range(0, len(blocks), 100):
            chunk = blocks[i : i + 100]
            self._api("PATCH", f"/blocks/{page_id}/children", {"children": chunk})

    def _page_to_meta(self, page: dict) -> dict | None:
        props = page.get("properties", {})
        return {
            "title": _get_title(props.get("Title", {})),
            "intent": _get_select(props.get("Intent", {})),
            "created_at": _get_date(props.get("Created At", {})),
            "tags": _get_multi_select(props.get("Tags", {})),
            "_file": page.get("id", ""),
        }
# ---- property extractors ----

def _get_title(prop: dict) -> str:
    results = prop.get("title", [])
    if results:
        return results[0].get("plain_text", "")
    return ""
def _get_select(prop: dict) -> str:
    sel = prop.get("select")
    if sel:
        return sel.get("name", "")
    return ""
def _get_multi_select(prop: dict) -> list[str]:
    return [s.get("name", "") for s in prop.get("multi_select", [])]
def _get_date(prop: dict) -> str:
    d = prop.get("date")
    if d:
        return d.get("start", "")
    return ""
def _get_rich_text(prop: dict) -> str:
    results = prop.get("rich_text", [])
    return results[0].get("plain_text", "") if results else ""
# ---- Notion blocks conversion ----

def _note_to_blocks(note: dict) -> list[dict]:
    blocks = []
    intent = note.get("intent", "")
    payload = note.get("payload", {})

    # Heading
    blocks.append({
        "object": "block",
        "type": "heading_1",
        "heading_1": {"rich_text": [{"type": "text", "text": {"content": note.get("title", "")}}]},
    })

    # Payload body
    body_text = _payload_to_text(intent, payload)
    if body_text:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": body_text[:2000]}}]},
        })

    # Context digest
    if note.get("context_digest"):
        blocks.append({
            "object": "block",
            "type": "divider",
            "divider": {},
        })
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Context (for AI)"}}]},
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": note["context_digest"][:2000]}}]},
        })

    return blocks
def _payload_to_text(intent: str, payload: dict) -> str:
    lines = []
    if intent == "bug_fix":
        if payload.get("symptom"):
            lines.append(f"Symptom: {payload['symptom']}")
        if payload.get("root_cause"):
            lines.append(f"Root Cause: {payload['root_cause']}")
        failed = payload.get("failed_attempts", [])
        if failed:
            lines.append("Failed Attempts:")
            for a in failed:
                lines.append(f"  - {a}")
        if payload.get("solution_summary"):
            lines.append(f"Solution: {payload['solution_summary']}")
        if payload.get("solution_code"):
            lines.append(f"```\n{payload['solution_code']}\n```")
    elif intent == "learning":
        if payload.get("core_concept"):
            lines.append(f"Core Concept: {payload['core_concept']}")
        if payload.get("feynman_summary"):
            lines.append(f"TL;DR: {payload['feynman_summary']}")
        if payload.get("detailed_explanation"):
            lines.append(payload["detailed_explanation"])
        related = payload.get("related_concepts", [])
        if related:
            lines.append("Related: " + ", ".join(related))
    elif intent == "idea":
        if payload.get("core_idea"):
            lines.append(f"Core Idea: {payload['core_idea']}")
        pc = payload.get("pros_cons", {})
        if pc.get("pros"):
            lines.append("Pros:\n" + "\n".join(f"- {p}" for p in pc["pros"]))
        if pc.get("cons"):
            lines.append("Cons:\n" + "\n".join(f"- {c}" for c in pc["cons"]))
    return "\n".join(lines)
def _blocks_to_text(blocks: list[dict]) -> str:
    texts = []
    for b in blocks:
        btype = b.get("type", "")
        content = b.get(btype, {})
        rich = content.get("rich_text", [])
        for r in rich:
            t = r.get("plain_text", "")
            if t:
                texts.append(t)
    return "\n".join(texts)
