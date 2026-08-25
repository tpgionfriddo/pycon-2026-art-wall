"""The moderation page keeping itself current without a manual reload.

A moderator at the booth is looking at the page, not at the browser's reload
button: submissions that finish rendering while they stand there have to arrive
on their own. What the page must not do is move — or throw away a source view
they are reading — at the moment they reach for Approve or Reject.

The poll's decisions live in the page's own script, which no test here can
run. What is tested is the contract underneath it: what the server reports,
and what the page publishes for the script to compare that against.
"""
from datetime import datetime, timedelta, timezone

from artwall import db

from .conftest import AUTH, approved, rendered, submit

STATE_URL = "/admin/api/moderation"


def _ids(body: str, attribute: str) -> list[int]:
    """The ids the page says it rendered into one of its two card grids."""
    marker = f'data-{attribute}="'
    value = body.split(marker, 1)[1].split('"', 1)[0]
    return [int(part) for part in value.split(",") if part]


def _queued_since(client, conn, minutes: int) -> None:
    """Backdate a fresh submission's arrival, as a stalled queue would."""
    location = submit(client).headers["location"]
    when = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    conn.execute("UPDATE submissions SET created_at = ? WHERE id = ?",
                 (when.isoformat(timespec="seconds"),
                  int(location.rsplit("/", 1)[1])))
    conn.commit()


def test_the_refresh_endpoint_requires_the_admin_password(client):
    assert client.get(STATE_URL).status_code == 401
    assert client.get(STATE_URL, auth=("booth", "wrong")).status_code == 401
    assert client.get(STATE_URL, auth=AUTH).status_code == 200


def test_it_reports_the_two_card_grids_and_the_header(client, conn):
    waiting = rendered(client, conn)
    on_wall = approved(client, conn)
    submit(client)                                    # queued, in neither grid

    state = client.get(STATE_URL, auth=AUTH).json()
    assert state["pending"] == [waiting]
    assert state["on_wall"] == [on_wall]
    assert state["counts"]["queued"] == 1
    assert state["counts"]["rendered"] == 1
    assert state["counts"]["approved"] == 1
    assert state["oldest_wait"] == "under a minute"


def test_an_empty_queue_reports_no_wait(client, conn):
    """The page drops the signal when this goes away, so it has to go away."""
    approved(client, conn)
    assert client.get(STATE_URL, auth=AUTH).json()["oldest_wait"] is None


def test_a_stalled_queue_shows_up_without_reloading_the_page(client, conn):
    _queued_since(client, conn, minutes=25)
    assert client.get(STATE_URL, auth=AUTH).json()["oldest_wait"] == "25 min"


def test_moderating_moves_a_submission_between_the_reported_grids(client, conn):
    sid = rendered(client, conn)
    state = client.get(STATE_URL, auth=AUTH).json()
    assert (state["pending"], state["on_wall"]) == ([sid], [])

    client.post(f"/admin/submissions/{sid}/approve", auth=AUTH,
                follow_redirects=False)
    state = client.get(STATE_URL, auth=AUTH).json()
    assert (state["pending"], state["on_wall"]) == ([], [sid])

    client.post(f"/admin/submissions/{sid}/takedown", auth=AUTH,
                follow_redirects=False)
    state = client.get(STATE_URL, auth=AUTH).json()
    assert (state["pending"], state["on_wall"]) == ([], [])


def test_a_rejected_submission_is_reported_in_neither_grid(client, conn):
    sid = rendered(client, conn)
    client.post(f"/admin/submissions/{sid}/reject", auth=AUTH,
                follow_redirects=False)
    state = client.get(STATE_URL, auth=AUTH).json()
    assert (state["pending"], state["on_wall"]) == ([], [])


def test_the_page_publishes_the_ids_it_rendered(client, conn):
    """Without this the poll has nothing to compare against, and every reply
    either looks like a change or like none."""
    waiting = rendered(client, conn)
    on_wall = approved(client, conn)

    body = client.get("/admin", auth=AUTH).text
    assert _ids(body, "pending") == [waiting]
    assert _ids(body, "on-wall") == [on_wall]


def test_the_published_ids_are_empty_on_an_empty_page(client):
    body = client.get("/admin", auth=AUTH).text
    assert _ids(body, "pending") == []
    assert _ids(body, "on-wall") == []


def test_a_new_submission_is_reported_after_the_ones_already_drawn(client,
                                                                  conn):
    """The page reloads unasked only when every card it is showing keeps its
    place, which it works out by position. Both halves of that comparison have
    to arrive oldest-first for it to hold.
    """
    first = rendered(client, conn)
    second = rendered(client, conn)
    assert client.get(STATE_URL, auth=AUTH).json()["pending"] == [first,
                                                                 second]
    assert _ids(client.get("/admin", auth=AUTH).text, "pending") == [first,
                                                                    second]


def test_the_page_publishes_a_hook_for_every_count(client):
    """The poll writes the numbers back into these; without the hooks the
    header silently freezes at whatever it was rendered with."""
    body = client.get("/admin", auth=AUTH).text
    for status in db.STATUSES:
        assert f'data-count="{status}"' in body


def test_the_header_wording_is_not_spelled_twice(client):
    """The poll must not carry its own copy of the header's words: a queue
    that is empty says nothing, and a script saying it anyway is still there
    in the page for anyone reading the source."""
    submit(client)
    body = client.get("/admin", auth=AUTH).text
    assert body.count("oldest queued") == 1


def test_the_page_carries_a_refresh_link_it_keeps_hidden(client):
    """A held-back reload has to be visible and clickable, and the click must
    not need the script that revealed it."""
    body = client.get("/admin", auth=AUTH).text
    assert 'id="notice"' in body
    assert 'href="/admin"' in body
    assert "hidden" in body.split('id="notice"', 1)[1].split(">", 1)[0]


def test_the_page_no_longer_asks_the_moderator_to_reload(client):
    body = client.get("/admin", auth=AUTH).text
    assert "does not auto-refresh" not in body
    assert "reload for new pieces" not in body


def test_the_page_polls_the_refresh_endpoint(client):
    assert STATE_URL in client.get("/admin", auth=AUTH).text
