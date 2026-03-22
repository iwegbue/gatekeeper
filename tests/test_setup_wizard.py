"""
Tests for the setup onboarding wizard (/setup/welcome … /setup/complete).

Covers:
- Each GET step renders the correct template
- POST /setup/ai saves provider settings
- POST /setup/plan with a template ID creates all rules
- POST /setup/plan with "scratch" creates no rules
- POST /setup/instruments adds and removes instruments
- POST /setup/complete marks setup_completed=True and redirects
- Auth middleware redirects to /setup/welcome when setup_completed=False
- Completed users bypass the wizard
- Skip links (AI, watchlist) advance without saving
"""
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.auth import SESSION_COOKIE, create_session_token
from app.csrf import generate_csrf_token
from app.main import app
from app.models.plan_rule import PlanRule
from app.models.settings import Settings
from app.services.plan_templates import get_template
from app.services.settings_service import set_admin_password

_TEST_PASSWORD = "wizardtest123"


def _inject_session(client) -> None:
    """Set a valid session cookie directly — avoids hitting the login rate limiter."""
    client.cookies.set(SESSION_COOKIE, create_session_token())


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def wizard_client(client, db):
    """
    Authenticated client with the admin password set and setup_completed=False.
    Mimics the state immediately after the password setup step: logged in,
    but onboarding not yet complete.
    """
    await set_admin_password(db, _TEST_PASSWORD)
    await db.commit()

    app.state.needs_setup = False
    app.state.setup_completed = False

    _inject_session(client)
    return client


@pytest_asyncio.fixture
async def completed_client(client, db):
    """
    Authenticated client with setup already completed.
    Used to verify completed users are not redirected back into the wizard.
    """
    await set_admin_password(db, _TEST_PASSWORD)
    await db.commit()

    app.state.needs_setup = False
    app.state.setup_completed = True

    _inject_session(client)
    return client


# ── Middleware redirect ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_middleware_redirects_to_welcome_when_setup_incomplete(wizard_client):
    """Authenticated users with setup_completed=False are redirected to /setup/welcome."""
    resp = await wizard_client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/setup/welcome")


@pytest.mark.asyncio
async def test_middleware_allows_dashboard_when_completed(completed_client):
    """Authenticated users with setup_completed=True reach the dashboard."""
    resp = await completed_client.get("/", follow_redirects=False)
    # Should NOT redirect to /setup/welcome
    assert resp.status_code == 200
    assert b"Dashboard" in resp.content


@pytest.mark.asyncio
async def test_setup_steps_exempt_from_middleware(wizard_client):
    """/setup/* paths are reachable even when setup is not complete."""
    resp = await wizard_client.get("/setup/welcome", follow_redirects=False)
    assert resp.status_code == 200


# ── Step 1: Welcome ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_welcome_page_renders(wizard_client):
    resp = await wizard_client.get("/setup/welcome")
    assert resp.status_code == 200
    assert b"Welcome to Gatekeeper" in resp.content


@pytest.mark.asyncio
async def test_welcome_redirects_when_completed(completed_client):
    resp = await completed_client.get("/setup/welcome", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


# ── Step 2: AI provider ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_page_renders(wizard_client):
    resp = await wizard_client.get("/setup/ai")
    assert resp.status_code == 200
    assert b"AI Provider" in resp.content


@pytest.mark.asyncio
async def test_ai_submit_saves_provider_and_redirects(wizard_client, db):
    resp = await wizard_client.post(
        "/setup/ai",
        data={
            "ai_provider": "openai",
            "openai_api_key": "sk-test-key",
            "anthropic_api_key": "",
            "ollama_base_url": "",
            "ai_model": "",
            "csrf_token": generate_csrf_token(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/setup/plan")

    result = await db.execute(select(Settings).limit(1))
    s = result.scalar_one()
    assert s.ai_provider == "openai"
    assert s.openai_api_key == "sk-test-key"


@pytest.mark.asyncio
async def test_ai_skip_goes_to_plan(wizard_client):
    """The skip link navigates directly to /setup/plan without a POST."""
    resp = await wizard_client.get("/setup/plan", follow_redirects=False)
    assert resp.status_code == 200


# ── Step 3: Trading plan ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plan_page_renders_templates(wizard_client):
    resp = await wizard_client.get("/setup/plan")
    assert resp.status_code == 200
    assert b"Trend Following" in resp.content
    assert b"Mean Reversion" in resp.content
    assert b"Start from scratch" in resp.content


@pytest.mark.asyncio
async def test_plan_submit_with_trend_following_creates_rules(wizard_client, db):
    tmpl = get_template("trend_following")
    expected_rule_count = len(tmpl["rules"])

    resp = await wizard_client.post(
        "/setup/plan",
        data={
            "template_id": "trend_following",
            "plan_name": "Trend Following Plan",
            "plan_description": "My trend following rules",
            "csrf_token": generate_csrf_token(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/setup/instruments")

    result = await db.execute(select(PlanRule))
    rules = result.scalars().all()
    assert len(rules) == expected_rule_count


@pytest.mark.asyncio
async def test_plan_submit_with_mean_reversion_creates_rules(wizard_client, db):
    tmpl = get_template("mean_reversion")
    expected_rule_count = len(tmpl["rules"])

    resp = await wizard_client.post(
        "/setup/plan",
        data={
            "template_id": "mean_reversion",
            "plan_name": "Mean Reversion Plan",
            "plan_description": "",
            "csrf_token": generate_csrf_token(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    result = await db.execute(select(PlanRule))
    rules = result.scalars().all()
    assert len(rules) == expected_rule_count


@pytest.mark.asyncio
async def test_plan_submit_scratch_creates_no_rules(wizard_client, db):
    resp = await wizard_client.post(
        "/setup/plan",
        data={
            "template_id": "scratch",
            "plan_name": "My Custom Plan",
            "plan_description": "",
            "csrf_token": generate_csrf_token(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    result = await db.execute(select(PlanRule))
    rules = result.scalars().all()
    assert len(rules) == 0


@pytest.mark.asyncio
async def test_plan_submit_unknown_template_treated_as_scratch(wizard_client, db):
    """An unrecognised template_id is silently treated as scratch."""
    resp = await wizard_client.post(
        "/setup/plan",
        data={
            "template_id": "nonexistent_template",
            "plan_name": "My Plan",
            "plan_description": "",
            "csrf_token": generate_csrf_token(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    result = await db.execute(select(PlanRule))
    rules = result.scalars().all()
    assert len(rules) == 0


# ── Step 4: Watchlist ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_instruments_page_renders(wizard_client):
    resp = await wizard_client.get("/setup/instruments")
    assert resp.status_code == 200
    assert b"Watchlist" in resp.content


@pytest.mark.asyncio
async def test_instruments_add_creates_instrument(wizard_client, db):
    resp = await wizard_client.post(
        "/setup/instruments",
        data={
            "symbol": "EURUSD",
            "display_name": "Euro / US Dollar",
            "asset_class": "FX",
            "csrf_token": generate_csrf_token(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert b"EURUSD" in resp.content


@pytest.mark.asyncio
async def test_instruments_symbol_upcased(wizard_client, db):
    resp = await wizard_client.post(
        "/setup/instruments",
        data={
            "symbol": "gbpusd",
            "display_name": "GBP/USD",
            "asset_class": "FX",
            "csrf_token": generate_csrf_token(),
        },
    )
    assert b"GBPUSD" in resp.content


@pytest.mark.asyncio
async def test_instruments_duplicate_symbol_ignored(wizard_client, db):
    """Submitting the same symbol twice does not create a duplicate."""
    data = {
        "symbol": "BTCUSD",
        "display_name": "Bitcoin/USD",
        "asset_class": "CRYPTO",
        "csrf_token": generate_csrf_token(),
    }
    await wizard_client.post("/setup/instruments", data=data)
    data["csrf_token"] = generate_csrf_token()
    resp = await wizard_client.post("/setup/instruments", data=data)

    # Only one list item for BTCUSD should appear
    assert resp.content.count(b"<strong>BTCUSD</strong>") == 1


@pytest.mark.asyncio
async def test_instruments_delete_removes_instrument(wizard_client, db):
    # Add
    await wizard_client.post(
        "/setup/instruments",
        data={
            "symbol": "XAUUSD",
            "display_name": "Gold",
            "asset_class": "FUTURES",
            "csrf_token": generate_csrf_token(),
        },
    )

    # Get the instrument ID from the DB
    from app.services import instrument_service
    inst = await instrument_service.get_by_symbol(db, "XAUUSD")
    assert inst is not None

    resp = await wizard_client.post(
        f"/setup/instruments/delete/{inst.id}",
        data={"csrf_token": generate_csrf_token()},
    )
    assert resp.status_code == 200
    assert b"XAUUSD" not in resp.content


# ── Step 5: Tour ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tour_page_renders(wizard_client):
    resp = await wizard_client.get("/setup/tour")
    assert resp.status_code == 200
    assert b"7-layer checklist" in resp.content


@pytest.mark.asyncio
async def test_tour_redirects_when_completed(completed_client):
    resp = await completed_client.get("/setup/tour", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


# ── Complete ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_sets_flag_and_redirects(wizard_client, db):
    resp = await wizard_client.post(
        "/setup/complete",
        data={"csrf_token": generate_csrf_token()},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] in ("/", "/?msg=Welcome+to+Gatekeeper")

    result = await db.execute(select(Settings).limit(1))
    s = result.scalar_one()
    assert s.setup_completed is True


@pytest.mark.asyncio
async def test_complete_updates_app_state(wizard_client, db):
    assert app.state.setup_completed is False

    await wizard_client.post(
        "/setup/complete",
        data={"csrf_token": generate_csrf_token()},
        follow_redirects=False,
    )
    assert app.state.setup_completed is True
