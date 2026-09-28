"""Step-by-step setup guide: builds a complete school (classes, curriculum, rooms, split rules,
pedagogical windows, teachers and the teacher assignment) from a few simple questions, starting
from the default curriculum.  Nothing has to be uploaded.

Pure logic (build_frames, needed_hours, suggest_counts, make_teachers, auto_assign, to_plan) is
kept separate from the Streamlit pages (render) so it can be tested on its own.
"""
import json
import math
import os

import pandas as pd

import i18n
from i18n import t
import assignment_planner as ap

LEVELS = ["1AM", "2AM", "3AM", "4AM"]
DAYS_N = 5
SLOTS_N = 7
MORNING = [0, 1, 2, 3]

# default curriculum (weekly hours per level) – same as the school example
BASE_CURRICULUM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data", "curriculum.csv")
PROJECT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects", "wizard")

# default coordination windows (day index, morning) with the curriculum codes
DEFAULT_WINDOWS = {"ARABIC": 1, "ISLAMIC": 1, "FRENCH": 2, "ENGLISH": 2, "INFO": 2, "PHYS": 3, "SCIENCE": 3,
                   "MATH": 4, "MUSIC": 4, "ART": 4, "HISTGEO": 0, "SPORT": 0, "AMAZIGH": 2}

DEFAULTS = {
    "levels": {"1AM": 5, "2AM": 5, "3AM": 5, "4AM": 5},
    "amazigh": False, "amazigh_h": 3,
    "arts": "music",                 # none | music | art | both
    "music_h": 1, "art_h": 1,
    "labs": "dedicated", "n_labs": 6,
    "classrooms": 20,
    "info_levels": ["1AM", "2AM"], "it_rooms": 1, "it_mode": "half_lang",   # full | half_lang
    "sport_cap": 2,
    "g_armath": True, "g_physsci": True, "g_lang34": True, "rem_armath": True,
    "base_hours": 20, "mumayaz_less": 2, "rem_hours": 1,
    "windows": dict(DEFAULT_WINDOWS),
}
STEPS = ["levels", "subjects", "grouping", "teachers", "windows", "assign", "finish"]

# ------------------------------------------------------------------ strings (merged into i18n.S)
i18n.S.update({
    "src_wizard": ("🧭 Setup guide (no files)", "🧭 دليل الإعداد (بدون ملفات)"),
    "wz_title": ("🧭 School setup guide", "🧭 دليل إعداد المؤسسة"),
    "wz_intro": ("Answer a few simple questions – the default curriculum does the rest. Every answer can be changed later.",
                 "أجب عن أسئلة بسيطة، والمنهاج الافتراضي يتكفّل بالباقي. يمكن تغيير كل إجابة لاحقًا."),
    "wz_step": ("Step {i} of {n}", "الخطوة {i} من {n}"),
    "wz_s_levels": ("Levels & classes", "المستويات والأفواج"),
    "wz_s_subjects": ("Subjects & rooms", "المواد والقاعات"),
    "wz_s_grouping": ("Groups", "التفويج"),
    "wz_s_teachers": ("Teachers", "الأساتذة"),
    "wz_s_windows": ("Time grid & windows", "الشبكة الزمنية والنوافذ"),
    "wz_s_assign": ("Assignment", "الإسناد"),
    "wz_s_finish": ("Finish", "إنهاء"),
    "wz_prev": ("⬅️ Back", "➡️ السابق"),
    "wz_next": ("Next ➡️", "التالي ⬅️"),
    "wz_reopen": ("🧭 Open the setup guide", "🧭 فتح دليل الإعداد"),
    "wz_restart": ("♻️ Start again from defaults", "♻️ البدء من جديد بالقيم الافتراضية"),
    "wz_project_ok": ("Using the school built with the setup guide ({c} classes, {p} teachers).",
                      "يُستعمل إعداد المؤسسة المُنشأ بالدليل ({c} فوجًا، {p} أستاذًا)."),
    "wz_not_done": ("The setup guide is not finished yet.", "لم يكتمل دليل الإعداد بعد."),
    # step 1
    "wz_q_levels": ("How many classes do you have in each level?", "كم عدد الأفواج في كل مستوى؟"),
    "wz_level": ("Level {l}", "المستوى {l}"),
    "wz_total_classes": ("Total: {n} classes", "المجموع: {n} فوجًا"),
    # step 2
    "wz_q_optional": ("Optional subjects", "المواد الاختيارية"),
    "wz_amazigh": ("Amazigh is taught", "تُدرَّس اللغة الأمازيغية"),
    "wz_hours_week": ("Hours per week", "ساعات في الأسبوع"),
    "wz_arts": ("Arts education", "التربية الفنية"),
    "wz_arts_none": ("None", "لا شيء"), "wz_arts_music": ("Music only", "موسيقى فقط"),
    "wz_arts_art": ("Art (drawing) only", "تربية تشكيلية فقط"), "wz_arts_both": ("Both", "كلاهما"),
    "wz_q_rooms": ("Rooms", "القاعات"),
    "wz_classrooms": ("Normal classrooms", "عدد القاعات العادية"),
    "wz_labs": ("Physics / Science practical work", "الأعمال التطبيقية (فيزياء / علوم)"),
    "wz_labs_dedicated": ("Dedicated labs", "مخابر مخصّصة"),
    "wz_labs_class": ("In normal classrooms", "في القاعات العادية"),
    "wz_n_labs": ("Number of labs", "عدد المخابر"),
    "wz_q_it": ("Computer science (IT)", "الإعلام الآلي"),
    "wz_info_levels": ("Levels that have IT", "المستويات التي تدرس الإعلام الآلي"),
    "wz_it_rooms": ("IT rooms", "عدد قاعات الإعلام الآلي"),
    "wz_it_mode": ("IT room capacity", "سعة قاعة الإعلام الآلي"),
    "wz_it_full": ("Full class", "فوج كامل"),
    "wz_it_half": ("Half class – the other half has French then English", "نصف فوج – النصف الآخر يدرس الفرنسية ثم الإنجليزية"),
    "wz_sport": ("Sport field: how many classes at the same time?", "الملعب: كم فوجًا في نفس الوقت؟"),
    "wz_curr_preview": ("Resulting curriculum (hours per week)", "المنهاج الناتج (ساعات أسبوعية)"),
    # step 3
    "wz_q_grouping": ("How are classes split into groups?", "كيف تُقسَّم الأفواج إلى أفواج فرعية؟"),
    "wz_g_armath": ("Arabic / Math practice (TD): half class each, groups swap",
                    "أعمال موجهة عربية / رياضيات: نصف فوج لكل مادة ثم يتبادلان"),
    "wz_g_armath_h": ("1AM–3AM: 1h, alternating weeks · 4AM: 2h block every week",
                      "1م–3م: ساعة بالتناوب أسبوعيًا · 4م: حصة ساعتين كل أسبوع"),
    "wz_g_physsci": ("Physics / Science practical work (TP): 2h block, groups swap after 1h",
                     "أعمال تطبيقية فيزياء / علوم: حصة ساعتين، يتبادل الفوجان بعد ساعة"),
    "wz_g_lang34": ("French / English practice for levels without IT: half class each",
                    "أعمال موجهة فرنسية / إنجليزية للمستويات بدون إعلام آلي: نصف فوج لكل مادة"),
    "wz_rem_title": ("Remedial work (استدراك)", "حصص الاستدراك"),
    "wz_rem_armath": ("Arabic and Math teachers of the same classes share ONE remedial session",
                      "أستاذا العربية والرياضيات لنفس الأفواج يشتركان في حصة استدراك واحدة"),
    "wz_rules_preview": ("Generated group rules", "قواعد التفويج الناتجة"),
    # step 4
    "wz_q_teachers": ("How many teachers per subject?", "كم أستاذًا في كل مادة؟"),
    "wz_base_hours": ("Full weekly load of a teacher (h)", "النصاب الأسبوعي للأستاذ (سا)"),
    "wz_mumayaz_less": ("A أستاذ مميز teaches fewer hours (h)", "الأستاذ المميز يدرّس ساعات أقل بـ (سا)"),
    "wz_rem_hours": ("Remedial hours per teacher (inside the load)", "ساعات الاستدراك لكل أستاذ (ضمن النصاب)"),
    "wz_c_subject": ("Subject", "المادة"), "wz_c_needed": ("Hours needed", "الساعات المطلوبة"),
    "wz_c_n": ("Teachers", "عدد الأساتذة"), "wz_c_mum": ("of which مميز", "منهم مميز"),
    "wz_c_rem": ("Remedial", "استدراك"), "wz_c_cap": ("Capacity", "الطاقة"),
    "wz_c_balance": ("Balance", "الفارق"),
    "wz_teacher_list": ("Teacher list (edit names, مميز and remedial per teacher)",
                        "قائمة الأساتذة (عدّل الأسماء، المميز والاستدراك لكل أستاذ)"),
    "wz_c_name": ("Teacher", "الأستاذ"), "wz_c_hours": ("Class hours", "ساعات الأفواج"),
    "wz_c_total": ("Total", "المجموع"), "wz_c_classes": ("Classes", "الأفواج"), "wz_c_max": ("Load", "النصاب"),
    "wz_short": ("⚠️ {s}: {h}h are missing – add a teacher, or accept to drop hours in the assignment step.",
                 "⚠️ {s}: تنقص {h} سا – أضف أستاذًا، أو اقبل حذف ساعات في خطوة الإسناد."),
    "wz_regen": ("↻ Rebuild the list from the counts", "↻ إعادة بناء القائمة من الأعداد"),
    # step 5
    "wz_grid_info": ("School week: Sunday–Thursday · 4 morning hours + 3 afternoon hours · Tuesday afternoon off. "
                     "The student grid is filled in this order: mornings, then hours 5–6, then hour 7.",
                     "أسبوع الدراسة: الأحد–الخميس · 4 ساعات صباحًا + 3 مساءً · مساء الثلاثاء عطلة. "
                     "تُملأ شبكة التلاميذ بالترتيب: الصباح، ثم الساعتان 5–6، ثم الساعة 7."),
    "wz_q_windows": ("Coordination windows: which morning is kept free for each subject's teachers?",
                     "النوافذ البيداغوجية: أي صبيحة تبقى حرة لأساتذة كل مادة؟"),
    "wz_no_window": ("No window", "بدون نافذة"),
    # step 6
    "wz_q_assign": ("Drag classes between teachers of the same subject. Totals update live.",
                    "اسحب الأفواج بين أساتذة نفس المادة. المجاميع تتحدث مباشرة."),
    "wz_auto": ("✨ Suggest automatically", "✨ اقتراح تلقائي"),
    "wz_unassigned": ("{n} class/subject pairs have no teacher ({h}h).", "{n} حصة (فوج/مادة) بدون أستاذ ({h} سا)."),
    "wz_bypass": ("Accept: these hours are dropped from the timetable (curriculum bypass)",
                  "أقبل: تُحذف هذه الساعات من الجدول (تجاوز المنهاج)"),
    "wz_add_teacher": ("➕ Go back and add teachers", "➕ الرجوع لإضافة أساتذة"),
    "wz_over": ("⛔ {n} teacher(s) above their load: {x}", "⛔ {n} أستاذ فوق النصاب: {x}"),
    "wz_accept_over": ("Accept the overload (overtime)", "أقبل تجاوز النصاب (ساعات إضافية)"),
    "wz_all_ok": ("✅ Every class has a teacher for every subject, and no teacher is above the load.",
                  "✅ لكل فوج أستاذ في كل مادة، ولا أحد فوق النصاب."),
    "wz_fix_first": ("Resolve the points above to continue.", "عالج النقاط أعلاه للمتابعة."),
    # step 7
    "wz_summary": ("Summary", "الملخص"),
    "wz_sum_line": ("{c} classes · {s} subjects · {p} teachers · {r} group rules · {w} windows",
                    "{c} فوجًا · {s} مادة · {p} أستاذًا · {r} قاعدة تفويج · {w} نافذة"),
    "wz_apply": ("✅ Use this school", "✅ اعتماد هذه المؤسسة"),
    "wz_download": ("⬇️ Download the data files (zip)", "⬇️ تنزيل ملفات المعطيات (zip)"),
    "wz_applied": ("Done! Review the assignment, then continue to ⚙️ Generate.",
                   "تم! راجع الإسناد ثم تابع إلى ⚙️ التوليد."),
    "wz_dropped": ("Dropped hours (bypass): {x}", "ساعات محذوفة (تجاوز): {x}"),
    "a_pool": ("Without teacher", "بدون أستاذ"), "a_drop_hint": ("Drop classes here", "أفلت الأفواج هنا"),
    "a_all": ("All subjects", "كل المواد"),
    "a_clear_t": ("Empty this teacher", "إفراغ هذا الأستاذ"),
    "a_clear_s": ("🧹 Empty this subject", "🧹 إفراغ هذه المادة"),
    "a_clear_a": ("🧹 Empty everything", "🧹 إفراغ الكل"),
    "a_confirm_all": ("Remove every class from every teacher?", "سحب كل الأفواج من كل الأساتذة؟"),
    "a_mode_on": ("✋ Click classes to give them to {t} (click again to remove)", "✋ انقر على الأفواج لإسنادها إلى {t} (نقرة ثانية للسحب)"),
    "a_mode_off": ("Tip: click a teacher, then click classes to assign them – or drag and drop.",
                   "نصيحة: انقر على أستاذ ثم انقر على الأفواج لإسنادها إليه – أو اسحب وأفلت."),
    "a_mode_stop": ("Done", "إنهاء"),
    "a_select_tip": ("Click to select this teacher", "انقر لاختيار هذا الأستاذ"),
})


def _ans(ss):
    if "wz" not in ss:
        ss["wz"] = json.loads(json.dumps(DEFAULTS))
    return ss["wz"]


# ------------------------------------------------------------------ pure logic
def build_frames(a):
    """answers -> dict of data frames in the application's formats (without teachers)."""
    classes = pd.DataFrame([{"Class_ID": f"{l}{i}", "Level": l}
                            for l in LEVELS for i in range(1, int(a["levels"].get(l, 0)) + 1)])
    active = [l for l in LEVELS if int(a["levels"].get(l, 0)) > 0]
    base = pd.read_csv(BASE_CURRICULUM)
    base = base[~base["Subject_Code"].isin(["MUSIC", "ART", "AMAZIGH", "INFO"])]
    extra = []
    for l in LEVELS:
        if a["arts"] in ("music", "both"):
            extra.append((l, "MUSIC", a["music_h"], 0, 0, 0, "classroom"))
        if a["arts"] in ("art", "both"):
            extra.append((l, "ART", a["art_h"], 0, 0, 0, "classroom"))
        if a["amazigh"]:
            extra.append((l, "AMAZIGH", a["amazigh_h"], 0, 0, 0, "classroom"))
        if l in a["info_levels"]:
            extra.append((l, "INFO", 0, 0, 2, 0, "computer_lab"))
    cur = pd.concat([base, pd.DataFrame(extra, columns=base.columns)], ignore_index=True)
    cur = cur[cur["Level"].isin(active)]
    if a["labs"] != "dedicated":
        cur.loc[cur["Subject_Code"].isin(["PHYS", "SCIENCE"]), "Required_Room_Type"] = "classroom"
    order = {s: i for i, s in enumerate(["ARABIC", "AMAZIGH", "ISLAMIC", "MATH", "FRENCH", "ENGLISH", "PHYS", "SCIENCE",
                                         "HISTGEO", "INFO", "MUSIC", "ART", "SPORT"])}
    cur = cur.assign(_o=cur["Subject_Code"].map(order).fillna(99), _l=cur["Level"]).sort_values(["_l", "_o"]) \
             .drop(columns=["_o", "_l"]).reset_index(drop=True)
    for c in ["Hrs_Cours", "Hrs_TD", "Hrs_TP", "Hrs_Practice"]:
        cur[c] = cur[c].astype(int)

    rooms = [("classroom", int(a["classrooms"])), ("gym", int(a["sport_cap"])), ("computer_lab", int(a["it_rooms"]))]
    if a["labs"] == "dedicated":
        rooms.append(("lab", int(a["n_labs"])))
    rooms = pd.DataFrame(rooms, columns=["Room_Type", "Capacity"])

    rules = []
    lv = lambda ls: ";".join(l for l in ls if l in active)
    if a["g_armath"]:
        if lv(["1AM", "2AM", "3AM"]):
            rules.append(("R_FOUJ_01", lv(["1AM", "2AM", "3AM"]), "ARABIC", "TD", 1, "MATH", "TD", 1, 2,
                          "1h per week: group A Arabic / group B Math - groups swap next week"))
        if lv(["4AM"]):
            rules.append(("R_FOUJ_02", "4AM", "ARABIC", "TD", 1, "MATH", "TD", 1, 1,
                          "Every week: 2h block - groups swap after the first hour"))
    if a["g_physsci"]:
        rules.append(("R_FOUJ_03", "ALL", "PHYS", "TP", 1, "SCIENCE", "TP", 1, 1,
                      "Every week: 2h lab block - groups swap after the first hour"))
    info_lv = lv(a["info_levels"])
    if a["it_mode"] == "half_lang" and info_lv:
        rules.append(("R_FOUJ_04", info_lv, "INFO", "TP", 2, "FRENCH;ENGLISH", "TD", "1;1", 2,
                      "2h per week: group A Informatics 2h / group B French 1h then English 1h - groups swap next week"))
    no_info = lv([l for l in LEVELS if l not in a["info_levels"]])
    if a["g_lang34"] and no_info:
        rules.append(("R_FOUJ_05", no_info, "FRENCH", "TD", 1, "ENGLISH", "TD", 1, 2,
                      "1h per week: group A French / group B English - groups swap next week"))
    rules = pd.DataFrame(rules, columns=["Rule_ID", "Level", "Primary_Subject", "Primary_Type", "Primary_Hours",
                                         "Secondary_Subject", "Secondary_Type", "Secondary_Hours", "Frequency",
                                         "Description"])
    subjects = set(cur["Subject_Code"])
    win = [{"Subject_Code": s, "Day_Index": int(d), "Blocked_Slots": ";".join(map(str, MORNING)),
            "Description": f"{s} coordination"} for s, d in a["windows"].items()
           if s in subjects and d is not None and int(d) >= 0]
    windows = pd.DataFrame(win, columns=["Subject_Code", "Day_Index", "Blocked_Slots", "Description"])
    return {"classes": classes, "subjects": cur, "rooms": rooms, "rules": rules, "inspections": windows}


_REQ_CACHE = {}


def needed_hours(frames):
    """Class × subject teacher hours (engine rules), one row per pair (memoised: it runs on every click)."""
    key = "|".join(frames[k].to_csv(index=False) for k in ("classes", "subjects", "rules"))
    if key not in _REQ_CACHE:
        if len(_REQ_CACHE) > 20:
            _REQ_CACHE.clear()
        _REQ_CACHE[key] = ap.required_hours(ap.make_loader(frames))
    return _REQ_CACHE[key].copy()


def suggest_counts(req, a, prev=None):
    """Per subject: hours needed, teachers suggested (keeps the manager's previous choices)."""
    prev = {r["Subject"]: r for r in (prev or [])}
    rows = []
    for s, h in req.groupby("Subject")["Hours"].sum().items():
        rem = a["rem_hours"] if s in ("ARABIC", "MATH", "FRENCH") else 0
        p = prev.get(s)
        n = int(p["n"]) if p else _min_teachers(req[req["Subject"] == s], a["base_hours"] - rem)
        rows.append({"Subject": s, "Needed": int(h), "n": n, "mum": int(p["mum"]) if p else 0,
                     "rem": bool(p["rem"]) if p else bool(rem)})
    return rows


def _min_teachers(g, cap):
    """Smallest number of teachers (load `cap`) that can hold every class of the subject (classes are not split)."""
    hrs = sorted(g["Hours"].astype(int), reverse=True)
    n = max(1, math.ceil(sum(hrs) / cap))
    while n < len(hrs):
        bins = [0] * n                      # first-fit decreasing, then exact check if it fails
        if all(_place(bins, h, cap) for h in hrs):
            return n
        fake = [{"Name": str(k), "Subject": "X", "Mumayaz": False, "Remedial": False} for k in range(n)]
        gg = g.assign(Subject="X")
        if all(auto_assign(gg, fake, {"base_hours": cap, "mumayaz_less": 0, "rem_hours": 0}, 2).values()):
            return n
        n += 1
    return n


def _place(bins, h, cap):
    for k, b in enumerate(bins):
        if b + h <= cap:
            bins[k] += h
            return True
    return False


def make_teachers(counts, a):
    rows = []
    for r in counts:
        for k in range(1, int(r["n"]) + 1):
            rows.append({"Name": ap.post_label(r["Subject"], k), "Subject": r["Subject"],
                         "Mumayaz": k <= int(r["mum"]), "Remedial": bool(r["rem"])})
    return rows


def load_of(tr, a):
    """Teaching capacity (hours of classes) of one teacher row."""
    full = int(a["base_hours"]) - (int(a["mumayaz_less"]) if tr["Mumayaz"] else 0)
    return full, full - (int(a["rem_hours"]) if tr["Remedial"] else 0)


def capacity_by_subject(teachers, a):
    cap = {}
    for tr in teachers:
        cap[tr["Subject"]] = cap.get(tr["Subject"], 0) + load_of(tr, a)[1]
    return cap


def auto_assign(req, teachers, a, time_limit=3):
    """Per subject, a small CP-SAT: assign as many hours as possible within each teacher's load, then keep
    each teacher on few levels, then balance.  Returns {(class, subject): teacher name or None}."""
    from ortools.sat.python import cp_model
    out = {}
    for s, g in req.groupby("Subject"):
        ts = [tr for tr in teachers if tr["Subject"] == s]
        items = sorted(g.itertuples(), key=lambda r: (r.Level, int(r.Class[3:])))
        if not ts:
            out.update({(r.Class, s): None for r in items}); continue
        m = cp_model.CpModel()
        x = {(i, p): m.NewBoolVar("") for i in range(len(items)) for p in range(len(ts))}
        for i in range(len(items)):
            m.Add(sum(x[i, p] for p in range(len(ts))) <= 1)
        levels = sorted({r.Level for r in items})
        y = {(p, l): m.NewBoolVar("") for p in range(len(ts)) for l in levels}
        for p, tr in enumerate(ts):
            m.Add(sum(x[i, p] * r.Hours for i, r in enumerate(items)) <= load_of(tr, a)[1])
            for i, r in enumerate(items):
                m.AddImplication(x[i, p], y[p, r.Level])
        done = sum(x[i, p] * r.Hours for i, r in enumerate(items) for p in range(len(ts)))
        m.Maximize(done * 1000 - sum(y.values()) * 10)
        sv = cp_model.CpSolver(); sv.parameters.max_time_in_seconds = time_limit; sv.parameters.num_workers = 2
        st_ = sv.Solve(m)
        for i, r in enumerate(items):
            who = None
            if st_ in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                who = next((ts[p]["Name"] for p in range(len(ts)) if sv.Value(x[i, p])), None)
            out[(r.Class, s)] = who
    return out


def status(req, assign, teachers, a):
    hours = {(r.Class, r.Subject): int(r.Hours) for r in req.itertuples()}
    un = [(k, h) for k, h in hours.items() if not assign.get(k)]
    tot = {}
    for k, n in assign.items():
        if n:
            tot[n] = tot.get(n, 0) + hours.get(k, 0)
    over = [(tr["Name"], tot.get(tr["Name"], 0), load_of(tr, a)[1]) for tr in teachers
            if tot.get(tr["Name"], 0) > load_of(tr, a)[1]]
    return un, over, tot


def to_plan(req, assign, teachers, a):
    hours = {(r.Class, r.Subject): int(r.Hours) for r in req.itertuples()}
    rows = [{"Teacher": n, "Post": n, "Class": c, "Subject": s, "Hours": hours[(c, s)]}
            for (c, s), n in assign.items() if n and (c, s) in hours]
    by = {tr["Name"]: tr for tr in teachers}
    used = {r["Teacher"] for r in rows}
    rem = {n: int(a["rem_hours"]) for n in used if by[n]["Remedial"] and int(a["rem_hours"]) > 0}
    mx = {n: load_of(by[n], a)[0] for n in used}
    plan = ap.finalize(pd.DataFrame(rows), remedial=rem, max_hours=mx)
    plan["mumayaz"] = [n for n in used if by[n]["Mumayaz"]]
    return plan


def save_project(frames, plan, a, teachers, db, ws):
    db.save_project(ws, {"frames": {k: frames[k].to_csv(index=False) for k in FRAME_KEYS},
                         "assignment": plan["assignment"].to_csv(index=False),
                         "answers": a, "teachers": teachers, "remedial": plan["remedial"],
                         "max_hours": plan["max_hours"]})


FRAME_KEYS = ["classes", "subjects", "rooms", "rules", "inspections"]


def load_project(db, ws):
    import io
    meta, stamp = db.load_project(ws)
    if not meta:
        return None
    frames = {k: pd.read_csv(io.StringIO(meta["frames"][k])) for k in FRAME_KEYS}
    plan = ap.finalize(pd.read_csv(io.StringIO(meta["assignment"])), remedial=meta["remedial"],
                       max_hours=meta["max_hours"])
    return {"frames": frames, "plan": plan, "answers": meta["answers"], "teachers": meta["teachers"], "stamp": stamp}


# ------------------------------------------------------------------ Streamlit pages
def render(st, dnd_assign, db=None, ws="demo"):
    """Draw the guide in the main area.  Returns True when the manager applied the result."""
    ss = st.session_state
    a = _ans(ss)
    step = ss.setdefault("wz_step", 0)
    st.subheader(t("wz_title"))
    st.caption(t("wz_intro"))
    labels = [t("wz_s_" + s) for s in STEPS]
    st.progress((step + 1) / len(STEPS), text=t("wz_step", i=step + 1, n=len(STEPS)) + " · " + labels[step])
    cols = st.columns(len(STEPS))
    for i, (c, lab) in enumerate(zip(cols, labels)):
        if c.button(("● " if i == step else "") + f"{i + 1}. {lab}", key=f"wz_nav{i}", width="stretch",
                    type="primary" if i == step else "secondary"):
            ss["wz_step"] = i; st.rerun()
    st.divider()

    frames = build_frames(a)
    can_next = True
    name = STEPS[step]
    if name == "levels":
        _step_levels(st, a)
    elif name == "subjects":
        _step_subjects(st, a, frames)
    elif name == "grouping":
        _step_grouping(st, a, frames)
    elif name == "teachers":
        can_next = _step_teachers(st, ss, a, frames)
    elif name == "windows":
        _step_windows(st, a, frames)
    elif name == "assign":
        can_next = _step_assign(st, ss, a, frames, dnd_assign)
    else:
        return _step_finish(st, ss, a, frames, db, ws)

    st.divider()
    b1, _, b2 = st.columns([1, 3, 1])
    if step > 0 and b1.button(t("wz_prev"), key="wz_prev", width="stretch"):
        ss["wz_step"] = step - 1; st.rerun()
    if b2.button(t("wz_next"), key="wz_next", type="primary", width="stretch", disabled=not can_next):
        ss["wz_step"] = step + 1; st.rerun()
    return False


def _step_levels(st, a):
    st.subheader(t("wz_q_levels"))
    cols = st.columns(4)
    for c, l in zip(cols, LEVELS):
        a["levels"][l] = int(c.number_input(t("wz_level", l=(l[0] + "م") if i18n.is_ar() else l), 0, 15,
                                            int(a["levels"].get(l, 0)), key=f"wz_lv_{l}"))
    st.info(t("wz_total_classes", n=sum(a["levels"].values())))


def _step_subjects(st, a, frames):
    st.subheader(t("wz_q_optional"))
    c1, c2 = st.columns(2)
    a["amazigh"] = c1.checkbox(t("wz_amazigh"), a["amazigh"], key="wz_amz")
    if a["amazigh"]:
        a["amazigh_h"] = int(c1.number_input(t("wz_hours_week"), 1, 5, int(a["amazigh_h"]), key="wz_amz_h"))
    opts = ["none", "music", "art", "both"]
    a["arts"] = c2.radio(t("wz_arts"), opts, opts.index(a["arts"]), key="wz_arts", horizontal=True,
                         format_func=lambda x: t("wz_arts_" + x))
    if a["arts"] in ("music", "both"):
        a["music_h"] = int(c2.number_input(i18n.subj("MUSIC") + " – " + t("wz_hours_week"), 1, 3, int(a["music_h"]), key="wz_mus_h"))
    if a["arts"] in ("art", "both"):
        a["art_h"] = int(c2.number_input(i18n.subj("ART") + " – " + t("wz_hours_week"), 1, 3, int(a["art_h"]), key="wz_art_h"))

    st.subheader(t("wz_q_rooms"))
    c1, c2, c3 = st.columns(3)
    a["classrooms"] = int(c1.number_input(t("wz_classrooms"), 1, 80, int(a["classrooms"]), key="wz_cr"))
    a["labs"] = c2.radio(t("wz_labs"), ["dedicated", "class"], ["dedicated", "class"].index(a["labs"]), key="wz_labs",
                         format_func=lambda x: t("wz_labs_" + x))
    if a["labs"] == "dedicated":
        a["n_labs"] = int(c2.number_input(t("wz_n_labs"), 1, 20, int(a["n_labs"]), key="wz_nlabs"))
    a["sport_cap"] = int(c3.number_input(t("wz_sport"), 1, 10, int(a["sport_cap"]), key="wz_sport"))

    st.subheader(t("wz_q_it"))
    c1, c2, c3 = st.columns(3)
    a["info_levels"] = c1.multiselect(t("wz_info_levels"), LEVELS, [l for l in a["info_levels"] if l in LEVELS], key="wz_infol")
    if a["info_levels"]:
        a["it_rooms"] = int(c2.number_input(t("wz_it_rooms"), 1, 10, int(a["it_rooms"]), key="wz_itr"))
        a["it_mode"] = c3.radio(t("wz_it_mode"), ["full", "half_lang"], ["full", "half_lang"].index(a["it_mode"]),
                                key="wz_itm", format_func=lambda x: t("wz_it_full") if x == "full" else t("wz_it_half"))
    frames = build_frames(a)
    with st.expander(t("wz_curr_preview")):
        cur = frames["subjects"].copy()
        cur["Total"] = cur[["Hrs_Cours", "Hrs_TD", "Hrs_TP", "Hrs_Practice"]].sum(axis=1)
        piv = cur.pivot_table(index="Subject_Code", columns="Level", values="Total", aggfunc="sum").fillna(0).astype(int)
        piv.index = [i18n.subj(s) for s in piv.index]
        piv.columns = [(c[0] + "م") if i18n.is_ar() else c for c in piv.columns]
        piv.loc["Σ"] = piv.sum()
        st.dataframe(piv, width="stretch")


def _step_grouping(st, a, frames):
    st.subheader(t("wz_q_grouping"))
    a["g_armath"] = st.checkbox(t("wz_g_armath"), a["g_armath"], key="wz_gam", help=t("wz_g_armath_h"))
    a["g_physsci"] = st.checkbox(t("wz_g_physsci"), a["g_physsci"], key="wz_gps")
    no_info = [l for l in LEVELS if l not in a["info_levels"] and a["levels"].get(l, 0)]
    if no_info:
        a["g_lang34"] = st.checkbox(t("wz_g_lang34") + f" ({', '.join(no_info)})", a["g_lang34"], key="wz_gl")
    if a["info_levels"] and a["it_mode"] == "half_lang":
        st.caption("✔ " + t("wz_it_half") + f" ({', '.join(a['info_levels'])})")
    st.subheader(t("wz_rem_title"))
    a["rem_armath"] = st.checkbox(t("wz_rem_armath"), a["rem_armath"], key="wz_rem")
    frames = build_frames(a)
    with st.expander(t("wz_rules_preview"), expanded=True):
        r = frames["rules"]
        if r.empty:
            st.caption("—")
        for _, x in r.iterrows():
            st.markdown(f"- **{x['Level'].replace(';', ', ')}** · {i18n.subj(x['Primary_Subject'])} ↔ "
                        f"{' / '.join(i18n.subj(s) for s in str(x['Secondary_Subject']).split(';'))} — {x['Description']}")


def _step_teachers(st, ss, a, frames):
    req = needed_hours(frames)
    c1, c2, c3 = st.columns(3)
    a["base_hours"] = int(c1.number_input(t("wz_base_hours"), 10, 30, int(a["base_hours"]), key="wz_bh"))
    a["mumayaz_less"] = int(c2.number_input(t("wz_mumayaz_less"), 0, 6, int(a["mumayaz_less"]), key="wz_ml"))
    a["rem_hours"] = int(c3.number_input(t("wz_rem_hours"), 0, 3, int(a["rem_hours"]), key="wz_rh"))
    st.subheader(t("wz_q_teachers"))
    counts = suggest_counts(req, a, ss.get("wz_counts"))
    df = pd.DataFrame(counts)
    df["Name"] = [i18n.subj(s) for s in df["Subject"]]
    ed = st.data_editor(
        df[["Name", "Needed", "n", "mum", "rem"]], hide_index=True, width="stretch", key="wz_counts_ed",
        disabled=["Name", "Needed"],
        column_config={"Name": st.column_config.TextColumn(t("wz_c_subject")),
                       "Needed": st.column_config.NumberColumn(t("wz_c_needed")),
                       "n": st.column_config.NumberColumn(t("wz_c_n"), min_value=0, max_value=30, step=1),
                       "mum": st.column_config.NumberColumn(t("wz_c_mum"), min_value=0, max_value=30, step=1),
                       "rem": st.column_config.CheckboxColumn(t("wz_c_rem"))})
    counts = [{"Subject": s, "Needed": int(r["Needed"]), "n": int(r["n"] or 0), "mum": min(int(r["mum"] or 0), int(r["n"] or 0)),
               "rem": bool(r["rem"])} for s, (_, r) in zip(df["Subject"], ed.iterrows())]
    changed = [(c["Subject"], c["n"], c["mum"], c["rem"]) for c in counts] != \
              [(c["Subject"], c["n"], c["mum"], c["rem"]) for c in ss.get("wz_counts") or []]
    ss["wz_counts"] = counts
    if changed or "wz_teachers" not in ss:
        ss["wz_teachers"] = make_teachers(counts, a)
        ss.pop("wz_assign", None)

    st.subheader(t("wz_teacher_list"))
    tl = pd.DataFrame(ss["wz_teachers"])
    tl["SubjName"] = [i18n.subj(s) for s in tl["Subject"]]
    tl["Max"] = [load_of(r, a)[0] for r in ss["wz_teachers"]]
    ed2 = st.data_editor(tl[["Name", "SubjName", "Mumayaz", "Remedial", "Max"]], hide_index=True, width="stretch",
                         key=f"wz_tl_{hash(tuple((c['Subject'], c['n'], c['mum'], c['rem']) for c in counts))}",
                         disabled=["SubjName", "Max"], height=min(600, 38 + 35 * len(tl)),
                         column_config={"Name": st.column_config.TextColumn(t("wz_c_name")),
                                        "SubjName": st.column_config.TextColumn(t("wz_c_subject")),
                                        "Mumayaz": st.column_config.CheckboxColumn("مميز"),
                                        "Remedial": st.column_config.CheckboxColumn(t("wz_c_rem")),
                                        "Max": st.column_config.NumberColumn(t("wz_c_max"))})
    new = [{"Name": str(r["Name"]).strip() or o["Name"], "Subject": o["Subject"], "Mumayaz": bool(r["Mumayaz"]),
            "Remedial": bool(r["Remedial"])} for o, (_, r) in zip(ss["wz_teachers"], ed2.iterrows())]
    if [x["Name"] for x in new] != [x["Name"] for x in ss["wz_teachers"]] and "wz_assign" in ss:
        ren = {o["Name"]: n["Name"] for o, n in zip(ss["wz_teachers"], new)}
        ss["wz_assign"] = {k: ren.get(v, v) for k, v in ss["wz_assign"].items()}
    ss["wz_teachers"] = new
    names = [x["Name"] for x in new]
    if len(set(names)) != len(names):
        st.error("⛔ " + ", ".join(sorted({n for n in names if names.count(n) > 1})))
        return False
    cap = capacity_by_subject(new, a)
    for c in counts:
        miss = c["Needed"] - cap.get(c["Subject"], 0)
        if miss > 0:
            st.warning(t("wz_short", s=i18n.subj(c["Subject"]), h=miss))
    return True


def _step_windows(st, a, frames):
    st.info(t("wz_grid_info"))
    st.subheader(t("wz_q_windows"))
    subjects = list(dict.fromkeys(frames["subjects"]["Subject_Code"]))
    opts = [-1] + list(range(DAYS_N))
    cols = st.columns(3)
    for i, s in enumerate(subjects):
        cur = a["windows"].get(s, -1)
        cur = -1 if cur is None else int(cur)
        a["windows"][s] = cols[i % 3].selectbox(i18n.subj(s), opts, opts.index(cur), key=f"wz_win_{s}",
                                                format_func=lambda d: t("wz_no_window") if d < 0 else i18n.day(d))


def _payload(req, assign, teachers, a):
    items = [{"cls": r.Class, "label": i18n.cls(r.Class), "subject": r.Subject, "hours": int(r.Hours),
              "teacher": assign.get((r.Class, r.Subject))} for r in req.itertuples()]
    import colors
    subs = list(dict.fromkeys(req["Subject"]))
    return {"teachers": [{"name": tr["Name"], "subject": tr["Subject"], "cap": load_of(tr, a)[1],
                          "full": load_of(tr, a)[0], "mum": tr["Mumayaz"], "rem": tr["Remedial"]} for tr in teachers],
            "items": items,
            "subjects": [{"code": s, "name": i18n.subj(s), "color": colors.strong(s), "light": colors.light(s)} for s in subs],
            "rtl": i18n.is_ar(),
            "i18n": {"h": "سا" if i18n.is_ar() else "h", "pool": t("a_pool"), "clear_t": t("a_clear_t"),
                     "clear_s": t("a_clear_s"), "clear_a": t("a_clear_a"), "confirm_all": t("a_confirm_all"),
                     "mode_on": t("a_mode_on"), "mode_off": t("a_mode_off"), "mode_stop": t("a_mode_stop"),
                     "select_tip": t("a_select_tip"), "drop": t("a_drop_hint"), "all": t("a_all"), "rem": t("wz_c_rem")}}


def _step_assign(st, ss, a, frames, dnd_assign):
    req = needed_hours(frames)
    teachers = ss.get("wz_teachers") or make_teachers(suggest_counts(req, a), a)
    ss["wz_teachers"] = teachers
    names = {tr["Name"] for tr in teachers}
    keys = {(r.Class, r.Subject) for r in req.itertuples()}
    cur = ss.get("wz_assign")
    if cur is None or set(cur) != keys or any(v and v not in names for v in cur.values()):
        cur = auto_assign(req, teachers, a)
    st.subheader(t("wz_q_assign"))
    if st.button(t("wz_auto"), key="wz_auto"):
        cur = auto_assign(req, teachers, a); ss["wz_nonce"] = None
    ss["wz_assign"] = cur
    ev = dnd_assign(data=_payload(req, cur, teachers, a), key="wz_dnd", default=None)
    if ev and ev.get("nonce") != ss.get("wz_nonce"):
        ss["wz_nonce"] = ev.get("nonce")
        for c_, s_, n_ in ev.get("assign", []):
            if (c_, s_) in cur:
                cur[(c_, s_)] = n_ or None
        for m in ev.get("moves", []):
            k = (m["cls"], m["subject"])
            if k in cur:
                cur[k] = m["teacher"] or None
        ss["wz_assign"] = cur
        st.rerun()
    un, over, _ = status(req, cur, teachers, a)
    ok = True
    if un:
        st.warning(t("wz_unassigned", n=len(un), h=sum(h for _, h in un)) + " " +
                   ", ".join(f"{i18n.cls(c)}·{i18n.subj(s)}" for (c, s), _ in un[:12]) + (" …" if len(un) > 12 else ""))
        c1, c2 = st.columns([3, 1])
        a["bypass"] = c1.checkbox(t("wz_bypass"), a.get("bypass", False), key="wz_bypass")
        if c2.button(t("wz_add_teacher"), key="wz_addt"):
            ss["wz_step"] = STEPS.index("teachers"); st.rerun()
        ok &= bool(a["bypass"])
    if over:
        st.error(t("wz_over", n=len(over), x=", ".join(f"{n} ({h}/{c})" for n, h, c in over)))
        a["accept_over"] = st.checkbox(t("wz_accept_over"), a.get("accept_over", False), key="wz_aover")
        ok &= bool(a["accept_over"])
    if not un and not over:
        st.success(t("wz_all_ok"))
    elif not ok:
        st.caption(t("wz_fix_first"))
    return ok


def _step_finish(st, ss, a, frames, db=None, ws="demo"):
    import datai18n as dl
    req = needed_hours(frames)
    teachers = ss.get("wz_teachers") or []
    cur = ss.get("wz_assign") or {}
    if not teachers or not cur:
        st.warning(t("wz_not_done"))
        if st.button(t("wz_prev"), key="wz_prev_f"):
            ss["wz_step"] = STEPS.index("assign"); st.rerun()
        return False
    plan = to_plan(req, cur, teachers, a)
    un, _, _ = status(req, cur, teachers, a)
    st.subheader(t("wz_summary"))
    st.success(t("wz_sum_line", c=len(frames["classes"]), s=frames["subjects"]["Subject_Code"].nunique(),
                 p=len(plan["teachers"]), r=len(frames["rules"]), w=len(frames["inspections"])))
    if un:
        st.caption(t("wz_dropped", x=", ".join(f"{i18n.cls(c)}·{i18n.subj(s)} ({h})" for (c, s), h in un)))
    with st.expander(t("rm_check_title"), expanded=True):
        import rooms as rms
        from engine import SchoolDataLoader, SchedulerConfig, SchoolSchedulerEngine
        fr = dict(frames); fr["teachers"] = plan["teachers"]
        eng = SchoolSchedulerEngine(SchoolDataLoader(fr), SchedulerConfig(), fixed_assignment=plan["assignment"])
        eng._generate_lessons_and_assignments()
        rms.render_check(st, rms.capacity_check(eng.lessons, eng.room_caps()))
    lt = ap.load_table(plan)
    lt["Subject"] = [i18n.subj(s) for s in lt["Subject"]]
    lt["Classes"] = [" ".join(i18n.cls(c.strip()) for c in x.split(",")) for x in lt["Classes"]]
    st.dataframe(lt[["Teacher", "Subject", "Hours", "Remedial", "Total", "Max", "Classes"]].rename(columns={
        "Teacher": t("wz_c_name"), "Subject": t("wz_c_subject"), "Hours": t("wz_c_hours"), "Remedial": t("wz_c_rem"),
        "Total": t("wz_c_total"), "Max": t("wz_c_max"), "Classes": t("wz_c_classes")}), hide_index=True, width="stretch")
    c1, c2, c3 = st.columns(3)
    applied = False
    if c1.button(t("wz_apply"), type="primary", key="wz_apply", width="stretch"):
        save_project(frames, plan, a, teachers, db, ws)
        ss["wz_open"] = False
        applied = True
    files = dict(frames)
    files["teachers"] = plan["teachers"]
    c2.download_button(t("wz_download"), dl.to_zip(files), "school_setup.zip", "application/zip", key="wz_zip",
                       width="stretch")
    if c3.button(t("wz_prev"), key="wz_prev_f2", width="stretch"):
        ss["wz_step"] = STEPS.index("assign"); st.rerun()
    return applied
