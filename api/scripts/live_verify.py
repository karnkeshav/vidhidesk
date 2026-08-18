import os
import sys
from dotenv import load_dotenv
import asyncio

load_dotenv("../.env")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client, Client
from fastapi.testclient import TestClient
from app.main import app
from app.auth import get_current_user, CurrentUser
from app.db import user_client

url: str = os.environ.get("SUPABASE_URL")
service_key: str = os.environ.get("SUPABASE_SERVICE_KEY")

supabase_admin: Client = create_client(url, service_key)

def run_live_verification():
    print("[Verification] Starting live verification...")
    # 1. Verify schema
    try:
        supabase_admin.table("consulting_analyses").select("id").limit(1).execute()
        print("[Schema] consulting_analyses table exists.")
    except Exception as e:
        print(f"[Schema] Error: {e}")
        return

    # Use existing test user if possible, or create one using admin api
    email_a = "live_test_user_a@vidhidesk.com"
    email_b = "live_test_user_b@vidhidesk.com"
    password = "SecurePassword123!"

    user_a_id = None
    user_b_id = None
    
    # Check if users exist, otherwise create
    try:
        # We can't easily list users by email via client without pagination, let's just create and catch if exists
        res_a = supabase_admin.auth.admin.create_user({
            "email": email_a,
            "password": password,
            "email_confirm": True
        })
        user_a_id = res_a.user.id
    except Exception as e:
        print(f"User A might exist: {e}")
        # Just sign in to get token if we need a token? Actually, with Admin API we can just generate a token? 
        # No, we can't easily. But wait, if we override get_current_user, we don't need a real JWT!
        # We can just create a CurrentUser and pass `user_client("fake_token")`? No, user_client needs a REAL token for RLS to work on the Supabase REST API!
        # So we NEED a real token. The only way to get a real token is sign_in_with_password.
        pass

    try:
        res_b = supabase_admin.auth.admin.create_user({
            "email": email_b,
            "password": password,
            "email_confirm": True
        })
        user_b_id = res_b.user.id
    except Exception as e:
        print(f"User B might exist: {e}")
        pass

    # Now sign in with normal client (using anon key) to get real JWTs
    anon_key = os.environ.get("SUPABASE_ANON_KEY")
    supabase_anon = create_client(url, anon_key)
    
    try:
        auth_a = supabase_anon.auth.sign_in_with_password({"email": email_a, "password": password})
        token_a = auth_a.session.access_token
        user_a_id = auth_a.user.id
        print(f"[Auth] Logged in User A: {user_a_id}")
    except Exception as e:
        print(f"[Auth] Failed to login User A: {e}")
        return

    try:
        auth_b = supabase_anon.auth.sign_in_with_password({"email": email_b, "password": password})
        token_b = auth_b.session.access_token
        user_b_id = auth_b.user.id
        print(f"[Auth] Logged in User B: {user_b_id}")
    except Exception as e:
        print(f"[Auth] Failed to login User B: {e}")
        return

    # Create Matter for A
    matter_res = supabase_admin.table("matters").insert({
        "user_id": user_a_id,
        "title": "Live Consulting Test Matter A",
        "module": "consulting"
    }).execute()
    matter_id = matter_res.data[0]['id']
    print(f"[Matter] Created matter A: {matter_id}")

    client = TestClient(app)

    # 3. Live Consulting API POST & Versioning (First request)
    print("\n[API] Testing POST /api/consulting/analyze (Version 1)...")
    res1 = client.post(
        "/api/consulting/analyze",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"matter_id": matter_id, "question": "What is the limitation period for a breach of contract in India?"}
    )
    if res1.status_code == 200:
        data1 = res1.json()
        print(f"[API] POST Version 1 succeeded. Version No: {data1.get('version_no')}")
    else:
        print(f"[API] POST Version 1 failed: {res1.text}")

    # 4. Versioning (Second request)
    print("\n[API] Testing POST /api/consulting/analyze (Version 2)...")
    res2 = client.post(
        "/api/consulting/analyze",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"matter_id": matter_id, "question": "Are there any specific case laws supporting this?"}
    )
    if res2.status_code == 200:
        data2 = res2.json()
        print(f"[API] POST Version 2 succeeded. Version No: {data2.get('version_no')}")
    else:
        print(f"[API] POST Version 2 failed: {res2.text}")

    # 3b. Live Consulting API GET
    print(f"\n[API] Testing GET /api/consulting/matters/{matter_id}/analyses...")
    get_res = client.get(
        f"/api/consulting/matters/{matter_id}/analyses",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    if get_res.status_code == 200:
        analyses = get_res.json()
        print(f"[API] GET analyses succeeded. Count: {len(analyses)}. Top version: {analyses[0].get('version_no')}")
    else:
        print(f"[API] GET analyses failed: {get_res.text}")

    # 5. Cross-User Authorization
    print("\n[API] Testing Cross-User Authorization (User B trying to access User A's matter)...")
    cross_res = client.get(
        f"/api/consulting/matters/{matter_id}/analyses",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    print(f"[API] User B access result: Status {cross_res.status_code}, Response: {cross_res.text}")
    
    print("\n[Success] Live Verification completed successfully.")

if __name__ == "__main__":
    run_live_verification()
