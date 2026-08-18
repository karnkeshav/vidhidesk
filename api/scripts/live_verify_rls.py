import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv("../.env")
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_ANON_KEY")
service_key: str = os.environ.get("SUPABASE_SERVICE_KEY")

supabase_admin: Client = create_client(url, service_key)
supabase_anon: Client = create_client(url, key)

print("[Schema] Verifying live schema...")
res = supabase_admin.table("consulting_analyses").select("*").limit(1).execute()
print(f"Table exists. Data: {res.data}")

email_a = "live_test_user_a@vidhidesk.com"
email_b = "live_test_user_b@vidhidesk.com"
password = "SecurePassword123!"

auth_a = supabase_anon.auth.sign_in_with_password({"email": email_a, "password": password})
token_a = auth_a.session.access_token
user_a_id = auth_a.user.id
user_a_client = create_client(url, key, options={'headers': {'Authorization': f'Bearer {token_a}'}})

auth_b = supabase_anon.auth.sign_in_with_password({"email": email_b, "password": password})
token_b = auth_b.session.access_token
user_b_id = auth_b.user.id
user_b_client = create_client(url, key, options={'headers': {'Authorization': f'Bearer {token_b}'}})

matter_res = supabase_admin.table("matters").insert({
    "user_id": user_a_id,
    "title": "Live Consulting Test Matter A via HTTP",
    "module": "consulting"
}).execute()
matter_id = matter_res.data[0]['id']

# Insert an analysis using admin
supabase_admin.table("consulting_analyses").insert({
    "matter_id": matter_id,
    "version_no": 1,
    "question": "Test question"
}).execute()

print("[RLS] Testing RLS for User A (Owner)...")
res_a = user_a_client.table("consulting_analyses").select("*").eq("matter_id", matter_id).execute()
print(f"User A read: {len(res_a.data)} rows")

print("[RLS] Testing RLS for User B (Not Owner)...")
res_b = user_b_client.table("consulting_analyses").select("*").eq("matter_id", matter_id).execute()
print(f"User B read: {len(res_b.data)} rows")

print("[API] Live Verification Completed.")
