"""Approved curriculum (المنهاج المعتمد) + assignment ↔ curriculum mismatches.

- The approved curriculum is available in every mode (wizard / upload); a school may replace it by its own file.
- When the assignment hours differ from the curriculum, the manager must correct ONE of them for every
  difference (assignment -> curriculum hours, or curriculum -> assignment hours) before generating.
"""
import io
import os

import pandas as pd

import i18n
from i18n import t

HERE = os.path.dirname(os.path.abspath(__file__))
APPROVED_PATH = os.path.join(HERE, "sample_data", "curriculum.csv")
YEAR = "2026/2027"

i18n.S.update({
    "curr_approved": ("Approved curriculum {y}", "المنهاج المعتمد لسنة {y}"),
    "curr_using_approved": ("📘 **Approved curriculum {y}** is used. Upload your own curriculum file only if your school differs.",
                            "📘 يُستعمل **المنهاج المعتمد لسنة {y}**. لا ترفع ملف منهاج إلا إذا كانت مؤسستك مختلفة."),
    "curr_using_custom": ("📗 Your own curriculum file is used instead of the approved curriculum {y}.",
                          "📗 يُستعمل ملف المنهاج الخاص بك بدل المنهاج المعتمد لسنة {y}."),
    "curr_download": ("⬇️ Download the approved curriculum", "⬇️ تنزيل المنهاج المعتمد"),
    "curr_upload": ("Replace by another curriculum (.csv / .xlsx)", "استبداله بمنهاج آخر (‎.csv / .xlsx)"),
    "curr_revert": ("↩️ Back to the approved curriculum", "↩️ العودة إلى المنهاج المعتمد"),
    "curr_bad_file": ("This file is not a curriculum (columns Level, Subject_Code, Hrs_Cours… expected).",
                      "هذا الملف ليس منهاجًا (يُنتظر أعمدة المستوى، رمز المادة، ساعات الدرس…)."),
    "curr_fixed_n": ("✏️ {n} curriculum line(s) changed to match the assignment.",
                     "✏️ عُدّل {n} سطر في المنهاج ليطابق الإسناد."),
    # mismatches
    "mm_title": ("⚠️ The assignment does not match the curriculum in {n} case(s)",
                 "⚠️ الإسناد لا يطابق المنهاج في {n} حالة"),
    "mm_explain": ("For each line, choose which one to correct. The timetable can only be generated when the assignment "
                   "and the curriculum agree. Changing the curriculum applies to the whole level.",
                   "اختر لكل سطر ما يجب تصحيحه. لا يمكن توليد التوزيع الزمني إلا إذا تطابق الإسناد والمنهاج. "
                   "تعديل المنهاج يسري على كل أفواج المستوى."),
    "mm_c_class": ("Class", "الفوج"), "mm_c_subject": ("Subject", "المادة"), "mm_c_teacher": ("Teacher", "الأستاذ"),
    "mm_c_assign": ("Assignment h", "ساعات الإسناد"), "mm_c_curr": ("Curriculum h", "ساعات المنهاج"),
    "mm_c_fix": ("Correction", "التصحيح"),
    "mm_fix_assign": ("Assignment ← curriculum hours", "تعديل الإسناد ← ساعات المنهاج"),
    "mm_fix_curr": ("Curriculum ← assignment hours", "تعديل المنهاج ← ساعات الإسناد"),
    "mm_all_assign": ("All: correct the assignment", "الكل: تعديل الإسناد"),
    "mm_all_curr": ("All: correct the curriculum", "الكل: تعديل المنهاج"),
    "mm_level_note": ("ℹ️ The curriculum was changed for a whole level, so the other classes of that level may now differ – "
                      "check the new lines.",
                      "ℹ️ عُدّل المنهاج لمستوى كامل، لذلك قد تختلف الآن أفواج أخرى من نفس المستوى – راجع الأسطر الجديدة."),
    "mm_apply": ("✅ Apply the corrections", "✅ تطبيق التصحيحات"),
    "mm_pick_all": ("Choose a correction for every line.", "اختر تصحيحًا لكل سطر."),
    "mm_done": ("Corrections applied: {a} in the assignment, {c} in the curriculum.",
                "طُبّقت التصحيحات: {a} في الإسناد، {c} في المنهاج."),
    "mm_block": ("⛔ Generation is blocked: the assignment and the curriculum differ in {n} case(s). Correct them below "
                 "or on the 👥 Assignment page.",
                 "⛔ التوليد متوقف: الإسناد والمنهاج مختلفان في {n} حالة. صحّحها أدناه أو في صفحة 👥 الإسناد."),
})


def approved():
    return pd.read_csv(APPROVED_PATH)


def label():
    return t("curr_approved", y=YEAR)


def is_curriculum(df):
    return df is not None and {"Level", "Subject_Code", "Hrs_Cours"} <= set(df.columns)


def approved_bytes():
    import datai18n as dl
    return dl.to_local(approved()).to_csv(index=False).encode("utf-8-sig")


# ------------------------------------------------------------------ corrections of the curriculum
def apply_fixes(subjects, fixes, hours_fn):
    """fixes {(level, subject): total weekly hours}.  Hrs_Cours absorbs the change (TD/TP parts come from the
    split rules / other columns and stay as they are)."""
    if not fixes or subjects is None:
        return subjects
    df = subjects.copy()
    for (lvl, subj), total in fixes.items():
        m = (df["Level"] == lvl) & (df["Subject_Code"] == subj)
        cur = hours_fn(lvl, subj) if m.any() else 0
        if m.any():
            i = df.index[m][0]
            df.at[i, "Hrs_Cours"] = max(0, int(df.at[i, "Hrs_Cours"]) + int(total) - int(cur))
        else:
            row = {c: 0 for c in df.columns}
            row.update(Level=lvl, Subject_Code=subj, Hrs_Cours=int(total))
            if "Required_Room_Type" in df.columns:
                row["Required_Room_Type"] = "classroom"
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return df


# ------------------------------------------------------------------ mismatches
def mismatches(plan, data_frames):
    """Rows (idx, Class, Level, Subject, Teacher, Assign, Curr) where the assignment hours differ."""
    if plan is None or data_frames.get("subjects") is None:
        return pd.DataFrame()
    from engine import SchedulerConfig, SchoolSchedulerEngine
    import assignment_planner as ap
    dfc = dict(data_frames)
    dfc.setdefault("classes", plan["classes"])
    dfc["teachers"] = plan["teachers"]
    probe = SchoolSchedulerEngine(ap.make_loader(dfc), SchedulerConfig(), fixed_assignment=plan["assignment"])
    levels = dict(zip(dfc["classes"]["Class_ID"], dfc["classes"]["Level"]))
    rows = []
    for i, r in plan["assignment"].iterrows():
        lvl = levels.get(r["Class"])
        need = probe._calculate_required_hours(lvl, r["Subject"])
        if int(need) != int(r["Hours"]):
            rows.append(dict(idx=i, Class=r["Class"], Level=lvl, Subject=r["Subject"], Teacher=r["Teacher"],
                             Assign=int(r["Hours"]), Curr=int(need)))
    return pd.DataFrame(rows)


def render_panel(st, mm, key):
    """Correction table.  Returns (assign_fixes {idx: hours}, curr_fixes {(lvl, subj): hours}) when applied."""
    st.error(t("mm_title", n=len(mm)))
    st.caption(t("mm_explain"))
    if st.session_state.get("curr_fix"):
        st.info(t("mm_level_note") + "  \n" + t("curr_fixed_n", n=len(st.session_state["curr_fix"])))
    opts = ["", "assign", "curr"]
    fmt = {"": "—", "assign": t("mm_fix_assign"), "curr": t("mm_fix_curr")}
    default = st.session_state.get(f"mm_all_{key}", "")
    b1, b2, _ = st.columns([1, 1, 2])
    if b1.button(t("mm_all_assign"), key=f"mm_aa_{key}"):
        st.session_state[f"mm_all_{key}"] = "assign"; st.session_state.pop(f"mm_ed_{key}", None); st.rerun()
    if b2.button(t("mm_all_curr"), key=f"mm_ac_{key}"):
        st.session_state[f"mm_all_{key}"] = "curr"; st.session_state.pop(f"mm_ed_{key}", None); st.rerun()
    view = pd.DataFrame({
        "Class": mm["Class"].map(i18n.cls), "Subject": mm["Subject"].map(i18n.subj), "Teacher": mm["Teacher"],
        "Assign": mm["Assign"], "Curr": mm["Curr"], "Fix": [fmt[default]] * len(mm)})
    ed = st.data_editor(view, hide_index=True, width="stretch", key=f"mm_ed_{key}",
                        disabled=["Class", "Subject", "Teacher", "Assign", "Curr"],
                        column_config={
                            "Class": st.column_config.TextColumn(t("mm_c_class")),
                            "Subject": st.column_config.TextColumn(t("mm_c_subject")),
                            "Teacher": st.column_config.TextColumn(t("mm_c_teacher")),
                            "Assign": st.column_config.NumberColumn(t("mm_c_assign")),
                            "Curr": st.column_config.NumberColumn(t("mm_c_curr")),
                            "Fix": st.column_config.SelectboxColumn(t("mm_c_fix"), options=[fmt[o] for o in opts],
                                                                    required=True)})
    if not st.button(t("mm_apply"), type="primary", key=f"mm_apply_{key}"):
        return None
    back = {v: k for k, v in fmt.items()}
    choice = [back.get(x, "") for x in ed["Fix"]]
    if "" in choice:
        st.warning(t("mm_pick_all"))
        return None
    a_fix, c_fix = {}, {}
    for (_, r), ch in zip(mm.iterrows(), choice):
        if ch == "assign":
            a_fix[int(r["idx"])] = int(r["Curr"])
        else:
            c_fix[(r["Level"], r["Subject"])] = int(r["Assign"])
    return a_fix, c_fix


def hours_fn(plan, data_frames):
    """Curriculum weekly hours per (level, subject), split rules included (same as the engine)."""
    from engine import SchedulerConfig, SchoolSchedulerEngine
    import assignment_planner as ap
    dfc = dict(data_frames)
    dfc.setdefault("classes", plan["classes"])
    dfc["teachers"] = plan["teachers"]
    probe = SchoolSchedulerEngine(ap.make_loader(dfc), SchedulerConfig(), fixed_assignment=plan["assignment"])
    return probe._calculate_required_hours


def same_as_approved(df):
    """True when an uploaded curriculum is just the approved one (e.g. inside a zip downloaded from the app)."""
    try:
        a = approved()
        cols = ["Level", "Subject_Code", "Hrs_Cours", "Hrs_TD", "Hrs_TP", "Hrs_Practice"]
        k = lambda d: d[cols].astype(str).sort_values(cols).reset_index(drop=True)
        return k(a).equals(k(df))
    except Exception:
        return False
