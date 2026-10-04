# Generic timetable solver: data model and migration plan (for approval)

## Principles (from your answers)
1. **Nothing is hard-coded.** Every value comes from a data table. A school type is just a **preset file** of default values, stored on the server and loaded when the app starts.
2. **Every table is loadable, exportable and editable**, including after an upload and including the demo/preset data. Each table has:
   - an editable grid;
   - ⬇️ export (CSV / XLSX);
   - ⬆️ import (replace or merge, with a confirmation before overwriting).
3. **Settings are layered:** preset → school → level (year) → teacher/class.
   - A lower level overrides a higher one. Examples: a time profile per level, availability per teacher.
4. **First preset:** `presets/middle_school_dz.json`, built from today's middle-school values.
   - Primary and secondary presets come later as new files. The engine itself doesn't change for them.

## Tables
| # | Table | Main columns | Notes |
|---|---|---|---|
| 1 | **time_profiles** | days, periods (label, start, end, morning/afternoon), lunch, closed half-days, week cycle (A/B) | **Per level** (each year points to a profile) |
| 2 | **stages** | id, name, policy | primary / middle / secondary / custom; mixed schools have several |
| 3 | **years** | id, name, stage, time_profile, order | Free number and names (1AS–3AS, 1AM–4AM, 1AP–5AP, custom) |
| 4 | **tracks** | id, name, parent track, years where it exists | A tree, e.g. common core (1AS) → Math, Experimental sciences (2–3AS). Empty = no tracks |
| 5 | **classes** | id, year, track, number of students, home room (optional) | Classes = year × track × number |
| 6 | **subjects** | id, names (en/ar), color | |
| 7 | **room_types / rooms** | type, count (or named rooms), capacity, subjects served, fallback type | |
| 8 | **curriculum** | year, track, subject, hours (course/TD/TP/practice), room type, allowed blocks, max per day, frequency (weekly / alternate weeks) | Class↔subject links come from here. Exceptions are set per class |
| 9 | **teachers** | id, name (optional), subjects, status, max hours, fixed years/tracks/classes (optional), availability | Fixed years/tracks/classes are hard limits for auto-assign |
| 10 | **teacher_availability** | teacher, day, period(s), week (A/B/both), unavailable or preferred | Each teacher's times can be changed |
| 11 | **subject_unavailable** | subject, day, periods, applies to (teachers / classes) | Generalises today's pedagogical windows |
| 12 | **assignment** | teacher, class, subject, part (course/TD/TP), hours | Manual, imported, or auto-assigned (respecting the fixings) |
| 13 | **session_templates** | kind = `split_class` / `multi_class` / `parallel_subjects`, years/classes, groups & parts, frequency, swap, duration, preferred periods, rooms | One generic mechanism covers split groups (تفويج), merged classes, parallel options, remedial and any special case |
| 14 | **fixed_sessions** | session, day, period, week | External teachers, or any session placed by hand before solving |
| 15 | **policies** | grid, gaps, comfort, priority, period costs, reception, remedial costs… | Soft rules with weights, per stage/level |

**Student-group rule (the core of the generalisation):** every session belongs to a student group, which can be:
- a class;
- a part of a class (A/B);
- a group spanning several classes.

Two sessions clash when their groups share students. This one rule replaces today's specific modes (SYNC_1H, TRI, remedial pairs…).

## Migration plan (step by step; each step is tested on your school, which must give the same result as today)
1. **Data layer:** a loader for the preset JSON, plus the generic tables. A converter from today's files (classes.csv, curriculum.csv, split_rules.csv, اسناد.csv…) to the new tables, so old zips still load.
2. **Engine reads the tables:** days/periods/lunch/closed half-days per level, policies, availability, and the A/B week.
   - Today's `SchedulerConfig` constants become values loaded from the preset.
3. **Generic session templates** replace the split-rule modes and the remedial code paths.
4. **UI:**
   - one table editor component (edit / import / export) used for all 15 tables;
   - the setup guide gets the extra steps (stage/years → tracks → classes → subjects/rooms → curriculum → teachers → assignment → special sessions).
5. **Regression:** your school data → same lesson count, 0 conflicts, KPIs within noise of today's results. Edit, adapt and improve keep working.

## Values I had to assume in the preset (please check)
- Period clock times: 08:00–12:00 and 13:00–16:00.
- Class size: 35 students.
- Room capacity: 40 (gym 80).
- Allowed blocks:
  - [1, 2] for subjects with ≥ 2 course hours;
  - [2] for the PHYS/SCIENCE TP;
  - max 1 per day.
- Teacher max hours: 20, with مميز = −2 h (taken from the wizard's defaults).

## Out of scope
Free course choice (university): not applicable in Algeria, as the programme is fixed by the administration.

## Implementation status
**Done: step 1 + step 2 core**
- `timegrid.py` is the only place that knows the week: days, periods, lunch, closed half-days, last period.
  - It is used by the solver, editor, reception, presolve, rooms, export, app and both drag-and-drop components.
  - No more hard-coded Tuesday, periods 0–3/4–6 or period 7.
- `presets.py` loads `presets/*.json` from the server at start-up.
  - The solver settings (time profile and every weight) come from the preset.
  - The default tables come from the preset: curriculum, subject unavailable times, rooms, and split templates converted to rules.
  - The setup guide's base curriculum comes from it too.
- **Old saved versions still load:** versions without stored week settings use the middle-school week.
- **Regression on your school:**
  - 523 lessons, 0 conflicts, KPIs within noise.
  - The preset tables are identical to the old sample files.
  - The forced switch still gives 0 duplicates.
  - The page tests pass.
- **Generic check:** the same school with Wednesday afternoon closed instead of Tuesday (settings only) gives 0 conflicts and 0 lessons on Wednesday afternoon.

**Done: step 2b**
- **Time profile per level:**
  - each year in the preset can point to its own time profile (number of periods, extra closed half-days);
  - the solver gives each class only the cells of its level's week;
  - the editor and the remedial sessions (all their classes' levels) respect it too.
  - Restriction: all profiles share the school's days and lunch position.
- **Teacher availability table** (`Teacher_ID, Day, Periods, Kind`):
  - "unavailable" is hard, "avoid" is soft (`teacher_avoid_cost`);
  - stored per workspace in the database, whatever the data source;
  - editable in the Data page, with CSV export and CSV/XLSX import (confirmation before replacing);
  - respected by the solver, the editor's forced moves and reception hours.
- **Capacity check before solving:** a class needing more hours than its level's week, or a teacher with more hours than his available cells, stops the run with a clear list.
- **Hidden hard-coded rules removed:**
  - INFO TP forced to 2 h in the loader;
  - INFO exempt from the same-day check (now `same_day_exempt` in the preset);
  - Arabic+Math as the default remedial pair (now from the preset's remedial template).

**Next**
- **Step 3:** the solver reads session templates directly (split_class / multi_class / parallel_subjects, A/B weeks), replacing split rules and remedial code paths.
- **Step 4:**
  - years / tracks / classes tables and the extended setup guide;
  - one table editor (edit / import / export) for all tables, including demo/preset data;
  - a preset selector.

## Done: step 3 (special sessions)
- **Joint sessions** (template kind `"joint"`, editable table *Joint sessions*: ID, Classes, Subjects, Hours, Block; `;`-separated):
  one lesson shared by all listed classes, with one or more subjects taught in parallel (merged classes / option groups).
  Counts as class time for every class (clashes, grid, gaps, capacity). Teachers = all teachers assigned to those subjects
  in those classes; one room per subject group. It replaces those subjects' course hours (Hrs_Cours) in those classes;
  a mismatch with the curriculum stops the solve with a message (manager corrects it).
- **Split rules** unchanged (already generic: any subjects / hours / frequency / mode).
- **Remedial** reads its template: `preferred_periods` (0-based) and `ends_day`.
- Editor/Adapt: joint lessons occupy all their classes; dragging a joint lesson shows conflicts but does no automatic switch.
- **Limits:** A/B weeks only via split-rule frequency 2 (both teachers reserved every week); joint TD/TP hours not covered
  (course hours only); joint sessions must sit inside one level's open time.

## Done: step 4 (structure + editing)
- **tables.py**: one generic editor (edit / save / export / import with confirmation / back to source). Every school
  table on the Data page (classes, curriculum, windows, rooms, split rules, staff, grid) is editable after loading
  (demo, upload or guide); edits are stored per workspace + data source and re-applied at start (marked ✏️).
  Availability, joint sessions and week-per-level use the same editor.
- **Week per level** table (Level, Periods, Closed "day:morning|afternoon|all;...") -> cfg.level_profiles
  (defaults from the preset's years).
- **Preset selector** on the Data page (lists presets/*.json).
- **Guide step 1**: years (free number/names, from the preset) and tracks (with the years they exist in) -> levels
  = year or year-track; classes = level × count. Track levels start from their year's curriculum; new years start
  empty and the curriculum is edited in step 2 ("Edit the curriculum").
- **Limits:** the guide's group-rule questions and optional subjects (Amazigh, arts, IT) are still the middle-school
  ones (other schools: edit the split-rules table); per-level weeks share days and lunch; teacher fixed
  tracks/years are expressed through the assignment.
