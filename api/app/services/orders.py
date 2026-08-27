from __future__ import annotations

from typing import Any

from supabase import Client


def list_orders(matter_id: str, db: Client) -> list[dict[str, Any]]:
    res = db.table("orders").select("*").eq("matter_id", matter_id).order("order_date", desc=True).execute()
    return res.data or []


def add_order(matter_id: str, organization_id: str, payload: dict[str, Any], db: Client) -> dict[str, Any]:
    data = {**payload, "matter_id": matter_id, "organization_id": organization_id}
    res = db.table("orders").insert(data).execute()
    return res.data[0] if res.data else data


def update_order(order_id: str, matter_id: str, payload: dict[str, Any], db: Client) -> dict[str, Any] | None:
    res = db.table("orders").update(payload).eq("id", order_id).eq("matter_id", matter_id).execute()
    return res.data[0] if res.data else None


def delete_order(order_id: str, matter_id: str, db: Client) -> bool:
    res = db.table("orders").delete().eq("id", order_id).eq("matter_id", matter_id).execute()
    return bool(res.data)
