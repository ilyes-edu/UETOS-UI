"""Step 1 – build the teacher assignment (جدول توزيع الحصص) before the timetable solver runs.

Two generation modes:
  * from_staff  : use staff.csv (qualified subjects + max hours) – the engine's own assignment model
  * auto_posts  : no staff needed – computes how many posts each subject needs (like a school does)
                  and distributes classes to posts, balancing hours and keeping each post on few levels
The result is a 'plan' dict, the same shape as an imported school matrix:
  assignment (Teacher, Post, Class, Subject, Hours), teachers, classes, remedial {teacher: hours}
"""
import math
import pandas as pd
from ortools.sat.python import cp_model

from engine import SchoolDataLoader, SchedulerConfig, SchoolSchedulerEngine
from assignment_matrix import CODE_TO_ARABIC, _class_key

EMPTY_TEACHERS = pd.DataFrame(columns=["Teacher_ID", "Qualified_Subjects", "Max_Weekly_Hours", "Requires_Reception"])


def make_loader(data_frames):
    dfs = dict(data_frames)
    dfs.setdefault("teachers", EMPTY_TEACHERS)
    return SchoolDataLoader(dfs)


def required_hours(loader):
    """Class × subject weekly hours, computed with the engine's own rules (curriculum + split rules)."""
    eng = SchoolSchedulerEngine(loader, SchedulerConfig())
    rows = []
    for _, c in loader.df_classes.iterrows():
        for s in loader.df_subjects[loader.df_subjects["Level"] == c["Level"]]["Subject_Code"]:
            h = eng._calculate_required_hours(c["Level"], s)
            if h > 0:
                rows.append({"Class": c["Class_ID"], "Level": c["Level"], "Subject": s, "Hours": int(h)})
    return pd.DataFrame(rows)


def post_label(subject, n):
    return f"{CODE_TO_ARABIC.get(subject, subject)}{n}"


# ------------------------------------------------------------------ mode 1: from staff
def plan_from_staff(loader):
    eng = SchoolSchedulerEngine(loader, SchedulerConfig())
    eng._generate_lessons_and_assignments()
    req = required_hours(loader)
    a = eng.assignment.merge(req[["Class", "Subject", "Hours"]], on=["Class", "Subject"], how="left")
    a["Hours"] = a["Hours"].fillna(0).astype(int)
    # post label per (teacher, subject)
    labels, counters = {}, {}
    for t, s in sorted(set(zip(a["Teacher"], a["Subject"]))):
        counters[s] = counters.get(s, 0) + 1
        labels[(t, s)] = post_label(s, counters[s])
    a["Post"] = [labels[(t, s)] for t, s in zip(a["Teacher"], a["Subject"])]
    maxh = dict(zip(loader.df_teachers["Teacher_ID"], loader.df_teachers["Max_Weekly_Hours"]))
    return finalize(a, remedial={}, max_hours={t: int(maxh.get(t, 0)) for t in a["Teacher"]})


# ------------------------------------------------------------------ mode 2: auto-create posts
def plan_auto_posts(loader, max_hours_default=20, max_hours_by_subject=None, remedial_by_subject=None,
                    time_limit=10):
    """For each subject: #posts = ceil(total hours / (max hours − remedial)), then a small CP-SAT
    assigns each class to a post: load ≤ capacity, few levels per post, balanced loads."""
    max_hours_by_subject = max_hours_by_subject or {}
    remedial_by_subject = remedial_by_subject or {}
    req = required_hours(loader)
    rows, remedial, max_hours, notes = [], {}, {}, []
    for subj, g in req.groupby("Subject"):
        mx = int(max_hours_by_subject.get(subj, max_hours_default))
        rem = int(remedial_by_subject.get(subj, 0))
        cap = mx - rem
        if cap <= 0 or g["Hours"].max() > cap:
            notes.append(("w_post_small", {"s": subj, "h": int(g['Hours'].max()), "c": cap}))
            cap = max(cap, int(g["Hours"].max()))
        # pedagogical windows: if a class needs this subject on every open day, one teacher cannot
        # hold more classes than the subject has usable slots on its most restricted open day
        day_slots = _subject_day_slots(loader, subj)
        open_slots = [n for n in day_slots if n > 0]
        max_cls = None
        if open_slots and g["Hours"].min() >= len(open_slots):
            max_cls = min(open_slots)
        n_posts = max(1, math.ceil(g["Hours"].sum() / cap), math.ceil(len(g) / max_cls) if max_cls else 1)
        sol = None
        for attempt in range(6):
            sol = _pack(g.reset_index(drop=True), n_posts, cap, time_limit, max_cls)
            if sol is not None:
                break
            n_posts += 1
        for idx, p in sol.items():
            r = g.iloc[idx]
            label = post_label(subj, p + 1)
            rows.append({"Teacher": label, "Post": label, "Class": r["Class"], "Subject": subj, "Hours": int(r["Hours"])})
            remedial[label] = rem
            max_hours[label] = mx
    plan = finalize(pd.DataFrame(rows), remedial={k: v for k, v in remedial.items() if v}, max_hours=max_hours)
    plan["notes"] = notes
    return plan


def _subject_day_slots(loader, subj, days=5, slots=7):
    """Usable slots per day for a subject (Tuesday afternoon off + pedagogical windows)."""
    ins = loader.df_inspections
    out = []
    for d in range(days):
        free = set(range(4) if d == 2 else range(slots))
        for _, r in ins[(ins["Subject_Code"] == subj) & (ins["Day_Index"] == d)].iterrows():
            free -= {int(b) for b in str(r["Blocked_Slots"]).split(";") if str(b).strip()}
        out.append(len(free))
    return out


def _pack(g, n_posts, cap, time_limit, max_cls=None):
    m = cp_model.CpModel()
    C, P = range(len(g)), range(n_posts)
    levels = sorted(g["Level"].unique())
    x = {(c, p): m.NewBoolVar(f"x{c}_{p}") for c in C for p in P}
    y = {(p, l): m.NewBoolVar(f"y{p}_{l}") for p in P for l in levels}
    for c in C:
        m.AddExactlyOne(x[c, p] for p in P)
    loads = []
    for p in P:
        load = sum(int(g.loc[c, "Hours"]) * x[c, p] for c in C)
        m.Add(load <= cap)
        if max_cls:
            m.Add(sum(x[c, p] for c in C) <= max_cls)
        loads.append(load)
        for c in C:
            m.AddImplication(x[c, p], y[p, g.loc[c, "Level"]])
    hi, lo = m.NewIntVar(0, cap, "hi"), m.NewIntVar(0, cap, "lo")
    for ld in loads:
        m.Add(hi >= ld); m.Add(lo <= ld)
    for p in range(n_posts - 1):                       # symmetry breaking: post loads descending
        m.Add(loads[p] >= loads[p + 1])
    m.Minimize(10 * sum(y.values()) + (hi - lo))
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = time_limit; s.parameters.num_workers = 8
    if s.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return {c: next(p for p in P if s.Value(x[c, p])) for c in C}


# ------------------------------------------------------------------ common
def finalize(assign, remedial=None, max_hours=None, reception=None):
    """Build teachers / classes tables from an assignment (Teacher, Post, Class, Subject, Hours)."""
    remedial = remedial or {}
    max_hours = max_hours or {}
    reception = reception or {}
    a = assign.copy().reset_index(drop=True)
    a["Hours"] = a["Hours"].astype(int)
    load = a.groupby("Teacher")["Hours"].sum()
    teachers = pd.DataFrame({
        "Teacher_ID": load.index,
        "Qualified_Subjects": [";".join(sorted(set(a[a.Teacher == t]["Subject"]))) for t in load.index],
        # the engine only needs this as information once the assignment is fixed
        "Max_Weekly_Hours": [max(int(max_hours.get(t, 0)), int(load[t] + remedial.get(t, 0))) for t in load.index],
        "Requires_Reception": [bool(reception.get(t, True)) for t in load.index],   # reception hour: yes by default
    })
    classes = pd.DataFrame({"Class_ID": sorted(a["Class"].unique(), key=_class_key)})
    classes["Level"] = classes["Class_ID"].str.extract(r"^(\d+AM)")[0]
    return {"assignment": a, "teachers": teachers, "classes": classes, "remedial": dict(remedial),
            "max_hours": dict(max_hours), "warnings": [], "notes": []}


def load_table(plan):
    """One row per post: subject, teacher, hours, remedial, total, max, #levels, classes."""
    a = plan["assignment"]
    rows = []
    for (post, t), g in a.groupby(["Post", "Teacher"], sort=False):
        rem = int(plan["remedial"].get(t, 0))
        mx = int(plan.get("max_hours", {}).get(t, 0) or 0)
        tot = int(g["Hours"].sum()) + rem
        rows.append({"Post": post, "Teacher": t, "Subject": g["Subject"].iloc[0], "Hours": int(g["Hours"].sum()),
                     "Remedial": rem, "Total": tot, "Max": mx or None,
                     "Status": "⛔ over max" if mx and tot > mx else "✅",
                     "Levels": ", ".join(sorted(set(c[:3] for c in g["Class"]))),
                     "Classes": ", ".join(sorted(g["Class"], key=_class_key))})
    order = {k: i for i, k in enumerate(CODE_TO_ARABIC)}
    df = pd.DataFrame(rows)
    return df.sort_values(["Subject", "Post"], key=lambda s: s.map(order).fillna(99) if s.name == "Subject" else s) \
             .reset_index(drop=True)


def reassign(plan, class_id, subject, new_post):
    """Move one class/subject to another post (existing or new)."""
    a = plan["assignment"].copy()
    post_teacher = dict(zip(a["Post"], a["Teacher"]))
    mask = (a["Class"] == class_id) & (a["Subject"] == subject)
    a.loc[mask, "Post"] = new_post
    a.loc[mask, "Teacher"] = post_teacher.get(new_post, new_post)
    out = finalize(a, plan["remedial"], plan.get("max_hours"))
    out["warnings"], out["notes"] = plan.get("warnings", []), plan.get("notes", [])
    out["class_hours"] = plan.get("class_hours", {})
    return out


def rename_teachers(plan, mapping):
    """mapping: old Teacher -> new name (fills the اللقب و الاسم row)."""
    mapping = {k: v for k, v in mapping.items() if v and v != k}
    if not mapping:
        return plan
    a = plan["assignment"].copy()
    a["Teacher"] = a["Teacher"].replace(mapping)
    ren = lambda d: {mapping.get(k, k): v for k, v in (d or {}).items()}
    out = finalize(a, ren(plan["remedial"]), ren(plan.get("max_hours")))
    out["warnings"], out["notes"] = plan.get("warnings", []), plan.get("notes", [])
    out["class_hours"] = plan.get("class_hours", {})
    return out
