---
name: encore
description: Archive the current conversation as a structured note with intent classification (bug_fix / learning / idea). Type /encore to trigger.
---

# Encore — AI Conversation Archiver

Archive the current conversation to `~/.encore/notes/`.

## Execution Flow

1. Review the full current session
2. Detect the conversation language and output all fields in that language
3. **Segment the session** into distinct topics (see Topic Segmentation below)
4. For **each segment**, classify intent and extract structured data independently
5. Assemble and save one note per segment
6. Report a summary of all notes created

## Topic Segmentation

A single session often spans multiple distinct topics. Split by logical boundaries:

- A new problem/error being raised = new segment
- A clear subject shift (e.g., from debugging → to deployment, from code → to docs) = new segment
- The user explicitly starting a new task = new segment

**Granularity rule**: if you're unsure whether two topics should be separate, merge them. Better one rich note than two thin ones.

For each segment, determine its own intent and fill the corresponding template.

## Intent Classification

- **bug_fix**: Troubleshooting errors, fixing bugs, resolving technical failures, ending with working code/configuration
- **learning**: Explaining concepts, learning new knowledge, understanding technical principles
- **idea**: Brainstorming, product design, solution discussion, architecture planning

## Templates

### bug_fix

```json
{
  "encore_version": "0.1",
  "intent": "bug_fix",
  "title": "One-line problem description (≤120 chars)",
  "context_digest": "Compressed AI summary (≤2000 chars): 1. error 2. root cause 3. fix 4. why this fix 5. remaining risks",
  "status": "resolved",
  "source_environment": "claude_code",
  "key_decision": "Core decision made (downgrade package, switch approach, etc.)",
  "open_questions": ["Unresolved follow-ups"],
  "tags": ["relevant", "tech", "tags"],
  "payload": {
    "symptom": "Error symptoms",
    "root_cause": "Root cause analysis",
    "failed_attempts": ["What didn't work"],
    "solution_code": "Final working code (if any)",
    "solution_summary": "Text summary of solution",
    "action_items": ["Follow-up todos"]
  }
}
```

### learning

```json
{
  "encore_version": "0.1",
  "intent": "learning",
  "title": "One-line summary of what was learned (≤120 chars)",
  "context_digest": "Compressed AI summary (≤2000 chars): 1. concept 2. key points 3. connections",
  "status": "resolved",
  "source_environment": "claude_code",
  "tags": ["relevant", "domain", "tags"],
  "payload": {
    "core_concept": "Core concept name",
    "feynman_summary": "One-line explanation a layperson would understand",
    "detailed_explanation": "Detailed explanation",
    "related_concepts": ["Related concept"],
    "references": ["Links or recommended reading"]
  }
}
```

### idea

```json
{
  "encore_version": "0.1",
  "intent": "idea",
  "title": "One-line description of the idea (≤120 chars)",
  "context_digest": "Compressed AI summary (≤2000 chars): 1. core idea 2. why it matters 3. risks 4. next steps",
  "status": "open",
  "source_environment": "claude_code",
  "tags": ["relevant", "domain", "tags"],
  "key_decision": "Key decision made during discussion (if any)",
  "open_questions": ["Questions still to discuss"],
  "payload": {
    "core_idea": "Core idea description",
    "pros_cons": {
      "pros": ["Advantage"],
      "cons": ["Risk / drawback"]
    },
    "action_steps": ["Concrete next step"]
  }
}
```

## context_digest Guidelines

Written for the **next AI**, not for humans:
- Pure narrative, no headings, no markdown formatting
- Structure: background → what was done → why → conclusion → open issues
- ≤2000 characters
- Complete enough that another AI can continue the conversation after reading it

## Save

After assembling the JSON, run:

```bash
encore save '<json string>'
```

## User Feedback

Report after save:
1. Archive type (emoji + label)
2. Note title
3. File path
4. Number of action items (if any)
