"""笔记存储：本地 Markdown + YAML frontmatter"""

import os
import re
import json
import yaml
from datetime import datetime
from pathlib import Path

NOTES_DIR = Path.home() / ".encore" / "notes"


def _ensure_dir() -> Path:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    return NOTES_DIR


def _slugify(title: str) -> str:
    """中英文标题转为文件名 safe slug"""
    slug = re.sub(r"[^\w一-鿿-]", "-", title.strip())
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-")[:80] or "untitled"


def save(note: dict) -> Path:
    """保存一条笔记，返回文件路径"""
    _ensure_dir()

    title = note.get("title", "未命名")
    ts = note.get("created_at", datetime.now().astimezone().isoformat())
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        dt = datetime.now()
    timestamp = dt.strftime("%Y-%m-%d-%H%M%S")
    filename = f"{timestamp}--{_slugify(title)}.md"
    filepath = NOTES_DIR / filename

    # Build YAML frontmatter
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

    # Build Markdown body
    body = _build_body(note)

    # Write file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.dump(frontmatter, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        f.write("---\n\n")
        f.write(body)

    return filepath


def _build_body(note: dict) -> str:
    """按意图类型生成人类可读正文"""
    intent = note.get("intent", "")
    payload = note.get("payload", {})

    blocks = []

    if intent == "bug_fix":
        if payload.get("symptom"):
            blocks.append(f"## 症状\n\n{payload['symptom']}\n")
        if payload.get("root_cause"):
            blocks.append(f"## 根因\n\n{payload['root_cause']}\n")
        failed = payload.get("failed_attempts", [])
        if failed:
            lines = "\n".join(f"- {a}" for a in failed)
            blocks.append(f"## 失败尝试\n\n{lines}\n")
        if payload.get("solution_summary"):
            blocks.append(f"## 解决方案\n\n{payload['solution_summary']}\n")
        if payload.get("solution_code"):
            blocks.append(f"## 最终代码\n\n```\n{payload['solution_code']}\n```\n")
        actions = payload.get("action_items", [])
        if actions:
            lines = "\n".join(f"- [ ] {a}" for a in actions)
            blocks.append(f"## 后续行动\n\n{lines}\n")

    elif intent == "learning":
        if payload.get("core_concept"):
            blocks.append(f"## 核心概念\n\n{payload['core_concept']}\n")
        if payload.get("feynman_summary"):
            blocks.append(f"## 一句话理解\n\n{payload['feynman_summary']}\n")
        if payload.get("detailed_explanation"):
            blocks.append(f"## 详细解释\n\n{payload['detailed_explanation']}\n")
        related = payload.get("related_concepts", [])
        if related:
            lines = "\n".join(f"- {c}" for c in related)
            blocks.append(f"## 关联概念\n\n{lines}\n")
        refs = payload.get("references", [])
        if refs:
            lines = "\n".join(f"- {r}" for r in refs)
            blocks.append(f"## 拓展阅读\n\n{lines}\n")

    elif intent == "idea":
        if payload.get("core_idea"):
            blocks.append(f"## 核心创意\n\n{payload['core_idea']}\n")
        pc = payload.get("pros_cons", {})
        if pc:
            if pc.get("pros"):
                lines = "\n".join(f"- {p}" for p in pc["pros"])
                blocks.append(f"## 优势\n\n{lines}\n")
            if pc.get("cons"):
                lines = "\n".join(f"- {c}" for c in pc["cons"])
                blocks.append(f"## 劣势\n\n{lines}\n")
        steps = payload.get("action_steps", [])
        if steps:
            lines = "\n".join(f"- [ ] {s}" for s in steps)
            blocks.append(f"## 落地步骤\n\n{lines}\n")

    # Append context_digest
    if note.get("context_digest"):
        blocks.append("---\n")
        blocks.append("## AI 上下文摘要 (context_digest)\n\n")
        blocks.append(f"{note['context_digest']}\n")

    return "\n".join(blocks)


def list_notes(intent_filter: str = None) -> list[dict]:
    """列出所有笔记摘要"""
    _ensure_dir()
    notes = []
    for fp in sorted(NOTES_DIR.glob("*.md"), reverse=True):
        meta = _read_frontmatter(fp)
        if meta:
            if intent_filter and meta.get("intent") != intent_filter:
                continue
            meta["_file"] = fp.name
            notes.append(meta)
    return notes


def search(keyword: str) -> list[dict]:
    """基于标题和标签的简单搜索"""
    _ensure_dir()
    results = []
    kw = keyword.lower()
    for fp in sorted(NOTES_DIR.glob("*.md"), reverse=True):
        meta = _read_frontmatter(fp)
        if not meta:
            continue
        title = meta.get("title", "").lower()
        tags = " ".join(meta.get("tags", [])).lower()
        if kw in title or kw in tags:
            meta["_file"] = fp.name
            results.append(meta)
    return results


def _read_frontmatter(filepath: Path) -> dict | None:
    """读取笔记的 YAML frontmatter"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.startswith("---"):
            return None
        _, fm, _ = content.split("---", 2)
        return yaml.safe_load(fm)
    except Exception:
        return None
