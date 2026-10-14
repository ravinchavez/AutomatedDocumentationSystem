# pages/all_transactions_page.py
import streamlit as st
from clients.b2_client import presigned_url
from clients.supabase_client import list_receipts, delete_receipt, update_receipt


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
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button(
                            "Delete",
                            key=f"del_{receipt_id}",
                            use_container_width=True,
                        ):
                            st.session_state["confirm_delete_id"] = receipt_id
                            st.rerun()
                    with dc2:
                        if st.button(
                            "Edit",
                            key=f"edit_{receipt_id}",
                            use_container_width=True,
                        ):
                            st.session_state["edit_receipt_id"] = receipt_id
                            st.rerun()

                if st.session_state.get("edit_receipt_id") == receipt_id:
                    st.divider()
                    st.subheader("Edit receipt")

                    fields = (
                        "merchant_id",
                        "or_number",
                        "category",
                        "transaction_date",
                        "documentation_date",
                        "description",
                        "currency",
                        "total_amount",
                        "php_total_amount",
                    )

                    with st.form(key=f"edit_form_{receipt_id}"):
                        merchant_id = st.text_input(
                            "Merchant",
                            value=str(r.get("merchant_id") or ""),
                            key=f"edit_merchant_{receipt_id}",
                        )
                        or_number = st.text_input(
                            "OR #",
                            value=str(r.get("or_number") or ""),
                            key=f"edit_or_{receipt_id}",
                        )
                        category = st.text_input(
                            "Category",
                            value=str(r.get("category") or ""),
                            key=f"edit_category_{receipt_id}",
                        )
                        transaction_date = st.text_input(
                            "Transaction date",
                            value=str(r.get("transaction_date") or ""),
                            key=f"edit_transaction_date_{receipt_id}",
                        )
                        documentation_date = st.text_input(
                            "Documentation date",
                            value=str(r.get("documentation_date") or ""),
                            key=f"edit_documentation_date_{receipt_id}",
                        )
                        description = st.text_area(
                            "Description",
                            value=str(r.get("description") or ""),
                            key=f"edit_description_{receipt_id}",
                        )
                        currency = st.text_input(
                            "Currency",
                            value=str(r.get("currency") or ""),
                            key=f"edit_currency_{receipt_id}",
                        )
                        total_amount = st.text_input(
                            "Total amount",
                            value=str(r.get("total_amount") or ""),
                            key=f"edit_total_amount_{receipt_id}",
                        )
                        php_total_amount = st.text_input(
                            "PHP total amount",
                            value=str(r.get("php_total_amount") or ""),
                            key=f"edit_php_total_amount_{receipt_id}",
                        )

                        save = st.form_submit_button(
                            "Save changes",
                            type="primary",
                            use_container_width=True,
                        )

                    if save:
                        try:
                            def parse_amount(value):
                                value = value.strip()
                                return float(value) if value else None

                            updates = {
                                "merchant_id": merchant_id.strip() or None,
                                "or_number": or_number.strip() or None,
                                "category": category.strip() or None,
                                "transaction_date": transaction_date.strip() or None,
                                "documentation_date": documentation_date.strip() or None,
                                "description": description.strip() or None,
                                "currency": currency.strip() or None,
                                "total_amount": parse_amount(total_amount),
                                "php_total_amount": parse_amount(php_total_amount),
                            }

                            updated = update_receipt(receipt_id, updates)
                            if updated:
                                st.session_state.pop("edit_receipt_id", None)
                                for field in fields:
                                    st.session_state.pop(
                                        f"edit_{field.replace('_', '')}_{receipt_id}",
                                        None,
                                    )
                                # Clear the actual widget keys.
                                for key in (
                                    f"edit_merchant_{receipt_id}",
                                    f"edit_or_{receipt_id}",
                                    f"edit_category_{receipt_id}",
                                    f"edit_transaction_date_{receipt_id}",
                                    f"edit_documentation_date_{receipt_id}",
                                    f"edit_description_{receipt_id}",
                                    f"edit_currency_{receipt_id}",
                                    f"edit_total_amount_{receipt_id}",
                                    f"edit_php_total_amount_{receipt_id}",
                                ):
                                    st.session_state.pop(key, None)

                                st.cache_data.clear()
                                st.success("Receipt updated.")
                                st.rerun()
                            else:
                                st.error("Update returned no rows.")
                        except ValueError:
                            st.error("Amounts must be valid numbers.")
                        except Exception as e:
                            st.error(f"Update failed: {e}")

                    if st.button(
                        "Cancel edit",
                        key=f"cancel_edit_{receipt_id}",
                        use_container_width=True,
                    ):
                        st.session_state.pop("edit_receipt_id", None)
                        st.rerun()