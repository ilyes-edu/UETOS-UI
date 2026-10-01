"""Lightweight UI to test the timetable scheduling logic (English / العربية).
Run:  streamlit run app.py
"""
import os
import re
import json
import time
import streamlit.components.v1 as components
import pandas as pd
import streamlit as st

import i18n
from i18n import t
from engine import (SchoolDataLoader, SchedulerConfig, SchoolSchedulerEngine,
                    SolutionManager, calculate_all_kpis, export_editable_state, teacher_stats, class_stats, class_slot_needs, teacher_fairness, grid_report,
                    repair, RepairMismatch, improve, IMPROVE_KPIS, IMPROVE_LINKS, cfg_from_dict)
from editor import ScheduleEditor
from assignment_matrix import (parse_assignment_matrix, read_any, build_matrix_xlsx,
                               validate_against_curriculum, CODE_TO_ARABIC, _class_key)
import assignment_planner as ap
import subject_mapping as sm
import split_rules_view as srv
import colors
import export
import wizard as wz
import rooms as rms
import datai18n as dl
import validate
import guide
import presolve
import reception
import store as dbstore
from ui_theme import apply_ui_theme      # UETOS UI kit - CSS-only theme (no logic)
import curriculum as curr
import zipfile
import io

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "sample_data")
FILES = {
    "teachers": "staff.csv", "classes": "classes.csv", "subjects": "curriculum.csv",
    "inspections": "pedagogical_windows.csv", "rooms": "rooms.csv",
    "rules": "split_rules.csv", "grid": "school_grid.csv",
}

# ------------------------------------------------------------------ language (must come first)
if "lang" not in st.session_state:
    st.session_state["lang"] = "ar"
i18n.set_lang(st.session_state["lang"])
st.set_page_config(page_title=t("page_title"), layout="wide")

lang_choice = st.sidebar.radio(t("language"), ["ar", "en"], horizontal=True,
                               index=0 if st.session_state["lang"] == "ar" else 1,
                               format_func=lambda x: "العربية" if x == "ar" else "English")
if lang_choice != st.session_state["lang"]:
    st.session_state["lang"] = lang_choice
    st.rerun()

# ------------------------------------------------------------------ navigation (one page runs per rerun)
ss = st.session_state
PAGES = ["data", "plan", "run", "tt", "cmp", "guide"]
_KEEP = {"src", "use_remedial", "max_time", "version_name", "allow_gaps", "allow_twice", "enforce_2h", "max_2h",
         "strict_grid", "morning_hard", "windows_hard", "lab_fallback", "prio", "workers"}
for _k in list(ss.keys()):          # keep settings alive while their page is not displayed
    if _k in _KEEP or str(_k).startswith("w_"):
        ss[_k] = ss[_k]
if ss.pop("_reset_vn", False):
    ss.pop("version_name", None)
if "_goto" in ss:
    ss["page"] = ss.pop("_goto")
if ss.get("page") == "edit" or st.query_params.get("p") == "edit":      # the editor now lives in the Timetables page
    ss["page"] = "tt"
if ss.get("page") not in PAGES:
    ss["page"] = st.query_params.get("p") if st.query_params.get("p") in PAGES else "data"
PAGE = ss["page"]
if st.query_params.get("p") != PAGE:
    st.query_params["p"] = PAGE


def goto(p, toast=None):
    """Switch page programmatically (optionally with a toast on arrival)."""
    ss["_goto"] = p
    if toast:
        ss["_toast"] = toast
    st.rerun()


nav_box = st.sidebar.container()


def render_nav(marks):
    with nav_box:
        st.radio(t("nav_title"), PAGES, key="page",
                 format_func=lambda p: f"{t('pg_' + p)} {marks.get(p, '')}".strip())


if "_toast" in ss:
    st.toast(ss.pop("_toast"), icon="✅")

st.markdown("""
<style>
  .block-container { padding-top: 1.6rem; max-width: 1500px; }
  .app-hero { background: linear-gradient(120deg, #1e3a5f 0%, #2e6f9e 60%, #3d8fb8 100%); color: #fff;
              border-radius: 14px; padding: 16px 22px 14px; margin-bottom: 14px; box-shadow: 0 3px 12px rgba(30,58,95,.18); }
  .app-hero-title { display: inline-block; font-size: 1.75rem; font-weight: 700; margin-inline-end: 12px; }
  .beta-badge { display: inline-block; background: #ffb300; color: #3e2700; font-weight: 700; font-size: .85rem;
                border-radius: 20px; padding: 3px 12px; vertical-align: middle; }
  .app-hero-sub { opacity: .88; font-size: .95rem; margin-top: 4px; }
  div[data-testid="stTabs"] button[role="tab"] { font-size: 1rem; padding: 6px 14px; }
  div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { background: #eef5fb; border-radius: 8px 8px 0 0; }
  section[data-testid="stSidebar"] h3 { font-size: 1.1rem; margin: .2rem 0 .1rem; color: #1e3a5f; }
  section[data-testid="stSidebar"] hr { margin: .6rem 0; }
  div[data-testid="stMetric"] { background: #f6f9fc; border: 1px solid #e3ebf3; border-radius: 10px; padding: 8px 12px; }
  div[data-testid="stExpander"] details { border-radius: 10px; }
  .stButton > button, .stDownloadButton > button { border-radius: 8px; }
  .small-screen { display: none; }
  @media (max-width: 900px) {
    .small-screen { display: block; background: #fff3cd; color: #664d03; border: 1px solid #ffe69c;
                    border-radius: 8px; padding: 8px 12px; margin-bottom: 10px; font-size: .9rem; }
    .app-hero-title { font-size: 1.25rem; }
  }
</style>""", unsafe_allow_html=True)

if i18n.is_ar():
    st.markdown("""
    <style>
      .stApp, section[data-testid="stSidebar"], .stMarkdown, .stAlert, .stCaption,
      div[data-testid="stExpander"], label, .stTabs, .stRadio, .stCheckbox, .stButton, h1, h2, h3, h4, p, li
        { direction: rtl; text-align: right; }
      div[data-testid="stNumberInput"] input, div[data-testid="stTextInput"] input { direction: rtl; }
      div[data-testid="stDataFrame"], div[data-testid="stDataEditor"], pre, code { direction: ltr; text-align: left; }
      section[data-testid="stSidebar"] { font-size: 15px; }
    </style>""", unsafe_allow_html=True)

apply_ui_theme(st)                        # UETOS UI kit - modern look, injected before the banner

st.markdown(f"""
<div class="app-hero">
  <div class="app-hero-title">🗓️ {t("app_title")}</div>
  <span class="beta-badge">{t("beta_badge")}</span>
  <div class="app-hero-sub">{t("app_subtitle")}</div>
</div>""", unsafe_allow_html=True)

@st.cache_resource(show_spinner=False)
def get_store():
    s_ = dbstore.Store()
    s_.import_folder("demo", os.path.join(HERE, "schedules"))      # reference version for the demo workspace
    return s_


DB = get_store()
_ws_q = st.query_params.get("ws", "demo")
WS = re.sub(r"\s+", " ", re.sub(r"[^\w\- .]", "", st.sidebar.text_input(
    t("workspace"), _ws_q, help=t("workspace_help") + ("" if DB.persistent else "\n\n" + t("db_local"))))).strip()[:60] or "demo"
if WS != _ws_q:
    st.query_params["ws"] = WS
    st.session_state.pop("ed", None)
    for _k in [k for k in st.session_state if str(k).startswith("wz") or k in ("plan_src", "plan")]:
        st.session_state.pop(_k, None)


class _Versions:
    """Same calls as the old file-based SolutionManager, stored in the database, per workspace."""
    def save(self, df, name, score=None, state=None):
        DB.save(WS, name, df, state)

    def load(self, name):
        return DB.load(WS, name)


manager = _Versions()
dnd_timetable = components.declare_component("dnd_timetable", path=os.path.join(HERE, "dnd_component"))
dnd_full = components.declare_component("dnd_full", path=os.path.join(HERE, "dnd_full"))
dnd_assign = components.declare_component("dnd_assign", path=os.path.join(HERE, "dnd_assign"))


def load_state(v):
    return DB.load_state(WS, v)


def loc_df(df, prefix):
    """Rename DataFrame columns through i18n keys '<prefix><col>'."""
    return df.rename(columns={c: t(prefix + c) for c in df.columns if (prefix + c) in i18n.S})


def kpi_frame(d):
    return {i18n.kpi(k): v for k, v in d.items()}


# ------------------------------------------------------------------ data
SIGNATURES = {
    "teachers": {"Teacher_ID", "Qualified_Subjects", "Max_Weekly_Hours"},
    "classes": {"Class_ID", "Level"},
    "subjects": {"Subject_Code", "Hrs_Cours", "Required_Room_Type"},
    "inspections": {"Subject_Code", "Day_Index", "Blocked_Slots"},
    "rooms": {"Room_Type", "Capacity"},
    "rules": {"Primary_Subject", "Secondary_Subject"},
}


ASSIGN_NAME = re.compile(r"assign|اسناد|إسناد|الإسناد|توزيع", re.I)


def detect(df, fname):
    cols = set(df.columns)
    for k, sig in SIGNATURES.items():
        if sig <= cols and not (k == "classes" and "Subject_Code" in cols):
            return k
    for k, f in FILES.items():
        if os.path.basename(fname).lower() == f:
            return k
    return "grid" if "grid" in fname.lower() else None


_SRC_FMT = lambda x: {"wizard": t("src_wizard"), "upload": t("src_upload"), "sample": t("src_sample")}[x]
if PAGE == "data":
    st.subheader(t("pg_data"))
    src = st.radio(t("source"), ["wizard", "upload", "sample"], format_func=_SRC_FMT, horizontal=True, key="src")
else:
    src = ss.get("src", "wizard")
data_frames, report = {}, []
WZ_PENDING = False
wz_proj = wz.load_project(DB, WS) if src in ("wizard", "upload") else None
if src in ("wizard", "upload"):          # Upload = the same guide, filled from the files (+ bulk loading panel)
    if st.session_state.get("wz_open", wz_proj is None):
        if "wz" not in st.session_state and wz_proj is not None:      # reopen: start from the saved answers
            st.session_state["wz"] = wz_proj["answers"]
            st.session_state["wz_teachers"] = wz_proj["teachers"]
            pa = wz_proj["plan"]["assignment"]
            st.session_state["wz_assign"] = {(c, s_): n for c, s_, n in zip(pa["Class"], pa["Subject"], pa["Teacher"])}
            st.session_state["wz_counts"] = None
        if PAGE == "data":
            render_nav(ss.get("_marks", {}))
            if st.button(t("wz_restart"), key="wz_restart_btn"):
                for k in [k for k in st.session_state if str(k).startswith("wz")]:
                    del st.session_state[k]
                st.session_state["wz_open"] = True
                st.rerun()
            if wz.render(st, dnd_assign, DB, WS, bulk=src == "upload"):
                st.session_state["wz_open"] = False
                goto("plan", t("wz_applied"))
            st.stop()
        WZ_PENDING = True
        data_frames = {"grid": None}
    else:
        if PAGE == "data":
            st.success(t("wz_project_ok", c=len(wz_proj["frames"]["classes"]), p=len(wz_proj["plan"]["teachers"])))
            if st.button(t("wz_reopen"), key="wz_reopen_btn"):
                st.session_state["wz_open"] = True
                st.rerun()
        data_frames = {k: v.copy() for k, v in wz_proj["frames"].items()}
        data_frames["grid"] = None
else:
    # default example = the school files in sample_data/ (assignment.csv = اسناد)
    data_frames = {k: pd.read_csv(os.path.join(SAMPLE, f)) for k, f in FILES.items()
                   if os.path.exists(os.path.join(SAMPLE, f))}
    data_frames.setdefault("grid", None)

# ---- subject-code mapping chosen by the user (school codes -> curriculum codes)
subj_map = st.session_state.get("subj_map", {})
data_frames = sm.apply_to_frames(data_frames, subj_map)

# ---- import a school assignment grid -> becomes the step-1 plan
mx_file = None                           # school assignment files are loaded through the guide (all modes)
def import_plan(fileobj, fname, key, origin):
    if st.session_state.get("plan_src") == key:
        return
    if "subjects" not in data_frames:
        st.warning(t("need_curriculum")); return
    try:
        known = data_frames["classes"]["Class_ID"].tolist() if "classes" in data_frames else None
        parsed = parse_assignment_matrix(read_any(fileobj), data_frames["subjects"]["Subject_Code"].unique(), known)
        a_mapped, map_conf = sm.apply_to_assignment(parsed["assignment"], subj_map)
        p = ap.finalize(a_mapped, parsed["remedial"])
        p["warnings"] = [w for w in parsed["warnings"]
                         if not (w[0] == "w_not_in_curr" and w[1]["s"] in subj_map)]
        p["warnings"] += [("w_map_conflict", {"c": c, "s": s_, "x": x}) for c, s_, x in map_conf]
        p["class_hours"] = parsed.get("class_hours", {})
        st.session_state.update(plan=p, plan_active=True, plan_src=key, plan_origin=origin)
    except Exception as ex:
        st.error(t("grid_read_error", e=ex))


SAMPLE_ASSIGN = os.path.join(SAMPLE, "assignment.csv")
if mx_file is not None:
    import_plan(mx_file, mx_file.name, f"{mx_file.name}:{mx_file.size}:{sorted(subj_map.items())}",
                ("o_import", {"f": mx_file.name}))
elif src == "sample" and os.path.exists(SAMPLE_ASSIGN):
    import_plan(SAMPLE_ASSIGN, SAMPLE_ASSIGN, f"sample:{sorted(subj_map.items())}", ("o_import", {"f": "اسناد.csv"}))
elif src in ("wizard", "upload") and wz_proj is not None:
    _k = f"wizard:{wz_proj['stamp']}"
    if st.session_state.get("plan_src") != _k:
        st.session_state.update(plan=wz_proj["plan"], plan_active=True, plan_src=_k, plan_origin=("o_wizard", {}))
elif str(st.session_state.get("plan_src", "")).startswith(("sample:", "wizard:")):
    st.session_state.update(plan_active=False, plan_src=None)   # left the example: drop its assignment

staff_original = data_frames.get("teachers")
plan = st.session_state.get("plan") if st.session_state.get("plan_active") else None
if plan is not None:
    if PAGE == "data":
        st.success(t("using_plan", p=len(plan["teachers"]), c=len(plan["classes"]),
                         o=i18n.tr_message(st.session_state.get("plan_origin", ""))))
    tdf = plan["teachers"].copy()
    if staff_original is not None and src in ("upload", "manual") and "Requires_Reception" in staff_original:
        staff = staff_original.set_index("Teacher_ID")
        tdf["Requires_Reception"] = tdf["Teacher_ID"].map(staff["Requires_Reception"]).map(
            lambda x: str(x).strip().lower() not in ("false", "0", "no", "لا", "nan", "")).where(
            tdf["Teacher_ID"].isin(staff.index), True)
    data_frames["teachers"] = tdf
    if "classes" not in data_frames:
        data_frames["classes"] = plan["classes"]

if ss.get("curr_fix_src") != ss.get("plan_src"):
    ss["curr_fix"], ss["curr_fix_src"] = {}, ss.get("plan_src")
if ss.get("curr_fix") and plan is not None and data_frames.get("subjects") is not None:
    data_frames["subjects"] = curr.apply_fixes(data_frames["subjects"], ss["curr_fix"],
                                               curr.hours_fn(plan, data_frames))


def mismatch_panel(key):
    """Assignment ↔ curriculum differences; the manager corrects one of them.  Returns the number left."""
    mm = curr.mismatches(plan, data_frames)
    if not len(mm):
        return 0
    res = curr.render_panel(st, mm, key)
    if res:
        a_fix, c_fix = res
        if a_fix:
            p_ = ss["plan"]; a_ = p_["assignment"].copy()
            for i_, h_ in a_fix.items():
                a_.at[i_, "Hours"] = h_
            rec_ = dict(zip(p_["teachers"]["Teacher_ID"], p_["teachers"].get("Requires_Reception", True)))
            new_ = ap.finalize(a_, p_.get("remedial"), p_.get("max_hours"), reception=rec_)
            for k_ in ("class_hours", "warnings", "notes"):
                if k_ in p_:
                    new_[k_] = p_[k_]
            ss["plan"] = new_
        if c_fix:
            ss.setdefault("curr_fix", {}).update(c_fix); ss["curr_fix_src"] = ss.get("plan_src")
        ss.pop("last", None)
        ss["_toast"] = t("mm_done", a=len(a_fix), c=len(c_fix))
        st.rerun()
    return len(mm)


missing = [k for k in FILES if k not in data_frames and k != "grid"]
if missing and src == "upload" and PAGE == "data":
    hint = t("or_build_plan") if missing == ["teachers"] else ""
    st.warning(t("still_needed", x="، ".join(t("ds_" + k) for k in missing) if i18n.is_ar()
                         else ", ".join(t("ds_" + k) for k in missing)) + hint)
data_ready = not missing and not WZ_PENDING
_n_versions = len(DB.versions(WS))
_last = ss.get("last")
ss["_marks"] = {"data": "✅" if data_ready else "⚠️", "plan": "✅" if plan is not None else "",
                "run": "✅" if _last and _last.get("sched") is not None else "",
                "tt": f"({_n_versions})" if _n_versions else "", "cmp": ""}
render_nav(ss["_marks"])

# ------------------------------------------------------------------ generation settings (run page)
d = SchedulerConfig()
RUN = PAGE == "run" and not WZ_PENDING
if RUN:
    st.subheader(t("pg_run"))
    run_pre = st.container()
    run_set = st.container(border=True)
else:
    run_pre = run_set = None


def W(box, fn, label, default, key, **kw):
    """Render a keyed setting widget in `box`, or return its remembered value when its page is not shown."""
    if box is None:
        return ss.get(key, default)
    if key in ss:
        return getattr(box, fn)(label, key=key, **kw)
    return getattr(box, fn)(label, value=default, key=key, **kw)


_row = run_set.columns([1, 1, 1.4]) if RUN else [None] * 3
use_remedial = W(_row[0], "checkbox", t("use_remedial"), True, "use_remedial", help=t("use_remedial_help"))
if wz_proj is not None and not wz_proj["answers"].get("rem_armath", True):
    _pre = st.session_state.setdefault("pre", {"joint": None, "units": None, "unit_fix": {}, "rem_ok": False,
                                              "ext": [], "fixed": {}, "src": None})
    if _pre.get("joint") is None and _pre.get("src") == st.session_state.get("plan_src"):
        _pre["joint"] = []
rem_groups = [{"ARABIC", "MATH"}]          # default; the «Before solving» panel decides (presolve.config_patch)
max_time = W(_row[1], "slider", t("max_time"), 600, "max_time", min_value=10, max_value=1800, step=10,
             help=t("max_time_help"))
version_name = W(_row[2], "text_input", t("save_as"), f"Version_{time.strftime('%Y%m%d_%H%M%S')}", "version_name")

# ---- advanced settings (optionally protected by a password: env ADMIN_PASSWORD or secrets admin_password)
adv = run_set.expander(t("advanced"), expanded=False) if RUN else None
unlocked = st.session_state.get("adv_ok", False)
if adv is not None and not unlocked:
    typed = adv.text_input(t("adv_password"), type="password", key="adv_pw")
    if typed:
        if DB.check_admin_password(typed):
            st.session_state["adv_ok"] = True; st.rerun()
        else:
            adv.error(t("adv_wrong"))
    adv.caption(t("adv_locked"))
_dis = not unlocked
if adv is not None:
    adv.caption(t("adv_caption"))
    adv.subheader(t("hard"))
allow_gaps = W(adv, "checkbox", t("allow_gaps"), d.allow_student_gaps, "allow_gaps", disabled=_dis)
allow_twice = W(adv, "checkbox", t("allow_twice"), d.allow_same_subject_twice_per_day, "allow_twice", disabled=_dis)
enforce_2h = W(adv, "checkbox", t("enforce_2h"), d.enforce_max_2h_courses_per_day, "enforce_2h", disabled=_dis)
max_2h = W(adv, "number_input", t("max_2h"), d.max_2h_courses_per_day, "max_2h", min_value=0, max_value=5,
           disabled=_dis or not enforce_2h)
strict_grid = W(adv, "checkbox", t("strict_grid"), d.strict_class_grid, "strict_grid", help=t("strict_grid_help"),
                disabled=_dis)
morning_hard = W(adv, "checkbox", t("morning_first"), d.morning_first_hard, "morning_hard", help=t("morning_first_help"),
                 disabled=_dis)
windows_hard = W(adv, "checkbox", t("windows_hard"), d.teacher_windows_hard, "windows_hard", help=t("windows_hard_help"),
                 disabled=_dis)
lab_fallback = W(adv, "checkbox", t("lab_fallback"), True, "lab_fallback", help=t("lab_fallback_help"), disabled=_dis)
if adv is not None:
    adv.subheader(t("fair_title"))
prio = W(adv, "slider", t("prio_strength"), float(d.teacher_priority_strength), "prio", min_value=1.0, max_value=6.0,
         step=0.5, help=t("prio_help"), disabled=_dis)
if adv is not None:
    adv.subheader(t("soft"))
# weights that only shape the student grid are meaningless while the strict grid is on -> hidden then
GRID_W = {"empty_morning_slot_penalty", "teacher_afternoon_penalty", "slot_1_penalty", "slot_4_penalty", "slot_5_penalty", "slot_7_penalty",
          "slot_7_equity_penalty"}
WEIGHTS = ["empty_morning_slot_penalty", "teacher_afternoon_penalty", "teacher_single_hour_weight",
           "teacher_single_gap_weight", "teacher_double_gap_weight", "teacher_working_day_weight",
           "slot_1_penalty", "slot_4_penalty", "slot_5_penalty", "slot_7_penalty",
           "slot_7_equity_penalty", "teacher_late_finish_weight"]
weights = {w: W(None if (strict_grid and w in GRID_W) else adv, "number_input", t("w_" + w), getattr(d, w), f"w_{w}",
                min_value=0, max_value=100000, step=10, disabled=_dis) for w in WEIGHTS}
if adv is not None:
    adv.subheader(t("solver"))
workers = W(adv, "slider", t("workers"), d.num_workers, "workers", min_value=1, max_value=16, disabled=_dis)
if adv is not None and unlocked:
    with adv.popover(t("pw_change")):
        p1 = st.text_input(t("pw_new"), type="password", key="pw1")
        p2 = st.text_input(t("pw_again"), type="password", key="pw2")
        if st.button(t("pw_save"), key="pw_save", disabled=not p1):
            if len(p1) < 6:
                st.error(t("pw_short"))
            elif p1 != p2:
                st.error(t("pw_mismatch"))
            else:
                DB.set_admin_password(p1); st.success(t("pw_saved"))
    if adv.button(t("adv_lock")):
        st.session_state["adv_ok"] = False; st.rerun()

_pre_ok = presolve.ready(st, plan, use_remedial)
run = False
_mm_left = 0
if RUN and data_ready and plan is not None:
    _mm_n = len(curr.mismatches(plan, data_frames))
    if _mm_n:
        with run_pre:
            st.error(t("mm_block", n=_mm_n))
            _mm_left = mismatch_panel("run")
if RUN:
    if data_ready and not _pre_ok:
        run_set.warning(t("pre_rem_need"))
    run = run_set.button(t("solve"), type="primary", width="stretch",
                         disabled=not data_ready or not _pre_ok or bool(_mm_left))
st.sidebar.caption(t("beta_footer"))


# ------------------------------------------------------------------ helpers
def versions():
    """Saved versions, oldest first / most recently saved last."""
    return DB.versions(WS)


def default_index(vs):
    """Open the version of the last solve / last saved edit by default."""
    cur = st.session_state.get("current_version")
    return vs.index(cur) if cur in vs else len(vs) - 1


@st.cache_data(show_spinner=False)
def _n_classes(ws, v, stamp):
    try:
        c = DB.load(ws, v)["Class"].astype(str)
        return int(c[~c.str.startswith("REM:")].nunique())
    except Exception:
        return 0


def version_label(v):
    return f"{v}  ({t('n_classes', n=_n_classes(WS, v, DB.stamp(WS, v)))})"


def grid_for(df, key_col, key, label_col):
    g = df[df[key_col] == key].pivot_table(index="Slot", columns="Day", values=label_col,
                                         aggfunc=lambda x: " | ".join(x))
    g = g.reindex(index=range(7), columns=range(5)).fillna("---")
    g.columns = [i18n.day(c) for c in g.columns]
    g.index = [i18n.slot_label(i) for i in range(7)]
    if i18n.is_ar():
        g = g[g.columns[::-1]]           # Sunday on the right, like a printed Arabic timetable
    return g


def nat(p):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", str(p))]


# ------------------------------------------------------------------ main
# ---- subject mapping assistant
if PAGE == "data" and "subjects" in data_frames:
    _cur = sorted(data_frames["subjects"]["Subject_Code"].astype(str).str.upper().unique())
    _unknown = sm.collect_unknown(data_frames, plan)
    if _unknown or subj_map:
        with st.expander(t("map_title", n=len(_unknown)), expanded=bool(_unknown)):
            if _unknown:
                st.caption(t("map_caption"))
                tbl = sm.suggestion_table(_unknown, _cur)
                tbl["Source"] = tbl["Source"].map(lambda x: t("ds_" + x) if x != "grid" else t("map_grid"))
                tbl["Kind"] = tbl["Kind"].map(lambda k: t("map_k_" + k))
                ed = st.data_editor(
                    tbl, hide_index=True, width="stretch", key="map_editor",
                    disabled=["Source", "Code", "Kind", "Reason"],
                    column_config={
                        "Source": st.column_config.TextColumn(t("map_c_src")),
                        "Code": st.column_config.TextColumn(t("map_c_code")),
                        "Target": st.column_config.SelectboxColumn(t("map_c_target"), options=[""] + _cur,
                                                                   help=t("map_target_help")),
                        "Kind": st.column_config.TextColumn(t("map_c_kind")),
                        "Reason": st.column_config.TextColumn(t("map_c_reason"))})
                if st.button(t("map_apply"), type="primary"):
                    new = dict(subj_map)
                    new.update({r["Code"]: r["Target"] for _, r in ed.iterrows()})
                    st.session_state["subj_map"] = new
                    st.session_state["plan_src"] = None
                    st.session_state.pop("last", None)
                    st.rerun()
            if subj_map:
                st.markdown(t("map_active") + " " + " · ".join(
                    f"`{k}` → `{v}`" if v else f"`{k}` → ✖" for k, v in sorted(subj_map.items())))
                if st.button(t("map_reset")):
                    st.session_state["subj_map"] = {}
                    st.session_state["plan_src"] = None
                    st.rerun()


def render_split_rules(dfs, key):
    """How the solver understands the split rules + download in the explicit v2 format."""
    if dfs.get("rules") is None or dfs.get("subjects") is None:
        return
    st.caption(t("sr_caption"))
    try:
        ex = srv.explain(dfs)
    except Exception as e_:
        st.warning(f"{type(e_).__name__}: {e_}")
        return
    st.dataframe(ex, hide_index=True, width="stretch")
    if "Frequency" not in dfs["rules"].columns:
        st.info(t("sr_old_format"))
    st.download_button(t("sr_download"), dl.to_local(srv.to_v2(dfs["rules"])).to_csv(index=False).encode("utf-8-sig"),
                       f"{dl._lbl(dl.FILE_NAMES['rules'], i18n.LANG)}.csv", "text/csv", key=f"srdl_{key}")
    with st.popover(t("sr_help_btn")):
        st.markdown(t("sr_help"))

st.markdown(f'<div class="small-screen">{t("small_screen")}</div>', unsafe_allow_html=True)
if WZ_PENDING and PAGE in ("plan", "run"):
    st.info(t("wz_pending"))
    if st.button(t("go_data"), type="primary"):
        goto("data")
    st.stop()


@st.dialog(" ")
def solved_dialog(info):
    st.markdown(f"### ✅ {t('dlg_solved_title')}")
    st.write(t("saved_as", n=info["name"]))
    m1, m2, m3 = st.columns(3)
    m1.metric(t("lessons_gen"), info["lessons"])
    m2.metric(t("objective"), f"{info['obj']:,.0f}" if info["obj"] is not None else "—")
    m3.metric(t("times"), f"{info['ts']:.0f}s")
    st.caption(t("dlg_solved_hint"))
    b1, b2, b3 = st.columns(3)
    if b1.button(t("dlg_view"), type="primary", width="stretch"):
        st.rerun()
    if b2.button(t("dlg_edit"), width="stretch"):
        ss["tt_mode"] = "quick"
        goto("tt")
    if b3.button(t("dlg_details"), width="stretch"):
        goto("run")


if PAGE == "guide":
    guide.render(st)

# ------------------------------------------------------------------ input data
if PAGE == "data":
    if data_frames.get("rules") is not None:
        st.subheader(t("sr_title"))
        render_split_rules(data_frames, "data")
    st.caption(t("raw_note"))
    for k, df in data_frames.items():
        if df is None:
            continue
        with st.expander(t("rows", k=t("ds_" + k), n=len(df))):
            st.dataframe(dl.to_local(df) if k != "grid" else df, width="stretch", hide_index=True)

def make_cfg():
    """Solver settings from the sidebar (same for a full solve and for a repair)."""
    cfg = SchedulerConfig()
    cfg.allow_student_gaps = allow_gaps
    cfg.allow_same_subject_twice_per_day = allow_twice
    cfg.enforce_max_2h_courses_per_day = enforce_2h
    cfg.max_2h_courses_per_day = int(max_2h)
    cfg.morning_first_hard = morning_hard
    cfg.strict_class_grid = strict_grid
    cfg.teacher_windows_hard = windows_hard
    cfg.room_fallback = {"lab": "classroom"} if lab_fallback else {}
    cfg.teacher_priority_strength = prio
    cfg.remedial_groups = [g for g in rem_groups if len(g) > 1]
    for k, v in weights.items():
        setattr(cfg, k, int(v))
    cfg.max_time_seconds = max_time
    cfg.num_workers = workers
    presolve.config_patch(st, cfg, plan, use_remedial)
    return cfg


def adapt_panel(editor, ed_state, v, sel, sel_key, conf):
    """📌 pins + "Adapt the timetable": the solver re-arranges the rest, changing as few lessons as possible."""
    desc = lambda lid: f"{i18n.subj(editor.L[lid]['subject'])} · {i18n.cls(editor.L[lid]['class'])} · " \
                       f"{i18n.teachers(editor.L[lid]['teachers'])}" if lid in editor.L else lid
    with st.container(border=True):
        c = st.columns([2, 2, 2, 3])
        c[0].metric(t("pins_n"), len(editor.pins))
        c[1].metric(t("conflicts_n"), len(conf))
        if c[2].button(t("pin_toggle"), disabled=sel is None, width="stretch", help=t("pin_toggle_help")):
            before = editor.export_state(); editor.toggle_pin(sel)
            ed_state["undo"].append(before); ed_state["cur"] = editor.export_state(); st.rerun()
        if c[2].button(t("pins_clear"), disabled=not editor.pins, width="stretch"):
            before = editor.export_state(); editor.pins.clear()
            ed_state["undo"].append(before); ed_state["cur"] = editor.export_state(); st.rerun()
        with c[3]:
            secs = st.slider(t("adapt_time"), 10, 300, 60, step=10, key="adapt_secs")
            b1, b2 = st.columns(2)
            go = b1.button(t("adapt_btn"), type="primary", disabled=not editor.pins, width="stretch",
                           help=t("adapt_help"))
            regen = b2.button(t("regen_pins"), disabled=not editor.pins, width="stretch", help=t("regen_pins_help"))
        if conf:
            with st.expander(t("conflicts_list", n=len(conf))):
                for lid, why in list(conf.items())[:40]:
                    st.markdown(f"- {'📌 ' if lid in editor.pins else ''}{desc(lid)} — {why}")
        if (go or regen) and data_ready:
            import threading
            box = {"res": None, "err": None, "lvl": (0, 0)}
            state_now, pins_now = editor.export_state(), sorted(editor.pins)
            cfg_ = make_cfg()
            def _work():
                try:
                    box["res"] = repair(SchoolDataLoader(data_frames), cfg_, state_now, pins_now,
                                        fixed_assignment=plan["assignment"] if plan is not None else None,
                                        time_limit=secs, keep_changes=not regen,
                                        progress=lambda i_, n_: box.update(lvl=(i_, n_)))
                except Exception as ex_:
                    box["err"] = ex_
            t0 = time.time(); th = threading.Thread(target=_work, daemon=True); th.start()
            bar, txt = st.progress(0.0), st.empty()
            while th.is_alive():
                el = time.time() - t0
                bar.progress(min(1.0, el / (secs + 10)))
                lv = box["lvl"]
                txt.info(t("adapt_running", m=int(max(0, secs + 10 - el)) // 60, s=f"{int(max(0, secs + 10 - el)) % 60:02d}",
                           l=lv[0] or "…", n=lv[1] or "…"))
                th.join(timeout=1.0)
            bar.empty(); txt.empty()
            if isinstance(box["err"], RepairMismatch):
                st.error(t("adapt_mismatch"))
            elif box["err"] is not None:
                st.error(f"❌ {type(box['err']).__name__}: {box['err']}")
            else:
                ed_state["proposal"] = dict(box["res"], base=state_now, regen=regen)
                ed_state["proposal"].pop("engine", None)
                st.rerun()
        pr = ed_state.get("proposal")
        if not pr:
            return
        if pr["state"] is None:
            if pr["status"] == "OUTSIDE":
                st.error(t("adapt_outside") + "\n\n" + "\n".join(f"- 📌 {desc(i)}" for i in pr["outside"]))
            elif pr["clash"]:
                st.error(t("adapt_clash") + "\n\n" + "\n".join(f"- 📌 {desc(i)}" for i in pr["clash"]))
            else:
                st.warning(t("adapt_none", s=pr["status"]))
                if pr.get("failed"):
                    st.caption(t("adapt_failed_at") + " " + " · ".join(f"📌 {desc(i)}" for i in pr["failed"]))
            if st.button(t("adapt_close")):
                ed_state.pop("proposal", None); st.rerun()
            return
        if pr.get("kind") == "improve":
            st.success(t("imp_ok", m=len(pr["moved"]), s=pr.get("seconds", "?")))
            ik = pd.DataFrame({t("before_col"): pr["before"], t("after_col"): pr["after"]})
            ik["Δ"] = ik[t("after_col")] - ik[t("before_col")]
            ik.index = [("🎯 " if k in pr["goals"] else "") + t("kpi_" + k) for k in ik.index]
            st.dataframe(ik, width="stretch")
        else:
            st.success(t("adapt_ok", p=len(pr["state"].get("pins", [])), m=len(pr["moved"]), l=pr["level"],
                     s=pr.get("seconds", "?")) if not pr["regen"] else
                   t("regen_ok", p=len(pr["state"].get("pins", [])), m=len(pr["moved"]), s=pr.get("seconds", "?")))
        if not pr["regen"] and pr.get("kind") != "improve" and len(pr["moved"]) > 10 * max(1, len(pr["state"].get("pins", []))):
            st.info(t("adapt_many"))
        old = {l["id"]: l for l in pr["base"]["lessons"]}
        new = {l["id"]: l for l in pr["state"]["lessons"]}
        where = lambda l: f"{i18n.day(l['day'])} {l['start'] + 1}"
        rows = [{t("mv_lesson"): desc(i), t("mv_from"): where(old[i]), t("mv_to"): where(new[i])}
                for i in pr["moved"] if i in old and i in new]
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown(t("mv_title"))
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=min(400, 38 + 35 * len(rows)))
        with c2:
            k0 = kpi_frame(calculate_all_kpis(ScheduleEditor(pr["base"]).to_schedule_df()))
            k1 = kpi_frame(calculate_all_kpis(pr["sched"]))
            kt = pd.DataFrame({t("before_col"): k0, t("after_col"): k1}); kt["Δ"] = kt[t("after_col")] - kt[t("before_col")]
            st.dataframe(kt, width="stretch")
        a1, a2 = st.columns(2)
        if a1.button(t("adapt_accept"), type="primary", width="stretch"):
            name = time.strftime("Version_%Y%m%d_%H%M%S")
            manager.save(pr["sched"], name, state=pr["state"])
            ed_state.pop("proposal", None)
            st.session_state["current_version"] = name
            st.session_state.pop("ed", None); st.session_state.pop(sel_key, None)
            st.toast(t("saved_new", n=name), icon="✅"); st.rerun()
        if a2.button(t("adapt_cancel"), width="stretch"):
            ed_state.pop("proposal", None); st.rerun()


def version_cfg(state):
    """The rules the version was solved with (saved in it); old versions fall back to the sidebar settings."""
    if state and state.get("solver_cfg"):
        c = cfg_from_dict(state["solver_cfg"]); c.num_workers = workers
        return c
    return make_cfg()


def improve_panel(editor, ed_state, v):
    """✨ Auto-improve a finished timetable: chosen KPI goals, optional relaxations, all other KPIs never worse."""
    with st.expander(t("imp_title")):
        st.caption(t("imp_help"))
        lab = lambda k: t("kpi_" + k)
        goals = st.multiselect(t("imp_goals"), IMPROVE_KPIS, default=["t_single", "t_gap1"], format_func=lab,
                               key="imp_goals")
        main = st.selectbox(t("imp_main"), goals, format_func=lab, key="imp_main") if goals else None
        st.markdown(t("imp_relax"))
        relax = {}
        rc = st.columns(len(IMPROVE_LINKS))
        for i, k in enumerate(IMPROVE_LINKS):
            if k in goals:
                continue
            n = rc[i].number_input(lab(k), 0, 50, 0, key=f"imp_rx_{k}", help=t("imp_relax_help"))
            if n:
                relax[k] = int(n)
        off = set()
        for k in relax:
            off |= set(IMPROVE_LINKS.get(k, []))
        guards = [k for k in IMPROVE_KPIS if k not in goals and k not in relax and k not in off]
        st.caption(t("imp_guards") + " " + " · ".join("🛡️ " + lab(k) for k in guards)
                   + ("  \n" + t("imp_off") + " " + " · ".join("⛔ " + lab(k) for k in sorted(off - set(goals))) if off else ""))
        c1, c2, c3 = st.columns([2, 2, 1])
        mode = c1.radio(t("imp_mode"), ["few", "free"], format_func=lambda m: t("imp_mode_" + m), key="imp_mode",
                        horizontal=True)
        secs = c2.slider(t("adapt_time"), 30, 600, 120, step=30, key="imp_secs")
        cap = c1.number_input(t("imp_cap"), 5, 300, 40, step=5, key="imp_cap") if mode == "few" else None
        go = c3.button(t("imp_btn"), type="primary", disabled=not goals or not data_ready, width="stretch")
        if not go:
            return
        import threading
        box = {"res": None, "err": None}
        state_now, cfg_ = editor.export_state(), version_cfg(editor.export_state())
        def _work():
            try:
                box["res"] = improve(SchoolDataLoader(data_frames), cfg_, state_now, sorted(editor.pins), goals,
                                     relax=relax, guards=guards, main=main,
                                     change_weight=3000 if mode == "few" else 0, max_moves=cap, time_limit=secs,
                                     fixed_assignment=plan["assignment"] if plan is not None else None)
            except Exception as ex_:
                box["err"] = ex_
        t0 = time.time(); th = threading.Thread(target=_work, daemon=True); th.start()
        bar, txt = st.progress(0.0), st.empty()
        while th.is_alive():
            el = time.time() - t0; rem = int(max(0, 2 * secs + 20 - el))
            bar.progress(min(1.0, el / (2 * secs + 20)))
            txt.info(t("imp_running", m=rem // 60, s=f"{rem % 60:02d}"))
            th.join(timeout=1.0)
        bar.empty(); txt.empty()
        if isinstance(box["err"], RepairMismatch):
            st.error(t("adapt_mismatch")); return
        if box["err"] is not None:
            st.error(f"❌ {type(box['err']).__name__}: {box['err']}"); return
        r = box["res"]
        if r["state"] is None:
            st.warning(t("imp_none", s=r["status"])); return
        ed_state["proposal"] = dict(r, base=state_now, regen=False, kind="improve", level="—", clash=[],
                                    goals=goals)
        st.rerun()


# ------------------------------------------------------------------ step 2: run
if RUN:
    if data_ready:
        with run_pre:
            presolve.render(st, plan, data_frames, use_remedial)
    if run:
        cfg = make_cfg()
        try:
            with st.spinner(t("building")):
                t0 = time.time()
                eng = SchoolSchedulerEngine(SchoolDataLoader(data_frames), cfg,
                                            fixed_assignment=plan["assignment"] if plan is not None else None)
                if plan is not None and use_remedial:
                    eng.remedial = dict(plan.get("remedial") or {})
                eng.build_model()
                t_build = time.time() - t0
            # solve in a background thread; the page shows a live countdown meanwhile
            import threading
            box = {"phase": 1, "sched": None, "err": None}
            def _work():
                try:
                    box["sched"] = eng.solve(progress=lambda p: box.update(phase=2))
                except Exception as ex_:
                    box["err"] = ex_
            t0 = time.time()
            th = threading.Thread(target=_work, daemon=True); th.start()
            ph_bar, ph_txt = st.progress(0.0), st.empty()
            ncpu = os.cpu_count() or 1
            while th.is_alive():
                el = time.time() - t0
                rem = max(0, int(max_time - el))
                ph_bar.progress(min(1.0, el / max_time))
                ph_txt.info(t("countdown", m=rem // 60, s=f"{rem % 60:02d}",
                              p=t("phase1_name") if box["phase"] == 1 else t("phase2_name"),
                              c=ncpu) + ("  \n" + t("cpu_hint", n=ncpu) if ncpu < 4 else ""))
                th.join(timeout=1.0)
            ph_bar.empty(); ph_txt.empty()
            if box["err"] is not None:
                raise box["err"]
            sched = box["sched"]
            t_solve = time.time() - t0
        except Exception as ex:
            st.error(f"❌ {type(ex).__name__}: {ex}")
            st.stop()
        st.session_state["last"] = dict(engine=eng, sched=sched, tb=t_build, ts=t_solve, name=version_name,
                                        remedial=plan["remedial"] if plan is not None else {},
                                        plan_assign=plan["assignment"] if plan is not None else None)
        if sched is not None:
            manager.save(sched, version_name, eng.objective_score,
                         state=reception.ensure(export_editable_state(eng)))
            st.session_state["current_version"] = version_name
            ss["_solved"] = dict(name=version_name, lessons=len(eng.lessons), obj=eng.objective_score, ts=t_solve)
            ss["_reset_vn"] = True
            goto("tt")

    last = st.session_state.get("last")
    if not data_ready:
        st.info(t("need_files"))
    elif not last:
        st.info(t("data_loaded"))
    else:
        eng, sched = last["engine"], last["sched"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("status"), t("feasible") if sched is not None else t("infeasible"))
        c2.metric(t("objective"), f"{eng.objective_score:,.0f}" if eng.objective_score is not None else "—")
        c3.metric(t("lessons_gen"), len(eng.lessons))
        c4.metric(t("times"), f"{last['tb']:.1f}s / {last['ts']:.1f}s")
        pi = getattr(eng, "phase_info", {})
        if pi.get("phase1"):
            st.caption(t("phase_caption", s1=pi["phase1"][0], t1=pi["phase1"][1],
                         s2=pi.get("phase2", ("—", 0))[0], t2=pi.get("phase2", ("—", 0))[1]))
        if sched is None:
            st.warning(t("no_solution"))
            if getattr(eng, "status_name", "") == "INFEASIBLE":
                st.error(t("proven_infeasible"))
            with st.expander(t("rm_check_title"), expanded=True):
                rms.render_check(st, rms.capacity_check(eng.lessons, eng.room_caps(),
                                                        fallback=getattr(eng.config, "room_fallback", {}) or {}))
            insp = eng.data.df_inspections
            known = set(eng.data.df_subjects["Subject_Code"])
            if len(insp) and st.button(t("diag_btn")):
                rows = []
                prog = st.progress(0.0)
                for i in range(len(insp)):
                    r = insp.iloc[i]
                    if r["Subject_Code"] not in known:
                        res = t("diag_ignored")
                    else:
                        dfs = dict(data_frames); dfs["inspections"] = insp.iloc[[i]]
                        c0 = SchedulerConfig(); c0.max_time_seconds = 20; c0.num_workers = workers
                        e0 = SchoolSchedulerEngine(SchoolDataLoader(dfs), c0, fixed_assignment=last.get("plan_assign"))
                        e0.build_model(); e0.solve()
                        res = {"INFEASIBLE": t("diag_bad"), "FEASIBLE": t("diag_ok"),
                               "OPTIMAL": t("diag_ok")}.get(e0.status_name, t("diag_unknown"))
                    rows.append({t("c_subject"): i18n.subj(r["Subject_Code"]), t("diag_day"): i18n.day(int(r["Day_Index"])),
                                 "Slots": str(r["Blocked_Slots"]), t("diag_result"): res})
                    prog.progress((i + 1) / len(insp))
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
                st.caption(t("diag_caption"))
        else:
            st.success(t("saved_as", n=last["name"]))
            st.subheader(t("kpis"))
            st.dataframe(pd.DataFrame(kpi_frame(calculate_all_kpis(sched)).items(), columns=[t("kpi"), t("value")]),
                         hide_index=True, width="stretch")
            gr = grid_report(sched, eng)
            if len(gr):
                n_ok = int(gr["OK"].sum())
                (st.success if n_ok == len(gr) else st.warning)(t("grid_ok", n=n_ok, m=len(gr)))
                if n_ok < len(gr):
                    bad = gr[~gr["OK"]].copy(); bad["Class"] = bad["Class"].map(i18n.cls)
                    st.dataframe(bad.drop(columns=["OK"]).rename(columns={c: t("gr_" + c) for c in bad.columns}),
                                 hide_index=True, width="stretch")
            rr = pd.DataFrame(getattr(eng, "remedial_report", []) or [])
            if len(rr):
                ok_ = rr[rr["Status"] == "ok"]
                n6 = int((ok_["Slot"] == eng.config.slots - 2).sum()); n7 = int((ok_["Slot"] == eng.config.slots - 1).sum())
                none_ = rr[rr["Status"] == "none"]
                (st.success if none_.empty else st.warning)(t("rem_summary", n=len(ok_), a=n6, b=n7, x=len(none_)))
                with st.expander(t("rem_table")):
                    show = ok_.assign(Day=ok_["Day"].map(lambda d_: i18n.day(int(d_))),
                                      Slot=ok_["Slot"].map(lambda s_: i18n.slot_label(int(s_))),
                                      Classes=ok_["Classes"].map(lambda z: " ".join(i18n.cls(c.strip()) for c in z.split(","))))
                    st.dataframe(show[["Teachers", "Day", "Slot", "Classes"]].rename(columns={
                        "Teachers": t("tot_teacher"), "Day": t("day"), "Slot": t("slot"), "Classes": t("tot_class")}),
                        hide_index=True, width="stretch")
                    for r_ in rr[rr["Status"] == "split"].itertuples():
                        st.caption(t("rem_split", t=r_.Teachers))
                    for r_ in none_.itertuples():
                        st.caption(t("rem_none", t=r_.Teachers))
            fr = teacher_fairness(sched, eng)
            if len(fr):
                with st.expander(t("fair_table")):
                    st.caption(t("fair_caption"))
                    fr["Factor"] = fr["Teacher"].map(lambda x: round(getattr(eng, "teacher_factor", {}).get(x, 1.0), 2))
                    fr = fr.rename(columns={c: t("fr_" + c) for c in fr.columns})
                    st.dataframe(fr, hide_index=True, width="stretch")
        st.subheader(t("teacher_assignment"))
        if eng.assignment is not None:
            levels = dict(zip(eng.data.df_classes["Class_ID"], eng.data.df_classes["Level"]))
            a = last["plan_assign"] if last.get("plan_assign") is not None else eng.assignment.copy()
            xl = build_matrix_xlsx(a, eng._calculate_required_hours, levels, remedial=last.get("remedial"))
            st.download_button(t("dl_school"), xl, f"{last['name']}_assignment.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            pv = eng.assignment.pivot_table(index="Class", columns="Subject", values="Teacher", aggfunc="first").fillna("")
            pv.index = [i18n.cls(c) for c in pv.index]
            pv.columns = [i18n.subj(c) for c in pv.columns]
            st.dataframe(pv, width="stretch")
        with st.expander(t("gen_lessons")):
            st.dataframe(pd.DataFrame([{**l, "subject": i18n.subj(l["subject"]), "class": i18n.cls(l["class"]),
                                        "teachers": i18n.teachers(l["teachers"]), "rooms": str(l["rooms"])}
                                       for l in eng.lessons]), width="stretch")
        if sched is not None:
            with st.expander(t("raw_schedule")):
                st.dataframe(sched, width="stretch")
                st.download_button(t("dl_csv"), sched.to_csv(index=False), f"{last['name']}.csv")

# ------------------------------------------------------------------ timetables
def styled_grid(sub, key_col, key, label_col):
    """Timetable grid coloured by subject (light tint per subject)."""
    g = grid_for(sub, key_col, key, label_col)
    x = sub[sub[key_col] == key].copy()
    x["Day"] = x["Day"].map(i18n.day)
    x["Slot"] = x["Slot"].map(i18n.slot_label)
    colmap = {(r.Slot, r.Day): f"background-color: {colors.light(r.Subject)}; color: #1b1b1b; "
                               f"border-left: 4px solid {colors.strong(r.Subject)}"
              for r in x.itertuples()}
    css = pd.DataFrame([[colmap.get((i, c), "color: #bbb") for c in g.columns] for i in g.index],
                       index=g.index, columns=g.columns)
    return g.style.apply(lambda _: css, axis=None)


def load_state_info(v):
    try:
        stt = load_state(v) or {}
        return stt.get("teacher_windows_info") or stt.get("teacher_windows", {}), stt.get("priority_strength", 3.0)
    except Exception:
        return {}, 3.0


def _chip(txt, bg="#f0f2f6", fg="#262730"):
    return (f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 9px;border-radius:10px;'
            f'background:{bg};color:{fg};font-size:13px;white-space:nowrap">{txt}</span>')


def prio_rate(r):
    """Priority shown as a rate: current / max (max = the fairness strength k used by the solver)."""
    mx = r.get("Priority_max", None) if hasattr(r, "get") else None
    return f"{float(r['Priority']):g}/{float(mx):g}" if mx is not None and mx == mx else f"{float(r['Priority']):g}"


def teacher_chips(r):
    """Main KPIs of one teacher as coloured chips (green = good, orange = to watch)."""
    ok, warn = ("#e3f5e1", "#1e6b2a"), ("#fff1d6", "#8a5a00")
    c = [_chip(t("k_prio", v=prio_rate(r)), "#e8e0ff", "#4b2c9a"),
         _chip(t("k_hours", v=r["Hours"]) + (f" ({t('k_rem', v=r['Remedial'])})" if r["Remedial"] else ""), "#dbe8ff", "#1f4e99"),
         _chip(t("k_days", v=r["Days"])),
         _chip(t("k_gaps", v=r["Gaps"]), *(ok if r["Gaps"] == 0 else warn)),
         _chip(t("k_single", v=r["Single_hour"]), *(ok if r["Single_hour"] == 0 else warn)),
         _chip(t("k_aft", v=r["Afternoon_h"])),
         _chip(t("k_slot7", v=r["Slot7"])),
         _chip(t("k_finish", v=r["Avg_finish"])),
         _chip(t("k_win", v=r["In_window"]), *(ok if r["In_window"] == 0 else warn))]
    subj_ = "".join(_chip(i18n.subj(x_), colors.light(x_)) for x_ in r["Subjects"])
    cls_ = " ".join(i18n.cls(x_.strip()) for x_ in str(r["Classes"]).split(",") if x_.strip())
    return (f'<div style="margin:-6px 0 4px 0">{"".join(c)}</div>'
            f'<div style="margin:0 0 6px 0">{subj_} <span style="font-size:13px;color:#555">🎒 {cls_}</span></div>')


def class_chips(r):
    ok, warn = ("#e3f5e1", "#1e6b2a"), ("#fff1d6", "#8a5a00")
    c = [_chip(t("k_hours", v=r["Hours"]) + (f" + {t('k_rem', v=r['Remedial'])}" if r["Remedial"] else ""), "#dbe8ff", "#1f4e99"),
         _chip(t("k_sgaps", v=r["Gaps"]), *(ok if r["Gaps"] == 0 else warn)),
         _chip(t("k_empty_m", v=r["Empty_morning"]), *(ok if r["Empty_morning"] == 0 else warn)),
         _chip(t("k_aft", v=r["Afternoon_h"])),
         _chip(t("k_slot7", v=r["Slot7"]))]
    return f'<div style="margin:-6px 0 6px 0">{"".join(c)}</div>'


EXPORT_DIR = os.path.join(HERE, "static", "exports")


def publish_file(data, ext="pdf"):
    """Put a generated file under ./static (served by Streamlit at app/static/...) so it opens in a NEW TAB
    instead of printing/downloading. Content-addressed name; only the 40 newest files are kept."""
    import hashlib
    os.makedirs(EXPORT_DIR, exist_ok=True)
    fn = f"{hashlib.sha1(data).hexdigest()[:20]}.{ext}"
    p_ = os.path.join(EXPORT_DIR, fn)
    if not os.path.exists(p_):
        with open(p_, "wb") as f_:
            f_.write(data)
        old = sorted((os.path.join(EXPORT_DIR, x) for x in os.listdir(EXPORT_DIR)), key=os.path.getmtime)[:-40]
        for x in old:
            try:
                os.remove(x)
            except OSError:
                pass
    return f"./app/static/exports/{fn}"


@st.cache_data(show_spinner=False, max_entries=32)
def entity_pdf(csv_bytes, title, kind, who, lang_, rec_json):
    i18n.set_lang(lang_)
    df_ = pd.read_csv(io.BytesIO(csv_bytes), dtype=str).fillna("")
    df_["Day"], df_["Slot"] = df_["Day"].astype(int), df_["Slot"].astype(int)
    return export.to_pdf(df_, title, sections=(kind,), only=(kind, who), reception=json.loads(rec_json) or None)


@st.cache_data(show_spinner=False, max_entries=16)
def export_file(kind, key):
    ws_, v_, _, lang_, secs_, only_ = key
    i18n.set_lang(lang_)
    df_ = DB.load(ws_, v_)
    rv = occ_ = None
    if "rooms" in secs_ or "full_teacher" in secs_:
        caps_ = rooms_caps(v_)
        occ_ = rms.allocate(df_, data_frames.get("subjects"), caps_)
        if "rooms" in secs_:
            rv = export.room_view(occ_, caps_)
    _sv = load_state(v_) or None
    recv = (_sv.get("reception") if "reception" in _sv else ScheduleEditor(_sv).rec) if _sv else None
    return (export.to_xlsx if kind == "xlsx" else export.to_pdf)(df_, f"{ws_} — {v_}", sections=secs_, rooms=rv,
                                                                 reception=recv, occ=occ_, only=only_)


def rooms_caps(v_):
    st_ = load_state(v_) or {}
    if st_.get("rooms"):
        return st_["rooms"]
    if data_frames.get("rooms") is not None:
        return dict(zip(data_frames["rooms"]["Room_Type"], data_frames["rooms"]["Capacity"].astype(int)))
    return {"classroom": 20}


REC_BG = "repeating-linear-gradient(45deg,#8d6e63,#8d6e63 6px,#795548 6px,#795548 12px)"


# ------------------------------------------------------------------ edit helpers: preview popup, apply, affected strip
def _pos(ed_):
    return {i: (l["day"], l["start"]) for i, l in ed_.L.items()}


def _where(d_, s_):
    return f"{i18n.day(d_)} {i18n.slot_label(s_)}"


def entity_table_html(ed_, kind, key, pv, lid):
    """Static timetable of ONE class/teacher in its CURRENT state; lessons the pending change would touch are outlined."""
    import html as _h
    esc = lambda x: _h.escape(str(x))
    mine = [l for l in ed_.L.values() if ((l["class"] == key or key in l.get("blocks_classes", []))
                                          if kind == "class" else key in l["teachers"])]
    cell, incoming = {}, {}
    for l in mine:
        for k in range(l["duration"]):
            cell.setdefault((l["day"], l["start"] + k), []).append(l)
        if l["id"] in pv["moves"]:
            dd, s0 = pv["moves"][l["id"]]
            for k in range(l["duration"]):
                incoming.setdefault((dd, s0 + k), []).append(l)
    for i, (dd, s0) in pv["moves"].items():                 # the dragged lesson arriving in THIS table (other entity)
        l = ed_.L[i]
        if l in mine:
            continue
        if (kind == "class" and (l["class"] == key or key in l.get("blocks_classes", []))) or \
           (kind == "teacher" and key in l["teachers"]):
            for k in range(l["duration"]):
                incoming.setdefault((dd, s0 + k), []).append(l)
    D, S, lb = ed_.cfg["days"], ed_.cfg["slots"], ed_.cfg["lunch_boundary"]
    rtl = i18n.is_ar()
    th = "".join(f"<th>{esc(i18n.day(d_))}</th>" for d_ in range(D))
    rows = []
    for s_ in range(S):
        tds = []
        for d_ in range(D):
            ls = cell.get((d_, s_), [])
            parts, style = [], ""
            for l in ls:
                title = (i18n.subj_short(l["subject"]) if kind == "class" else
                         (i18n.subj_short("REMEDIAL") if l.get("remedial") else i18n.cls(l["class"])))
                sub = i18n.teachers(l["teachers"]) if kind == "class" else i18n.subj_short(l["subject"])
                tag = ""
                if l["id"] in pv["clash"]:
                    tag = f"<div class='pv-tag pv-r'>⚠ {esc(t('pv_clash'))}</div>"
                    style = "outline:3px solid #d64545;outline-offset:-3px;"
                elif l["id"] in pv["moves"]:
                    dd, s0 = pv["moves"][l["id"]]
                    tag = f"<div class='pv-tag pv-y'>↦ {esc(t('pv_moves_to', w=_where(dd, s0 + (s_ - l['start']))))}</div>"
                    style = "outline:3px dashed #c58b00;outline-offset:-3px;"
                parts.append(f"<b>{esc(title)}</b><br><small>{esc(sub)}</small>{tag}")
            bg = colors.light(ls[0]["subject"]) if ls else ("#eef1f5" if (d_ == 2 and s_ > lb) else "#fff")
            inc = [l for l in incoming.get((d_, s_), []) if l not in ls or pv["moves"].get(l["id"]) != (l["day"], l["start"])]
            if inc:
                l = inc[0]
                nm = i18n.subj_short(l["subject"]) if kind == "class" else i18n.cls(l["class"])
                parts.append(f"<div class='pv-tag pv-g'>⬅ {esc(nm)} · {esc(t('pv_incoming'))}</div>")
                if not style:
                    style = "outline:3px solid #1e9e57;outline-offset:-3px;"
            tds.append(f"<td style='background:{bg};{style}'>{''.join(parts)}</td>")
        sep = " class='pv-lunch'" if s_ == lb + 1 else ""
        rows.append(f"<tr{sep}><th>{esc(i18n.slot_label(s_))}</th>{''.join(tds)}</tr>")
    head = ("🎒 " + i18n.cls(key)) if kind == "class" else ("👨‍🏫 " + key)
    return (f"<div class='pv-box' dir='{'rtl' if rtl else 'ltr'}'><div class='pv-h'>{esc(head)}</div>"
            f"<table class='pv'><tr><th></th>{th}</tr>{''.join(rows)}</table></div>")


PV_CSS = """<style>
.pv-box{margin:6px 0 14px}.pv-h{font-weight:700;margin-bottom:4px}
table.pv{border-collapse:separate;border-spacing:3px;width:100%;table-layout:fixed;font-size:12px}
table.pv th{background:#f0f4f9;border-radius:6px;padding:3px;font-weight:600;font-size:11.5px}
table.pv td{border:1px solid #e1e8f0;border-radius:7px;padding:3px 5px;vertical-align:top;height:44px;line-height:1.25}
table.pv tr.pv-lunch td, table.pv tr.pv-lunch th{border-top:3px dashed #c9d6e3}
.pv-tag{font-size:10.5px;font-weight:700;margin-top:2px}.pv-y{color:#9a6a00}.pv-g{color:#137a42}.pv-r{color:#c03030}
.pv-leg span{display:inline-block;margin-inline-end:14px;font-size:12px}
</style>"""


def single_payload(editor, view, who, free=False, readonly=False, tw=None):
    """Payload of the one-class / one-teacher drag & drop board (also used read-only in View mode)."""
    mine = [l for l in editor.L.values() if ((l["class"] == who or who in l.get("blocks_classes", []))
                                             if view == "class" else who in l["teachers"])]
    lessons_payload = []
    for l in mine:
        sname = i18n.subj(l["subject"])
        lessons_payload.append({
            "id": l["id"], "day": l["day"], "start": l["start"], "duration": l["duration"],
            "locked": False if free else editor.locked(l),
            "title": sname if view == "class" else f"{i18n.cls(l['class'])} · {sname}",
            "sub": i18n.teachers(l["teachers"]) if view == "class"
                   else i18n.teachers([x for x in l["teachers"] if x != who]) or "&nbsp;",
            "colorKey": l["subject"].split("_")[0],
            "bg": colors.css_background(l["subject"]),
            "tooltip": t("tooltip", s=sname, c=i18n.cls(l["class"]), t=i18n.teachers(l["teachers"]),
                         d=l["duration"], r=l["rooms"]),
        })
    _st_map = {} if readonly else editor.status_map([l["id"] for l in mine], free=free)
    if view == "teacher" and who in editor.rec:
        _rd, _rs = editor.rec[who]
        lessons_payload.append({"id": f"REC::{who}", "day": int(_rd), "start": int(_rs), "duration": 1,
                                "locked": False, "title": t("rec_title"), "sub": "&nbsp;", "colorKey": "REC",
                                "bg": REC_BG, "tooltip": t("rec_tip", t=who)})
        if not readonly:
            _st_map[f"REC::{who}"] = editor.rec_status(who)
    _tw = tw or {}
    win_cells = [f"{d_},{s_}" for d_, s_ in _tw.get(who, [])] if view == "teacher" else []
    payload = {
        "windows": win_cells,
        "title": i18n.cls(who) if view == "class" else who, "lessons": lessons_payload,
        "status": _st_map, "free": free,
        "rtl": i18n.is_ar(), "days": i18n.DAYS[i18n.LANG], "slots": [i18n.slot_label(i) for i in range(7)],
        "i18n": {"free": t("dnd_free"), "swap": t("dnd_swap"), "impossible": t("dnd_impossible"),
                 "current": t("dnd_current"), "hint": t("dnd_hint"), "moving": t("dnd_moving"),
                 "not_allowed": t("dnd_not_allowed"), "applying": t("dnd_applying"), "lunch": t("dnd_lunch"),
                 "st_green": t("st_green"), "st_yellow": t("st_yellow"), "st_red": t("st_red"),
                 "st_current": t("st_current"), "tgt_head": t("dnd_tgt_head"), "tgt_none": t("dnd_tgt_none"),
                 "win": t("dnd_win"), "win_msg": t("dnd_win_msg"), "forced": t("dnd_forced"),
                 "st_orange": t("dnd_forced_s")},
    }

    if readonly:
        payload["readonly"] = True
    return payload

def do_move(ed_, ed_state, lid, d_, s_, free):
    """Apply a move (checked or forced), record undo/log and remember which other classes/teachers were touched."""
    pv = ed_.preview(lid, d_, s_, free)
    before_pos, before = _pos(ed_), ed_.export_state()
    ok, msg = (ed_.move_free if free else ed_.apply)(lid, d_, s_)
    if ok:
        ed_state["undo"].append(before)
        ed_state["cur"] = ed_.export_state()
        l = ed_.L[lid]
        ed_state["log"].append(t("log_move", s=i18n.subj(l["subject"]), c=i18n.cls(l["class"]),
                                 d=i18n.day(d_), sl=s_, m=msg))
        after = _pos(ed_)
        moved = {i: (before_pos[i], after[i]) for i in after if after[i] != before_pos[i]}
        ed_state["affected"] = {"entities": pv["entities"], "moved": moved, "lid": lid}
    return ok, msg


def queue_or_move(ed_, ed_state, lid, d_, s_, free, sel_key=None):
    """Swaps (yellow) and forced moves (orange) touch other classes/teachers: ask first (popup), else apply now."""
    pv = ed_.preview(lid, d_, s_, free)
    if pv["status"] in ("yellow", "orange"):
        ed_state["pending"] = {"lid": lid, "d": d_, "s": s_, "free": free, "sel_key": sel_key}
        st.rerun()
    ok, msg = do_move(ed_, ed_state, lid, d_, s_, free)
    if ok:
        if sel_key:
            st.session_state[sel_key] = None
        st.rerun()
    st.error(t("move_rejected", m=msg))


def confirm_popup(ed_, ed_state):
    p = ed_state.get("pending")
    if not p or p["lid"] not in ed_.L:
        ed_state.pop("pending", None)
        return

    def _dismiss():
        st.session_state["ed"].pop("pending", None)

    @st.dialog(t("pv_title"), width="large", on_dismiss=_dismiss)
    def _dlg():
        pv = ed_.preview(p["lid"], p["d"], p["s"], p["free"])
        l = ed_.L[p["lid"]]
        st.markdown(PV_CSS, unsafe_allow_html=True)
        st.markdown(f"**{i18n.subj(l['subject'])} · {i18n.cls(l['class'])} · {i18n.teachers(l['teachers'])}** → "
                    f"**{_where(p['d'], p['s'])}**")
        (st.warning if pv["status"] == "orange" else st.info)(pv["msg"])
        if not pv["entities"]:
            st.caption(t("pv_none"))
        _kind = st.radio(t("pv_show"), ["teacher", "class"], horizontal=True, key="pv_kind",
                         format_func=lambda x: t("pv_show_" + x))
        st.caption(t("pv_state"))
        st.markdown(f"<div class='pv-leg'><span>🟨 {t('pv_leg_move')}</span><span>🟩 {t('pv_leg_in')}</span>"
                    + (f"<span>🟥 {t('pv_leg_clash')}</span>" if pv["clash"] else "") + "</div>", unsafe_allow_html=True)
        for key_ in (pv["teachers"] if _kind == "teacher" else pv["classes"]):
            st.markdown(entity_table_html(ed_, _kind, key_, pv, p["lid"]), unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button(t("pv_confirm"), type="primary", width="stretch", disabled=pv["status"] == "red"):
            ok, msg = do_move(ed_, ed_state, p["lid"], p["d"], p["s"], p["free"])
            ed_state.pop("pending", None)
            if ok and p.get("sel_key"):
                st.session_state[p["sel_key"]] = None
            if not ok:
                ss["_move_err"] = msg
            st.rerun()
        if c2.button(t("pv_cancel"), width="stretch"):
            ed_state.pop("pending", None)
            st.rerun()

    _dlg()


def affected_strip(ed_state):
    a = ed_state.get("affected")
    if not a or not a.get("entities"):
        return
    ed_ = ScheduleEditor(ed_state["cur"])
    info = []
    for i, ((d0, s0), (d1, s1)) in a["moved"].items():
        if i == a["lid"] or i not in ed_.L:
            continue
        l = ed_.L[i]
        info.append(f"{i18n.subj_short(l['subject'])} {i18n.cls(l['class'])}: {_where(d0, s0)} → {_where(d1, s1)}")
    with st.container(border=True):
        st.markdown(f"**{t('aff_title')}** " + (" · ".join(info) if info else ""))
        ents = a["entities"][:6]
        cols = st.columns(len(ents) + 1)
        for j, (k_, key_) in enumerate(ents):
            lab = ("🎒 " + i18n.cls(key_)) if k_ == "class" else ("👨‍🏫 " + key_)
            if cols[j].button(lab, key=f"aff_{j}_{key_}", width="stretch", help=t("aff_open")):
                ss["_ed_goto"] = (k_, key_)
                st.rerun()
        if cols[-1].button(t("aff_clear"), key="aff_hide", width="stretch"):
            ed_state.pop("affected", None)
            st.rerun()


def full_payload(lessons, rows_by, sel=None, status=None, locked_fn=None, readonly=False, pins=(), clash=None,
                 free=False, moved=(), rec=None):
    """Data for the full timetable (rows = all classes or all teachers, columns = every day × slot)."""
    lessons = list(lessons)
    if rows_by == "class":
        keys = sorted({l["class"] for l in lessons if not str(l["class"]).startswith("REM:")}, key=_class_key)
    else:
        keys = sorted({x for l in lessons for x in l["teachers"]}, key=nat)
    hours = {k: 0 for k in keys}
    remh = {k: 0 for k in keys}
    out = []
    for l in lessons:
        rem = bool(l.get("remedial")) or l["subject"] == "REMEDIAL"
        if rows_by == "class":
            rows = list(l.get("blocks_classes", [])) if rem else [l["class"]]
            title = i18n.subj_short(l.get("rem_subject") and "REMEDIAL" or l["subject"])
            sub = i18n.teachers(l["teachers"])
        else:
            rows = list(l["teachers"])
            title = i18n.subj_short("REMEDIAL") if rem else i18n.cls(l["class"])
            sub = t("n_classes", n=len(l.get("blocks_classes", []))) if rem else i18n.subj_short(l["subject"])
        for r in rows:
            if r in hours:
                (remh if rem else hours)[r] += l["duration"]
        out.append({"id": l["id"], "rows": [r for r in rows if r in hours], "day": l["day"], "start": l["start"],
                    "duration": l["duration"], "title": title, "sub": sub, "bg": colors.css_background(l["subject"]),
                    "locked": bool(locked_fn(l)) if locked_fn else False,
                    "pinned": l["id"] in pins, "clash": bool(clash and l["id"] in clash), "moved": l["id"] in moved,
                    "tooltip": ("📌 " if l["id"] in pins else "") + (f"⚠ {clash[l['id']]} · " if clash and l["id"] in clash else "") + f"{i18n.subj(l['subject'])} · {i18n.cls(l['class']) if not rem else i18n.subj('REMEDIAL')} · "
                               f"{i18n.teachers(l['teachers'])}"})
    if rec and rows_by == "teacher":                 # reception hours: teacher-only cards (no class, no room)
        for tc_, (d_, s_) in rec.items():
            if tc_ in hours:
                out.append({"id": f"REC::{tc_}", "rows": [tc_], "day": int(d_), "start": int(s_), "duration": 1,
                            "title": t("rec_title"), "sub": "&nbsp;", "bg": REC_BG, "locked": False, "pinned": False,
                            "clash": False, "moved": False, "tooltip": t("rec_tip", t=tc_)})
    rows_ = [{"key": k, "label": i18n.cls(k) if rows_by == "class" else k,
              "sub": t("tot_h", h=hours[k]) + (f" + {remh[k]}" if remh[k] else "")} for k in keys]
    return {"rows": rows_, "lessons": out, "sel": sel, "status": status, "readonly": readonly, "free": free,
            "title": t("class") if rows_by == "class" else t("teacher"),
            "days": [i18n.day(d_) for d_ in range(5)], "slots": [str(i + 1) for i in range(7)],
            "off": [f"2,{s_}" for s_ in range(4, 7)], "lunch": 3, "rtl": i18n.is_ar(),
            "i18n": {"free": t("dnd_free"), "swap": t("dnd_swap"), "impossible": t("dnd_impossible"),
                     "current": t("dnd_current"), "hint": t("full_hint"), "moving": t("dnd_moving"),
                     "not_allowed": t("dnd_not_allowed"), "applying": t("dnd_applying"), "loading": t("full_loading"),
                     "other_row": t("full_other_row"), "locked": t("e_locked"), "forced": t("dnd_forced"),
                     "st_green": t("st_green"), "st_yellow": t("st_yellow"), "st_red": t("st_red"), "st_current": t("st_current")}}


def subject_legend(subjects):
    chips = "".join(f'<span style="display:inline-block;margin:2px 6px 2px 0;padding:2px 9px;border-radius:10px;'
                    f'background:{colors.light(s_)};border-left:5px solid {colors.strong(s_)};font-size:13px">'
                    f'{i18n.subj(s_)}</span>' for s_ in subjects)
    st.markdown(f"<div>{chips}</div>", unsafe_allow_html=True)


TT_MODE = "view"
if PAGE == "tt":
    if "_solved" in ss:
        solved_dialog(ss.pop("_solved"))
    vs = versions()
    if not vs:
        st.info(t("no_versions"))
    else:
        _hd = st.columns([3, 2])
        v = _hd[0].selectbox(t("version"), vs, index=default_index(vs), format_func=version_label,
                             key=f"tt_version_{st.session_state.get('current_version')}")
        _can_edit = v in DB.has_state(WS)
        _modes = ["view", "quick", "free"] if _can_edit else ["view"]
        if ss.get("tt_mode") not in _modes:
            ss["tt_mode"] = "view"
        TT_MODE = _hd[1].radio(t("tt_mode"), _modes, horizontal=True, key="tt_mode",
                               format_func=lambda x: t("mode_" + x), help=t("mode_help"))
        if not _can_edit:
            _hd[1].caption(t("no_state_edit"))
        _eds = ss.get("ed")
        _unsaved = bool(_eds and _eds.get("version") == v and _eds.get("undo"))
        if TT_MODE == "view":
            if _unsaved:
                df = ScheduleEditor(_eds["cur"]).to_schedule_df()
                st.warning(t("unsaved_badge", n=len(_eds["undo"])))
            else:
                df = manager.load(v)
            _vstate = _eds["cur"] if _unsaved else load_state(v)
            if "Classes" not in df.columns:
                df["Classes"] = ""
            df["Classes"] = df["Classes"].fillna("").astype(str)
            is_rem = df["Class"].astype(str).str.startswith("REM:")
            with st.expander(t("export_title")):
                secs = st.multiselect(t("export_sections"), ["full_class", "full_teacher", "class", "teacher", "rooms"],
                                      default=["full_class", "full_teacher", "class", "teacher", "rooms"],
                                      format_func=lambda x: t("exp_" + x), key=f"exp_secs_{v}")
                _ents = sorted({c_ for c_ in df.loc[~is_rem, "Class"]}, key=_class_key)
                _tchs = sorted({x_ for z_ in df["Teachers"] for x_ in str(z_).split(", ") if x_}, key=nat)
                _only = st.selectbox(t("exp_only"), [None] + [("class", c_) for c_ in _ents] + [("teacher", x_) for x_ in _tchs],
                                     format_func=lambda o: t("exp_all") if o is None else
                                     (("🎒 " + i18n.cls(o[1])) if o[0] == "class" else "👨‍🏫 " + o[1]), key=f"exp_only_{v}")
                if _only:
                    secs = [_only[0]]
                _k = (WS, v, DB.stamp(WS, v), i18n.LANG, tuple(secs), _only)
                c_x, c_p, c_o = st.columns(3)
                _fn = f"{WS}_{v}" + (f"_{_only[1]}" if _only else "")
                if _unsaved:
                    st.caption(t("export_unsaved"))
                elif secs:
                    c_x.download_button(t("export_xlsx"), export_file("xlsx", _k), f"{_fn}.xlsx",
                                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
                    _pdf = export_file("pdf", _k)
                    c_p.download_button(t("export_pdf"), _pdf, f"{_fn}.pdf", "application/pdf", width="stretch")
                    c_o.link_button(t("open_pdf_tab"), publish_file(_pdf), width="stretch")
            subject_legend(sorted({colors.base(x) for x in df["Subject"]}, key=lambda z: (z == "REMEDIAL", z)))
            view = st.radio(t("view_by"), ["class", "teacher", "full_class", "full_teacher", "rooms"], horizontal=True,
                            format_func=lambda x: t("lay_" + x) if x.startswith("full") else (t("rm_view") if x == "rooms" else t(x)))
            if view == "rooms":
                _caps = rooms_caps(v)
                occ = rms.allocate(df, data_frames.get("subjects"), _caps)
                sm_ = rms.summary(occ, _caps)
                st.subheader(t("rm_title"))
                for x_ in sm_["types"]:
                    st.caption(t("rm_kpi_used", rt=rms.rt_label(x_["rt"]), u=x_["used"], a=x_["avail"],
                                 p=round(100 * x_["used"] / x_["avail"]) if x_["avail"] else 0, m=x_["peak"], c=x_["cap"]))
                (st.warning if sm_["none"] else st.success)(t("rm_none", n=sm_["none"]) if sm_["none"] else t("rm_all_ok"))
                st.caption(" · ".join([t("rm_borrowed_n", n=sm_["borrowed"])] +
                                      ([t("rm_fallback_n", n=sm_["fallback"])] if sm_["fallback"] else [])) +
                           "  (↪ = " + t("rm_note_borrow", c="…") + ", 🔁 = " + t("rm_note_fb") + ")")
                st.markdown(rms.grid_html(occ, _caps, color_light=colors.light, color_strong=colors.strong), unsafe_allow_html=True)
                st.subheader(t("rm_free_title"))
                ft_ = rms.free_table(occ, _caps)
                st.dataframe(ft_.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=max(4, int(_caps.get("classroom", 1)) // 3))
                             .format(lambda z: "—" if z != z else f"{int(z)}"), width="stretch")
                _o = occ.assign(Day=occ["Day"].map(i18n.day), Slot=occ["Slot"] + 1,
                                RoomType=occ["RoomType"].map(rms.rt_label), Subject=occ["Subject"].map(i18n.subj),
                                Note=[rms.note_text(r_) for r_ in occ.itertuples()]).drop(columns=["NoteArg"])
                _o["Class"] = [", ".join(i18n.cls(c_.strip()) for c_ in str(x_).split(",")) for x_ in _o["Class"]]
                _o = _o.rename(columns={c_: dl._lbl(dl.COLS[c_], i18n.LANG) for c_ in _o.columns if c_ in dl.COLS})
                st.download_button("⬇️ CSV", _o.to_csv(index=False).encode("utf-8-sig"), f"{v}_rooms.csv", "text/csv")
            elif view.startswith("full"):
                pseudo = []
                for i_, r in enumerate(df.itertuples()):
                    rem_ = str(r.Class).startswith("REM:")
                    pseudo.append({"id": f"p{i_}", "class": r.Class, "teachers": str(r.Teachers).split(", "), "subject": r.Subject,
                                   "day": int(r.Day), "start": int(r.Slot), "duration": 1, "remedial": rem_,
                                   "blocks_classes": [z.strip() for z in str(r.Classes).split(",") if z.strip()] if rem_ else []})
                _rec_v = None
                if view == "full_teacher":
                    _sv = load_state(v)
                    if _sv:
                        _rec_v = (_sv.get("reception") if "reception" in _sv else ScheduleEditor(_sv).rec)
                dnd_full(data=full_payload(pseudo, "class" if view == "full_class" else "teacher", readonly=True, rec=_rec_v),
                         key=f"ttfull_{v}_{view}", default=None)
            elif view in ("class", "teacher") and _vstate:
                # same board as the editor, read-only (the plain grid layout is kept for the printouts)
                _ved = ScheduleEditor(_vstate)
                if view == "class":
                    _opts = sorted({l["class"] for l in _ved.L.values() if not str(l["class"]).startswith("REM:")}, key=_class_key)
                else:
                    _opts = sorted({x for l in _ved.L.values() for x in l["teachers"]}, key=nat)
                _who = st.selectbox(t(view), _opts, key=f"view_who_{view}",
                                    format_func=(lambda c_: f"{i18n.cls(c_)}") if view == "class" else str)
                if view == "class":
                    _cs = class_stats(df)
                    if _who in _cs.index:
                        st.markdown(class_chips(_cs.loc[_who]), unsafe_allow_html=True)
                else:
                    _wi, _kk = load_state_info(v)
                    _ts = teacher_stats(df, _wi, _kk)
                    if _who in _ts.index:
                        st.markdown(teacher_chips(_ts.loc[_who]), unsafe_allow_html=True)
                dnd_timetable(data=single_payload(_ved, view, _who, readonly=True, tw=_vstate.get("teacher_windows", {})),
                              key=f"vdnd_{v}_{view}", default=None)
            elif view == "class":
                own = df[~is_rem].copy()
                own["Label"] = [f"{i18n.subj(s_)} ({tc})" for s_, tc in zip(own["Subject"], own["Teachers"])]
                rem = df[is_rem]
                if "RemSubject" not in rem.columns:
                    rem = rem.assign(RemSubject="")
                cellmap = {}
                for r in rem.itertuples():            # remediation shown in every class of the teacher
                    for c in [z.strip() for z in r.Classes.split(",") if z.strip()]:
                        cellmap.setdefault((c, r.Day, r.Slot), []).append((str(r.RemSubject or ""), r.Teachers))
                rem_rows = []
                for (c, d_, s_), items in cellmap.items():  # grouped sessions (same hour) -> ONE cell
                    subs = " / ".join(dict.fromkeys(i18n.subj(x) for x, _ in items if x and x != "nan"))
                    tchs = " / ".join(tc for _, tc in items)
                    rem_rows.append({"Class": c, "Day": d_, "Slot": s_, "Subject": "REMEDIAL", "Teachers": tchs,
                                     "Label": f"{i18n.subj('REMEDIAL')}{': ' + subs if subs else ''} ({tchs})"})
                full = pd.concat([own, pd.DataFrame(rem_rows)], ignore_index=True) if rem_rows else own
                classes_ = sorted(own["Class"].unique(), key=_class_key)
                summ = pd.DataFrame({t("tot_class"): [i18n.cls(c) for c in classes_],
                                     t("tot_hours"): [int((own["Class"] == c).sum()) for c in classes_],
                                     t("tot_rem"): [sum(1 for x in rem_rows if x["Class"] == c) for c in classes_]})
                with st.expander(t("tot_title_c", n=len(classes_), h=int(len(own))), expanded=False):
                    st.dataframe(summ, hide_index=True, width="stretch")
                cst = class_stats(df)
                for c in classes_:
                    h = int((own["Class"] == c).sum()); r_ = sum(1 for x in rem_rows if x["Class"] == c)
                    st.markdown(f"#### 🎒 {i18n.cls(c)} — {t('tot_h', h=h)}" + (f" + {t('tot_rem_h', h=r_)}" if r_ else ""))
                    if c in cst.index:
                        st.markdown(class_chips(cst.loc[c]), unsafe_allow_html=True)
                    st.dataframe(styled_grid(full, "Class", c, "Label"), width="stretch")
            else:
                dt = df.assign(Teacher=df["Teachers"].str.split(", ")).explode("Teacher")
                dt["Label"] = [f"{i18n.subj(s_)} ({cl})" if str(c).startswith("REM:") else f"{i18n.cls(c)} ({i18n.subj(s_)})"
                               for c, s_, cl in zip(dt["Class"], dt["Subject"], dt["Classes"])]
                teachers_ = sorted(dt["Teacher"].unique(), key=nat)
                tot = dt.groupby("Teacher").size()
                remc = dt[dt["Subject"] == "REMEDIAL"].groupby("Teacher").size()
                win_info, k_ = load_state_info(v)
                tst = teacher_stats(df, win_info, k_)
                summ = tst.reset_index()[["Teacher", "Priority", "Hours", "Remedial", "Days", "Gaps", "Single_hour",
                                          "Afternoon_h", "Slot7", "Avg_finish", "In_window", "Classes"]]
                summ = summ.sort_values(["Priority", "Teacher"], ascending=[False, True])
                summ["Priority"] = [prio_rate(tst.loc[x_]) for x_ in summ["Teacher"]]
                summ.columns = [t("ks_" + c_) for c_ in summ.columns]
                with st.expander(t("tot_title_t", n=len(teachers_), h=int(len(dt))), expanded=False):
                    st.dataframe(summ, hide_index=True, width="stretch")
                for tch in teachers_:
                    st.markdown(f"#### 👨‍🏫 {tch} — {t('tot_h', h=int(tot.get(tch, 0)))}")
                    if tch in tst.index:
                        st.markdown(teacher_chips(tst.loc[tch]), unsafe_allow_html=True)
                    st.dataframe(styled_grid(dt, "Teacher", tch, "Label"), width="stretch")

# ------------------------------------------------------------------ compare
if PAGE == "cmp":
    vs = versions()
    sel = st.multiselect(t("versions_cmp"), vs, default=vs[-2:])
    if sel:
        table = pd.DataFrame({v: kpi_frame(calculate_all_kpis(manager.load(v))) for v in sel})
        st.dataframe(table, width="stretch")
        st.caption(t("lower_better"))
    if vs:
        with st.expander(t("manage_versions")):
            mv = st.selectbox(t("version"), vs, index=len(vs) - 1, key="mv_sel")
            c_r1, c_r2 = st.columns([3, 1])
            new_nm = c_r1.text_input(t("new_name"), mv, key=f"mv_new_{mv}")
            if c_r2.button(t("rename"), width="stretch", key="mv_ren"):
                if DB.rename(WS, mv, new_nm.strip()):
                    if st.session_state.get("current_version") == mv:
                        st.session_state["current_version"] = new_nm.strip()
                    st.session_state.pop("ed", None); st.rerun()
                else:
                    st.error(t("rename_bad"))
            c_d1, c_d2 = st.columns([3, 1])
            sure = c_d1.checkbox(t("delete_confirm", v=mv), key=f"mv_sure_{mv}")
            if c_d2.button(t("delete"), width="stretch", disabled=not sure, key="mv_del"):
                DB.delete(WS, mv); st.session_state.pop("ed", None); st.rerun()
            st.divider()
            sure_all = st.checkbox(t("delete_all_confirm", n=len(vs)), key="mv_sure_all")
            if st.button(t("delete_all"), disabled=not sure_all, key="mv_del_all"):
                DB.clear(WS); st.session_state.pop("ed", None); st.rerun()

# ------------------------------------------------------------------ interactive editor
if PAGE == "tt" and TT_MODE != "view":
    if "_rn_who" in ss:                          # teacher renamed: keep showing the same teacher
        ss["ed_who_teacher"] = ss.pop("_rn_who")
    if "_ed_goto" in ss:                         # "affected" strip: open that class/teacher in the single layout
        _gk, _gw = ss.pop("_ed_goto")
        ss["ed_layout"], ss["ed_view"], ss[f"ed_who_{_gk}"] = "single", _gk, _gw
    if True:
        top = st.columns([2, 2])
        ed_state = st.session_state.get("ed")
        if ed_state is None or ed_state["version"] != v:
            base = load_state(v)
            ed_state = st.session_state["ed"] = {"version": v, "base": base, "cur": base, "undo": [], "log": [], "nonce": 0}
        editor = ScheduleEditor(ed_state["cur"])
        free = TT_MODE == "free"
        if ss.get("_move_err"):
            st.error(t("move_rejected", m=ss.pop("_move_err")))
        confirm_popup(editor, ed_state)
        affected_strip(ed_state)

        layout = top[0].radio(t("layout"), ["single", "full_class", "full_teacher"], key="ed_layout",
                              format_func=lambda x: t("lay_" + x))
        if layout == "single":
            view = st.radio(t("edit_by"), ["class", "teacher"], horizontal=True, key="ed_view", format_func=t)
            if view == "class":
                options = sorted({l["class"] for l in editor.L.values() if not str(l["class"]).startswith("REM:")}, key=_class_key)
            else:
                options = sorted({x for l in editor.L.values() for x in l["teachers"]})
            who = top[1].selectbox(t(view), options, key=f"ed_who_{view}",
                                   format_func=i18n.cls if view == "class" else str)

            payload = single_payload(editor, view, who, free=free, tw=ed_state["cur"].get("teacher_windows", {}))
            _tw = ed_state["cur"].get("teacher_windows", {})
            _live = editor.to_schedule_df()
            if view == "teacher":
                _ts = teacher_stats(_live, ed_state["cur"].get("teacher_windows_info") or _tw,
                                    ed_state["cur"].get("priority_strength", 3.0))
                if who in _ts.index:
                    st.markdown(f"**👨‍🏫 {who}**", unsafe_allow_html=True)
                    st.markdown(teacher_chips(_ts.loc[who]), unsafe_allow_html=True)
            else:
                _cs = class_stats(_live)
                if who in _cs.index:
                    st.markdown(f"**🎒 {i18n.cls(who)}**")
                    st.markdown(class_chips(_cs.loc[who]), unsafe_allow_html=True)
            _pdf1 = entity_pdf(_live.to_csv(index=False).encode("utf-8"), f"{WS} — {v}", view, who, i18n.LANG,
                               json.dumps(editor.rec if view == "teacher" else {}))
            st.link_button(t("open_this_pdf"), publish_file(_pdf1))
            event = dnd_timetable(data=payload, key=f"dnd_{v}", default=None)
            if event and event.get("nonce", 0) > ed_state["nonce"] and str(event.get("lid")).startswith("REC::"):
                ed_state["nonce"] = event["nonce"]
                before = editor.export_state()
                ok, msg = editor.move_rec(event["lid"][5:], event["day"], event["slot"])
                if ok:
                    ed_state["undo"].append(before); ed_state["cur"] = editor.export_state(); ed_state["log"].append(msg)
                    st.rerun()
                else:
                    st.error(t("move_rejected", m=msg))
            elif event and event.get("nonce", 0) > ed_state["nonce"]:
                ed_state["nonce"] = event["nonce"]
                queue_or_move(editor, ed_state, event["lid"], event["day"], event["slot"], free)

            # adapt / pins panel (was only under the full boards before the views were merged)
            _conf1 = editor.conflicts()
            _pr1 = ed_state.get("proposal")
            if _pr1 and _pr1.get("state"):
                st.info(t("proposal_preview"))
                _pe1 = ScheduleEditor(_pr1["state"])
                dnd_full(data=full_payload(_pe1.L.values(), view, readonly=True, pins=_pe1.pins,
                                           clash=_pe1.conflicts(), moved=set(_pr1["moved"])),
                         key=f"dndprev1_{v}_{view}", default=None)
            if free or editor.pins or _conf1 or (_pr1 and _pr1.get("state")):
                adapt_panel(editor, ed_state, v, None, f"single_sel_{v}", _conf1)

        else:
            rows_by = "class" if layout == "full_class" else "teacher"
            sel_key = f"full_sel_{v}_{rows_by}"
            sel = st.session_state.get(sel_key)
            if sel not in editor.L and not str(sel).startswith("REC::"):
                sel = None
            _conf = editor.conflicts()
            _pr = ed_state.get("proposal")
            if _pr and _pr.get("state"):
                # a solver proposal is waiting: show IT (read-only), not the edited timetable with its conflicts
                st.info(t("proposal_preview"))
                _pe = ScheduleEditor(_pr["state"])
                dnd_full(data=full_payload(_pe.L.values(), rows_by, readonly=True, pins=_pe.pins,
                                           clash=_pe.conflicts(), moved=set(_pr["moved"])),
                         key=f"dndprev_{v}_{rows_by}", default=None)
                adapt_panel(editor, ed_state, v, sel if sel in editor.L else None, sel_key, _conf)
            if sel and str(sel).startswith("REC::") and (rows_by != "teacher" or sel[5:] not in editor.rec):
                sel = None
            _st_sel = (editor.rec_status(sel[5:]) if sel and str(sel).startswith("REC::")
                       else editor.status_map([sel], free=free)[sel] if sel else None)
            payload = None if (_pr and _pr.get("state")) else full_payload(editor.L.values(), rows_by, sel=sel,
                                   status=_st_sel, rec=editor.rec,
                                   locked_fn=(lambda l_: False) if free else editor.locked,
                                   pins=editor.pins, clash=_conf, free=free)
            ev = dnd_full(data=payload, key=f"dndfull_{v}_{rows_by}", default=None) if payload else None
            if ev and ev.get("nonce", 0) > ed_state.get("nonce_full", 0):
                ed_state["nonce_full"] = ev["nonce"]
                if ev.get("type") == "select":
                    st.session_state[sel_key] = ev.get("lid")
                    st.rerun()
                elif ev.get("type") == "move" and str(ev["lid"]).startswith("REC::"):
                    before = editor.export_state()
                    ok, msg = editor.move_rec(ev["lid"][5:], ev["day"], ev["slot"])
                    if ok:
                        ed_state["undo"].append(before); ed_state["cur"] = editor.export_state()
                        ed_state["log"].append(msg); st.session_state[sel_key] = None; st.rerun()
                    else:
                        st.error(t("move_rejected", m=msg))
                elif ev.get("type") == "move":
                    queue_or_move(editor, ed_state, ev["lid"], ev["day"], ev["slot"], free, sel_key)

            if payload:
                adapt_panel(editor, ed_state, v, sel if sel in editor.L else None, sel_key, _conf)

        if not ed_state.get("proposal"):
            improve_panel(editor, ed_state, v)
        b = st.columns(4)
        if b[0].button(t("undo"), disabled=not ed_state["undo"], width="stretch"):
            ed_state["cur"] = ed_state["undo"].pop(); ed_state["log"].append(t("log_undo")); st.rerun()
        if b[1].button(t("reset"), disabled=not ed_state["undo"], width="stretch"):
            ed_state["cur"], ed_state["undo"] = ed_state["base"], []; ed_state["log"].append(t("log_reset")); st.rerun()
        new_name = b[2].text_input(t("save_as"), f"{v}_edited", label_visibility="collapsed")
        if b[3].button(t("save_new"), type="primary", width="stretch"):
            manager.save(editor.to_schedule_df(), new_name, state=editor.export_state())
            st.session_state["current_version"] = new_name
            st.success(t("saved_new", n=new_name))

        with st.expander(t("rn_panel"), expanded=False):
            st.caption(t("rn_help"))
            _names = sorted({x for l in editor.L.values() for x in l["teachers"]}, key=nat)
            _rn = st.data_editor(pd.DataFrame({t("rn_old"): _names, t("rn_new"): [""] * len(_names)}),
                                 disabled=[t("rn_old")], hide_index=True, width="stretch",
                                 key=f"rn_tbl_{v}_{len(ed_state['undo'])}")
            if st.button(t("rn_apply"), key="rn_apply"):
                _map = dict(zip(_rn[t("rn_old")], _rn[t("rn_new")].fillna("").astype(str)))
                before = editor.export_state()
                ok, msg = editor.rename_teachers(_map)
                if ok:
                    ed_state["undo"].append(before); ed_state["cur"] = editor.export_state(); ed_state["log"].append(msg)
                    if ss.get("ed_who_teacher") in _map and str(_map[ss["ed_who_teacher"]]).strip():
                        ss["_rn_who"] = str(_map[ss["ed_who_teacher"]]).strip()
                    ss["_toast"] = msg
                    st.rerun()
                else:
                    st.error(msg)

        with st.expander(t("rec_panel", n=len(editor.rec)), expanded=False):
            st.caption(t("rec_panel_help"))
            _all_t = sorted({x for l in editor.L.values() for x in l["teachers"]}, key=nat)
            rc1, rc2 = st.columns([2, 3])
            with rc1:
                _rt = st.selectbox(t("teacher"), _all_t, key="rec_teacher",
                                   format_func=lambda x: f"{x} – {i18n.day(editor.rec[x][0])} {editor.rec[x][1] + 1}"
                                   if x in editor.rec else f"{x} – {t('rec_none')}")
                bb = st.columns(3)
                if bb[0].button(t("rec_add"), width="stretch", help=t("rec_add_help")):
                    before = editor.export_state(); editor.rec.pop(_rt, None)
                    cell = editor.add_rec(_rt)
                    if cell:
                        ed_state["undo"].append(before); ed_state["cur"] = editor.export_state()
                        ed_state["log"].append(t("rec_moved", t=_rt, d=i18n.day(cell[0]), s=cell[1] + 1)); st.rerun()
                    else:
                        st.warning(t("rec_nowhere"))
                if bb[1].button(t("rec_remove"), width="stretch", disabled=_rt not in editor.rec):
                    before = editor.export_state(); editor.remove_rec(_rt)
                    ed_state["undo"].append(before); ed_state["cur"] = editor.export_state(); st.rerun()
                if bb[2].button(t("rec_reset"), width="stretch", help=t("rec_reset_help")):
                    before = editor.export_state(); editor.rec, editor.rec_removed = {}, set(); editor.fix_reception()
                    ed_state["undo"].append(before); ed_state["cur"] = editor.export_state(); st.rerun()
            with rc2:
                st.dataframe(pd.DataFrame([{t("teacher"): k, t("pre_c_day"): i18n.day(d_), t("pre_c_slot"): s_ + 1}
                                           for k, (d_, s_) in sorted(editor.rec.items(), key=lambda x: nat(x[0]))]),
                             hide_index=True, width="stretch", height=240)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(t("live_kpis"))
            k0 = kpi_frame(calculate_all_kpis(ScheduleEditor(ed_state["base"]).to_schedule_df()))
            k1 = kpi_frame(calculate_all_kpis(editor.to_schedule_df()))
            kt = pd.DataFrame({t("solver_col"): k0, t("edited_col"): k1})
            kt["Δ"] = kt[t("edited_col")] - kt[t("solver_col")]
            st.dataframe(kt, width="stretch")
        with c2:
            st.markdown(t("change_log"))
            st.code("\n".join(ed_state["log"][-15:]) or t("no_changes"), language=None)
            hv = editor.hard_violations()
            st.caption(t("no_double") if not hv else "❌ " + t("sep").join(hv))

# ------------------------------------------------------------------ step 1: assignment (جدول توزيع الحصص)
if PAGE == "plan":
    st.markdown(t("plan_title"))
    st.caption(t("plan_caption"))
    cur = st.session_state.get("plan")
    can_gen = "classes" in data_frames and "subjects" in data_frames

    with st.expander(t("gen_expander"), expanded=cur is None):
        if not can_gen:
            st.info(t("need_classes_curr"))
        else:
            mode = st.radio(t("method"), ["auto", "staff"], horizontal=True,
                            format_func=lambda x: t("m_auto") if x == "auto" else t("m_staff"))
            if mode == "auto":
                c1, c2 = st.columns([1, 3])
                max_default = c1.number_input(t("max_per_post"), 10, 30, 21)
                subjects = sorted(data_frames["subjects"]["Subject_Code"].unique())
                defaults = pd.DataFrame({
                    t("c_subject"): subjects,
                    t("c_arabic"): [CODE_TO_ARABIC.get(x, x) for x in subjects],
                    t("c_max"): [max_default] * len(subjects),
                    t("c_remedial"): [1 if x in ("ARABIC", "MATH", "FRENCH") else 0 for x in subjects]})
                with c2:
                    st.caption(t("per_subject"))
                    per = st.data_editor(defaults, hide_index=True, width="stretch",
                                         disabled=[t("c_subject"), t("c_arabic")],
                                         key=f"per_subj_{max_default}_{i18n.LANG}")
                if st.button(t("generate"), type="primary"):
                    with st.spinner(t("generating")):
                        try:
                            p = ap.plan_auto_posts(ap.make_loader(data_frames), max_default,
                                                   dict(zip(per[t("c_subject")], per[t("c_max")])),
                                                   dict(zip(per[t("c_subject")], per[t("c_remedial")])))
                            st.session_state.update(plan=p, plan_active=True, plan_origin=("o_auto", {}))
                            st.rerun()
                        except Exception as ex:
                            st.error(f"❌ {ex}")
            else:
                if staff_original is None:
                    st.info(t("need_staff"))
                elif st.button(t("gen_staff"), type="primary"):
                    with st.spinner(t("assigning")):
                        try:
                            dfs = dict(data_frames, teachers=staff_original)
                            if src == "sample":
                                dfs["classes"] = pd.read_csv(os.path.join(SAMPLE, FILES["classes"]))
                            p = ap.plan_from_staff(ap.make_loader(dfs))
                            st.session_state.update(plan=p, plan_active=True, plan_origin=("o_staff", {}))
                            st.rerun()
                        except Exception as ex:
                            st.error(f"❌ {ex}")

    if cur is None:
        st.info(t("no_plan"))
    else:
        top = st.columns([3, 2])
        top[0].markdown(t("current_plan", o=i18n.tr_message(st.session_state.get("plan_origin", "")),
                          p=len(cur["teachers"]), c=len(cur["classes"]),
                          h=int(cur["assignment"]["Hours"].sum() + sum(cur["remedial"].values()))))
        active = top[1].toggle(t("use_plan"), st.session_state.get("plan_active", True))
        if active != st.session_state.get("plan_active"):
            st.session_state["plan_active"] = active; st.rerun()
        if active and data_ready and top[1].button(t("go_run"), type="primary", key="plan_go_run"):
            goto("run")

        for w in cur.get("warnings", []) + cur.get("notes", []):
            st.warning(i18n.tr_message(w))

        # ---- checks: teacher hours vs curriculum, and REAL class slots (split sessions counted once)
        c0 = SchedulerConfig()
        slots_avail = c0.days * c0.slots - (c0.slots - (c0.lunch_boundary + 1))
        try:
            dfc = dict(data_frames); dfc.setdefault("classes", cur["classes"]); dfc["teachers"] = cur["teachers"]
            probe = SchoolSchedulerEngine(ap.make_loader(dfc), c0, fixed_assignment=cur["assignment"])
            probe._generate_lessons_and_assignments()
            levels = dict(zip(dfc["classes"]["Class_ID"], dfc["classes"]["Level"]))
            diff, _ = validate_against_curriculum(cur["assignment"], levels, probe._calculate_required_hours, slots_avail)
            need = class_slot_needs(probe)
            over = need[need["slots"] > slots_avail]["slots"]
            if len(over):
                st.error(t("over_cap", n=len(over), s=slots_avail, d=c0.days, k=c0.slots,
                           lst=", ".join(f"{i18n.cls(c)} ({int(h)})" for c, h in over.items())))
            if len(diff):
                mismatch_panel("plan")
            if not len(over) and not len(diff):
                st.success(t("plan_ok"))
            with st.expander(t("slots_title", s=slots_avail), expanded=bool(len(over))):
                st.caption(t("slots_caption"))
                nt = need.loc[sorted(need.index, key=_class_key)].copy()
                declared = cur.get("class_hours") or {}
                if declared:
                    nt["declared"] = [int(declared[c]) if c in declared else None for c in nt.index]
                nt["free"] = slots_avail - nt["slots"]
                nt["grid"] = [f"20 + 8 + {int(h) - 28}" if h >= 28 else (f"20 + {int(h) - 20}" if h >= 20 else str(int(h)))
                              for h in nt["slots"]]
                nt.index = [i18n.cls(c) for c in nt.index]
                st.dataframe(nt.rename(columns={"teacher_hours": t("sl_teacher"), "split_overlap": t("sl_overlap"),
                                                "slots": t("sl_slots"), "declared": t("sl_declared"),
                                                "free": t("sl_free"), "grid": t("sl_grid")}), width="stretch")
        except Exception as ex:
            st.caption(t("crosscheck_na", e=ex))
        if data_frames.get("rules") is not None:
            with st.expander(t("sr_title")):
                render_split_rules(data_frames, "plan")

        # ---- posts / loads, editable teacher names
        st.markdown(t("posts_title"))
        lt = ap.load_table(cur)
        lt["Status"] = lt["Status"].replace({"⛔ over max": t("over_max")})
        lt["Subject"] = lt["Subject"].map(i18n.subj)
        lt["Classes"] = lt["Classes"].map(lambda s: "، ".join(i18n.cls(x.strip()) for x in s.split(",")) if i18n.is_ar() else s)
        lt["Levels"] = lt["Levels"].map(lambda s: s.replace("AM", "م") if i18n.is_ar() else s)
        lt.insert(2, "Name", lt["Teacher"])
        shown = loc_df(lt, "lt_")
        name_col = t("lt_Name")
        ed_lt = st.data_editor(shown, hide_index=True, width="stretch", key=f"lt_{id(cur)}_{i18n.LANG}",
                               disabled=[c for c in shown.columns if c != name_col])
        if st.button(t("apply_names")):
            st.session_state["plan"] = ap.rename_teachers(cur, dict(zip(lt["Teacher"], ed_lt[name_col])))
            st.rerun()

        # ---- reassign classes: class × subject -> post
        st.markdown(t("reassign_title"))
        a = cur["assignment"]
        grid = a.pivot_table(index="Class", columns="Subject", values="Post", aggfunc="first")
        order = {k: i for i, k in enumerate(CODE_TO_ARABIC)}
        grid = grid[sorted(grid.columns, key=lambda x: order.get(x, 99))]
        grid = grid.loc[sorted(grid.index, key=_class_key)]
        colcfg = {"Class": st.column_config.TextColumn(t("class"))}
        for sj in grid.columns:
            posts_s = sorted(a[a.Subject == sj]["Post"].unique(), key=nat)
            colcfg[sj] = st.column_config.SelectboxColumn(i18n.subj(sj), options=posts_s + [ap.post_label(sj, len(posts_s) + 1)])
        g0 = grid.reset_index()
        g_show = g0.copy(); g_show["Class"] = g_show["Class"].map(i18n.cls)
        ed_grid = st.data_editor(g_show, hide_index=True, width="stretch", column_config=colcfg,
                                 disabled=["Class"], key=f"grid_{id(cur)}_{i18n.LANG}")
        changes = []
        for i in range(len(g0)):
            for sj in grid.columns:
                o, n = g0.iloc[i][sj], ed_grid.iloc[i][sj]
                if isinstance(n, str) and n and n != o:
                    changes.append((g0.iloc[i]["Class"], sj, n))
        if changes:
            st.info(t("n_changes", n=len(changes),
                      x=t("sep").join(f"{i18n.cls(c)} {i18n.subj(s_)} → {p_}" for c, s_, p_ in changes)))
            if st.button(t("apply_reassign"), type="primary"):
                p = cur
                for c, s_, n in changes:
                    p = ap.reassign(p, c, s_, n)
                st.session_state["plan"] = p
                st.rerun()

        # ---- school format view + download
        st.markdown(t("school_format"))
        view_df = a.copy()
        lbl = lambda post, tch: post if tch == post else f"{post} · {tch}"
        view_df["Col"] = [lbl(p_, t_) for p_, t_ in zip(view_df["Post"], view_df["Teacher"])]
        lt0 = ap.load_table(cur)
        cols_order = list(dict.fromkeys(lbl(p_, t_) for p_, t_ in zip(lt0["Post"], lt0["Teacher"])))
        mat = view_df.pivot_table(index="Class", columns="Col", values="Hours", aggfunc="sum")
        mat = mat.reindex(index=sorted(mat.index, key=_class_key), columns=[c for c in cols_order if c in mat.columns])
        mat.insert(0, t("weekly_hours"), mat.sum(axis=1).astype(int))
        mat.index = [i18n.cls(c) for c in mat.index]
        tot = pd.DataFrame([mat.sum()], index=[t("total_no_rem")])
        st.dataframe(pd.concat([mat, tot]).fillna("").astype(str).replace(r"\.0$", "", regex=True), width="stretch")
        xl = build_matrix_xlsx(a, None, {}, remedial=cur["remedial"])
        st.download_button(t("dl_plan"), xl, "assignment_توزيع_الحصص.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")


# ------------------------------------------------------------------ next step
_NEXT = {"data": "plan", "plan": "run", "tt": "cmp"}
if PAGE in _NEXT and (PAGE != "data" or data_ready) and not (PAGE == "plan" and plan is None):
    st.divider()
    if st.button(t("next_to", p=t("pg_" + _NEXT[PAGE])), key="next_page"):
        goto(_NEXT[PAGE])
