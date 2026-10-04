"""One generic editor for every data table: edit / save / export / import (with confirmation) / reset.

Edited tables are stored per workspace (and per data source for the school tables) in the project store,
and re-applied on top of the source data at every start, so demo data, uploaded data and guide data can all
be corrected after loading."""
import io

import pandas as pd

from i18n import t


def _read(file):
    return (pd.read_excel(file, dtype=str) if file.name.lower().endswith("xlsx") else pd.read_csv(file, dtype=str)).fillna("")


def load(db, ws, name):
    """Stored version of a table or None."""
    pr_ = db.load_project(ws, name=name)[0]
    if pr_ and pr_.get("csv") is not None:
        try:
            return pd.read_csv(io.StringIO(pr_["csv"]), dtype=str).fillna("")
        except pd.errors.EmptyDataError:
            return None
    return None


def save(db, ws, name, df):
    db.save_project(ws, {"csv": df.to_csv(index=False)}, name=name)


def clear(db, ws, name):
    db.save_project(ws, {"csv": None}, name=name)


def coerce_like(new, ref):
    """Give an edited (string) table the numeric dtypes of the original one."""
    out = new.copy()
    for c in out.columns:
        if ref is not None and c in ref.columns and pd.api.types.is_numeric_dtype(ref[c]):
            num = pd.to_numeric(out[c], errors="coerce")
            out[c] = num.fillna(0).astype(ref[c].dtype if pd.api.types.is_integer_dtype(ref[c]) else float)
    return out


def editor(st, db, ws, name, df, key, cols=None, column_config=None, filename=None, resettable=False, edited=False):
    """Draw the editor of one table.  Returns the table currently shown (possibly unsaved edits)."""
    cols = list(cols or df.columns)
    shown = st.data_editor(df.astype(str) if not df.empty else df, num_rows="dynamic", width="stretch",
                           key=key + "_ed", column_config=column_config or {})
    b1, b2, b3, b4 = st.columns([1, 1, 2, 1])
    if b1.button(t("tb_save"), type="primary", width="stretch", key=key + "_sv"):
        save(db, ws, name, shown); st.toast("✅"); st.rerun()
    b2.download_button(t("tb_export"), shown.to_csv(index=False).encode("utf-8-sig"), filename or (name + ".csv"),
                       "text/csv", width="stretch", key=key + "_dl")
    up = b3.file_uploader(t("tb_import"), type=["csv", "xlsx"], key=key + "_up", label_visibility="collapsed")
    if resettable and edited and b4.button(t("tb_reset"), width="stretch", key=key + "_rs"):
        clear(db, ws, name); st.rerun()
    if up is not None:
        new = _read(up)
        missing = [c for c in cols if c not in new.columns]
        if missing:
            st.error(t("tb_bad_cols", c=", ".join(missing)))
        elif len(df) and not st.checkbox(t("tb_overwrite", n=len(df), m=len(new)), key=key + "_ow"):
            pass
        elif st.button(t("tb_apply", n=len(new)), key=key + "_ap"):
            save(db, ws, name, new[cols + [c for c in new.columns if c not in cols]]); st.rerun()
    return shown
