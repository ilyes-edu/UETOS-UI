# Beta audit – نظام إعداد الجداول الزمنية (نسخة تجريبية)

## Requested items
- [x] `matplotlib` in requirements (it was missing; the free-rooms colour table needed it and would have crashed)
- [x] Everything in Arabic **and** English, data files too
  - Data files can use internal codes, English labels or Arabic labels (headers and values: subjects, levels, classes, room types, TD/TP, days, hours 1–7, yes/no)
  - Upload accepts CSV **and** Excel; template download (CSV / Excel) in the interface language
  - Data tab, guide export, split-rules download and room-occupancy CSV all use the interface language
  - Runtime audit (Arabic): no untranslated labels left in the sample, guide or upload modes
- [x] Renamed: **نظام إعداد الجداول الزمنية – نسخة تجريبية** / Timetable Preparation System – Evaluation version (beta)
- [x] UI: header banner with beta badge, lighter sidebar headings, tab / card / button styling, beta footer
- [x] Only one from-scratch builder: the setup guide (old "create/edit in the app" builder removed)
- [x] Sidebar cleanup: assignment-matrix upload only in upload mode; "files still needed" only in upload mode; unused `sample_data_school/` removed
- [x] Assignment board: select a teacher → click classes to assign (click again to remove); ✖ empty a teacher; empty the subject; empty everything; fast clicks can't be lost (full state sent)

## Found during the audit (fixed)
- [x] Example school showed an "unknown subject codes" panel on first open (windows file used HIST/GEO/CIVICS/PE/ART_MUSIC) → file now uses curriculum codes
- [x] Old test versions removed from `schedules/` (only the reference version is kept)
- [x] One untranslated field label ("name") in the Edit tab
- [x] Guide summary / curriculum preview had English column headers
- [x] Guide recalculated class hours on every click → cached (faster board)

## Suggestions for the beta (not done yet)
1. **Storage**: versions and guide projects are files on the server. On a shared/cloud host, testers overwrite each other and files can vanish on restart → one workspace per tester, or a database.
2. **Delete / rename versions** from the UI (currently only by deleting files).
3. **Set `ADMIN_PASSWORD`** before handing out the beta, otherwise the advanced settings are open to all.
4. **Feedback button** (form or e-mail link) with the version name attached, so testers' reports are traceable.
5. **Teachers with two subjects** (e.g. history-geography + civics taught by one teacher) in the guide.
6. **Room occupancy in the PDF/Excel export** (now only a CSV in the rooms view).
7. **Arabic+Math remedial = 2 rooms** in the solver (the rooms view already shows 2).
8. **Free-text descriptions** in the example files are still English (codes/labels are translated; descriptions are user text).
9. **Solve time**: 10 minutes on 2 CPUs. Show a clear progress/ETA message, and suggest 4+ CPUs for the server.
10. **Short user guide** (1–2 pages, AR/EN) + a "What's new / known limits" panel for testers.
11. **Row-level upload validation** (e.g. "line 7: unknown subject 'Physique'") instead of a generic error.
12. **Mobile/tablet**: the full timetables need a wide screen; show a hint on small screens.

## Follow-up implemented (beta 2)
| # | Item | Status |
|---|---|---|
| 1 | DB storage (SQLAlchemy: MySQL via secrets `[connections.db] url`, else SQLite `data/app.db`), one workspace per tester | ✅ |
| 2 | Rename / delete / delete-all versions (Compare tab → Manage versions) | ✅ |
| 3 | Admin password hashed in DB (default `beta2026`), change-password popover | ✅ |
| 5 | Two-subject teachers → Guide → known limits | ✅ |
| 6 | Room occupancy section in PDF & XLSX export | ✅ |
| 7 | ~~Arabic+Math remedial = 2 rooms~~ → corrected: grouped remediation alternates weekly = 1 session, 1 room; slot-6 remediation ends the day | ✅ |
| 9 | Solve in background thread: countdown, phase, progress bar, CPU hint (<4 CPUs) | ✅ |
| 10 | Guide tab AR/EN + What's new / known limits | ✅ |
| 11 | Row-level validation of uploads (file · line N · message) | ✅ |
| 12 | Small-screen hint (<900 px); full mobile layout listed as limit | ✅ |
Tests: AppTest audit (3 sources, 0 exceptions), store round-trip, 60 s solve (13/13 remedial placed), PDF/XLSX rooms export.
