"""The terms page. Consent rests on this text, so it has to exist and be
reachable from the control that accepts it.
"""
import re

from .conftest import links_home, submit


def test_terms_page_resolves(client):
    resp = client.get("/terms")
    assert resp.status_code == 200
    assert "terms" in resp.text.lower()


def test_terms_page_carries_the_real_competition_terms(client):
    """The inverse of the gate this test used to hold: the supplied wording is
    in place, so the placeholder warning must be gone."""
    page = client.get("/terms").text
    assert "Aquion Pty Ltd" in page
    assert "ABN 57 094 985 136" in page
    assert "PLACEHOLDER" not in page


def test_submission_form_links_to_the_terms(client):
    assert 'href="/terms"' in client.get("/").text


def test_acceptance_is_still_required(client):
    form = {"code": "def draw():\n    return [[0]]\n",
            "first_name": "Ada", "last_name": "Lovelace",
            "email": "ada@example.com", "byline": "Ada"}
    assert client.post("/submit", data=form,
                       follow_redirects=False).status_code == 400
    assert submit(client).status_code == 303


def _consent_sentence(page: str) -> str:
    """The consent label's prose, tags stripped and whitespace collapsed.

    Asserted on the rendered sentence rather than the markup because the
    sentence wraps across source lines, and the thing that matters to an
    attendee is what they read.
    """
    label = re.search(r'<label class="consent">(.*?)</label>', page, re.S).group(1)
    label = re.sub(r"<!--.*?-->", "", label, flags=re.S)
    # Tags drop out rather than becoming spaces: the markup deliberately puts
    # no whitespace before the full stop, and this must not invent any.
    return " ".join(re.sub(r"<[^>]+>", "", label).split())


def test_consent_names_both_documents(client):
    page = client.get("/").text
    assert _consent_sentence(page) == \
        "I accept the terms and conditions and the privacy policy."


def test_both_consent_documents_open_in_a_new_tab(client):
    """Losing the editor buffer to a legal document is not acceptable."""
    page = client.get("/").text
    for href in ('/terms', 'https://www.aquion.com.au/privacy'):
        link = re.search(rf'<a\s+href="{re.escape(href)}"[^>]*>', page, re.S).group(0)
        assert 'target="_blank"' in link
        assert 'rel="noopener"' in link


def test_moderation_is_disclosed_before_the_details_are_handed_over(client):
    """Beside the tickbox, and word for word the sentence the instructions
    carry. Asserting only that each is present would pass if one drifted."""
    page = " ".join(client.get("/").text.split())
    sentence = "Pieces are moderated before they appear on the wall."
    note = re.search(r'<span id="moderation-note">(.*?)</span>', page).group(1)
    assert note == sentence
    instructions = re.findall(rf'<p>{re.escape(sentence)}</p>', page)
    assert len(instructions) == 2, "the modal and the panel each carry it once"


def test_the_terms_do_not_send_a_reader_into_a_second_submit_page(client):
    """The consent link opens `/terms` in a new tab, so the submit page is
    still sitting behind it holding the editor buffer, the booted runtime and
    the preview that armed the submit button. A link back to `/` from here
    loads a fresh, empty submit page in this tab instead of returning anyone
    anywhere, leaving two submit tabs and a guess about which one has the
    work in it. Closing the tab is the way back.
    """
    assert links_home(client.get("/terms").text) == []


def _clauses(page: str) -> list[str]:
    return re.findall(r"<li>(.*?)</li>", page, re.S)


def test_the_terms_carry_every_clause_of_the_supplied_instrument(client):
    """The promoter's document is seventeen numbered clauses in six sections.
    It was first transcribed as unnumbered paragraphs, and clause 13 was left
    out of it without anything noticing, which is the argument for both the
    numbering and this test.
    """
    page = client.get("/terms").text
    assert len(_clauses(page)) == 17
    starts = [int(n) for n in re.findall(r'<ol start="(\d+)">', page)]
    assert starts == [1, 4, 7, 10, 14, 15], "the count must run unbroken 1 to 17"
    assert page.count("<h3>") == 6


def test_the_marketing_consent_clause_is_on_the_page(client):
    """Clause 13 is what the contact list's marketing use rests on. The booth
    exists to build that list, so this clause going missing would quietly
    invalidate the thing the whole activity is for.
    """
    page = " ".join(client.get("/terms").text.split())
    assert ("Entrants consent to their contact details being utilised for "
            "marketing purposes by Aquion.") in page
