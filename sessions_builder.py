"""Simple creation of groupings: parallel groups (class divided, different subjects at the same time),
divided lessons (class divided, the same teacher teaches each group in turn) and multi-class sessions.
Each form adds one row to its table (split rules / divided lessons / joint sessions); the tables stay editable,
exportable and importable on the Data page."""
import pandas as pd

import i18n
from i18n import t
import tables
from engine import DIVIDED_COLS

RULE_COLS = ["Rule_ID", "Level", "Primary_Subject", "Primary_Type", "Primary_Hours", "Secondary_Subject",
             "Secondary_Type", "Secondary_Hours", "Frequency", "Description"]


def _next_id(df, col, prefix):
    used = set(df[col].astype(str)) if df is not None and col in df else set()
    i = 1
    while f"{prefix}{i:02d}" in used:
        i += 1
    return f"{prefix}{i:02d}"


def _subjects(dfs, levels):
    cur = dfs["subjects"]
    if levels:
        cur = cur[cur["Level"].astype(str).isin(levels)]
    return sorted(cur["Subject_Code"].astype(str).unique())


def _hours(dfs, levels, subj, col):
    cur = dfs["subjects"]
    cur = cur[(cur["Subject_Code"] == subj) & (cur["Level"].astype(str).isin(levels))]
    return sorted({int(x) for x in pd.to_numeric(cur[col], errors="coerce").fillna(0)})


def _append(db, ws, name, df, row, cols):
    base = df if df is not None else pd.DataFrame(columns=cols)
    new = pd.concat([base.astype(str), pd.DataFrame([{c: str(row.get(c, "")) for c in cols}])], ignore_index=True)
    tables.save(db, ws, name, new)


def render(st, db, ws, src, dfs):
    if dfs.get("subjects") is None or dfs.get("classes") is None:
        return
    levels = list(dict.fromkeys(dfs["classes"]["Level"].astype(str)))
    lvl_fmt = lambda x: x
    st.caption(t("sb_help"))
    tab1, tab2, tab3 = st.tabs([t("sb_par"), t("sb_div"), t("sb_joint")])

    # ---------------------------------------------------------------- 1. parallel groups (split rule)
    with tab1:
        st.caption(t("sb_par_help"))
        lv = st.multiselect(t("sb_levels"), levels, levels[:1], key="sb_p_lv", format_func=lvl_fmt)
        subs = _subjects(dfs, lv)
        c1, c2 = st.columns(2)
        c1.markdown("**" + t("sb_group", g="A") + "**")
        pa = c1.selectbox(t("sb_subject"), subs, key="sb_p_a", format_func=i18n.subj)
        pa_t = c1.radio(t("sb_type"), ["TD", "TP"], horizontal=True, key="sb_p_at")
        pa_h = int(c1.number_input(t("sb_hours_group"), 1, 6, 1, key="sb_p_ah"))
        c2.markdown("**" + t("sb_group", g="B") + "**")
        pb = c2.multiselect(t("sb_subjects_seq"), [x for x in subs if x != pa], key="sb_p_b", format_func=i18n.subj,
                            max_selections=3)
        pb_t = c2.radio(t("sb_type"), ["TD", "TP"], horizontal=True, key="sb_p_bt")
        pb_h = [int(c2.number_input(t("sb_hours_of", s=i18n.subj(x)), 1, 6, 1 if len(pb) > 1 else pa_h, key=f"sb_p_bh_{x}"))
                for x in pb]
        swap = st.radio(t("sb_swap"), ["block", "week"], horizontal=True, key="sb_p_sw",
                        format_func=lambda x: t("sb_swap_" + x))
        if pa and pb:
            desc = t("sb_par_desc", a=i18n.subj(pa), ha=pa_h, b=" → ".join(i18n.subj(x) for x in pb), hb=sum(pb_h),
                     w=t("sb_swap_" + swap))
            st.info(desc)
            if sum(pb_h) != pa_h:
                st.warning(t("sb_par_len", a=pa_h, b=sum(pb_h)))
            miss = [f"{x} ({ty})" for x, ty in [(pa, pa_t)] + [(y, pb_t) for y in pb]
                    if not any(h > 0 for h in _hours(dfs, lv, x, "Hrs_" + ty))]
            if miss:
                st.warning(t("sb_no_hours", s=", ".join(miss)))
            if st.button(t("sb_add"), type="primary", key="sb_p_add", disabled=not lv):
                r = dfs.get("rules")
                _append(db, ws, f"tbl_{src}_rules", r, {
                    "Rule_ID": _next_id(r, "Rule_ID", "R_G"), "Level": "ALL" if sorted(lv) == sorted(levels) else ";".join(lv),
                    "Primary_Subject": pa, "Primary_Type": pa_t, "Primary_Hours": pa_h,
                    "Secondary_Subject": ";".join(pb), "Secondary_Type": pb_t, "Secondary_Hours": ";".join(map(str, pb_h)),
                    "Frequency": 1 if swap == "block" else 2, "Description": desc},
                    list(r.columns) if r is not None and len(r.columns) else RULE_COLS)
                st.toast("✅"); st.rerun()

    # ---------------------------------------------------------------- 2. divided lesson (same teacher, groups in turn)
    with tab2:
        st.caption(t("sb_div_help"))
        lv = st.multiselect(t("sb_levels"), levels, levels[:1], key="sb_d_lv", format_func=lvl_fmt)
        c1, c2, c3, c4 = st.columns(4)
        sj = c1.selectbox(t("sb_subject"), _subjects(dfs, lv), key="sb_d_s", format_func=i18n.subj)
        ty = c2.selectbox(t("sb_type"), ["TD", "TP", "TD+TP"], key="sb_d_t")
        g = int(c3.number_input(t("sb_groups"), 2, 4, 2, key="sb_d_g"))
        blk = int(c4.selectbox(t("sb_block"), [1, 2], key="sb_d_b"))
        if sj and lv:
            cols = ["Hrs_TD", "Hrs_TP"] if ty == "TD+TP" else ["Hrs_" + ty]
            cur = dfs["subjects"]
            cur = cur[(cur["Subject_Code"] == sj) & (cur["Level"].astype(str).isin(lv))]
            hs = sorted({int(sum(int(float(r[c] or 0)) for c in cols)) for r in cur.to_dict("records")})
            if not hs or max(hs) == 0:
                st.warning(t("sb_no_hours", s=f"{sj} ({ty})"))
            else:
                st.info(t("sb_div_desc", s=i18n.subj(sj), h="/".join(map(str, hs)), g=g, th="/".join(str(h * g) for h in hs)))
            d = dfs.get("divided")
            if st.button(t("sb_add"), type="primary", key="sb_d_add", disabled=not hs or max(hs) == 0):
                _append(db, ws, "divided", d, {"ID": _next_id(d, "ID", "D"), "Levels": "ALL" if sorted(lv) == sorted(levels) else ";".join(lv),
                                               "Subject": sj, "Type": ty, "Groups": g, "Block": blk}, DIVIDED_COLS)
                st.toast("✅"); st.rerun()

    # ---------------------------------------------------------------- 3. multi-class session (joint)
    with tab3:
        st.caption(t("sb_joint_help"))
        cls = st.multiselect(t("js_classes"), dfs["classes"]["Class_ID"].astype(str).tolist(), key="sb_j_c",
                             format_func=i18n.cls)
        lvls = sorted(set(dfs["classes"][dfs["classes"]["Class_ID"].astype(str).isin(cls)]["Level"].astype(str)))
        sjs = st.multiselect(t("js_subjects"), _subjects(dfs, lvls), key="sb_j_s", format_func=i18n.subj)
        hc = sorted({h for x in sjs for h in _hours(dfs, lvls, x, "Hrs_Cours")})
        c1, c2 = st.columns(2)
        h = int(c1.number_input(t("js_hours"), 1, 10, hc[0] if hc else 1, key=f"sb_j_h_{'_'.join(sjs)}"))
        blk = int(c2.selectbox(t("js_block"), [1, 2], key="sb_j_b"))
        if len(cls) >= 2 and sjs:
            st.info(t("sb_joint_desc", c=", ".join(map(i18n.cls, cls)), s=" | ".join(map(i18n.subj, sjs)), h=h))
            if len(hc) > 1 or (hc and hc[0] != h):
                st.warning(t("sb_joint_hours", h=h, c="/".join(map(str, hc))))
            j = dfs.get("joint_sessions")
            if st.button(t("sb_add"), type="primary", key="sb_j_add"):
                import presets
                _append(db, ws, "joint_sessions", j, {"ID": _next_id(j, "ID", "J"), "Classes": ";".join(cls),
                                                      "Subjects": ";".join(sjs), "Hours": h, "Block": blk}, presets.JOINT_COLS)
                st.toast("✅"); st.rerun()
        elif cls or sjs:
            st.caption(t("sb_joint_need"))
