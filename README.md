# Encore — Turn Every AI Conversation Into a Digital Asset

## The Problem: Forgotten "Digital Gold"

Every day, we have incredibly valuable conversations with ChatGPT, Claude, and Cursor. We debug deep code issues, explore brilliant product architectures, and learn obscure technical concepts.

But the moment you close that chat window, that knowledge evaporates. The next time you hit the same error, you start from scratch. The "next steps" your AI suggested? Forgotten by tomorrow.

**Conversations are fragmented. Knowledge shouldn't be.**

## What is Encore?

Encore isn't another note-taking app. It's an **intent-driven AI knowledge router**.

It lives inside your existing AI environments (Claude Code, IDE, browser). It understands your conversations with AI, strips away the noise, extracts the core value, and transforms it into structured documents and action items — delivered precisely into your existing workflow.

**You focus on solving problems with AI. Encore remembers everything.**

## Core Features

### Zero-Friction Capture

"The best tool is the one you don't notice."

Encore rejects the copy-paste-between-apps workflow. By embedding directly into Claude Code as a Skill, and through IDE and browser extensions, Encore lives where your conversations happen. One command or one click — the rest happens silently in the background.

### Dynamic Intent Parsing

Encore doesn't just export chat logs. It has its own reasoning core that identifies the true intent of your conversation and applies the right extraction template:

| Mode | Automatically Extracted |
|------|------------------------|
| 🐛 Debug | Error symptoms → failed attempts → root cause → working solution |
| 📚 Learning | Core concept → Feynman-style summary → related concepts → further reading |
| 💡 Ideation | Core idea → pros/cons analysis → concrete action steps |

### Intelligent Asset Distribution

Encore follows the principle of "send information where it belongs," integrating seamlessly with your existing tools:

- Review docs & knowledge → auto-sync to Notion / Obsidian
- Reusable utility functions → auto-extract to GitHub Gist
- Next-step action items → auto-push to Todoist

### Memory Resonance

"Knowledge that resurfaces when you need it — that's a second brain."

When you encounter a similar error again, Encore wakes up and reminds you: "You ran into something similar last month. Here's the post-mortem. Want to take a look first?"

### AI Context Handoff

"Cross-AI conversations without losing context."

Every archived note auto-generates a `context_digest` — a structured summary under 2000 characters. The next AI can read it, pick up the context, and continue without you re-explaining everything. **50 rounds of conversation, compressed into a single card.**

## Product Architecture

Encore follows a **"parasitic frontend, standalone backend"** architecture:

- **Encore for Claude Code** — a Claude Code Skill for one-click knowledge archiving in the terminal
- **Encore Browser Extension** — embed into ChatGPT / Claude Web for one-click web conversation archiving
- **Encore Workflow** — an async processing engine built on LangGraph for intent recognition and data distribution

## Quick Start

```bash
pip install encore-ai
```

Then copy the skill file:

```bash
mkdir -p ~/.claude/skills
cp .claude/skills/encore.md ~/.claude/skills/
```

Start a Claude Code session, have a conversation, and type `/encore` to archive it.

## Vision

Encore's ultimate goal is to build a **cognitive second brain** that truly understands you.

Over time, what Encore accumulates isn't just documents — it's your personal thinking patterns, hard-won debugging lessons, and growth trajectory. It turns AI from a tool for solving today's problems into a partner for building lifelong digital assets.

**Encore — what matters, remembered.**
