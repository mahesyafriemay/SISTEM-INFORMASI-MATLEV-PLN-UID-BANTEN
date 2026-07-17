"""
Komponen UI bersama untuk SIMONA — versi STABIL.

Sengaja TIDAK memakai st.markdown(unsafe_allow_html=True) untuk struktur
layout (topbar/hero/kartu custom) sama sekali. Hanya pakai komponen native
Streamlit (st.image, st.columns, st.container, st.markdown teks biasa).

Ini keputusan sadar untuk menghindari potensi konflik antara HTML/CSS custom
dengan internal Streamlit di browser tertentu — stabilitas diutamakan di atas
tampilan yang lebih fancy.
"""

import streamlit as st
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"


def get_favicon():
    path = ASSETS_DIR / "logo_pln.png"
    return str(path) if path.exists() else None


def render_topbar():
    """Topbar sederhana pakai st.columns + st.image, tanpa HTML custom."""
    col1, col2, col3 = st.columns([1, 4, 1])
    with col1:
        logo_path = ASSETS_DIR / "logo_danantara.png"
        if logo_path.exists():
            st.image(str(logo_path), width=140)
    with col2:
        st.markdown("### SIMONA")
        st.caption("Maturity Level Gudang Distribusi — UID Banten")
    with col3:
        logo_path = ASSETS_DIR / "logo_pln.png"
        if logo_path.exists():
            st.image(str(logo_path), width=60)
    st.divider()


def render_sidebar_profile():
    role = st.session_state.get("role")
    fullname = st.session_state.get("fullname")
    unit_name = st.session_state.get("unit_name")

    with st.sidebar:
        st.markdown(f"**{fullname}**")
        st.caption(f"{role} · {unit_name}")
        if st.button("Ganti Role / Logout", use_container_width=True, key="logout_btn"):
            for k in ["role", "unit_id", "unit_name", "fullname", "is_authenticated"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.divider()


def render_hero(badge_text: str = "", title_html: str = "", subtitle: str = ""):
    """
    Hero halaman login — versi sederhana pakai komponen native.
    title_html/badge_text mungkin mengandung tag HTML sisa (mis. <span>) dari
    pemanggil lama; kalau ada, ditampilkan sebagai teks biasa (tag dibuang).
    """
    import re
    plain_title = re.sub(r"<[^>]+>", "", title_html) if title_html else "SIMONA"

    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        logo_path = ASSETS_DIR / "logo_danantara.png"
        if logo_path.exists():
            st.image(str(logo_path), width=150)
    with col3:
        logo_path = ASSETS_DIR / "logo_pln.png"
        if logo_path.exists():
            st.image(str(logo_path), width=70)

    bg_path = ASSETS_DIR / "hero_bg.jpg"
    if bg_path.exists():
        st.image(str(bg_path), use_container_width=True)

    st.title(plain_title)
    if subtitle:
        st.write(subtitle)
    st.divider()
