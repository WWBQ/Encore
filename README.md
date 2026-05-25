# Encore — Turn Every AI Conversation Into a Digital Asset

## What is Encore?

Encore archives your AI conversations as structured, searchable notes. One command saves a complete session summary — what you learned, what you fixed, what you decided — to your local machine and/or Feishu.

## Quick Start

```bash
pip install encore-ai

# Save to local Markdown (works immediately)
encore save '{"title":"Learned X","intent":"learning","context_digest":"...","payload":{"core_concept":"X","feynman_summary":"X is..."}}'

# Or connect Feishu
encore setup feishu
```

## Core Commands

| Command | Description |
|---------|-------------|
| `encore save '<json>'` | Archive a structured note |
| `encore list` | List all notes |
| `encore search <kw>` | Search by keyword |
| `encore share <kw>` | Output a note for AI context handoff |
| `encore setup feishu` | Guided Feishu OAuth setup |
| `encore config show` | Show adapter status |

## Storage Adapters

| Adapter | Status | Storage |
|---------|--------|---------|
| Local | ✅ | `~/.encore/notes/*.md` |
| Feishu | ✅ | Personal docx + bitable index |
| GitHub | Code ready | Repository Markdown |
| Notion | Code ready | Database pages |

## Note Format

Each note follows the Encore v0.1 schema with intent-driven payloads:

| Intent | Payload Fields |
|--------|---------------|
| `bug_fix` | symptom, root_cause, failed_attempts, solution_summary, solution_code, action_items |
| `learning` | core_concept, feynman_summary, detailed_explanation, related_concepts, references |
| `idea` | core_idea, pros_cons, action_steps |

Every note includes `context_digest` — a compressed AI-readable summary for cross-session context handoff.

## Architecture

```
encore save (CLI)
  → schema.py    validate JSON structure
  → storage.py   dispatch to all enabled adapters
    → local.py     write ~/.encore/notes/*.md
    → feishu.py    POST docx/v1/documents + OAuth
    → github.py    PUT repo contents
    → notion.py    POST pages
```

## Vision

Encore's goal is a **cognitive second brain** — not just documents, but your personal thinking patterns, debugging lessons, and growth trajectory, accumulated over time and resurfaced when you need them.

Future: IDE/browser extensions, memory resonance (auto-resurface relevant past notes), and team shared libraries.

---

**Encore — what matters, remembered.**
