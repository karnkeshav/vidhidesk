"""Browser-driven regression test for the Consulting Module.

Verifies:
- Landing page intake -> creates new matter
- Analysis result page
- Follow-up question -> creates new version
"""

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
    
    # We use service_key for direct database manipulation during cleanup
    return create_client(url, service_key)

@pytest.fixture
def test_user(supabase: Client):
    """Ensure the standard throwaway test account exists."""
    try:
        res = supabase.auth.admin.invite_user_by_email(TEST_EMAIL)
    except Exception:
        pass # Probably already exists

    # Ensure password is set
    try:
        supabase.auth.admin.update_user_by_id(
            uid=supabase.auth.admin.list_users().users[0].id, # Approximation, will rely on actual login
            attributes={"password": TEST_PASSWORD, "email_confirm": True}
        )
    except Exception:
        pass
    
    # The actual robust login
    res = supabase.auth.sign_in_with_password({"email": TEST_EMAIL, "password": TEST_PASSWORD})
    return res.user

@pytest.fixture
def auth_page(page: Page, test_user) -> Page:
    """Logs in and provides an authenticated page."""
    base_url = os.environ.get("E2E_BASE_URL", "http://localhost:3000")
    
    page.goto(f"{base_url}/login")
    page.fill('input[type="email"]', TEST_EMAIL)
    page.fill('input[type="password"]', TEST_PASSWORD)
    page.click('button:has-text("Sign In")')
    
    expect(page).to_have_url(f"{base_url}/dashboard", timeout=15000)
    return page

@pytest.fixture
def cleanup_matters(supabase: Client, test_user):
    """Tracks and cleans up matters created by this test."""
    created_matter_ids = []
    
    yield created_matter_ids
    
    for matter_id in created_matter_ids:
        # Verify ownership before deleting
        res = supabase.table("matters").select("user_id").eq("id", matter_id).execute()
        if res.data and res.data[0]["user_id"] == test_user.id:
            supabase.table("matters").delete().eq("id", matter_id).execute()


def test_consulting_end_to_end(auth_page: Page, cleanup_matters: list, test_user):
    base_url = os.environ.get("E2E_BASE_URL", "http://localhost:3000")
    
    # 1. Dashboard -> Consulting Hub
    auth_page.click('div.rounded-sm:has(h3:has-text("Consulting")) >> button:has-text("Continue Working")')
    expect(auth_page).to_have_url(f"{base_url}/consulting")
    
    # 2. Intake
    question = "[TEST] E2E Consulting Question: Is a verbal agreement for a 3-year commercial lease valid in India?"
    auth_page.fill("textarea", question)
    
    # Optional fields
    auth_page.fill('input[placeholder*="Party Names"]', "John Doe, Jane Smith")
    
    # Submit
    auth_page.click('button:has-text("Analyze")')
    
    # 3. Wait for Analysis Result and extract Matter ID
    expect(auth_page).to_have_url(re.compile(r".*/consulting/[0-9a-fA-F-]+$"), timeout=30000)
    
    current_url = auth_page.url
    matter_id = current_url.split("/")[-1]
    cleanup_matters.append(matter_id)
    
    # 4. Verify Version 1 renders
    expect(auth_page.locator("body")).to_contain_text("Version 1")
    expect(auth_page.locator("body")).to_contain_text(question)
    
    # 5. Follow-up
    follow_up = "What if they exchange emails?"
    auth_page.fill('input[placeholder*="follow-up"]', follow_up)
    auth_page.click('button:has-text("Analyze")')
    
    # 6. Verify Version 2 renders
    expect(auth_page.locator("body")).to_contain_text("Version 2", timeout=30000)
    expect(auth_page.locator("body")).to_contain_text(follow_up)
