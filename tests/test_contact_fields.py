"""The contact fields the form collects: a split name, and two optional extras.

`name` stays the composed full name, because it is what the status page, the
admin list and the CSV export already show. First and last are stored as well
so the organisers can sort and greet by either. Phone and company are optional
and must survive being left blank, which is the common case at a booth.
"""
import sqlite3

from artwall import db

from .conftest import AUTH, VALID_FORM, approved, submit


def test_first_and_last_are_stored_and_composed_into_name(client, conn):
    submit(client, first_name="Ada", last_name="Lovelace")
    row = db.get_submission(conn, 1)
    assert row["first_name"] == "Ada"
    assert row["last_name"] == "Lovelace"
    assert row["name"] == "Ada Lovelace"


def test_surrounding_whitespace_is_stripped_before_composing(client, conn):
    submit(client, first_name="  Ada  ", last_name="  Lovelace  ")
    row = db.get_submission(conn, 1)
    assert row["first_name"] == "Ada"
    assert row["last_name"] == "Lovelace"
    assert row["name"] == "Ada Lovelace"


def test_first_and_last_name_are_both_required(client):
    assert submit(client, first_name="   ").status_code == 400
    assert submit(client, last_name="   ").status_code == 400


def test_phone_and_company_are_stored_when_given(client, conn):
    submit(client, phone="+44 7700 900123", company="Analytical Engines Ltd")
    row = db.get_submission(conn, 1)
    assert row["phone"] == "+44 7700 900123"
    assert row["company"] == "Analytical Engines Ltd"


def test_phone_and_company_are_optional(client, conn):
    form = {k: v for k, v in VALID_FORM.items()
            if k not in ("phone", "company")}
    resp = client.post("/submit", data=form, follow_redirects=False)
    assert resp.status_code == 303
    row = db.get_submission(conn, 1)
    assert row["phone"] == ""
    assert row["company"] == ""


def test_blank_phone_and_company_are_stored_as_empty_not_whitespace(client, conn):
    submit(client, phone="   ", company="   ")
    row = db.get_submission(conn, 1)
    assert row["phone"] == ""
    assert row["company"] == ""


def test_the_new_fields_reach_the_csv_export(client, conn):
    submit(client, first_name="Grace", last_name="Hopper",
           phone="555-0100", company="UNIVAC")
    resp = client.get("/admin/export.csv", auth=AUTH)
    header, row = resp.text.strip().splitlines()[:2]
    for column in ("first_name", "last_name", "phone", "company"):
        assert column in header.split(","), column
    for value in ("Grace", "Hopper", "555-0100", "UNIVAC"):
        assert value in row, value


def test_the_new_fields_never_reach_the_wall(client, conn):
    """The byline is the only credit that leaves the server (see test_byline).

    A phone number and an employer are exactly the kind of thing that must not
    follow a piece onto a big screen in a public hall.
    """
    approved(client, conn, first_name="Ada", last_name="Lovelace",
             phone="555-0100", company="Analytical Engines Ltd",
             byline="lovelace_dev")
    payload = client.get("/api/wall").text
    for leaked in ("555-0100", "Analytical Engines", "Ada", "Lovelace"):
        assert leaked not in payload, leaked


def test_the_form_offers_every_field(client):
    page = client.get("/").text
    for field in ("first_name", "last_name", "email", "phone", "company"):
        assert f'name="{field}"' in page, field


def test_phone_and_company_are_marked_optional_for_the_attendee(client):
    """Required and optional have to be tellable apart without submitting."""
    page = client.get("/").text
    assert 'name="phone"' in page and 'name="company"' in page
    # The two optional inputs must not carry the `required` attribute.
    for field in ("phone", "company"):
        start = page.index(f'name="{field}"')
        tag_start = page.rindex("<input", 0, start)
        tag_end = page.index(">", start)
        assert "required" not in page[tag_start:tag_end], field


def test_a_migrated_database_matches_a_fresh_one(tmp_path):
    """`db.APPENDED_COLUMNS` has to stay in SCHEMA's declaration order: it is
    the only thing keeping a booth laptop's migrated file identical to a fresh
    one, and nothing else would notice if the two drifted apart."""
    fresh = db.connect(tmp_path / "fresh.db")
    fresh_columns = [r["name"] for r in
                     fresh.execute("PRAGMA table_info(submissions)")]
    fresh.close()

    path = tmp_path / "migrated.db"
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
    old.commit()
    old.close()

    migrated = db.connect(path)
    migrated_columns = [r["name"] for r in
                        migrated.execute("PRAGMA table_info(submissions)")]
    migrated.close()

    assert migrated_columns == fresh_columns
    assert fresh_columns[-len(db.APPENDED_COLUMNS):] == list(db.APPENDED_COLUMNS)


def test_an_older_database_gains_the_new_columns_on_connect(tmp_path):
    """`_add_missing_columns` is the only migration step (see db.py), so a
    booth laptop carrying yesterday's file must not need a manual ALTER."""
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
                " created_at) VALUES ('c', 'Ada Lovelace', 'a@x', 1,"
                " '2026-08-24')")
    old.commit()
    old.close()

    for _ in range(2):                       # connecting twice must be safe
        conn = db.connect(path)
        row = db.get_submission(conn, 1)
        assert row["name"] == "Ada Lovelace"   # the old row is left alone
        assert row["first_name"] == ""
        assert row["last_name"] == ""
        assert row["phone"] == ""
        assert row["company"] == ""
        conn.close()
