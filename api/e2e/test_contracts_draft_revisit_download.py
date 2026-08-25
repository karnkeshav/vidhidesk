"""Browser-driven regression test: a Contracts matter's draft state --
version badge, Download buttons, AND the document preview -- must survive
leaving and revisiting the workspace (not just the same session that
generated the draft).

Companion to api/e2e/test_rera_draft_revisit_download.py, which covers the
same class of defect for RERA. Both pages
(web/src/app/{contracts,rera}/[matterId]/page.tsx) share the identical
init()/latestDraft/latestDraftRef shape and the identical generic backend
(GET /api/drafts/{draft_version_id}/text -- see
app.routers.contracts.get_draft_text's own docstring for why it reads the
actual persisted .docx rather than reconstructing text from stored clause
data). Unlike the RERA test above -- written before that endpoint
existed -- this test also asserts the *preview* is actually restored, not
just Download/version, since getDraftText() is live for Contracts from the
same commit that adds this test.

Reads the actual persisted .docx server-side, no LLM call, no DB write.
Best-effort on the frontend: a getDraftText() failure must not remove the
already-known draft/version/download state (backed by latestDraftRef's
drafts[0] fallback) -- this is a structural guarantee of the implementation
(try/catch around the fetch, independent of the fallback), not something a
live round-trip E2E run can directly fault-inject without a network-level
mock this suite deliberately doesn't use (see test_no_auto_pdf_download.py
on why these tests talk to a real backend/Supabase project, not mocks).

NOT part of the fast `pytest tests/` suite (deliberately outside
`api/tests/` for that reason) -- needs BOTH dev servers running, a real
browser, and a live Supabase project with the NDA template seeded. Run
explicitly:

    # Terminal 1
    cd api && source .venv/bin/activate && uvicorn app.main:app --reload
    # Terminal 2
    cd web && npm run dev
    # Terminal 3
    cd api && source .venv/bin/activate
    python -m pytest e2e/test_contracts_draft_revisit_download.py -v

Set E2E_BASE_URL if the frontend isn't on the default localhost:3000.

Schema-driven per the project's own testing discipline (see
test_no_auto_pdf_download.py) -- fills from the NDA template's real, live
schema_json, not hand-picked field ids.

The matter title is never explicitly set (the app auto-titles it from the
template name) -- cleanup identifies rows purely by the exact matter id
captured from the URL right after creation, never by title/module/account,
same discipline as every other E2E test in this suite.
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

# A distinctive synthetic (non-real-person) party name -- interpolated
# verbatim into the NDA's fixed_boilerplate party-block clause (Jinja
# {{ party_a_name }}, not an LLM paraphrase target, unlike e.g. `purpose`),
# so it's a reliable, non-flaky marker that the restored preview carries
# real historical content rather than being merely non-empty.
SYNTHETIC_PARTY_A_NAME = "Synthetic E2E Revisit Test Party Alpha"


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


def _select_option(page, trigger_selector: str, option_text: str) -> None:
    page.click(trigger_selector)
    page.get_by_role("option", name=option_text, exact=True).click()


def _fill_field(page, field: dict) -> None:
    field_id = field["key"]
    ftype = field["type"]
    if field_id == "party_a_name":
        page.fill(f"#{field_id}", SYNTHETIC_PARTY_A_NAME)
    elif ftype == "date":
        page.fill(f"#{field_id}", "2026-08-01")
    elif ftype in ("text", "textarea"):
        page.fill(f"#{field_id}", "Synthetic E2E test value")
    elif ftype == "select":
        options = field.get("options") or []
        if not options:
            return
        first = options[0]
        label = first if isinstance(first, str) else first["label"]
        _select_option(page, f"#{field_id}", label)
    # boolean: left at its schema default. list: NDA has none.


def _fill_schema_driven_form(page, schema: dict) -> None:
    for field in schema["fields"]:
        if field.get("condition"):
            continue  # left at default; every boolean stays False
        if field["type"] == "list":
            continue  # NDA has none
        _fill_field(page, field)


@pytest.fixture(scope="module", autouse=True)
def ensure_test_user() -> str:
    return _ensure_test_user()


@pytest.fixture
def created_matter_ids(ensure_test_user: str):
    ids: list[str] = []
    yield ids
    for matter_id in ids:
        _cleanup_matter(matter_id, ensure_test_user)


def test_contracts_matter_revisit_restores_draft_state(created_matter_ids: list[str]):
    from playwright.sync_api import sync_playwright

    db = service_client()
    schema = db.table("templates").select("schema_json").eq("template_key", "nda").execute().data[0]["schema_json"]

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()

        page.goto(f"{BASE_URL}/login")
        page.wait_for_selector("text=VidhiDesk")
        page.fill("#email", TEST_EMAIL)
        page.fill("#password", TEST_PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_url("**/dashboard", timeout=15000)

        # 1. Contracts hub -> select NDA -> create matter.
        page.goto(f"{BASE_URL}/contracts")
        page.get_by_role("heading", name="Non-Disclosure Agreement", exact=True).click()
        page.get_by_role("button", name="Continue to Intake Form").click()
        page.wait_for_url("**/contracts/*", timeout=20000)
        matter_id = page.url.split("/contracts/")[-1].split("?")[0].rstrip("/")
        created_matter_ids.append(matter_id)

        # 2. Fill intake form and generate a real draft -- confirms a
        # draft/version exists before the revisit.
        page.wait_for_selector(f"text={schema['fields'][0]['label']}", timeout=15000)
        page.wait_for_timeout(500)  # let dev-mode hydration settle
        _fill_schema_driven_form(page, schema)

        page.click("text=Generate draft")
        # "Download .docx" is the unambiguous signal a draft actually
        # succeeded -- NOT the footer's always-present
        # "Version {latestDraftRef?.version_no || '1.0'}" text, which
        # substring-matches "Version 1" even before any draft exists.
        page.wait_for_selector("text=Download .docx", timeout=180000)
        page.wait_for_selector("text=Drafting Stage", state="detached", timeout=5000)

        # 3. Leave and revisit the matter fresh -- a full navigation, not
        # just React state carried over in the same session.
        page.goto(f"{BASE_URL}/contracts")
        page.wait_for_url(f"{BASE_URL}/contracts", timeout=15000)
        page.goto(f"{BASE_URL}/contracts/{matter_id}")
        page.wait_for_selector("text=Loading contract workspace", state="detached", timeout=20000)

        # 4. Version/badge restored -- must NOT show "Drafting Stage" now
        # that a real draft exists (latestDraftRef, backed by drafts[0]).
        page.wait_for_selector("text=Drafting Stage", state="detached", timeout=5000)

        # 5. Download remains available (latestDraftRef never depends on
        # getDraftText succeeding).
        page.wait_for_selector("text=Download .docx", timeout=15000)
        with page.expect_download(timeout=20000) as dl_info:
            page.click("text=Download .docx")
        download = dl_info.value
        path = download.path()
        assert path is not None, "download did not produce a local file"
        assert os.path.getsize(path) > 0, "downloaded .docx was empty"

        # 6. Preview actually restored via getDraftText() -- the distinctive
        # synthetic party name from the original intake form must be
        # visible in the re-rendered document body, proving the preview
        # carries real historical content, not a blank/placeholder state.
        page.wait_for_selector(f"text={SYNTHETIC_PARTY_A_NAME}", timeout=15000)

        browser.close()
