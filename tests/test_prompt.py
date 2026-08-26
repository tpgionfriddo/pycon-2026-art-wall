"""The AI prompt page.

Served by the application rather than linked, because `docs/` is excluded
from the container images and the booth laptop is the one place the prompt is
needed.
"""
from artwall.config import SUPPORTED_PACKAGES


def test_the_prompt_is_served(client):
    page = client.get("/prompt").text
    assert "You are an expert Python creative coder." in page
    assert "Supported Packages" in page


def test_the_placeholder_reaches_the_page(client):
    """`{{DESIGN PROMPT}}` is what an attendee replaces, and it is also valid
    Jinja syntax, so it only survives because the block is raw."""
    assert "{{DESIGN PROMPT}}" in client.get("/prompt").text


def test_the_prompt_names_exactly_the_supported_packages(client):
    """The prompt hardcodes the package list, because it is quoted verbatim
    and an attendee pastes it into a chat model. ADR-0001 makes drift between
    the preview, the worker and this list the failure that matters, and this
    is the only thing holding the third copy in step.
    """
    page = client.get("/prompt").text
    for package in SUPPORTED_PACKAGES:
        assert f"`{package}`" in page, package


def test_the_prompt_does_not_send_a_reader_into_a_second_submit_page(client):
    """Opened in a new tab for the same reason the terms are, and so carrying
    the same trap: see the matching test in `test_terms.py`.
    """
    assert 'href="/"' not in client.get("/prompt").text
