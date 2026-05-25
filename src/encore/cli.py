"""Encore CLI — AI 对话知识归档命令行工具"""

import json
import click
from datetime import datetime, timezone

from .storage import save, list_notes, search, read_note
from .schema import validate
from .config import load_config, save_config, CONFIG_PATH


def _run_feishu_auth():
    from .adapters.feishu import FeishuAdapter
    try:
        ad = FeishuAdapter()
        result = ad.start_oauth()
        click.echo(f"\n✅ 飞书授权成功！")
        click.echo(f"   token 已保存，可以开始使用 encore save")
    except Exception as e:
        click.echo(f"\n❌ 授权失败: {e}", err=True)
        click.echo(f"   请检查 App ID/Secret 和重定向 URL，然后重试")


def _run_feishu_guide(current_cfg: dict):
    click.echo("═══ 飞书接入向导 ═══\n")

    click.echo("步骤 1: 在飞书开放平台创建应用")
    click.echo("   → 打开 https://open.feishu.cn/app")
    click.echo("   → 创建「企业自建应用」，名称随意（如 Encore）")
    click.echo("   → 在应用页面左侧找到「凭证与基础信息」，复制 App ID 和 App Secret\n")

    click.echo("步骤 2: 配置权限")
    click.echo("   → 左侧「权限管理」，搜索并开通：")
    click.echo("      - docx:document  (文档读写)")
    click.echo("      - drive:drive    (云盘文件列表)")
    click.echo("      - bitable:app    (多维表格，可选)")
    click.echo("   → 开通后点击「批量开通」确认\n")

    click.echo("步骤 3: 配置重定向 URL")
    click.echo("   → 左侧「安全设置」，重定向 URL 输入：")
    click.echo("      http://localhost:8888/callback")
    click.echo("   → 点击保存\n")

    click.echo("步骤 4: 发布应用")
    click.echo("   → 右上角「发布新版本」→ 确认发布\n")

    if not click.confirm("\n以上步骤完成了吗？"):
        click.echo("请完成后再运行 encore setup feishu")
        return

    app_id = click.prompt("App ID", default=current_cfg.get("app_id", ""), type=str).strip()
    app_secret = click.prompt("App Secret", default=current_cfg.get("app_secret", ""), type=str).strip()
    domain = click.prompt("飞书企业域名（打开飞书网页版，地址栏 xxx.feishu.cn 中取 xxx 部分）",
                          default=current_cfg.get("domain", ""), type=str).strip()

    cfg = load_config()
    cfg["adapters"]["feishu"].update({
        "enabled": True,
        "app_id": app_id,
        "app_secret": app_secret,
        "domain": domain,
    })
    save_config(cfg)
    click.echo("\n✅ 配置已保存")

    click.echo("\n步骤 5: OAuth 授权（浏览器将打开飞书授权页）")
    if click.confirm("开始授权？"):
        _run_feishu_auth()
@click.group()
def main():
    """Encore — AI 对话知识归档工具"""
    pass
@main.command(name="save")
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

    if "created_at" not in note:
        note["created_at"] = datetime.now(timezone.utc).isoformat()
    if "status" not in note:
        note["status"] = "resolved"
    if "source_environment" not in note:
        note["source_environment"] = "claude_code"

    errors = validate(note)
    if errors:
        for e in errors:
            click.echo(f"校验错误: {e}", err=True)
        raise SystemExit(1)

    results = save(note)
    for name, identifier in results.items():
        if identifier:
            click.echo(f"✅ [{name}] {identifier}")
        else:
            click.echo(f"❌ [{name}] 保存失败")
@main.command(name="list")
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
@main.command(name="search")
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
@main.command(name="share")
@click.argument("keyword")
def share_cmd(keyword: str):
    """分享一条笔记给其他 AI（输出 metadata + context_digest）

    示例:
      encore share pypi
      encore share schema
    """
    results = search(keyword)
    if not results:
        click.echo(f"未找到与 '{keyword}' 相关的笔记。")
        return

    for n in results:
        note = read_note(n["_file"])
        if not note:
            click.echo(f"⚠ 无法读取: {n['_file']}")
            continue

        intent_icon = {"bug_fix": "🐛", "learning": "📚", "idea": "💡"}.get(note.get("intent", ""), "📝")
        click.echo(f"---")
        click.echo(f"{intent_icon} {note.get('title', '')}")
        click.echo(f"Intent: {note.get('intent', '')} | Status: {note.get('status', '')}")
        if note.get("tags"):
            click.echo(f"Tags: {', '.join(note['tags'])}")
        if note.get("key_decision"):
            click.echo(f"Key Decision: {note['key_decision']}")
        if note.get("open_questions"):
            click.echo(f"Open Questions:")
            for q in note["open_questions"]:
                click.echo(f"  - {q}")
        click.echo(f"\nContext (for AI):\n")
        click.echo(note.get("context_digest", ""))
        click.echo()
@main.group()
def setup():
    """一键接入外部服务"""


@setup.command()
@click.option("--reset", is_flag=True, help="清除飞书配置和授权")
def feishu(reset: bool):
    """接入飞书 — 引导创建应用并完成授权"""
    from .adapters.feishu import FeishuAdapter, _read_user_token_cache, _clear_user_token_cache

    cfg = load_config()
    feishu_cfg = cfg.get("adapters", {}).get("feishu", {})

    if reset:
        if not click.confirm("确认清除飞书所有配置和授权信息？"):
            return
        cfg["adapters"]["feishu"] = {"enabled": True}
        save_config(cfg)
        _clear_user_token_cache()
        click.echo("✅ 飞书配置和授权已清除，运行 encore setup feishu 重新接入")
        return

    is_configured = bool(feishu_cfg.get("app_id") and feishu_cfg.get("app_secret"))
    is_authed = _read_user_token_cache() is not None

    try:
        if is_configured and is_authed:
            click.echo("飞书已接入 ✅\n")
            click.echo(f"  App ID: {feishu_cfg['app_id']}")
            click.echo(f"  Domain: {feishu_cfg.get('domain', '(未设置)')}")
            click.echo(f"  授权状态: 已授权")
            click.echo(f"\n运行 encore save 即可存档到飞书。")
            if click.confirm("\n重新授权？"):
                _run_feishu_auth()
            elif click.confirm("重新配置 App ID？"):
                _run_feishu_guide(feishu_cfg)
            return

        if is_configured and not is_authed:
            click.echo("飞书已配置，但尚未 OAuth 授权。\n")
            if click.confirm("开始授权？"):
                _run_feishu_auth()
            return

        _run_feishu_guide(feishu_cfg)
    except click.Abort:
        pass


@main.command()
@click.option("--port", default=8888, help="本地回调端口")
def auth(port: int):
    """飞书 OAuth 授权 — 以个人身份创建文档。"""
    from .adapters.feishu import FeishuAdapter

    try:
        ad = FeishuAdapter()
        result = ad.start_oauth(port)
        click.echo(f"✅ 飞书个人授权成功")
        click.echo(f"   access_token: {result.get('access_token', '')[:20]}...")
        click.echo(f"   expires_in: {result.get('expires_in', '')}s")
        click.echo(f"   token 已保存到 ~/.encore/.feishu_user_token")
    except Exception as e:
        click.echo(f"❌ 授权失败: {e}", err=True)
        raise SystemExit(1)


@main.group()
def config():
    """管理适配器配置"""
@config.command()
def show():
    """显示当前配置"""
    cfg = load_config()
    click.echo(f"配置文件: {CONFIG_PATH}\n")
    for name, acfg in cfg.get("adapters", {}).items():
        status = "✅ enabled" if acfg.get("enabled") else "○ disabled"
        click.echo(f"  [{status}] {name}")
        for k, v in acfg.items():
            if k == "enabled":
                continue
            display = v if v else "(not set)"
            click.echo(f"         {k}: {display}")
@config.command()
@click.argument("adapter")
def enable(adapter: str):
    """启用一个适配器"""
    cfg = load_config()
    if adapter not in cfg.get("adapters", {}):
        click.echo(f"未知适配器: {adapter} (支持: local, github, feishu, notion)", err=True)
        raise SystemExit(1)
    cfg["adapters"][adapter]["enabled"] = True
    save_config(cfg)
    click.echo(f"✅ {adapter} 已启用")
@config.command()
@click.argument("adapter")
def disable(adapter: str):
    """禁用一个适配器"""
    cfg = load_config()
    if adapter not in cfg.get("adapters", {}):
        click.echo(f"未知适配器: {adapter}", err=True)
        raise SystemExit(1)
    cfg["adapters"][adapter]["enabled"] = False
    save_config(cfg)
    click.echo(f"○ {adapter} 已禁用")
@config.command()
@click.argument("adapter")
@click.argument("key")
@click.argument("value")
def set(adapter: str, key: str, value: str):
    """设置适配器配置项

    \b
    示例:
      encore config set github token ghp_xxx
      encore config set github repo you/encore-notes
      encore config set feishu app_id cli_xxx
      encore config set notion database_id xxx
    """
    cfg = load_config()
    if adapter not in cfg.get("adapters", {}):
        click.echo(f"未知适配器: {adapter}", err=True)
        raise SystemExit(1)
    cfg["adapters"][adapter][key] = value
    save_config(cfg)
    click.echo(f"✅ {adapter}.{key} = {value}")
