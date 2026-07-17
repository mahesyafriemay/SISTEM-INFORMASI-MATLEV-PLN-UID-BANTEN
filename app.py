import streamlit as st
from data import init_demo_data
from ui import get_favicon

st.set_page_config(
    page_title="SIMONA - Maturity Level Gudang Distribusi UID Banten",
    page_icon=get_favicon(),
    layout="wide",
)

init_demo_data()
role = st.session_state.get("role")
authenticated = st.session_state.get("is_authenticated", False)

home_page = st.Page("views/home.py", title="Beranda", icon=":material/home:", default=True)

if not authenticated:
    pg = st.navigation([home_page])
else:
    pages = [
        home_page,
        st.Page("views/dashboard.py", title="Dashboard", icon=":material/bar_chart:"),
    ]
    if role in ("UP3", "ULP"):
        pages.append(st.Page("views/assessment.py", title="Assessment", icon=":material/edit_note:"))
    if role == "UID":
        pages.append(st.Page("views/review.py", title="Review", icon=":material/fact_check:"))
        pages.append(st.Page("views/master_data.py", title="Master Data", icon=":material/storage:"))
    pages.append(st.Page("views/notifikasi.py", title="Notifikasi", icon=":material/notifications:"))
    pg = st.navigation(pages)

pg.run()
