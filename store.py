"""SmartLock Store - the public shop (no login to browse). Orders go into the SAME database as the portal.
Normally launched through app.py (store = home page, portal = /portal).
Standalone alternative:  streamlit run store.py --server.port 8502
"""
import re
import streamlit as st

import smartlock as sl   # noqa: E402  (shares the database, payment checks and checkout)
import box_core as bc    # noqa: E402


def identify(ident, name, pw, create):
    """Find or create the customer account behind a store order. Returns (user dict | None, error | None)."""
    ident = ident.strip().lower()
    if not ident or not pw:
        return None, "Enter your mobile number (or username) and password."
    r = sl.q("SELECT * FROM users WHERE username=?", (ident,), one=True)
    if r:
        if r["role"] != "customer" or not sl.check_pw(pw, r["pw"]):
            return None, "Wrong password for this account."
        return dict(r), None
    if not create:
        return None, "No account found. Place an order first to create one."
    if not re.fullmatch(r"03\d{9}", ident):
        return None, "New customers: use your mobile number (03XXXXXXXXX). Returning customers: use your portal username."
    if not name.strip() or len(pw) < 6:
        return None, "Enter your name and a password of at least 6 characters."
    uid = sl.q("INSERT INTO users(username,pw,role,name) VALUES(?,?,?,?)", (ident, sl.hp(pw), "customer", name.strip()), commit=True)
    return dict(sl.q("SELECT * FROM users WHERE id=?", (uid,), one=True)), None


def identity_form(prefix, create):
    ident = st.text_input("Mobile number" + (" (or portal username)" if create else " / username"), key=f"{prefix}_id", placeholder="03XXXXXXXXX")
    name = st.text_input("Full name (new customers)", key=f"{prefix}_name") if create else ""
    pw = st.text_input("Password" + (" (new customers: choose one, min 6)" if create else ""), type="password", key=f"{prefix}_pw")
    if st.button("Continue" if create else "Show my orders", type="primary", key=f"{prefix}_go"):
        user, err = identify(ident, name, pw, create)
        if err:
            st.error(err)
        else:
            st.session_state.store_user = user
            if re.fullmatch(r"03\d{9}", user["username"]):
                st.session_state.setdefault("phone", user["username"])
            st.rerun()


def main(set_config=True, portal_page=None):
    if set_config:
        st.set_page_config(page_title="SmartLock Store", page_icon="🛍️", layout="wide")
    sl.H(sl.CSS)
    sl.hero("Shop now · pay your way · collect from a secure SmartLock box or get it delivered.", "🛍️ SmartLock Store")
    if portal_page:
        st.page_link(portal_page, label="Staff / rider / seller login", icon="🔐")
    else:
        sl.H(f'<p style="text-align:right;margin:-8px 0 8px"><a href="{sl.esc(bc.base_url())}" target="_blank">Staff / rider / seller login →</a></p>')

    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash") + " It is now visible to our team in the portal.")

    me = st.session_state.get("store_user")
    if "buy" in st.session_state:
        if me:
            sl.checkout(me)
        else:
            if st.button("← Back to shop"):
                del st.session_state.buy
                st.rerun()
            st.markdown("### Almost there — who is ordering?")
            st.caption("No sign-up page needed: your mobile number becomes your account, so you can track the order and open your SmartLock box.")
            identity_form("co", create=True)
    else:
        tabs = st.tabs(["🛍️ Shop", "📦 My Orders & Tracking"])
        with tabs[0]:
            sl.shop_view()
            st.caption("🔐 Smart Lock pickups: scan the QR on the box screen and log in with your mobile number and password.")
        with tabs[1]:
            if me:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**Hi, {sl.esc(me['name'])}!**")
                if c2.button("Not you? Sign out"):
                    del st.session_state.store_user
                    st.rerun()
                sl.orders_view(me)
                with st.expander("🔔 Notifications"):
                    sl.notes_view(me)
            else:
                st.markdown("#### Find my orders")
                identity_form("tr", create=False)
    sl.footer()


if __name__ == "__main__":
    main()
