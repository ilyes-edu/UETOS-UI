"""Timetable scheduling engine (extracted from Untitled2.ipynb, logic unchanged)."""
import os
import pandas as pd
import timegrid
from ortools.sat.python import cp_model


REM_PREFIX = "REM:"


def is_rem(c):
    return str(c).startswith(REM_PREFIX)


ENGINE_MODES = {"SYNCHRONOUS_1H", "SYNCHRONOUS_2H_SWAP", "CONSECUTIVE_TRI_SWAP", "SPLIT_PAIR", "SPLIT_CHAIN"}


def _split_list(v):
    return [x.strip() for x in str(v).replace(" ", "").split(";") if x.strip() and x.strip().lower() != "nan"]


def _int_list(v):
    out = []
    for x in _split_list(v):
        try:
            out.append(int(float(x)))
        except ValueError:
            pass
    return out


def normalize_split_rules(df):
    """Split rules (تفويج) -> one normalized row per rule.

    v2 format (recommended):
        Rule_ID, Level, Primary_Subject, Primary_Type, Primary_Hours,
        Secondary_Subject, Secondary_Type, Secondary_Hours, Frequency
      * Primary_Hours   : length of ONE split session (group A does the primary subject all along)
      * Secondary_Hours : hours of each secondary subject IN ORDER during that session ("1;1" for FRENCH;ENGLISH);
                          must add up to Primary_Hours
      * Frequency       : 1 = every week (groups swap inside the same week -> 2 sessions / week)
                          2 = every 14 days (one session / week, groups swap the following week)
      A 1h session repeated every week (Frequency 1) is placed as ONE 2h back-to-back block (swap after 1h).
    Legacy formats are still accepted: Coupling_Mode = 1H / 2H (school) or the engine mode names.

    Output columns: Rule_ID, Level, Primary_Subject, Primary_Type, Secondary_Subject (';'), Secondary_Type,
        Block_Len, Sec_Hours (';'), Frequency, Sessions, Back_To_Back, Coupling_Mode (engine mode, informative),
        Problems (';' list of i18n keys)."""
    cols = ["Rule_ID", "Level", "Primary_Subject", "Primary_Type", "Secondary_Subject", "Secondary_Type",
            "Block_Len", "Sec_Hours", "Frequency", "Sessions", "Back_To_Back", "Coupling_Mode", "Problems"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    v2 = "Frequency" in df.columns or "Primary_Hours" in df.columns
    for i, r in df.reset_index(drop=True).iterrows():
        g = lambda k, dflt="": r[k] if k in r and pd.notna(r[k]) and str(r[k]).strip() != "" else dflt
        secs = _split_list(g("Secondary_Subject"))
        probs = []
        if v2:
            L = _int_list(g("Primary_Hours", "1"))
            L = L[0] if L else 1
            sh = _int_list(g("Secondary_Hours", ""))
            if not sh:
                sh = [L] if len(secs) == 1 else [max(1, L // max(1, len(secs)))] * len(secs)
            f = _int_list(g("Frequency", "2"))
            f = f[0] if f else 2
        else:
            m = str(g("Coupling_Mode")).strip().upper()
            if m in ("SYNCHRONOUS_1H",) or (m.startswith("1") and m not in ENGINE_MODES):
                L, sh, f = 1, [1] * len(secs), 2
            elif m == "CONSECUTIVE_TRI_SWAP" or (m.startswith("2") and len(secs) >= 2):
                L, sh, f = len(secs), [1] * len(secs), 2
            else:                                             # SYNCHRONOUS_2H_SWAP / 2H single secondary
                L, sh, f = 1, [1] * len(secs), 1
        if len(sh) != len(secs):
            probs.append("sr_p_count")
            sh = (sh + [1] * len(secs))[:len(secs)]
        if sum(sh) != L:
            probs.append("sr_p_sum")
        if f not in (1, 2):
            probs.append("sr_p_freq")
            f = 2
        b2b = (f == 1 and L == 1 and len(secs) == 1)
        sessions = 1 if (f == 2 or b2b) else 2
        if len(secs) == 1:
            mode = "SYNCHRONOUS_1H" if (L == 1 and f == 2) else "SYNCHRONOUS_2H_SWAP" if b2b else "SPLIT_PAIR"
        else:
            mode = "CONSECUTIVE_TRI_SWAP" if (L == 2 and f == 2 and sh == [1, 1]) else "SPLIT_CHAIN"
        rows.append({"Rule_ID": g("Rule_ID", f"R{i + 1}"), "Level": str(g("Level", "ALL")).replace(" ", ""),
                     "Primary_Subject": str(g("Primary_Subject")).strip(), "Primary_Type": str(g("Primary_Type", "TD")),
                     "Secondary_Subject": ";".join(secs), "Secondary_Type": str(g("Secondary_Type", "TD")),
                     "Block_Len": L, "Sec_Hours": ";".join(map(str, sh)), "Frequency": f, "Sessions": sessions,
                     "Back_To_Back": b2b, "Coupling_Mode": mode, "Problems": ";".join(probs)})
    return pd.DataFrame(rows, columns=cols)


def split_rule_hours(rule):
    """Weekly teacher hours per subject created by ONE class following this rule, and class slots used."""
    L, f, S = int(rule["Block_Len"]), int(rule["Frequency"]), int(rule["Sessions"])
    secs, sh = _split_list(rule["Secondary_Subject"]), _int_list(rule["Sec_Hours"])
    reps = 2 if rule["Back_To_Back"] else S                 # sessions per week (a 2h back-to-back block = 2 × 1h)
    hours = {rule["Primary_Subject"]: L * reps}
    for s_, h in zip(secs, sh):
        hours[s_] = hours.get(s_, 0) + h * reps
    return hours, L * reps


class SchoolDataLoader:
    def __init__(self, paths):
        # each entry may be a file path / file-like object or an already-loaded DataFrame
        rd = lambda k: paths[k].copy() if isinstance(paths[k], pd.DataFrame) else pd.read_csv(paths[k])
        self.df_teachers = rd('teachers').fillna('')
        self.df_classes = rd('classes')
        self.df_subjects = rd('subjects')
        self.df_inspections = rd('inspections')
        self.df_rooms = rd('rooms')
        self.df_rules = normalize_split_rules(rd('rules'))
        self.df_grid = rd('grid') if 'grid' in paths and paths['grid'] is not None else pd.DataFrame()

class SchedulerConfig:
    def __init__(self):
        self.days = 5
        self.slots = 7
        self.lunch_boundary = 3
        self.closed_halfdays = [[2, "afternoon"]]   # [[day, "morning"|"afternoon"]] (preset: time profile)
        self.level_profiles = {}                    # {level: {"slots": n, "closed": [[day, half]]}} levels with their own week
        self.teacher_unavailable = {}               # {teacher: [[day, period], ...]} hard (availability table)
        self.teacher_avoid = {}                     # {teacher: [[day, period], ...]} soft
        self.teacher_avoid_cost = 300               # per lesson-hour placed in an "avoid" time

        # Hard Constraints
        self.allow_student_gaps = False
        self.allow_same_subject_twice_per_day = False

        self.enforce_max_2h_courses_per_day = True
        self.max_2h_courses_per_day = 1

        # Soft Constraints
        self.teacher_single_hour_weight = 900
        self.teacher_single_gap_weight = 300
        self.teacher_double_gap_weight = 800
        self.teacher_working_day_weight = 10
        self.reception_in_gap_reward = 1

        self.slot_1_penalty = 0   # was 10; conflicted with morning-first
        self.slot_4_penalty = 50
        self.slot_5_penalty = 25
        self.slot_7_penalty = 500
        self.slot_7_equity_penalty = 900

        # Morning-first policy
        self.morning_first_hard = False         # (optional hard rule) class may use an afternoon only if that day's morning is full
        # Standard class grid (highest priority): 5 mornings × 4 slots (20h) + 4 afternoons × first 2 slots (8h);
        # every hour above 28 = one day with a 7th slot.  An afternoon is always filled from its first slot.
        # Standard class grid = filling order (SOFT, very high priority): mornings first, then the first 2
        # afternoon slots, then extra afternoon slots (7th hour), avoiding no_slot7_days.  Soft so that the
        # same engine works for schools without lunch break or tracks with fewer hours.
        self.strict_class_grid = True
        self.grid_cost_afternoon = 5000         # per class-hour placed in the first 2 afternoon slots
        self.grid_cost_extra = 15000            # per class-hour placed after them (7th slot …)
        self.grid_cost_bad_day = 40000          # extra, per class-hour in the 7th slot on no_slot7_days
        self.no_slot7_days = [4]                # 4 = Thursday
        self.grid_phase_share = 0.6             # share of the time given to phase 1 (grid only)
        # Remediation (الاستدراك): teacher-only sessions, preferably at the end of the day
        self.remedial_cost_morning = 30
        self.remedial_cost_afternoon = 10
        self.remedial_slot7_cost = 50           # remediation in slot 7 instead of slot 6
        self.remedial_gap_cost = 400            # remediation hour not preceded by a lesson of the teacher
        self.remedial_groups = []                   # from the preset's remedial template (e.g. ARABIC+MATH)
        self.same_day_exempt = []
        self.joint_sessions = []                    # [{"id","classes":[..],"subjects":[..],"hours":h,"block":1|2}] shared sessions
        self.remedial_periods = None                # allowed remedial periods (None = last two); from the remedial template
        self.remedial_ends_day = True               # a remedial session before the last period ends the classes' day                   # subjects allowed twice a day in the editor check (preset)
        self.remedial_units_manual = None       # [{'teachers': [...], 'fixed': [day, slot] or None}] set before solving
        self.fixed_lessons = {}                 # {lesson key (see lesson_keys): [day, slot]} e.g. external teachers   # remediation subjects sharing ONE session (students split in groups)
        self.remedial_group_cost = 3000         # grouped sessions not at the same time
        self.remedial_overlap_cost = 20000      # sessions of different groups overlapping for a class
        self.empty_morning_slot_penalty = 400   # per empty morning slot (class) -> pushes lessons into mornings
        self.teacher_afternoon_penalty = 20     # per teacher afternoon hour -> teachers' work packed in mornings

        # Teacher fairness: teachers with more weekly hours get better timetables
        self.teacher_late_finish_weight = 40    # per day × index of the teacher's last slot (earlier finish = better)
        self.teacher_priority_strength = 3      # comfort weights × this factor for the most loaded teacher (×1 for the lightest)
        self.priority_levels_share = 0.0        # 0 = priority from hours only; 0.5 = half hours, half number of levels taught
        self.teacher_shift_weight = 0           # cost of each worked half-day (shift); 0 = off (working days only)
        self.teacher_windows_hard = True        # teachers are unavailable during their subject's pedagogical windows

        self.max_time_seconds = 60
        self.room_fallback = {'lab': 'classroom'}   # a lesson needing a lab may use a free classroom
        self.num_workers = 8
        try:                                     # defaults come from the server preset (presets/*.json)
            import presets as _pr
            _pr.apply_to_config(self)
        except FileNotFoundError:
            pass

def rem_info(assignment, remedial, valid, known):
    """{teacher: {'classes', 'subject', 'hours'}} for the teachers with remediation hours."""
    info = {}
    for tch, h in (remedial or {}).items():
        try:
            h = int(float(h))
        except (TypeError, ValueError):
            continue
        if tch not in known or h <= 0:
            continue
        rows_t = assignment[assignment['Teacher'] == tch]
        cls = {c for c in rows_t['Class'] if c in valid}
        if not cls:
            continue
        m = rows_t['Subject'].astype(str).str.split('_').str[0].mode()
        info[tch] = {'classes': cls, 'subject': str(m.iloc[0]) if len(m) else '', 'hours': h}
    return info


def lesson_keys(lessons):
    """Stable keys 'teacher|class|subject|duration|k' for every (lesson, teacher) – used to fix lessons by hand."""
    seen, out = {}, {}
    for l in lessons:
        if l.get('remedial'):
            continue
        for tc in l['teachers']:
            base = f"{tc}|{l['class']}|{l['subject']}|{l['duration']}"
            k = seen.get(base, 0); seen[base] = k + 1
            out.setdefault(l['id'], []).append(f"{base}|{k}")
    return out


def rem_group_units(info, groups):
    """Remediation units.  info: {teacher: {'classes': set, 'subject': str}}.
    Teachers of one group (e.g. ARABIC+MATH, alternating weekly) that are LINKED through shared classes form ONE unit
    = one common hour: each teacher has one session per week and every class gets exactly one session, with its own
    teachers.  Teachers outside any group (or without a partner) get their own session."""
    units, used = [], set()
    for g in [set(x) for x in (groups or []) if len(x) > 1]:
        members = sorted([tc for tc, v in info.items() if v['subject'] in g], key=str)
        seen = set()
        for start in members:
            if start in seen:
                continue
            comp, stack = [], [start]
            seen.add(start)
            while stack:                                  # connected component through shared classes
                a = stack.pop(); comp.append(a)
                for b in members:
                    if b not in seen and info[a]['classes'] & info[b]['classes']:
                        seen.add(b); stack.append(b)
            if len({info[tc]['subject'] for tc in comp}) > 1:
                units.append(sorted(comp, key=str)); used.update(comp)
    units += [[tc] for tc in sorted(info, key=str) if tc not in used]
    return units


def rem_rooms(unit, info):
    """Rooms needed by a unit at its hour: the largest number of teachers of one subject (they teach at the same time)."""
    from collections import Counter
    return max(Counter(info[tc]['subject'] for tc in unit).values())


class SchoolSchedulerEngine:
    def __init__(self, data: SchoolDataLoader, config: SchedulerConfig, fixed_assignment=None):
        # fixed_assignment: optional DataFrame (Teacher, Class, Subject) imported from the school's
        # assignment matrix. When given, the automatic teacher-assignment step is skipped.
        self.fixed_assignment = fixed_assignment
        self.remedial = {}                      # {teacher/post: weekly remediation hours} (الاستدراك)
        self.data = data
        self.config = config
        self.G = timegrid.set_current(timegrid.from_config(config))   # days / periods / lunch / closed half-days
        self.model = cp_model.CpModel()
        self.x = {}
        self.class_active = {}
        self.teacher_active = {}
        self.lessons = []
        self.assignment = None
        self.objective_score = None
        self.penalties = []
        self.placements = {}
        self.kpi_terms = {}               # name -> list of model terms; used by improve() (goals and guards)

    def capacity_issues(self):
        """Impossible weeks, found BEFORE solving: a class needing more hours than its level's week has, or a
        teacher with more hours than his available cells.  -> [{"kind", "who", "need", "have"}]"""
        G, out = self.G, []
        cls_lv = dict(zip(self.data.df_classes['Class_ID'].astype(str), self.data.df_classes['Level'].astype(str)))
        need_c, need_t = {}, {}
        for l in self.lessons:
            for c in {str(l['class'])} | {str(k) for k in l.get('blocks_classes', [])} | {str(k) for k in l.get('also_classes', [])}:
                if c in cls_lv:
                    need_c[c] = need_c.get(c, 0) + l['duration']
            for tc in l['teachers']:
                need_t[tc] = need_t.get(tc, 0) + l['duration']
        for c, n in need_c.items():
            have = sum(1 for d in range(G.days) for s_ in range(G.slots) if not G.is_off(d, s_, cls_lv[c]))
            if n > have:
                out.append({"kind": "class", "who": c, "need": n, "have": have})
        un = {tc: {tuple(x) for x in v} for tc, v in (getattr(self.config, 'teacher_unavailable', None) or {}).items()}
        win = getattr(self, 't_windows', {}) or {}
        for tc, n in need_t.items():
            have = sum(1 for d in range(G.days) for s_ in range(G.slots)
                       if not G.is_off(d, s_) and (d, s_) not in un.get(tc, ()) and (d, s_) not in win.get(tc, ()))
            if n > have:
                out.append({"kind": "teacher", "who": tc, "need": n, "have": have})
        return out

    def build_model(self, generate=True):
        if generate:
            self._generate_lessons_and_assignments()
        self._apply_fixed_lessons()
        self._create_variables()
        self._add_core_constraints()

        if not self.config.allow_student_gaps: self._add_student_gap_constraints()
        if not self.config.allow_same_subject_twice_per_day: self._add_pedagogical_spreading()
        if self.config.enforce_max_2h_courses_per_day: self._add_2h_course_limits()

        self._add_teacher_comfort_constraints()
        self._add_remedial_day_end()
        if not getattr(self.config, 'strict_class_grid', False):   # the grid already fixes slot-7 counts
            self._add_class_equity_constraints()
        self._add_morning_first_policy()
        self._build_objective_function()

    def solve(self, progress=None):
        """With the standard class grid: lexicographic, still SOFT.
           Phase 1 – minimize only the grid cost (the timetable closest to the perfect student grid),
           Phase 2 – keep that grid quality (grid cost ≤ phase-1 value) and optimize everything else,
                     starting from the phase-1 timetable.
        Total time = config.max_time_seconds (phase 1 gets grid_phase_share of it)."""
        import time as _time
        T = float(self.config.max_time_seconds)
        self.phase_info = {}
        start = _time.time()
        s1 = None
        grid = getattr(self, 'grid_terms', None)
        if getattr(self.config, 'strict_class_grid', False) and grid:
            self.model.Minimize(sum(grid))
            s1 = cp_model.CpSolver()
            s1.parameters.max_time_in_seconds = max(5.0, T * getattr(self.config, 'grid_phase_share', 0.5))
            s1.parameters.num_search_workers = self.config.num_workers
            st1 = s1.Solve(self.model)
            self.phase_info['phase1'] = (s1.StatusName(st1), round(s1.WallTime(), 1))
            if st1 == cp_model.INFEASIBLE:
                self.status_name = s1.StatusName(st1)
                self.model.Minimize(sum(self.penalties))
                return None
            if st1 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                self.grid_cost = int(s1.ObjectiveValue())
                self.model.Add(sum(grid) <= self.grid_cost)
                self.model.ClearHints()
                for v in self.x.values():
                    self.model.AddHint(v, s1.Value(v))
            else:
                s1 = None             # phase 1 found nothing in its time: phase 2 gets the rest of the time
            self.model.Minimize(sum(self.penalties))
            if progress: progress(1)
        remaining = max(5.0, T - (_time.time() - start))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = remaining
        solver.parameters.num_search_workers = self.config.num_workers
        status = solver.Solve(self.model)
        self.status_name = solver.StatusName(status)
        self.phase_info['phase2'] = (solver.StatusName(status), round(solver.WallTime(), 1))
        best = solver if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else s1
        if best is None:
            return None
        if best is s1:
            self.status_name = "FEASIBLE"
            self.objective_score = None
        else:
            self.objective_score = solver.ObjectiveValue()
        self.placements = {lid: (d, sl) for (lid, d, sl), v in self.x.items() if best.Value(v) == 1}
        return self.place_remedial(self._extract_schedule(best))

    # ---------------------------------------------------------------- remediation (after the timetable is done)
    def place_remedial(self, sched):
        """الاستدراك – placed AFTER the timetable is finished.
        One session per teacher for ALL his classes (the teacher divides his students himself).  Teachers of a
        remediation group (e.g. ARABIC+MATH) sharing classes get ONE common session: free for both teachers and all
        their classes, whatever the level.  Slot 6 is tried first (no extra 7th hour), then slot 7."""
        self.remedial_report, self.remedial_domains = [], {}
        if sched is None or not self.remedial or self.assignment is None:
            return sched
        reserved = [l for l in self.lessons if l.get('remedial') and l['id'] in self.placements]
        if reserved:
            placed = {tc for l in reserved for tc in l['teachers']}
            for l in reserved:
                d, s0 = self.placements[l['id']]
                self.remedial_report.append({'Teachers': ' + '.join(l['teachers']), 'Status': 'ok', 'Day': d, 'Slot': s0,
                                             'Classes': ', '.join(l['blocks_classes'])})
            for unit, classes, subj, n in self.remedial_units():
                if not set(unit) & placed:
                    self.remedial_report.append({'Teachers': ' + '.join(unit), 'Status': 'none'})
            return sched
        cfg, lb = self.config, self.config.lunch_boundary
        valid = set(self.data.df_classes['Class_ID'])
        known = set(self.data.df_teachers['Teacher_ID'])
        info = {}
        for tch, h in self.remedial.items():
            if tch not in known or int(h) <= 0:
                continue
            rows_t = self.assignment[self.assignment['Teacher'] == tch]
            cls = {c for c in rows_t['Class'] if c in valid}
            if not cls:
                continue
            m = rows_t['Subject'].astype(str).str.split('_').str[0].mode()
            info[tch] = {'classes': cls, 'subject': str(m.iloc[0]) if len(m) else '', 'hours': int(h)}
        # --- units: pairs (or n-tuples) of teachers of one group sharing the most classes, else single teachers
        units = rem_group_units(info, getattr(cfg, 'remedial_groups', []))
        # --- occupancy of the finished timetable
        busy_c, busy_t, room = set(), set(), {}
        for r in sched.itertuples():
            busy_c.add((r.Class, r.Day, r.Slot))
            for tc in str(r.Teachers).split(', '):
                busy_t.add((tc, r.Day, r.Slot))
        for l in self.lessons:
            if l['id'] in self.placements:
                d, s0 = self.placements[l['id']]
                for k in range(l['duration']):
                    room[(d, s0 + k)] = room.get((d, s0 + k), 0) + l['rooms'].get('classroom', 0)
                    lab_over = room.setdefault(('lab', d, s0 + k), 0) + l['rooms'].get('lab', 0)
                    room[('lab', d, s0 + k)] = lab_over
        _caps = self.room_caps()
        if 'lab' in (getattr(cfg, 'room_fallback', {}) or {}):
            for key in [k for k in room if k[0] == 'lab']:
                room[key[1:]] = room.get(key[1:], 0) + max(0, room[key] - _caps.get('lab', 0))
        cap = int(_caps.get('classroom', 999))
        win = self._teacher_windows()
        days_aft = [d for d in range(cfg.days) if d != 2]           # Tuesday afternoon is off
        slot_order = [cfg.slots - 2, cfg.slots - 1]                 # slot 6 first, then slot 7

        rem_c = set()
        def free_days(teachers, classes, s):
            out = []
            for d in days_aft:
                if any((tc, d, s) in busy_t or (d, s) in win.get(tc, set()) for tc in teachers): continue
                if any((c, d, s) in busy_c for c in classes): continue
                if room.get((d, s), 0) + rem_rooms(teachers, info) > cap: continue   # alternating weekly: rooms = teachers of one subject
                if s == cfg.slots - 2 and any((c, d, s + 1) in busy_c or (c, d, s + 1) in rem_c for c in classes): continue
                if s == cfg.slots - 1 and any((c, d, s - 1) in rem_c for c in classes): continue   # slot-6 remediation ends the day
                out.append(d)
            return out

        def place(teachers):
            classes = set().union(*(info[tc]['classes'] for tc in teachers))
            for s in slot_order:
                ds = free_days(teachers, classes, s)
                if ds:
                    # prefer no teacher gap (teachers teach the hour before), then the least used day
                    d = max(ds, key=lambda d: (sum((tc, d, s - 1) in busy_t for tc in teachers), -room.get((d, s), 0), -d))
                    return d, s, classes
            return None

        rows, l_idx = [], 0
        queue = [list(u) for u in units]
        while queue:
            unit = queue.pop(0)
            n = min(info[tc]['hours'] for tc in unit)
            for _ in range(n):
                res = place(unit)
                if res is None:
                    if len(unit) > 1:                                  # no common hour for the group -> separately
                        queue += [[tc] for tc in unit]
                        self.remedial_report.append({'Teachers': ' + '.join(unit), 'Status': 'split'})
                    else:
                        self.remedial_report.append({'Teachers': unit[0], 'Status': 'none',
                                                     'Classes': ', '.join(sorted(info[unit[0]]['classes'], key=str))})
                    break
                d, s, classes = res
                lid = f"R_{l_idx}"; l_idx += 1
                subj = '+'.join(dict.fromkeys(info[tc]['subject'] for tc in unit))
                lesson = {'id': lid, 'class': f"{REM_PREFIX}{'+'.join(unit)}", 'teachers': list(unit), 'subject': 'REMEDIAL',
                          'duration': 1, 'rooms': {'classroom': rem_rooms(unit, info)}, 'remedial': True,
                          'blocks_classes': sorted(classes, key=str), 'rem_subject': subj}
                self.lessons.append(lesson); self.placements[lid] = (d, s)
                rem_c.update((c, d, s) for c in classes)
                self.remedial_domains[lid] = [[dd, ss] for dd in days_aft for ss in (cfg.slots - 2, cfg.slots - 1)]
                for c in classes: busy_c.add((c, d, s))
                for tc in unit: busy_t.add((tc, d, s))
                room[(d, s)] = room.get((d, s), 0) + len(unit)
                rows.append({'Class': lesson['class'], 'Day': d, 'Slot': s, 'Subject': 'REMEDIAL',
                             'Teachers': ', '.join(unit), 'Classes': ', '.join(lesson['blocks_classes']), 'RemSubject': subj})
                self.remedial_report.append({'Teachers': ' + '.join(unit), 'Status': 'ok', 'Day': d, 'Slot': s,
                                             'Classes': ', '.join(lesson['blocks_classes'])})
            else:
                continue
        return pd.concat([sched, pd.DataFrame(rows)], ignore_index=True) if rows else sched

    def _open_days(self, subj):
        """Days on which `subj` still has at least one usable slot (pedagogical windows + Tuesday afternoon off)."""
        n = 0
        for d in range(self.config.days):
            slots = set(self.G.open_slots(d))
            insp = self.data.df_inspections[(self.data.df_inspections['Subject_Code'] == subj) & (self.data.df_inspections['Day_Index'] == d)]
            for _, row in insp.iterrows():
                slots -= {int(b) for b in str(row['Blocked_Slots']).split(';') if str(b).strip() != ''}
            if getattr(self.config, 'strict_class_grid', False):
                # with the standard grid, afternoons are scarce (2 slots): a day whose whole morning is blocked
                # is not counted, so the subject gets a 2h block instead of needing that afternoon
                slots &= set(range(self.config.lunch_boundary + 1))
            n += bool(slots)
        return n

    def _rule_applies(self, rule, c_lvl):
        """Rule is used for this level only if its level matches AND every subject of the rule exists there."""
        levels = str(rule['Level']).split(';')
        if 'ALL' not in levels and c_lvl not in levels:
            return False
        subs = set(self.data.df_subjects[self.data.df_subjects['Level'] == c_lvl]['Subject_Code'])
        return rule['Primary_Subject'] in subs and all(x in subs for x in _split_list(rule['Secondary_Subject']))

    def _calculate_required_hours(self, c_lvl, subj_code):
        s_row = self.data.df_subjects[(self.data.df_subjects['Level'] == c_lvl) & (self.data.df_subjects['Subject_Code'] == subj_code)]
        if s_row.empty: return 0
        s_row = s_row.iloc[0]
        hrs_cours, td_tp_hrs, rule_applied = int(s_row['Hrs_Cours']), 0, False
        for _, rule in self.data.df_rules.iterrows():
            if not self._rule_applies(rule, c_lvl): continue
            hrs, _ = split_rule_hours(rule)
            if subj_code in hrs:
                td_tp_hrs = hrs[subj_code]; rule_applied = True; break
        if not rule_applied: td_tp_hrs = int(s_row['Hrs_TD'] + s_row['Hrs_TP'] + s_row['Hrs_Practice'])
        return hrs_cours + td_tp_hrs

    def _generate_lessons_and_assignments(self):
        supported_subjs = set(s for qs in self.data.df_teachers['Qualified_Subjects'] for s in str(qs).split(';'))
        if self.fixed_assignment is not None:
            self.assignment = self.fixed_assignment[['Teacher', 'Class', 'Subject']].reset_index(drop=True)
            supported_subjs |= set(self.assignment['Subject'])
        else:
            model = cp_model.CpModel()
            classes = self.data.df_classes['Class_ID'].tolist()
            supported_subjs = set(s for qs in self.data.df_teachers['Qualified_Subjects'] for s in str(qs).split(';'))
            x_assign = {}
            for _, t in self.data.df_teachers.iterrows():
                t_id = t['Teacher_ID']
                for c in classes:
                    c_lvl = self.data.df_classes[self.data.df_classes['Class_ID'] == c]['Level'].iloc[0]
                    for s in str(t['Qualified_Subjects']).split(';'):
                        if s in supported_subjs and not self.data.df_subjects[(self.data.df_subjects['Level'] == c_lvl) & (self.data.df_subjects['Subject_Code'] == s)].empty:
                            x_assign[t_id, c, s] = model.NewBoolVar(f"xa_{t_id}_{c}_{s}")
            for c in classes:
                c_lvl = self.data.df_classes[self.data.df_classes['Class_ID'] == c]['Level'].iloc[0]
                for s in self.data.df_subjects[self.data.df_subjects['Level'] == c_lvl]['Subject_Code']:
                    if s not in supported_subjs: continue
                    possible_t = [t['Teacher_ID'] for _, t in self.data.df_teachers.iterrows() if s in str(t['Qualified_Subjects']).split(';')]
                    if possible_t: model.AddExactlyOne([x_assign[t, c, s] for t in possible_t if (t, c, s) in x_assign])
            overflow = model.NewIntVar(0, 50, "overflow")
            for _, t in self.data.df_teachers.iterrows():
                t_id, max_hrs = t['Teacher_ID'], t['Max_Weekly_Hours']
                t_hrs = [x_assign[t_id, c, s] * self._calculate_required_hours(self.data.df_classes[self.data.df_classes['Class_ID'] == c]['Level'].iloc[0], s)
                         for c in classes for s in str(t['Qualified_Subjects']).split(';') if (t_id, c, s) in x_assign]
                model.Add(sum(t_hrs) <= int(max_hrs) + overflow)
            model.Minimize(overflow)
            solver = cp_model.CpSolver()
            if solver.Solve(model) in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                self.assignment = pd.DataFrame([{'Teacher': t, 'Class': c, 'Subject': s} for (t, c, s), var in x_assign.items() if solver.Value(var) == 1])
            else: raise Exception(__import__("i18n").t("assign_failed"))

        l_idx = 0
        joint_cover = self._make_joint_sessions()         # {(class, subject)} whose course hours are a joint session
        def _get_room(lvl, subj):
            row = self.data.df_subjects[(self.data.df_subjects['Level'] == lvl) & (self.data.df_subjects['Subject_Code'] == subj)]
            return row.iloc[0]['Required_Room_Type'] if not row.empty else 'classroom'

        for _, c_row in self.data.df_classes.iterrows():
            c_id, c_lvl = c_row['Class_ID'], c_row['Level']
            df_l = self.data.df_subjects[self.data.df_subjects['Level'] == c_lvl]
            def get_teacher(subj):
                t = self.assignment[(self.assignment['Class'] == c_id) & (self.assignment['Subject'] == subj)]
                return t['Teacher'].iloc[0] if not t.empty else None

            # 🌟 NEW: Track exactly how many days a subject has been scheduled to calculate overflow
            subject_days_used = {}
            def mark_used(subj_str, course=False):
                if not course: return   # TD/TP/split sessions may share a day with a course
                for s in subj_str.replace('_TD', '').replace('_TP', '').replace('_Pract/TD', '').replace('_TD/TP', '').split('+'):
                    subject_days_used[s] = subject_days_used.get(s, 0) + 1

            consumed_td_tp = set()

            # 1. SPLIT RULES (FOUJ) – generic: one session = Block_Len hours; the primary teacher stays all along,
            #    the secondary teachers follow each other (Sec_Hours, in order).  Sessions per week from Frequency.
            for _, rule in self.data.df_rules.iterrows():
                if not self._rule_applies(rule, c_lvl): continue
                p_subj = rule['Primary_Subject']
                secs, sh = _split_list(rule['Secondary_Subject']), _int_list(rule['Sec_Hours'])
                t_p = get_teacher(p_subj)
                t_s = [get_teacher(x) for x in secs]
                if not t_p or not all(t_s): continue
                r_p = _get_room(c_lvl, p_subj)
                suffix = "_TD/TP" if len(secs) == 1 else "_TD"
                for sess in range(int(rule['Sessions'])):
                    if len(secs) == 1:
                        dur = 2 if rule['Back_To_Back'] else int(rule['Block_Len'])
                        r_s = _get_room(c_lvl, secs[0])
                        rooms = {r_p: 1}; rooms[r_s] = rooms.get(r_s, 0) + 1
                        self.lessons.append({'id': f"L_{l_idx}", 'class': c_id, 'teachers': [t_p, t_s[0]],
                                             'subject': f"{p_subj}+{secs[0]}{suffix}", 'duration': dur, 'rooms': rooms,
                                             'rule': rule['Rule_ID']})
                        l_idx += 1
                    else:
                        ids = [f"L_{l_idx + k}" for k in range(len(secs))]; l_idx += len(secs)
                        total, off = int(sum(sh)), 0
                        for k, (s_k, t_k, h_k) in enumerate(zip(secs, t_s, sh)):
                            r_s = _get_room(c_lvl, s_k)
                            rooms = {r_p: 1}; rooms[r_s] = rooms.get(r_s, 0) + 1
                            les = {'id': ids[k], 'class': c_id, 'teachers': [t_p, t_k], 'subject': f"{p_subj}+{s_k}{suffix}",
                                   'duration': int(h_k), 'rooms': rooms, 'rule': rule['Rule_ID'],
                                   'chain_offset': off, 'chain_total': total, 'chain_primary': p_subj}
                            if k + 1 < len(secs): les['linked_next'] = ids[k + 1]
                            if k > 0: les['linked_prev'] = ids[k - 1]
                            self.lessons.append(les); off += int(h_k)
                    mark_used(p_subj)
                    for x in secs: mark_used(x)
                consumed_td_tp.update([p_subj] + secs)

            # 2. STANDALONE TD/TP/PRACTICE
            for _, s_row in df_l.iterrows():
                subj = s_row['Subject_Code']
                if subj not in supported_subjs: continue
                t_id = get_teacher(subj)
                if not t_id: continue
                r_type = s_row['Required_Room_Type']
                if subj not in consumed_td_tp:
                    hrs_extra = int(s_row['Hrs_TD'] + s_row['Hrs_TP'] + s_row['Hrs_Practice'])
                    dur = 2 if hrs_extra >= 2 else 1
                    while hrs_extra > 0:
                        d = min(dur, hrs_extra)
                        self.lessons.append({'id': f"L_{l_idx}", 'class': c_id, 'teachers': [t_id], 'subject': f"{subj}_Pract/TD", 'duration': d, 'rooms': {r_type: 1}})
                        l_idx += 1; hrs_extra -= d
                        mark_used(subj)

            # 3. 🌟 NEW: DYNAMIC COURS (Pigeonhole Allocation Algorithm)
            for _, s_row in df_l.iterrows():
                subj = s_row['Subject_Code']
                if subj not in supported_subjs: continue
                t_id = get_teacher(subj)
                if not t_id: continue

                hrs_cours = int(s_row['Hrs_Cours'])
                r_type = s_row['Required_Room_Type']
                if (str(c_id), subj) in joint_cover: continue        # taught in a joint session (template)
                if hrs_cours <= 0: continue

                # Calculate how many days we have left for this subject
                avail_days = self._open_days(subj) - subject_days_used.get(subj, 0)
                if avail_days <= 0: avail_days = 1 # Fallback safeguard

                # Bundle into 2-Hour blocks ONLY if forced by math
                while hrs_cours > avail_days and hrs_cours >= 2:
                    self.lessons.append({'id': f"L_{l_idx}", 'class': c_id, 'teachers': [t_id], 'subject': subj, 'duration': 2, 'rooms': {r_type: 1}})
                    l_idx += 1; hrs_cours -= 2; avail_days -= 1
                    mark_used(subj, True)

                # Schedule the rest as pure 1-Hour blocks!
                while hrs_cours > 0:
                    d = 2 if (avail_days <= 0 and hrs_cours >= 2) else 1
                    self.lessons.append({'id': f"L_{l_idx}", 'class': c_id, 'teachers': [t_id], 'subject': subj, 'duration': d, 'rooms': {r_type: 1}})
                    l_idx += 1; hrs_cours -= d; avail_days -= 1
                    mark_used(subj, True)


        # 4. REMEDIATION (الاستدراك) – one session per teacher (or teacher group, e.g. ARABIC+MATH) for ALL their
        #    classes, at an hour free for the teacher(s) and every one of those classes.  Slot 6 if the timetable leaves
        #    it free for all of them (no extra hour), otherwise slot 7.  The solver reserves that hour while building.
        l_idx = 0
        for unit, classes, subj, n in self.remedial_units():
            for k in range(n):
                self.lessons.append({'id': f"R_{l_idx}", 'class': f"{REM_PREFIX}{'+'.join(unit)}", 'teachers': list(unit),
                                     'subject': 'REMEDIAL', 'duration': 1, 'rooms': {'classroom': self._rem_rooms.get(tuple(unit), 1)}, 'remedial': True,
                                     'blocks_classes': sorted(classes, key=str), 'rem_subject': subj,
                                     **({'fixed': self._rem_fixed[tuple(unit)]} if tuple(unit) in getattr(self, '_rem_fixed', {}) and k == 0 else {})})
                l_idx += 1

    def _make_joint_sessions(self):
        """Joint sessions (templates): ONE session shared by several classes, with one or more subjects taught in
        parallel (merged classes, option groups).  It counts as class time for every class in it; teachers come from
        the assignment (all teachers of those subjects in those classes); one room per subject group.
        Returns {(class, subject)} whose course hours are replaced by the template."""
        cover = set()
        self.joint_warnings = []
        cls_lv = dict(zip(self.data.df_classes['Class_ID'].astype(str), self.data.df_classes['Level'].astype(str)))
        n = 0
        for tp in getattr(self.config, 'joint_sessions', None) or []:
            classes = [str(c) for c in tp.get('classes', []) if str(c) in cls_lv]
            subjects = [str(x) for x in tp.get('subjects', [])]
            hours, block = int(tp.get('hours', 0) or 0), max(1, int(tp.get('block', 1) or 1))
            if len(classes) < 1 or not subjects or hours <= 0:
                self.joint_warnings.append((tp.get('id'), 'incomplete'))
                continue
            teachers, rooms = [], {}
            for sj in subjects:
                a = self.assignment[(self.assignment['Class'].astype(str).isin(classes)) & (self.assignment['Subject'] == sj)]
                tl = list(dict.fromkeys(a['Teacher']))
                if not tl:
                    self.joint_warnings.append((tp.get('id'), f'no teacher for {sj}'))
                for tc in tl:
                    if tc not in teachers:
                        teachers.append(tc)
                    row = self.data.df_subjects[(self.data.df_subjects['Subject_Code'] == sj)
                                                & (self.data.df_subjects['Level'] == cls_lv[classes[0]])]
                    rt = row.iloc[0]['Required_Room_Type'] if not row.empty else 'classroom'
                    rooms[rt] = rooms.get(rt, 0) + 1
                for c in classes:
                    row = self.data.df_subjects[(self.data.df_subjects['Subject_Code'] == sj) & (self.data.df_subjects['Level'] == cls_lv[c])]
                    if row.empty or int(row.iloc[0]['Hrs_Cours']) != hours:
                        self.joint_warnings.append((tp.get('id'), f'{c}/{sj}: curriculum course hours differ from {hours}'))
                    cover.add((c, sj))
            if not teachers:
                continue
            left = hours
            while left > 0:
                d = min(block, left)
                self.lessons.append({'id': f"J_{n}", 'class': classes[0], 'also_classes': classes[1:], 'teachers': teachers,
                                     'subject': '+'.join(subjects), 'duration': d, 'rooms': rooms, 'joint': tp.get('id')})
                n += 1; left -= d
        return cover

    # =========================================================
    # REMAINDER OF THE SOLVER (Constraints, Extractor, etc.)
    # =========================================================
    def remedial_units(self):
        """[(teachers, classes, subject_label, hours)] – one unit = ONE remediation session for the teacher(s) and ALL
        their classes.  Teachers of a group (e.g. ARABIC+MATH) are paired by the most shared classes (global greedy)."""
        if not self.remedial or self.assignment is None:
            return []
        valid = set(self.data.df_classes['Class_ID']); known = set(self.data.df_teachers['Teacher_ID'])
        info = rem_info(self.assignment, self.remedial, valid, known)
        self._rem_fixed = {}
        manual = getattr(self.config, 'remedial_units_manual', None)
        if manual:
            units, used = [], set()
            for u in manual:
                tt = [tc for tc in u.get('teachers', []) if tc in info and tc not in used]
                if tt:
                    units.append(tt); used.update(tt)
                    if u.get('fixed'):
                        self._rem_fixed[tuple(tt)] = tuple(int(v) for v in u['fixed'])
            units += [[tc] for tc in sorted(info, key=str) if tc not in used]
            self._rem_rooms = {tuple(u): rem_rooms(u, info) for u in units}
            out = []
            for u in units:
                out.append((u, set().union(*(info[tc]['classes'] for tc in u)),
                            '+'.join(dict.fromkeys(info[tc]['subject'] for tc in u)), min(info[tc]['hours'] for tc in u)))
            return out
        units = rem_group_units(info, getattr(self.config, 'remedial_groups', []))
        self._rem_rooms = {tuple(u): rem_rooms(u, info) for u in units}
        out = []
        for u in units:
            out.append((u, set().union(*(info[tc]['classes'] for tc in u)),
                        '+'.join(dict.fromkeys(info[tc]['subject'] for tc in u)), min(info[tc]['hours'] for tc in u)))
        return out

    def remedial_group_of(self, subj):
        """Index of the remediation group containing this subject (config.remedial_groups), else a group of its own."""
        for i, g in enumerate(getattr(self.config, 'remedial_groups', []) or []):
            if subj in g:
                return f"G{i}"
        return f"S:{subj}"

    def _add_remedial_day_end(self):
        """A remediation session in slot 6 ends the day of all its classes: nothing in slot 7 (lesson or remediation)."""
        S = self.config.slots
        rem = [l for l in self.lessons if l.get('remedial')]
        if not rem or not getattr(self.config, 'remedial_ends_day', True):
            return
        for c in self.data.df_classes['Class_ID'].tolist():
            mine = [l for l in rem if c in l.get('blocks_classes', ())]
            if not mine:
                continue
            for d in range(self.config.days):
                r6 = [self.x[l['id'], d, S - 2] for l in mine if (l['id'], d, S - 2) in self.x]
                r7 = [self.x[l['id'], d, S - 1] for l in mine if (l['id'], d, S - 1) in self.x]
                if r6 and (c, d, S - 1) in self.class_active:
                    self.model.Add(sum(r6) + self.class_active[c, d, S - 1] + sum(r7) <= 1)

    def _add_remedial_grouping(self):
        """Remediation sessions sharing a class:
           * same group (e.g. ARABIC+MATH)  -> should be the SAME session (same day, same hour; students split in groups)
           * different groups               -> should not overlap (students cannot attend both)."""
        rem = [l for l in self.lessons if l.get('remedial')]
        cfg = self.config
        self.rem_overlap_terms = []
        for i, a in enumerate(rem):
            for b in rem[i + 1:]:
                if a['teachers'] == b['teachers'] or not (set(a['blocks_classes']) & set(b['blocks_classes'])):
                    continue
                cells = {(d, s) for (lid, d, s) in self.x if lid == a['id']} & {(d, s) for (lid, d, s) in self.x if lid == b['id']}
                if a['rem_group'] == b['rem_group']:
                    for d in range(cfg.days):
                        xa = [self.x[a['id'], d, s] for s in range(cfg.slots) if (a['id'], d, s) in self.x]
                        xb = [self.x[b['id'], d, s] for s in range(cfg.slots) if (b['id'], d, s) in self.x]
                        m = self.model.NewBoolVar(f"rgm_{a['id']}_{b['id']}_{d}")
                        self.model.Add(m >= sum(xa) - sum(xb))
                        self.penalties.append(m * cfg.remedial_group_cost)
                else:
                    for (d, s) in cells:
                        o = self.model.NewBoolVar(f"rov_{a['id']}_{b['id']}_{d}_{s}")
                        self.model.Add(o >= self.x[a['id'], d, s] + self.x[b['id'], d, s] - 1)
                        self.penalties.append(o * cfg.remedial_overlap_cost)
                        self.rem_overlap_terms.append(o)

    def _teacher_windows(self):
        """{teacher: {(day, slot), ...}} – pedagogical windows of the subjects each teacher teaches."""
        out = {}
        if self.assignment is None or self.data.df_inspections is None or self.data.df_inspections.empty:
            return out
        ins = self.data.df_inspections
        for tch, g in self.assignment.groupby('Teacher'):
            cells = set()
            for subj in set(g['Subject']):
                for _, row in ins[ins['Subject_Code'] == subj].iterrows():
                    for b in str(row['Blocked_Slots']).split(';'):
                        if str(b).strip() != '':
                            cells.add((int(row['Day_Index']), int(b)))
            if cells:
                out[tch] = cells
        return out

    def _teacher_loads(self):
        loads = {}
        for l in self.lessons:
            for tch in l['teachers']:
                loads[tch] = loads.get(tch, 0) + l['duration']
        return loads

    def priority_factor(self, tch):
        """1.0 for the least loaded teacher … teacher_priority_strength for the most loaded one."""
        loads = getattr(self, '_loads', None) or self._teacher_loads()
        if not loads:
            return 1.0
        lo, hi = min(loads.values()), max(loads.values())
        k = max(1.0, float(self.config.teacher_priority_strength))
        a = min(1.0, max(0.0, float(getattr(self.config, 'priority_levels_share', 0.0) or 0.0)))
        h = (loads.get(tch, lo) - lo) / (hi - lo) if hi > lo else 0.0
        if a == 0.0:
            return 1.0 + (k - 1.0) * h
        lv = getattr(self, '_levels', None)
        if lv is None:
            cl = dict(zip(self.data.df_classes['Class_ID'], self.data.df_classes['Level']))
            lv = {}
            for l in self.lessons:
                if not l.get('remedial'):
                    for t_ in l['teachers']:
                        lv.setdefault(t_, set()).add(cl.get(l['class']))
            lv = self._levels = {t_: len(v) for t_, v in lv.items()}
        l0, l1 = min(lv.values()), max(lv.values())
        g = (lv.get(tch, l0) - l0) / (l1 - l0) if l1 > l0 else 0.0
        return 1.0 + (k - 1.0) * ((1 - a) * h + a * g)

    def _apply_fixed_lessons(self):
        """Lessons fixed by the manager before solving (e.g. external teachers): {lesson key: [day, slot]}."""
        fx = getattr(self.config, 'fixed_lessons', None) or {}
        if not fx:
            return
        for lid, keys in lesson_keys(self.lessons).items():
            for k in keys:
                if k in fx:
                    l = next(x for x in self.lessons if x['id'] == lid)
                    l['fixed'] = tuple(int(v) for v in fx[k])
                    break

    def _lesson_levels(self, l):
        if not hasattr(self, '_cls_level'):
            self._cls_level = dict(zip(self.data.df_classes['Class_ID'].astype(str), self.data.df_classes['Level'].astype(str)))
        return [self._cls_level[c] for c in [str(l['class'])] + [str(k) for k in l.get('blocks_classes', [])]
                + [str(k) for k in l.get('also_classes', [])]
                if c in self._cls_level]

    def _create_variables(self):
        self.t_windows = self._teacher_windows() if self.config.teacher_windows_hard else {}
        t_off = {tc: {tuple(c) for c in v} for tc, v in (getattr(self.config, 'teacher_unavailable', None) or {}).items()}
        self._loads = self._teacher_loads()
        for l in self.lessons:
            l_id, dur = l['id'], l['duration']
            if l.get('fixed'):              # fixed by the manager: that hour only (may be inside a pedagogical window)
                d, s = l['fixed']
                if 0 <= s and s + dur <= self.config.slots:
                    self.x[l_id, d, s] = self.model.NewBoolVar(f"x_{l_id}_{d}_{s}")
                continue
            lvls = self._lesson_levels(l)
            for d in range(self.config.days):
                for s in range(self.config.slots):
                    if s + dur > self.config.slots: continue
                    if dur == 2 and s == self.config.lunch_boundary: continue
                    if self.G.off_span(d, s, dur, lvls): continue
                    if t_off and any((d, s + k) in t_off.get(tc, ()) for tc in l['teachers'] for k in range(dur)): continue
                    if l.get('remedial') and s not in (getattr(self.config, 'remedial_periods', None)
                                                       or range(self.config.slots - 2, self.config.slots)): continue
                    if 'chain_total' in l:
                        h0, h1 = s - l['chain_offset'], s - l['chain_offset'] + l['chain_total'] - 1
                        if h0 < 0 or h1 >= self.config.slots: continue
                        if h0 <= self.config.lunch_boundary < h1: continue          # never across the lunch break
                        if self.G.off_span(d, h0, h1 - h0 + 1, lvls): continue
                    conflict = False
                    for sub_subj in l['subject'].replace('_TD', '').replace('_TP', '').replace('_Pract/TD', '').replace('_TD/TP', '').split('+'):
                        insp = self.data.df_inspections[self.data.df_inspections['Subject_Code'] == sub_subj]
                        for _, row in insp[insp['Day_Index'] == d].iterrows():
                            blocked = [int(bs) for bs in str(row['Blocked_Slots']).split(';')]
                            if any((s + step) in blocked for step in range(dur)): conflict = True
                    if not conflict and self.t_windows:
                        for tch in l['teachers']:
                            w = self.t_windows.get(tch)
                            if w and any((d, s + step) in w for step in range(dur)): conflict = True
                    if conflict: continue
                    self.x[l_id, d, s] = self.model.NewBoolVar(f"x_{l_id}_{d}_{s}")

    def _add_core_constraints(self):
        for l in self.lessons:
            self.model.AddExactlyOne([self.x[l['id'], d, s] for d in range(self.config.days) for s in range(self.config.slots) if (l['id'], d, s) in self.x])
        for l in self.lessons:
            if 'linked_next' in l:
                l1_id, l2_id = l['id'], l['linked_next']
                for d in range(self.config.days):
                    off = l['duration']
                    for s in range(self.config.slots):
                        if (l1_id, d, s) in self.x and (l2_id, d, s + off) in self.x:
                            self.model.Add(self.x[l1_id, d, s] == self.x[l2_id, d, s + off])
                        elif (l1_id, d, s) in self.x:
                            self.model.Add(self.x[l1_id, d, s] == 0)

        classes = self.data.df_classes['Class_ID'].tolist()
        teachers = self.data.df_teachers['Teacher_ID'].tolist()

        for d in range(self.config.days):
            for s in range(self.config.slots):
                for c in classes:
                    c_lessons = [self.x[l['id'], d, s - step] for l in self.lessons if l['class'] == c or c in l.get('also_classes', ())
                                 for step in range(l['duration']) if (l['id'], d, s - step) in self.x]
                    blockers = [self.x[l['id'], d, s] for l in self.lessons if c in l.get('blocks_classes', ()) and (l['id'], d, s) in self.x]
                    expr = sum(c_lessons)
                    self.model.Add(expr + sum(blockers) <= 1)      # remediation: all the unit's classes free
                    b = self.model.NewBoolVar(f"ca_{c}_{d}_{s}")
                    self.model.Add(b == expr)
                    self.class_active[c, d, s] = b

                for t in teachers:
                    t_lessons = [self.x[l['id'], d, s - step] for l in self.lessons if t in l['teachers'] for step in range(l['duration']) if (l['id'], d, s - step) in self.x]
                    expr = sum(t_lessons)
                    self.model.Add(expr <= 1)
                    b = self.model.NewBoolVar(f"ta_{t}_{d}_{s}")
                    self.model.Add(b == expr)
                    self.teacher_active[t, d, s] = b

                self._add_room_limits(d, s)

    def room_caps(self):
        caps = {r['Room_Type']: int(r['Capacity']) for _, r in self.data.df_rooms.iterrows()}
        for l in self.lessons:
            for rt in l['rooms']:
                caps.setdefault(rt, 0)
        return caps

    def _add_room_limits(self, d, s):
        """Room pools per slot.  A type with a fallback (lab -> classroom) may overflow into free rooms of the
        fallback type: use[lab] + use[classroom] <= cap[lab] + cap[classroom] and use[classroom] <= cap[classroom]
        (exact for nested pools – the concrete rooms are allocated after solving)."""
        caps = self.room_caps()
        fb = getattr(self.config, 'room_fallback', {}) or {}
        use = {}
        for l in self.lessons:
            for step in range(l['duration']):
                v = self.x.get((l['id'], d, s - step))
                if v is None: continue
                for rt, n in l['rooms'].items():
                    use.setdefault(rt, []).append(v * n)
        for rt, cap in caps.items():
            if rt in use and rt not in fb:
                self.model.Add(sum(use[rt]) <= cap)
        for rt, to in fb.items():
            if rt in use:
                self.model.Add(sum(use[rt]) + sum(use.get(to, [])) <= caps.get(rt, 0) + caps.get(to, 0))

    def _add_2h_course_limits(self):
        classes = self.data.df_classes['Class_ID'].tolist()
        for c in classes:
            c_2h_courses = [l for l in self.lessons if l['class'] == c and l['duration'] == 2 and '+' not in l['subject'] and '_' not in l['subject']]
            for d in range(self.config.days):
                starts_today = [self.x[l['id'], d, s] for l in c_2h_courses for s in range(self.config.slots) if (l['id'], d, s) in self.x]
                if starts_today:
                    self.model.Add(sum(starts_today) <= self.config.max_2h_courses_per_day)

    def _add_student_gap_constraints(self):
        classes = self.data.df_classes['Class_ID'].tolist()
        for c in classes:
            for d in range(self.config.days):
                self.model.Add(self.class_active[c, d, 0] + self.class_active[c, d, 2] - self.class_active[c, d, 1] <= 1)
                self.model.Add(self.class_active[c, d, 1] + self.class_active[c, d, 3] - self.class_active[c, d, 2] <= 1)
                self.model.Add(self.class_active[c, d, 0] + self.class_active[c, d, 3] - self.class_active[c, d, 1] <= 1)
                self.model.Add(self.class_active[c, d, 0] + self.class_active[c, d, 3] - self.class_active[c, d, 2] <= 1)
                self.model.Add(self.class_active[c, d, 4] + self.class_active[c, d, 6] - self.class_active[c, d, 5] <= 1)

    def _add_pedagogical_spreading(self):
        classes = self.data.df_classes['Class_ID'].tolist()
        def get_base_subjs(subj_str): return subj_str.replace('_TD', '').replace('_TP', '').replace('_Pract/TD', '').replace('_TD/TP', '').split('+')
        for c in classes:
            c_lessons = [l for l in self.lessons if l['class'] == c]
            unique_base_subjs = set()
            for l in c_lessons: unique_base_subjs.update(get_base_subjs(l['subject']))
            for d in range(self.config.days):
                for subj in unique_base_subjs:
                    subj_lessons = [l for l in c_lessons if subj in get_base_subjs(l['subject'])
                                    and not (l.get('chain_offset', 0) > 0 and l.get('chain_primary') == subj)]
                    is_course = lambda l: l['subject'] == subj
                    for grp in ([l for l in subj_lessons if is_course(l)], [l for l in subj_lessons if not is_course(l)]):
                        starts_today = [self.x[l['id'], d, s] for l in grp for s in range(self.config.slots) if (l['id'], d, s) in self.x]
                        if len(starts_today) > 1: self.model.Add(sum(starts_today) <= 1)

    def _add_teacher_comfort_constraints(self):
        """Gaps, single-hour half-days, working days and late finish – each weighted by the teacher's load
        (priority_factor), so the most loaded teachers get the most comfortable timetables.
        Pedagogical-window hours count as 'busy' (the teacher is at the school), never as gaps."""
        teachers = self.data.df_teachers['Teacher_ID'].tolist()
        W = lambda base, f: int(round(base * f))
        self.teacher_factor = {}
        for t in teachers:
            f = self.priority_factor(t)
            self.teacher_factor[t] = f
            win = self.t_windows.get(t, set()) if hasattr(self, 't_windows') else set()
            t_row = self.data.df_teachers[self.data.df_teachers['Teacher_ID'] == t].iloc[0]
            rec_ok = str(t_row.get('Requires_Reception', False)).strip().lower() in ('true', '1', 'yes', 'نعم')
            rec_gaps = []
            for d in range(self.config.days):
                busy = {s: (1 if (d, s) in win else self.teacher_active[t, d, s]) for s in range(self.config.slots)}
                t_day_active = self.model.NewBoolVar(f"t_day_{t}_{d}")
                for s in range(self.config.slots): self.model.AddImplication(self.teacher_active[t, d, s], t_day_active)
                self.penalties.append(t_day_active * W(self.config.teacher_working_day_weight, f))
                self.kpi_terms.setdefault("t_days", []).append((t_day_active, t))
                for nm_, rng_ in (("m", self.G.morning), ("a", self.G.afternoon)):     # shifts (half-days)
                    sh_ = self.model.NewBoolVar(f"shift_{nm_}_{t}_{d}")
                    for s_ in rng_:
                        self.model.AddImplication(self.teacher_active[t, d, s_], sh_)
                    self.model.Add(sh_ <= sum(self.teacher_active[t, d, s_] for s_ in rng_))
                    self.kpi_terms.setdefault("t_shifts", []).append((sh_, t))
                    if getattr(self.config, 'teacher_shift_weight', 0):
                        self.penalties.append(sh_ * W(self.config.teacher_shift_weight, f))

                morn_sum = sum(busy[s] for s in self.G.morning)
                aft_sum = sum(busy[s] for s in self.G.afternoon)
                for nm, sm in (("m", morn_sum), ("a", aft_sum)):
                    single = self.model.NewBoolVar(f"{nm}_single_{t}_{d}")
                    self.model.Add(sm == 1).OnlyEnforceIf(single)
                    self.model.Add(sm != 1).OnlyEnforceIf(single.Not())
                    self.penalties.append(single * W(self.config.teacher_single_hour_weight, f))
                    self.kpi_terms.setdefault("t_single", []).append((single, t))

                for s in range(self.config.slots - 2):
                    if s == 2: continue
                    sg = self.model.NewBoolVar(f"sg_{t}_{d}_{s}")
                    self.model.Add(busy[s] + busy[s + 2] - busy[s + 1] - 1 <= sg)
                    self.penalties.append(sg * W(self.config.teacher_single_gap_weight, f))
                    self.kpi_terms.setdefault("t_gap1", []).append((sg, t))
                    if rec_ok: rec_gaps.append(sg)

                for s in range(self.config.slots - 3):
                    if s in [1, 2]: continue
                    dg = self.model.NewBoolVar(f"dg_{t}_{d}_{s}")
                    self.model.Add(busy[s] + busy[s + 3] - busy[s + 1] - busy[s + 2] - 1 <= dg)
                    self.penalties.append(dg * W(self.config.teacher_double_gap_weight, f))
                    self.kpi_terms.setdefault("t_gap2", []).append((dg, t))

                if self.config.teacher_late_finish_weight:
                    last = self.model.NewIntVar(0, self.config.slots, f"last_{t}_{d}")
                    for s in range(self.config.slots):
                        self.model.Add(last >= (s + 1) * self.teacher_active[t, d, s])
                    self.penalties.append(last * W(self.config.teacher_late_finish_weight, f))
                    self.kpi_terms.setdefault("t_late", []).append((self.teacher_active[t, d, self.config.slots - 1], t))
            if rec_gaps:          # reception hour (استقبال الأولياء): ONE single gap per week becomes the reception hour
                rec = self.model.NewBoolVar(f"rec_{t}")
                self.model.Add(rec <= sum(rec_gaps))
                self.penalties.append(-W(self.config.teacher_single_gap_weight, f) * rec)

    def _add_class_equity_constraints(self):
        levels = self.data.df_classes['Level'].unique()
        for lvl in levels:
            classes_in_lvl = self.data.df_classes[self.data.df_classes['Level'] == lvl]['Class_ID'].tolist()
            max_slot_7_lvl = self.model.NewIntVar(0, 5, f'max_slot_7_{lvl}')
            for c in classes_in_lvl:
                c_slot_7_count = sum(self.class_active[c, d, 6] for d in range(self.config.days))
                self.model.Add(max_slot_7_lvl >= c_slot_7_count)
            self.penalties.append(max_slot_7_lvl * self.config.slot_7_equity_penalty)

    def class_hours(self):
        h = {}
        for l in self.lessons:
            if l.get('remedial'): continue
            h[l['class']] = h.get(l['class'], 0) + l['duration']
        return h

    def required_cells(self, hours, level=None):
        """Cells that MUST be used by a class with `hours` weekly slots under the standard grid (its level's week)."""
        cfg = self.config
        morning = [(d, s) for d in range(cfg.days) for s in self.G.morning if not self.G.is_off(d, s, level)]
        aft_days = [d for d in range(cfg.days) if self.G.afternoon and not self.G.is_off(d, self.G.afternoon[0], level)]
        req = []
        if hours >= len(morning):
            req += morning
        if hours >= len(morning) + 2 * len(aft_days):
            req += [(d, s) for d in aft_days for s in (cfg.lunch_boundary + 1, cfg.lunch_boundary + 2)]
        return req

    def _add_class_grid(self):
        """Soft filling order.  Each used class cell costs: morning 0 · first 2 afternoon slots grid_cost_afternoon ·
        later slots grid_cost_extra (+ grid_cost_bad_day on no_slot7_days).  The weekly hours are fixed, so
        minimizing this cost fills mornings, then slots 5–6, then the 7th slot – as long as the rules allow it."""
        cfg = self.config
        hrs = self.class_hours()
        self.class_required = {c: self.required_cells(hrs.get(c, 0), lv) for c, lv in
                               zip(self.data.df_classes['Class_ID'], self.data.df_classes['Level'].astype(str))}
        lb = cfg.lunch_boundary
        self.grid_terms = []
        for c in self.data.df_classes['Class_ID'].tolist():
            for d in range(cfg.days):
                for s in range(lb + 1, cfg.slots):
                    k = s - lb - 1                                   # 0,1 = first two afternoon slots
                    cost = cfg.grid_cost_afternoon if k < 2 else cfg.grid_cost_extra
                    if k >= 2 and d in getattr(cfg, 'no_slot7_days', []):
                        cost += cfg.grid_cost_bad_day
                    self.grid_terms.append(self.class_active[c, d, s] * cost)
                for s in range(lb + 2, cfg.slots):                   # afternoon filled from its first slot (soft)
                    hole = self.model.NewBoolVar(f"ah_{c}_{d}_{s}")
                    self.model.Add(self.class_active[c, d, s] - self.class_active[c, d, s - 1] <= hole)
                    self.grid_terms.append(hole * cfg.grid_cost_afternoon)
        self.penalties.extend(self.grid_terms)

    def _add_morning_first_policy(self):
        cfg = self.config
        if cfg.strict_class_grid:
            self._add_class_grid()
        morning = range(cfg.lunch_boundary + 1)
        afternoon = range(cfg.lunch_boundary + 1, cfg.slots)
        for c in self.data.df_classes['Class_ID'].tolist():
            for d in range(cfg.days):
                if cfg.morning_first_hard:
                    for a in afternoon:
                        for m in morning:
                            self.model.AddImplication(self.class_active[c, d, a], self.class_active[c, d, m])
                if cfg.empty_morning_slot_penalty and not cfg.strict_class_grid:   # redundant with the grid
                    for m in morning:
                        self.penalties.append((1 - self.class_active[c, d, m]) * cfg.empty_morning_slot_penalty)
        if cfg.teacher_afternoon_penalty and not cfg.strict_class_grid:   # grid + late finish already decide it
            for t in self.data.df_teachers['Teacher_ID'].tolist():
                for d in range(cfg.days):
                    for a in afternoon:
                        self.penalties.append(self.teacher_active[t, d, a]
                                              * int(round(cfg.teacher_afternoon_penalty * self.priority_factor(t))))

    def _add_teacher_avoid(self):
        av = {tc: {tuple(c) for c in v} for tc, v in (getattr(self.config, 'teacher_avoid', None) or {}).items()}
        w = int(getattr(self.config, 'teacher_avoid_cost', 0) or 0)
        if not av or not w:
            return
        for l in self.lessons:
            cells_t = [av[tc] for tc in l['teachers'] if tc in av]
            if not cells_t:
                continue
            for (lid, d, s), v in list(self.x.items()):
                if lid == l['id']:
                    n = sum(1 for k in range(l['duration']) for cs in cells_t if (d, s + k) in cs)
                    if n:
                        self.penalties.append(v * (w * n))

    def _build_objective_function(self):
        self._add_teacher_avoid()
        classes = self.data.df_classes['Class_ID'].tolist()
        for c in classes if not getattr(self.config, 'strict_class_grid', False) else []:   # grid prices these cells
            for d in range(self.config.days):
                _a = self.G.afternoon                         # 2nd period, 1st/2nd afternoon periods, last period
                for s_, w_ in ((1, self.config.slot_1_penalty), (_a[0] if _a else None, self.config.slot_4_penalty),
                               (_a[1] if len(_a) > 1 else None, self.config.slot_5_penalty), (self.G.last, self.config.slot_7_penalty)):
                    if s_ is not None and w_:
                        self.penalties.append(self.class_active[c, d, s_] * w_)
        lb = self.config.lunch_boundary
        for l in self.lessons:
            if l.get('remedial'):
                for d in range(self.config.days):
                    for s_ in range(self.config.slots):
                        if (l['id'], d, s_) in self.x:
                            c_ = 0 if s_ == self.config.slots - 2 else self.config.remedial_slot7_cost
                            if c_: self.penalties.append(self.x[l['id'], d, s_] * c_)
        # remediation must not create a teacher gap: the teacher should also teach the hour before
        for l in self.lessons:
            if not l.get('remedial'): continue
            for tch in l['teachers']:
                for d in range(self.config.days):
                    for s_ in range(1, self.config.slots):
                        if (l['id'], d, s_) in self.x:
                            g = self.model.NewBoolVar(f"rg_{l['id']}_{tch}_{d}_{s_}")
                            self.model.Add(g >= self.x[l['id'], d, s_] - self.teacher_active[tch, d, s_ - 1])
                            self.penalties.append(g * self.config.remedial_gap_cost)
        self.model.Minimize(sum(self.penalties))

    def _extract_schedule(self, solver):
        res = []
        for l in self.lessons:
            for d in range(self.config.days):
                for s in range(self.config.slots):
                    if (l['id'], d, s) in self.x and solver.Value(self.x[l['id'], d, s]) == 1:
                        for step in range(l['duration']):
                            for cc in [l['class']] + list(l.get('also_classes', [])):
                                res.append({'Class': cc, 'Day': d, 'Slot': s + step, 'Subject': l['subject'], 'Teachers': ", ".join(l['teachers']),
                                            'Classes': ", ".join(l.get('blocks_classes', [])), 'RemSubject': l.get('rem_subject', ''),
                                            'Joint': l.get('joint', '') or ''})
        return pd.DataFrame(res)

class SolutionManager:
    def __init__(self, storage_dir="schedules"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def save(self, df_schedule, version_name, score=None):
        if df_schedule is not None:
            import json, time as _time
            op = os.path.join(self.storage_dir, "_order.json")
            try:
                order = json.load(open(op))
            except Exception:
                order = {}
            order[version_name] = _time.time()              # save order (file dates are not reliable)
            json.dump(order, open(op, "w"))
            filepath = os.path.join(self.storage_dir, f"{version_name}.csv")
            df_schedule.to_csv(filepath, index=False)
            pass  # print(f"💾 Saved '{version_name}' to disk. (Score: {score})")

    def load(self, version_name):
        filepath = os.path.join(self.storage_dir, f"{version_name}.csv")
        if os.path.exists(filepath): return pd.read_csv(filepath)
        return None


def calculate_all_kpis(df):
    _G = timegrid.CURRENT
    if df is None: return {}
    kpis = {}
    df = df[(~df['Class'].astype(str).str.startswith(REM_PREFIX)) & (df['Subject'] != 'REMEDIAL')]

    # --- 1. STUDENT KPIs ---
    student_gaps = 0
    for c, group in df.groupby('Class'):
        for d in range(_G.days):
            slots = sorted(group[group['Day'] == d]['Slot'].tolist())
            morn = [s for s in slots if s <= _G.lunch]
            aft = [s for s in slots if s > _G.lunch]
            if len(morn) > 1: student_gaps += (morn[-1] - morn[0] + 1) - len(morn)
            if len(aft) > 1: student_gaps += (aft[-1] - aft[0] + 1) - len(aft)

    kpis['Student Gaps (Free Periods)'] = student_gaps
    kpis['Empty Morning Slots (classes)'] = sum(_G.n_morning - len(g[(g['Day'] == d) & (g['Slot'] <= _G.lunch)]['Slot'].unique())
                                                for _, g in df.groupby('Class') for d in range(_G.days))
    kpis['Afternoon Hours (classes)'] = len(df[df['Slot'] > _G.lunch])
    kpis['Afternoon used w/o full morning'] = sum(
        1 for _, g in df.groupby('Class') for d in range(_G.days)
        if (g[(g['Day'] == d)]['Slot'] > _G.lunch).any() and len(g[(g['Day'] == d) & (g['Slot'] <= _G.lunch)]['Slot'].unique()) < _G.n_morning)
    kpis['Slot 1 Usage (Late Morning)'] = len(df[df['Slot'] == 1])
    kpis['Slot 4 Usage (Early Aft)'] = len(df[df['Slot'] == 4])
    kpis['Slot 5 Usage (Mid Aft)'] = len(df[df['Slot'] == 5])
    kpis['Slot 7 Usage (Late Dismissal)'] = len(df[df['Slot'] == _G.last])

    # Max Late Slots for a single class (Equity check)
    class_late = df[df['Slot'] == _G.last].groupby('Class')['Slot'].count()
    kpis['Max Slot 7s for any single class'] = class_late.max() if not class_late.empty else 0

    # --- 2. TEACHER KPIs ---
    df_t = df.copy()
    df_t['Teacher'] = df_t['Teachers'].str.split(', ')
    df_t = df_t.explode('Teacher')

    kpis['Total Teacher Working Days'] = len(df_t.groupby(['Teacher', 'Day']))

    single_shifts, single_gaps, double_gaps = 0, 0, 0
    for (t, d), group in df_t.groupby(['Teacher', 'Day']):
        slots = sorted(group['Slot'].tolist())
        morn = [s for s in slots if s <= _G.lunch]
        aft = [s for s in slots if s > _G.lunch]

        if len(morn) == 1: single_shifts += 1
        if len(aft) == 1: single_shifts += 1

        # Calculate gaps within shifts (ignoring lunch boundary)
        def count_gaps(shift_slots):
            sg, dg = 0, 0
            if len(shift_slots) > 1:
                for i in range(len(shift_slots)-1):
                    diff = shift_slots[i+1] - shift_slots[i]
                    if diff == 2: sg += 1
                    elif diff == 3: dg += 1
            return sg, dg

        m_sg, m_dg = count_gaps(morn)
        a_sg, a_dg = count_gaps(aft)
        single_gaps += (m_sg + a_sg)
        double_gaps += (m_dg + a_dg)

    kpis['Teacher Single-Hour Shifts'] = single_shifts
    kpis['Teacher Single Gaps (1h)'] = single_gaps
    kpis['Teacher Double Gaps (2h)'] = double_gaps

    return kpis



class RepairMismatch(Exception):
    """The data / settings changed since the version was solved: its lessons cannot be matched any more."""


def _lesson_sig(l):
    return (str(l['class']), str(l['subject']), tuple(sorted(map(str, l['teachers']))), int(l['duration']))


def repair(data, config, state, pins, fixed_assignment=None, time_limit=30, change_weight=20000, keep_changes=True,
           progress=None):
    """Adapt a timetable to the manager's pinned lessons ("📌"), changing as few other lessons as possible.

    state : editor state of the current timetable (lessons with ids, day, start)
    pins  : lesson ids that must stay exactly where they are in `state` (moved by hand or locked)
    keep_changes=False : full regeneration that only keeps the pins (no preference for the old positions)
    Search in growing circles: 1) lessons sharing a class/teacher with a pin, 2) their neighbours, 3) everything.
    -> dict(status, sched, state, moved, level, clash, outside)
    """
    import time as _time
    t_start = _time.time()
    eng = SchoolSchedulerEngine(data, config, fixed_assignment=fixed_assignment)
    eng.remedial = {}                                   # remediation sessions come from the state
    eng._generate_lessons_and_assignments()
    old = {l['id']: l for l in state['lessons']}
    gen = [l for l in eng.lessons if not l.get('remedial')]
    for l in gen:
        if l['id'] not in old or _lesson_sig(old[l['id']]) != _lesson_sig(l):
            raise RepairMismatch(l['id'])
    if len(gen) != sum(1 for l in old.values() if not l.get('remedial')):
        raise RepairMismatch('count')
    eng.lessons = gen + [{k: v for k, v in l.items() if k not in ('day', 'start', 'domain', 'domain_set')}
                         for l in old.values() if l.get('remedial')]
    eng.build_model(generate=False)
    m, x = eng.model, eng.x
    pos = {lid: (int(l['day']), int(l['start'])) for lid, l in old.items()}
    pins = [p for p in pins if p in old]
    by_id = {l['id']: l for l in eng.lessons}
    outside = [p for p in pins if (p,) + pos[p] not in x]
    if outside:
        return dict(status='OUTSIDE', outside=outside, clash=[], sched=None, state=None, moved=[], level=0)
    occ, pairs = {}, []
    for p in pins:                                      # obvious contradictions between pins: same class/teacher, same hour
        l = by_id[p]
        for k in range(l['duration']):
            for who in [l['class']] + list(l.get('blocks_classes', [])) + list(l.get('also_classes', [])) + list(l['teachers']):
                key = (who, pos[p][0], pos[p][1] + k)
                if key in occ and occ[key] != p and not (l.get('remedial') and by_id[occ[key]].get('remedial')
                                                          and who not in l['teachers']):
                    pairs.append((occ[key], p))
                occ.setdefault(key, p)
    if pairs:
        return dict(status='CLASH', outside=[], clash=sorted({i for pr in pairs for i in pr}), pairs=pairs,
                    sched=None, state=None, moved=[], level=0)

    pos_cur = dict(pos)                                 # positions after the steps already done

    def chg(V):                                         # number of lessons not at their current place
        out = 0
        for l in eng.lessons:
            k = (l['id'],) + pos_cur[l['id']]
            out += (1 - V(x[k])) if k in x else 1
        return out

    def members(l):
        return set(l['teachers']) | {l['class']} | set(l.get('blocks_classes', [])) | set(l.get('also_classes', []))

    def grow(ids):
        keys = set().union(*(members(by_id[i]) for i in ids)) if ids else set()
        return {l['id'] for l in eng.lessons if members(l) & keys}

    def run(mm, seconds, big=False):
        slv = cp_model.CpSolver()
        slv.parameters.max_time_in_seconds = max(2.0, seconds)
        slv.parameters.num_search_workers = config.num_workers
        # repair_hint is essential on big neighbourhoods, but aborts CP-SAT (fixed_search check) on tiny ones
        slv.parameters.repair_hint = big
        return slv, slv.Solve(mm)

    # Several manual moves are applied ONE AFTER ANOTHER in the same model: each step frees only the
    # neighbourhood of its move (plus the moves still waiting), earlier moves stay pinned.  Solving all
    # the moves at once frees most of the school and the search no longer finds a small change in time.
    steps = [[p] for p in pins] if (keep_changes and len(pins) > 1) else [pins]
    done = []
    status, best, level, clash, V = 'UNKNOWN', None, 0, [], None
    for si, step in enumerate(steps):
        final = si == len(steps) - 1
        active = done + step
        waiting = {p for st_ in steps[si + 1:] for p in st_}
        if keep_changes:
            lv1 = grow(step) | waiting
            def touched(ids):       # target days + days where the moved lessons' classes now have a hole
                days = {pos[p][0] for p in ids}
                for p in ids:
                    for c in [by_id[p]['class']] + list(by_id[p].get('blocks_classes', [])) + list(by_id[p].get('also_classes', [])):
                        used = {(pos_cur[l['id']][0], pos_cur[l['id']][1] + k) for l in eng.lessons
                                if (l['class'] == c or c in l.get('also_classes', ())) and not l.get('remedial')
                                for k in range(l['duration'])}
                        days |= {d for d, s_ in state.get('class_required', {}).get(c, []) if (d, s_) not in used}
                return days

            def on_days(ids, days):
                return {i_ for i_ in ids if pos_cur[i_][0] in days}
            days = touched(step)
            lv2 = grow(lv1)
            lv_days = lv1 | on_days(lv2, days)
            lv_days2 = lv_days | on_days(grow(lv_days), days)
            # interplay with the moves already applied: free their neighbourhoods too (on their days)
            lvA1 = grow(active) | waiting
            daysA = touched(active)
            lvA = lv_days2 | lvA1 | on_days(grow(lvA1), daysA)
            levels = [lv1, lv_days, lv_days2, lvA, lv2 | waiting | lvA, set(by_id)]
        else:
            levels = [set(by_id)]
        uniq = []
        for lv in levels:
            if not uniq or len(lv) > len(uniq[-1]):
                uniq.append(lv)
        best = None
        for i, free in enumerate(uniq):
            last = i == len(uniq) - 1
            if progress:
                progress(si + 1, len(steps)) if len(steps) > 1 else progress(i + 1, len(uniq))
            mm = m.Clone()
            V = lambda v, mm=mm: mm.GetBoolVarFromProtoIndex(v.Index())
            for p in active:
                mm.Add(V(x[(p,) + pos[p]]) == 1)
            for l in eng.lessons:
                k = (l['id'],) + pos_cur[l['id']]
                if l['id'] not in free and k in x:
                    mm.Add(V(x[k]) == 1)
            mm.ClearHints()
            for (lid, d, s_), v in x.items():
                mm.AddHint(V(v), int(pos_cur[lid] == (d, s_)))
            remaining = time_limit - (_time.time() - t_start)
            # small neighbourhoods solve in a second; a big one may take up to half of the time left
            step_budget = remaining if final else max(remaining / (len(steps) - si),
                                                      remaining * 0.5 if len(free) > 150 else 0)
            budget = step_budget if last else step_budget * 0.6
            # phase A: fewest moved lessons (keep_changes) / plain quality (full regeneration)
            mm.Minimize(chg(V) if keep_changes else sum(eng.penalties))
            slv, stt = run(mm, budget * (0.5 if (keep_changes and final) else 1.0), big=len(free) > 150)
            status = slv.StatusName(stt)
            if stt in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                best, level = slv, i + 1
                if keep_changes and final:    # phase B: best quality without moving more lessons
                    nmin = int(round(slv.ObjectiveValue()))
                    mm.Add(chg(V) <= nmin)
                    mm.ClearHints()
                    for (lid, d, s_), v in x.items():
                        mm.AddHint(V(v), slv.Value(V(v)))
                    mm.Minimize(sum(eng.penalties) + change_weight * chg(V))
                    rem2 = time_limit - (_time.time() - t_start)
                    slv2, stt2 = run(mm, rem2, big=len(free) > 150)
                    if stt2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                        best = slv2
                break
            if last and stt == cp_model.INFEASIBLE and active:
                # which moves are incompatible: separate short solve with assumptions (no hints)
                mc = m.Clone(); mc.ClearHints()
                Vc = lambda v, mc=mc: mc.GetBoolVarFromProtoIndex(v.Index())
                lits = [Vc(x[(p,) + pos[p]]) for p in active]
                mc.AddAssumptions(lits)
                sc = cp_model.CpSolver(); sc.parameters.max_time_in_seconds = 20
                sc.parameters.num_search_workers = config.num_workers
                if sc.Solve(mc) == cp_model.INFEASIBLE:
                    core = set(sc.SufficientAssumptionsForInfeasibility())
                    idx = {lit.Index(): p for lit, p in zip(lits, active)}
                    clash = [idx[c] for c in core if c in idx]
        if best is None:
            return dict(status=status, outside=[], clash=clash, sched=None, state=None, moved=[], level=0,
                        failed=step if len(steps) > 1 else [], applied=list(done))
        for (lid, d, s_), v in x.items():
            if best.Value(V(v)):
                pos_cur[lid] = (d, s_)
        done += step
    _best, _V = best, V
    best = type("B", (), {"Value": staticmethod(lambda v: _best.Value(_V(v))),
                          "ObjectiveValue": staticmethod(_best.ObjectiveValue)})
    Vb = lambda v: best.Value(v)
    eng.placements = {lid: (d, s_) for (lid, d, s_), v in x.items() if Vb(v) == 1}

    class _S:                                          # adapter: _extract_schedule reads solver.Value
        Value = staticmethod(Vb)
    sched = eng._extract_schedule(_S)
    eng.objective_score = best.ObjectiveValue()
    new_state = export_editable_state(eng)
    new_state['pins'] = sorted(pins)
    import reception as _rc                            # keep the manager's reception hours when still free
    new_state['reception'] = dict(state.get('reception') or {})
    new_state['reception_removed'] = list(state.get('reception_removed') or [])
    _rc.ensure(new_state)
    moved = [lid for lid in by_id if eng.placements.get(lid) != pos[lid] and lid not in pins]
    return dict(status=status, sched=sched, state=new_state, moved=moved, level=level, clash=[], outside=[],
                seconds=round(_time.time() - t_start, 1), engine=eng)


IMPROVE_KPIS = ["t_single", "t_gap1", "t_gap2", "t_shifts", "t_days", "t_late",
                "c_empty_morning", "c_aft", "c_slot7", "c_slot7_max"]
# relaxing a rule switches off the guards that would forbid it (linked rules)
IMPROVE_LINKS = {"c_empty_morning": ["c_aft", "c_slot7", "c_slot7_max"],   # non-full mornings -> the grid is no longer rigid
                 "c_slot7": ["c_slot7_max", "c_aft"],
                 "c_aft": []}


def _improve_build(data, config, state, fixed_assignment):
    """Engine + model rebuilt from a saved timetable, with KPI expressions (counts K, priority-weighted KW)."""
    eng = SchoolSchedulerEngine(data, config, fixed_assignment=fixed_assignment)
    eng.remedial = {}
    eng._generate_lessons_and_assignments()
    old = {l['id']: l for l in state['lessons']}
    gen = [l for l in eng.lessons if not l.get('remedial')]
    for l in gen:
        if l['id'] not in old or _lesson_sig(old[l['id']]) != _lesson_sig(l):
            raise RepairMismatch(l['id'])
    eng.lessons = gen + [{k: v for k, v in l.items() if k not in ('day', 'start', 'domain', 'domain_set')}
                         for l in old.values() if l.get('remedial')]
    eng.build_model(generate=False)
    m, cfg = eng.model, eng.config
    classes = eng.data.df_classes['Class_ID'].tolist()
    lb, S, D = cfg.lunch_boundary, cfg.slots, cfg.days
    fac = getattr(eng, 'teacher_factor', {})
    K, KW, pcm = {}, {}, {}
    for nm in ("t_single", "t_gap1", "t_gap2", "t_shifts", "t_days", "t_late"):
        terms = eng.kpi_terms.get(nm, [])
        K[nm] = sum(v for v, _t in terms)
        KW[nm] = sum(int(round(10 * fac.get(_t, 1.0))) * v for v, _t in terms)
    ca = eng.class_active
    for c in classes:
        pcm[c] = sum(1 - ca[c, d, s] for d in range(D) for s in range(lb + 1))
    K["c_empty_morning"] = sum(pcm.values())
    K["c_aft"] = sum(ca[c, d, s] for c in classes for d in range(D) for s in range(lb + 1, S))
    K["c_slot7"] = sum(ca[c, d, S - 1] for c in classes for d in range(D))
    mx7 = m.NewIntVar(0, D, "imp_max7")
    for c in classes:
        m.Add(mx7 >= sum(ca[c, d, S - 1] for d in range(D)))
    K["c_slot7_max"] = mx7
    for nm in ("c_empty_morning", "c_aft", "c_slot7", "c_slot7_max"):
        KW[nm] = 10 * K[nm]
    pos = {lid: (int(l['day']), int(l['start'])) for lid, l in old.items()}
    return eng, K, KW, pcm, pos


def improve(data, config, state, pins, goals, relax=None, guards=None, change_weight=3000, time_limit=60, max_moves=None,
            fixed_assignment=None, main=None):
    """Keep optimizing a FINISHED timetable ("as if the solver ran longer"), on chosen goals only.
    goals  : KPI names to reduce (IMPROVE_KPIS); teacher KPIs are weighted by the teacher's priority factor
    main   : one goal counted x3
    relax  : {kpi: extra units allowed} e.g. {"c_empty_morning": 4} (empty mornings: also at most +1 per class)
    guards : KPI names that must not get worse (default: all the others, minus those switched off by `relax`)
    change_weight : cost of one moved lesson (0 = free re-arrangement); pins never move
    -> dict(status, sched, state, moved, before, after, seconds)"""
    import time as _time
    t0 = _time.time()
    relax = {k: int(v) for k, v in (relax or {}).items()}
    # 1) current values, with the model's own definitions: everything fixed to the current timetable
    e1, K1, _, pcm1, pos = _improve_build(data, config, state, fixed_assignment)
    outside = [lid for lid in pos if (lid,) + pos[lid] not in e1.x]
    if outside:
        return dict(status='OUTSIDE', outside=outside, sched=None, state=None, moved=[], before={}, after={})
    for lid, (d, s_) in pos.items():
        e1.model.Add(e1.x[(lid, d, s_)] == 1)
    e1.model.Minimize(0)
    sc = cp_model.CpSolver(); sc.parameters.max_time_in_seconds = 30
    sc.parameters.num_search_workers = config.num_workers
    stc = sc.Solve(e1.model)
    if stc not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return dict(status='CONFLICTS', outside=[], sched=None, state=None, moved=[], before={}, after={})
    before = {nm: int(sc.Value(e)) for nm, e in K1.items()}
    cur_m = {c: int(sc.Value(e)) for c, e in pcm1.items()}
    # 2) improvement model
    eng, K, KW, pcm, _ = _improve_build(data, config, state, fixed_assignment)
    m, x = eng.model, eng.x
    for p in pins:
        if p in pos:
            m.Add(x[(p,) + pos[p]] == 1)
    off = set()
    for r in relax:
        off |= set(IMPROVE_LINKS.get(r, []))
    if guards is None:
        guards = [k for k in IMPROVE_KPIS if k not in goals]
    for nm in guards:
        if nm in relax or nm in off or nm in goals:
            continue
        m.Add(K[nm] <= before[nm])
    for nm, extra in relax.items():
        m.Add(K[nm] <= before[nm] + extra)
        if nm == "c_empty_morning":
            for c, e in pcm.items():
                m.Add(e <= cur_m[c] + 1)
    for g in goals:                                     # a goal never gets worse either
        m.Add(K[g] <= before[g])
    chg = sum(1 - x[(lid,) + pos[lid]] for lid in pos)
    obj = sum((3 if g == main else 1) * 10000 * KW[g] for g in goals)
    if change_weight:
        obj = obj + int(change_weight) * chg
    if max_moves is not None:                           # hard cap on moved lessons ("few changes")
        m.Add(chg <= int(max_moves))
    m.Minimize(obj + sum(eng.penalties))
    m.ClearHints()
    for (lid, d, s_), v in x.items():
        m.AddHint(v, int(pos[lid] == (d, s_)))
    slv = cp_model.CpSolver()
    slv.parameters.max_time_in_seconds = float(time_limit)      # the chosen time is all SEARCH (setup is extra)
    slv.parameters.num_search_workers = config.num_workers
    t_s = _time.time()
    stt = slv.Solve(m)
    status = slv.StatusName(stt)
    solve_s = round(_time.time() - t_s, 1)
    if stt not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return dict(status=status, outside=[], sched=None, state=None, moved=[], before=before, after={},
                    solve_seconds=solve_s)
    after = {nm: int(slv.Value(e)) for nm, e in K.items()}
    eng.placements = {lid: (d, s_) for (lid, d, s_), v in x.items() if slv.Value(v) == 1}

    class _S:
        Value = staticmethod(slv.Value)
    sched = eng._extract_schedule(_S)
    new_state = export_editable_state(eng)
    new_state['pins'] = sorted(p for p in pins if p in pos)
    import reception as _rc
    new_state['reception'] = dict(state.get('reception') or {})
    new_state['reception_removed'] = list(state.get('reception_removed') or [])
    _rc.ensure(new_state)
    moved = [lid for lid in pos if eng.placements.get(lid) != pos[lid]]
    return dict(status=status, sched=sched, state=new_state, moved=moved, before=before, after=after,
                outside=[], seconds=round(_time.time() - t0, 1), solve_seconds=solve_s)


def cfg_to_dict(c):
    """All solver settings as plain JSON (saved inside each version so adapt/improve use the SAME rules)."""
    import json as _j
    def conv(v):
        if isinstance(v, (set, frozenset)):
            return sorted(conv(x) for x in v)
        if isinstance(v, (list, tuple)):
            return [conv(x) for x in v]
        if isinstance(v, dict):
            return {str(k): conv(x) for k, x in v.items()}
        return v
    out = {}
    for k, v in vars(c).items():
        try:
            out[k] = _j.loads(_j.dumps(conv(v)))
        except (TypeError, ValueError):
            pass
    return out


def cfg_from_dict(d):
    c = SchedulerConfig()
    for k, v in (d or {}).items():
        if k == "remedial_groups":
            v = [set(g) for g in v]
        setattr(c, k, v)
    return c


def export_editable_state(engine):
    """Everything the interactive editor needs to re-check moves without re-solving."""
    domains = {}
    for (lid, d, s) in engine.x.keys():
        domains.setdefault(lid, []).append([d, s])
    domains.update(getattr(engine, 'remedial_domains', {}) or {})
    c = engine.config
    return {
        "lessons": [{**l, "day": engine.placements[l["id"]][0], "start": engine.placements[l["id"]][1],
                     "domain": domains.get(l["id"], [])} for l in engine.lessons],
        "solver_cfg": cfg_to_dict(c),
        "class_level": {r["Class_ID"]: r["Level"] for _, r in engine.data.df_classes.iterrows()},
        # subjects whose weekly course hours allow a 2h block (Hrs_Cours >= 2), per level
        "two_hour_subjects": {lvl: sorted(g[g["Hrs_Cours"] >= 2]["Subject_Code"].tolist())
                              for lvl, g in engine.data.df_subjects.groupby("Level")},
        "rooms": {r["Room_Type"]: int(r["Capacity"]) for _, r in engine.data.df_rooms.iterrows()},
        "config": {"days": c.days, "slots": c.slots, "lunch_boundary": c.lunch_boundary,
                   "same_day_exempt": list(getattr(c, "same_day_exempt", [])),
                   "closed": [list(x) for x in getattr(c, "closed_halfdays", timegrid.DEFAULT_CLOSED)],
                   "level_off": {k: sorted([list(x) for x in v]) for k, v in engine.G.level_off.items()},
                   "room_fallback": getattr(c, "room_fallback", {}) or {},
                   "allow_student_gaps": c.allow_student_gaps,
                   "allow_same_subject_twice_per_day": c.allow_same_subject_twice_per_day,
                   "enforce_max_2h_courses_per_day": c.enforce_max_2h_courses_per_day,
                   "max_2h_courses_per_day": c.max_2h_courses_per_day,
                   "morning_first_hard": c.morning_first_hard,
                   "strict_class_grid": getattr(c, "strict_class_grid", False),
                   "no_slot7_days": list(getattr(c, "no_slot7_days", []) if getattr(c, "strict_class_grid", False) else [])},
        "class_required": {k: [list(x) for x in v] for k, v in getattr(engine, "class_required", {}).items()},
        "teacher_unavailable": {tc: sorted([list(x) for x in v]) for tc, v in (getattr(c, "teacher_unavailable", None) or {}).items()},
        "teacher_windows": {tch: sorted([list(x) for x in cells]) for tch, cells in getattr(engine, 't_windows', {}).items()},
        "teacher_windows_info": {tch: sorted([list(x) for x in cells]) for tch, cells in engine._teacher_windows().items()},
        "priority_strength": float(getattr(c, "teacher_priority_strength", 3.0)),
        "reception_teachers": [r["Teacher_ID"] for _, r in engine.data.df_teachers.iterrows()
                               if str(r.get("Requires_Reception", True)).strip().lower() in ("true", "1", "yes", "نعم")],
    }


def grid_report(sched, engine):
    """Per class: hours, holes in the standard grid, 7th slots, 7th slots on forbidden days."""
    if sched is None or sched.empty:
        return pd.DataFrame()
    cfg = engine.config
    x = sched[(~sched['Class'].astype(str).str.startswith(REM_PREFIX)) & (sched['Subject'] != 'REMEDIAL')]
    rows = []
    for c, g in x.groupby('Class'):
        used = set(zip(g['Day'], g['Slot']))
        req = set(engine.required_cells(len(used)))
        extra = [d for d in range(cfg.days) if (d, cfg.slots - 1) in used]
        rows.append({'Class': c, 'Hours': len(used), 'Holes': len(req - used), 'Slot7_days': len(extra),
                     'Slot7_bad_day': sum(d in getattr(cfg, 'no_slot7_days', []) for d in extra),
                     'OK': not (req - used) and not any(d in getattr(cfg, 'no_slot7_days', []) for d in extra)})
    return pd.DataFrame(rows)


def teacher_fairness(sched, engine=None):
    """Per-teacher comfort report from a schedule (Class, Day, Slot, Subject, Teachers)."""
    _G = timegrid.CURRENT
    rows = []
    if sched is None or sched.empty:
        return pd.DataFrame()
    x = sched.assign(Teacher=sched["Teachers"].str.split(", ")).explode("Teacher")
    x = x.drop_duplicates(["Teacher", "Day", "Slot"])
    win = getattr(engine, "t_windows", {}) if engine is not None else {}
    for tch, g in x.groupby("Teacher"):
        gaps = singles = late = 0
        finishes = []
        for d, gd in g.groupby("Day"):
            busy = set(gd["Slot"]) | {s for (dd, s) in win.get(tch, set()) if dd == d}
            for half in (_G.morning, _G.afternoon):
                act = sorted(s for s in busy if s in half)
                if act:
                    gaps += (act[-1] - act[0] + 1) - len(act)
                    singles += len([s for s in gd["Slot"] if s in half]) == 1 and len(act) == 1
            finishes.append(int(gd["Slot"].max()) + 1)
            late += int(gd["Slot"].max()) >= 5
        rows.append({"Teacher": tch, "Hours": len(g), "Days": g["Day"].nunique(), "Gaps": gaps,
                     "Single_hour": int(singles), "Afternoon_h": int((g["Slot"] > _G.lunch).sum()),
                     "Avg_finish": round(sum(finishes) / len(finishes), 2), "Late_days": late})
    return pd.DataFrame(rows).sort_values(["Hours", "Teacher"], ascending=[False, True]).reset_index(drop=True)


def class_slot_needs(engine):
    """Weekly slots each class really occupies (split sessions count once), vs the sum of teacher hours.
    Requires engine._generate_lessons_and_assignments() to have run."""
    rows = {}
    for l in engine.lessons:
        if l.get('remedial'): continue
        r = rows.setdefault(l["class"], {"slots": 0, "teacher_hours": 0})
        r["slots"] += l["duration"]
        r["teacher_hours"] += l["duration"] * len(l["teachers"])
    df = pd.DataFrame.from_dict(rows, orient="index")
    df["split_overlap"] = df["teacher_hours"] - df["slots"]
    return df


def teacher_stats(sched, windows=None, k=3.0):
    """Main KPIs per teacher (remediation included in hours).
    Priority = 1 (least loaded) … k (most loaded) – same formula as the solver's fairness priority."""
    _G = timegrid.CURRENT
    if sched is None or sched.empty:
        return pd.DataFrame()
    windows = windows or {}
    x = sched.assign(Teacher=sched["Teachers"].astype(str).str.split(", ")).explode("Teacher")
    x = x.drop_duplicates(["Teacher", "Day", "Slot"])
    rows = []
    for tch, g in x.groupby("Teacher"):
        gaps = singles = 0
        finishes = []
        win = {tuple(c) for c in windows.get(tch, [])}
        for d, gd in g.groupby("Day"):
            for half in (_G.morning, _G.afternoon):
                act = sorted(s for s in gd["Slot"] if s in half)
                if act:
                    gaps += (act[-1] - act[0] + 1) - len(act)
                    singles += len(act) == 1
            finishes.append(int(gd["Slot"].max()) + 1)
        rem = g["Subject"] == "REMEDIAL"
        own = g[~rem]
        rows.append({"Teacher": tch, "Hours": len(g), "Remedial": int(rem.sum()), "Days": g["Day"].nunique(),
                     "Gaps": int(gaps), "Single_hour": int(singles), "Afternoon_h": int((g["Slot"] > _G.lunch).sum()),
                     "Slot7": int((g["Slot"] == _G.last).sum()), "Avg_finish": round(sum(finishes) / len(finishes), 1),
                     "In_window": int(sum((int(d), int(s)) in win for d, s in zip(own["Day"], own["Slot"]))),
                     "Classes": ", ".join(sorted(set(own["Class"].astype(str)), key=lambda c: (len(c), c))),
                     "Subjects": sorted({str(s).split("+")[0].split("_")[0] for s in own["Subject"]})})
    df = pd.DataFrame(rows)
    lo, hi = df["Hours"].min(), df["Hours"].max()
    k = max(1.0, float(k))
    df["Priority"] = [round(1.0 + (k - 1.0) * (h - lo) / (hi - lo), 2) if hi > lo else 1.0 for h in df["Hours"]]
    df["Priority_max"] = round(k, 2)
    return df.set_index("Teacher")


def class_stats(sched):
    """Main KPIs per class: own hours, remediation hours shown in its table, gaps, 7th slots, empty mornings."""
    _G = timegrid.CURRENT
    if sched is None or sched.empty:
        return pd.DataFrame()
    s = sched.copy()
    s["Classes"] = s.get("Classes", pd.Series([""] * len(s))).fillna("").astype(str)
    own = s[~s["Class"].astype(str).str.startswith(REM_PREFIX)]
    rem = s[s["Class"].astype(str).str.startswith(REM_PREFIX)]
    rows = []
    for c, g in own.groupby("Class"):
        gaps = 0
        for d, gd in g.groupby("Day"):
            for half in (_G.morning, _G.afternoon):
                act = sorted(x for x in set(gd["Slot"]) if x in half)
                if act: gaps += (act[-1] - act[0] + 1) - len(act)
        used = set(zip(g["Day"], g["Slot"]))
        rem_cells = {(r.Day, r.Slot) for r in rem.itertuples() if c in [z.strip() for z in str(r.Classes).split(",")]}
        rows.append({"Class": c, "Hours": len(used), "Remedial": len(rem_cells),
                     "Gaps": int(gaps), "Slot7": int(sum(1 for d_, s_ in used if s_ == _G.last)),
                     "Empty_morning": int(sum(1 for d in range(_G.days) for s_ in _G.morning if (d, s_) not in used)),
                     "Afternoon_h": int(sum(1 for _, s_ in used if s_ > _G.lunch))})
    return pd.DataFrame(rows).set_index("Class")
