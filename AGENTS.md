# Code Art Wall — agent instructions

A conference-booth activity: attendees write Python that generates art,
submit it with contact info, and approved pieces appear on a big-screen wall.
See `README.md` for how to run the stack.

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/<feature-slug>/` in
your working copy. That directory is deliberately **untracked** — the repo is
public, and the specs describe unfixed weaknesses in detail. It therefore does
not travel with a clone: ask whoever owns the checkout for it.
See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, used verbatim as `Status:` values on issue
files. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root.
See `docs/agents/domain.md`.
