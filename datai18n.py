"""Bilingual data files.

Internally the engine uses canonical columns / codes (Class_ID, Level=1AM, Subject_Code=MATH, Day_Index=0,
Blocked_Slots 0-based …).  For people, every file can be written and read in English or Arabic:

    to_local(df, kind, lang)   canonical  -> labelled table (headers + values translated, hours 1-based)
    from_local(df)             any of: canonical / English labels / Arabic labels -> canonical

A file is recognised as "localised" when its headers are labels (not canonical names); only then are
day names and 1-based hour numbers converted back.
"""
import io
import re
import zipfile

import pandas as pd

import i18n
from assignment_matrix import normalize, CODE_TO_ARABIC, class_to_id

# canonical column -> (English label, Arabic label)
COLS = {
    "Class_ID": ("Class", "الفوج"), "Level": ("Level", "المستوى"),
    "Subject_Code": ("Subject", "المادة"), "Hrs_Cours": ("Course hours", "ساعات الدرس"),
    "Hrs_TD": ("Practice hours (TD)", "ساعات الأعمال الموجهة"), "Hrs_TP": ("Lab hours (TP)", "ساعات الأعمال التطبيقية"),
    "Hrs_Practice": ("Sport/practice hours", "ساعات التطبيق"), "Required_Room_Type": ("Room type", "نوع القاعة"),
    "Day_Index": ("Day", "اليوم"), "Blocked_Slots": ("Blocked hours", "الساعات المحجوزة"),
    "Description": ("Description", "الوصف"), "Room_Type": ("Room type", "نوع القاعة"), "Capacity": ("Count", "العدد"),
    "Rule_ID": ("Rule", "القاعدة"), "Primary_Subject": ("Subject A", "المادة أ"), "Primary_Type": ("Type A", "النوع أ"),
    "Primary_Hours": ("Hours A", "ساعات أ"), "Secondary_Subject": ("Subject B", "المادة ب"),
    "Secondary_Type": ("Type B", "النوع ب"), "Secondary_Hours": ("Hours B", "ساعات ب"),
    "Frequency": ("Sessions per week", "الحصص في الأسبوع"), "Teacher_ID": ("Teacher", "الأستاذ"),
    "Qualified_Subjects": ("Subjects", "المواد"), "Max_Weekly_Hours": ("Weekly load", "النصاب الأسبوعي"),
    "Requires_Reception": ("Reception hour", "ساعة الاستقبال"),
    # timetable / occupancy exports
    "Class": ("Class", "الفوج"), "Day": ("Day", "اليوم"), "Slot": ("Hour", "الساعة"), "Subject": ("Subject", "المادة"),
    "Teachers": ("Teachers", "الأساتذة"), "Teacher": ("Teacher", "الأستاذ"), "Classes": ("Classes", "الأفواج"),
    "Room": ("Room", "القاعة"), "RoomType": ("Room type", "نوع القاعة"), "Note": ("Note", "ملاحظة"),
    "RemSubject": ("Remedial subjects", "مواد الاستدراك"),
}
ROOM_TYPES = {"classroom": ("Classroom", "قاعة"), "lab": ("Lab", "مخبر"), "computer_lab": ("IT room", "قاعة إعلام آلي"),
              "gym": ("Sport field", "ملعب")}
KINDS = {"TD": ("Practice (TD)", "أعمال موجهة"), "TP": ("Lab work (TP)", "أعمال تطبيقية")}
YES_NO = {True: ("Yes", "نعم"), False: ("No", "لا")}
SUBJECT_EN = {"ARABIC": "Arabic", "ISLAMIC": "Islamic education", "MATH": "Mathematics", "FRENCH": "French",
              "ENGLISH": "English", "PHYS": "Physics", "PHYSICS": "Physics", "SCIENCE": "Natural science",
              "HISTGEO": "History-Geography", "INFO": "Computer science", "MUSIC": "Music", "ART": "Art",
              "SPORT": "Physical education", "PE": "Physical education", "AMAZIGH": "Amazigh", "REMEDIAL": "Remedial",
              "HIST": "History", "GEO": "Geography", "CIVICS": "Civics", "ART_MUSIC": "Arts", "TECH": "Technology"}
SUBJECT_COLS = {"Subject_Code", "Primary_Subject", "Secondary_Subject", "Qualified_Subjects", "Subject", "RemSubject"}
LEVEL_COLS = {"Level"}
CLASS_COLS = {"Class_ID", "Class", "Classes"}
ROOM_COLS = {"Required_Room_Type", "Room_Type", "RoomType"}
KIND_COLS = {"Primary_Type", "Secondary_Type"}


def _lbl(pair, lang):
    return pair[1] if lang == "ar" else pair[0]


def _subj_name(code, lang):
    if lang == "ar":
        return i18n.SUBJECT_AR.get(code, CODE_TO_ARABIC.get(code, code))
    return SUBJECT_EN.get(code, code)


def _level(l, lang):
    m = re.match(r"^(\d)AM$", str(l))
    if not m:
        return l
    return f"{m.group(1)}م" if lang == "ar" else f"{m.group(1)}AM"


def _class(c, lang):
    return i18n.cls(c) if lang == "ar" else c


def _split(v, sep_re=r"[;+]"):
    return [x.strip() for x in re.split(sep_re, str(v)) if x.strip()]


# ------------------------------------------------------------------ canonical -> localised
def to_local(df, lang=None):
    lang = lang or i18n.LANG
    if df is None:
        return df
    out = df.copy()
    for c in out.columns:
        col = out[c]
        if c in SUBJECT_COLS:
            out[c] = col.map(lambda v: v if pd.isna(v) else ";".join(_subj_name(x, lang) for x in _split(v, r"[;]"))
                             if "+" not in str(v) else i18n.subj(v) if lang == "ar" else v)
        elif c in LEVEL_COLS:
            out[c] = col.map(lambda v: ";".join(_level(x, lang) if x != "ALL" else ("الكل" if lang == "ar" else "ALL")
                                                for x in _split(v, r";")) if not pd.isna(v) else v)
        elif c in CLASS_COLS:
            out[c] = col.map(lambda v: ", ".join(_class(x, lang) for x in _split(v, r"[,;]")) if not pd.isna(v) else v)
        elif c in ROOM_COLS:
            out[c] = col.map(lambda v: _lbl(ROOM_TYPES[v], lang) if v in ROOM_TYPES else v)
        elif c in KIND_COLS:
            out[c] = col.map(lambda v: _lbl(KINDS[v], lang) if v in KINDS else v)
        elif c in ("Day_Index", "Day"):
            out[c] = col.map(lambda v: i18n.DAYS[lang][int(v)] if str(v).lstrip("-").isdigit() and 0 <= int(v) < 5 else v)
        elif c == "Blocked_Slots":
            out[c] = col.map(lambda v: ";".join(str(int(x) + 1) for x in _split(v, r"[;,]") if x.isdigit()))
        elif c == "Slot":
            out[c] = col.map(lambda v: int(v) + 1 if str(v).isdigit() else v)
        elif c == "Requires_Reception":
            out[c] = col.map(lambda v: _lbl(YES_NO[str(v).strip().lower() in ("true", "1")], lang))
    return out.rename(columns={c: _lbl(COLS[c], lang) for c in out.columns if c in COLS})


# ------------------------------------------------------------------ localised -> canonical
def _norm(s):
    return re.sub(r"[\s_\-()/.]", "", normalize(str(s))) if re.search(r"[\u0600-\u06FF]", str(s)) \
        else re.sub(r"[\s_\-()/.]", "", str(s).lower())


DATA_CANON = {"Class_ID", "Level", "Subject_Code", "Hrs_Cours", "Hrs_TD", "Hrs_TP", "Hrs_Practice", "Required_Room_Type",
              "Day_Index", "Blocked_Slots", "Description", "Room_Type", "Capacity", "Rule_ID", "Primary_Subject",
              "Primary_Type", "Primary_Hours", "Secondary_Subject", "Secondary_Type", "Secondary_Hours", "Frequency",
              "Teacher_ID", "Qualified_Subjects", "Max_Weekly_Hours", "Requires_Reception"}
_HEAD = {}
for canon, (en, ar) in COLS.items():
    _HEAD.setdefault(_norm(en), canon); _HEAD.setdefault(_norm(ar), canon)
_CANON_NORM = {_norm(c): c for c in COLS}
PREFERRED = ["ARABIC", "ISLAMIC", "MATH", "FRENCH", "ENGLISH", "PHYS", "SCIENCE", "HISTGEO", "INFO", "MUSIC", "ART",
             "SPORT", "AMAZIGH", "HIST", "GEO", "CIVICS", "ART_MUSIC", "TECH", "REMEDIAL"]
_SUBJ_REV = {}
for code in PREFERRED:                      # the curriculum's codes win when a name has several codes
    for src in (i18n.SUBJECT_AR, CODE_TO_ARABIC, SUBJECT_EN):
        if code in src:
            _SUBJ_REV.setdefault(_norm(src[code]), code)
for code, name in list(i18n.SUBJECT_AR.items()) + list(CODE_TO_ARABIC.items()) + list(SUBJECT_EN.items()):
    _SUBJ_REV.setdefault(_norm(name), code)
_ROOM_REV = {_norm(x): k for k, (en, ar) in ROOM_TYPES.items() for x in (k, en, ar)}
_KIND_REV = {_norm(x): k for k, (en, ar) in KINDS.items() for x in (k, en, ar)}
_DAY_REV = {_norm(d): i for lang in ("en", "ar") for i, d in enumerate(i18n.DAYS[lang])}


def _subj_code(v):
    s = str(v).strip()
    if re.fullmatch(r"[A-Z_]+", s):
        return s
    return _SUBJ_REV.get(_norm(s), s)


def _level_code(v):
    s = str(v).strip()
    if _norm(s) in ("all", "الكل"):
        return "ALL"
    m = re.match(r"^(\d)\s*(?:م|AM|am)$", s)
    return f"{m.group(1)}AM" if m else s


def header_map(columns):
    """-> (rename dict, localised?)"""
    ren, localised = {}, False
    for c in columns:
        n = _norm(c)
        if str(c) in DATA_CANON:
            continue
        if n in _HEAD and _HEAD[n] != c:
            ren[c] = _HEAD[n]; localised = True
        elif n in _CANON_NORM and _CANON_NORM[n] != c:
            ren[c] = _CANON_NORM[n]
    return ren, localised


def from_local(df):
    if df is None or df.empty and not len(df.columns):
        return df
    ren, localised = header_map(df.columns)
    out = df.rename(columns=ren).copy()
    if "Capacity" in out.columns and "Required_Room_Type" in out.columns and "Room_Type" not in out.columns:
        out = out.rename(columns={"Required_Room_Type": "Room_Type"})      # rooms file: same label
    # duplicated targets (e.g. "Room type" in rooms and curriculum) are fine: one per file
    for c in out.columns:
        col = out[c]
        if c in SUBJECT_COLS and c not in ("Subject", "RemSubject"):
            out[c] = col.map(lambda v: v if pd.isna(v) else ";".join(_subj_code(x) for x in _split(v, r"[;،,]")))
        elif c in LEVEL_COLS:
            out[c] = col.map(lambda v: v if pd.isna(v) else ";".join(_level_code(x) for x in _split(v, r"[;،,]")))
        elif c == "Class_ID":
            out[c] = col.map(lambda v: class_to_id(v) or v)
        elif c in ROOM_COLS:
            out[c] = col.map(lambda v: _ROOM_REV.get(_norm(v), v))
        elif c in KIND_COLS:
            out[c] = col.map(lambda v: _KIND_REV.get(_norm(v), v))
        elif c == "Day_Index":
            out[c] = col.map(lambda v: _DAY_REV.get(_norm(v), v))
            out[c] = pd.to_numeric(out[c], errors="coerce")
        elif c == "Blocked_Slots" and localised:
            out[c] = col.map(lambda v: ";".join(str(int(x) - 1) for x in _split(v, r"[;,،]") if x.isdigit()))
        elif c == "Requires_Reception":
            out[c] = col.map(lambda v: str(v).strip().lower() in ("true", "1", "yes", "نعم"))
    return out


def read_table(file):
    """CSV or Excel upload -> canonical DataFrame."""
    name = getattr(file, "name", str(file)).lower()
    if name.endswith((".xlsx", ".xls", ".xlsm")):
        df = pd.read_excel(file)
    else:
        raw = file.read() if hasattr(file, "read") else open(file, "rb").read()
        df = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    return from_local(df)


FILE_NAMES = {"classes": ("classes", "الأفواج"), "subjects": ("curriculum", "المنهاج"), "rooms": ("rooms", "القاعات"),
              "inspections": ("pedagogical_windows", "النوافذ_البيداغوجية"), "rules": ("split_rules", "قواعد_التفويج"),
              "teachers": ("staff", "الأساتذة")}


def to_zip(dfs, lang=None, fmt="csv"):
    """Data files, headers and values in the chosen language (CSV UTF-8 with BOM → opens fine in Excel)."""
    lang = lang or i18n.LANG
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, df in dfs.items():
            if k not in FILE_NAMES or df is None:
                continue
            name = _lbl(FILE_NAMES[k], lang)
            loc = to_local(df, lang)
            if fmt == "xlsx":
                b = io.BytesIO(); loc.to_excel(b, index=False); z.writestr(f"{name}.xlsx", b.getvalue())
            else:
                z.writestr(f"{name}.csv", loc.to_csv(index=False).encode("utf-8-sig"))
    return buf.getvalue()
