"""The byline: attendee-controlled credit, and the only name the wall shows.

The privacy assertions here are the point of the feature — a cleared byline
has to mean the contact name and email appear nowhere attendee-facing.
"""
import json
import sqlite3

from artwall import db

from .conftest import AUTH, approved, submit


def test_byline_is_stored_separately_from_the_contact_name(client, conn):
    submit(client, first_name="Ada", last_name="Lovelace",
           byline="lovelace_dev")
    row = db.get_submission(conn, 1)
    assert row["name"] == "Ada Lovelace"
    assert row["byline"] == "lovelace_dev"


def test_byline_defaults_to_empty_when_the_form_omits_it(client, conn):
    client.post("/submit", data={"code": "def draw():\n    return [[0]]\n",
                                 "first_name": "Ada",
                                 "last_name": "Lovelace",
                                 "email": "ada@example.com",
                                 "consent": "on"}, follow_redirects=False)
    assert db.get_submission(conn, 1)["byline"] == ""


def test_a_handle_credits_the_piece_by_that_handle(client, conn):
    approved(client, conn, first_name="Ada", last_name="Lovelace",
             byline="lovelace_dev")
    piece = client.get("/api/wall").json()["pieces"][0]
    assert piece["byline"] == "lovelace_dev"
    assert "lovelace_dev" in client.get("/piece/1").text


def test_cleared_byline_puts_no_name_on_the_wall(client, conn):
    approved(client, conn, first_name="Ada", last_name="Lovelace",
             byline="")
    piece = client.get("/api/wall").json()["pieces"][0]
    assert piece["byline"] is None


def test_cleared_byline_puts_no_name_on_the_piece_page(client, conn):
    approved(client, conn, first_name="Ada", last_name="Lovelace",
             byline="   ")
    body = client.get("/piece/1").text
    assert "Ada Lovelace" not in body
    assert "ada@example.com" not in body
    # Not a placeholder label either — no "by" credit line at all.
    assert "Anonymous" not in body
    assert ">by<" not in body


def test_contact_data_never_reaches_the_wall_whatever_the_byline(client, conn):
    for byline in ("lovelace_dev", "", "Ada Lovelace"):
        submit(client, first_name="Ada", last_name="Lovelace",
               email="ada@example.com", byline=byline)
    for sid in (1, 2, 3):
        db.claim_next_queued(conn)
        db.mark_rendered(conn, sid, "static", f"{sid}.png")
        db.moderate(conn, sid, approved=True)

    payload = json.dumps(client.get("/api/wall").json())
    assert "ada@example.com" not in payload
    assert '"name"' not in payload
    assert '"email"' not in payload
    assert '"code"' not in payload
    # The byline the attendee chose may of course equal their name.
    assert payload.count("Ada Lovelace") == 1


def test_moderation_queue_shows_the_byline_beside_the_contact_name(client, conn):
    submit(client, first_name="Ada", last_name="Lovelace",
           byline="lovelace_dev")
    row = db.claim_next_queued(conn)
    db.mark_rendered(conn, row["id"], "static", "1.png")
    body = client.get("/admin", auth=AUTH).text
    assert "Ada Lovelace" in body
    assert "lovelace_dev" in body


def test_csv_export_gains_a_byline_column(client, conn):
    submit(client, first_name="Ada", last_name="Lovelace",
           email="ada@example.com", byline="lovelace_dev")
    resp = client.get("/admin/export.csv", auth=AUTH)
    header, first = resp.text.strip().splitlines()[:2]
    assert "byline" in header.split(",")
    # The existing columns are untouched.
    assert header.split(",")[:6] == ["id", "name", "email", "consent",
                                     "created_at", "status"]
    assert "lovelace_dev" in first
    assert "Ada Lovelace" in first
    assert "ada@example.com" in first


def test_submission_form_offers_a_byline_field(client):
    assert 'name="byline"' in client.get("/").text


def test_database_created_before_the_byline_opens_and_gains_the_column(tmp_path):
    """The migration is idempotent: an old database keeps its rows."""
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL,
            consent INTEGER NOT NULL, created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            kind TEXT, media_path TEXT, error TEXT,
            rendered_at TEXT, moderated_at TEXT
        );
    """)
    old.execute("INSERT INTO submissions (code, name, email, consent,"
                " created_at) VALUES ('c', 'Ada', 'a@x', 1, '2026-08-24')")
    old.commit()
    old.close()

    for _ in range(2):                       # connecting twice must be safe
        conn = db.connect(path)
        row = db.get_submission(conn, 1)
        assert row["name"] == "Ada"
        assert row["byline"] == ""
        conn.close()
