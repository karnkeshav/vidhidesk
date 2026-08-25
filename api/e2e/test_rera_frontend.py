"""Browser-driven RERA Phase 3 validation.

Follows the exact fixture conventions established by test_consulting_frontend.py
(same TEST_EMAIL/TEST_PASSWORD E2E account, same auth_page login flow, same
service-role-client cleanup pattern) -- not modifying that file, just reusing
its conventions in a new, independent test module.

Verifies the real browser-facing RERA workflow: hub -> deed template
discovery/selection -> workspace load -> real draft generation (synthetic
data only) -> RERA Complaint workspace initialization. Every created matter
is tracked and deleted at teardown; no template/clause/state_rules row is
ever modified.

Historical-revisit coverage for RERA lives separately, in
api/e2e/test_rera_draft_revisit_download.py -- not duplicated here.
"""
import json
import os
import re
import pytest
from supabase import create_client, Client
from playwright.sync_api import Page, expect

TEST_EMAIL = "e2e-test@vidhidesk.local"
TEST_PASSWORD = "test-password-123"


@pytest.fixture(scope="session")
def supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    assert url and key and service_key, "SUPABASE credentials missing"
    return create_client(url, service_key)


@pytest.fixture
def test_user(supabase: Client):
    res = supabase.auth.sign_in_with_password({"email": TEST_EMAIL, "password": TEST_PASSWORD})
    return res.user


@pytest.fixture
def network_log(page: Page):
    """Records every /api/ request's method, path, status, and timing --
    used for the required network-forensics evidence, never logs headers
    (no bearer token ever captured)."""
    log = []

    def on_response(response):
        url = response.url
        if "/api/" not in url:
            return
        path = "/api/" + url.split("/api/", 1)[1]
        log.append({
            "method": response.request.method,
            "path": path,
            "status": response.status,
        })

    page.on("response", on_response)
    return log


@pytest.fixture
def auth_page(page: Page, test_user) -> Page:
    base_url = os.environ.get("E2E_BASE_URL", "http://localhost:3000")
    page.set_default_timeout(20000)
    page.goto(f"{base_url}/login")
    page.fill('input[type="email"]', TEST_EMAIL)
    page.fill('input[type="password"]', TEST_PASSWORD)
    page.click('button:has-text("Sign In")')
    expect(page).to_have_url(f"{base_url}/dashboard", timeout=15000)
    return page


@pytest.fixture
def cleanup_matters(supabase: Client, test_user):
    created_matter_ids = []
    yield created_matter_ids
    for matter_id in created_matter_ids:
        res = supabase.table("matters").select("user_id").eq("id", matter_id).execute()
        if res.data and res.data[0]["user_id"] == test_user.id:
            supabase.table("matters").delete().eq("id", matter_id).execute()


SYNTHETIC_FORM_DATA = {
    "gift-deed": {
        "text": {
            "donor_name": "E2E Test Donor", "donor_address": "1 E2E Lane, Delhi",
            "donee_name": "E2E Test Donee", "donee_address": "1 E2E Lane, Delhi",
            "relationship_with_donee": "parent and child",
            "property_description": "Synthetic E2E test property description, Delhi.",
            "title_background": "Synthetic E2E test title background.",
        },
        "date": {"possession_date": "2026-08-22", "execution_date": "2026-08-22"},
        "select": {"property_state": "Delhi"},
    },
    "mortgage-deed": {
        "text": {
            "mortgagor_name": "E2E Test Mortgagor", "mortgagor_address": "2 E2E Lane, Delhi",
            "mortgagee_name": "E2E Test Mortgagee", "mortgagee_address": "3 E2E Lane, Delhi",
            "property_description": "Synthetic E2E test property description, Delhi.",
            "principal_amount": "Rs. 5,00,000/-", "interest_rate": "10% per annum",
            "repayment_terms": "Synthetic E2E repayment terms.",
            "title_background": "Synthetic E2E test title background.",
        },
        "date": {"execution_date": "2026-08-22"},
        "select": {"property_state": "Delhi"},
    },
    "relinquishment-deed": {
        "text": {
            "releasor_name": "E2E Test Releasor", "releasor_address": "4 E2E Lane, Delhi",
            "releasee_name": "E2E Test Releasee", "releasee_address": "4 E2E Lane, Delhi",
            "relationship_context": "Synthetic E2E co-ownership context.",
            "property_description": "Synthetic E2E test property description, Delhi.",
            "share_relinquished": "undivided one-half share",
            "title_background": "Synthetic E2E test title background.",
        },
        "date": {"execution_date": "2026-08-22"},
        "select": {"property_state": "Delhi"},
    },
    "sale-deed": {
        "text": {
            "vendor_name": "E2E Test Vendor", "vendor_address": "5 E2E Lane, Delhi",
            "purchaser_name": "E2E Test Purchaser", "purchaser_address": "6 E2E Lane, Delhi",
            "property_description": "Synthetic E2E test property description, Delhi.",
            "sale_consideration_amount": "Rs. 1,00,000/-",
            "consideration_paid_details": "Synthetic E2E payment details.",
            "title_background": "Synthetic E2E test title background.",
        },
        "date": {"possession_date": "2026-08-22", "execution_date": "2026-08-22"},
        "select": {"property_state": "Delhi"},
    },
}

def _fill_deed_form(page: Page, template_key: str):
    """Fills by field `id` (== the schema's field `key`, always plain
    ASCII), not by label text. Deliberately robust against RERA-3's own
    finding: Sale Deed/RERA Complaint's stored schema_json has a
    pre-existing em-dash mojibake corruption in several label strings
    (see the phase report) -- label-text matching would be fragile
    against that, while the field `id` is untouched by it."""
    data = SYNTHETIC_FORM_DATA[template_key]
    for key, val in {**data["text"], **data["date"]}.items():
        page.locator(f"#{key}").fill(val)
    for key, val in data["select"].items():
        page.locator(f"#{key}").click()
        page.get_by_role("option", name=val, exact=True).click()


@pytest.mark.parametrize("template_key,template_name", [
    ("sale-deed", "Sale Deed"),
    ("gift-deed", "Gift Deed"),
    ("mortgage-deed", "Mortgage Deed"),
    ("relinquishment-deed", "Relinquishment Deed"),
])
def test_rera_deed_template_full_workflow(
    auth_page: Page, cleanup_matters: list, network_log: list, template_key, template_name
):
    base_url = os.environ.get("E2E_BASE_URL", "http://localhost:3000")

    # 1. Dashboard -> RERA hub
    auth_page.click('div.rounded-sm:has(h3:has-text("RERA")) >> button:has-text("Continue Working")')
    expect(auth_page).to_have_url(f"{base_url}/rera", timeout=20000)

    # 2. RERA hub -> Draft Property Deed
    auth_page.click('a[href="/rera/deeds"]')
    expect(auth_page).to_have_url(f"{base_url}/rera/deeds", timeout=20000)

    # 3. STEP 1: template appears in UI (waits out "Loading property templates…")
    card = auth_page.locator(f'div.flex.flex-col.justify-between:has(h3:has-text("{template_name}"))')
    expect(card).to_be_visible(timeout=20000)

    # 4. STEP 2/3: select it -- creates the matter, navigates with template state
    card.get_by_role("button", name="Start Drafting").click()
    expect(auth_page).to_have_url(re.compile(rf"{re.escape(base_url)}/rera/[0-9a-fA-F-]+$"), timeout=20000)
    matter_id = auth_page.url.rstrip("/").split("/")[-1]
    cleanup_matters.append(matter_id)

    # 5. STEP 4: workspace loads with the correct template's intake form
    expect(auth_page.get_by_role("heading", name=template_name, exact=False).first).to_be_visible(timeout=15000)

    # 6. STEP 6/7: fill synthetic data and generate a real draft
    _fill_deed_form(auth_page, template_key)
    auth_page.get_by_role("button", name="Generate draft").click()

    # 7. STEP 8: draft succeeds -- unambiguous signal only, NOT the footer's
    # always-present "Version {latestDraft?.version_no || '1.0'}" text
    # (substring-matches "Version 1" even before any draft exists -- a real
    # false positive caught during this phase's own validation, see report).
    # "Download .docx" only renders once `latestDraft` is actually set.
    expect(auth_page.get_by_role("button", name="Download .docx")).to_be_visible(timeout=120000)

    # STEP 5: network evidence -- the drafts POST must be present and 2xx
    draft_calls = [r for r in network_log if "/drafts" in r["path"] and r["method"] == "POST"]
    assert draft_calls, f"no POST .../drafts call observed for {template_key}"
    assert all(200 <= r["status"] < 300 for r in draft_calls), f"draft POST failed for {template_key}: {draft_calls}"

    template_calls = [r for r in network_log if r["path"].startswith("/api/templates") and r["method"] == "GET"]
    assert all(r["status"] == 200 for r in template_calls), f"a templates GET failed for {template_key}: {template_calls}"


def test_rera_complaint_workflow_initializes(auth_page: Page, cleanup_matters: list, network_log: list):
    base_url = os.environ.get("E2E_BASE_URL", "http://localhost:3000")

    auth_page.goto(f"{base_url}/rera/complaint/new")
    auth_page.click('button:has-text("Start Complaint Workspace")')

    # Must NOT show "template not found" -- and must actually navigate to a
    # real matter workspace within a reasonable time.
    expect(auth_page).to_have_url(re.compile(rf"{re.escape(base_url)}/rera/[0-9a-fA-F-]+$"), timeout=20000)
    matter_id = auth_page.url.rstrip("/").split("/")[-1]
    cleanup_matters.append(matter_id)

    expect(auth_page.locator("text=template not found")).to_have_count(0)
    expect(auth_page.get_by_role("heading", name="RERA Complaint", exact=False).first).to_be_visible(timeout=15000)

    template_calls = [r for r in network_log if r["path"].startswith("/api/templates") and r["method"] == "GET"]
    assert all(r["status"] == 200 for r in template_calls)
