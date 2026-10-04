"""Interactive schedule editor: evaluates & applies manual moves using the engine's hard rules.

Colour semantics for a candidate start (day, slot) of a lesson:
  green  : slot is free for the class and all its teachers and every hard rule holds
  yellow : slot is valid only by swapping with another lesson -> affects other teacher(s)/class(es)
  red    : impossible (blocked slot, rule violation, or the conflict cannot be resolved by a swap)
"""
import copy
import timegrid
import pandas as pd
import reception as rc
import i18n
from i18n import t, subj as S_, cls as C_, teachers as T_


def base_subjects(subj):
    return (subj.replace('_TD/TP', '').replace('_Pract/TD', '').replace('_TD', '').replace('_TP', '')
            .split('+'))


def is_2h_course(l):
    return l['duration'] == 2 and '+' not in l['subject'] and '_' not in l['subject']


class ScheduleEditor:
    def __init__(self, state):
        self.state = copy.deepcopy(state)
        self.cfg = self.state['config']
        self.G = timegrid.from_state_cfg(self.cfg)
        timegrid.set_current(self.G)
        self.rooms = self.state['rooms']
        self.L = {l['id']: l for l in self.state['lessons']}
        self.pins = set(self.state.get('pins', [])) & set(self.L)
        self.rec_removed = set(self.state.get('reception_removed', []))
        if 'reception' not in self.state:                 # older versions: create the reception hours now
            rc.ensure(self.state)
        self.rec = {k: list(v) for k, v in (self.state.get('reception') or {}).items()}
        self._two_hour_cache = {}
        for l in self.L.values():
            l['domain_set'] = {tuple(x) for x in l['domain']}
        self._index()

    # ------------------------------------------------------------ helpers
    @staticmethod
    def cells(l, d=None, s=None):
        d = l['day'] if d is None else d
        s = l['start'] if s is None else s
        return [(d, s + k) for k in range(l['duration'])]

    @staticmethod
    def classes_of(l):
        """The class itself + every class a remediation session blocks."""
        return [l['class']] + list(l.get('also_classes', [])) + list(l.get('blocks_classes', []))

    def class_conflicts(self, l, c):
        """Lessons clashing with l on cell c for class reasons (remediation vs remediation is allowed)."""
        out = set(self.class_occ.get((l['class'],) + c, set()))
        for k in l.get('also_classes', []):                 # joint session: every class of it
            out |= self.class_occ.get((k,) + c, set())
            out |= self.rem_occ.get((k,) + c, set())
        for k in l.get('blocks_classes', []):
            out |= self.class_occ.get((k,) + c, set())
        out |= self.rem_occ.get((l['class'],) + c, set())
        for k in l.get('blocks_classes', []):
            out |= self.rem_occ.get((k,) + c, set())
        return out

    def locked(self, l):
        return 'linked_next' in l or 'linked_prev' in l

    def _index(self):
        self.class_occ, self.teacher_occ, self.rem_occ = {}, {}, {}
        for l in self.L.values():
            for c in self.cells(l):
                self.class_occ.setdefault((l['class'],) + c, set()).add(l['id'])
                for k in l.get('also_classes', []):
                    self.class_occ.setdefault((k,) + c, set()).add(l['id'])
                for k in l.get('blocks_classes', []):
                    self.rem_occ.setdefault((k,) + c, set()).add(l['id'])
                for tt in l['teachers']:
                    self.teacher_occ.setdefault((tt,) + c, set()).add(l['id'])

    def two_hour(self, cls):
        """Subjects that may form a 2h block for this class.
        = subjects listed at solve time (Hrs_Cours >= 2)  UNION  subjects whose single-subject lessons
        for this class total >= 2h (derived from the lessons, so it also works for older saved versions)."""
        if cls not in self._two_hour_cache:
            lvl = self.state.get('class_level', {}).get(cls)
            allowed = set(self.state.get('two_hour_subjects', {}).get(str(lvl), [])) | \
                      set(self.state.get('two_hour_subjects', {}).get(lvl, []) if isinstance(lvl, str) else [])
            hours = {}
            for x in self.L.values():
                if x['class'] == cls and '+' not in x['subject']:
                    b = base_subjects(x['subject'])[0]
                    hours[b] = hours.get(b, 0) + x['duration']
            allowed |= {b for b, h in hours.items() if h >= 2}
            self._two_hour_cache[cls] = allowed
        return self._two_hour_cache[cls]

    def forms_block(self, a, b, pos):
        """True if lessons a and b are 1h courses of the same (2h-allowed) subject, same class & teacher,
        placed back-to-back on the same day without crossing lunch."""
        if a['duration'] != 1 or b['duration'] != 1: return False
        if '+' in a['subject'] or '+' in b['subject']: return False   # split (two-teacher) lessons excluded
        sa, sb = base_subjects(a['subject'])[0], base_subjects(b['subject'])[0]
        if sa != sb or sa not in self.two_hour(a['class']): return False
        if a['class'] != b['class'] or set(a['teachers']) != set(b['teachers']): return False
        (da, xa), (db, xb) = pos(a), pos(b)
        return da == db and abs(xa - xb) == 1 and min(xa, xb) != self.cfg['lunch_boundary']

    def block_reason(self, l, dup, b, pos):
        if b not in self.two_hour(l['class']):
            return t("e_no2h", b=S_(b))
        if len(dup) > 1:
            return t("e_exceed2h", b=S_(b))
        x = dup[0]
        if l['duration'] != 1 or x['duration'] != 1:
            return t("e_already2h", b=S_(b))
        if '+' in l['subject'] or '+' in x['subject']:
            return t("e_split2h")
        if set(l['teachers']) != set(x['teachers']):
            return t("e_diffteach", b=S_(b))
        (d1, s1), (d2, s2) = pos(l), pos(x)
        if abs(s1 - s2) == 1:
            return t("e_lunch2h")
        return t("e_place_adj", b=S_(b))

    def count_2h_blocks(self, cls, d, pos):
        day = [x for x in self.L.values() if x['class'] == cls and pos(x)[0] == d]
        n = sum(is_2h_course(x) for x in day)
        singles = [x for x in day if x['duration'] == 1 and '+' not in x['subject'] and '_' not in x['subject']]
        n += sum(1 for i, a in enumerate(singles) for b in singles[i + 1:] if self.forms_block(a, b, pos))
        return n

    def describe(self, l):
        return f"{S_(l['subject'])} ({C_(l['class'])} / {T_(l['teachers'])})"

    # ------------------------------------------------------------ validation
    def check(self, moves):
        """moves: {lid: (d, s)}. Returns list of hard errors for the moved lessons."""
        errs = []
        pos = lambda x: moves.get(x['id'], (x['day'], x['start']))
        moved = [self.L[i] for i in moves]
        moved_ids = set(moves)
        for l in moved:
            d, s = moves[l['id']]
            if (d, s) not in l['domain_set']:
                errs.append(t("e_cannot_start", s=S_(l['subject'])))
                continue
            for c in self.cells(l, d, s):
                # class & teacher clashes with lessons that stay in place
                if self.class_conflicts(l, c) - moved_ids:
                    errs.append(t("e_class_busy", c=C_(l['class']))); break
                for t_ in l['teachers']:
                    if self.teacher_occ.get((t_,) + c, set()) - moved_ids:
                        errs.append(t("e_teacher_busy", t=t_))
                # clashes among moved lessons
                for m in moved:
                    if m is l: continue
                    if c in self.cells(m, *moves[m['id']]) and (set(self.classes_of(m)) & set(self.classes_of(l)) or set(m['teachers']) & set(l['teachers'])):
                        errs.append(t("e_overlap"))
            if errs: continue
        # room capacity on affected cells
        affected = {c for l in moved for c in self.cells(l, *moves[l['id']])}
        for c in affected:
            usage = {}
            for x in self.L.values():
                if c in self.cells(x, *pos(x)):
                    for rt, n in x['rooms'].items():
                        usage[rt] = usage.get(rt, 0) + n
            fb = self.state.get('config', {}).get('room_fallback', {'lab': 'classroom'})
            for rt, to in fb.items():            # lab overflow goes into free classrooms
                over = usage.get(rt, 0) - self.rooms.get(rt, 0)
                if over > 0:
                    usage[rt] -= over; usage[to] = usage.get(to, 0) + over
            for rt, n in usage.items():
                if n > self.rooms.get(rt, 0 if rt in fb.values() or rt in fb else 10 ** 6):
                    errs.append(t("e_room", r=rt, n=n, cap=self.rooms.get(rt, 0)))
        # pedagogical spreading & 2h-course limit (only if the config enforces them)
        for l in moved:
            d = moves[l['id']][0]
            same_day = [x for x in self.L.values() if x['class'] == l['class'] and x['id'] != l['id'] and pos(x)[0] == d]
            if not self.cfg['allow_same_subject_twice_per_day']:
                for b in base_subjects(l['subject']):
                    if b in self.cfg.get('same_day_exempt', ['INFO']): continue   # old versions: INFO
                    dup = [x for x in same_day if b in base_subjects(x['subject'])]
                    if not dup: continue
                    if len(dup) == 1 and self.forms_block(l, dup[0], pos):
                        continue   # adjacent same-subject hours = one allowed 2h block
                    errs.append(t("e_already", b=S_(b), c=C_(l['class'])) + self.block_reason(l, dup, b, pos))
            if self.cfg['enforce_max_2h_courses_per_day']:
                n = self.count_2h_blocks(l['class'], d, pos)
                if n > self.cfg['max_2h_courses_per_day']:
                    errs.append(t("e_max2h", n=self.cfg['max_2h_courses_per_day'], c=C_(l['class'])))
        # morning-first: an afternoon lesson requires a full morning (checked on every affected class-day)
        if self.cfg.get('morning_first_hard'):
            lb = self.cfg['lunch_boundary']
            keys = {(l['class'], moves[l['id']][0]) for l in moved} | {(l['class'], l['day']) for l in moved}
            for c, d in keys:
                used = {sl for x in self.L.values() if x['class'] == c and pos(x)[0] == d
                        for sl in range(pos(x)[1], pos(x)[1] + x['duration'])}
                if any(sl > lb for sl in used) and not all(m in used for m in range(lb + 1)):
                    errs.append(t("e_morning", c=C_(c)))
        return list(dict.fromkeys(errs))

    def gap_warnings(self, moves):
        """Soft check: student gaps created in the affected class-days."""
        if self.cfg['allow_student_gaps']:
            return []
        pos = lambda x: moves.get(x['id'], (x['day'], x['start']))
        keys = set()
        for lid, (d, s) in moves.items():
            l = self.L[lid]
            keys.add((l['class'], d)); keys.add((l['class'], l['day']))
        out = []
        for c, d in keys:
            slots = sorted(sl for x in self.L.values() if x['class'] == c and pos(x)[0] == d
                           for sl in range(pos(x)[1], pos(x)[1] + x['duration']))
            for half in ([s for s in slots if s <= self.G.lunch], [s for s in slots if s > self.G.lunch]):
                if len(half) > 1 and half[-1] - half[0] + 1 > len(half):
                    out.append(t("e_gap", c=C_(c)))
        # standard class grid (soft): warn when a move leaves a hole or uses a 7th slot on a forbidden day
        if self.cfg.get('strict_class_grid') and self.state.get('class_required'):
            pos = lambda x: moves.get(x['id'], (x['day'], x['start']))
            lb = self.cfg['lunch_boundary']
            for c in {self.L[i]['class'] for i in moves}:
                if str(c).startswith("REM:"):
                    continue
                used = {(pos(x)[0], sl) for x in self.L.values() if x['class'] == c
                        for sl in range(pos(x)[1], pos(x)[1] + x['duration'])}
                req = {tuple(x) for x in self.state['class_required'].get(c, [])}
                late = any((d, self.cfg['slots'] - 1) in used for d in self.cfg.get('no_slot7_days', []))
                if (req - used) or late:
                    out.append(t("e_grid", c=C_(c)))
        return list(dict.fromkeys(out))

    def evaluate(self, lid, d, s):
        """-> (status, message, moves)"""
        l = self.L[lid]
        if (d, s) == (l['day'], l['start']):
            return 'current', t('e_current'), {}
        if self.locked(l):
            return 'red', t('e_locked'), {}
        if (d, s) not in l['domain_set']:
            return 'red', t('e_blocked'), {}
        tgt = self.cells(l, d, s)
        conflicts = set()
        for c in tgt:
            conflicts |= self.class_conflicts(l, c)
            for tt in l['teachers']:
                conflicts |= self.teacher_occ.get((tt,) + c, set())
        conflicts.discard(lid)

        if not conflicts:
            moves = {lid: (d, s)}
            errs = self.check(moves)
            if errs:
                return 'red', t('sep').join(errs), {}
            w = self.gap_warnings(moves)
            blk = self.block_note(lid, moves)
            return 'green', t('e_free') + blk + (' ⚠ ' + t('sep').join(w) if w else ''), moves

        if len(conflicts) == 1:
            m = self.L[next(iter(conflicts))]
            if self.locked(m):
                return 'red', t("e_conf_locked", d=self.describe(m)), {}
            if m['class'] == l['class'] and set(m['teachers']) == set(l['teachers']):
                return 'red', t("e_noop", d=self.describe(m)), {}
            if bool(m.get('remedial')) != bool(l.get('remedial')):      # remediation only swaps with remediation
                return 'red', t("e_rem_swap"), {}
            if m['duration'] != l['duration']:
                return 'red', t("e_diffdur", d=self.describe(m)), {}
            moves = {lid: (d, s), m['id']: (l['day'], l['start'])}
            errs = self.check(moves)
            if errs:
                return 'red', t("e_swap_imp", d=self.describe(m), e=t('sep').join(errs)), {}
            affected = [tt for tt in m["teachers"] if tt not in l['teachers']]
            who = []
            if affected: who.append(t('e_w_teacher', x=T_(affected)))
            if m['class'] != l['class']: who.append(t('e_w_class', x=C_(m['class'])))
            w = self.gap_warnings(moves)
            blk = self.block_note(lid, moves)
            return ('yellow', t("e_swap", d=self.describe(m)) + blk + (t("e_affects", w=t("e_and").join(who)) if who else '')
                    + (' ⚠ ' + t('sep').join(w) if w else ''), moves)
        return 'red', t("e_conf_n", n=len(conflicts)), {}

    def block_note(self, lid, moves):
        pos = lambda x: moves.get(x['id'], (x['day'], x['start']))
        l = self.L[lid]
        for x in self.L.values():
            if x['id'] != lid and self.forms_block(l, x, pos):
                return t("e_forms2h", b=S_(base_subjects(l['subject'])[0]))
        return ''

    def status_map(self, lesson_ids, free=False):
        out = {}
        for lid in lesson_ids:
            out[lid] = {}
            for d in range(self.cfg['days']):
                for s in range(self.cfg['slots']):
                    st, msg, _ = self.evaluate(lid, d, s)
                    if free and st == 'red':
                        ok, why = self.force_ok(lid, d, s)
                        if ok and self.forced_moves(lid, d, s) is None:
                            ok, why = False, t('e_noswitch')
                        st, msg = ('orange', t('e_forced', m=msg)) if ok else ('red', why)
                    out[lid][f"{d},{s}"] = [st, msg]
        return out

    # ------------------------------------------------------------ free moves (📌 pins, adapted later by the solver)
    def chain(self, l):
        """The lesson + the lessons linked to it (split rules: they move together)."""
        while 'linked_prev' in l and l['linked_prev'] in self.L:
            l = self.L[l['linked_prev']]
        out = [l]
        while 'linked_next' in l and l['linked_next'] in self.L:
            l = self.L[l['linked_next']]; out.append(l)
        return out

    def _chain_target(self, lid, d, s):
        l = self.L[lid]
        ds = s - l['start']
        return [(m, d, m['start'] + ds) for m in self.chain(l)]

    def _levels(self, m):
        cl = self.state.get('class_level') or {}
        return [cl[c] for c in self.classes_of(m) if c in cl]

    def _t_off(self, m, dd, ss):
        un = self.state.get('teacher_unavailable') or {}
        return any([dd, ss + k] in un.get(tc, []) for tc in m['teachers'] for k in range(m['duration']))

    def force_ok(self, lid, d, s):
        lb, S = self.cfg['lunch_boundary'], self.cfg['slots']
        for m, dd, ss in self._chain_target(lid, d, s):
            if ss < 0 or ss + m['duration'] > S:
                return False, t('e_outside')
            if m['duration'] > 1 and ss <= lb < ss + m['duration'] - 1:
                return False, t('e_lunch')
            if self.G.off_span(dd, ss, m['duration'], self._levels(m)):   # closed half-day / level's week
                return False, t('e_outside')
            if self._t_off(m, dd, ss):
                return False, t('e_t_unavail')
        return True, ''

    def _cell_ok(self, m, dd, ss):
        lb, S = self.cfg['lunch_boundary'], self.cfg['slots']
        if ss < 0 or ss + m['duration'] > S:
            return False
        if m['duration'] > 1 and ss <= lb < ss + m['duration'] - 1:
            return False
        if self.G.off_span(dd, ss, m['duration'], self._levels(m)) or self._t_off(m, dd, ss):
            return False
        return True

    def forced_moves(self, lid, d, s):
        """Forced move WITH automatic switch (window exchange): the dragged lesson goes to (d, s); the time window it
        lands on and the window it leaves are grown until each holds whole lessons of the class, then the class's
        lessons in the two windows are exchanged (works for 1h <-> 2h too). Clashes a switch cannot solve (a teacher
        busy in another class, a blocked hour) stay and are shown as conflicts."""
        l = self.L[lid]
        plain = {m['id']: (dd, ss) for m, dd, ss in self._chain_target(lid, d, s)}
        if l.get('also_classes'):                        # joint session: no automatic switch (conflicts are shown)
            return plain
        c, d0, ds = l['class'], l['day'], s - l['start']
        S = self.cfg['slots']
        mine = [x for x in self.L.values() if x['class'] == c]
        cl = [m for m in self.chain(l) if m['class'] == c and m['day'] == d0]
        a0 = min(m['start'] for m in cl); b0 = max(m['start'] + m['duration'] for m in cl)
        for _ in range(10):                                # source window [a0, b0) on d0  <->  [a0+ds, b0+ds) on d
            if a0 < 0 or b0 > S or a0 + ds < 0 or b0 + ds > S:
                return None
            if d0 == d and a0 < b0 + ds and a0 + ds < b0:  # the two windows overlap: rotate instead
                return self._rotate(l, cl, d, ds, plain)
            na, nb = a0, b0
            for x in mine:
                e_ = x['start'] + x['duration']
                if x['day'] == d0 and x['start'] < b0 and e_ > a0:
                    na, nb = min(na, x['start']), max(nb, e_)
                if x['day'] == d and x['start'] < b0 + ds and e_ > a0 + ds:
                    na, nb = min(na, x['start'] - ds), max(nb, e_ - ds)
            if (na, nb) == (a0, b0):
                break
            a0, b0 = na, nb
        else:
            return None
        moves = {}
        for x in mine:
            e_ = x['start'] + x['duration']
            if x['day'] == d0 and x['start'] >= a0 and e_ <= b0:
                moves[x['id']] = (d, x['start'] + ds)
            elif x['day'] == d and x['start'] >= a0 + ds and e_ <= b0 + ds:
                moves[x['id']] = (d0, x['start'] - ds)
        ids = set(moves)
        for i in list(ids):                                # a split chain must move entirely
            if any(m['id'] not in ids for m in self.chain(self.L[i])):
                return None
        if any(not self._cell_ok(self.L[i], dd, ss) for i, (dd, ss) in moves.items()):
            return None
        return moves

    def _rotate(self, l, cl, d, ds, plain):
        """Same-day shift that overlaps itself: the dragged lessons take the target cells, the other lessons of the
        union window keep their order and fill the cells that are left."""
        c = l['class']
        a = min(m['start'] for m in cl); b = max(m['start'] + m['duration'] for m in cl)
        ua, ub = min(a, a + ds), max(b, b + ds)
        mine = [x for x in self.L.values() if x['class'] == c and x['day'] == d and x['id'] not in plain]
        for _ in range(10):
            na, nb = ua, ub
            for x in mine:
                if x['start'] < ub and x['start'] + x['duration'] > ua:
                    na, nb = min(na, x['start']), max(nb, x['start'] + x['duration'])
            if (na, nb) == (ua, ub):
                break
            ua, ub = na, nb
        if ua < 0 or ub > self.cfg['slots']:
            return None
        others = sorted((x for x in mine if x['start'] >= ua and x['start'] + x['duration'] <= ub), key=lambda x: x['start'])
        taken = {ss + k for i, (dd, ss) in plain.items() for k in range(self.L[i]['duration'])}
        free = [k for k in range(ua, ub) if k not in taken]
        moves, p = dict(plain), 0
        for x in others:
            if any(m['id'] not in plain and m['id'] not in {o['id'] for o in others} for m in self.chain(x)):
                return None
            seg = free[p:p + x['duration']]
            if len(seg) < x['duration'] or seg != list(range(seg[0], seg[0] + x['duration'])):
                return None
            moves[x['id']] = (d, seg[0]); p += x['duration']
        if any(not self._cell_ok(self.L[i], dd, ss) for i, (dd, ss) in moves.items()):
            return None
        return moves

    def _try(self, moves):
        """Conflicts the timetable would have after `moves` (no change to self)."""
        e2 = ScheduleEditor.__new__(ScheduleEditor)
        e2.__dict__.update(self.__dict__)
        e2.L = {k: dict(v) for k, v in self.L.items()}
        for i, (dd, ss) in moves.items():
            e2.L[i]['day'], e2.L[i]['start'] = dd, ss
        e2._index()
        return e2.conflicts()

    def move_free(self, lid, d, s):
        """Free mode: a valid move/swap is applied normally; otherwise the lesson (and its chain) is placed anyway.
        The moved lesson(s) get a 📌 pin."""
        st, msg, moves = self.evaluate(lid, d, s)
        if st == 'current':
            return False, msg
        if st in ('green', 'yellow'):
            for i, (dd, ss) in moves.items():
                self.L[i]['day'], self.L[i]['start'] = dd, ss
            self.pins.add(lid)
        else:
            ok, why = self.force_ok(lid, d, s)
            if not ok:
                return False, why
            fm = self.forced_moves(lid, d, s)
            if fm is None:
                return False, t('e_noswitch')
            for i, (dd, ss) in fm.items():
                self.L[i]['day'], self.L[i]['start'] = dd, ss
                self.pins.add(i)
            msg = t('e_forced', m=msg)
        self._index()
        self.fix_reception()
        return True, msg

    def preview(self, lid, d, s, free=False):
        """What a move WOULD do, without doing it (for the confirmation popup).
        -> {"status", "msg", "moves": {id: (d, s)}, "clash": [ids left in conflict], "entities": [("teacher"|"class", key)]}
        entities = the OTHER teachers/classes touched (not the ones of the dragged lesson), in a stable order."""
        l = self.L[lid]
        st, msg, moves = self.evaluate(lid, d, s)
        clash = []
        if free and st == 'red':
            ok, why = self.force_ok(lid, d, s)
            if not ok:
                return {"status": "red", "msg": why, "moves": {}, "clash": [], "entities": []}
            st, msg = 'orange', t('e_forced', m=msg)
            moves = self.forced_moves(lid, d, s)
            if moves is None:
                return {"status": "red", "msg": t('e_noswitch'), "moves": {}, "clash": [], "entities": []}
            c0 = set(self.conflicts())
            clash = sorted(set(self._try(moves)) - c0)
        own_t, own_c = set(l['teachers']), l['class']
        ents = []
        for i in [x for x in moves if x != lid] + clash:
            m = self.L[i]
            if self.chain(m) and any(x['id'] == lid for x in self.chain(m)) and i not in clash:
                continue                                   # the dragged lesson's own split partners
            for tt in m['teachers']:
                if tt not in own_t and ("teacher", tt) not in ents:
                    ents.append(("teacher", tt))
            if m['class'] != own_c and ("class", m['class']) not in ents and not str(m['class']).startswith("REM:"):
                ents.append(("class", m['class']))
        # everything involved, for the popup's teacher/class switch (the "other" entities first)
        allt, allc = [], []
        for i in list(moves) + clash:
            m = self.L[i]
            allt += [x for x in m['teachers'] if x not in allt]
            if m['class'] not in allc and not str(m['class']).startswith("REM:"):
                allc.append(m['class'])
            allc += [k for k in m.get('blocks_classes', []) if k not in allc]
        allt.sort(key=lambda x: x in own_t)
        allc.sort(key=lambda x: x == own_c)
        return {"status": st, "msg": msg, "moves": moves, "clash": clash, "entities": ents,
                "teachers": allt, "classes": allc}

    def rename_teachers(self, mapping):
        """Rename teachers in this solution only (lessons, windows, reception). mapping = {old: new}.
        -> (ok, message). Refuses empty names and names that would merge two teachers."""
        mapping = {str(o): str(n).strip() for o, n in mapping.items() if str(n).strip() and str(n).strip() != str(o)}
        if not mapping:
            return False, t("rn_nothing")
        names = {x for l in self.L.values() for x in l['teachers']}
        final = [mapping.get(x, x) for x in names]
        dup = sorted({x for x in final if final.count(x) > 1})
        if dup:
            return False, t("rn_dup", x=", ".join(dup))
        R = lambda x: mapping.get(x, x)
        for l in self.L.values():
            l['teachers'] = [R(x) for x in l['teachers']]
        for key in ('teacher_windows', 'teacher_windows_info'):
            if isinstance(self.state.get(key), dict):
                self.state[key] = {R(k): v for k, v in self.state[key].items()}
        if isinstance(self.state.get('reception_teachers'), list):
            self.state['reception_teachers'] = [R(x) for x in self.state['reception_teachers']]
        self.rec = {R(k): v for k, v in self.rec.items()}
        self.rec_removed = {R(x) for x in self.rec_removed}
        self._index()
        return True, t("rn_done", n=len(mapping))

    def toggle_pin(self, lid):
        ids = [m['id'] for m in self.chain(self.L[lid])]
        if lid in self.pins:
            self.pins -= set(ids)
        else:
            self.pins |= set(ids)

    def conflicts(self):
        """Lessons in conflict (double booking or outside their allowed hours) -> {lid: reason}."""
        out = {}
        for key, ids in list(self.class_occ.items()) + list(self.teacher_occ.items()):
            if len(ids) > 1:
                for i in ids:
                    out.setdefault(i, t('e_c_double', w=C_(key[0]) if key in self.class_occ else key[0]))
        for key, ids in self.rem_occ.items():
            clash = ids | self.class_occ.get(key, set())
            if self.class_occ.get(key):
                for i in clash:
                    out.setdefault(i, t('e_c_double', w=C_(key[0])))
        for l in self.L.values():
            if l['domain_set'] and (l['day'], l['start']) not in l['domain_set']:
                out.setdefault(l['id'], t('e_blocked'))
        return out

    # ------------------------------------------------------------ mutation
    def apply(self, lid, d, s):
        st, msg, moves = self.evaluate(lid, d, s)
        if st not in ('green', 'yellow'):
            return False, msg
        for i, (dd, ss) in moves.items():
            self.L[i]['day'], self.L[i]['start'] = dd, ss
        self._index()
        self.fix_reception()
        return True, msg

    # ------------------------------------------------------------ reception hours (not lessons)
    def _rec_state(self):
        return {'lessons': [{'day': l['day'], 'start': l['start'], 'duration': l['duration'], 'teachers': l['teachers']}
                            for l in self.L.values()],
                'config': self.cfg, 'reception': self.rec, 'reception_removed': sorted(self.rec_removed),
                'reception_teachers': self.state.get('reception_teachers'),
                'teacher_windows': self.state.get('teacher_windows'),
                'teacher_windows_info': self.state.get('teacher_windows_info')}

    def fix_reception(self):
        """After a move: reception hours now covered by a lesson are placed again automatically."""
        self.rec = rc.ensure(self._rec_state())['reception']

    def move_rec(self, tc, d, s):
        ok, why = rc.free_for(self._rec_state(), tc, d, s)
        if not ok:
            return False, t(why)
        self.rec[tc] = [d, s]
        return True, t('rec_moved', t=tc, d=i18n.day(d), s=s + 1)

    def add_rec(self, tc):
        self.rec_removed.discard(tc)
        st = self._rec_state()
        if tc not in rc.teachers_of(st):
            st['reception_teachers'] = list(rc.teachers_of(st)) + [tc]
            self.state['reception_teachers'] = st['reception_teachers']
        cell = rc.best_cell(st, tc)
        if cell:
            self.rec[tc] = cell
        return cell

    def remove_rec(self, tc):
        self.rec.pop(tc, None); self.rec_removed.add(tc)

    def rec_status(self, tc):
        return rc.status_map(self._rec_state(), tc, {'current': t('e_current'), 'free': t('rec_free'),
                                                     'rec_off': t('rec_off'), 'rec_busy': t('rec_busy'),
                                                     'rec_window': t('rec_window')})

    def export_state(self):
        st = copy.deepcopy(self.state)
        st['lessons'] = [{k: v for k, v in l.items() if k != 'domain_set'} for l in self.L.values()]
        st['pins'] = sorted(self.pins)
        st['reception'] = copy.deepcopy(self.rec)
        st['reception_removed'] = sorted(self.rec_removed)
        return st

    def to_schedule_df(self):
        rows = [{'Class': cc, 'Day': l['day'], 'Slot': l['start'] + k, 'Subject': l['subject'],
                 'Teachers': ', '.join(l['teachers']), 'Classes': ', '.join(l.get('blocks_classes', [])), 'RemSubject': l.get('rem_subject', ''),
                 'Joint': l.get('joint', '') or ''}
                for l in self.L.values() for k in range(l['duration']) for cc in [l['class']] + list(l.get('also_classes', []))]
        return pd.DataFrame(rows)

    def hard_violations(self):
        """Full-schedule audit (should stay empty; edits can only produce valid states)."""
        v = []
        for key, ids in list(self.class_occ.items()) + list(self.teacher_occ.items()):
            if len(ids) > 1:
                v.append(t("e_double", k=key))
        return v
