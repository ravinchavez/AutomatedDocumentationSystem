# pages/all_transactions_page.py
import streamlit as st
from clients.b2_client import presigned_url
from clients.supabase_client import list_receipts, delete_receipt


@st.cache_data(ttl=300, show_spinner=False)
def _cached_presigned(key: str) -> str:
    return presigned_url(key)


def _fmt(value, fallback: str = "—") -> str:
    return value if value not in (None, "") else fallback


def all_transactions_page():
    st.title("All Receipt Entries")

    try:
        rows = list_receipts()
    except ValueError:
        st.error("You must be logged in to view receipts.")
        return
    except Exception as e:
        st.error(f"Could not load receipts: {e}")
        return

    if not rows:
        st.info("No receipts yet.")
        return

    # Tracks which receipt ID is pending confirmation
    confirm_id = st.session_state.get("confirm_delete_id")

    for r in rows:
        merchant = _fmt(r.get("merchant_id"))
        amount = r.get("total_amount")
        currency = _fmt(r.get("currency"), "")
        amount_str = f"{currency} {amount}" if amount is not None else "—"
        receipt_id = r.get("id")
        php_amount = r.get("php_total_amount")

        with st.expander(
            f"{_fmt(r.get('transaction_date'))} · {merchant} · {amount_str} · PHP {php_amount}",
        ):
            c1, c2 = st.columns([1, 2])
            with c1:
                key = r.get("backblaze_image")
                if key:
                    try:
                        st.image(
                            _cached_presigned(key),
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.warning(f"Image unavailable: {e}")
                else:
                    st.caption("No image attached.")
            with c2:
                st.write(f"**Merchant:** {merchant}")
                st.write(f"**OR #:** {_fmt(r.get('or_number'))}")
                st.write(f"**Category:** {_fmt(r.get('category'))}")
                st.write(f"**Transaction date:** {_fmt(r.get('transaction_date'))}")
                st.write(f"**Documentation date:** {_fmt(r.get('documentation_date'))}")
                st.write(f"**Description:** {_fmt(r.get('description'))}")
                if r.get("image_context"):
                    st.caption(f"{r['image_context']}")
                if r.get("text_context"):
                    with st.expander("Raw OCR text"):
                        st.text(r["text_context"])

                st.divider()

                if confirm_id == receipt_id:
                    st.warning("Delete this receipt? This cannot be undone.")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button(
                            "Yes, delete",
                            key=f"confirm_del_{receipt_id}",
                            type="primary",                            
                            use_container_width=True,
                        ):
                            try:
                                ok = delete_receipt(receipt_id)
                                if ok:
                                    st.session_state.pop("confirm_delete_id", None)
                                    st.cache_data.clear()
                                    st.success("Receipt deleted.")
                                    st.rerun()
                                else:
                                    st.error("Delete returned no rows.")
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                    with dc2:
                        if st.button(
                            "Cancel",
                            key=f"cancel_del_{receipt_id}",
                            use_container_width=True,
                        ):
                            st.session_state.pop("confirm_delete_id", None)
                            st.rerun()
                else:
                    if st.button(
                        "Delete",
                        key=f"del_{receipt_id}",
                        use_container_width=True,
                    ):
                        st.session_state["confirm_delete_id"] = receipt_id
                        st.rerun()