# clients/supabase_client.py
import csv
import io

import streamlit as st
from supabase import Client, create_client


@st.cache_resource
def _get_supabase_url_and_key():
    return st.secrets["supabase"]["url"], st.secrets["supabase"]["key"]


def get_supabase() -> Client:
    url, key = _get_supabase_url_and_key()

    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = create_client(url, key)

    client: Client = st.session_state.supabase_client

    session = st.session_state.get("session")
    if session is not None:
        try:
            client.auth.set_session(
                session.access_token,
                session.refresh_token,
            )
        except Exception:
            clear_session()

    return client


def _ensure_state_keys():
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("session", None)


def persist_session(res) -> None:
    _ensure_state_keys()
    st.session_state.session = res.session
    st.session_state.user = res.user
    st.session_state.logged_in = True

    if res.session is not None:
        try:
            get_supabase().auth.set_session(
                res.session.access_token,
                res.session.refresh_token,
            )
        except Exception as e:
            st.error(f"Failed to apply session: {e}")


def clear_session() -> None:
    st.session_state.session = None
    st.session_state.user = None
    st.session_state.logged_in = False
    st.session_state.pop("supabase_client", None)


def logout() -> None:
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    clear_session()
    st.rerun()


def get_user_id() -> str:
    user = st.session_state.get("user")
    if user is None or not getattr(user, "id", None):
        raise ValueError("User is not logged in.")
    return user.id


TABLE = "receipts"


def create_receipt(payload: dict) -> dict:
    supabase = get_supabase()
    row = {**payload, "user_id": get_user_id()}
    res = supabase.table(TABLE).insert(row).execute()
    if not res.data:
        raise RuntimeError(
            "Insert returned no rows — check RLS 'with check' policy on receipts."
        )
    return res.data[0]


def list_receipts(order_by: str = "transaction_date", desc: bool = True) -> list[dict]:
    supabase = get_supabase()
    res = (
        supabase.table(TABLE)
        .select("*")
        .eq("user_id", get_user_id())
        .order(order_by, desc=desc)
        .execute()
    )
    return res.data or []


def get_receipt(receipt_id: str) -> dict | None:
    supabase = get_supabase()
    res = (
        supabase.table(TABLE)
        .select("*")
        .eq("id", receipt_id)
        .eq("user_id", get_user_id())
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def update_receipt(receipt_id: str, updates: dict) -> dict | None:
    supabase = get_supabase()
    safe = {k: v for k, v in updates.items() if k not in ("id", "user_id")}
    if not safe:
        return get_receipt(receipt_id)
    res = (
        supabase.table(TABLE)
        .update(safe)
        .eq("id", receipt_id)
        .eq("user_id", get_user_id())
        .execute()
    )
    return res.data[0] if res.data else None


def delete_receipt(receipt_id: str) -> bool:
    supabase = get_supabase()
    res = (
        supabase.table(TABLE)
        .delete()
        .eq("id", receipt_id)
        .eq("user_id", get_user_id())
        .execute()
    )
    return bool(res.data)


def export_receipts_to_csv() -> bytes:
    rows = list_receipts(order_by="transaction_date", desc=True)
    if not rows:
        raise ValueError("No receipts to export.")

    preferred = [
        "transaction_date",
        "documentation_date",
        "merchant",
        "or_number",
        "category",
        "description",
        "currency",
        "total_amount",
        "php_total_amount",
        "backblaze_image",
        "text_context",
        "image_context",
        "id",
        "user_id",
        "created_at",
        "updated_at",
    ]
    fieldnames = [c for c in preferred if c in rows[0]]
    fieldnames += [c for c in rows[0].keys() if c not in fieldnames]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

    return buf.getvalue().encode("utf-8-sig")