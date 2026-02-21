---
name: summarize
description: Summarize the current session's work, decisions, and changes
disable-model-invocation: true
argument-hint: "[optional focus area]"
---

# Summarize Session

Produce a concise summary of the current conversation session.

## Instructions

1. Review the full conversation context — all messages, tool calls, decisions, and code changes
2. If `$ARGUMENTS` is provided, focus the summary on that area (e.g. "backend changes", "bugs fixed")
3. Produce a structured summary with these sections:

```
## Session Summary

### What was done
- Bullet list of completed work

### Key decisions
- Architectural or design choices made and why

### Files changed
- List of files created, modified, or deleted

### Open items
- Anything unfinished, blocked, or flagged for follow-up
```

4. Keep it concise — aim for something someone could skim in 30 seconds
5. Use plain language, not jargon
