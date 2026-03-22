"""Tests for authentication middleware and login/logout routes."""

import pytest
import pytest_asyncio

from app.csrf import generate_csrf_token
from app.services.settings_service import set_admin_password

_TEST_PASSWORD = "testpassword123"


@pytest_asyncio.fixture
async def seeded_client(client, db):
    """HTTP client with an admin password pre-seeded in the DB."""
    await set_admin_password(db, _TEST_PASSWORD)
    await db.commit()
    # Mark setup as complete so the middleware doesn't redirect to /setup or /setup/welcome
    from app.main import app

    app.state.needs_setup = False
    app.state.setup_completed = True
    return client


@pytest.mark.asyncio
async def test_login_page_accessible_without_auth(client):
    response = await client.get("/login", follow_redirects=False)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_protected_route_redirects_to_login(seeded_client):
    response = await seeded_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


@pytest.mark.asyncio
async def test_login_with_correct_password(seeded_client):
    response = await seeded_client.post(
        "/login",
        data={"password": _TEST_PASSWORD, "csrf_token": generate_csrf_token()},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "gatekeeper_session" in response.cookies


@pytest.mark.asyncio
async def test_login_with_wrong_password(seeded_client):
    response = await seeded_client.post(
        "/login",
        data={"password": "wrongpassword", "csrf_token": generate_csrf_token()},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Invalid password" in response.content


@pytest.mark.asyncio
async def test_login_without_csrf_token_rejected(seeded_client):
    response = await seeded_client.post(
        "/login",
        data={"password": _TEST_PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_logout_clears_session(seeded_client):
    # First login
    login_resp = await seeded_client.post(
        "/login",
        data={"password": _TEST_PASSWORD, "csrf_token": generate_csrf_token()},
        follow_redirects=False,
    )
    assert login_resp.status_code == 303

    # Then logout
    logout_resp = await seeded_client.get("/logout", follow_redirects=False)
    assert logout_resp.status_code == 302

    # Session cookie should be cleared (empty value or deleted)
    cookie = logout_resp.cookies.get("gatekeeper_session", "")
    assert cookie == ""


@pytest.mark.asyncio
async def test_static_files_accessible_without_auth(client):
    # /static is exempt from auth
    response = await client.get("/static/style.css", follow_redirects=False)
    # Should NOT redirect to login (may 200 or 404 depending on static setup, but not 302)
    assert response.status_code != 302
