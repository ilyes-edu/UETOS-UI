"""Row-level checks of uploaded data files -> [(line, message)] in the interface language.

Line numbers are the ones a person sees in Excel / a text editor: line 1 = header, first data row = line 2.
"""
import re

import pandas as pd

import i18n
from i18n import t
import datai18n as dl

LEVEL_RE = re.compile(r"^\dAM$")
CLASS_RE = re.compile(r"^\dAM\d+$")
ROOM_TYPES = set(dl.ROOM_TYPES)
KNOWN_SUBJECTS = set(dl.PREFERRED) | set(i18n.SUBJECT_AR) | set(dl.SUBJECT_EN)
REQUIRED = {
    "classes": ["Class_ID", "Level"],
    "subjects": ["Level", "Subject_Code", "Hrs_Cours", "Hrs_TD", "Hrs_TP", "Hrs_Practice", "Required_Room_Type"],
    "inspections": ["Subject_Code", "Day_Index", "Blocked_Slots"],
    "rooms": ["Room_Type", "Capacity"],
    "rules": ["Level", "Primary_Subject", "Primary_Type", "Primary_Hours", "Secondary_Subject", "Secondary_Type",
              "Secondary_Hours", "Frequency"],
    "teachers": ["Teacher_ID", "Qualified_Subjects", "Max_Weekly_Hours"],
}

i18n.S.update({
    "v_title": ("⚠️ Problems found in the uploaded files", "⚠️ مشاكل في الملفات المحمّلة"),
    "v_none": ("✅ No problem found in the uploaded files.", "✅ لا توجد مشاكل في الملفات المحمّلة."),
    "v_line": ("line {n}", "السطر {n}"),
    "v_missing_col": ("missing column '{c}'", "العمود «{c}» غير موجود"),
    "v_empty": ("empty value in '{c}'", "قيمة فارغة في «{c}»"),
    "v_bad_level": ("unknown level '{v}' (expected 1AM…4AM or 1م…4م)", "مستوى غير معروف «{v}» (المتوقع 1م…4م)"),
    "v_bad_class": ("class name '{v}' not understood (expected e.g. 1AM3 or 1م3)", "اسم الفوج «{v}» غير مفهوم (مثال: 1م3)"),
    "v_class_level": ("class {c} is not in level {l}", "الفوج {c} لا ينتمي إلى المستوى {l}"),
    "v_dup": ("duplicate of line {n}", "مكرر مع السطر {n}"),
    "v_bad_subject": ("unknown subject '{v}'", "مادة غير معروفة «{v}»"),
    "v_not_in_curr": ("subject '{v}' is not in the curriculum", "المادة «{v}» غير موجودة في المنهاج"),
    "v_bad_number": ("'{c}' must be a whole number ≥ 0 (found '{v}')", "«{c}» يجب أن يكون عددًا صحيحًا ≥ 0 (وُجد «{v}»)"),
    "v_bad_room": ("unknown room type '{v}'", "نوع قاعة غير معروف «{v}»"),
    "v_room_missing": ("room type '{v}' has no line in the rooms file", "نوع القاعة «{v}» غير موجود في ملف القاعات"),
    "v_bad_day": ("unknown day '{v}'", "يوم غير معروف «{v}»"),
    "v_bad_slots": ("hours '{v}' must be numbers between 1 and 7", "الساعات «{v}» يجب أن تكون أرقامًا بين 1 و7"),
    "v_bad_type": ("type '{v}' must be TD or TP", "النوع «{v}» يجب أن يكون أعمالًا موجهة أو تطبيقية"),
    "v_bad_freq": ("sessions per week must be 1 or 2 (found '{v}')", "عدد الحصص يجب أن يكون 1 أو 2 (وُجد «{v}»)"),
    "v_sec_hours": ("{n} subjects B but {m} hour values", "{n} مادة ب مقابل {m} قيمة ساعات"),
    "v_sum_hours": ("hours B add up to {s}, hours A = {p}", "مجموع ساعات ب = {s} وساعات أ = {p}"),
})


def _line(i):
    return int(i) + 2


def _int_ok(v):
    try:
        f = float(str(v).strip())
        return f >= 0 and f == int(f)
    except ValueError:
        return False


def _split(v, sep=r"[;،,]"):
    return [x.strip() for x in re.split(sep, str(v)) if x.strip()]


def check(kind, df, frames=None, localised=False):
    """df: already converted by datai18n.from_local.  frames: the other files (for cross checks)."""
    frames = frames or {}
    out = []
    cols = set(df.columns)
    for c in REQUIRED.get(kind, []):
        if c not in cols:
            out.append((1, t("v_missing_col", c=dl._lbl(dl.COLS.get(c, (c, c)), i18n.LANG))))
    if out:
        return out
    lab = lambda c: dl._lbl(dl.COLS.get(c, (c, c)), i18n.LANG)
    curr = set(frames["subjects"]["Subject_Code"].astype(str)) if frames.get("subjects") is not None else None
    room_file = set(frames["rooms"]["Room_Type"].astype(str)) if frames.get("rooms") is not None else None
    seen = {}

    def req(i, r, c):
        v = r.get(c)
        if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
            out.append((_line(i), t("v_empty", c=lab(c)))); return None
        return str(v).strip()

    def subj_ok(i, v, need_curr=True):
        if v not in KNOWN_SUBJECTS and not re.fullmatch(r"[A-Z_]+", v):
            out.append((_line(i), t("v_bad_subject", v=v))); return
        if need_curr and curr is not None and kind != "subjects" and v not in curr:
            out.append((_line(i), t("v_not_in_curr", v=i18n.subj(v))))

    for i, r in df.iterrows():
        r = r.to_dict()
        if kind == "classes":
            c, l = req(i, r, "Class_ID"), req(i, r, "Level")
            if c and not CLASS_RE.match(c):
                out.append((_line(i), t("v_bad_class", v=c)))
            if l and not LEVEL_RE.match(l):
                out.append((_line(i), t("v_bad_level", v=l)))
            if c and l and CLASS_RE.match(c) and LEVEL_RE.match(l) and not c.startswith(l):
                out.append((_line(i), t("v_class_level", c=i18n.cls(c), l=l)))
            key = c
        elif kind == "subjects":
            l, s_ = req(i, r, "Level"), req(i, r, "Subject_Code")
            if l and not LEVEL_RE.match(l):
                out.append((_line(i), t("v_bad_level", v=l)))
            if s_:
                subj_ok(i, s_)
            for c in ["Hrs_Cours", "Hrs_TD", "Hrs_TP", "Hrs_Practice"]:
                v = r.get(c)
                if v is not None and str(v).strip() not in ("", "nan") and not _int_ok(v):
                    out.append((_line(i), t("v_bad_number", c=lab(c), v=v)))
            rt = req(i, r, "Required_Room_Type")
            if rt and rt not in ROOM_TYPES:
                out.append((_line(i), t("v_bad_room", v=rt)))
            elif rt and room_file is not None and rt not in room_file:
                out.append((_line(i), t("v_room_missing", v=dl._lbl(dl.ROOM_TYPES[rt], i18n.LANG))))
            key = (l, s_)
        elif kind == "inspections":
            s_ = req(i, r, "Subject_Code")
            if s_:
                subj_ok(i, s_)
            d = r.get("Day_Index")
            if d is None or pd.isna(d) or not _int_ok(d) or not 0 <= int(float(d)) <= 4:
                out.append((_line(i), t("v_bad_day", v=d)))
            sl = req(i, r, "Blocked_Slots")
            if sl:
                parts = _split(sl)
                if not parts or not all(p.lstrip("-").isdigit() and 0 <= int(p) <= 6 for p in parts):
                    shown = ";".join(str(int(p) + 1) if p.lstrip("-").isdigit() else p for p in parts)
                    out.append((_line(i), t("v_bad_slots", v=shown)))
            key = (s_, d)
        elif kind == "rooms":
            rt = req(i, r, "Room_Type")
            if rt and rt not in ROOM_TYPES:
                out.append((_line(i), t("v_bad_room", v=rt)))
            if not _int_ok(r.get("Capacity")):
                out.append((_line(i), t("v_bad_number", c=lab("Capacity"), v=r.get("Capacity"))))
            key = rt
        elif kind == "rules":
            for l in _split(req(i, r, "Level") or ""):
                if l != "ALL" and not LEVEL_RE.match(l):
                    out.append((_line(i), t("v_bad_level", v=l)))
            p = req(i, r, "Primary_Subject")
            if p:
                subj_ok(i, p)
            secs = _split(req(i, r, "Secondary_Subject") or "")
            for s_ in secs:
                subj_ok(i, s_)
            for c in ["Primary_Type", "Secondary_Type"]:
                v = req(i, r, c)
                if v and v not in ("TD", "TP"):
                    out.append((_line(i), t("v_bad_type", v=v)))
            ph = r.get("Primary_Hours")
            if not _int_ok(ph):
                out.append((_line(i), t("v_bad_number", c=lab("Primary_Hours"), v=ph)))
            sh = _split(str(r.get("Secondary_Hours", "")), r"[;،,]")
            if secs and len(sh) not in (1, len(secs)):
                out.append((_line(i), t("v_sec_hours", n=len(secs), m=len(sh))))
            elif len(secs) > 1 and len(sh) == len(secs) and all(_int_ok(x) for x in sh) and _int_ok(ph) \
                    and sum(int(float(x)) for x in sh) != int(float(ph)):
                out.append((_line(i), t("v_sum_hours", s=sum(int(float(x)) for x in sh), p=int(float(ph)))))
            fq = r.get("Frequency")
            if not _int_ok(fq) or int(float(fq)) not in (1, 2):
                out.append((_line(i), t("v_bad_freq", v=fq)))
            key = r.get("Rule_ID") or i
        elif kind == "teachers":
            tid = req(i, r, "Teacher_ID")
            for s_ in _split(req(i, r, "Qualified_Subjects") or ""):
                subj_ok(i, s_)
            if not _int_ok(r.get("Max_Weekly_Hours")):
                out.append((_line(i), t("v_bad_number", c=lab("Max_Weekly_Hours"), v=r.get("Max_Weekly_Hours"))))
            key = tid
        else:
            key = i
        if key is not None and kind not in ("rules",):
            k2 = str(key)
            if k2 in seen:
                out.append((_line(i), t("v_dup", n=seen[k2])))
            else:
                seen[k2] = _line(i)
    return out


def check_all(uploads, frames):
    """uploads: [(file name, kind, df)] -> {file name: [(line, msg)]}"""
    return {name: check(kind, df, frames) for name, kind, df in uploads if kind and kind != "grid"}
