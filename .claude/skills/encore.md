---
name: encore
description: 将当前对话归档为结构化笔记，支持 bug_fix / learning / idea 三种意图分类。输入 /encore 即可触发。
---

# Encore — AI 对话知识归档

将当前对话内容分析、分类、提取结构化信息，写入本地笔记库 `~/.encore/notes/`。

## 执行流程

1. 回顾当前会话的完整内容
2. 判断对话的核心意图：bug_fix（排错）、learning（学习）、idea（灵感）
3. 根据意图类型，按对应模板提取结构化数据
4. 生成 context_digest：2000 字以内的压缩摘要，让其他 AI 能直接接手后续对话
5. 组装为完整 JSON，调用 `encore save` 保存为 Markdown

## 意图判断规则

- **bug_fix**：对话核心是排查报错、修复 bug、解决技术故障，最终给出了可运行的代码或配置
- **learning**：对话核心是解释概念、学习新知识、理解技术原理
- **idea**：对话核心是头脑风暴、产品设计、方案探讨、架构规划

## 三类提取模板

### bug_fix 排错模式

提取以下字段（无对应内容则写空字符串或空数组）：

```
{
  "encore_version": "0.1",
  "intent": "bug_fix",
  "title": "一句话描述问题（≤120字）",
  "context_digest": "给AI看的压缩摘要（≤2000字）：1.什么报错 2.真正原因 3.怎么修的 4.为什么这样修 5.遗留风险",
  "status": "resolved",
  "source_environment": "claude_code",
  "key_decision": "本次解决的核心决策（如：降级某个包、改用某个方案）",
  "open_questions": ["未解决的问题或后续需要跟进的点"],
  "tags": ["相关技术栈标签，如 langgraph", "pydantic", "python"],
  "payload": {
    "symptom": "报错现象/症状描述",
    "root_cause": "根因分析",
    "failed_attempts": ["试过但失败的方法1", "试过但失败的方法2"],
    "solution_code": "最终可运行的代码（如有）",
    "solution_summary": "解决方案的文字总结",
    "action_items": ["后续待办1", "后续待办2"]
  }
}
```

### learning 学习模式

```
{
  "encore_version": "0.1",
  "intent": "learning",
  "title": "一句话概括学到的东西（≤120字）",
  "context_digest": "给AI看的压缩摘要（≤2000字）：1.学了什么概念 2.核心要点 3.和其他概念的关联",
  "status": "resolved",
  "source_environment": "claude_code",
  "tags": ["相关领域标签"],
  "payload": {
    "core_concept": "核心概念名称",
    "feynman_summary": "用费曼技巧一句话解释（让外行也能听懂）",
    "detailed_explanation": "详细的解释说明",
    "related_concepts": ["关联概念1", "关联概念2"],
    "references": ["参考链接或推荐阅读"]
  }
}
```

### idea 灵感模式

```
{
  "encore_version": "0.1",
  "intent": "idea",
  "title": "一句话描述这个想法（≤120字）",
  "context_digest": "给AI看的压缩摘要（≤2000字）：1.核心想法 2.为什么值得做 3.有什么风险 4.下一步是什么",
  "status": "open",
  "source_environment": "claude_code",
  "tags": ["相关领域标签"],
  "key_decision": "本次讨论中做出的关键决策（如有）",
  "open_questions": ["待讨论的问题"],
  "payload": {
    "core_idea": "核心创意描述",
    "pros_cons": {
      "pros": ["优势1", "优势2"],
      "cons": ["劣势/风险1", "劣势/风险2"]
    },
    "action_steps": ["落地步骤1", "落地步骤2"]
  }
}
```

## context_digest 编写规范

context_digest 是给**下一个 AI** 看的，不是给人看的。要求：
- 纯叙述，无标题、无 Markdown 格式
- 包含：背景 → 做了什么 → 为什么 → 结论 → 遗留问题
- 不超过 2000 字
- 足够完整，让另一个 AI 读完即可继续对话

## 保存

组装完 JSON 后，执行：

```bash
encore save '<json string>'
```

## 反馈用户

保存成功后向用户报告：
1. 归档类型（emoji + 文字）
2. 笔记标题
3. 文件路径
4. 提取的待办事项数量（如有）
