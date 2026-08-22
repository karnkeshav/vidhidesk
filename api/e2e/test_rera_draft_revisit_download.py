"""Browser-driven regression test: a RERA matter's Download buttons must
still work after leaving and revisiting the workspace (not just in the
same session that generated the draft).

Found live (RERA Phase 2E, 2026-08-22): `web/src/app/rera/[matterId]/page.tsx`
only ever set `latestDraft` (draft_version_id, version_no, full_text,
clause_fills) inside handleGenerate/handleAmend -- the page-load `init()`
effect calls listDrafts() (which does return a persisted draft's id/
version_no) but never wrote it into `latestDraft`. Result: a matter with a
real, correctly-persisted draft (draft_versions row + draft_clause_fills +
a real, non-empty .docx on disk) lost its Download .docx/.pdf buttons and
"Version N" badge entirely the moment the page was left and revisited --
even though the exact same draft downloads fine via the backend. Confirmed
with a direct repro before the fix (Playwright: generate, navigate to
BASE_URL + the same matter URL fresh, Download .docx button absent) and
after (button present, click produces a real, non-empty download).

The fix adds `latestDraftRef` -- `latestDraft` if present, else falls back
to `drafts[0]` (from the already-fetched listDrafts() result, ordered
newest-first) -- used only for the download buttons and version badge/
footer, which need nothing but draft_version_id + version_no. The document
*preview* pane (LegalDocumentSheet's fullText) still needs full_text, which
no existing endpoint provides outside handleGenerate/handleAmend's own
response -- deliberately left showing an empty preview on revisit; that is
a separate, known, unfixed gap (would need a new backend endpoint), not
covered by this test.

NOT part of the fast `pytest tests/` suite (deliberately outside
`api/tests/` for that reason) -- needs BOTH dev servers running, a real
browser, and a live Supabase project with the RERA deed templates seeded
(mortgage-deed, relinquishment-deed -- see
api/scripts/seed_mortgage_deed_template.py / seed_relinquishment_deed_template.py).
Run explicitly:

    # Terminal 1
    cd api && source .venv/bin/activate && uvicorn app.main:app --reload
    # Terminal 2
    cd web && npm run dev -- -p 3001
    # Terminal 3 (E2E_BASE_URL only needed if not on the default port 3000)
    cd api && source .venv/bin/activate
    E2E_BASE_URL=http://localhost:3001 python -m pytest e2e/test_rera_draft_revisit_download.py -v

Schema-driven per the project's own testing discipline (see
test_no_auto_pdf_download.py) -- fills from each template's real, live
schema_json, not hand-picked field ids, so this keeps working if a
schema's shape changes; both templates here have only
text/textarea/select/date fields (no `list`/`condition`), so the plain
field-filling loop is sufficient without needing the list/condition
handling test_no_auto_pdf_download.py's NDA form required.

The matter title this test creates is never explicitly set (the app
auto-titles it "New {template.name}") -- cleanup identifies rows purely
by the exact matter id captured from the URL right after creation (see
created_matter_ids below), same discipline as test_no_auto_pdf_download.py,
never by title/module/account.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import service_client  # noqa: E402

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:3000")
TEST_EMAIL = "e2e-test@vidhidesk.local"
TEST_PASSWORD = "TestPassword123!"

# Synthetic (non-real-person) intake values, reused across both templates —
# any key not present here falls back to a generic synthetic string.
SYNTHETIC_VALUES = {
    "mortgagor_name": "Ramesh Kumar Sharma (Synthetic Test Party)",
    "mortgagor_address": "123 Test Colony, New Delhi - 110001",
    "mortgagee_name": "Sunita Devi Verma (Synthetic Test Party)",
    "mortgagee_address": "456 Sample Nagar, Pune, Maharashtra - 411001",
    "principal_amount": "Rs. 20,00,000/- (Rupees Twenty Lakhs Only)",
    "interest_rate": "12% per annum",
    "repayment_terms": "60 equal monthly instalments (synthetic test data).",
    "title_background": "Acquired by registered sale deed dated 2020-01-01 (synthetic test data).",
    "property_description": "Plot No. 42, Block C, Test Layout, 200 sq. yards (synthetic test data).",
    "releasor_name": "Anita Kumari Singh (Synthetic Test Party)",
    "releasor_address": "789 Sample Vihar, Lucknow, Uttar Pradesh - 226001",
    "releasee_name": "Vikram Singh Rathore (Synthetic Test Party)",
    "releasee_address": "321 Test Enclave, New Delhi - 110002",
    "relationship_context": "Co-heirs of a common ancestor (synthetic test data).",
    "share_relinquished": "undivided one-third share (synthetic test data)",
}

MATTER_URL_RE = re.compile(r"/rera/[0-9a-fA-F-]{36}(\?.*)?$")


def _ensure_test_user() -> str:
    db = service_client()
    try:
        created = db.auth.admin.create_user(
            {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True}
        )
        return created.user.id
    except Exception:  # noqa: BLE001 — already exists is the expected steady state
        existing = next(u for u in db.auth.admin.list_users() if u.email == TEST_EMAIL)
        return existing.id


def _cleanup_matter(matter_id: str, e2e_user_id: str) -> None:
    db = service_client()
    rows = db.table("matters").select("id,user_id").eq("id", matter_id).limit(1).execute().data
    if not rows:
        print(f"[e2e cleanup] matter {matter_id} already gone — nothing to clean up")
        return
    owner_id = rows[0]["user_id"]
    if owner_id != e2e_user_id:
        print(
            f"[e2e cleanup] REFUSING to delete matter {matter_id}: owned by "
            f"{owner_id}, not the E2E test account ({e2e_user_id}) — failing closed"
        )
        return
    db.table("matters").delete().eq("id", matter_id).eq("user_id", e2e_user_id).execute()


def _fill_field(page, field: dict) -> None:
    field_id = field["key"]
    ftype = field["type"]
    if ftype == "date":
        page.fill(f"#{field_id}", "2026-08-01")
    elif ftype in ("text", "textarea"):
        page.fill(f"#{field_id}", SYNTHETIC_VALUES.get(field_id, "Synthetic E2E test value"))
    elif ftype == "select":
        options = field.get("options") or []
        if not options:
            return
        first = options[0]
        label = first if isinstance(first, str) else first["label"]
        page.click(f"#{field_id}")
        page.get_by_role("option", name=label, exact=True).click()


@pytest.fixture(scope="module", autouse=True)
def ensure_test_user() -> str:
    return _ensure_test_user()


@pytest.fixture
def created_matter_ids(ensure_test_user: str):
    ids: list[str] = []
    yield ids
    for matter_id in ids:
        _cleanup_matter(matter_id, ensure_test_user)


@pytest.mark.parametrize("template_key,card_label", [
    ("mortgage-deed", "Mortgage Deed"),
    ("relinquishment-deed", "Relinquishment Deed"),
])
def test_draft_download_survives_revisit(created_matter_ids: list[str], template_key: str, card_label: str):
    from playwright.sync_api import sync_playwright

    db = service_client()
    schema = db.table("templates").select("schema_json").eq("template_key", template_key).execute().data[0]["schema_json"]

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()

        page.goto(f"{BASE_URL}/login")
        page.wait_for_selector("text=VidhiDesk")
        page.fill("#email", TEST_EMAIL)
        page.fill("#password", TEST_PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_url("**/dashboard", timeout=15000)

        page.goto(f"{BASE_URL}/rera/deeds")
        page.wait_for_function("document.querySelectorAll(\"button\").length >= 6", timeout=20000)
        heading = page.get_by_role("heading", name=card_label, exact=True).first
        heading.wait_for(state="visible", timeout=10000)
        heading.locator("xpath=ancestor::div[contains(@class,'shadow-none')][1]//button").first.click()
        page.wait_for_url(MATTER_URL_RE, timeout=20000)
        matter_id = page.url.split("/rera/")[-1].split("?")[0].rstrip("/")
        created_matter_ids.append(matter_id)

        page.wait_for_selector("text=Loading contract workspace", state="detached", timeout=20000)
        page.wait_for_selector(f"text={schema['fields'][0]['label']}", timeout=15000)
        page.wait_for_timeout(500)
        for field in schema["fields"]:
            _fill_field(page, field)

        page.click("text=Generate draft")
        page.wait_for_selector("text=Download .docx", timeout=180000)

        # The actual regression: leave and revisit the matter fresh (a full
        # navigation, not just React state carried over in the same session).
        page.goto(f"{BASE_URL}/rera/{matter_id}")
        page.wait_for_selector("text=Loading contract workspace", state="detached", timeout=20000)

        page.wait_for_selector("text=Download .docx", timeout=15000)
        with page.expect_download(timeout=20000) as dl_info:
            page.click("text=Download .docx")
        download = dl_info.value
        path = download.path()
        assert path is not None, "download did not produce a local file"
        assert os.path.getsize(path) > 0, "downloaded .docx was empty"

        browser.close()
