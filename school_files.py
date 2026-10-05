"""Reading the school's own files (classes, staff, curriculum) for a new school.

Works with the bilingual files (code + Arabic + English columns) and with the original Arabic files
(e.g. '2ع ت.' / 'ه الطرقان'): names are matched to the preset's codes through its names and aliases,
ignoring dots, spaces, tatweel and hamza/alef/ya/ta-marbuta forms.  Everything not recognised is returned
so the guide can ask the manager (dropdown) instead of guessing silently."""
import io
import re

import pandas as pd

import presets


# ------------------------------------------------------------------ name matching
def norm(x):
    s = str(x or "").strip().lower()
    s = re.sub(r"[\u0640.\u060c,:;/\\()\-_]", " ", s)            # tatweel, punctuation
    s = re.sub("[أإآٱ]", "ا", s).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub(r"\s+", " ", s).strip()


def _table(kind, P):
    """[(normalised name, code)] from the preset names + aliases, longest first."""
    out = []
    items = list(P.get("tracks", []) if kind == "tracks" else P.get("subjects", []))
    if kind == "tracks":                                          # streams with options (e.g. TM) can be named alone
        items += [{"id": k, "name": v.get("name", {})} for k, v in (P.get("track_options") or {}).items()]
    for it in items:
        for v in (it.get("name") or {}).values():
            out.append((norm(v), it["id"]))
        out.append((norm(it["id"]), it["id"]))
    for code, names in (P.get("aliases", {}).get(kind) or {}).items():
        out += [(norm(n), code) for n in names]
    return sorted({x for x in out if x[0]}, key=lambda x: -len(x[0]))


def match(kind, text, P=None):
    """Code for a track/subject name, or None.  Exact normalised match first, then 'contains'."""
    P = P or presets.load()
    n = norm(text)
    if not n:
        return None
    tab = _table(kind, P)
    for k, code in tab:
        if n == k:
            return code
    for k, code in tab:
        if len(k) >= 3 and (k in n.split(" ") or f" {k} " in f" {n} " or n.startswith(k + " ") or n.endswith(" " + k)):
            return code
    return None


def _read_any(file, sheet=None):
    name = getattr(file, "name", str(file)).lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file, sheet_name=sheet if sheet is not None else 0, header=None, dtype=object)
    raw = file.read() if hasattr(file, "read") else open(file, "rb").read()
    for enc in ("utf-8-sig", "cp1256", "latin-1"):
        try:
            return pd.read_csv(io.StringIO(raw.decode(enc)), header=None, dtype=object)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    return pd.DataFrame()


def _num(v):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ classes
def read_classes(file, P=None):
    """-> (counts {level key: n}, problems [{row, text, year, guess}]).  Level key = year (no track) or year-track."""
    P = P or presets.load()
    df = _read_any(file)
    years = [str(y["id"]) for y in P.get("years", [])]
    has_tracks = {y: [tr["id"] for tr in P.get("tracks", []) if y in tr.get("years", [])] for y in years}
    counts, probs = {}, []
    head = [norm(x) for x in df.iloc[0].tolist()] if len(df) else []
    code_col = next((i for i, h in enumerate(head) if "code" in h or h == "track"), None)
    year_col = next((i for i, h in enumerate(head) if "year" in h or "السنه" in h), None)
    for i, row in df.iterrows():
        cells = [c for c in row.tolist()]
        nums = [(_num(c), j) for j, c in enumerate(cells) if _num(c) is not None]
        texts = [str(c) for c in cells if c is not None and str(c).strip() and _num(c) is None and str(c) != "nan"]
        if not nums or (not texts and code_col is None):
            continue
        if any(norm(x) in ("total", "المجموع", "مجموع") for x in texts):
            continue
        n = nums[-1][0]                                           # last number of the row = classes
        if code_col is not None and year_col is not None:         # bilingual file: explicit year + code
            y = str(cells[year_col]).strip()
            if not y or y == "nan":
                continue
            y = next((yy for yy in years if yy == y or yy.startswith(y)), y)
            tr = str(cells[code_col]).strip()
            opts = (P.get("track_options") or {}).get(tr)
            if opts:
                probs.append({"row": int(i) + 1, "text": f"{y} {tr}", "n": n, "year": y,
                              "guess": next(iter(opts["options"])), "choices": list(opts["options"])})
                continue
            key = f"{y}-{tr}" if tr and tr != "nan" else y
            counts[key] = counts.get(key, 0) + n
            continue
        text = texts[0]
        m = re.search(r"\d", text)
        y = None
        if m:
            y = next((yy for yy in years if yy.startswith(m.group(0))), None)
            text = text.replace(m.group(0), " ", 1)
        tr = match("tracks", text, P)
        opts = (P.get("track_options") or {}).get(tr)
        if opts:                                                  # option not given: ask (first option proposed)
            probs.append({"row": int(i) + 1, "text": str(cells[0]), "n": n, "year": y,
                          "guess": next(iter(opts["options"])), "choices": list(opts["options"])})
            continue
        if y and not has_tracks.get(y):
            counts[y] = counts.get(y, 0) + n
        elif y and tr in has_tracks.get(y, []):
            counts[f"{y}-{tr}"] = counts.get(f"{y}-{tr}", 0) + n
        else:
            probs.append({"row": int(i) + 1, "text": str(cells[0] if texts else ""), "n": n, "year": y, "guess": tr})
    return counts, probs


# ------------------------------------------------------------------ staff
def read_staff(file, P=None):
    """-> (counts {post subject: [regular, distinguished]}, problems [{row, text}]).
    Columns: subject name, regular (أستاذ ت ث), distinguished (مميز), [total]."""
    P = P or presets.load()
    df = _read_any(file)
    out, probs = {}, []
    head = [norm(x) for x in df.iloc[0].tolist()] if len(df) else []
    code_col = next((i for i, h in enumerate(head) if "code" in h), None)
    for i, row in df.iterrows():
        if i == 0 and code_col is not None:
            continue
        cells = row.tolist()
        nums = [_num(c) for c in cells if _num(c) is not None]
        texts = [str(c) for c in cells if c is not None and str(c).strip() and str(c) != "nan" and _num(c) is None]
        if len(nums) < 1 or not texts:
            continue
        if norm(texts[0]) in ("المجموع", "total", "مجموع"):
            continue
        code = str(cells[code_col]).strip() if code_col is not None else match("subjects", texts[0], P)
        if not code or code == "nan":
            probs.append({"row": int(i) + 1, "text": texts[0], "nums": nums})
            continue
        reg, dist = (nums + [0, 0])[:2]
        prev = out.get(code, [0, 0])
        out[code] = [prev[0] + reg, prev[1] + dist]
    return out, probs


# ------------------------------------------------------------------ curriculum (Course / TD / TP per stream)
def read_curriculum(file, P=None):
    """Sheets per year; a header row with '<stream> Course | <stream> TD | <stream> TP' triplets (read by position).
    -> (curriculum DataFrame in the app format, problems)."""
    P = P or presets.load()
    years = [str(y["id"]) for y in P.get("years", [])]
    xl = pd.ExcelFile(file)
    rows, probs = [], []
    for si, sh in enumerate(xl.sheet_names):
        df = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object)
        m = re.search(r"\d", sh + " " + str(df.iloc[0, 0] if len(df) else ""))
        y = next((yy for yy in years if m and yy.startswith(m.group(0))), years[si] if si < len(years) else None)
        hr = next((i for i in range(min(6, len(df)))
                   if sum("course" in norm(c) or norm(c).endswith(" td") or norm(c).endswith(" tp") or norm(c) in ("td", "tp")
                          for c in df.iloc[i].tolist()) >= 3), None)
        if hr is None or y is None:
            probs.append({"sheet": sh, "text": "no Course/TD/TP header"})
            continue
        head = df.iloc[hr].tolist()
        first = next(j for j, c in enumerate(head) if "course" in norm(c))
        code_col = next((j for j, c in enumerate(head[:first]) if "code" in norm(c)), None)
        streams = []
        for j in range(first, len(head) - 2, 3):
            name = re.sub(r"\b(coursee?|cours|course|درس)\b", "", str(head[j]), flags=re.I).strip()
            tr = match("tracks", name, P)
            has_tracks = any(y in t_.get("years", []) for t_ in P.get("tracks", []))
            key = (f"{y}-{tr}" if tr else None) if has_tracks else y
            if key is None:
                probs.append({"sheet": sh, "text": name})
            streams.append((j, key))
        for i in range(hr + 1, len(df)):
            r = df.iloc[i].tolist()
            label = next((str(c) for c in r[:first] if c is not None and str(c).strip() and str(c) != "nan"), "")
            if not label or norm(label) in ("total", "المجموع"):
                continue
            code = str(r[code_col]).strip() if code_col is not None else match("subjects", label, P)
            if not code:
                probs.append({"sheet": sh, "text": label})
                continue
            for j, key in streams:
                if key is None:
                    continue
                c, td, tp = (_num(r[j]) or 0, _num(r[j + 1]) or 0, _num(r[j + 2]) or 0)
                if not c + td + tp:
                    continue
                y_, _, tr_ = key.partition("-")
                op = (P.get("track_options") or {}).get(tr_)
                targets = [(f"{y_}-{o}", (s_ if code == op["subject"] else code)) for o, s_ in op["options"].items()] \
                    if op else [(key, code)]
                for lv_, cd_ in targets:
                    rows.append({"Level": lv_, "Subject_Code": cd_, "Hrs_Cours": c, "Hrs_TD": td, "Hrs_TP": tp,
                                 "Hrs_Practice": 0})
    cur = pd.DataFrame(rows, columns=["Level", "Subject_Code", "Hrs_Cours", "Hrs_TD", "Hrs_TP", "Hrs_Practice"])
    return cur, probs
