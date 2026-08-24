"""Admin auth, moderation actions, CSV export."""
from artwall import db

from .conftest import AUTH, rendered, submit


def test_admin_requires_auth(client):
    assert client.get("/admin").status_code == 401
    assert client.get("/admin", auth=("booth", "wrong")).status_code == 401
    assert client.get("/admin", auth=AUTH).status_code == 200


def test_admin_api_routes_require_auth(client, conn):
    sid = rendered(client, conn)
    assert client.post(f"/admin/submissions/{sid}/approve",
                       follow_redirects=False).status_code == 401
    assert client.get("/admin/export.csv").status_code == 401


def test_approve_and_reject(client, conn):
    sid = rendered(client, conn)
    resp = client.post(f"/admin/submissions/{sid}/approve", auth=AUTH,
                       follow_redirects=False)
    assert resp.status_code == 303
    assert db.get_submission(conn, sid)["status"] == "approved"

    sid2 = rendered(client, conn, first_name="Grace", last_name="Hopper")
    client.post(f"/admin/submissions/{sid2}/reject", auth=AUTH,
                follow_redirects=False)
    assert db.get_submission(conn, sid2)["status"] == "rejected"


def test_moderation_only_touches_rendered(client, conn):
    submit(client)  # still queued
    client.post("/admin/submissions/1/approve", auth=AUTH,
                follow_redirects=False)
    assert db.get_submission(conn, 1)["status"] == "queued"


def test_csv_export_all_submissions(client, conn):
    submit(client)
    sid = rendered(client, conn, first_name="Grace", last_name="Hopper",
                   email="grace@example.com")
    db.moderate(conn, sid, approved=False)  # rejected rows are kept + exported

    resp = client.get("/admin/export.csv", auth=AUTH)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    lines = resp.text.strip().splitlines()
    assert lines[0].startswith("id,")
    assert len(lines) == 3
    assert "grace@example.com" in resp.text
    assert "rejected" in resp.text
