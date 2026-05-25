"""GitHub adapter — stores notes as Markdown files in a GitHub repository.

Config fields in ~/.encore/config.yaml:
  github:
    enabled: true
    token: ghp_xxx          # GitHub personal access token
    repo: owner/repo-name   # e.g. "wwbq/encore-notes"
    path: notes             # optional — subdirectory in the repo (default: "")
"""

import base64
import json
import re
import urllib.request
import urllib.error
from datetime import datetime

from .base import BaseAdapter
from ..config import load_config
from .local import _build_body, LocalAdapter
def _get_github_config() -> dict:
    config = load_config()
    return config.get("adapters", {}).get("github", {})
class GitHubAdapter(BaseAdapter):
    name = "github"

    def __init__(self):
        cfg = _get_github_config()
        self.token = cfg.get("token", "")
        self.repo = cfg.get("repo", "")
        self.path_prefix = cfg.get("path", "").strip("/")
        self._slugify = LocalAdapter._slugify

    # ---- API helpers ----

    @property
    def _api_base(self):
        return f"https://api.github.com/repos/{self.repo}/contents"

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _api(self, method: str, path: str = "", body: dict | None = None) -> tuple[int, dict]:
        if self.path_prefix:
            url = f"{self._api_base}/{self.path_prefix}/{path}".rstrip("/")
        elif path:
            url = f"{self._api_base}/{path}"
        else:
            url = f"{self._api_base}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in self._headers().items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            return 200, result
        except urllib.error.HTTPError as e:
            body_str = e.read().decode(errors="replace")
            return e.code, json.loads(body_str) if body_str else {}

    # ---- BaseAdapter interface ----

    def save(self, note: dict) -> str:
        title = note.get("title", "untitled")
        ts = note.get("created_at", datetime.now().astimezone().isoformat())
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            dt = datetime.now()
        timestamp = dt.strftime("%Y-%m-%d-%H%M%S")
        filename = f"{timestamp}--{self._slugify(title)}.md"

        # Build the same Markdown content as local adapter
        frontmatter = {
            "title": note.get("title", ""),
            "intent": note.get("intent", ""),
            "status": note.get("status", "resolved"),
            "tags": note.get("tags", []),
            "created_at": note.get("created_at", dt.isoformat()),
            "source": note.get("source_environment", "claude_code"),
        }
        if note.get("key_decision"):
            frontmatter["key_decision"] = note["key_decision"]
        if note.get("open_questions"):
            frontmatter["open_questions"] = note["open_questions"]
        if note.get("context_digest"):
            frontmatter["context_digest"] = note["context_digest"]

        import yaml
        body = _build_body(note)
        markdown = "---\n"
        markdown += yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)
        markdown += "---\n\n"
        markdown += body

        encoded = base64.b64encode(markdown.encode("utf-8")).decode("ascii")

        # Check if file exists to get sha for update
        sha = self._get_sha(filename)

        payload = {
            "message": f"encore: {title}",
            "content": encoded,
        }
        if sha:
            payload["sha"] = sha

        status, result = self._api("PUT", filename, payload)
        if status in (200, 201):
            return filename
        raise RuntimeError(f"GitHub save failed: {status} {result.get('message', '')}")

    def list_notes(self, intent_filter: str | None = None) -> list[dict]:
        status, data = self._api("GET", "")
        if status != 200:
            return []
        if isinstance(data, dict):
            # Single file, not a directory
            return []
        notes = []
        for item in data or []:
            if item.get("type") != "file" or not item["name"].endswith(".md"):
                continue
            meta = self._parse_filename(item["name"])
            if not meta:
                continue
            if intent_filter and meta.get("intent", "") != intent_filter:
                continue
            notes.append(meta)
        notes.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return notes

    def search(self, keyword: str) -> list[dict]:
        status, data = self._api("GET", "")
        if status != 200 or isinstance(data, dict):
            return []
        results = []
        kw = keyword.lower()
        for item in data or []:
            if item.get("type") != "file" or not item["name"].endswith(".md"):
                continue
            meta = self._parse_filename(item["name"])
            if not meta:
                continue
            title = meta.get("title", "").lower()
            if kw in title:
                results.append(meta)
                continue
            full = self.read_note(item["name"])
            if full:
                full_title = full.get("title", "").lower()
                full_tags = " ".join(full.get("tags", [])).lower()
                if kw in full_title or kw in full_tags:
                    meta["tags"] = full.get("tags", [])
                    meta["intent"] = full.get("intent", "")
                    results.append(meta)
        return results

    def read_note(self, identifier: str) -> dict | None:
        status, data = self._api("GET", identifier)
        if status != 200:
            return None
        content_b64 = data.get("content", "")
        try:
            content = base64.b64decode(content_b64).decode("utf-8")
        except Exception:
            return None

        import yaml
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        meta = yaml.safe_load(parts[1])
        body = parts[2].strip()
        meta["_file"] = identifier
        meta["_body"] = body
        if "context_digest" not in meta:
            m = re.search(r"(?:AI 上下文摘要|context_digest)[^\n]*\n\n(.+)", body, re.DOTALL)
            if m:
                meta["context_digest"] = m.group(1).strip()
        return meta

    def delete(self, identifier: str) -> bool:
        sha = self._get_sha(identifier)
        if not sha:
            return False
        status, result = self._api("DELETE", identifier, {
            "message": f"encore: delete {identifier}",
            "sha": sha,
        })
        return status in (200, 204)

    # ---- internal helpers ----

    def _get_sha(self, filename: str) -> str | None:
        status, data = self._api("GET", filename)
        if status == 200:
            return data.get("sha")
        return None

    @staticmethod
    def _parse_filename(filename: str) -> dict | None:
        m = re.match(r"(\d{4}-\d{2}-\d{2}-\d{6})--(.+)\.md$", filename)
        if not m:
            return None
        title = m.group(2).replace("-", " ")
        return {
            "title": title,
            "intent": "",
            "created_at": m.group(1),
            "tags": [],
            "_file": filename,
        }
