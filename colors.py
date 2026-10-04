"""One fixed colour per subject – shared by the timetable tables and the drag & drop editor."""
import hashlib

# strong colour (cards)  – light tint is derived for table backgrounds
SUBJECT_COLORS = {
    "ARABIC": "#2e7d32", "ISLAMIC": "#00897b", "MATH": "#1565c0", "FRENCH": "#6a1b9a",
    "ENGLISH": "#c2185b", "PHYS": "#e65100", "SCIENCE": "#558b2f", "HIST": "#795548",
    "GEO": "#8d6e63", "CIVICS": "#5d4037", "HIST_GEO": "#795548", "INFO": "#0277bd",
    "ART_MUSIC": "#ad1457", "ART": "#ad1457", "MUSIC": "#9e9d24", "PE": "#f9a825",
    "TAMAZIGHT": "#00695c", "AMAZIGH": "#00695c", "REMEDIAL": "#455a64", "PHYSICS": "#e65100", "HISTGEO": "#795548",
    "SPORT": "#f9a825", "CIVIC": "#5d4037", "RECEPTION": "#a1887f",
}
_EXTRA = ["#4e79a7", "#9c755f", "#b07aa1", "#76b7b2", "#59a14f", "#edc948", "#e15759", "#f28e2b"]


def base(subject):
    s = str(subject)
    for suf in ("_TD/TP", "_Pract/TD", "_TD", "_TP"):
        s = s.replace(suf, "")
    return s.split("+")[0].upper()


def parts(subject):
    import re as _re
    s = _re.sub(r"_G\d+$", "", str(subject))      # group of a divided lesson
    for suf in ("_TD/TP", "_Pract/TD", "_TD", "_TP"):
        s = s.replace(suf, "")
    return [p.upper() for p in s.split("+") if p]


def strong(subject):
    b = base(subject)
    if b in SUBJECT_COLORS:
        return SUBJECT_COLORS[b]
    h = int(hashlib.md5(b.encode()).hexdigest(), 16)
    return _EXTRA[h % len(_EXTRA)]


def light(subject, mix=0.78):
    c = strong(subject).lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(v + (255 - v) * mix) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def css_background(subject):
    """Card background: split lessons get a two-colour gradient."""
    ps = parts(subject)
    if len(ps) > 1:
        return f"linear-gradient(135deg, {strong(ps[0])} 0 50%, {strong(ps[1])} 50% 100%)"
    return strong(subject)
