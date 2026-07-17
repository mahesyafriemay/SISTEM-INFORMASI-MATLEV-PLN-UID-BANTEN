import streamlit as st
from data import (
    init_demo_data, get_periods, get_aspects, get_indicators, get_assessment,
    save_draft, submit_unit_assessments, add_evidence, get_aspect_weight,
    compute_unit_total_score,
)
from ui import render_topbar, render_sidebar_profile

init_demo_data()
render_topbar()
render_sidebar_profile()

if not st.session_state.get("is_authenticated"):
    st.warning("Silakan masuk terlebih dahulu di halaman utama.")
    st.stop()

role = st.session_state["role"]
if role not in ("UP3", "ULP"):
    st.error("Halaman ini khusus untuk role UP3/ULP (unit gudang). UID tidak input nilai, hanya me-review.")
    st.stop()

unit_id = st.session_state["unit_id"]
unit_name = st.session_state["unit_name"]
fullname = st.session_state["fullname"]

st.title("Self Assessment Maturity Level Gudang")
st.caption(f"Unit: **{unit_name}** ({role}) &middot; kriteria & skala level menyesuaikan tipe unit ini secara otomatis.")

aspects_df = get_aspects(unit_type=role)
max_level = 5 if role == "UP3" else 3

tab_isi, tab_panduan = st.tabs(["Isi Assessment", "Panduan & Kriteria Penilaian"])

# =============================================================================
# TAB: ISI ASSESSMENT
# =============================================================================
with tab_isi:
    periods_df = get_periods().copy()
    periods_df["label"] = periods_df.apply(lambda r: f"{r['month']:02d}/{r['year']} ({r['status']})", axis=1)
    selected_label = st.selectbox("Pilih Periode", periods_df["label"].tolist())
    period_row = periods_df[periods_df["label"] == selected_label].iloc[0]
    period_id = period_row["id"]
    is_period_locked = period_row["status"] == "LOCKED"

    if is_period_locked:
        st.warning(
            "Periode ini sudah **LOCKED** — data di bawah bersifat read-only "
            "(tidak bisa diedit lagi, sudah final)."
        )

    # ---- ringkasan progres di atas ----
    summary = compute_unit_total_score(unit_id, period_id)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nilai Saat Ini", f"{summary['total_score']} / 100")
    c2.metric("Maturity Level", f"{summary['matlev']} / 5")
    c3.metric("Approved", f"{summary['approved_indicators']} / {summary['total_indicators']}")
    c4.metric("Completion", f"{summary['completion_percentage']}%")
    st.progress(min(summary["completion_percentage"] / 100, 1.0))

    st.caption(
        f"Geser slider untuk pilih **Level 1-{max_level}** tiap indikator sesuai kondisi gudang saat ini — "
        "baca kriteria lengkapnya di tab **Panduan & Kriteria Penilaian** kalau ragu. "
        "Simpan Draft untuk menyimpan tanpa mengirim, atau Submit ketika seluruh indikator sudah lengkap."
    )
    st.divider()

    any_locked_for_edit = False

    for _, aspect in aspects_df.iterrows():
        indicators = get_indicators(aspect["id"])
        if not indicators:
            continue
        bobot_aspek = get_aspect_weight(period_id, aspect["id"])

        filled_count = sum(
            1 for ind in indicators
            if (get_assessment(unit_id, period_id, ind["id"]) or {}).get("level") is not None
        )
        header = f"{aspect['name']} · bobot {bobot_aspek} · {filled_count}/{len(indicators)} terisi"

        with st.expander(header, expanded=not is_period_locked):
            for ind in indicators:
                existing = get_assessment(unit_id, period_id, ind["id"]) or {}
                current_level = existing.get("level") or 1
                current_notes = existing.get("notes", "")
                current_status = existing.get("status", "DRAFT")
                is_locked = is_period_locked or current_status in ("SUBMITTED", "IN_REVIEW", "APPROVED")
                if is_locked:
                    any_locked_for_edit = True

                status_color = {
                    "DRAFT": "gray", "SUBMITTED": "blue", "IN_REVIEW": "orange",
                    "REVISION": "red", "APPROVED": "green",
                }.get(current_status, "gray")
                st.markdown(f"**{ind['name']}** &nbsp; :{status_color}[{current_status}]")

                col1, col2 = st.columns([2, 3])
                with col1:
                    level_options = list(range(1, max_level + 1))
                    selected_level = st.select_slider(
                        "Level", options=level_options, value=current_level,
                        key=f"level_{ind['id']}_{period_id}", disabled=is_locked,
                    )
                    level_map = {lv["level"]: lv["level_label"] for lv in ind["levels"]}
                    st.info(f"**Level {selected_level}:** {level_map.get(selected_level, '-')}")
                with col2:
                    notes = st.text_area("Catatan", value=current_notes, key=f"notes_{ind['id']}_{period_id}",
                                          disabled=is_locked, height=100)

                if not is_locked:
                    if st.button("Simpan Draft", key=f"save_{ind['id']}_{period_id}"):
                        save_draft(unit_id, period_id, ind["id"], selected_level, notes, fullname)
                        st.success("Tersimpan.")
                        st.rerun()

                st.markdown("_Evidence:_")
                evidences = existing.get("evidences", [])
                if evidences:
                    for idx, ev in enumerate(evidences):
                        c1, c2 = st.columns([4, 1])
                        c1.write(f"{ev['filename']} — diupload {ev['uploaded_at'].strftime('%d/%m/%Y %H:%M')}")
                        if ev.get("file_bytes"):
                            c2.download_button(
                                "Download", data=ev["file_bytes"], file_name=ev["filename"],
                                mime=ev.get("mime_type") or "application/octet-stream",
                                key=f"dl_{ind['id']}_{period_id}_{idx}",
                            )
                else:
                    st.caption("Belum ada evidence.")

                if not is_locked:
                    uploaded_file = st.file_uploader(
                        "Upload evidence baru",
                        type=["pdf", "png", "jpg", "jpeg", "xlsx", "xls", "docx", "doc"],
                        key=f"upload_{ind['id']}_{period_id}",
                    )
                    if uploaded_file is not None:
                        if st.button("Upload", key=f"upload_btn_{ind['id']}_{period_id}"):
                            add_evidence(
                                unit_id, period_id, ind["id"], uploaded_file.name, fullname,
                                file_bytes=uploaded_file.getvalue(), mime_type=uploaded_file.type,
                            )
                            st.success("Evidence terupload.")
                            st.rerun()

                st.divider()

    if not is_period_locked:
        st.markdown("### Kirim Assessment")
        if any_locked_for_edit:
            st.info("Beberapa indikator sudah SUBMITTED/APPROVED sehingga tidak bisa diedit lagi.")

        if st.button("Submit Semua Draft ke UID", type="primary"):
            count = submit_unit_assessments(unit_id, period_id, fullname)
            if count:
                st.success(f"{count} indikator berhasil di-submit dan menunggu review UID.")
            else:
                st.warning("Tidak ada draft yang bisa di-submit (isi minimal satu indikator dulu).")
            st.rerun()

# =============================================================================
# TAB: PANDUAN & KRITERIA
# =============================================================================
with tab_panduan:
    st.caption(
        f"Referensi lengkap kriteria penilaian untuk unit tipe **{role}** "
        f"(skala Level 1-{max_level}). Gunakan ini sebagai acuan sebelum memilih level di tab Isi Assessment."
    )

    aspect_filter = st.selectbox(
        "Filter Aspek", ["Semua Aspek"] + aspects_df["name"].tolist(), key="guide_aspect_filter"
    )

    for _, aspect in aspects_df.iterrows():
        if aspect_filter != "Semua Aspek" and aspect["name"] != aspect_filter:
            continue
        indicators = get_indicators(aspect["id"])
        if not indicators:
            continue
        bobot_aspek_juli = None  # bobot bisa beda per periode, tampilkan generik saja di panduan

        st.markdown(f"### {aspect['name']}")
        for ind in indicators:
            with st.container(border=True):
                st.markdown(f"**{ind['name']}**")
                levels_sorted = sorted(ind["levels"], key=lambda x: x["level"])
                for lv in levels_sorted:
                    st.markdown(f"- **Level {lv['level']}:** {lv['level_label']}")
        st.write("")
