"""POST /submit guards: validation, size cap, rate limit, queue depth."""
from artwall import db
from artwall.config import Settings

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
    for field in ("code", "first_name", "last_name", "email"):
        form = {k: v for k, v in VALID_FORM.items() if k != field}
        resp = client.post("/submit", data=form, follow_redirects=False)
        assert resp.status_code == 422, field


def test_missing_consent_rejected(client):
    form = {"code": "def draw():\n    return [[0]]\n",
            "first_name": "Ada", "last_name": "Lovelace",
            "email": "ada@example.com"}
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


def test_a_shared_address_gets_the_whole_hall_through(make_client):
    """Venue wifi puts every attendee behind one public address, so the
    default ceiling has to clear a hall rather than a person. What stands
    between a flood and the booth is the queue-depth cap, not this."""
    client = make_client()
    assert client.settings.rate_limit_max == 60
    assert client.settings.rate_limit_window_s == 600
    for i in range(60):
        assert submit(client).status_code == 303, i
    assert submit(client).status_code == 429


def test_rate_limit_is_tunable_through_the_environment(monkeypatch):
    """A jammed booth is answered with a stack variable, not a commit."""
    for var in ("ARTWALL_RATE_LIMIT_MAX", "ARTWALL_RATE_LIMIT_WINDOW_S"):
        monkeypatch.delenv(var, raising=False)
    defaults = Settings.from_env()
    assert (defaults.rate_limit_max, defaults.rate_limit_window_s) == (60, 600)

    monkeypatch.setenv("ARTWALL_RATE_LIMIT_MAX", "5")
    monkeypatch.setenv("ARTWALL_RATE_LIMIT_WINDOW_S", "30")
    tuned = Settings.from_env()
    assert (tuned.rate_limit_max, tuned.rate_limit_window_s) == (5, 30)


def test_queue_depth_cap(make_client):
    client = make_client(max_queue_depth=2, rate_limit_max=100)
    assert submit(client).status_code == 303
    assert submit(client).status_code == 303
    assert submit(client).status_code == 429
