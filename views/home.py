import streamlit as st
from data import authenticate, get_all_credentials_list, reset_demo_data
from ui import render_topbar, render_hero, render_sidebar_profile


def render_login():
    render_hero(
        badge_text="SIMONA",
        title_html='Kelola Maturity Level Gudang Distribusi <span class="accent">Secara Presisi</span>',
        subtitle=(
            "Self-assessment digital untuk seluruh unit gudang distribusi PLN UID Banten — "
            "menggantikan penilaian manual berbasis Excel dengan sistem yang terukur, "
            "terpusat, dan dapat dipantau secara real-time."
        ),
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            st.markdown("#### Masuk ke SIMONA")
            st.caption("Masukkan ID unit dan password yang sudah diberikan.")

            with st.form("login_form"):
                username = st.text_input("ID Unit", placeholder="contoh: UID Banten / Serpong / ULP Serang")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Masuk", type="primary", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("ID Unit dan password wajib diisi.")
                else:
                    user = authenticate(username, password)
                    if user:
                        st.session_state["role"] = user["role"]
                        st.session_state["unit_id"] = user["unit_id"]
                        st.session_state["unit_name"] = user["unit_name"]
                        st.session_state["fullname"] = user["fullname"]
                        st.session_state["is_authenticated"] = True
                        st.rerun()
                    else:
                        st.error("ID Unit atau password salah.")

            with st.expander("Lihat daftar ID & password (mode prototipe)"):
                st.caption(
                    "Ini hanya tampil di mode prototipe supaya gampang dicoba. "
                    "Di versi produksi nanti, kredensial dikelola lewat sistem auth sungguhan (Supabase), bukan ditampilkan di sini."
                )
                rows = get_all_credentials_list()
                st.dataframe(
                    [{"ID Unit": r["username"], "Password": r["password"], "Role": r["role"]} for r in rows],
                    use_container_width=True, hide_index=True,
                )

            st.divider()
            if st.button("Reset semua data demo ke kondisi awal", use_container_width=True):
                reset_demo_data()
                st.success("Data demo direset ke data Juni 2026 real + Juli 2026 kosong.")
                st.rerun()

    st.write("")
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("**Kriteria UP3 & ULP Terpisah**")
            st.caption("UP3: 6 aspek, skala level 1-5. ULP: 5 aspek, skala level 1-3 — sesuai standar masing-masing.")
    with c2:
        with st.container(border=True):
            st.markdown("**29 + 25 Indikator Terukur**")
            st.caption("Tiap indikator punya rubrik kriteria yang jelas, bukan penilaian subjektif.")
    with c3:
        with st.container(border=True):
            st.markdown("**Data Real-time**")
            st.caption("Skor & progres assessment ter-update otomatis begitu unit submit dan UID approve — langsung terlihat di Dashboard.")


ASPECT_DESCRIPTIONS = {
    "Sumber Daya Manusia": "Kecukupan & kompetensi pegawai/petugas yang mengelola gudang (sertifikasi, K3, keamanan).",
    "Anggaran dan Pengelolaan Keuangan": "Ketersediaan dan realisasi anggaran khusus untuk pengelolaan gudang.",
    "Tata Kelola": "Kepatuhan pada SOP/BPM, penyusunan & identifikasi material, implementasi 5S di gudang.",
    "Infrastruktur": "Kondisi fisik gudang: rak, lantai, atap, demarkasi area, ruang penunjang.",
    "Peralatan Penunjang Operasional": "Ketersediaan alat handling, APD, CCTV, APAR/Hydrant, identitas gudang.",
    "Kinerja": "Efisiensi operasional gudang: perputaran material, penghapusan aset tak terpakai, material slow moving.",
}


def render_bobot_breakdown(unit_type: str, period_id: str):
    from data import get_aspects, get_indicators, get_aspect_weight
    import pandas as pd
    import plotly.express as px

    aspects_df = get_aspects(unit_type=unit_type)
    if aspects_df.empty:
        st.caption("Belum ada aspek terdaftar untuk tipe unit ini.")
        return

    rows = []
    for _, aspect in aspects_df.iterrows():
        inds = get_indicators(aspect["id"])
        bobot = get_aspect_weight(period_id, aspect["id"])
        rows.append({
            "Aspek": aspect["name"],
            "Bobot (%)": bobot,
            "Jumlah Indikator": len(inds),
            "Deskripsi": ASPECT_DESCRIPTIONS.get(aspect["name"], "-"),
        })
    df = pd.DataFrame(rows).sort_values("Bobot (%)", ascending=True)

    col1, col2 = st.columns([1.1, 1])
    with col1:
        fig = px.bar(
            df, x="Bobot (%)", y="Aspek", orientation="h",
            color="Bobot (%)", color_continuous_scale="Blues",
            text="Bobot (%)",
        )
        fig.update_layout(showlegend=False, height=280, margin=dict(l=0, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        for _, r in df.sort_values("Bobot (%)", ascending=False).iterrows():
            st.markdown(f"**{r['Aspek']}** — bobot {r['Bobot (%)']:.0f}%, {r['Jumlah Indikator']} indikator")
            st.caption(r["Deskripsi"])

    max_level = 5 if unit_type == "UP3" else 3
    st.caption(
        f"Total bobot seluruh aspek = 100. Tiap indikator dalam satu aspek berkontribusi sama besar "
        f"(bobot aspek dibagi rata jumlah indikatornya), dengan skala Level 1-{max_level} untuk unit tipe {unit_type}."
    )


def render_konversi_matlev():
    import pandas as pd
    st.markdown("##### Konversi Nilai Total → Maturity Level (Matlev)")
    konversi = pd.DataFrame({
        "Nilai Total": [20, 40, 60, 80, 100],
        "Matlev": [1, 2, 3, 4, 5],
    })
    st.dataframe(konversi, use_container_width=True, hide_index=True)
    st.caption("Matlev = Nilai Total ÷ 20. Contoh: Nilai Total 62 → Matlev 3,10.")


def render_home():
    render_topbar()
    render_sidebar_profile()

    role = st.session_state.get("role")
    fullname = st.session_state.get("fullname")
    unit_name = st.session_state.get("unit_name")

    st.success(f"Selamat datang, **{fullname}** ({role} - {unit_name}).")
    st.info(
        "Gunakan menu di sidebar kiri: **Dashboard**, **Assessment**, "
        "**Review** (khusus UID), **Master Data** (khusus UID), dan **Notifikasi**."
    )

    st.markdown("#### Ringkasan Peran Kamu")
    if role == "UID":
        st.write("Kelola periode, aspek, indikator & bobot aspek. Review dan approve assessment dari seluruh unit gudang UP3 & ULP.")
    else:
        st.write("Isi self-assessment maturity level gudang bulanan, upload evidence, simpan draft, submit, dan pantau catatan revisi dari UID.")

    st.markdown("---")
    st.markdown("### Komposisi Penilaian Maturity Level")

    from data import get_periods
    periods_df = get_periods()
    open_periods = periods_df[periods_df["status"] == "OPEN"]
    ref_period = (open_periods.iloc[0] if not open_periods.empty else periods_df.iloc[-1])

    if role == "UID":
        tab_up3, tab_ulp = st.tabs(["Kriteria UP3 (Level 1-5)", "Kriteria ULP (Level 1-3)"])
        with tab_up3:
            render_bobot_breakdown("UP3", ref_period["id"])
        with tab_ulp:
            render_bobot_breakdown("ULP", ref_period["id"])
    else:
        render_bobot_breakdown(role, ref_period["id"])

    st.markdown("---")
    col_formula, col_konversi = st.columns([1.2, 1])
    with col_formula:
        st.markdown("##### Formula Penilaian")
        if role == "ULP":
            st.latex(r"Nilai = \sum \frac{Level}{3} \times \frac{Bobot\ Aspek}{Jumlah\ Indikator\ dalam\ Aspek}")
        elif role == "UP3":
            st.latex(r"Nilai = \sum \frac{Level}{5} \times \frac{Bobot\ Aspek}{Jumlah\ Indikator\ dalam\ Aspek}")
        else:
            st.latex(r"Nilai = \sum \frac{Level}{Skala\ Maks} \times \frac{Bobot\ Aspek}{Jumlah\ Indikator\ dalam\ Aspek}")
            st.caption("Skala Maks = 5 untuk unit UP3, 3 untuk unit ULP.")
    with col_konversi:
        render_konversi_matlev()


if not st.session_state.get("is_authenticated"):
    render_login()
else:
    render_home()
