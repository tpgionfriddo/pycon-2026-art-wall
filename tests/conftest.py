import pytest
from fastapi.testclient import TestClient

from artwall import db
from artwall.config import Settings
from artwall.server import create_app

ADMIN_PASSWORD = "hunter2"
AUTH = ("booth", ADMIN_PASSWORD)

VALID_FORM = {
    "code": "def draw():\n    return [[0]]\n",
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "consent": "on",
}


@pytest.fixture
def make_client(tmp_path):
    """Factory: TestClient over a fresh app + fresh SQLite in tmp_path."""
    clients = []

    def make(**overrides) -> TestClient:
        settings = Settings(
            data_dir=tmp_path, admin_password=ADMIN_PASSWORD, **overrides
        )
        client = TestClient(create_app(settings))
        client.settings = settings
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def conn(client):
    conn = db.connect(client.settings.db_path)
    yield conn
    conn.close()


def submit(client, **overrides):
    form = {**VALID_FORM, **overrides}
    return client.post("/submit", data=form, follow_redirects=False)
