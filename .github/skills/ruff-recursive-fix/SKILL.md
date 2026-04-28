 ---
name: ruff-recursive-fix
description: Run Ruff checks with optional scope and rule overrides, apply safe and unsafe autofixes iteratively, review each change, and resolve remaining findings with targeted edits or user decisions.
---

# Ruff Recursive Fix

## Overview

Use this skill to enforce code quality with Ruff in a controlled, iterative workflow. It supports:

- Optional scope limitation to a specific folder.
- Default project settings from `pyproject.toml`.
- Flexible Ruff invocation (`uv`, direct `ruff`, `python -m ruff`, or equivalent).
- Optional per-run rule overrides (`--select`, `--ignore`, `--extend-select`, `--extend-ignore`).
- Automatic safe then unsafe autofixes.
- Diff review after each fix pass.
- Recursive repetition until findings are resolved or require a decision.

## Inputs

Collect these inputs before running:

- `target_path` (optional): folder or file to check. Empty means whole repository.
- `ruff_runner` (optional): explicit Ruff command prefix (for example `uv run`, `ruff`, `python -m ruff`).
- `rules_select` (optional): comma-separated rule codes to enforce.
- `rules_ignore` (optional): comma-separated rule codes to ignore.
- `allow_unsafe_fixes` (default: true): whether to run Ruff unsafe fixes.
- `ask_on_ambiguity` (default: true): always ask the user when multiple valid choices exist.

## Workflow

### 1. Baseline Analysis

1. Run `<ruff_cmd> check` with the selected scope and options.
2. Classify findings by type: autofixable safe, autofixable unsafe, not autofixable.
3. If no findings remain, stop.

### 2. Safe Autofix Pass

1. Run Ruff with `--fix` using the same scope/options.
2. Review resulting diff carefully for semantic correctness.
3. Run `<ruff_cmd> format` on the same scope.
4. Re-run `<ruff_cmd> check` to refresh remaining findings.

### 3. Unsafe Autofix Pass

Run only if findings remain and `allow_unsafe_fixes=true`.

1. Run Ruff with `--fix --unsafe-fixes` using the same scope/options.
2. Review resulting diff carefully, prioritizing behavior-sensitive edits.
3. Run `<ruff_cmd> format` on the same scope.
4. Re-run `<ruff_cmd> check`.

### 4. Manual Remediation Pass

For remaining findings:

1. Fix directly in code when there is a clear, safe correction.
2. Keep edits minimal and local.
3. Run `<ruff_cmd> format` on the same scope.
4. Re-run `<ruff_cmd> check`.

### 5. Suppression Decision (`# noqa`)

Use suppression only when all conditions are true:

- The rule conflicts with required behavior, public API, framework conventions, or readability goals.
- Refactoring would be disproportionate to the value of the rule.
- The suppression is narrow and specific (single line, explicit code when possible).

Prefer `# noqa: <RULE>` over broad `# noqa`.

### 6. Recursive Loop and Stop Criteria

Repeat steps 2 to 5 until one of these outcomes:

- `<ruff_cmd> check` returns clean.
- Remaining findings require architectural/product decisions.
- Remaining findings are intentionally suppressed with documented rationale.
- Repeated loop makes no progress.

## Output Contract

At the end of execution, report:

- Scope and Ruff options used.
- Number of iterations performed.
- Summary of fixed findings.
- List of manual fixes.
- List of suppressions with rationale.
- Remaining findings, if any, and required user decisions.
