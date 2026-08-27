"""The punctuation the copy tickets removed, kept out.

15 took the em dashes out of the submit page, 17 did the same for status,
piece, terms and wall, and 18 finished the job on admin. That work has
already been silently undone once: 17 was finished on its own branch, and the
page it had cleaned was rewritten meanwhile, so the dashes and the retired
gradient both came back with no test to notice. This is ticket 18's own
verification grep, run by the suite instead of by hand.

Two rules of the house style are gated here and the third deliberately is
not. Em dashes and ellipsis characters are mechanical, so they are checked.
"No decorative glyphs" is not: it needs a judgement about whether a glyph is
carrying meaning, and the one live exception was ratified rather than
overlooked. The wall's approval message keeps its celebration glyph, the
terms page keeps a warning sign, and the AI prompt keeps an arrow and a
multiplication sign in technical notation. A gate here would have to list
them, which is a list of judgements pretending to be a rule.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ARTWALL = ROOT / "artwall"
TEMPLATES = ARTWALL / "templates"

BANNED = {"—": "an em dash", "…": "an ellipsis character"}

# The promoter's competition terms are somebody else's legal instrument,
# reproduced verbatim, so the house style deliberately stops at that block.
# Keyed on the template's own comment saying so rather than on `<main>`: the
# exemption should cover the quoted document and not every future paragraph
# that happens to be written inside the same tag.
VERBATIM_MARKER = "reproduced verbatim"


def _house_copy(path: Path) -> str:
    """The template's text, minus any block reproduced from elsewhere."""
    text = path.read_text()
    if VERBATIM_MARKER not in text:
        return text
    # From the comment that declares the quotation to the end of the element
    # holding it. Everything before the comment is ours and stays checked,
    # which is where house copy on such a page belongs. Prose added after the
    # declaration is inside the exemption and escapes this gate: that is the
    # cost of exempting a quoted block by position at all, and the guard test
    # below is what keeps the block from drifting into house copy unnoticed.
    declaration = text.rindex("<!--", 0, text.index(VERBATIM_MARKER))
    return text[:declaration] + text[text.index("</main>"):]


TEMPLATE_FILES = sorted(TEMPLATES.glob("*.html"))
# An empty parameter set is a skip, not a failure, so a moved or renamed
# templates directory would quietly retire this whole gate.
assert TEMPLATE_FILES, f"no templates found under {TEMPLATES}"


@pytest.mark.parametrize("path", TEMPLATE_FILES, ids=lambda p: p.name)
def test_no_template_reintroduces_the_removed_punctuation(path):
    copy = _house_copy(path)
    for character, name in BANNED.items():
        assert character not in copy, (
            f"{path.name} has {name}. Rewrite it as two sentences or a "
            f"colon, not a hyphen."
        )


def test_the_refusals_an_attendee_reads_follow_the_same_rules():
    """The templates are not the whole of the copy an attendee sees. A full
    queue and a tripped rate limit are both refusals shown to somebody
    standing at the booth, and they live in the server rather than in a
    template, which is how they kept punctuation the pages had lost.
    """
    source = (ARTWALL / "server.py").read_text()
    messages = re.findall(r'HTTPException\(\s*\d+,\s*"([^"]+)"', source)
    assert messages, "no HTTPException messages found to check"
    for message in messages:
        for character, name in BANNED.items():
            assert character not in message, f"{message!r} has {name}"


def test_the_runbook_quotes_the_refusals_it_tells_an_operator_to_match():
    """The runbook's symptom lines are quoted message text, so a reworded
    message leaves an operator matching against wording nobody will ever see.
    That drifted the moment those two messages were rewritten, which is why
    it is checked rather than remembered.
    """
    source = (ARTWALL / "server.py").read_text()
    runbook = (ROOT / "docs" / "RUNBOOK.md").read_text()
    refusals = re.findall(r'HTTPException\(\s*429,\s*"([^"]+)"', source)
    assert refusals, "no 429 refusals found to check"
    for message in refusals:
        assert message in runbook, (
            f"RUNBOOK does not quote {message!r}; an operator matching the "
            f"symptom would be looking for different words"
        )


def test_the_verbatim_exemption_still_describes_a_quoted_document():
    """The exemption above is only defensible while it covers text genuinely
    reproduced from elsewhere. Checked by weight as well as by marker: a
    single surviving heading would satisfy a spot-check of one string while
    the rest of the block had become house copy the gate no longer reads.
    """
    terms = (TEMPLATES / "terms.html").read_text()
    assert VERBATIM_MARKER in terms
    assert "Digital Artwork Competition" in terms
    assert "Aquion Pty Ltd" in terms
    exempted = len(terms) - len(_house_copy(TEMPLATES / "terms.html"))
    assert exempted > 2000, (
        f"only {exempted} characters are exempt; if the quoted document has "
        f"shrunk this far, the exemption has stopped earning its keep"
    )
