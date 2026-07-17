import streamlit as st
from data import init_demo_data, get_notifications_for
from ui import render_topbar, render_sidebar_profile

init_demo_data()
render_topbar()
render_sidebar_profile()

if not st.session_state.get("is_authenticated"):
    st.warning("Silakan masuk terlebih dahulu di halaman utama.")
    st.stop()

role = st.session_state["role"]
unit_id = st.session_state["unit_id"]

st.title("Notifikasi")

notifs = get_notifications_for(role, unit_id)

if not notifs:
    st.info(
        "Belum ada notifikasi. Notifikasi akan muncul otomatis di sini ketika: "
        "ULP/UP3 submit assessment (UID dapat notif), atau UID approve/minta revisi (unit terkait dapat notif)."
    )
else:
    for n in notifs:
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{n['title']}**")
                st.caption(n.get("message") or "")
                st.caption(f"{n['type']} · {n['created_at'].strftime('%d/%m/%Y %H:%M')}")
            with c2:
                if not n["is_read"]:
                    st.caption("🆕 Baru")
