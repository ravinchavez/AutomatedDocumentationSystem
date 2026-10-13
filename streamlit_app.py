# streamlit_app.py
import streamlit as st

from pages.add_transaction_page import add_transaction_page
from pages.all_transactions_page import all_transactions_page
from pages.generate_liquidation import generate_liquidation_page
from pages.export_data_page import export_data_page
from pages.financial_overview_page import financial_overview_page
from pages.login_page import login_page
from clients.supabase_client import clear_session, logout 


# ---------- Bootstrap session state ----------
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("user", None)
st.session_state.setdefault("session", None)

# ---------- Navigation ----------
if not st.session_state.logged_in:
    pg = st.navigation(
        [st.Page(login_page, title="Home", icon=":material/login:")]
    )
else:
    pg = st.navigation(
        {
            "Commands": [
                st.Page(
                    add_transaction_page,
                    title="Smart Receipt Entry",
                    icon=":material/edit:",
                ),
            ],
            "Records": [                
                st.Page(
                    financial_overview_page,
                    title="Financial Overview",
                    icon=":material/insights:",
                ), 
                st.Page(
                    all_transactions_page,
                    title="Receipt Logbook",
                    icon=":material/folder_open:",
                ),
                st.Page(
                    generate_liquidation_page,
                    title="Generate Liquidation",
                    icon=":material/receipt_long:",
                ),
                st.Page(
                    export_data_page,
                    title="Export Data",
                    icon=":material/description:",
                ),
            ],
            "Support": [
                st.Page(
                    "https://www.facebook.com/rpfchavez/",
                    title="Contact Support",
                    icon=":material/support_agent:",
                ),
            ],
        }
    )
pg.run()

st.sidebar.title("Automated Documentation System")
if st.session_state.logged_in and st.session_state.user is not None:
    st.sidebar.write(f"Signed in as **{st.session_state.user.email}**")
    if st.sidebar.button(
        "Log Out", icon=":material/logout:", use_container_width=True
    ):
        logout()
else:
    st.sidebar.write("Please log in to access the app.")