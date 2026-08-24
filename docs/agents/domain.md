# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, or
- **`CONTEXT-MAP.md`** at the repo root if it exists — it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/` for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

This repo is **single-context**:

```
/
├── CONTEXT.md                         ← Piece, Submission, Preview, Wall, Tile, …
├── docs/adr/
│   ├── 0001-preview-defines-supported-packages.md
│   ├── 0002-sqlite-is-the-queue.md
│   ├── 0003-webm-vp9-for-animated-pieces.md
│   ├── 0004-cloud-vps-hosting.md
│   ├── 0005-wall-tiles-fill-the-screen.md
│   └── 0006-jetbrains-branded-light-theme.md
├── artwall/                           ← server, worker, db, config, templates, static
└── worker/                            ← sandbox Dockerfile + render harness
```

A multi-context repo would instead carry a `CONTEXT-MAP.md` at the root pointing at one `CONTEXT.md` per context, with context-specific decisions under `src/<context>/docs/adr/` and system-wide ones staying in the root `docs/adr/`. That does not apply here.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids — each entry lists its rejected synonyms on an `_Avoid_` line, and those are binding.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0003 (WebM/VP9 for animated pieces) — but worth reopening because…_
