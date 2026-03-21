"""Tests for authentication middleware and login/logout routes."""
import pytest

from app.csrf import generate_csrf_token


@pytest.mark.asyncio
async def test_login_page_accessible_without_auth(client):
    response = await client.get("/login", follow_redirects=False)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_protected_route_redirects_to_login(client):
    response = await client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


@pytest.mark.asyncio
async def test_login_with_correct_password(client):
    response = await client.post(
        "/login",
        data={"password": "admin", "csrf_token": generate_csrf_token()},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "gatekeeper_session" in response.cookies


@pytest.mark.asyncio
async def test_login_with_wrong_password(client):
    response = await client.post(
        "/login",
        data={"password": "wrongpassword", "csrf_token": generate_csrf_token()},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Invalid password" in response.content


@pytest.mark.asyncio
async def test_login_without_csrf_token_rejected(client):
    response = await client.post(
        "/login",
        data={"password": "admin"},
        follow_redirects=False,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_logout_clears_session(client):
    # First login
    login_resp = await client.post(
        "/login",
        data={"password": "admin", "csrf_token": generate_csrf_token()},
        follow_redirects=False,
    )
    assert login_resp.status_code == 303

    # Then logout
    logout_resp = await client.get("/logout", follow_redirects=False)
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
