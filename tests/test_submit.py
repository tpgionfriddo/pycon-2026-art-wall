"""POST /submit guards: validation, size cap, rate limit, queue depth."""
from artwall import db

from .conftest import VALID_FORM, submit


def test_valid_submission_queues_and_redirects(client, conn):
    resp = submit(client)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/submission/1"
    row = db.get_submission(conn, 1)
    assert row["status"] == "queued"
    assert row["name"] == "Ada Lovelace"
    assert row["consent"] == 1


def test_missing_fields_rejected(client):
    for field in ("code", "name", "email"):
        form = {k: v for k, v in VALID_FORM.items() if k != field}
        resp = client.post("/submit", data=form, follow_redirects=False)
        assert resp.status_code == 422, field


def test_blank_name_rejected(client):
    assert submit(client, name="   ").status_code == 400


def test_missing_consent_rejected(client):
    form = {"code": "def draw():\n    return [[0]]\n",
            "name": "Ada", "email": "ada@example.com"}
    resp = client.post("/submit", data=form, follow_redirects=False)
    assert resp.status_code == 400


def test_code_size_cap(client, conn):
    big = "# " + "x" * (32 * 1024)
    assert submit(client, code=big).status_code == 413
    assert db.count_queued(conn) == 0


def test_rate_limit_per_ip(make_client):
    client = make_client(rate_limit_max=3)
    for _ in range(3):
        assert submit(client).status_code == 303
    assert submit(client).status_code == 429


def test_queue_depth_cap(make_client):
    client = make_client(max_queue_depth=2, rate_limit_max=100)
    assert submit(client).status_code == 303
    assert submit(client).status_code == 303
    assert submit(client).status_code == 429
