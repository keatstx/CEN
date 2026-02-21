---
name: commit
description: Stage and commit changes with a conventional commit message
disable-model-invocation: true
allowed-tools: Bash(git *)
argument-hint: "[type: subject]"
---

# Commit

Create a Git commit following conventional commit format.

## Format

```
<type>(<scope>): <subject>

<body>
```

## Types

- **feat** — New feature
- **fix** — Bug fix
- **refactor** — Code restructuring (no behavior change)
- **style** — Formatting, whitespace (no logic change)
- **docs** — Documentation only
- **chore** — Build, deps, tooling
- **test** — Adding or fixing tests

## Instructions

1. Run `git status` and `git diff --stat` to understand what changed
2. If `$ARGUMENTS` is provided, use it as the commit message
3. If no arguments, analyze the changes and draft a concise commit message
4. Stage relevant files by name (avoid `git add -A` to prevent committing secrets or build artifacts)
5. Commit with the message, appending the co-author trailer:
   ```
   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
   ```
6. Show the result with `git log -1`
