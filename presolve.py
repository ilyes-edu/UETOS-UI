"""Before solving: remediation units (joint subjects, singles/pairs, fixed hours) and external teachers' fixed lessons.

Everything is stored in st.session_state["pre"] and turned into solver settings by config_patch().
"""
import pandas as pd

import i18n
from i18n import t
from engine import (rem_info, rem_group_units, rem_rooms, lesson_keys, SchoolDataLoader, SchedulerConfig,
                    SchoolSchedulerEngine)

AUTO = "auto"

i18n.S.update({
    "pre_title": ("🧩 Before solving", "🧩 قبل التوليد"),
    "pre_caption": ("Check these settings, then press «Solve» below.", "راجع هذه الإعدادات ثم اضغط «حلّ» أدناه."),
    "pre_rem_title": ("📚 Remediation sessions", "📚 حصص الاستدراك"),
    "pre_rem_found": ("The assignment contains remediation hours for {n} teacher(s).", "يحتوي الإسناد على ساعات استدراك لـ {n} أستاذ."),
    "pre_joint": ("Joint subjects (share ONE weekly hour, alternating: one week the first subject, the next week the other)",
                  "مواد مشتركة (تتقاسم ساعة أسبوعية واحدة بالتناوب: أسبوع المادة الأولى والأسبوع الموالي الأخرى)"),
    "pre_proposal": ("Proposal: teachers of joint subjects that share classes are grouped. Change the «Unit» number to regroup or separate teachers; set a day and hour to fix a session.",
                     "الاقتراح: يُجمع أساتذة المواد المشتركة الذين يتقاسمون أفواجًا. غيّر رقم «الوحدة» لإعادة التجميع أو الفصل، وحدّد يومًا وساعة لتثبيت حصة."),
    "pre_c_teacher": ("Teacher", "الأستاذ"), "pre_c_subject": ("Subject", "المادة"), "pre_c_classes": ("Classes", "الأفواج"),
    "pre_c_unit": ("Unit", "الوحدة"), "pre_c_day": ("Day", "اليوم"), "pre_c_slot": ("Hour", "الساعة"),
    "pre_c_hours": ("Hours", "الساعات"), "pre_c_rooms": ("Rooms", "القاعات"), "pre_c_teachers": ("Teachers", "الأساتذة"),
    "pre_units": ("**Resulting sessions** (one per unit and per week)", "**الحصص الناتجة** (حصة لكل وحدة أسبوعيًا)"),
    "pre_auto": ("auto", "تلقائي"),
    "pre_w_double": ("{c} would receive {n} «{g}» sessions (units {u}) – each class should get one.",
                     "الفوج {c} سيتلقى {n} حصص «{g}» (الوحدات {u}) – يجب حصة واحدة لكل فوج."),
    "pre_w_other": ("{c}: its {s} teacher is not in unit {u} (the class would get another teacher's remediation).",
                    "{c}: أستاذ {s} الخاص به ليس في الوحدة {u} (سيتلقى الفوج استدراك أستاذ آخر)."),
    "pre_w_slot": ("Unit {u}: day and hour must both be set (or both auto).", "الوحدة {u}: يجب تحديد اليوم والساعة معًا (أو تلقائي للاثنين)."),
    "pre_w_off": ("{w}: {d} {s} is outside school hours.", "{w}: {d} {s} خارج أوقات الدراسة."),
    "pre_rem_ok": ("✅ I checked the remediation setup", "✅ راجعت إعداد الاستدراك"),
    "pre_rem_need": ("⚠ Confirm the remediation setup in «🧩 Before solving» above.",
                     "⚠ أكّد إعداد الاستدراك في «🧩 قبل التوليد» أعلاه."),
    "pre_ext_title": ("🚌 External teachers (fixed sessions)", "🚌 الأساتذة الخارجيون (حصص مثبّتة)"),
    "pre_ext_help": ("Teachers coming from another school: choose them, then fix the day and hour of their lessons. Fixed lessons may exceptionally fall in the pedagogical window of their subject. Lessons left on «auto» are placed by the solver.",
                     "أساتذة قادمون من مؤسسة أخرى: اخترهم ثم ثبّت يوم وساعة حصصهم. يمكن للحصص المثبّتة استثنائيًا أن تكون في النافذة البيداغوجية لمادتهم. الحصص «تلقائي» يضعها المحلّل."),
    "pre_ext_pick": ("External teachers", "الأساتذة الخارجيون"),
    "pre_ext_fixed": ("{n} lesson(s) fixed", "{n} حصة مثبّتة"),
    "pre_w_clash": ("{d} {s}: {w} has two fixed lessons at the same hour.", "{d} {s}: لـ {w} حصتان مثبّتتان في نفس الساعة."),
    "pre_lessons_err": ("Lessons could not be generated: {e}", "تعذّر توليد الحصص: {e}"),
})


def _state(st):
    return st.session_state.setdefault("pre", {"joint": None, "units": None, "unit_fix": {}, "rem_ok": False,
                                               "ext": [], "fixed": {}, "src": None})


def _day_opts(D):
    return [t("pre_auto")] + [i18n.day(d) for d in range(D)]


def _slot_opts(S):
    return [t("pre_auto")] + [str(s + 1) for s in range(S)]


def _to_cell(day_lbl, slot_lbl, D, S):
    """labels -> (day, slot) | None (auto) | 'bad' (only one of both set)"""
    dl, sl = _day_opts(D), _slot_opts(S)
    d = dl.index(day_lbl) - 1 if day_lbl in dl else -1
    s = sl.index(slot_lbl) - 1 if slot_lbl in sl else -1
    if d < 0 and s < 0:
        return None
    if d < 0 or s < 0:
        return "bad"
    return d, s


def _labels(fx, D, S):
    return (_day_opts(D)[fx[0] + 1], _slot_opts(S)[fx[1] + 1]) if fx else (t("pre_auto"), t("pre_auto"))


def remedial_present(plan):
    return plan is not None and any(float(v or 0) > 0 for v in (plan.get("remedial") or {}).values())


def config_patch(st, cfg, plan, use_remedial):
    """Apply the pre-solve settings to a SchedulerConfig."""
    p = _state(st)
    if use_remedial and remedial_present(plan) and p.get("units"):
        groups = {}
        for tc, u in p["units"].items():
            groups.setdefault(int(u), []).append(tc)
        cfg.remedial_units_manual = [{"teachers": sorted(tt, key=str), "fixed": p["unit_fix"].get(str(u))}
                                     for u, tt in sorted(groups.items())]
        cfg.remedial_groups = [set(p["joint"])] if p.get("joint") and len(p["joint"]) > 1 else []
    cfg.fixed_lessons = {k: v for k, v in p.get("fixed", {}).items()
                         if k.split("|")[0] in set(p.get("ext", []))}
    return cfg


def ready(st, plan, use_remedial):
    return not (use_remedial and remedial_present(plan)) or _state(st).get("rem_ok", False)


def render(st, plan, data_frames, use_remedial, days=5, slots=7, lunch=3):
    p = _state(st)
    src = st.session_state.get("plan_src")
    if p.get("src") != src:                      # new assignment -> start again
        p.update(joint=None, units=None, unit_fix={}, rem_ok=False, ext=[], fixed={}, src=src)
    off = lambda d, s, dur=1: d == 2 and s + dur - 1 > lunch        # Tuesday afternoon

    st.subheader(t("pre_title"))
    st.caption(t("pre_caption"))
    # ------------------------------------------------------------ remediation
    if use_remedial and remedial_present(plan):
        with st.expander(t("pre_rem_title"), expanded=not p["rem_ok"]):
            classes = set(data_frames["classes"]["Class_ID"]) if "classes" in data_frames else set(plan["classes"]["Class_ID"])
            info = rem_info(plan["assignment"], plan["remedial"], classes, set(plan["teachers"]["Teacher_ID"]))
            st.caption(t("pre_rem_found", n=len(info)))
            subjects = sorted({v["subject"] for v in info.values()})
            if p["joint"] is None:
                p["joint"] = [x for x in ("ARABIC", "MATH") if x in subjects]
            joint = st.multiselect(t("pre_joint"), subjects, default=[x for x in p["joint"] if x in subjects],
                                   format_func=i18n.subj, key="pre_joint_ms")
            if joint != p["joint"] or p["units"] is None or set(p["units"]) != set(info):
                p["joint"] = joint
                units = rem_group_units(info, [set(joint)] if len(joint) > 1 else [])
                p["units"] = {tc: i + 1 for i, u in enumerate(units) for tc in u}
                p["unit_fix"], p["rem_ok"] = {}, False
            st.caption(t("pre_proposal"))
            rows = pd.DataFrame([{"tc": tc, "subj": i18n.subj(info[tc]["subject"]),
                                  "cls": ", ".join(i18n.cls(c) for c in sorted(info[tc]["classes"])),
                                  "unit": int(p["units"][tc])} for tc in sorted(info, key=lambda x: (p["units"][x], str(x)))])
            ed = st.data_editor(rows, hide_index=True, width="stretch", key=f"pre_units_{src}_{'+'.join(joint)}",
                                disabled=["tc", "subj", "cls"],
                                column_config={"tc": st.column_config.TextColumn(t("pre_c_teacher")),
                                               "subj": st.column_config.TextColumn(t("pre_c_subject")),
                                               "cls": st.column_config.TextColumn(t("pre_c_classes")),
                                               "unit": st.column_config.NumberColumn(t("pre_c_unit"), min_value=1,
                                                                                     max_value=99, step=1)})
            new_units = {r.tc: int(r.unit) for r in ed.itertuples()}
            if new_units != p["units"]:
                p["units"], p["rem_ok"] = new_units, False; p["_dirty"] = True
            groups = {}
            for tc, u in p["units"].items():
                groups.setdefault(u, []).append(tc)
            st.markdown(t("pre_units"))
            urows = []
            for u, tt in sorted(groups.items()):
                fx = p["unit_fix"].get(str(u))
                urows.append({"unit": u, "tt": " + ".join(sorted(tt, key=str)),
                              "cls": len(set().union(*(info[tc]["classes"] for tc in tt))),
                              "rooms": rem_rooms(tt, info),
                              "day": _labels(fx, days, slots)[0], "slot": _labels(fx, days, slots)[1]})
            ued = st.data_editor(pd.DataFrame(urows), hide_index=True, width="stretch",
                                 key=f"pre_ufix_{src}_{hash(tuple(sorted(p['units'].items())))}",
                                 disabled=["unit", "tt", "cls", "rooms"],
                                 column_config={"unit": st.column_config.NumberColumn(t("pre_c_unit")),
                                                "tt": st.column_config.TextColumn(t("pre_c_teachers")),
                                                "cls": st.column_config.NumberColumn(t("pre_c_classes")),
                                                "rooms": st.column_config.NumberColumn(t("pre_c_rooms")),
                                                "day": st.column_config.SelectboxColumn(t("pre_c_day"), options=_day_opts(days)),
                                                "slot": st.column_config.SelectboxColumn(t("pre_c_slot"), options=_slot_opts(slots))})
            warns = []
            fix = {}
            for r in ued.itertuples():
                c_ = _to_cell(r.day, r.slot, days, slots)
                if c_ == "bad":
                    warns.append(t("pre_w_slot", u=r.unit)); continue
                if c_:
                    d, s_ = c_
                    if off(d, s_):
                        warns.append(t("pre_w_off", w=t("pre_c_unit") + f" {r.unit}", d=i18n.day(d), s=s_ + 1)); continue
                    fix[str(r.unit)] = [d, s_]
            if fix != p["unit_fix"]:
                p["unit_fix"], p["rem_ok"] = fix, False; p["_dirty"] = True
            # checks: each class one session per joint group, always with its own teachers
            if len(joint) > 1:
                own = {}
                for r in plan["assignment"].itertuples():
                    b = str(r.Subject).split("_")[0]
                    if b in joint:
                        own.setdefault((r.Class, b), set()).add(r.Teacher)
                per_class = {}
                for u, tt in groups.items():
                    if any(info[tc]["subject"] in joint for tc in tt):
                        for c in set().union(*(info[tc]["classes"] for tc in tt)):
                            per_class.setdefault(c, []).append(u)
                            for b in joint:
                                mine = own.get((c, b), set()) & set(info)
                                if mine and not mine & set(tt):
                                    warns.append(t("pre_w_other", c=i18n.cls(c), s=i18n.subj(b), u=u))
                for c, us in sorted(per_class.items()):
                    if len(us) > 1:
                        warns.append(t("pre_w_double", c=i18n.cls(c), n=len(us), g=" + ".join(map(i18n.subj, joint)),
                                       u=", ".join(map(str, sorted(us)))))
            for w in dict.fromkeys(warns):
                st.warning(w)
            new_ok = st.checkbox(t("pre_rem_ok"), value=p["rem_ok"], key=f"pre_ok_{src}_{p['rem_ok']}")
            if new_ok != p["rem_ok"] or p.pop("_dirty", False):
                p["rem_ok"] = new_ok
                st.rerun()                # the sidebar «Solve» button is drawn before this tab: refresh it
    # ------------------------------------------------------------ external teachers
    with st.expander(t("pre_ext_title"), expanded=bool(p["ext"])):
        st.caption(t("pre_ext_help"))
        if plan is None:
            return
        load = plan["assignment"].groupby("Teacher")["Hours"].sum() if "Hours" in plan["assignment"] else None
        teachers = sorted(plan["teachers"]["Teacher_ID"], key=lambda x: (float(load.get(x, 0)) if load is not None else 0, str(x)))
        fmt = (lambda x: f"{x} ({int(load.get(x, 0))} {t('pre_c_hours')})") if load is not None else str
        p["ext"] = st.multiselect(t("pre_ext_pick"), teachers, default=[x for x in p["ext"] if x in teachers],
                                  format_func=fmt, key=f"pre_ext_{src}")
        if not p["ext"]:
            return
        lessons = _lessons(st, data_frames, plan)
        if isinstance(lessons, str):
            st.error(t("pre_lessons_err", e=lessons)); return
        keys = lesson_keys(lessons)
        by_id = {l["id"]: l for l in lessons}
        cells, warns = {}, []
        for tc in p["ext"]:
            rows = []
            for lid, ks in keys.items():
                for k in ks:
                    if k.split("|")[0] == tc:
                        l = by_id[lid]; fx = p["fixed"].get(k)
                        rows.append({"key": k, "cls": i18n.cls(l["class"]), "subj": i18n.subj(l["subject"]),
                                     "h": l["duration"], "day": _labels(fx, days, slots)[0], "slot": _labels(fx, days, slots)[1]})
            st.markdown(f"**{tc}** – " + t("pre_ext_fixed", n=sum(1 for r in rows if r["day"] != t("pre_auto"))))
            ed = st.data_editor(pd.DataFrame(rows), hide_index=True, width="stretch", key=f"pre_fx_{src}_{tc}",
                                disabled=["key", "cls", "subj", "h"], column_order=["cls", "subj", "h", "day", "slot"],
                                column_config={"cls": st.column_config.TextColumn(t("pre_c_classes")),
                                               "subj": st.column_config.TextColumn(t("pre_c_subject")),
                                               "h": st.column_config.NumberColumn(t("pre_c_hours")),
                                               "day": st.column_config.SelectboxColumn(t("pre_c_day"), options=_day_opts(days)),
                                               "slot": st.column_config.SelectboxColumn(t("pre_c_slot"), options=_slot_opts(slots))})
            for r in ed.itertuples():
                c_ = _to_cell(r.day, r.slot, days, slots)
                if c_ in (None, "bad"):
                    p["fixed"].pop(r.key, None); continue
                d, s_ = c_
                lid = next(i for i, ks in keys.items() if r.key in ks)
                l = by_id[lid]
                if s_ + l["duration"] > slots or off(d, s_, l["duration"]) or (l["duration"] > 1 and s_ <= lunch < s_ + l["duration"] - 1):
                    warns.append(t("pre_w_off", w=f"{tc} · {r.cls}", d=i18n.day(d), s=s_ + 1))
                    p["fixed"].pop(r.key, None); continue
                p["fixed"][r.key] = [d, s_]
                for k2 in range(l["duration"]):
                    for who in [tc, l["class"]]:
                        c_ = (who, d, s_ + k2)
                        if c_ in cells and cells[c_] != lid:
                            warns.append(t("pre_w_clash", d=i18n.day(d), s=s_ + k2 + 1, w=i18n.cls(who) if who == l["class"] else who))
                        cells[c_] = lid
        for w in dict.fromkeys(warns):
            st.warning(w)


def _lessons(st, data_frames, plan):
    """Lessons the solver will create (cached per assignment)."""
    key = ("pre_lessons", st.session_state.get("plan_src"))
    cache = st.session_state.setdefault("_pre_cache", {})
    if key not in cache:
        try:
            eng = SchoolSchedulerEngine(SchoolDataLoader(data_frames), SchedulerConfig(), fixed_assignment=plan["assignment"])
            eng._generate_lessons_and_assignments()
            cache[key] = [l for l in eng.lessons if not l.get("remedial")]
        except Exception as ex:           # noqa: BLE001
            return f"{type(ex).__name__}: {ex}"
    return cache[key]
