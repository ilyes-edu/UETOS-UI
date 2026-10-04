"""Reception hour (ساعة استقبال الأولياء): ONE hour per week per teacher, stored in the editor state as
state['reception'] = {teacher: [day, slot]}.  Not a lesson: no class, no room.

Automatic placement, best first:
  0. a single gap of the teacher (free hour between two busy hours of the same half-day)  -> fills the gap
  1. an hour right before / after his lessons on a day he already works (same half-day, never the last slot)
  2. any free hour on a day he already works
Manual changes (drag in the teacher tables, add / remove) are kept as long as the hour stays free.
"""
import timegrid



def _busy(state):
    busy = {}
    for l in state["lessons"]:
        for k in range(l["duration"]):
            for tc in l["teachers"]:
                busy.setdefault(tc, set()).add((l["day"], l["start"] + k))
    return busy


def _cfg(state):
    c = state.get("config", {})
    return c.get("days", 5), c.get("slots", 7), c.get("lunch_boundary", 3)


def teachers_of(state):
    rt = state.get("reception_teachers")
    if rt is not None:
        return list(rt)
    return sorted({tc for l in state["lessons"] for tc in l["teachers"]}, key=str)


def is_off(state, d, s):
    return timegrid.from_state_cfg(state.get("config")).off_span(d, s)        # bounds + closed half-days


def free_for(state, tc, d, s, busy=None):
    """-> (ok, reason_key)"""
    busy = busy if busy is not None else _busy(state)
    if is_off(state, d, s):
        return False, "rec_off"
    if [d, s] in (state.get("teacher_unavailable") or {}).get(tc, []):
        return False, "rec_off"
    if (d, s) in busy.get(tc, set()):
        return False, "rec_busy"
    win = {tuple(x) for x in (state.get("teacher_windows_info") or state.get("teacher_windows") or {}).get(tc, [])}
    if (d, s) in win:
        return False, "rec_window"
    return True, ""


def best_cell(state, tc, busy=None):
    busy = busy if busy is not None else _busy(state)
    D, S, lb = _cfg(state)
    mine = busy.get(tc, set())
    days = sorted({d for d, _ in mine})
    half = lambda s: 0 if s <= lb else 1
    cands = []
    for d in days:
        for s in range(S):
            ok, _ = free_for(state, tc, d, s, busy)
            if not ok:
                continue
            prev_, next_ = (d, s - 1) in mine and half(s - 1) == half(s), (d, s + 1) in mine and half(s + 1) == half(s)
            if prev_ and next_:
                score = 0
            elif (prev_ or next_) and s < S - 1:
                score = 1
            else:
                score = 2
            cands.append((score, half(s), s, d))
    if not cands:
        return None
    _, _, s, d = min(cands)
    return [d, s]


def ensure(state, keep=True):
    """Place a reception hour for every reception teacher that has none (or whose hour is no longer free)."""
    rec = dict(state.get("reception") or {}) if keep else {}
    busy = _busy(state)
    removed = set(state.get("reception_removed") or [])
    for tc in teachers_of(state):
        if tc in removed:
            rec.pop(tc, None)
            continue
        cur = rec.get(tc)
        if cur and free_for(state, tc, cur[0], cur[1], busy)[0]:
            continue
        cell = best_cell(state, tc, busy)
        if cell:
            rec[tc] = cell
        else:
            rec.pop(tc, None)
    state["reception"] = rec
    return state


def status_map(state, tc, texts):
    """For the drag & drop tables: {'d,s': [status, message]} for moving tc's reception hour."""
    busy = _busy(state)
    cur = (state.get("reception") or {}).get(tc)
    D, S, _ = _cfg(state)
    out = {}
    for d in range(D):
        for s in range(S):
            if cur and [d, s] == list(cur):
                out[f"{d},{s}"] = ["current", texts["current"]]
                continue
            ok, why = free_for(state, tc, d, s, busy)
            out[f"{d},{s}"] = ["green", texts["free"]] if ok else ["red", texts[why]]
    return out
