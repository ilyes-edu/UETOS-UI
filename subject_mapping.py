"""Suggest a mapping between subject codes used in the school's files (windows, split rules,
assignment grid) and the curriculum codes, including GROUPING (several codes -> one subject,
e.g. HIST + GEO + CIVICS -> HISTGEO)."""
import difflib
import re
import pandas as pd

# well-known synonyms (unknown code -> preferred curriculum codes, first present wins)
SYNONYMS = {
    "PE": ["SPORT", "EPS"], "EPS": ["SPORT", "PE"], "SPORT": ["EPS", "PE"],
    "ART_MUSIC": ["MUSIC", "ART"], "ART": ["ART_MUSIC", "MUSIC"], "MUSIC": ["ART_MUSIC"],
    "CS": ["INFO"], "INFO": ["CS"], "IT": ["INFO", "CS"], "TECH": ["INFO"],
    "SVT": ["SCIENCE"], "SCIENCE": ["SVT"], "NATSCI": ["SCIENCE", "SVT"],
    "PHYSICS": ["PHYS"], "PHYS": ["PHYSICS"],
    "MATHS": ["MATH"], "MATH": ["MATHS"],
    "HG": ["HISTGEO"], "HISTGEO": ["HG"],
    "HIST": ["HISTGEO", "HG"], "GEO": ["HISTGEO", "HG"], "HISTORY": ["HISTGEO", "HG"],
    "GEOGRAPHY": ["HISTGEO", "HG"], "CIVICS": ["HISTGEO", "HG", "CIVIC"], "CIVIC": ["HISTGEO", "HG", "CIVICS"],
    "ISLAM": ["ISLAMIC"], "AMAZIGH": ["TAMAZIGHT"], "TAMAZIGHT": ["AMAZIGH"],
    "ENG": ["ENGLISH"], "FR": ["FRENCH"], "AR": ["ARABIC"],
}
# component words that make a code a part of a combined subject
PARTS = {"HISTGEO": ["HIST", "GEO", "CIVIC", "CIVICS", "HISTORY", "GEOGRAPHY"],
         "HG": ["HIST", "GEO", "CIVIC", "CIVICS"],
         "ART_MUSIC": ["ART", "MUSIC"], "PHYSCHEM": ["PHYS", "CHEM"]}


def _tokens(code):
    return {x for x in re.split(r"[_\-\s/+]+", code.upper()) if x}


def suggest(code, curriculum):
    """-> (target or None, kind, reason)   kind ∈ synonym | group | part | similar | none"""
    code = str(code).strip().upper()
    cur = [c.upper() for c in curriculum]
    if code in cur:
        return code, "same", ""
    for c in SYNONYMS.get(code, []):
        if c in cur:
            kind = "group" if c in PARTS and code in PARTS[c] else "synonym"
            return c, kind, f"{code} ≈ {c}"
    for c, parts in PARTS.items():                       # HIST is a part of HISTGEO
        if c in cur and code in parts:
            return c, "group", f"{code} ⊂ {c}"
    for c in cur:                                        # substring either way (MUSIC in ART_MUSIC)
        if len(c) >= 3 and (c in code or code in c):
            return c, "part", f"{code} ~ {c}"
    tk = _tokens(code)
    best = max(cur, key=lambda c: len(tk & _tokens(c)), default=None)
    if best and tk & _tokens(best):
        return best, "part", f"{code} ~ {best}"
    close = difflib.get_close_matches(code, cur, n=1, cutoff=0.6)
    if close:
        return close[0], "similar", f"{code} ≈ {close[0]}"
    return None, "none", ""


def collect_unknown(data_frames, plan=None):
    """Find subject codes that are not in the curriculum. -> list of (source, code)."""
    if "subjects" not in data_frames:
        return []
    cur = set(data_frames["subjects"]["Subject_Code"].astype(str).str.upper())
    found = []
    ins = data_frames.get("inspections")
    if ins is not None and "Subject_Code" in ins:
        for c in ins["Subject_Code"].astype(str).str.upper().unique():
            if c not in cur:
                found.append(("inspections", c))
    rules = data_frames.get("rules")
    if rules is not None:
        for col in ("Primary_Subject", "Secondary_Subject"):
            if col in rules:
                for v in rules[col].dropna().astype(str):
                    for c in v.upper().split(";"):
                        c = c.strip()
                        if c and c not in cur:
                            found.append(("rules", c))
    tch = data_frames.get("teachers")
    if tch is not None and "Qualified_Subjects" in tch:
        for v in tch["Qualified_Subjects"].dropna().astype(str):
            for c in v.upper().split(";"):
                c = c.strip()
                if c and c not in cur:
                    found.append(("teachers", c))
    if plan is not None:
        for c in plan["assignment"]["Subject"].astype(str).str.upper().unique():
            if c not in cur:
                found.append(("grid", c))
    return list(dict.fromkeys(found))


def suggestion_table(unknown, curriculum):
    rows = []
    for src, code in unknown:
        tgt, kind, why = suggest(code, curriculum)
        rows.append({"Source": src, "Code": code, "Target": tgt or "", "Kind": kind, "Reason": why})
    df = pd.DataFrame(rows, columns=["Source", "Code", "Target", "Kind", "Reason"])
    if len(df):                                           # several codes -> same target = grouping
        n = df[df.Target != ""].groupby(["Source", "Target"])["Code"].transform("count")
        df.loc[n.index[n > 1], "Kind"] = "group"
    return df


# ------------------------------------------------------------------ apply
def _map_list(v, m):
    out = []
    for c in str(v).split(";"):
        c = c.strip()
        c2 = m.get(c.upper(), c)
        if c2 and c2 not in out:
            out.append(c2)
    return ";".join(out)


def apply_to_frames(data_frames, mapping):
    """mapping: {UNKNOWN: TARGET or ''} ('' = drop). Returns a new dict."""
    if not mapping:
        return data_frames
    dfs = dict(data_frames)
    ins = dfs.get("inspections")
    if ins is not None and "Subject_Code" in ins:
        ins = ins.copy()
        ins["Subject_Code"] = ins["Subject_Code"].astype(str).map(lambda c: mapping.get(c.upper(), c))
        ins = ins[ins["Subject_Code"] != ""]
        # grouped codes on the same day -> one row with the union of blocked slots
        agg = (ins.groupby(["Subject_Code", "Day_Index"])["Blocked_Slots"]
               .agg(lambda x: ";".join(str(v) for v in sorted({int(b) for s in x for b in str(s).split(";") if str(b).strip()})))
               .reset_index())
        dfs["inspections"] = agg
    rules = dfs.get("rules")
    if rules is not None:
        rules = rules.copy()
        for col in ("Primary_Subject", "Secondary_Subject"):
            if col in rules:
                rules[col] = rules[col].map(lambda v: _map_list(v, mapping) if pd.notna(v) else v)
        dfs["rules"] = rules
    tch = dfs.get("teachers")
    if tch is not None and "Qualified_Subjects" in tch:
        tch = tch.copy()
        tch["Qualified_Subjects"] = tch["Qualified_Subjects"].map(lambda v: _map_list(v, mapping) if pd.notna(v) else v)
        dfs["teachers"] = tch
    return dfs


def apply_to_assignment(assign, mapping):
    """Remap the grid's subjects; grouped subjects of the same class & teacher are summed."""
    if not mapping:
        return assign, []
    a = assign.copy()
    a["Subject"] = a["Subject"].astype(str).map(lambda c: mapping.get(c.upper(), c))
    a = a[a["Subject"] != ""]
    conflicts = []
    for (c, s), g in a.groupby(["Class", "Subject"]):
        if g["Teacher"].nunique() > 1:
            conflicts.append((c, s, ", ".join(g["Teacher"].unique())))
    a = (a.groupby(["Teacher", "Class", "Subject"], as_index=False)
         .agg(Hours=("Hours", "sum"), Post=("Post", "first")))
    return a[["Teacher", "Post", "Class", "Subject", "Hours"]], conflicts
