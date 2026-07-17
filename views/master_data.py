import streamlit as st
import pandas as pd
import datetime
from data import (
    init_demo_data, get_periods, add_period, lock_period, get_units, add_unit,
    get_aspects, add_aspect, get_indicators, add_indicator, add_level,
    get_aspect_weight, set_aspect_weight, export_data_json, import_data_json,
)
from ui import render_topbar, render_sidebar_profile

init_demo_data()
render_topbar()
render_sidebar_profile()

if not st.session_state.get("is_authenticated"):
    st.warning("Silakan masuk terlebih dahulu di halaman utama.")
    st.stop()

if st.session_state["role"] != "UID":
    st.error("Halaman ini khusus untuk role UID.")
    st.stop()

st.title("Master Data")

tab_periods, tab_units, tab_aspects, tab_indicators, tab_weights, tab_backup = st.tabs(
    ["Periode", "Unit", "Aspek", "Indikator & Level", "Bobot Aspek", "Backup & Restore"]
)

# ---------------------------------------------------------------------------
with tab_periods:
    st.subheader("Kelola Periode Assessment")
    with st.form("new_period_form"):
        c1, c2, c3, c4 = st.columns(4)
        month = c1.selectbox("Bulan", list(range(1, 13)), index=7)
        year = c2.number_input("Tahun", min_value=2020, max_value=2100, value=2026)
        submission_deadline = c3.date_input("Deadline Submit", value=None)
        review_deadline = c4.date_input("Deadline Review", value=None)
        if st.form_submit_button("Buat Periode Baru", type="primary"):
            add_period(month, year, submission_deadline, review_deadline)
            st.success(f"Periode {month:02d}/{year} berhasil dibuat (bobot aspek disalin dari periode terakhir).")
            st.rerun()

    st.divider()
    periods_df = get_periods()
    st.dataframe(
        periods_df[["month", "year", "status", "submission_deadline", "review_deadline"]],
        use_container_width=True, hide_index=True,
    )
    openable = periods_df[periods_df["status"] != "LOCKED"]
    if not openable.empty:
        openable = openable.copy()
        openable["label"] = openable.apply(lambda r: f"{r['month']:02d}/{r['year']}", axis=1)
        lock_target = st.selectbox("Kunci periode", openable["label"].tolist())
        if st.button("Lock Periode Ini"):
            target_id = openable[openable["label"] == lock_target].iloc[0]["id"]
            lock_period(target_id)
            st.success("Periode dikunci. Bobot aspek & assessment pada periode ini kini beku.")
            st.rerun()

# ---------------------------------------------------------------------------
with tab_units:
    st.subheader("Kelola Unit Gudang (UP3 & ULP)")
    with st.form("new_unit_form"):
        c1, c2, c3 = st.columns(3)
        u_name = c1.text_input("Nama Unit")
        u_type = c2.selectbox("Tipe", ["UP3", "ULP"])
        units_all = get_units()
        if u_type == "UP3":
            parent_options = {row["name"]: row["id"] for _, row in units_all[units_all["type"] == "UID"].iterrows()}
        else:
            parent_options = {row["name"]: row["id"] for _, row in units_all[units_all["type"] == "UP3"].iterrows()}
        parent_label = c3.selectbox("Induk Unit", list(parent_options.keys()))
        if st.form_submit_button("Tambah Unit", type="primary"):
            add_unit(u_name, u_type, parent_options[parent_label])
            st.success(f"Unit '{u_name}' ({u_type}) berhasil ditambahkan.")
            st.rerun()

    st.divider()
    units_display = get_units()
    parent_name_map = {row["id"]: row["name"] for _, row in units_display.iterrows()}
    units_display = units_display.copy()
    units_display["induk"] = units_display["parent_id"].map(parent_name_map).fillna("-")
    st.dataframe(
        units_display[["name", "type", "induk"]].rename(columns={"name": "Nama Unit", "type": "Tipe", "induk": "Induk"}),
        use_container_width=True, hide_index=True,
    )

# ---------------------------------------------------------------------------
with tab_aspects:
    st.subheader("Kelola Aspek Penilaian")
    aspect_unit_type = st.radio("Kriteria untuk", ["UP3", "ULP"], horizontal=True, key="aspect_unit_type")

    with st.form("new_aspect_form"):
        a_name = st.text_input("Nama Aspek")
        if st.form_submit_button("Tambah Aspek", type="primary"):
            add_aspect(a_name, unit_type=aspect_unit_type)
            st.success(f"Aspek '{a_name}' ({aspect_unit_type}) berhasil ditambahkan.")
            st.rerun()

    st.divider()
    st.dataframe(get_aspects(unit_type=aspect_unit_type), use_container_width=True, hide_index=True)
    if aspect_unit_type == "UP3":
        st.caption(
            "Aspek default UP3 sesuai dokumen resmi: Sumber Daya Manusia, Anggaran dan Pengelolaan Keuangan, "
            "Tata Kelola, Infrastruktur, Peralatan Penunjang Operasional, Kinerja. (skala Level 1-5)"
        )
    else:
        st.caption(
            "Aspek default ULP: Sumber Daya Manusia, Tata Kelola, Infrastruktur, "
            "Peralatan Penunjang Operasional, Kinerja. (skala Level 1-3)"
        )

# ---------------------------------------------------------------------------
with tab_indicators:
    st.subheader("Kelola Indikator & Rubrik Level")
    ind_unit_type = st.radio("Kriteria untuk", ["UP3", "ULP"], horizontal=True, key="ind_unit_type")
    max_lv = 5 if ind_unit_type == "UP3" else 3
    aspects_df = get_aspects(unit_type=ind_unit_type)

    if aspects_df.empty:
        st.warning("Buat Aspek terlebih dahulu di tab 'Aspek'.")
    else:
        with st.form("new_indicator_form"):
            c1, c2 = st.columns([2, 2])
            aspect_label = c1.selectbox("Aspek", aspects_df["name"].tolist())
            i_name = c2.text_input("Nama Indikator")
            if st.form_submit_button("Tambah Indikator", type="primary"):
                aspect_id = aspects_df[aspects_df["name"] == aspect_label].iloc[0]["id"]
                add_indicator(aspect_id, i_name, maximum_score=max_lv)
                st.success(f"Indikator '{i_name}' berhasil ditambahkan. Jangan lupa tambah rubrik level 1-{max_lv} di bawah.")
                st.rerun()

        st.divider()
        aspect_ids_this_type = set(aspects_df["id"].tolist())
        indicators = [i for i in get_indicators() if i["aspect_id"] in aspect_ids_this_type]
        if indicators:
            aspect_name_map = {a["id"]: a["name"] for _, a in aspects_df.iterrows()}
            ind_df = pd.DataFrame([{
                "name": i["name"], "aspect_name": aspect_name_map.get(i["aspect_id"], "-"),
                "jumlah_level": len(i["levels"]),
            } for i in indicators])
            st.dataframe(
                ind_df.rename(columns={"name": "Indikator", "aspect_name": "Aspek", "jumlah_level": "Jml Level"}),
                use_container_width=True, hide_index=True,
            )

            st.markdown("#### Tambah / Ubah Rubrik Level")
            ind_labels = {f"{i['name']} ({aspect_name_map.get(i['aspect_id'], '-')})": i["id"] for i in indicators}
            with st.form("new_level_form"):
                c1, c2, c3 = st.columns([2, 1, 3])
                ind_label = c1.selectbox("Indikator", list(ind_labels.keys()))
                lv_level = c2.selectbox("Level ke-", list(range(1, max_lv + 1)))
                lv_desc = c3.text_area("Kriteria / deskripsi level ini", height=80)
                if st.form_submit_button("Simpan Level"):
                    add_level(ind_labels[ind_label], lv_level, lv_desc)
                    st.success("Level berhasil disimpan.")
                    st.rerun()

            with st.expander("Lihat semua rubrik indikator yang sudah ada"):
                pick = st.selectbox("Pilih indikator", list(ind_labels.keys()), key="preview_ind")
                ind_obj = next(i for i in indicators if i["id"] == ind_labels[pick])
                for lv in sorted(ind_obj["levels"], key=lambda x: x["level"]):
                    st.write(f"**Level {lv['level']}:** {lv['level_label']}")
        else:
            st.info("Belum ada indikator untuk tipe ini.")

# ---------------------------------------------------------------------------
with tab_weights:
    st.subheader("Bobot Aspek per Periode")
    st.caption(
        "Sesuai dokumen resmi, bobot ditetapkan di level **Aspek** (bukan per indikator). "
        "Nilai tiap indikator otomatis dibagi rata terhadap jumlah indikator dalam aspek tersebut. "
        "Bobot di-snapshot per periode — periode yang sudah **LOCKED** tidak bisa diubah bobotnya."
    )

    weight_unit_type = st.radio("Kriteria untuk", ["UP3", "ULP"], horizontal=True, key="weight_unit_type")

    periods_df = get_periods().copy()
    periods_df["label"] = periods_df.apply(lambda r: f"{r['month']:02d}/{r['year']} ({r['status']})", axis=1)
    period_label = st.selectbox("Periode", periods_df["label"].tolist())
    period_row = periods_df[periods_df["label"] == period_label].iloc[0]

    aspects_df = get_aspects(unit_type=weight_unit_type)
    if aspects_df.empty:
        st.info("Belum ada aspek untuk tipe ini.")
    else:
        with st.form(f"weights_form_{weight_unit_type}"):
            new_weights = {}
            for _, aspect in aspects_df.iterrows():
                jml_indikator = len(get_indicators(aspect["id"]))
                default_weight = get_aspect_weight(period_row["id"], aspect["id"])
                new_weights[aspect["id"]] = st.number_input(
                    f"{aspect['name']} ({jml_indikator} indikator)",
                    min_value=0.0, max_value=100.0, value=float(default_weight), step=1.0,
                    key=f"weight_{aspect['id']}_{period_row['id']}",
                )
            total_weight = sum(new_weights.values())
            st.caption(f"Total bobot saat ini: **{total_weight:.1f}** (idealnya = 100)")

            if st.form_submit_button("Simpan Semua Bobot Aspek", type="primary"):
                try:
                    for aspect_id, w in new_weights.items():
                        set_aspect_weight(period_row["id"], aspect_id, w)
                    st.success("Bobot aspek berhasil disimpan.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

        st.divider()
        st.markdown("#### Bobot Default (sesuai dokumen resmi)")
        if weight_unit_type == "UP3":
            st.write("Sumber Daya Manusia: **10** · Anggaran dan Pengelolaan Keuangan: **10** · "
                     "Tata Kelola: **30** · Infrastruktur: **10** · Peralatan Penunjang Operasional: **10** · "
                     "Kinerja: **30** &nbsp; (Total = 100, skala Level 1-5)")
        else:
            st.write("Sumber Daya Manusia: **20** · Tata Kelola: **30** · Infrastruktur: **10** · "
                     "Peralatan Penunjang Operasional: **20** · Kinerja: **20** "
                     "&nbsp; (Total = 100, skala Level 1-3)")

# ---------------------------------------------------------------------------
with tab_backup:
    st.subheader("Backup & Restore Data")
    st.warning(
        "Mode prototipe ini menyimpan data di memori server, BUKAN database permanen. "
        "Kalau server sempat restart/tidur (misal aplikasi lama tidak diakses), data bisa "
        "kembali ke kondisi awal. **Download backup secara rutin** (disarankan tiap akhir hari "
        "kerja, atau setelah banyak assessment baru masuk) supaya ada cadangan yang bisa dipulihkan."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Download Backup")
        st.caption("Simpan seluruh data (unit, periode, assessment, evidence, kredensial) jadi satu file JSON.")
        backup_json = export_data_json()
        filename = f"simona_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json"
        st.download_button(
            "Download Backup Sekarang", data=backup_json, file_name=filename,
            mime="application/json", type="primary", use_container_width=True,
        )
        st.caption(f"Ukuran file: ~{len(backup_json) / 1024:.0f} KB")

    with col2:
        st.markdown("#### Restore dari Backup")
        st.caption("Upload file backup JSON untuk memulihkan data. Ini akan MENIMPA seluruh data yang sedang aktif sekarang.")
        uploaded = st.file_uploader("Pilih file backup (.json)", type=["json"])
        if uploaded is not None:
            st.error("⚠️ Restore akan menimpa SEMUA data yang sedang berjalan untuk SEMUA user saat ini. Pastikan file backup benar.")
            confirm = st.checkbox("Saya yakin ingin menimpa data yang sedang aktif dengan file backup ini.")
            if st.button("Restore Sekarang", disabled=not confirm, type="primary", use_container_width=True):
                try:
                    import_data_json(uploaded.getvalue().decode("utf-8"))
                    st.success("Data berhasil dipulihkan dari backup.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal memulihkan backup: {e}")
