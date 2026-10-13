# pages/login_page.py
import streamlit as st
from clients.supabase_client import get_supabase, persist_session


def login_page():
    st.title("Log In")
    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    supabase = get_supabase()

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="li_email")
            password = st.text_input("Password", type="password", key="li_pw")
            submitted = st.form_submit_button("Log In", use_container_width=True)
        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                try:
                    res = supabase.auth.sign_in_with_password(
                        {"email": email, "password": password}
                    )
                    if res.session is None:
                        st.error(
                            "Login succeeded but no session was returned. "
                            "Please confirm your email and try again."
                        )
                    else:
                        persist_session(res)
                        st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email", key="su_email")
            password = st.text_input("Password", type="password", key="su_pw")
            submitted = st.form_submit_button(
                "Create Account", use_container_width=True
            )

        if submitted:
            email = (email or "").strip().lower()
            password = password or ""

            if not email or not password:
                st.error("Please enter both email and password.")
                return
            
            ALLOWED_DOMAIN = "umindanao.edu.ph"
            if not email.endswith(f"@{ALLOWED_DOMAIN}"):
                st.warning(
                    f"Sign-up is restricted to **@{ALLOWED_DOMAIN}** email "
                    "addresses.\n\n"
                    "If you're part of the organization but use a different "
                    "email, please contact the administrator to request an "
                    "invitation link."
                )
                st.stop()

            # ---- Proceed with sign-up ----
            try:
                res = supabase.auth.sign_up(
                    {"email": email, "password": password}
                )
                if res.user and not res.session:
                    st.success(
                        "Account created. Check your email to confirm "
                        "your account, then log in."
                    )
                elif res.session:
                    persist_session(res)
                    st.rerun()
                else:
                    st.warning(
                        "Sign up did not return a user or session. "
                        "Please try logging in."
                    )
            except Exception as e:
                st.error(f"Sign up failed: {e}")