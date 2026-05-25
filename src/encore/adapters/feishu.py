"""Feishu (Lark) Docx adapter — stores notes in user's personal Feishu Drive.

Requires OAuth authorization: run `encore auth` first.
Config fields in ~/.encore/config.yaml:
  feishu:
    enabled: true
    app_id: cli_xxx
    app_secret: xxx
    folder_token: xxx
    domain: xxx
"""

import json
import re
import secrets
import ssl
import time
import urllib.request
import urllib.error
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from .base import BaseAdapter
from ..config import load_config

FEISHU_HOST = "https://open.feishu.cn"
APP_TOKEN_CACHE_FILE = Path.home() / ".encore" / ".feishu_app_token"
USER_TOKEN_CACHE_FILE = Path.home() / ".encore" / ".feishu_user_token"


def _get_feishu_config() -> dict:
    config = load_config()
    return config.get("adapters", {}).get("feishu", {})


class FeishuAdapter(BaseAdapter):
    name = "feishu"

    def __init__(self):
        cfg = _get_feishu_config()
        self.app_id = cfg.get("app_id", "")
        self.app_secret = cfg.get("app_secret", "")
        self.folder_token = cfg.get("folder_token", "")
        self.domain = cfg.get("domain", "")
        self._app_token = None
        self._user_token = None

    def _get_token(self) -> str:
        if self._user_token:
            return self._user_token
        cached = _read_user_token_cache()
        if not cached:
            raise RuntimeError(
                "飞书未授权，请先运行 encore auth 完成 OAuth 授权"
            )
        if cached.get("expire_at", 0) > time.time():
            self._user_token = cached["user_access_token"]
            return self._user_token
        try:
            self._refresh_user_token(cached.get("refresh_token", ""))
            return self._user_token
        except Exception:
            _clear_user_token_cache()
            raise RuntimeError(
                "飞书 token 已过期且刷新失败，请重新运行 encore auth"
            )

    def _get_app_token(self) -> str:
        if self._app_token:
            return self._app_token
        cached = _read_app_token_cache()
        if cached and cached.get("token") and cached.get("expire_at", 0) > time.time():
            self._app_token = cached["token"]
            return self._app_token
        self._app_token = self._fetch_app_token()
        return self._app_token

    def _fetch_app_token(self) -> str:
        url = f"{FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal"
        body = json.dumps({"app_id": self.app_id, "app_secret": self.app_secret}).encode()
        data = _request_with_retry(url, data=body, method="POST")
        token = data.get("tenant_access_token", "")
        if not token:
            raise RuntimeError("Failed to get tenant_access_token")
        expire = data.get("expire", 7200)
        _write_app_token_cache(token, time.time() + expire - 300)
        return token

    def _refresh_user_token(self, refresh_token: str) -> None:
        data = self._api_app("POST", "/open-apis/authen/v1/oidc/refresh_token", {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        })
        self._user_token = data.get("access_token", "")
        new_refresh_token = data.get("refresh_token", refresh_token)
        _write_user_token_cache(
            self._user_token,
            new_refresh_token,
            time.time() + data.get("expires_in", 7200) - 300,
        )

    def _api(self, method: str, path: str, body: dict | None = None) -> dict:
        token = self._get_token()
        url = f"{FEISHU_HOST}{path}"
        data = json.dumps(body).encode() if body else None
        return _request_with_retry(url, data=data, method=method, token=token)

    def _api_app(self, method: str, path: str, body: dict | None = None) -> dict:
        token = self._get_app_token()
        url = f"{FEISHU_HOST}{path}"
        data = json.dumps(body).encode() if body else None
        return _request_with_retry(url, data=data, method=method, token=token)

    def start_oauth(self, port: int = 8888) -> dict:
        state = secrets.token_urlsafe(32)
        redirect_uri = f"http://localhost:{port}/callback"
        scope = "docx:document drive:drive bitable:app"
        auth_url = (
            f"{FEISHU_HOST}/open-apis/authen/v1/authorize"
            f"?app_id={self.app_id}"
            f"&redirect_uri={urllib.parse.quote(redirect_uri, safe=':/')}"
            f"&scope={urllib.parse.quote(scope, safe='')}"
            f"&state={state}"
        )

        result_holder = {"code": None, "error": None, "state": state}
        server = _start_callback_server(port, result_holder)

        print("Opening browser for Feishu authorization...")
        print(f"If the browser doesn't open, visit:\n  {auth_url}")
        webbrowser.open(auth_url)

        server.timeout = 120
        deadline = time.time() + 120
        code = None
        while time.time() < deadline:
            server.handle_request()
            if result_holder["code"]:
                try:
                    result = self._exchange_code(result_holder["code"])
                    server.server_close()
                    return result
                except Exception:
                    result_holder["code"] = None
                    continue
            if result_holder["error"]:
                server.server_close()
                raise RuntimeError(f"OAuth failed: {result_holder['error']}")

        server.server_close()
        raise RuntimeError("OAuth timeout: no authorization code received")

    def _exchange_code(self, code: str) -> dict:
        data = self._api_app("POST", "/open-apis/authen/v1/oidc/access_token", {
            "grant_type": "authorization_code",
            "code": code,
        })
        access_token = data.get("access_token", "")
        refresh_token = data.get("refresh_token", "")
        expires_in = data.get("expires_in", 7200)
        _write_user_token_cache(access_token, refresh_token, time.time() + expires_in - 300)

        self._user_token = access_token
        return data

    def save(self, note: dict) -> str:
        title = note.get("title", "Untitled")
        body = {"title": title}
        if self.folder_token:
            body["folder_token"] = self.folder_token

        data = self._api("POST", "/open-apis/docx/v1/documents", body)
        doc = data.get("document", {})
        doc_id = doc.get("document_id", "")

        try:
            self._write_content(doc_id, note)
        except Exception:
            try:
                self._api("DELETE", f"/open-apis/drive/v1/files/{doc_id}?type=docx")
            except Exception:
                pass
            raise

        if self.domain:
            return f"https://{self.domain}.feishu.cn/docx/{doc_id}"
        return doc_id

    def list_notes(self, intent_filter: str | None = None) -> list[dict]:
        return self._search_files("", intent_filter)

    def search(self, keyword: str) -> list[dict]:
        return self._search_files(keyword)

    def read_note(self, identifier: str) -> dict | None:
        try:
            blocks = self._api("GET", f"/open-apis/docx/v1/documents/{identifier}/blocks")
            body_text = _blocks_to_text(blocks.get("items", []))
            return _parse_body(identifier, body_text)
        except Exception:
            return None

    def delete(self, identifier: str) -> bool:
        try:
            self._api("DELETE", f"/open-apis/drive/v1/files/{identifier}?type=docx")
            return True
        except Exception:
            return False

    def _write_content(self, doc_id: str, note: dict) -> None:
        children = _note_to_blocks(note)
        self._api("POST", f"/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children", {
            "children": children,
        })

    def _search_files(self, keyword: str, intent_filter: str | None = None) -> list[dict]:
        try:
            notes = []
            page_token = None
            while True:
                path = "/open-apis/drive/v1/files?page_size=50"
                if page_token:
                    path += f"&page_token={page_token}"
                data = self._api("GET", path)
                for f in data.get("files", []):
                    if f.get("type") != "docx":
                        continue
                    name = f.get("name", "")
                    if keyword and keyword.lower() not in name.lower():
                        continue
                    meta = {
                        "title": name,
                        "intent": "",
                        "created_at": f.get("created_time", ""),
                        "tags": [],
                        "_file": f.get("token", ""),
                    }
                    if intent_filter and meta.get("intent") != intent_filter:
                        continue
                    notes.append(meta)
                if not data.get("has_more"):
                    break
                page_token = data.get("page_token", "")
                if not page_token:
                    break

            self._enrich_metadata(notes, intent_filter)
            return notes
        except Exception:
            return []

    def _enrich_metadata(self, notes: list[dict], intent_filter: str | None) -> None:
        for note in notes:
            try:
                blocks = self._api(
                    "GET",
                    f"/open-apis/docx/v1/documents/{note['_file']}/blocks?page_size=5",
                )
                body_text = _blocks_to_text(blocks.get("items", []))
                parsed = _parse_body(note["_file"], body_text)
                note["intent"] = parsed.get("intent", "")
                note["tags"] = parsed.get("tags", [])
                if intent_filter and note["intent"] != intent_filter:
                    note["_skip"] = True
            except Exception:
                pass

        for note in notes[:]:
            if note.pop("_skip", False):
                notes.remove(note)


def _note_to_blocks(note: dict) -> list[dict]:
    blocks = []
    blocks.append({
        "block_type": 3,
        "heading1": {"elements": [{"text_run": {"content": note.get("title", "")}}]},
    })

    intent = note.get("intent", "")
    status = note.get("status", "")
    tags = ", ".join(note.get("tags", []))
    blocks.append({
        "block_type": 2,
        "text": {"elements": _lines_to_elements([
            f"意图: {_intent_label(intent)}",
            f"状态: {status}",
            f"标签: {tags}",
            f"创建时间: {note.get('created_at', '')}",
        ])},
    })

    if note.get("key_decision"):
        blocks.append({
            "block_type": 2,
            "text": {"elements": _lines_to_elements([
                "核心决策",
                note["key_decision"],
            ])},
        })

    payload = note.get("payload", {})
    body_text = _payload_to_text(intent, payload)
    if body_text:
        for paragraph in body_text.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            blocks.append({
                "block_type": 2,
                "text": {"elements": _lines_to_elements(paragraph.split("\n"))},
            })

    if note.get("context_digest"):
        blocks.append({"block_type": 22, "divider": {}})
        blocks.append({
            "block_type": 4,
            "heading2": {"elements": [{"text_run": {"content": "AI 上下文摘要"}}]},
        })
        for paragraph in note["context_digest"].split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            blocks.append({
                "block_type": 2,
                "text": {"elements": _lines_to_elements(paragraph.split("\n"))},
            })

    if note.get("open_questions"):
        blocks.append({"block_type": 22, "divider": {}})
        blocks.append({
            "block_type": 4,
            "heading2": {"elements": [{"text_run": {"content": "遗留问题"}}]},
        })
        for q in note["open_questions"]:
            blocks.append({
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": f"- {q}"}}]},
            })

    return blocks


def _lines_to_elements(lines: list[str]) -> list[dict]:
    non_empty = [l for l in lines if l]
    elements = []
    for i, line in enumerate(non_empty):
        if i > 0:
            elements.append({"text_run": {"content": "\n"}})
        elements.append({"text_run": {"content": line}})
    return elements


def _intent_label(intent: str) -> str:
    return {"bug_fix": "排错", "learning": "学习", "idea": "灵感"}.get(intent, intent)


def _payload_to_text(intent: str, payload: dict) -> str:
    lines = []
    if intent == "bug_fix":
        if payload.get("symptom"):
            lines.append("")
            lines.append("【症状】")
            lines.append(payload["symptom"])
        if payload.get("root_cause"):
            lines.append("")
            lines.append("【根因】")
            lines.append(payload["root_cause"])
        failed = payload.get("failed_attempts", [])
        if failed:
            lines.append("")
            lines.append("【失败的尝试】")
            for a in failed:
                lines.append(f"  - {a}")
        if payload.get("solution_summary"):
            lines.append("")
            lines.append("【解决方案】")
            lines.append(payload["solution_summary"])
        if payload.get("solution_code"):
            lines.append("")
            lines.append("【最终代码】")
            lines.append(payload["solution_code"])
        actions = payload.get("action_items", [])
        if actions:
            lines.append("")
            lines.append("【后续行动】")
            for a in actions:
                lines.append(f"  - [ ] {a}")
    elif intent == "learning":
        if payload.get("core_concept"):
            lines.append("")
            lines.append("【核心概念】")
            lines.append(payload["core_concept"])
        if payload.get("feynman_summary"):
            lines.append("")
            lines.append("【一句话理解】")
            lines.append(payload["feynman_summary"])
        if payload.get("detailed_explanation"):
            lines.append("")
            lines.append("【详细解释】")
            lines.append(payload["detailed_explanation"])
        related = payload.get("related_concepts", [])
        if related:
            lines.append("")
            lines.append("【关联概念】")
            for c in related:
                lines.append(f"  - {c}")
        refs = payload.get("references", [])
        if refs:
            lines.append("")
            lines.append("【拓展阅读】")
            for r in refs:
                lines.append(f"  - {r}")
    elif intent == "idea":
        if payload.get("core_idea"):
            lines.append("")
            lines.append("【核心创意】")
            lines.append(payload["core_idea"])
        pc = payload.get("pros_cons", {})
        if pc.get("pros"):
            lines.append("")
            lines.append("【优势】")
            for p in pc["pros"]:
                lines.append(f"  - {p}")
        if pc.get("cons"):
            lines.append("")
            lines.append("【劣势 / 风险】")
            for c in pc["cons"]:
                lines.append(f"  - {c}")
        steps = payload.get("action_steps", [])
        if steps:
            lines.append("")
            lines.append("【落地步骤】")
            for s in steps:
                lines.append(f"  - [ ] {s}")
    return "\n".join(lines)


def _blocks_to_text(items: list[dict]) -> str:
    texts = []
    for b in items:
        for key in ("heading1", "heading2", "text"):
            if key in b:
                for e in b[key].get("elements", []):
                    t = e.get("text_run", {}).get("content", "")
                    if t:
                        texts.append(t)
                break
    return "\n".join(texts)


def _parse_body(doc_id: str, body: str) -> dict:
    raw_json = _extract_raw_json(body)
    if raw_json:
        raw_json["_file"] = doc_id
        raw_json["_body"] = body
        return raw_json

    meta = {"_file": doc_id, "_body": body, "title": "", "intent": "", "tags": []}
    lines = body.split("\n")
    if lines:
        meta["title"] = lines[0].strip()
    for line in lines:
        line = line.strip()
        if line.startswith("Intent:"):
            try:
                meta["intent"] = line.split(":", 1)[1].split("|")[0].strip()
            except Exception:
                pass
        elif line.startswith("Tags:"):
            try:
                meta["tags"] = [t.strip() for t in line.split(":", 1)[1].split(",") if t.strip()]
            except Exception:
                pass
    m = re.search(r"Context \(for AI\)[^\n]*\n+(.+)", body, re.DOTALL)
    if m:
        meta["context_digest"] = m.group(1).strip()
    return meta


def _extract_raw_json(body: str) -> dict | None:
    lines = [l for l in body.split("\n") if l.strip()]
    if not lines:
        return None
    last = lines[-1].strip()
    if last.startswith("{") and last.endswith("}"):
        try:
            return json.loads(last)
        except json.JSONDecodeError:
            pass
    return None


def _ssl_context():
    cfg = _get_feishu_config()
    verify = cfg.get("verify_ssl", True)
    if isinstance(verify, str):
        verify = verify.lower() not in ("false", "0", "no", "off")
    if not verify:
        return ssl._create_unverified_context()
    return None


def _request_with_retry(url: str, data: bytes | None = None,
                        method: str = "GET", token: str = "") -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(2):
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
                result = json.loads(resp.read())
            if result.get("code") != 0:
                raise RuntimeError(f"Feishu API error: {result.get('code')} {result.get('msg')}")
            return result.get("data") or {k: v for k, v in result.items() if k not in ("code", "msg")}
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, OSError) as e:
            if attempt == 1:
                raise RuntimeError(f"Feishu API request failed: {e}")


def _read_app_token_cache() -> dict | None:
    try:
        with open(APP_TOKEN_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _write_app_token_cache(token: str, expire_at: float) -> None:
    APP_TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(APP_TOKEN_CACHE_FILE, "w") as f:
        json.dump({"token": token, "expire_at": expire_at}, f)
    APP_TOKEN_CACHE_FILE.chmod(0o600)


def _read_user_token_cache() -> dict | None:
    try:
        with open(USER_TOKEN_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _write_user_token_cache(access_token: str, refresh_token: str, expire_at: float) -> None:
    USER_TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USER_TOKEN_CACHE_FILE, "w") as f:
        json.dump({
            "user_access_token": access_token,
            "refresh_token": refresh_token,
            "expire_at": expire_at,
        }, f)
    USER_TOKEN_CACHE_FILE.chmod(0o600)


def _clear_user_token_cache() -> None:
    try:
        USER_TOKEN_CACHE_FILE.unlink()
    except Exception:
        pass


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.client_address[0] not in ("127.0.0.1", "::1", "localhost"):
            self._respond("Forbidden")
            return

        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/callback":
            cb_state = params.get("state", [None])[0]
            expected_state = self.server.result.get("state", "")
            if cb_state != expected_state:
                self.server.result["error"] = "state_mismatch"
                self._respond("Authorization failed: state mismatch.")
                return

            code = params.get("code", [None])[0]
            error = params.get("error", [None])[0]
            if code:
                self.server.result["code"] = code
                self._respond("Authorization successful! You may close this window.")
            elif error:
                self.server.result["error"] = error
                self._respond(f"Authorization failed: {error}")
            else:
                self.server.result["error"] = "no_code"
                self._respond("No authorization code received.")
        else:
            self._respond("OK")

    def _respond(self, msg: str):
        body = f"<html><body><p>{msg}</p></body></html>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def _start_callback_server(port: int, result_holder: dict) -> HTTPServer:
    server = HTTPServer(("", port), _CallbackHandler)
    server.result = result_holder
    server.timeout = 10
    return server


