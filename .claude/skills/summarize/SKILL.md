---
name: summarize
description: Summarize the current session and persist a cumulative project log so future Claude Code sessions can come up to speed instantly
disable-model-invocation: true
argument-hint: "[optional focus area]"
---

# Summarize Session

Produce a structured summary of the current conversation **and persist it to `docs/session_log.md`** as a cumulative, longitudinal record so future Claude Code sessions can read one file and be fully oriented to the project's history and current state.

## What this file is for

`docs/session_log.md` is the **living memory of the project**. It is read at the start of every new Claude Code session to bring the assistant up to speed instantly. It complements `CLAUDE.md` (which is the static guide to conventions) by providing the *historical and current-state* layer:

- What has been built so far
- What was decided and why
- What is in flight, deferred, or known broken
- A running, append-only session-by-session log

If you are reading this in a fresh session, **read `docs/session_log.md` end-to-end before doing anything else**. The "Current State" section at the top reflects the latest reality; the "Session History" section below is an append-only log of every prior session, newest at top.

## Instructions

### Step 1 — Read the existing log if any

Read `docs/session_log.md` if it exists. If it does not exist yet, you are creating it from scratch for the first time.

### Step 2 — Review the full conversation context

Walk every message, tool call, decision, code change, file created, test added, and bug fixed in this session. Don't miss anything — the goal is that a future session can recover the full picture from the log.

If `$ARGUMENTS` is provided, weight the new session entry toward that focus area (e.g. "backend changes", "bugs fixed"), but still update the Current State section with anything that materially changed.

### Step 3 — Produce the new file content

The file has two top-level sections that work in tandem:

- **Current State** — rewritten every session to reflect the latest shipped reality. Future sessions read this first to know what's true *now*.
- **Session History** — append-only, newest at top. Each session adds a new dated entry. Prior entries are preserved verbatim, never edited or summarized away. This is the longitudinal record.

Use this structure:

```markdown
# CEN — Session Log

> **Read this file at the start of every new Claude Code session.**
> Top section reflects current reality. Bottom section is the append-only history.

## Current State

[Rewrite this entire section every session. It should always reflect
the latest shipped reality of the project.]

### Project overview
One-paragraph description of what CEN is, who uses it, and what the
prototype currently does end-to-end.

### Tech stack
Bullet list — language, framework, db, key libraries, deploy target.
Match what's actually in pyproject.toml + frontend/package.json + Dockerfile.

### How to run locally
Concrete commands:
- backend: `uvicorn cen.api.app:create_app --factory --reload --port 8000`
- frontend: `cd frontend && npm run dev` (port 5173)
- tests: `pytest tests/ -v`
- Docker build (matches Render): `docker build -t cen-test . && docker run --rm -p 10001:10000 cen-test`

### Architecture at a glance
What modules exist, what each one does, what the data flow is. Three
or four short bullets — link to CLAUDE.md §3 for the canonical version.

### What's shipped
Feature inventory of everything that currently works in the running
app, organized by area (Workflows, Engine, UI, Storage, Concierge,
Export, etc.). Should be specific enough that a new session can
answer "is X built yet?" without grepping.

### Non-negotiables in force
The CLAUDE.md non-negotiables that are actually being followed in the
current code (PII scrubbing, append-only audit, idempotent resume,
module version pinning, etc.). Note any that are stubbed.

### Open items
Numbered list of known limitations, deferred work, and follow-ups.
Each item should say what it is and why it was deferred.

### Recent test counts and verification status
- Backend tests: N/N passing
- Frontend tsc: clean / N errors
- Last commit: <hash> — <one-line summary>

## Session History

[Append-only — never edit prior session entries. Newest at top.]

### YYYY-MM-DD — <session theme in 3-5 words>

**Commits:** <list of commit hashes from this session>

**What was done:**
- Bullet list of completed work

**Key decisions:**
- Architectural or design choices made and why

**Files changed:**
- Grouped by area: backend, frontend, tests, modules, docs

**Open items raised:**
- Anything new that was flagged for follow-up

---

### YYYY-MM-DD — <previous session theme>
[earlier entries below — preserved verbatim from the prior version of this file]
```

### Step 4 — Write the file

Use the Write tool to write the full file content to `docs/session_log.md` (path is relative to the repo root, which on this machine is `C:\Users\Patrick\CEN\docs\session_log.md`).

If the `docs/` directory does not exist yet, the Write tool will fail — in that case use Bash to `mkdir -p docs` first, then Write the file.

**CRITICAL — preserve history:**
When updating an existing file, you MUST preserve every prior session entry in the Session History section verbatim. The workflow is:
1. Read the existing file.
2. Extract the existing Session History block (every entry from every prior session).
3. Rewrite the Current State section in place from scratch.
4. Prepend a new session entry to the top of the Session History (newest first).
5. Write the combined file.

Never delete, edit, summarize, or compact prior session entries. If you think a prior entry is wrong or outdated, add a correction note in the *new* session entry instead of editing the old one. The history is the longitudinal record — its value is precisely that it is unedited.

### Step 5 — Confirm to the user

After writing, briefly tell the user:
- The path written
- Whether it was a fresh creation or an update
- The new session entry's theme and how many history entries the file now contains
- Suggest they commit the file (`git add docs/session_log.md && git commit -m "docs: session log for <date>"`)

## Style guidelines

- **Plain language.** No jargon, no marketing words. Write for someone who just walked into the project and needs to understand it in 5 minutes.
- **Specific over abstract.** "Added 23 input_schema entries across 6 modules" beats "improved authoring."
- **Cite commit hashes** for any concrete shipped change so future sessions can `git show <hash>` for the code.
- **Cite file paths** for any non-obvious component or pattern.
- **Don't restate CLAUDE.md.** That file is the static guide; session_log.md is the living history. Cross-reference instead of duplicating.
- **Don't include emojis** unless the user has explicitly asked for them in their conventions.
- **Length is fine.** This file is read by the assistant, not skimmed by a human. Be thorough enough that the next session doesn't have to ask "did you build X?" — the answer should be findable.
- **The Current State section is the source of truth for "now"**; the Session History entries are the source of truth for "how we got here." Don't conflate the two.
