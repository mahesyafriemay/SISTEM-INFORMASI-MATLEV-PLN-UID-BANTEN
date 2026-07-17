import streamlit as st
import pandas as pd
from data import (
    init_demo_data, get_units, get_periods, get_indicators, get_aspects,
    get_assessments_for_units, get_unit_by_id, approve_assessment, request_revision,
    get_reviews_for, get_assessment,
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

fullname = st.session_state["fullname"]

st.title("Review Assessment")
st.caption("Daftar assessment yang menunggu review dari seluruh unit gudang.")

periods_df = get_periods().copy()
periods_df["label"] = periods_df.apply(lambda r: f"{r['month']:02d}/{r['year']} ({r['status']})", axis=1)
selected_label = st.selectbox("Periode", periods_df["label"].tolist())
period_row = periods_df[periods_df["label"] == selected_label].iloc[0]
period_id = period_row["id"]

all_units = get_units()
unit_ids = all_units[all_units["type"] != "UID"]["id"].tolist()
all_assessments = get_assessments_for_units(unit_ids, period_id)

pending = [a for a in all_assessments if a["status"] in ("SUBMITTED", "IN_REVIEW")]

if not pending:
    st.success("Tidak ada assessment yang menunggu review saat ini.")
    st.stop()

indicators_all = get_indicators()
ind_lookup = {i["id"]: i for i in indicators_all}
aspects_lookup = {a["id"]: a["name"] for _, a in get_aspects().iterrows()}

rows = []
for a in pending:
    ind = ind_lookup.get(a["indicator_id"], {})
    unit = get_unit_by_id(a["unit_id"])
    rows.append({
        "unit_id": a["unit_id"], "indicator_id": a["indicator_id"],
        "unit_name": unit["name"] if unit else "-",
        "aspect_name": aspects_lookup.get(ind.get("aspect_id"), "-"),
        "indicator_name": ind.get("name", "-"),
        "level": a.get("level"), "score": a.get("score"), "status": a.get("status"),
        "notes": a.get("notes"),
    })
pending_df = pd.DataFrame(rows)

unit_filter = st.selectbox("Filter Unit", ["Semua"] + sorted(pending_df["unit_name"].unique().tolist()))
filtered_df = pending_df if unit_filter == "Semua" else pending_df[pending_df["unit_name"] == unit_filter]

st.dataframe(
    filtered_df[["unit_name", "aspect_name", "indicator_name", "level", "score", "status"]].rename(columns={
        "unit_name": "Unit", "aspect_name": "Aspek", "indicator_name": "Indikator",
        "level": "Level", "score": "Kontribusi Nilai", "status": "Status",
    }),
    use_container_width=True, hide_index=True,
)

st.divider()
st.markdown("### Detail & Keputusan")

filtered_df = filtered_df.copy()
filtered_df["display_label"] = filtered_df.apply(
    lambda r: f"{r['unit_name']} · {r['aspect_name']} · {r['indicator_name']}", axis=1
)
selected = st.selectbox("Pilih assessment untuk direview", filtered_df["display_label"].tolist())
row = filtered_df[filtered_df["display_label"] == selected].iloc[0]

col1, col2 = st.columns([2, 1])
with col1:
    st.write(f"**Unit:** {row['unit_name']}")
    st.write(f"**Aspek:** {row['aspect_name']}")
    st.write(f"**Indikator:** {row['indicator_name']}")
    st.write(f"**Level dipilih unit:** {row['level']} — **Kontribusi Nilai:** {row['score']}")
    ind_detail = ind_lookup.get(row["indicator_id"], {})
    level_desc = next((lv["level_label"] for lv in ind_detail.get("levels", []) if lv["level"] == row["level"]), "-")
    st.caption(f"Kriteria level {row['level']}: {level_desc}")
    st.write(f"**Catatan dari unit:** {row.get('notes') or '-'}")

    st.markdown("**Evidence:**")
    a_detail = get_assessment(row["unit_id"], period_id, row["indicator_id"]) or {}
    evidences = a_detail.get("evidences", [])
    if evidences:
        for idx, ev in enumerate(evidences):
            file_bytes = ev.get("file_bytes")
            mime_type = ev.get("mime_type") or ""
            c1, c2 = st.columns([4, 1])
            c1.write(f"{ev['filename']}")
            if file_bytes:
                c2.download_button(
                    "Download", data=file_bytes, file_name=ev["filename"],
                    mime=mime_type or "application/octet-stream",
                    key=f"review_dl_{idx}_{row['unit_id']}_{row['indicator_id']}",
                )
                if mime_type.startswith("image/"):
                    st.image(file_bytes, caption=ev["filename"], width=400)
                elif mime_type == "application/pdf":
                    import base64
                    b64 = base64.b64encode(file_bytes).decode()
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,{b64}" '
                        f'width="100%" height="500" style="border:1px solid #E4E9F2;border-radius:8px;">'
                        f'</iframe>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Konten file tidak tersimpan.")
    else:
        st.caption("Tidak ada evidence yang diupload.")

    st.markdown("**Riwayat Review:**")
    reviews = get_reviews_for(row["unit_id"], period_id, row["indicator_id"])
    if reviews:
        for rv in sorted(reviews, key=lambda x: x["time"], reverse=True):
            st.write(f"- `{rv['decision']}` oleh **{rv['reviewer']}**: {rv.get('comments') or '-'}")
    else:
        st.caption("Belum ada riwayat review.")

with col2:
    st.markdown("**Keputusan**")
    comments = st.text_area("Komentar", key="review_comments", height=100)

    if st.button("Approve", type="primary", use_container_width=True):
        approve_assessment(row["unit_id"], period_id, row["indicator_id"], fullname, comments)
        st.success("Assessment di-approve.")
        st.rerun()

    if st.button("Kembalikan untuk Revisi", use_container_width=True):
        if not comments.strip():
            st.error("Komentar wajib diisi ketika meminta revisi.")
        else:
            request_revision(row["unit_id"], period_id, row["indicator_id"], fullname, comments)
            st.warning("Assessment dikembalikan untuk revisi.")
            st.rerun()
