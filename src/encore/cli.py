"""Encore CLI — AI 对话知识归档命令行工具"""

import json
import click
from datetime import datetime, timezone

from .storage import save, list_notes, search
from .schema import validate


@click.group()
def main():
    """Encore — AI 对话知识归档工具"""
    pass


@main.command()
@click.argument("data", required=False)
@click.option("--file", "-f", "json_file", type=click.Path(exists=True), help="从 JSON 文件读取")
def save_cmd(data: str | None, json_file: str | None):
    """保存一条结构化笔记。传入 JSON 字符串，或通过 --file 指定 JSON 文件。

    \b
    示例:
      encore save '{"title":"测试","intent":"learning","context_digest":"...","payload":{...}}'
      encore save --file note.json
    """
    if json_file:
        with open(json_file, "r", encoding="utf-8") as f:
            data = f.read()

    if not data:
        click.echo("错误: 请提供 JSON 数据或使用 --file 指定文件", err=True)
        raise SystemExit(1)

    try:
        note = json.loads(data)
    except json.JSONDecodeError as e:
        click.echo(f"JSON 解析错误: {e}", err=True)
        raise SystemExit(1)

    # Fill defaults
    if "created_at" not in note:
        note["created_at"] = datetime.now(timezone.utc).isoformat()
    if "status" not in note:
        note["status"] = "resolved"
    if "source_environment" not in note:
        note["source_environment"] = "claude_code"

    # Validate
    errors = validate(note)
    if errors:
        for e in errors:
            click.echo(f"校验错误: {e}", err=True)
        raise SystemExit(1)

    # Save
    filepath = save(note)
    click.echo(f"✅ 已归档: {filepath}")


@main.command()
@click.option("--intent", "-i", type=click.Choice(["bug_fix", "learning", "idea"]), help="按意图过滤")
def list_cmd(intent: str | None):
    """列出所有已归档笔记"""
    notes = list_notes(intent)
    if not notes:
        click.echo("暂无归档笔记。")
        return

    click.echo(f"共 {len(notes)} 条笔记:\n")
    for n in notes:
        intent_icon = {"bug_fix": "🐛", "learning": "📚", "idea": "💡"}.get(n.get("intent", ""), "📝")
        title = n.get("title", "未命名")
        click.echo(f"  {intent_icon} {title}")
        click.echo(f"    文件: {n['_file']}  |  {n.get('created_at', '')}")


@main.command()
@click.argument("keyword")
def search_cmd(keyword: str):
    """按关键词搜索笔记（匹配标题和标签）"""
    results = search(keyword)
    if not results:
        click.echo(f"未找到与 '{keyword}' 相关的笔记。")
        return

    click.echo(f"找到 {len(results)} 条相关笔记:\n")
    for n in results:
        intent_icon = {"bug_fix": "🐛", "learning": "📚", "idea": "💡"}.get(n.get("intent", ""), "📝")
        title = n.get("title", "未命名")
        click.echo(f"  {intent_icon} {title}")
        click.echo(f"    文件: {n['_file']}  |  标签: {', '.join(n.get('tags', []))}")
