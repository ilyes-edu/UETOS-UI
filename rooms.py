"""Rooms: capacity check before solving, concrete room allocation after solving, occupancy tables.

Model (same as the solver): rooms of a type form a pool per time slot.  Every class has a HOME classroom
(when there are enough classrooms).  While a class is away (sport field, IT room, lab …) its home room is
free and can host a split group (تفويج) or a lesson that falls back from a missing lab.
"""
import re
from collections import Counter, defaultdict

import pandas as pd

import i18n
from i18n import t

SUFFIX_RE = re.compile(r"_(TD/TP|TD|TP|Pract/TD)$")
ORDER = ["classroom", "lab", "computer_lab", "gym"]
FALLBACK = {"lab": "classroom"}

i18n.S.update({
    "rt_classroom": ("Classroom", "قاعة"), "rt_lab": ("Lab", "مخبر"), "rt_computer_lab": ("IT room", "قاعة إعلام آلي"),
    "rt_gym": ("Sport field", "ملعب"),
    "rm_view": ("🏫 Rooms", "🏫 القاعات"),
    "rm_title": ("Room occupancy", "شغل القاعات"),
    "rm_kpi_used": ("{rt}: {u} of {a} room-hours used ({p}%) · peak {m}/{c}",
                    "{rt}: {u} من {a} ساعة-قاعة مشغولة ({p}%) · الذروة {m}/{c}"),
    "rm_free_title": ("Free classrooms per hour", "القاعات الشاغرة في كل ساعة"),
    "rm_none": ("⚠️ {n} lesson-hours found no free room", "⚠️ {n} ساعة-حصة بدون قاعة شاغرة"),
    "rm_all_ok": ("✅ Every lesson and group has a room.", "✅ لكل حصة وكل فوج فرعي قاعة."),
    "rm_fallback_n": ("{n} lab hours held in a free classroom", "{n} ساعة أعمال تطبيقية في قاعة عادية شاغرة"),
    "rm_borrowed_n": ("{n} group hours use the home room of a class that is away", "{n} ساعة لفوج فرعي في قاعة فوج غائب"),
    "rm_note_home": ("home room", "قاعة الفوج"), "rm_note_borrow": ("room of {c} (away)", "قاعة {c} (غائب)"),
    "rm_note_spare": ("spare room", "قاعة إضافية"), "rm_note_fb": ("instead of a lab", "بدل المخبر"),
    "rm_note_none": ("no room!", "بدون قاعة!"),
    "rm_check_title": ("Room capacity", "سعة القاعات"),
    "rm_check_line": ("{rt}: needs {d} room-hours per week, {s} available ({p}%)",
                      "{rt}: تحتاج {d} ساعة-قاعة أسبوعيًا، والمتاح {s} ({p}%)"),
    "rm_check_over": ("⛔ Not enough rooms: {x}. Add rooms/labs or reduce split groups.",
                      "⛔ القاعات غير كافية: {x}. أضف قاعات/مخابر أو قلّل التفويج."),
    "rm_check_tight": ("⚠️ Rooms are very tight ({p}% of all usable hours). The solver may fail or take very long. "
                       "Adding {n} classroom(s) (or labs) brings it under 85%.",
                       "⚠️ القاعات ضيقة جدًا ({p}% من كل الساعات المتاحة). قد يفشل الحل أو يطول كثيرًا. "
                       "إضافة {n} قاعة (أو مخابر) تنزل بها تحت 85%."),
    "rm_check_ok": ("✅ Room capacity is sufficient ({p}% of classroom-type hours used).",
                    "✅ سعة القاعات كافية (استعمال {p}% من ساعات القاعات)."),
    "rm_check_expl": ("Freed rooms are already counted: a class at sport, in the IT room or in a lab leaves its "
                      "classroom free for a split group.",
                      "القاعات المحرَّرة محسوبة: الفوج الذي في الملعب أو قاعة الإعلام الآلي أو المخبر يترك قاعته "
                      "شاغرة لفوج فرعي."),
    "rm_room": ("Room", "القاعة"),
})


def rt_label(rt):
    return t("rt_" + rt) if ("rt_" + rt) in i18n.S else rt


def room_names(caps):
    """{type: [names]} – e.g. قاعة 1 … ; a sport field with capacity n is one field holding n classes."""
    out = {}
    for rt in sorted(caps, key=lambda r: ORDER.index(r) if r in ORDER else 9):
        n = int(caps[rt])
        if rt == "gym":
            out[rt] = [f"{rt_label(rt)} ({k + 1})" if n > 1 else rt_label(rt) for k in range(n)]
        else:
            out[rt] = [f"{rt_label(rt)} {k + 1}" for k in range(n)]
    return out


# ------------------------------------------------------------------ before solving
def capacity_check(lessons, caps, usable_slots=32, fallback=FALLBACK):
    """lessons: engine lessons (with 'rooms' and 'duration').  Returns a dict used by render_check."""
    dem = Counter()
    for l in lessons:
        if l.get("remedial"):
            continue
        for rt, n in l["rooms"].items():
            dem[rt] += n * l["duration"]
    lines, over = [], []
    for rt in sorted(set(dem) | set(caps), key=lambda r: ORDER.index(r) if r in ORDER else 9):
        s = int(caps.get(rt, 0)) * usable_slots
        if rt in fallback:        # judged together with its fallback type
            continue
        d = dem[rt] + sum(dem[k] for k, v in fallback.items() if v == rt)
        s += sum(int(caps.get(k, 0)) * usable_slots for k, v in fallback.items() if v == rt)
        lines.append((rt, d, s))
        if d > s:
            over.append(rt)
    main = next((x for x in lines if x[0] == "classroom"), None)
    ratio = main[1] / main[2] if main and main[2] else 0
    need = 0
    if main and ratio > 0.85:
        need = max(0, -(-int(main[1] / 0.85 - main[2]) // usable_slots))
    return {"lines": lines, "over": over, "ratio": ratio, "extra_rooms": need}


def render_check(st, chk):
    for rt, d, s in chk["lines"]:
        st.caption(t("rm_check_line", rt=rt_label(rt) + (" + " + rt_label("lab") if rt == "classroom" else ""),
                     d=d, s=s, p=round(100 * d / s) if s else "∞"))
    if chk["over"]:
        st.error(t("rm_check_over", x=", ".join(rt_label(r) for r in chk["over"])))
    elif chk["ratio"] > 0.85:
        st.warning(t("rm_check_tight", p=round(100 * chk["ratio"]), n=chk["extra_rooms"]))
    else:
        st.success(t("rm_check_ok", p=round(100 * chk["ratio"])))
    st.caption(t("rm_check_expl"))


# ------------------------------------------------------------------ after solving
def _room_type_map(curriculum):
    if curriculum is None:
        return {}
    return {(str(r.Level), str(r.Subject_Code)): str(r.Required_Room_Type) for r in curriculum.itertuples()}


def _demands(row, rtm):
    """Room demands of one schedule row: list of (subject part, teacher, room type, is_main)."""
    cls, subj = str(row.Class), str(row.Subject)
    teachers = [x.strip() for x in str(row.Teachers).split(",")]
    if cls.startswith("REM:"):
        return [("REMEDIAL", " / ".join(teachers), "classroom", False)]   # grouped remediation alternates weekly: 1 room
    base = SUFFIX_RE.sub("", subj)
    parts = base.split("+")
    lvl = cls[:3]
    out = []
    for k, p in enumerate(parts):
        rt = rtm.get((lvl, p), "classroom")
        out.append((p, teachers[k] if k < len(teachers) else teachers[-1], rt, k == 0))
    return out


def allocate(df, curriculum, caps, classes=None, fallback=FALLBACK):
    """df: saved timetable (Class, Day, Slot, Subject, Teachers, Classes).  Returns one row per room use:
    Day, Slot, RoomType, Room, Class, Subject, Teacher, Note, NoteArg."""
    rtm = _room_type_map(curriculum)
    names = room_names(caps)
    real = sorted({c for c in df["Class"].astype(str) if not c.startswith("REM:")},
                  key=lambda c: (c[:3], int(re.sub(r"\D", "", c[3:]) or 0))) if classes is None else list(classes)
    home = {c: names.get("classroom", [])[i] for i, c in enumerate(real) if i < len(names.get("classroom", []))}
    owner = {r: c for c, r in home.items()}
    rows = []
    for (d, s), g in df.groupby(["Day", "Slot"]):
        present = {str(c) for c in g["Class"] if not str(c).startswith("REM:")}
        dem = []
        for r in g.itertuples():
            for p, tc, rt, main in _demands(r, rtm):
                label = str(r.Classes) if str(r.Class).startswith("REM:") else str(r.Class)
                dem.append({"cls": str(r.Class), "label": label, "subj": p, "tc": tc, "rt": rt, "main": main,
                            "fb": False, "rem": str(r.Class).startswith("REM:")})
        # 1. special rooms (lab, IT, field) – overflow of a type with a fallback goes to classrooms
        free = {rt: list(v) for rt, v in names.items()}
        for x in dem:
            if x["rt"] == "classroom":
                continue
            pool = free.get(x["rt"], [])
            if pool:
                x["room"] = pool.pop(0); x["note"] = ""
            elif x["rt"] in fallback:
                x["rt"], x["fb"] = fallback[x["rt"]], True
            else:
                x["room"] = None; x["note"] = "none"
        # 2. main lesson of each class stays in its home room
        cl = free.get("classroom", [])
        for x in dem:
            if x["rt"] == "classroom" and "room" not in x and x["main"] and not x["fb"] and home.get(x["cls"]) in cl:
                cl.remove(home[x["cls"]]); x["room"] = home[x["cls"]]; x["note"] = "home"
        # 3. remediation: a home room of one of its classes first; then groups / fallbacks: rooms of absent classes
        def pick(x):
            if x["rem"]:
                for c in [z.strip() for z in x["label"].split(",")]:
                    if home.get(c) in cl:
                        return home[c]
            away = [r for r in cl if owner.get(r) and owner[r] not in present]
            spare = [r for r in cl if not owner.get(r)]
            for cand in (spare, away, cl):
                if cand:
                    return cand[0]
            return None
        for x in dem:
            if x["rt"] == "classroom" and "room" not in x:
                r = pick(x)
                if r:
                    cl.remove(r); x["room"] = r
                    x["note"] = "fb" if x["fb"] else ("home" if owner.get(r) == x["cls"] else
                                                     ("borrow" if owner.get(r) else "spare"))
                else:
                    x["room"], x["note"] = None, "none"
        for x in dem:
            rows.append({"Day": int(d), "Slot": int(s), "RoomType": x["rt"], "Room": x["room"], "Class": x["label"],
                         "Subject": x["subj"], "Teacher": x["tc"], "Note": x["note"],
                         "NoteArg": owner.get(x["room"], "") if x["note"] == "borrow" else ""})
    return pd.DataFrame(rows, columns=["Day", "Slot", "RoomType", "Room", "Class", "Subject", "Teacher", "Note", "NoteArg"])


def summary(occ, caps, usable_slots=32):
    out = []
    for rt, n in caps.items():
        u = occ[(occ["RoomType"] == rt) & occ["Room"].notna()]
        per = u.groupby(["Day", "Slot"]).size()
        out.append({"rt": rt, "used": len(u), "avail": int(n) * usable_slots, "peak": int(per.max()) if len(per) else 0,
                    "cap": int(n)})
    return {"types": out, "none": int(occ["Room"].isna().sum()), "fallback": int((occ["Note"] == "fb").sum()),
            "borrowed": int((occ["Note"] == "borrow").sum())}


def note_text(r):
    if r.Note == "borrow":
        return t("rm_note_borrow", c=i18n.cls(r.NoteArg))
    return t("rm_note_" + r.Note) if r.Note in ("home", "spare", "fb", "none") else ""


def grid_html(occ, caps, days=5, slots=7, color_light=None, color_strong=None):
    """Rows = rooms, columns = day × slot.  Each cell: class + short subject, colored by subject."""
    names = room_names(caps)
    all_rooms = [r for rt in names for r in names[rt]]
    cell = {(r.Room, r.Day, r.Slot): r for r in occ.itertuples() if r.Room}
    dir_ = "rtl" if i18n.is_ar() else "ltr"
    h = [f'<div style="overflow-x:auto;direction:{dir_}"><table style="border-collapse:collapse;font-size:11px;'
         f'font-family:Segoe UI,Tahoma,sans-serif">']
    h.append(f'<tr><th rowspan=2 style="position:sticky;{"right" if dir_ == "rtl" else "left"}:0;background:#fff;'
             f'padding:3px 6px;border:1px solid #ddd">{t("rm_room")}</th>')
    for d in range(days):
        h.append(f'<th colspan={slots} style="border:1px solid #bbb;background:#f5f5f5;padding:2px">{i18n.day(d)}</th>')
    h.append("</tr><tr>")
    for d in range(days):
        for s in range(slots):
            h.append(f'<th style="border:1px solid #ddd;padding:1px 3px;font-weight:400;color:#666">{s + 1}</th>')
    h.append("</tr>")
    for room in all_rooms:
        h.append(f'<tr><th style="position:sticky;{"right" if dir_ == "rtl" else "left"}:0;background:#fff;'
                 f'white-space:nowrap;padding:2px 6px;border:1px solid #ddd;text-align:start">{room}</th>')
        for d in range(days):
            for s in range(slots):
                off = d == 2 and s >= 4
                x = cell.get((room, d, s))
                bl = "border-inline-start:2px solid #999;" if s == 0 else ""
                if x is None:
                    bg = "repeating-linear-gradient(45deg,#eee,#eee 3px,#fafafa 3px,#fafafa 6px)" if off else "#fff"
                    h.append(f'<td style="border:1px solid #eee;{bl}min-width:46px;height:28px;background:{bg}"></td>')
                    continue
                lab = x.Class if not str(x.Class).startswith("REM") else x.Class
                cls_txt = ", ".join(i18n.cls(c.strip()) for c in str(lab).split(",")[:3])
                mark = {"borrow": " ↪", "fb": " 🔁", "spare": ""}.get(x.Note, "")
                tip = f"{i18n.subj(x.Subject)} · {x.Teacher} · {note_text(x)}"
                bg = color_light(x.Subject) if color_light else "#e3f2fd"
                bd = color_strong(x.Subject) if color_strong else "#1e88e5"
                h.append(f'<td title="{tip}" style="border:1px solid #eee;{bl}min-width:46px;height:28px;background:{bg};'
                         f'border-top:3px solid {bd};text-align:center;line-height:1.1;padding:1px">'
                         f'<b>{cls_txt}</b>{mark}<br><span style="font-size:10px">{i18n.subj_short(x.Subject)}</span></td>')
        h.append("</tr>")
    h.append("</table></div>")
    return "".join(h)


def free_table(occ, caps, days=5, slots=7):
    """Day × slot table of free classrooms (classroom type)."""
    n = int(caps.get("classroom", 0))
    used = occ[(occ["RoomType"] == "classroom") & occ["Room"].notna()].groupby(["Day", "Slot"]).size()
    data = {i18n.day(d): [None if (d == 2 and s >= 4) else n - int(used.get((d, s), 0)) for s in range(slots)]
            for d in range(days)}
    return pd.DataFrame(data, index=[i18n.slot_label(s) for s in range(slots)])
