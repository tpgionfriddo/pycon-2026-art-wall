"""The terms page. Consent rests on this text, so it has to exist and be
reachable from the control that accepts it.
"""
from .conftest import submit


def test_terms_page_resolves(client):
    resp = client.get("/terms")
    assert resp.status_code == 200
    assert "terms" in resp.text.lower()


def test_terms_page_is_an_unmistakable_placeholder(client):
    """Until ticket 13 pastes the real text, nobody may mistake it for done."""
    assert "PLACEHOLDER" in client.get("/terms").text


def test_submission_form_links_to_the_terms(client):
    assert 'href="/terms"' in client.get("/").text


def test_acceptance_is_still_required(client):
    form = {"code": "def draw():\n    return [[0]]\n",
            "first_name": "Ada", "last_name": "Lovelace",
            "email": "ada@example.com", "byline": "Ada"}
    assert client.post("/submit", data=form,
                       follow_redirects=False).status_code == 400
    assert submit(client).status_code == 303
