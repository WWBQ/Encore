"""Schema 加载与基础校验"""

import json
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "encore_schema_v0.1.json"
def load_schema() -> dict:
    """加载数据 Schema 定义"""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
def validate(note: dict) -> list[str]:
    """校验必填字段和枚举值，返回错误列表"""
    errors = []
    schema = load_schema()

    for field in schema.get("required", []):
        if field not in note or note[field] is None:
            errors.append(f"缺少必填字段: {field}")

    intent = note.get("intent", "")
    intent_schema = schema["properties"]["intent"]
    valid_intents = intent_schema.get("enum", [])
    if intent not in valid_intents:
        errors.append(f"无效意图 '{intent}'，允许值: {valid_intents}")

    status = note.get("status", "resolved")
    status_schema = schema["properties"]["status"]
    valid_statuses = status_schema.get("enum", [])
    if status not in valid_statuses:
        errors.append(f"无效状态 '{status}'，允许值: {valid_statuses}")

    _validate_payload(note, schema, errors)
    return errors


def _validate_payload(note: dict, schema: dict, errors: list[str]) -> None:
    intent = note.get("intent", "")
    payload = note.get("payload", {})
    if not payload:
        return

    defs = schema.get("$defs", {})
    def_key = f"{intent}_payload"
    intent_def = defs.get(def_key, {})
    if not intent_def:
        return

    for field in intent_def.get("required", []):
        if field not in payload or payload[field] is None:
            errors.append(f"payload 缺少必填字段: {field}")

    allowed = set(intent_def.get("properties", {}).keys())
    for key in payload:
        if key not in allowed:
            errors.append(f"payload 未知字段 '{key}'，允许字段: {sorted(allowed)}")
