"""Time structure of the school week – the ONLY place that knows days / periods / lunch / closed half-days.

Every module asks this one instead of hard-coding (Tuesday afternoon, periods 0-3 / 4-6, last period …).
Values come from the preset / solver settings (SchedulerConfig or a saved state's "config").
"""


class Grid:
    def __init__(self, days=5, slots=7, lunch_boundary=3, closed=None, no_extra_days=None, level_off=None):
        self.days = int(days)
        self.slots = int(slots)
        self.lunch = int(lunch_boundary)                       # last morning period index
        # closed half-days: [[day, "morning"|"afternoon"], ...]
        self.closed = [tuple(x) for x in (closed if closed is not None else [])]
        self.no_extra_days = list(no_extra_days or [])
        # per-level time profiles: {level: {(day, period), ...}} cells that do not exist for that level
        self.level_off = {str(k): {tuple(c) for c in v} for k, v in (level_off or {}).items()}

    # ---- halves
    @property
    def morning(self):
        return list(range(0, self.lunch + 1))

    @property
    def afternoon(self):
        return list(range(self.lunch + 1, self.slots))

    @property
    def last(self):
        return self.slots - 1

    @property
    def n_morning(self):
        return self.lunch + 1

    def half(self, s):
        return "morning" if s <= self.lunch else "afternoon"

    # ---- availability
    def is_off(self, d, s, levels=None):
        """Closed for the whole school, or (when `levels` is given) closed for any of these levels."""
        if (d, self.half(s)) in self.closed:
            return True
        if levels:
            for lv in ([levels] if isinstance(levels, str) else levels):
                if (d, s) in self.level_off.get(str(lv), ()):
                    return True
        return False

    def off_span(self, d, s, dur=1, levels=None):
        """True when a block of `dur` periods starting at (d, s) is outside the week (bounds, closed half-day,
        or outside the time profile of one of `levels`)."""
        if not (0 <= d < self.days and 0 <= s and s + dur <= self.slots):
            return True
        return any(self.is_off(d, s + k, levels) for k in range(dur))

    def crosses_lunch(self, s, dur):
        return dur > 1 and s <= self.lunch < s + dur - 1

    def open_slots(self, d, levels=None):
        return [s for s in range(self.slots) if not self.is_off(d, s, levels)]

    def off_cells(self, levels=None):
        return [(d, s) for d in range(self.days) for s in range(self.slots) if self.is_off(d, s, levels)]

    def to_dict(self):
        return {"days": self.days, "slots": self.slots, "lunch_boundary": self.lunch,
                "closed": [list(x) for x in self.closed], "no_slot7_days": self.no_extra_days,
                "level_off": {k: sorted([list(c) for c in v]) for k, v in self.level_off.items()}}


DEFAULT_CLOSED = [[2, "afternoon"]]          # only used for OLD saved versions that did not store their week


def from_config(cfg):
    return Grid(cfg.days, cfg.slots, cfg.lunch_boundary, getattr(cfg, "closed_halfdays", DEFAULT_CLOSED),
                getattr(cfg, "no_slot7_days", []), level_off_from_profiles(cfg))


def from_state_cfg(c):
    """From a saved editable state's "config" dict (older versions: middle-school week)."""
    c = c or {}
    return Grid(c.get("days", 5), c.get("slots", 7), c.get("lunch_boundary", 3),
                c.get("closed", DEFAULT_CLOSED), c.get("no_slot7_days", []), c.get("level_off", {}))


def level_off_from_profiles(cfg):
    """cfg.level_profiles = {level: {"slots": n, "closed": [[day, half], ...]}} -> {level: [(d, s), ...]}.
    A level's week is the school week minus its extra closed half-days and minus the periods after its last one."""
    out = {}
    lb = cfg.lunch_boundary
    for lv, p in (getattr(cfg, "level_profiles", None) or {}).items():
        n = int(p.get("slots", cfg.slots))
        closed = {(int(d), h) for d, h in p.get("closed", [])}
        cells = [(d, s) for d in range(cfg.days) for s in range(cfg.slots)
                 if s >= n or (d, "morning" if s <= lb else "afternoon") in closed or (d, "all") in closed]
        if cells:
            out[str(lv)] = cells
    return out


# grid used by the stand-alone KPI/report functions (set by the app / engine when settings are known)
CURRENT = Grid(closed=DEFAULT_CLOSED, no_extra_days=[4])


def set_current(g):
    global CURRENT
    CURRENT = g
    return g
