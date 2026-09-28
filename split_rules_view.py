"""Plain-language explanation of the split rules (تفويج), exactly as the engine understands them."""
import pandas as pd
import i18n
from i18n import t
from engine import normalize_split_rules, split_rule_hours, _split_list, _int_list

V2_COLUMNS = ["Rule_ID", "Level", "Primary_Subject", "Primary_Type", "Primary_Hours",
              "Secondary_Subject", "Secondary_Type", "Secondary_Hours", "Frequency", "Description"]


def _s(code):
    return i18n.subj(code)


def explain(data_frames):
    rules = data_frames.get("rules")
    subjects = data_frames.get("subjects")
    if rules is None or subjects is None:
        return pd.DataFrame()
    norm = normalize_split_rules(rules)
    if "classes" in data_frames and data_frames["classes"] is not None:
        all_levels = sorted(data_frames["classes"]["Level"].astype(str).unique())
    else:
        all_levels = sorted(subjects["Level"].astype(str).unique())
    rows = []
    for _, r in norm.iterrows():
        lv = str(r["Level"]).split(";")
        target = all_levels if "ALL" in lv else [x for x in lv if x]
        secs, sh = _split_list(r["Secondary_Subject"]), _int_list(r["Sec_Hours"])
        subj_all = [r["Primary_Subject"]] + secs
        used, ignored = [], []
        for L in target:
            have = set(subjects[subjects["Level"].astype(str) == L]["Subject_Code"])
            miss = [x for x in subj_all if x not in have]
            (ignored if miss else used).append((L, miss))

        p = f"{_s(r['Primary_Subject'])} {r['Primary_Type']}"
        seq = " → ".join(f"{_s(x)} {h}{t('sr_h')}" for x, h in zip(secs, sh))
        if len(secs) == 1:
            seq = f"{_s(secs[0])} {r['Secondary_Type']}"
        blk = int(r["Block_Len"])
        if r["Back_To_Back"]:
            desc = t("sr_d_b2b", p=p, s=seq)
        elif int(r["Frequency"]) == 2:
            desc = t("sr_d_14", L=blk, p=p, s=seq)
        else:
            desc = t("sr_d_week2", L=blk, p=p, s=seq)

        hrs, slots = split_rule_hours(r)
        teach = " · ".join(f"{_s(k)} {v}{t('sr_h')}" for k, v in hrs.items())

        checks = [t(k) for k in str(r["Problems"]).split(";") if k]
        for L, _ in used:                                   # compare with the curriculum TD/TP hours
            row = subjects[subjects["Level"].astype(str) == L]
            for sub, h in hrs.items():
                x = row[row["Subject_Code"] == sub]
                if x.empty:
                    continue
                x = x.iloc[0]
                cur_h = int(x.get("Hrs_TD", 0) or 0) + int(x.get("Hrs_TP", 0) or 0) + int(x.get("Hrs_Practice", 0) or 0)
                if sub == "INFO":
                    cur_h = max(cur_h, 2)                   # engine forces INFO TP = 2
                if cur_h != h:
                    checks.append(t("sr_p_curr", l=L, s=_s(sub), c=cur_h, r=h))
        rows.append({
            t("sr_c_rule"): r["Rule_ID"],
            t("sr_c_levels"): ", ".join(L for L, _ in used) or "—",
            t("sr_c_desc"): desc,
            t("sr_c_slots"): slots,
            t("sr_c_teach"): teach,
            t("sr_c_ignored"): " ; ".join(t("sr_ign", l=L, s=", ".join(_s(m) for m in miss)) for L, miss in ignored) or "",
            t("sr_c_check"): " ; ".join(checks) if checks else "✅",
        })
    return pd.DataFrame(rows)


def to_v2(rules):
    """Convert any accepted rule file to the explicit v2 format (for download)."""
    n = normalize_split_rules(rules)
    out = pd.DataFrame({
        "Rule_ID": n["Rule_ID"], "Level": n["Level"],
        "Primary_Subject": n["Primary_Subject"], "Primary_Type": n["Primary_Type"], "Primary_Hours": n["Block_Len"],
        "Secondary_Subject": n["Secondary_Subject"], "Secondary_Type": n["Secondary_Type"],
        "Secondary_Hours": n["Sec_Hours"], "Frequency": n["Frequency"]})
    if "Description" in rules.columns and len(rules) == len(out):
        out["Description"] = rules["Description"].values
    else:
        out["Description"] = ""
    return out[V2_COLUMNS]
