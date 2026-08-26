# LLM Art Prompt

**The prompt itself now lives in the application**, at
`artwall/templates/prompt.html`, and is served at `/prompt` with a copy
button. Edit it there; this file is a pointer so the text exists once.

It moved because `docs/` is excluded from the container images
(`.dockerignore`), so a copy kept here is not present at the booth, which is
the one place it is needed. The submission page links it in a new tab from
both the arrival modal and the "How this works" panel: navigating away in the
same tab would throw away the editor buffer, and being stuck for an idea is
exactly when there is work worth not losing.

What it is: a copy-paste prompt for an LLM, meant for the AI assistant on the
booth laptop. An attendee replaces `{{DESIGN PROMPT}}` with a description of
the piece they want. The rules baked into it mirror the Draw Contract, the
Supported Packages list (ADR-0001) and the render worker's limits, so the
generated code should pass the preview gate and render on the wall unchanged.
