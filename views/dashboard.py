import streamlit as st
import plotly.express as px
import pandas as pd
from data import (
    init_demo_data, get_periods, get_units, compute_unit_total_score,
    compute_aspect_scores, compute_evidence_completion,
)
from ui import render_topbar, render_sidebar_profile

init_demo_data()
render_topbar()
render_sidebar_profile()

if not st.session_state.get("is_authenticated"):
    st.warning("Silakan masuk terlebih dahulu di halaman utama.")
    st.stop()

role = st.session_state["role"]
unit_id = st.session_state["unit_id"]

st.title("Dashboard Maturity Level Gudang Distribusi")

periods_df = get_periods().copy()
periods_df["label"] = periods_df.apply(lambda r: f"{r['month']:02d}/{r['year']} ({r['status']})", axis=1)
selected_label = st.selectbox("Periode", periods_df["label"].tolist())
period_row = periods_df[periods_df["label"] == selected_label].iloc[0]
period_id = period_row["id"]

st.divider()

# ---------------------------------------------------------------------------
# UID: lihat semua unit
# ---------------------------------------------------------------------------
if role == "UID":
    all_units = get_units()
    unit_rows = all_units[all_units["type"] != "UID"]

    scores = [compute_unit_total_score(u, period_id) for u in unit_rows["id"]]
    scores_df = pd.DataFrame(scores).merge(unit_rows[["id", "name", "type"]], left_on="unit_id", right_on="id")

    type_filter = st.radio("Tampilkan", ["Semua Unit", "UP3 saja", "ULP saja"], horizontal=True)
    if type_filter == "UP3 saja":
        scores_df = scores_df[scores_df["type"] == "UP3"]
    elif type_filter == "ULP saja":
        scores_df = scores_df[scores_df["type"] == "ULP"]

    total_units = len(scores_df)
    submitted = int(scores_df["submitted_indicators"].sum())
    draft = int(scores_df["draft_indicators"].sum())
    revision = int(scores_df["revision_indicators"].sum())
    approved = int(scores_df["approved_indicators"].sum())
    avg_matlev = round(scores_df["matlev"].mean(), 2) if not scores_df.empty else "-"

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Unit Gudang", total_units)
    c2.metric("Submitted", submitted)
    c3.metric("Draft", draft)
    c4.metric("Revisi", revision)
    c5.metric("Approved", approved)
    c6.metric("Rata-rata Matlev", avg_matlev)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Ranking Unit (Maturity Level)")
        rank_df = scores_df.sort_values("matlev", ascending=True)
        if not rank_df.empty:
            fig = px.bar(
                rank_df, x="matlev", y="name", orientation="h",
                color="matlev", color_continuous_scale="Blues", range_x=[0, 5],
                labels={"matlev": "Matlev (1-5)", "name": "Unit"},
                text="matlev",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada unit dengan skor pada periode ini.")

    with col2:
        st.subheader("Evidence Completion per Unit")
        ev_rows = [{"name": row["name"], "evidence_pct": compute_evidence_completion(row["unit_id"], period_id)}
                   for _, row in scores_df.iterrows()]
        ev_df = pd.DataFrame(ev_rows)
        if not ev_df.empty:
            fig2 = px.bar(ev_df, x="name", y="evidence_pct", color="evidence_pct",
                          color_continuous_scale="Teal", labels={"evidence_pct": "% Lengkap", "name": "Unit"})
            st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Radar Capaian per Aspek (rata-rata unit yang ditampilkan, dinormalisasi 0-100%)")
    st.caption("Dinormalisasi supaya UP3 (skala level 1-5) dan ULP (skala level 1-3) bisa dibandingkan secara adil.")
    agg_rows = []
    for _, row in scores_df.iterrows():
        adf = compute_aspect_scores(row["unit_id"], period_id)
        agg_rows.append(adf)
    if agg_rows:
        combined = pd.concat(agg_rows)
        agg = combined.groupby("aspect_name", as_index=False)["pct_achieved"].mean()
        fig3 = px.line_polar(agg, r="pct_achieved", theta="aspect_name", line_close=True, range_r=[0, 100])
        fig3.update_traces(fill="toself")
        st.plotly_chart(fig3, use_container_width=True)

    st.subheader("Tabel Monitoring per Unit")
    display_df = scores_df[["name", "type", "total_score", "matlev", "completion_percentage",
                             "submitted_indicators", "draft_indicators",
                             "revision_indicators", "approved_indicators"]].rename(columns={
        "name": "Unit", "type": "Tipe", "total_score": "Nilai (0-100)", "matlev": "Matlev",
        "completion_percentage": "Completion (%)",
        "submitted_indicators": "Submitted", "draft_indicators": "Draft",
        "revision_indicators": "Revisi", "approved_indicators": "Approved",
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    with st.expander("Contoh perhitungan (klik untuk lihat detail per aspek suatu unit)"):
        pick_unit = st.selectbox("Pilih unit", unit_rows["name"].tolist(), key="detail_unit")
        pick_unit_id = unit_rows[unit_rows["name"] == pick_unit].iloc[0]["id"]
        detail_df = compute_aspect_scores(pick_unit_id, period_id)
        st.dataframe(
            detail_df[["aspect_name", "aspect_score", "bobot_aspek", "avg_level", "max_level"]].rename(columns={
                "aspect_name": "Aspek", "aspect_score": "Kontribusi Nilai",
                "bobot_aspek": "Bobot Aspek", "avg_level": "Rata-rata Level", "max_level": "Skala Maks",
            }),
            use_container_width=True, hide_index=True,
        )
        st.caption(f"Total = {detail_df['aspect_score'].sum():.2f} → Matlev = {detail_df['aspect_score'].sum()/20:.2f}")

# ---------------------------------------------------------------------------
# UP3: lihat unit sendiri saja
# ---------------------------------------------------------------------------
else:
    my_score = compute_unit_total_score(unit_id, period_id)
    my_evidence = compute_evidence_completion(unit_id, period_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nilai Total (0-100)", my_score["total_score"])
    c2.metric("Maturity Level", f"{my_score['matlev']} / 5")
    c3.metric("Assessment Completion", f"{my_score['completion_percentage']}%")
    c4.metric("Evidence Completion", f"{my_evidence}%")

    st.divider()
    st.subheader("Rata-rata Level per Aspek")
    aspect_df = compute_aspect_scores(unit_id, period_id)
    if not aspect_df.empty:
        max_level_axis = int(aspect_df["max_level"].max()) if "max_level" in aspect_df else 5
        fig = px.bar(aspect_df, x="aspect_name", y="avg_level", color="avg_level",
                     color_continuous_scale="Blues", range_y=[0, max_level_axis],
                     labels={"aspect_name": "Aspek", "avg_level": f"Rata-rata Level (maks {max_level_axis})"})
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Rincian Kontribusi Nilai per Aspek")
        st.dataframe(
            aspect_df[["aspect_name", "aspect_score", "bobot_aspek", "avg_level", "max_level"]].rename(columns={
                "aspect_name": "Aspek", "aspect_score": "Kontribusi Nilai",
                "bobot_aspek": "Bobot Aspek", "avg_level": "Rata-rata Level", "max_level": "Skala Maks",
            }),
            use_container_width=True, hide_index=True,
        )

    if role == "UP3":
        from data import get_child_units
        ulp_units = get_child_units(unit_id)
        if not ulp_units.empty:
            st.divider()
            st.subheader("Monitoring ULP di Bawah Unit Ini")
            ulp_scores = pd.DataFrame([
                {**compute_unit_total_score(u, period_id), "name": name}
                for u, name in zip(ulp_units["id"], ulp_units["name"])
            ])
            display_ulp = ulp_scores[["name", "total_score", "matlev", "completion_percentage",
                                       "submitted_indicators", "draft_indicators",
                                       "revision_indicators", "approved_indicators"]].rename(columns={
                "name": "ULP", "total_score": "Nilai (0-100)", "matlev": "Matlev",
                "completion_percentage": "Completion (%)",
                "submitted_indicators": "Submitted", "draft_indicators": "Draft",
                "revision_indicators": "Revisi", "approved_indicators": "Approved",
            })
            st.dataframe(display_ulp, use_container_width=True, hide_index=True)
        else:
            st.caption("Tidak ada ULP terdaftar di bawah unit ini.")

    st.page_link("views/assessment.py", label="Isi Assessment Sekarang", icon=":material/arrow_forward:")
