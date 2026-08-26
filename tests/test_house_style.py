"""The punctuation the copy tickets removed, kept out.

15 took the em dashes out of the submit page, 17 did the same for status,
piece, terms and wall, and 18 finished the job on admin. That work has
already been silently undone once: 17 was finished on its own branch, and
the page it had cleaned was rewritten meanwhile, so the dashes and the
retired gradient both came back with no test to notice. This is ticket 18's
own verification grep, run by the suite instead of by hand.
"""
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "artwall" / "templates"

# The promoter's competition terms are somebody else's legal instrument,
# reproduced verbatim, so the house style deliberately stops at that block.
# The comment above it in the template says so, and is what this points at.
VERBATIM = {"terms.html": ("<main>", "</main>")}

BANNED = {"—": "an em dash", "…": "an ellipsis character"}


def _house_copy(path: Path) -> str:
    """The template's text, minus any block reproduced from elsewhere."""
    text = path.read_text()
    if path.name in VERBATIM:
        opening, closing = VERBATIM[path.name]
        start, end = text.index(opening), text.index(closing)
        text = text[:start] + text[end:]
    return text


@pytest.mark.parametrize("path", sorted(TEMPLATES.glob("*.html")), ids=lambda p: p.name)
def test_no_template_reintroduces_the_removed_punctuation(path):
    copy = _house_copy(path)
    for character, name in BANNED.items():
        assert character not in copy, (
            f"{path.name} has {name}. Rewrite it as two sentences or a "
            f"colon, not a hyphen."
        )


def test_the_supplied_terms_are_exempt_and_still_present():
    """The exemption above is only defensible while it covers a real verbatim
    document. If that block ever loses its own punctuation the exemption has
    stopped describing anything and should go.
    """
    terms = (TEMPLATES / "terms.html").read_text()
    assert "reproduced verbatim" in terms
    assert "Digital Artwork Competition — Terms &amp; Conditions" in terms
