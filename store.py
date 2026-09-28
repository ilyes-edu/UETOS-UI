"""Persistent storage: timetable versions, editable states, setup-guide projects and settings.

Backend
  * MySQL / PostgreSQL / any SQLAlchemy URL  – set it in Streamlit secrets:
        [connections.db]
        url = "mysql+pymysql://user:password@host:3306/dbname"
    (or environment variable DATABASE_URL)
  * otherwise a local SQLite file (data/app.db) – fine for one machine, NOT persistent on Streamlit Cloud.

Every row belongs to a WORKSPACE (one per tester / school) so testers never overwrite each other.
"""
import hashlib
import io
import json
import os
import secrets as _secrets
import time

import pandas as pd
from sqlalchemy import create_engine, text

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ADMIN_PASSWORD = "beta2026"

DDL = [
    """CREATE TABLE IF NOT EXISTS versions (
         ws VARCHAR(64) NOT NULL, name VARCHAR(160) NOT NULL, created DOUBLE PRECISION NOT NULL,
         sched {TEXT} NOT NULL, state {TEXT} NULL, PRIMARY KEY (ws, name))""",
    """CREATE TABLE IF NOT EXISTS projects (
         ws VARCHAR(64) NOT NULL, name VARCHAR(64) NOT NULL, created DOUBLE PRECISION NOT NULL,
         data {TEXT} NOT NULL, PRIMARY KEY (ws, name))""",
    """CREATE TABLE IF NOT EXISTS settings (k VARCHAR(64) NOT NULL PRIMARY KEY, v {TEXT} NOT NULL)""",
]


def _url():
    try:
        import streamlit as st
        u = st.secrets.get("connections", {}).get("db", {}).get("url")
        if u:
            return u
    except Exception:
        pass
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    return "sqlite:///" + os.path.join(HERE, "data", "app.db")


def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()


class Store:
    def __init__(self, url=None):
        self.url = url or _url()
        self.kind = self.url.split(":")[0].split("+")[0]
        self.eng = create_engine(self.url, pool_pre_ping=True, pool_recycle=280)
        big = "LONGTEXT" if self.kind == "mysql" else "TEXT"
        with self.eng.begin() as c:
            for q in DDL:
                c.execute(text(q.replace("{TEXT}", big)))
        if self.get_setting("admin_pw") is None:          # default admin password (change it in the app)
            self.set_admin_password(os.environ.get("ADMIN_PASSWORD") or DEFAULT_ADMIN_PASSWORD)

    @property
    def persistent(self):
        return self.kind != "sqlite"

    # ------------------------------------------------------------ generic helpers
    def _q(self, sql, **kw):
        with self.eng.begin() as c:
            return c.execute(text(sql), kw)

    def _upsert(self, table, keys, values):
        cols = {**keys, **values}
        with self.eng.begin() as c:
            where = " AND ".join(f"{k} = :{k}" for k in keys)
            n = c.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), keys).scalar()
            if n:
                sets = ", ".join(f"{k} = :{k}" for k in values)
                c.execute(text(f"UPDATE {table} SET {sets} WHERE {where}"), cols)
            else:
                c.execute(text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + k for k in cols)})"),
                          cols)

    # ------------------------------------------------------------ versions
    def versions(self, ws):
        """Names, oldest first / most recent last."""
        r = self._q("SELECT name FROM versions WHERE ws = :ws ORDER BY created, name", ws=ws)
        return [x[0] for x in r]

    def stamp(self, ws, name):
        r = self._q("SELECT created FROM versions WHERE ws = :ws AND name = :n", ws=ws, n=name).first()
        return r[0] if r else 0

    def save(self, ws, name, df, state=None):
        vals = {"created": time.time(), "sched": df.to_csv(index=False)}
        if state is not None:
            vals["state"] = json.dumps(state, ensure_ascii=False, default=_json_default)
        self._upsert("versions", {"ws": ws, "name": name}, vals)

    def load(self, ws, name):
        r = self._q("SELECT sched FROM versions WHERE ws = :ws AND name = :n", ws=ws, n=name).first()
        return pd.read_csv(io.StringIO(r[0])) if r else None

    def load_state(self, ws, name):
        r = self._q("SELECT state FROM versions WHERE ws = :ws AND name = :n", ws=ws, n=name).first()
        return json.loads(r[0]) if r and r[0] else None

    def has_state(self, ws):
        return {x[0] for x in self._q("SELECT name FROM versions WHERE ws = :ws AND state IS NOT NULL", ws=ws)}

    def delete(self, ws, name):
        self._q("DELETE FROM versions WHERE ws = :ws AND name = :n", ws=ws, n=name)

    def rename(self, ws, old, new):
        if not new or new == old or new in self.versions(ws):
            return False
        self._q("UPDATE versions SET name = :new WHERE ws = :ws AND name = :old", ws=ws, old=old, new=new)
        return True

    def clear(self, ws):
        self._q("DELETE FROM versions WHERE ws = :ws", ws=ws)

    # ------------------------------------------------------------ setup-guide projects
    def save_project(self, ws, data, name="wizard"):
        self._upsert("projects", {"ws": ws, "name": name},
                     {"created": time.time(), "data": json.dumps(data, ensure_ascii=False, default=_json_default)})

    def load_project(self, ws, name="wizard"):
        r = self._q("SELECT data, created FROM projects WHERE ws = :ws AND name = :n", ws=ws, n=name).first()
        return (json.loads(r[0]), r[1]) if r else (None, None)

    # ------------------------------------------------------------ settings / admin password
    def get_setting(self, k, default=None):
        r = self._q("SELECT v FROM settings WHERE k = :k", k=k).first()
        return r[0] if r else default

    def set_setting(self, k, v):
        self._upsert("settings", {"k": k}, {"v": v})

    def set_admin_password(self, pw):
        salt = _secrets.token_hex(8)
        self.set_setting("admin_pw", f"{salt}${_hash(pw, salt)}")

    def check_admin_password(self, pw):
        v = self.get_setting("admin_pw")
        if not v or "$" not in v:
            return False
        salt, h = v.split("$", 1)
        return _secrets.compare_digest(_hash(pw or "", salt), h)

    # ------------------------------------------------------------ one-time import of the old file storage
    def import_folder(self, ws, folder):
        if self.versions(ws) or not os.path.isdir(folder):
            return 0
        try:
            order = json.load(open(os.path.join(folder, "_order.json")))
        except Exception:
            order = {}
        n = 0
        for f in sorted(os.listdir(folder)):
            if not f.endswith(".csv"):
                continue
            name = f[:-4]
            df = pd.read_csv(os.path.join(folder, f))
            sp = os.path.join(folder, f"{name}.state.json")
            state = json.load(open(sp)) if os.path.exists(sp) else None
            self.save(ws, name, df, state)
            self._q("UPDATE versions SET created = :c WHERE ws = :ws AND name = :n",
                    c=float(order.get(name, time.time())), ws=ws, n=name)
            n += 1
        return n


def _json_default(o):
    try:
        import numpy as np
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except Exception:
        pass
    if isinstance(o, (set, tuple)):
        return list(o)
    raise TypeError(str(type(o)))
