# LLM Art Prompt

Copy everything between the markers below into an LLM (the PyCharm AI
assistant on the booth laptop, or any chat model) and replace
`{{DESIGN PROMPT}}` with the attendee's description of the piece they want.
The rules baked into the prompt mirror the Draw Contract, the Supported
Packages list (ADR-0001), and the render worker limits, so the generated
code should pass the preview gate and render on the wall unchanged.

---8<--- copy from here ---8<---

You are an expert Python creative coder. Write a single, self-contained
Python script that generates a piece of algorithmic art for a conference
"Code Art Wall". The piece described below will be rendered by an automated
pipeline, so the code must follow the contract exactly.

## The piece to create

{{DESIGN PROMPT}}

## Contract (must follow exactly)

- Define exactly ONE top-level function, choosing one of:
  - `def draw():` — a static piece.
  - `def draw(t):` — an animated piece; `t` is a float sweeping 0.0 → 1.0
    over one 5-second loop (150 frames at 30 fps).
- `draw` must RETURN one of:
  - a numpy array — shape `(H, W, 3)` or `(H, W, 4)`, either `uint8`
    (0–255) or floats in 0..1,
  - a matplotlib `Figure`, or
  - a PIL `Image`.
- Animated pieces must loop perfectly: the frame at `t = 1.0` must be
  identical to the frame at `t = 0.0`. Drive every motion with periodic
  functions of `t` (e.g. phases like `2 * numpy.pi * t`, or integer
  multiples of full rotations) — never with unbounded time.

## Supported Packages (nothing else)

`numpy`, `matplotlib`, `Pillow` (PIL), `pandas`, `shapely`, `scipy`,
`colour`, `trimesh`, `svgpathtools`

Only these packages plus the Python standard library are installed.
Do NOT use `py5`, `Processing`, `cairo`, `pygame`, `OpenCV`, `torch`,
or anything else.

## Hard environment rules

- The code runs once in an offline sandbox: no network access, no file
  reads or writes, no user input, no `plt.show()`, no windows.
- Deterministic output is required: seed every random generator explicitly
  (e.g. `rng = numpy.random.default_rng(42)`) so re-renders are identical.
- Budget: the whole render (all 150 frames for animation) must finish in
  well under 60 seconds on one CPU core with 1 GB of RAM. For `draw(t)`
  keep one frame under ~0.2 s: precompute anything expensive at module
  level, outside `draw`.

## Canvas and style guidance

- Target a square canvas: 512×512 pixels for animated pieces, up to
  1024×1024 for static ones. (With matplotlib: e.g.
  `plt.subplots(figsize=(5.12, 5.12), dpi=100)`.)
- Transparent backgrounds are supported and encouraged — pieces float on
  the wall. With matplotlib set `fig.patch.set_facecolor("none")` and
  `ax.set_facecolor("none")`; with numpy/PIL return an RGBA array/image
  with alpha 0 where the piece paints nothing. An opaque background is also
  fine if the design calls for it.
- With matplotlib: hide axes (`ax.axis("off")`), fix limits explicitly
  (essential for animation so the view doesn't jitter between frames),
  keep `ax.set_aspect("equal")`, and use
  `fig.subplots_adjust(left=0, right=1, bottom=0, top=1)` so the art
  fills the frame.
- Aim for something visually striking on a large screen: bold shapes,
  rich color palettes, high contrast. Avoid text unless the design asks
  for it.

## Output format

Reply with ONLY the complete Python code for the piece — no explanations,
no markdown fences. Start with a one-line docstring naming the piece and
whether it is static or animated.

---8<--- copy up to here ---8<---
