"""Reading uploaded school files: one zip with everything, or separate CSV / Excel files.

read_uploads(files) -> list of dict(name, kind, df | assign, error)
kind: classes | subjects | rooms | rules | inspections | teachers | assign | None (not recognised)
"""
import io
import os
import re
import zipfile

import datai18n as dl

SIGNATURES = {
    "teachers": {"Teacher_ID", "Qualified_Subjects", "Max_Weekly_Hours"},
    "classes": {"Class_ID", "Level"},
    "subjects": {"Subject_Code", "Hrs_Cours", "Required_Room_Type"},
    "inspections": {"Subject_Code", "Day_Index", "Blocked_Slots"},
    "rooms": {"Room_Type", "Capacity"},
    "rules": {"Primary_Subject", "Secondary_Subject"},
}
FILE_HINTS = {"teachers": "staff", "classes": "classes", "subjects": "curriculum", "inspections": "pedagogical_windows",
              "rooms": "rooms", "rules": "split_rules"}
ASSIGN_NAME = re.compile(r"assign|اسناد|إسناد|الإسناد|توزيع", re.I)
KINDS = ["classes", "subjects", "rooms", "rules", "teachers", "inspections", "assign"]


def detect(df, fname):
    cols = set(df.columns)
    for k, sig in SIGNATURES.items():
        if sig <= cols and not (k == "classes" and "Subject_Code" in cols):
            return k
    base = os.path.splitext(os.path.basename(fname))[0].lower()
    for k, f in FILE_HINTS.items():
        if base == f:
            return k
    return None


def _expand(files):
    """Uploaded objects (zip or single files) -> list of named BytesIO."""
    out = []
    for up in files or []:
        name = getattr(up, "name", "file")
        data = up.getvalue() if hasattr(up, "getvalue") else up.read()
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for zn in z.namelist():
                        if zn.endswith("/") or not zn.lower().endswith((".csv", ".xlsx", ".xls")):
                            continue
                        b = io.BytesIO(z.read(zn)); b.name = os.path.basename(zn)
                        out.append(b)
            except zipfile.BadZipFile as ex:
                out.append(("error", name, str(ex)))
        else:
            b = io.BytesIO(data); b.name = name
            out.append(b)
    return out


def parse_assignment(fileobj, curriculum_codes, known_classes=None):
    from assignment_matrix import parse_assignment_matrix, read_any
    fileobj.seek(0)
    p = parse_assignment_matrix(read_any(fileobj), curriculum_codes, known_classes)
    if p is None or p.get("assignment") is None or not len(p["assignment"]):
        raise ValueError("empty assignment")
    return p


def read_uploads(files, curriculum_codes=(), known_classes=None):
    res = []
    for b in _expand(files):
        if isinstance(b, tuple):
            res.append(dict(name=b[1], kind=None, error=b[2])); continue
        name = b.name
        df, err = None, None
        if not ASSIGN_NAME.search(name):
            try:
                df = dl.read_table(b)
            except Exception as ex:
                err = str(ex)
            k = detect(df, name) if df is not None else None
            if k:
                res.append(dict(name=name, kind=k, df=df)); continue
        try:                                            # the school assignment grid (جدول الإسناد)
            p = parse_assignment(b, curriculum_codes, known_classes)
            res.append(dict(name=name, kind="assign", assign=p))
        except Exception as ex:
            res.append(dict(name=name, kind=None, error=err or str(ex)))
    return res
