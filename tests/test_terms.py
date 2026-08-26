"""The terms page. Consent rests on this text, so it has to exist and be
reachable from the control that accepts it.
"""
import re

from .conftest import submit


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
    """Kept identical to the arrival modal's sentence."""
    page = client.get("/").text
    assert "Pieces are moderated before they appear on the wall." in \
        " ".join(page.split())
