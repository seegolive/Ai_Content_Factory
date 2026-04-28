 ---
name: acquire-codebase-knowledge
description: 'Use this skill when the user explicitly asks to map, document, or onboard into an existing codebase. Trigger for prompts like "map this codebase", "document this architecture", "onboard me to this repo", or "create codebase docs". Do not trigger for routine feature implementation, bug fixes, or narrow code edits unless the user asks for repository-level discovery.'
license: MIT
---

# Acquire Codebase Knowledge

Produces seven populated documents in `docs/codebase/` covering everything needed to work effectively on the project. Only document what is verifiable from files or terminal output — never infer or assume.

## Output Contract (Required)

Before finishing, all of the following must be true:

1. Exactly these files exist in `docs/codebase/`: `STACK.md`, `STRUCTURE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `INTEGRATIONS.md`, `TESTING.md`, `CONCERNS.md`.
2. Every claim is traceable to source files, config, or terminal output.
3. Unknowns are marked as `[TODO]`; intent-dependent decisions are marked `[ASK USER]`.
4. Every document includes a short "evidence" list with concrete file paths.
5. Final response includes numbered `[ASK USER]` questions and intent-vs-reality divergences.

## Workflow

```
- [ ] Phase 1: Run scan, read intent documents
- [ ] Phase 2: Investigate each documentation area
- [ ] Phase 3: Populate all seven docs in docs/codebase/
- [ ] Phase 4: Validate docs, present findings, resolve all [ASK USER] items
```

### Phase 1: Scan and Read Intent

1. Search for `PRD`, `TRD`, `README`, `ROADMAP`, `SPEC`, `DESIGN` files and read them.
2. Summarize the stated project intent before reading any source code.

### Phase 2: Investigate

Use the scan output to answer questions for each of the seven templates:
- STACK: language, runtime, frameworks, all dependencies
- STRUCTURE: directory layout, entry points, key files
- ARCHITECTURE: layers, patterns, data flow
- CONVENTIONS: naming, formatting, error handling, imports
- INTEGRATIONS: external APIs, databases, auth, monitoring
- TESTING: frameworks, file organization, mocking strategy
- CONCERNS: tech debt, bugs, security risks, perf bottlenecks

### Phase 3: Populate Templates

Fill documents in this order:

1. `STACK.md` — language, runtime, frameworks, all dependencies
2. `STRUCTURE.md` — directory layout, entry points, key files
3. `ARCHITECTURE.md` — layers, patterns, data flow
4. `CONVENTIONS.md` — naming, formatting, error handling, imports
5. `INTEGRATIONS.md` — external APIs, databases, auth, monitoring
6. `TESTING.md` — frameworks, file organization, mocking strategy
7. `CONCERNS.md` — tech debt, bugs, security risks, perf bottlenecks

Use `[TODO]` for anything that cannot be determined from code. Use `[ASK USER]` where the right answer requires team intent.

### Phase 4: Validate, Repair, Verify

1. For each non-trivial claim, confirm at least one evidence reference exists.
2. Fix any missing or unsupported sections.
3. Present summary of all seven documents, list every `[ASK USER]` item as a numbered question.
4. Highlight any Intent vs. Reality divergences from Phase 1.

## Gotchas

- **Outdated README:** README often describes intended architecture, not the current one. Cross-reference with actual file structure.
- **TypeScript path aliases:** `tsconfig.json` `paths` config means imports like `@/foo` don't map directly to the filesystem.
- **Generated/compiled output:** Never document patterns from `dist/`, `build/`, `.next/`, `__pycache__/`.
- **`.env.example` reveals required config:** Read `.env.example` to discover required environment variables.
- **`devDependencies` ≠ production stack:** Document linters, formatters, and test frameworks separately as dev tooling.
