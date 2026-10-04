"""Server-side presets (school-type default values) – e.g. presets/middle_school_dz.json.

Nothing in the solver is hard-coded any more: the time profile, the soft-rule weights and the default data tables
(curriculum, subject unavailable times, rooms, split/session templates) come from the active preset.  The manager
can still edit / import / export every table; the preset only fills the starting values.
"""
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "presets")
DEFAULT_ID = "middle_school_dz"
_cache = {}


def available():
    """{preset id: display name dict} for every JSON file in presets/."""
    out = {}
    for f in sorted(os.listdir(DIR)) if os.path.isdir(DIR) else []:
        if f.endswith(".json"):
            try:
                out[f[:-5]] = load(f[:-5]).get("name", {"en": f[:-5]})
            except Exception:
                pass
    return out


def load(pid=DEFAULT_ID):
    if pid not in _cache:
        with open(os.path.join(DIR, pid + ".json"), encoding="utf-8") as fh:
            _cache[pid] = json.load(fh)
    return _cache[pid]


def time_profile(P, pid=None):
    tps = P.get("time_profiles") or []
    return next((x for x in tps if x.get("id") == pid), tps[0] if tps else None)


def policy(P, pid=None):
    pols = P.get("policies") or []
    return (next((x for x in pols if x.get("id") == pid), pols[0] if pols else {}) or {}).get("rules", {})


def apply_to_config(cfg, P=None):
    """Write the preset's time profile + policy weights into a SchedulerConfig (all keys optional)."""
    P = P or load()
    tp = time_profile(P)
    if tp:
        cfg.days = len(tp.get("days") or []) or cfg.days
        cfg.slots = len(tp.get("periods") or []) or cfg.slots
        if tp.get("lunch_after_period") is not None:
            cfg.lunch_boundary = int(tp["lunch_after_period"])
        cfg.closed_halfdays = [[int(c["day"]), c["half"]] for c in tp.get("closed", [])]
    # years with their own time profile -> level_profiles (same days and lunch as the school week)
    lp = {}
    for y in P.get("years", []):
        yp = time_profile(P, y.get("time_profile"))
        if yp and tp and yp.get("id") != tp.get("id"):
            lp[str(y["id"])] = {"slots": len(yp.get("periods") or []) or cfg.slots,
                                "closed": [[int(c["day"]), c["half"]] for c in yp.get("closed", [])]}
    cfg.level_profiles = lp
    r = policy(P)
    g = r.get("class_grid", {})
    if g:
        cfg.strict_class_grid = bool(g.get("on", cfg.strict_class_grid))
        cfg.no_slot7_days = list(g.get("avoid_extra_days", cfg.no_slot7_days))
        c = g.get("costs", {})
        cfg.grid_cost_afternoon = c.get("afternoon", cfg.grid_cost_afternoon)
        cfg.grid_cost_extra = c.get("extra", cfg.grid_cost_extra)
        cfg.grid_cost_bad_day = c.get("extra_bad_day", cfg.grid_cost_bad_day)
        cfg.empty_morning_slot_penalty = c.get("empty_morning_period", cfg.empty_morning_slot_penalty)
    if "student_gaps" in r:
        cfg.allow_student_gaps = r["student_gaps"] != "forbidden"
    if "max_2h_blocks_per_day" in r:
        cfg.enforce_max_2h_courses_per_day = r["max_2h_blocks_per_day"] is not None
        cfg.max_2h_courses_per_day = int(r["max_2h_blocks_per_day"] or 1)
    tc = r.get("teacher_comfort", {})
    for k, a in (("single_hour_half_day", "teacher_single_hour_weight"), ("gap_1h", "teacher_single_gap_weight"),
                 ("gap_2h", "teacher_double_gap_weight"), ("working_day", "teacher_working_day_weight"),
                 ("half_day_shift", "teacher_shift_weight"), ("late_finish", "teacher_late_finish_weight"),
                 ("afternoon_hour", "teacher_afternoon_penalty")):
        if k in tc:
            setattr(cfg, a, tc[k])
    tp_ = r.get("teacher_priority", {})
    cfg.teacher_priority_strength = tp_.get("strength", cfg.teacher_priority_strength)
    cfg.priority_levels_share = tp_.get("levels_share", cfg.priority_levels_share)
    pc = r.get("period_costs", {})
    for k, a in (("1", "slot_1_penalty"), ("4", "slot_4_penalty"), ("5", "slot_5_penalty"), ("7", "slot_7_penalty"),
                 ("7_equity", "slot_7_equity_penalty")):
        if k in pc:
            setattr(cfg, a, pc[k])
    if "reception" in r:
        cfg.reception_in_gap_reward = r["reception"].get("in_gap_reward", cfg.reception_in_gap_reward)
    rc = r.get("remedial_costs", {})
    for k, a in (("morning", "remedial_cost_morning"), ("afternoon", "remedial_cost_afternoon"),
                 ("period_7", "remedial_slot7_cost"), ("gap", "remedial_gap_cost"), ("group", "remedial_group_cost"),
                 ("overlap", "remedial_overlap_cost")):
        if k in rc:
            setattr(cfg, a, rc[k])
    if "same_day_exempt" in r:
        cfg.same_day_exempt = list(r["same_day_exempt"])
    if "subject_unavailable_hard" in r:
        cfg.teacher_windows_hard = bool(r["subject_unavailable_hard"])
    rem = next((x for x in P.get("session_templates", []) if x.get("kind") == "multi_class"
                and x.get("who") == "teacher_all_classes"), None)
    if rem and rem.get("subjects_pair") is not None:
        cfg.remedial_groups = [set(p_) for p_ in rem["subjects_pair"]]
    if rem:
        if rem.get("preferred_periods"):
            cfg.remedial_periods = [int(x) for x in rem["preferred_periods"]]
        cfg.remedial_ends_day = bool(rem.get("ends_day", True))
    fb = {x["id"]: x["fallback"] for x in P.get("room_types", []) if x.get("fallback")}
    cfg.room_fallback = fb
    sv = P.get("solver", {})
    cfg.max_time_seconds = sv.get("time_limit_s", cfg.max_time_seconds)
    cfg.num_workers = sv.get("workers", cfg.num_workers)
    cfg.grid_phase_share = sv.get("grid_phase_share", cfg.grid_phase_share)
    return cfg


def day_names(P=None):
    tp = time_profile(P or load())
    return [d.get("name", {}) for d in tp.get("days", [])] if tp else None


def level_week_df(P=None, classes=None):
    """Per-level week as an editable table: one row per level (Periods = last period, Closed = extra closed
    half-days "day:half;..." with 1-based days, half = morning|afternoon|all), from the preset's years."""
    import pandas as pd
    from engine import SchedulerConfig
    P = P or load()
    cfg = apply_to_config(SchedulerConfig(), P)
    levels = list(dict.fromkeys(classes["Level"].astype(str))) if classes is not None and "Level" in classes else \
        [str(y["id"]) for y in P.get("years", [])]
    rows = []
    for lv in levels:
        pr = cfg.level_profiles.get(lv, {})
        rows.append({"Level": lv, "Periods": str(pr.get("slots", cfg.slots)),
                     "Closed": ";".join(f"{int(d) + 1}:{h}" for d, h in pr.get("closed", []))})
    return pd.DataFrame(rows, columns=["Level", "Periods", "Closed"])


JOINT_COLS = ["ID", "Classes", "Subjects", "Hours", "Block"]


def joint_df(P=None):
    """Joint-session templates (kind "joint") as an editable table; lists are ";"-separated."""
    import pandas as pd
    rows = [{"ID": x.get("id", ""), "Classes": ";".join(x.get("classes", [])), "Subjects": ";".join(x.get("subjects", [])),
             "Hours": str(x.get("hours", "")), "Block": str(x.get("block", 1))}
            for x in (P or load()).get("session_templates", []) if x.get("kind") == "joint"]
    return pd.DataFrame(rows, columns=JOINT_COLS)


def joint_to_cfg(df, cfg):
    out = []
    for r in ([] if df is None else df.fillna("").to_dict("records")):
        sp = lambda v: [x.strip() for x in str(v).replace(",", ";").split(";") if x.strip()]
        try:
            h, b = int(float(r.get("Hours") or 0)), int(float(r.get("Block") or 1))
        except ValueError:
            continue
        if sp(r.get("Classes")) and sp(r.get("Subjects")) and h > 0:
            out.append({"id": str(r.get("ID") or f"J{len(out) + 1}"), "classes": sp(r["Classes"]),
                        "subjects": sp(r["Subjects"]), "hours": h, "block": b})
    cfg.joint_sessions = out
    return cfg


# ---------------------------------------------------------------- default data tables (current file formats)
def curriculum_df(P=None):
    P = P or load()
    return pd.DataFrame([{"Level": r["year"], "Subject_Code": r["subject"], "Hrs_Cours": r["hours"].get("course", 0),
                          "Hrs_TD": r["hours"].get("td", 0), "Hrs_TP": r["hours"].get("tp", 0),
                          "Hrs_Practice": r["hours"].get("practice", 0), "Required_Room_Type": r.get("room_type", "classroom")}
                         for r in P.get("curriculum", [])])


def windows_df(P=None):
    P = P or load()
    return pd.DataFrame([{"Subject_Code": r["subject"], "Day_Index": int(r["day"]),
                          "Blocked_Slots": ";".join(str(x) for x in r["periods"]), "Description": r.get("why", "")}
                         for r in P.get("subject_unavailable", [])],
                        columns=["Subject_Code", "Day_Index", "Blocked_Slots", "Description"])


def rooms_df(P=None):
    P = P or load()
    return pd.DataFrame([{"Room_Type": r["id"], "Capacity": int(r.get("count", 0))} for r in P.get("room_types", [])])


def rules_df(P=None):
    """split_class session templates -> the split_rules table format used by the engine."""
    P = P or load()
    rows = []
    yrs_all = [y["id"] for y in P.get("years", [])]
    for r in P.get("session_templates", []):
        if r.get("kind") != "split_class" or len(r.get("groups", [])) != 2:
            continue
        a, b = r["groups"][0]["parts"], r["groups"][1]["parts"]
        yrs = r.get("years") or yrs_all
        rows.append({"Rule_ID": r["id"], "Level": "ALL" if sorted(yrs) == sorted(yrs_all) else ";".join(yrs),
                     "Primary_Subject": a[0]["subject"], "Primary_Type": a[0]["type"], "Primary_Hours": int(a[0]["hours"]),
                     "Secondary_Subject": ";".join(x["subject"] for x in b), "Secondary_Type": b[0]["type"],
                     "Secondary_Hours": ";".join(str(int(x["hours"])) for x in b) if len(b) > 1 else int(b[0]["hours"]),
                     "Frequency": 2 if r.get("frequency") == "alternate_weeks" else 1,
                     "Description": r.get("description", "")})
    return pd.DataFrame(rows)


def teacher_defaults(P=None):
    return (P or load()).get("teacher_defaults", {})


def default_frames(P=None):
    """The preset's default data tables, keyed like the app's data_frames."""
    P = P or load()
    return {"subjects": curriculum_df(P), "inspections": windows_df(P), "rooms": rooms_df(P), "rules": rules_df(P)}
