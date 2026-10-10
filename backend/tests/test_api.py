from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.main import create_app
from app.models import TasteProfile, UserProfile

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
ROOT = Path(__file__).resolve().parents[1]


def supabase_response(request):
    assert request.url == "https://test.supabase.co/auth/v1/user"
    assert request.headers["apikey"] == "test-public-key"
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    if token == "provider-down":
        return httpx.Response(503, json={"error": "unavailable"})
    if token not in ("user-a", "user-b", "anonymous", "unconfirmed", "malformed"):
        return httpx.Response(401, json={"error": "invalid token"})
    return httpx.Response(200, json={
        "id": USER_B if token == "user-b" else "invalid-id" if token == "malformed" else USER_A,
        "email": "b@example.com" if token == "user-b" else "a@example.com",
        "email_confirmed_at": None if token == "unconfirmed" else "2026-01-01T00:00:00Z",
        "is_anonymous": token == "anonymous",
        "user_metadata": {"full_name": "Muselly user"},
    })


@pytest.fixture
def database(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_engine(url, connect_args={"check_same_thread": False})
    yield engine, config
    engine.dispose()
    get_settings.cache_clear()


@pytest.fixture
def client(database, tmp_path):
    engine, _ = database
    settings = Settings(_env_file=None, supabase_url="https://test.supabase.co", supabase_publishable_key="test-public-key")
    app = create_app(settings, auth_transport=httpx.MockTransport(supabase_response), public_directory=tmp_path)

    def db_override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    with TestClient(app) as test_client:
        yield test_client


def headers(token="user-a"):
    return {"Authorization": f"Bearer {token}"}


def test_health_and_authentication(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    for route in ("/api/auth/me", "/api/taste-test"):
        assert client.get(route).status_code == 401
        for token in ("forged", "anonymous", "unconfirmed", "malformed"):
            assert client.get(route, headers=headers(token)).status_code == 401
    assert client.put("/api/taste-test", json={"selected_styles": ["romantic"]}).status_code == 401
    me = client.get("/api/auth/me", headers=headers())
    assert me.json() == {"id": USER_A, "email": "a@example.com", "display_name": "Muselly user"}
    assert me.headers["cache-control"] == "no-store"
    assert client.get("/api/auth/me", headers=headers("provider-down")).status_code == 503


def test_saved_answers_are_validated_and_isolated_by_verified_user(client, database):
    assert client.get("/api/taste-test", headers=headers()).json() == {"selected_styles": []}
    for styles in ([], ["unknown"], ["classic", "classic"], ["classic"] * 5):
        assert client.put("/api/taste-test", headers=headers(), json={"selected_styles": styles}).status_code == 422
    assert client.put("/api/taste-test", headers=headers(), json={"selected_styles": ["classic"], "user_id": USER_B}).status_code == 422
    saved = client.put("/api/taste-test", headers=headers(), json={"selected_styles": ["romantic", "casual"]})
    assert saved.status_code == 200
    assert client.get("/api/taste-test", headers=headers()).json() == {"selected_styles": ["romantic", "casual"]}
    assert client.get("/api/taste-test", headers=headers("user-b")).json() == {"selected_styles": []}
    client.put("/api/taste-test", headers=headers("user-b"), json={"selected_styles": ["chic"]})
    client.put("/api/taste-test", headers=headers(), json={"selected_styles": ["classic"]})
    assert client.get("/api/taste-test", headers=headers()).json() == {"selected_styles": ["classic"]}
    assert client.get("/api/taste-test", headers=headers("user-b")).json() == {"selected_styles": ["chic"]}
    with Session(database[0]) as db:
        assert len(db.scalars(select(UserProfile)).all()) == 2
        assert len(db.scalars(select(TasteProfile)).all()) == 2
        assert db.get(UserProfile, UUID(USER_A)).email == "a@example.com"


def test_migration_round_trip_and_model_consistency(database):
    engine, config = database
    assert set(inspect(engine).get_table_names()) == {"alembic_version", "muselly_user_profiles", "muselly_taste_profiles", "muselly_taste_tests", "muselly_inspiration_images"}
    command.check(config)
    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    command.upgrade(config, "head")
    assert "muselly_taste_profiles" in inspect(engine).get_table_names()


def test_missing_auth_configuration_blocks_private_routes():
    with TestClient(create_app(Settings(_env_file=None, supabase_url="", supabase_publishable_key=""))) as client:
        assert client.get("/api/auth/me", headers=headers()).status_code == 503


def test_serves_only_known_react_routes_and_assets(tmp_path):
    (tmp_path / "index.html").write_text("<main>React frontend</main>")
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "collage.png").write_bytes(b"collage")
    with TestClient(create_app(Settings(_env_file=None), public_directory=tmp_path)) as client:
        for route in ("/", "/sign-in", "/taste-test", "/dashboard", "/auth/callback"):
            assert client.get(route).status_code == 200
            assert client.get(route).text == "<main>React frontend</main>"
        assert client.get("/images/collage.png").content == b"collage"
        assert client.get("/api/unknown").status_code == 404
        assert client.get("/images/../.env").status_code == 404
