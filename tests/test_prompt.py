"""The AI prompt page.

Served by the application rather than linked, because `docs/` is excluded
from the container images and the booth laptop is the one place the prompt is
needed.
"""


def test_the_prompt_is_served(client):
    page = client.get("/prompt").text
    assert "You are an expert Python creative coder." in page
    assert "Supported Packages" in page


def test_the_placeholder_reaches_the_page(client):
    """`{{DESIGN PROMPT}}` is what an attendee replaces, and it is also valid
    Jinja syntax, so it only survives because the block is raw."""
    assert "{{DESIGN PROMPT}}" in client.get("/prompt").text
