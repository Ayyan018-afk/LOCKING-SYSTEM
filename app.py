"""SmartLock Delivery - ONE app, two pages sharing one database:
   /        -> Store (public shop, no login)
   /portal  -> Portal (login for admin, rider, seller, customer)
Run:  streamlit run app.py        (Streamlit Cloud main file: app.py)
"""
import streamlit as st

st.set_page_config(page_title="SmartLock Delivery", page_icon="🔐", layout="wide")
import smartlock as portal_app   # noqa: E402
import store as store_app        # noqa: E402


def run_store():
    store_app.main(set_config=False, portal_page=portal_page)


def run_portal():
    portal_app.main(set_config=False, store_page=store_page)


store_page = st.Page(run_store, title="Store", icon="🛍️", url_path="store", default=True)
portal_page = st.Page(run_portal, title="Portal", icon="🔐", url_path="portal")
st.navigation([store_page, portal_page], position="hidden").run()
