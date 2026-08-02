"""Browser-driven regression test: generating a Contracts draft must
never automatically trigger a PDF download.

Found live (Sprint 2, 2026-08-01): PDF export shells out to headless
LibreOffice (3-8s) and is a final artifact, not the working one — .docx
should be the only thing that happens without an explicit click. This
guards that regardless of the exact mechanism that produced the original
report (code review at the time found no auto-fire in the frontend; this
test exists so the question doesn't need re-litigating by hand again).

NOT part of the fast `pytest tests/` suite (deliberately outside
`api/tests/` for that reason) — needs BOTH dev servers running, a real
browser, and a live Supabase project with at least the NDA template
seeded. Run explicitly:

    # Terminal 1
    cd api && source .venv/bin/activate && uvicorn app.main:app --reload
    # Terminal 2
    cd web && npm run dev
    # Terminal 3
    cd api && source .venv/bin/activate && pip install playwright && playwright install chromium
    python -m pytest e2e/ -v

Set E2E_BASE_URL if the frontend isn't on the default localhost:3000
(e.g. a port picked because 3000 was already in use by another session).

In a sandboxed environment without normal system audio libraries,
Chromium may fail to launch with a missing libasound.so.2 error — see
docs/lessons_learned.md if that happens; it's an environment gap, not
a project one, and the workaround doesn't belong in normal setup docs.

Schema-driven per the project's own testing discipline (this is what
caught the StrictUndefined and "Fixed Fee" masking bugs): the form is
filled from the template's real, live `schema_json` (fetched directly
from Supabase, the same source the frontend renders from), not
hand-picked field IDs — so this test keeps working if NDA's schema
changes shape, and is reusable against any template whose required
fields are all unconditional (no per-field `condition`) and whose
required `list` fields need only one item to satisfy `min_items`.

The matter title is prefixed `[TEST] ` (see docs/lessons_learned.md's
process rule on this) so a later audit sweep of `matters`/
`draft_versions`/`clause_reviews` can filter test-created rows out of
Nitesh's real review history by title alone, without needing to join
through the throwaway auth user.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import service_client  # noqa: E402

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:3000")
TEST_EMAIL = "e2e-test@vidhidesk.local"
TEST_PASSWORD = "TestPassword123!"


def _ensure_test_user() -> None:
    """Create the throwaway test user if it doesn't already exist —
    makes this test self-sufficient on a fresh environment, not
    dependent on a user a prior manual session happened to leave behind."""
    db = service_client()
    try:
        db.auth.admin.create_user(
            {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
        )
    except Exception:  # noqa: BLE001 — already exists is the expected steady state
        pass


def _fetch_nda_schema() -> dict:
    db = service_client()
    rows = db.table("templates").select("schema_json").eq("template_key", "nda").execute().data
    if not rows:
        raise RuntimeError("NDA template not seeded — run scripts/seed_nda_template.py first")
    return rows[0]["schema_json"]


def _select_option(page, trigger_selector: str, option_text: str) -> None:
    page.click(trigger_selector)
    page.get_by_role("option", name=option_text, exact=True).click()


def _fill_field(page, field: dict, id_prefix: str = "") -> None:
    field_id = f"{id_prefix}{field['key']}"
    ftype = field["type"]
    if ftype == "date":
        page.fill(f"#{field_id}", "2026-08-01")
    elif ftype in ("text", "textarea"):
        page.fill(f"#{field_id}", "Test value for automated E2E coverage")
    elif ftype == "select":
        options = field.get("options") or []
        if not options:
            return
        first = options[0]
        label = first if isinstance(first, str) else first["label"]
        _select_option(page, f"#{field_id}", label)
    # boolean: left at its schema default (normally False) — avoids
    # needing to also satisfy whatever conditional fields it would reveal.
    # list: handled by _fill_schema_driven_form directly (needs the
    # Add-item button clicked first, not a plain fill).


def _fill_schema_driven_form(page, schema: dict) -> None:
    for field in schema["fields"]:
        if field.get("condition"):
            continue  # left at default; every boolean stays False, so nothing conditional is visible
        if field["type"] == "list":
            if (field.get("min_items") or 0) < 1:
                continue
            page.click(f"text=+ Add {field.get('item_singular_label', 'Item')}")
            for item_field in field.get("item_schema", []):
                if item_field.get("condition"):
                    continue
                _fill_field(page, item_field, id_prefix=f"{field['key']}-0-")
            continue
        _fill_field(page, field)


@pytest.fixture(scope="module", autouse=True)
def ensure_test_user():
    _ensure_test_user()


def test_generating_a_draft_never_auto_fetches_pdf():
    from playwright.sync_api import sync_playwright

    schema = _fetch_nda_schema()

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()

        pdf_requests: list[str] = []
        page.on(
            "request",
            lambda req: pdf_requests.append(req.url) if "download.pdf" in req.url else None,
        )

        page.goto(f"{BASE_URL}/login")
        page.wait_for_selector("text=VidhiDesk")
        page.fill("#email", TEST_EMAIL)
        page.fill("#password", TEST_PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_url("**/dashboard", timeout=15000)

        page.goto(f"{BASE_URL}/contracts")
        page.wait_for_selector("text=Non-Disclosure Agreement", timeout=15000)
        page.click("text=Non-Disclosure Agreement")
        page.wait_for_selector("#title", timeout=5000)
        page.fill("#title", "[TEST] no-auto-pdf regression check")
        page.click("text=Continue to intake form")
        page.wait_for_url("**/contracts/*", timeout=15000)
        page.wait_for_selector(f"text={schema['fields'][0]['label']}", timeout=15000)
        page.wait_for_timeout(500)  # let dev-mode hydration settle — see docs/lessons_learned.md

        _fill_schema_driven_form(page, schema)

        page.click("text=Generate draft")
        page.wait_for_selector("text=Draft — version 1", timeout=60000)

        # The actual assertion: give any wrongly-automatic PDF fetch a
        # real window to fire before declaring it absent.
        page.wait_for_timeout(3000)

        browser.close()

    assert pdf_requests == [], f"unexpected automatic PDF download request(s): {pdf_requests}"
