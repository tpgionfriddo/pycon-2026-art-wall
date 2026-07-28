"""Status endpoint lifecycle and moderation gating of the wall JSON."""
from artwall import db

from .conftest import submit


def test_status_endpoint_lifecycle(client, conn):
    submit(client)
    assert client.get("/api/submission/1").json()["status"] == "queued"

    db.claim_next_queued(conn)
    assert client.get("/api/submission/1").json()["status"] == "rendering"

    db.mark_rendered(conn, 1, "static", "1.png")
    body = client.get("/api/submission/1").json()
    assert body["status"] == "rendered"
    assert body["media_url"] == "/media/1.png"

    db.moderate(conn, 1, approved=True)
    assert client.get("/api/submission/1").json()["status"] == "approved"


def test_failed_submission_shows_error(client, conn):
    submit(client)
    db.claim_next_queued(conn)
    db.mark_failed(conn, 1, "NameError: draw is not defined")
    body = client.get("/api/submission/1").json()
    assert body["status"] == "failed"
    assert "NameError" in body["error"]


def test_status_unknown_id_404(client):
    assert client.get("/api/submission/999").status_code == 404


def test_status_page_renders(client):
    submit(client)
    resp = client.get("/submission/1")
    assert resp.status_code == 200


def test_wall_only_lists_approved(client, conn):
    submit(client)                       # 1: stays queued
    submit(client, name="Grace")         # 2: rendered, not moderated
    submit(client, name="Mary")          # 3: approved
    submit(client, name="Edsger")        # 4: rejected

    for sid in (2, 3, 4):
        conn.execute(
            "UPDATE submissions SET status='rendered', kind='static',"
            " media_path=? WHERE id=?", (f"{sid}.png", sid))
    conn.commit()
    db.moderate(conn, 3, approved=True)
    db.moderate(conn, 4, approved=False)

    pieces = client.get("/api/wall").json()["pieces"]
    assert [p["id"] for p in pieces] == [3]
    assert pieces[0]["name"] == "Mary"
    assert pieces[0]["media_url"] == "/media/3.png"
    assert pieces[0]["kind"] == "static"


def test_wall_json_has_no_contact_data(client, conn):
    submit(client)
    conn.execute("UPDATE submissions SET status='rendered', kind='static',"
                 " media_path='1.png' WHERE id=1")
    conn.commit()
    db.moderate(conn, 1, approved=True)
    piece = client.get("/api/wall").json()["pieces"][0]
    assert "email" not in piece
    assert "code" not in piece


def test_piece_page_only_for_approved(client, conn):
    submit(client)
    conn.execute("UPDATE submissions SET status='rendered', kind='static',"
                 " media_path='1.png' WHERE id=1")
    conn.commit()
    assert client.get("/piece/1").status_code == 404
    db.moderate(conn, 1, approved=True)
    resp = client.get("/piece/1")
    assert resp.status_code == 200
    assert "Ada Lovelace" in resp.text


def test_wall_page_renders(client):
    assert client.get("/wall").status_code == 200


def test_submission_page_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "pyodide" in resp.text.lower()
