import os
import sys
import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv("../.env")
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_ANON_KEY")
service_key: str = os.environ.get("SUPABASE_SERVICE_KEY")

supabase_admin: Client = create_client(url, service_key)
supabase_anon: Client = create_client(url, key)

email_a = "live_test_user_a@vidhidesk.com"
email_b = "live_test_user_b@vidhidesk.com"
password = "SecurePassword123!"

# login A
auth_a = supabase_anon.auth.sign_in_with_password({"email": email_a, "password": password})
token_a = auth_a.session.access_token
user_a_id = auth_a.user.id

# login B
auth_b = supabase_anon.auth.sign_in_with_password({"email": email_b, "password": password})
token_b = auth_b.session.access_token
user_b_id = auth_b.user.id

matter_res = supabase_admin.table("matters").insert({
    "user_id": user_a_id,
    "title": "Live Consulting Test Matter A via HTTP",
    "module": "consulting"
}).execute()
matter_id = matter_res.data[0]['id']

print("\n[API] Testing POST /api/consulting/analyze (Version 1)...")
with httpx.Client(timeout=120.0) as client:
    res1 = client.post(
        "http://localhost:8000/api/consulting/analyze",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"matter_id": matter_id, "question": "What is the limitation period for a breach of contract in India?"}
    )
    if res1.status_code == 200:
        data1 = res1.json()
        print(f"[API] POST Version 1 succeeded. Version No: {data1.get('version_no')}")
    else:
        print(f"[API] POST Version 1 failed: {res1.text}")

    print("\n[API] Testing POST /api/consulting/analyze (Version 2)...")
    res2 = client.post(
        "http://localhost:8000/api/consulting/analyze",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"matter_id": matter_id, "question": "Are there any specific case laws supporting this?"}
    )
    if res2.status_code == 200:
        data2 = res2.json()
        print(f"[API] POST Version 2 succeeded. Version No: {data2.get('version_no')}")
    else:
        print(f"[API] POST Version 2 failed: {res2.text}")

    print(f"\n[API] Testing GET /api/consulting/matters/{matter_id}/analyses...")
    get_res = client.get(
        f"http://localhost:8000/api/consulting/matters/{matter_id}/analyses",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    if get_res.status_code == 200:
        analyses = get_res.json()
        print(f"[API] GET analyses succeeded. Count: {len(analyses)}. Top version: {analyses[0].get('version_no')}")
    else:
        print(f"[API] GET analyses failed: {get_res.text}")

    print("\n[API] Testing Cross-User Authorization (User B trying to access User A's matter)...")
    cross_res = client.get(
        f"http://localhost:8000/api/consulting/matters/{matter_id}/analyses",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    print(f"[API] User B access result: Status {cross_res.status_code}, Response: {cross_res.text}")
