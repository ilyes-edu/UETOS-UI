"""English / Arabic strings for the whole application (UI, editor messages, KPIs, import warnings)."""
import re

LANG = "en"


def set_lang(lang):
    global LANG
    LANG = lang if lang in ("en", "ar") else "en"


def is_ar():
    return LANG == "ar"


def t(key, **kw):
    entry = S.get(key)
    if entry is None:
        return key.format(**kw) if kw else key
    txt = entry[1] if LANG == "ar" else entry[0]
    return txt.format(**kw) if kw else txt


# ------------------------------------------------------------------ domain labels
DAYS = {"en": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
        "ar": ["الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس"]}

SUBJECT_AR = {"REMEDIAL": "استدراك", "ARABIC": "لغة عربية", "ISLAMIC": "تربية إسلامية", "MATH": "رياضيات", "FRENCH": "لغة فرنسية",
              "ENGLISH": "لغة إنجليزية", "PHYSICS": "علوم فيزيائية", "SCIENCE": "علوم طبيعية",
              "HISTGEO": "تاريخ وجغرافيا", "INFO": "إعلام آلي", "MUSIC": "تربية موسيقية", "SPORT": "تربية بدنية",
              "PE": "تربية بدنية", "ART": "تربية تشكيلية", "CIVIC": "تربية مدنية", "AMAZIGH": "لغة أمازيغية",
              "TECH": "تكنولوجيا", "PHYS": "علوم فيزيائية", "SVT": "علوم طبيعية", "HG": "تاريخ وجغرافيا",
              "HIST": "تاريخ", "GEO": "جغرافيا", "CIVICS": "تربية مدنية", "ART_MUSIC": "تربية فنية",
              "CS": "إعلام آلي", "MATHS": "رياضيات", "EPS": "تربية بدنية", "TAMAZIGHT": "لغة أمازيغية"}
SUFFIX = {"_TD/TP": ("TD/TP", "أ.م/أ.ت"), "_Pract/TD": ("Practice/TD", "تطبيق"), "_TD": ("TD", "أ.م"),
          "_TP": ("TP", "أ.ت")}


def day(i):
    return DAYS[LANG][i]


def slot_label(i):
    if LANG == "ar":
        return f"الحصة {i + 1} ({'صباحًا' if i <= 3 else 'مساءً'})"
    return f"Slot {i + 1} ({'M' if i <= 3 else 'A'})"


def subj(code):
    """'MATH' -> 'رياضيات' ; 'SCIENCE+PHYSICS_TD/TP' -> 'علوم طبيعية + علوم فيزيائية (أ.م/أ.ت)'."""
    code = str(code)
    suffix = ""
    for sfx, (en, ar) in SUFFIX.items():
        if code.endswith(sfx):
            code, suffix = code[: -len(sfx)], (ar if LANG == "ar" else en)
            break
    parts = code.split("+")
    names = [SUBJECT_AR.get(p.upper(), p) if LANG == "ar" else p for p in parts]
    out = " + ".join(names)
    return f"{out} ({suffix})" if suffix else out


SHORT = {"ARABIC": ("ARA", "عربية"), "ISLAMIC": ("ISL", "إسلامية"), "MATH": ("MATH", "رياضيات"), "FRENCH": ("FR", "فرنسية"),
         "ENGLISH": ("ENG", "إنجليزية"), "PHYS": ("PHY", "فيزياء"), "PHYSICS": ("PHY", "فيزياء"), "SCIENCE": ("SCI", "علوم"),
         "HISTGEO": ("H-G", "تاريخ/جغ"), "HIST": ("HIST", "تاريخ"), "GEO": ("GEO", "جغرافيا"), "CIVICS": ("CIV", "مدنية"),
         "INFO": ("INFO", "إعلام"), "MUSIC": ("MUS", "موسيقى"), "ART_MUSIC": ("ART", "فنون"), "ART": ("ART", "رسم"),
         "SPORT": ("PE", "رياضة"), "PE": ("PE", "رياضة"), "REMEDIAL": ("REM", "استدراك"), "TAMAZIGHT": ("TAM", "أمازيغية"), "AMAZIGH": ("TAM", "أمازيغية")}


def subj_short(code):
    """Compact subject name for dense tables: 'INFO+FRENCH_TD' -> 'إعلام/فرنسية'."""
    code = str(code)
    for sfx in ("_TD/TP", "_Pract/TD", "_TD", "_TP"):
        code = code.replace(sfx, "")
    i = 1 if LANG == "ar" else 0
    return "/".join(SHORT.get(p.upper(), (p, p))[i] for p in code.split("+") if p)


def cls(c):
    """'1AM3' -> '1م3' in Arabic."""
    if str(c).startswith("REM:"):
        return ("استدراك – " if LANG == "ar" else "Remediation – ") + str(c)[4:]
    return re.sub(r"^(\d+)AM(\d+)$", r"\1م\2", str(c)) if LANG == "ar" else str(c)


def teachers(lst):
    return "، ".join(lst) if LANG == "ar" else ", ".join(lst)


KPI = {
    "Student Gaps (Free Periods)": "فراغات التلاميذ (ساعات فارغة)",
    "Empty Morning Slots (classes)": "حصص صباحية فارغة (الأفواج)",
    "Afternoon Hours (classes)": "ساعات المساء (الأفواج)",
    "Afternoon used w/o full morning": "مساء مستعمل دون صباح كامل",
    "Slot 1 Usage (Late Morning)": "استعمال الحصة 1",
    "Slot 4 Usage (Early Aft)": "استعمال الحصة 4 (بداية المساء)",
    "Slot 5 Usage (Mid Aft)": "استعمال الحصة 5 (وسط المساء)",
    "Slot 7 Usage (Late Dismissal)": "استعمال الحصة 7 (خروج متأخر)",
    "Max Slot 7s for any single class": "أقصى عدد للحصة 7 لفوج واحد",
    "Total Teacher Working Days": "مجموع أيام عمل الأساتذة",
    "Teacher Single-Hour Shifts": "فترات بساعة واحدة للأساتذة",
    "Teacher Single Gaps (1h)": "فراغات الأساتذة (ساعة)",
    "Teacher Double Gaps (2h)": "فراغات الأساتذة (ساعتان)",
}


def kpi(name):
    return KPI.get(name, name) if LANG == "ar" else name


# ------------------------------------------------------------------ strings  key: (English, Arabic)
S = {
    # ---- navigation (sidebar pages)
    "ds_assign": ("Assignment (جدول الإسناد)", "جدول الإسناد"),
    "school_name": ("🏫 School name", "🏫 اسم المؤسسة"),
    "nav_title": ("Pages", "الصفحات"),
    "pg_data": ("📂 Data", "📂 المعطيات"),
    "pg_plan": ("👥 Assignment", "👥 الإسناد"),
    "pg_run": ("⚙️ Generate", "⚙️ التوليد"),
    "pg_tt": ("📅 Timetables", "📅 الجداول"),
    "pg_edit": ("✋ Manual editing", "✋ التعديل اليدوي"),
    "pg_cmp": ("🗂 Versions & export", "🗂 النسخ والتصدير"),
    "pg_guide": ("📘 Guide", "📘 الدليل"),
    "next_to": ("Next step: {p} ➡️", "الخطوة التالية: {p} ⬅️"),
    "go_run": ("⚙️ Continue to generation", "⚙️ المتابعة إلى التوليد"),
    "go_data": ("📂 Open the data page", "📂 فتح صفحة المعطيات"),
    "wz_pending": ("The setup wizard is not finished yet – complete it on the Data page first.",
                   "لم يكتمل معالج الإعداد بعد – أكمله أولًا في صفحة المعطيات."),
    "up_added": ("Loaded: {x}", "تم تحميل: {x}"),
    "up_cached": ("Files in use:", "الملفات المعتمدة:"),
    "up_clear": ("🗑 Clear files", "🗑 إفراغ الملفات"),
    "dlg_solved_title": ("Timetable generated", "تم توليد التوزيع الزمني"),
    "dlg_solved_hint": ("The new version is open below. Drag lessons on the Manual editing page, then export from Versions & export.",
                        "النسخة الجديدة معروضة أدناه. يمكنك سحب الحصص في صفحة التعديل اليدوي، ثم التصدير من صفحة النسخ والتصدير."),
    "dlg_view": ("📅 View timetables", "📅 عرض الجداول"),
    "dlg_edit": ("✋ Edit", "✋ تعديل"),
    "dlg_details": ("📊 Details", "📊 التفاصيل"),
    # general / sidebar
    "page_title": ("Timetable Preparation System – Beta", "نظام إعداد الجداول الزمنية – نسخة تجريبية"),
    "app_title": ("Timetable Preparation System", "نظام إعداد الجداول الزمنية"),
    "beta_badge": ("Evaluation version (beta)", "نسخة تجريبية"),
    "app_subtitle": ("Build the teacher assignment and the school timetable, check them, edit by drag and drop, export.",
                     "إعداد الإسناد والتوزيع الزمني، مراقبتهما، تعديلهما بالسحب والإفلات، ثم التصدير."),
    "beta_footer": ("🧪 Evaluation version (beta) – please report any problem to the administrator.",
                    "🧪 نسخة تجريبية – يرجى إبلاغ المسؤول بأي مشكلة."),
    "upload_help": ("A zip downloaded from the setup wizard can be uploaded as is (the assignment inside is imported too). "
                    "Column names and values may be in English or Arabic (download a template below). "
                    "The curriculum is optional: the approved curriculum is used by default.",
                    "يمكن رفع ملف zip المنزَّل من معالج الإعداد كما هو (يُستورد الإسناد الذي بداخله أيضًا). "
                    "أسماء الأعمدة والقيم بالعربية أو الإنجليزية (نزّل نموذجًا أدناه). "
                    "المنهاج اختياري: يُستعمل المنهاج المعتمد افتراضيًا."),
    "tpl_csv": ("⬇️ Template CSV", "⬇️ نموذج CSV"), "tpl_xlsx": ("⬇️ Template Excel", "⬇️ نموذج Excel"),
    "tpl_name": ("templates", "نماذج"),
    "language": ("🌐 Language / اللغة", "🌐 اللغة / Language"),
    "data": ("📂 Data", "📂 المعطيات"),
    "source": ("Source", "المصدر"),
    "src_upload": ("📂 Upload from computer", "📂 تحميل من الحاسوب"),
    "lab_fallback": ("Labs may use free classrooms", "المخابر يمكن تعويضها بقاعات شاغرة"),
    "lab_fallback_help": ("When no lab is free, practical work (TP) groups use a classroom left free by a class at sport, IT…",
                          "إذا لم يتوفر مخبر، تستعمل أفواج الأعمال التطبيقية قاعة تركها فوج في الملعب أو الإعلام الآلي…"),
    "o_wizard": ("setup guide", "دليل الإعداد"),
    "src_sample": ("🧪 Sample data", "🧪 معطيات تجريبية"),
    "upload_csvs": ("Select your files: one zip with all the files, or the CSV / Excel files (multi-select)",
                    "اختر ملفاتك: ملف zip واحد يضم كل الملفات، أو ملفات CSV / Excel (اختيار متعدد)"),
    "unreadable": ("❌ unreadable: {e}", "❌ غير مقروء: {e}"),
    "not_recognised": ("⚠️ not recognised", "⚠️ غير معروف"),
    "grid_upload_title": ("**📑 Assignment grid (optional)**", "**📑 جدول توزيع الحصص (اختياري)**"),
    "grid_upload": ("Import school assignment grid (.xlsx / .csv)", "استيراد جدول توزيع الحصص (‎.xlsx / .csv)"),
    "grid_upload_help": ("Rows = classes (4م1 …), columns = posts (عربية1, رياضيات2 …), cells = hours. "
                         "Or generate one on the 👥 Assignment page.",
                         "الأسطر = الأفواج (4م1 …)، الأعمدة = المناصب (عربية1، رياضيات2 …)، الخانات = الساعات. "
                         "أو أنشئه في صفحة الإسناد."),
    "need_curriculum": ("Upload the curriculum file too, so posts can be mapped to subjects.",
                        "حمّل ملف المنهاج أيضًا لربط المناصب بالمواد."),
    "grid_read_error": ("❌ Could not read grid: {e}", "❌ تعذّرت قراءة الجدول: {e}"),
    "using_plan": ("Using assignment: {p} posts · {c} classes ({o})", "الإسناد المعتمد: {p} منصب · {c} فوج ({o})"),
    "still_needed": ("Still needed: {x}", "ما زال مطلوبًا: {x}"),
    "or_build_plan": (" (or build an assignment on the 👥 Assignment page)", " (أو أنشئ إسنادًا في صفحة 👥 الإسناد)"),
    "config": ("⚙️ Configuration", "⚙️ الإعدادات"),
    "hard": ("Hard constraints", "القيود الصارمة"),
    "allow_gaps": ("Allow student gaps", "السماح بفراغات التلاميذ"),
    "allow_twice": ("Allow same subject twice per day", "السماح بنفس المادة مرتين في اليوم"),
    "enforce_2h": ("Enforce max 2h courses per day", "تحديد أقصى عدد لحصص الساعتين يوميًا"),
    "max_2h": ("Max 2h courses per day", "أقصى عدد لحصص الساعتين يوميًا"),
    "morning_first": ("🌅 Morning first (afternoon only if morning is full)",
                      "🌅 الأولوية للصباح (المساء فقط إذا امتلأ الصباح)"),
    "morning_first_help": ("Hard rule per class & day: an afternoon lesson is allowed only when all morning slots are used.",
                           "قاعدة صارمة لكل فوج ويوم: لا يُسمح بحصة مسائية إلا إذا استُعملت كل حصص الصباح."),
    "soft": ("Soft constraint weights", "أوزان القيود المرنة"),
    "solver": ("Solver", "المُحلّل"),
    "max_time": ("Max solve time (s)", "أقصى زمن للحل (ثا)"),
    "workers": ("Workers", "عدد مسارات المعالجة"),
    "save_as": ("Save as version", "حفظ كنسخة"),
    "solve": ("🚀 Solve", "🚀 حلّ"),
    # weights
    "w_empty_morning_slot_penalty": ("Empty morning slot penalty", "عقوبة الحصة الصباحية الفارغة"),
    "w_teacher_afternoon_penalty": ("Teacher afternoon penalty", "عقوبة ساعات المساء للأستاذ"),
    "w_teacher_single_hour_weight": ("Teacher single-hour shift weight", "وزن فترة الساعة الواحدة للأستاذ"),
    "w_teacher_single_gap_weight": ("Teacher 1h gap weight", "وزن فراغ الساعة للأستاذ"),
    "w_teacher_double_gap_weight": ("Teacher 2h gap weight", "وزن فراغ الساعتين للأستاذ"),
    "w_teacher_working_day_weight": ("Teacher working day weight", "وزن يوم العمل للأستاذ"),
    "w_reception_in_gap_reward": ("Reception-in-gap reward", "مكافأة الاستقبال في الفراغ"),
    "w_slot_1_penalty": ("Slot 1 penalty", "عقوبة الحصة 1"),
    "w_slot_4_penalty": ("Slot 4 penalty", "عقوبة الحصة 4"),
    "w_slot_5_penalty": ("Slot 5 penalty", "عقوبة الحصة 5"),
    "w_slot_7_penalty": ("Slot 7 (late) penalty", "عقوبة الحصة 7 (متأخرة)"),
    "w_slot_7_equity_penalty": ("Slot 7 equity penalty", "عقوبة عدم الإنصاف في الحصة 7"),
    # tabs
    "tab_plan": ("1️⃣ Assignment", "1️⃣ الإسناد"),
    "tab_run": ("2️⃣ Timetable (Run)", "2️⃣ التوزيع الزمني (توليد)"),
    "tab_data": ("📋 Input data", "📋 المعطيات المُدخلة"),
    "tab_tt": ("📅 Timetables", "📅 الجداول"),
    "tab_edit": ("✋ Edit (drag & drop)", "✋ تعديل (سحب وإفلات)"),
    "tab_cmp": ("📊 Compare versions", "📊 مقارنة النسخ"),
    # data tab
    "rows": ("{k} — {n} rows", "{k} — {n} سطر"),
    "ds_teachers": ("Staff", "الأساتذة"), "ds_classes": ("Classes", "الأفواج"), "ds_subjects": ("Curriculum", "المنهاج"),
    "ds_inspections": ("Pedagogical windows", "النوافذ البيداغوجية"), "ds_rooms": ("Rooms", "القاعات"),
    "ds_rules": ("Split rules", "قواعد التفويج"), "ds_grid": ("School grid", "الشبكة الزمنية"),
    "raw_note": ("Column names are the file format and stay in English.", "أسماء الأعمدة هي صيغة الملف وتبقى بالإنجليزية."),
    # run tab
    "building": ("Building model (teacher assignment + lessons)…", "بناء النموذج (إسناد الأساتذة + الحصص)…"),
    "solving": ("Solving (up to {s}s)…", "جارٍ الحل (حتى {s} ثا)…"),
    "need_files": ("📂 Upload your CSV files on the 📂 Data page: staff, classes, curriculum, pedagogical_windows, rooms, "
                   "split_rules (school_grid is optional). If you build or import an assignment (👥 Assignment page), staff and "
                   "classes are not needed. Files are recognised by their columns.",
                   "📂 حمّل ملفات CSV في صفحة 📂 المعطيات: الأساتذة، الأفواج، المنهاج، النوافذ البيداغوجية، القاعات، "
                   "قواعد التفويج (الشبكة الزمنية اختيارية). إذا أنشأت أو استوردت إسنادًا (صفحة 👥 الإسناد) فلا حاجة لملفي "
                   "الأساتذة والأفواج. يتم التعرف على الملفات من أعمدتها."),
    "data_loaded": ("Data loaded ✅. Check the settings below, then click **Solve**.",
                    "تم تحميل المعطيات ✅. راجع الإعدادات أدناه ثم اضغط **حلّ**."),
    "status": ("Status", "الحالة"),
    "proven_infeasible": ("The solver PROVED no timetable exists with these data (not a timeout).",
                          "أثبت المحلّل أنه لا يوجد أي جدول ممكن بهذه المعطيات (ليس انتهاء وقت)."),
    "diag_btn": ("🔍 Diagnose pedagogical windows", "🔍 تشخيص النوافذ البيداغوجية"),
    "diag_day": ("Day", "اليوم"),
    "diag_result": ("Result (window alone)", "النتيجة (النافذة وحدها)"),
    "diag_bad": ("❌ Impossible by itself", "❌ مستحيلة وحدها"),
    "diag_ok": ("✅ OK", "✅ سليمة"),
    "diag_unknown": ("⏳ Not decided in 20 s", "⏳ لم يُحسم في 20 ثا"),
    "diag_ignored": ("⚠️ Subject not in curriculum – ignored", "⚠️ المادة غير موجودة في المنهاج – مُهملة"),
    "diag_caption": ("Each window is tested alone. If none is impossible alone, the problem is a combination of windows.",
                     "تُختبر كل نافذة وحدها. إن لم تكن أي نافذة مستحيلة وحدها فالمشكلة في اجتماع عدة نوافذ."),
    "feasible": ("✅ Feasible", "✅ ممكن"),
    "infeasible": ("❌ Infeasible / timeout", "❌ غير ممكن / انتهى الوقت"),
    "objective": ("Objective score", "قيمة دالة الهدف"),
    "lessons_gen": ("Lessons generated", "الحصص المُنشأة"),
    "times": ("Build / solve time", "زمن البناء / الحل"),
    "no_solution": ("No solution found. Try relaxing hard constraints or increasing solve time.",
                    "لم يُعثر على حل. جرّب تخفيف القيود الصارمة أو زيادة زمن الحل."),
    "saved_as": ("Saved as **{n}**", "حُفظ باسم **{n}**"),
    "kpis": ("KPIs", "مؤشرات الأداء"),
    "kpi": ("KPI", "المؤشر"), "value": ("Value", "القيمة"),
    "teacher_assignment": ("Teacher assignment", "إسناد الأساتذة"),
    "dl_school": ("📑 Download assignment in school format (.xlsx)", "📑 تنزيل جدول توزيع الحصص (‎.xlsx)"),
    "gen_lessons": ("Generated lessons", "الحصص المُنشأة"),
    "raw_schedule": ("Raw schedule", "الجدول الخام"),
    "dl_csv": ("Download CSV", "تنزيل CSV"),
    # timetables tab
    "no_versions": ("No saved versions yet.", "لا توجد نسخ محفوظة بعد."),
    "version": ("Version", "النسخة"),
    "view_by": ("View by", "العرض حسب"),
    "class": ("Class", "الفوج"), "teacher": ("Teacher", "الأستاذ"),
    # compare
    "versions_cmp": ("Versions to compare", "النسخ للمقارنة"),
    "lower_better": ("Lower is better for every KPI except working days (context-dependent).",
                     "الأقل أفضل لكل المؤشرات باستثناء أيام العمل (حسب السياق)."),
    "delete_all": ("🗑️ Delete all saved versions", "🗑️ حذف كل النسخ المحفوظة"),
    # editor tab
    "solve_first": ("Solve a timetable first – solved versions become editable here.",
                    "احسب توزيعًا زمنيًا أولًا – تصبح النسخ المحلولة قابلة للتعديل هنا."),
    "version_edit": ("Version to edit", "النسخة المراد تعديلها"),
    "edit_by": ("Edit by", "التعديل حسب"),
    "move_rejected": ("Move rejected: {m}", "رُفض النقل: {m}"),
    "undo": ("↩️ Undo", "↩️ تراجع"),
    "reset": ("🔄 Reset to solver result", "🔄 العودة إلى نتيجة المُحلّل"),
    "save_new": ("💾 Save as new version", "💾 حفظ كنسخة جديدة"),
    "saved_new": ("Saved **{n}** – see it in Timetables / Compare.", "حُفظت **{n}** – اطّلع عليها في الجداول / المقارنة."),
    "live_kpis": ("**Live KPIs (solver result → edited)**", "**المؤشرات الحية (نتيجة المُحلّل ← بعد التعديل)**"),
    "solver_col": ("Solver", "المُحلّل"), "edited_col": ("Edited", "بعد التعديل"),
    "change_log": ("**Change log**", "**سجل التغييرات**"),
    "no_changes": ("no changes yet", "لا توجد تغييرات بعد"),
    "log_move": ("{s} ({c}) → {d} slot {sl}: {m}", "{s} ({c}) ← {d} الحصة {sl}: {m}"),
    "log_undo": ("undo", "تراجع"), "log_reset": ("reset", "إعادة ضبط"),
    "no_double": ("✅ No double bookings", "✅ لا يوجد تداخل في الحجز"),
    "tooltip": ("{s} | {c} | {t} | {d}h | rooms: {r}", "{s} | {c} | {t} | {d} سا | القاعات: {r}"),
    # dnd component
    "dnd_free": ("free – move directly", "حرّ – نقل مباشر"),
    "dnd_swap": ("possible via swap (affects other teacher/class)", "ممكن بالتبديل (يمسّ أستاذًا/فوجًا آخر)"),
    "dnd_impossible": ("impossible", "مستحيل"),
    "dnd_current": ("current", "الموضع الحالي"),
    "dnd_win": ("pedagogical window", "نافذة بيداغوجية"),
    "dnd_win_msg": ("pedagogical window of this teacher – no lesson can be placed here.",
                    "نافذة بيداغوجية لهذا الأستاذ – لا يمكن وضع أي حصة هنا."),
    "dnd_tgt_head": ("{n} lesson(s) can move here – click one (🟢 free move, 🟡 swap):",
                     "{n} حصة يمكن نقلها إلى هنا – اضغط على إحداها (🟢 نقل حر، 🟡 تبديل):"),
    "dnd_tgt_none": ("no lesson of this view can move here.", "لا توجد حصة في هذا العرض يمكن نقلها إلى هنا."),
    "dnd_hint": ("Drag a lesson (or click it, then click a target) to see where it can go. Click an empty slot to see which lessons can fill it.",
                 "اسحب حصة (أو انقر عليها ثم على الخانة الهدف) لرؤية الأماكن الممكنة. انقر على خانة فارغة لرؤية الحصص التي يمكن وضعها فيها."),
    "dnd_moving": ("Moving <b>{t}</b> ({d}h) – {s}. Drop on green/yellow.",
                   "نقل <b>{t}</b> ({d} سا) – {s}. أفلِت على الأخضر/الأصفر."),
    "dnd_not_allowed": ("❌ Not allowed: {m}", "❌ غير مسموح: {m}"),
    "dnd_applying": ("Applying move…", "جارٍ تطبيق النقل…"),
    "dnd_lunch": ("lunch break", "استراحة الغداء"),
    "st_green": ("GREEN", "أخضر"), "st_yellow": ("YELLOW", "أصفر"), "st_red": ("RED", "أحمر"), "st_current": ("CURRENT", "حالي"),
    # editor messages
    "e_cannot_start": ("{s} cannot start at this slot (blocked / lunch / end of day)",
                       "لا يمكن أن تبدأ {s} في هذه الحصة (محجوبة / غداء / نهاية اليوم)"),
    "e_class_busy": ("class {c} busy", "الفوج {c} مشغول"),
    "e_teacher_busy": ("teacher {t} busy", "الأستاذ {t} مشغول"),
    "e_overlap": ("moved lessons overlap", "الحصص المنقولة متداخلة"),
    "e_room": ("no free '{r}' room ({n}/{cap})", "لا توجد قاعة '{r}' شاغرة ({n}/{cap})"),
    "e_already": ("{b} already taught to {c} that day", "{b} مُدرّسة للفوج {c} في هذا اليوم"),
    "e_no2h": (" ({b} has no 2h blocks)", " ({b} ليس لها حصص بساعتين)"),
    "e_exceed2h": (" (would exceed 2h of {b})", " (سيتجاوز ساعتين من {b})"),
    "e_already2h": (" (already a 2h {b} block that day)", " (توجد حصة ساعتين من {b} في هذا اليوم)"),
    "e_split2h": (" (split lessons can't form a 2h block)", " (الحصص المفوّجة لا تشكل حصة ساعتين)"),
    "e_diffteach": (" (different {b} teachers)", " (أساتذة {b} مختلفون)"),
    "e_lunch2h": (" (a 2h block can't span the lunch break)", " (لا يمكن أن تمتد حصة الساعتين عبر استراحة الغداء)"),
    "e_place_adj": (" – place it right before/after the other {b} hour to make a 2h block",
                    " – ضعها مباشرة قبل/بعد ساعة {b} الأخرى لتكوين حصة ساعتين"),
    "e_max2h": ("max {n} two-hour course(s)/day for {c}", "الحد الأقصى {n} حصة بساعتين يوميًا للفوج {c}"),
    "e_morning": ("morning-first: {c} would have an afternoon lesson without a full morning",
                  "الأولوية للصباح: سيكون للفوج {c} حصة مسائية دون صباح كامل"),
    "e_gap": ("creates a student gap for {c}", "يُحدث فراغًا لتلاميذ الفوج {c}"),
    "e_current": ("current position", "الموضع الحالي"),
    "e_locked": ("linked (consecutive) lesson – locked", "حصة مرتبطة (متتالية) – مقفلة"),
    "e_blocked": ("blocked slot (Tuesday pm / lunch / inspection / end of day)",
                  "حصة محجوبة (مساء الثلاثاء / غداء / تفتيش / نهاية اليوم)"),
    "e_free": ("free", "حرّ"),
    "e_forms2h": (" – forms a 2h {b} block", " – يُكوّن حصة ساعتين من {b}"),
    "e_conf_locked": ("conflicts with locked lesson {d}", "يتعارض مع حصة مقفلة {d}"),
    "e_noop": ("swap with {d} changes nothing (same class & same teacher)",
               "التبديل مع {d} لا يغيّر شيئًا (نفس الفوج ونفس الأستاذ)"),
    "e_diffdur": ("conflicts with {d} (different duration, no swap)", "يتعارض مع {d} (مدة مختلفة، لا تبديل)"),
    "e_swap_imp": ("swap with {d} impossible: {e}", "التبديل مع {d} مستحيل: {e}"),
    "e_swap": ("swap with {d}", "تبديل مع {d}"),
    "e_affects": (" → affects {w}", " ← يمسّ {w}"),
    "e_w_teacher": ("teacher {x}", "الأستاذ {x}"),
    "e_w_class": ("class {x}", "الفوج {x}"),
    "e_and": (" & ", " و "),
    "e_conf_n": ("conflicts with {n} lessons", "يتعارض مع {n} حصص"),
    "e_double": ("double booking {k}", "حجز مزدوج {k}"),
    "sep": ("; ", "؛ "),
    # assignment step
    "plan_title": ("### 1️⃣ Teacher assignment – جدول توزيع الحصص", "### 1️⃣ إسناد الأساتذة – جدول توزيع الحصص"),
    "plan_caption": ("Build the assignment first (generate, import or edit), check it, download it in the school format, "
                     "then use it for the timetable in step 2.",
                     "أنشئ الإسناد أولًا (توليد أو استيراد أو تعديل)، راجعه، نزّله بصيغة المؤسسة، ثم استعمله لإعداد "
                     "التوزيع الزمني في الخطوة 2."),
    "gen_expander": ("⚙️ Generate an assignment", "⚙️ توليد إسناد"),
    "need_classes_curr": ("Load at least classes and curriculum (📂 Data page) to generate an assignment.",
                          "حمّل على الأقل الأفواج والمنهاج (صفحة 📂 المعطيات) لتوليد إسناد."),
    "method": ("Method", "الطريقة"),
    "m_auto": ("Auto-create posts (no staff file needed)", "إنشاء المناصب تلقائيًا (دون ملف الأساتذة)"),
    "m_staff": ("From staff file (qualified subjects & max hours)", "من ملف الأساتذة (المواد والحجم الأقصى)"),
    "max_per_post": ("Max hours per post", "الحجم الساعي الأقصى للمنصب"),
    "per_subject": ("Per-subject settings (edit if needed)", "إعدادات كل مادة (عدّل عند الحاجة)"),
    "c_subject": ("Subject", "المادة"), "c_arabic": ("Arabic name", "الاسم بالعربية"),
    "c_max": ("Max hours", "الحجم الأقصى"), "c_remedial": ("Remedial (استدراك)", "الاستدراك"),
    "generate": ("⚙️ Generate assignment", "⚙️ توليد الإسناد"),
    "generating": ("Computing posts and distributing classes…", "حساب المناصب وتوزيع الأفواج…"),
    "need_staff": ("Upload staff.csv to use this method.", "حمّل ملف الأساتذة staff.csv لاستعمال هذه الطريقة."),
    "gen_staff": ("⚙️ Generate from staff", "⚙️ توليد من ملف الأساتذة"),
    "assigning": ("Assigning teachers…", "جارٍ إسناد الأساتذة…"),
    "o_auto": ("auto-generated posts", "مناصب مولّدة تلقائيًا"),
    "o_staff": ("generated from staff", "مولّد من ملف الأساتذة"),
    "o_import": ("imported from {f}", "مستورد من {f}"),
    "no_plan": ("No assignment yet – generate one above or import a school grid on the 📂 Data page.",
                "لا يوجد إسناد بعد – ولّد واحدًا أعلاه أو استورد جدول الإسناد من صفحة 📂 المعطيات."),
    "current_plan": ("**Current assignment** – {o}: {p} posts · {c} classes · {h} hours",
                     "**الإسناد الحالي** – {o}: {p} منصب · {c} فوج · {h} ساعة"),
    "use_plan": ("Use this assignment for the timetable (step 2)", "اعتماد هذا الإسناد لإعداد التوزيع الزمني"),
    "over_cap": ("⛔ {n} class(es) need more than the {s} weekly slots of the grid ({d} days × {k} slots, Tuesday "
                 "afternoon off) – timetable will be infeasible: {lst}",
                 "⛔ {n} فوج يحتاج أكثر من {s} حصة أسبوعية متاحة ({d} أيام × {k} حصص، مساء الثلاثاء عطلة) – "
                 "سيكون التوزيع الزمني غير ممكن: {lst}"),
    "diff_hours": ("⚠️ {n} class/subject hours differ from the curriculum (timetable uses curriculum hours)",
                   "⚠️ {n} ساعات فوج/مادة تختلف عن المنهاج (التوزيع الزمني يعتمد ساعات المنهاج)"),
    "slots_title": ("🧮 Weekly load per class – teacher hours vs real class slots (max {s})",
                    "🧮 الحجم الأسبوعي لكل فوج – ساعات الأساتذة مقابل الحصص الفعلية للفوج (الأقصى {s})"),
    "slots_caption": ("Split sessions (تفويج, from split_rules) put two teachers with the two halves of the class in the "
                      "same slot, so they count for each teacher but only once for the class.",
                      "حصص التفويج (من ملف قواعد التفويج) تجمع أستاذين مع نصفي الفوج في نفس الحصة، فتُحسب لكل أستاذ "
                      "لكنها تُحسب مرة واحدة فقط للفوج."),
    "sl_teacher": ("Teacher hours (sum)", "مجموع ساعات الأساتذة"),
    "sl_overlap": ("Split overlap", "تداخل التفويج"),
    "sl_slots": ("Class slots needed", "الحصص الفعلية للفوج"),
    "sl_declared": ("Declared (حجم ساعي)", "الحجم الساعي المصرّح"),
    "sl_free": ("Free slots", "حصص شاغرة"),
    "plan_ok": ("Hours match the curriculum and every class fits in the weekly grid ✅",
                "الساعات مطابقة للمنهاج وكل فوج يتسع في الشبكة الأسبوعية ✅"),
    "crosscheck_na": ("(curriculum cross-check unavailable: {e})", "(تعذّرت المقارنة مع المنهاج: {e})"),
    "posts_title": ("#### 👩‍🏫 Posts (المناصب) – loads & teacher names", "#### 👩‍🏫 المناصب – الحجم الساعي وأسماء الأساتذة"),
    "apply_names": ("💾 Apply teacher names", "💾 تطبيق أسماء الأساتذة"),
    "reassign_title": ("#### 🔀 Reassign – choose the post for each class & subject",
                       "#### 🔀 إعادة الإسناد – اختر المنصب لكل فوج ومادة"),
    "n_changes": ("{n} change(s): {x}", "{n} تغيير: {x}"),
    "apply_reassign": ("✅ Apply reassignment", "✅ تطبيق إعادة الإسناد"),
    "school_format": ("#### 📑 School format (جدول توزيع الحصص)", "#### 📑 صيغة المؤسسة (جدول توزيع الحصص)"),
    "weekly_hours": ("Weekly hours", "حجم ساعي"),
    "total_no_rem": ("Total (without remedial)", "المجموع (دون استدراك)"),
    "dl_plan": ("📥 Download assignment (.xlsx, school format)", "📥 تنزيل الإسناد (‎.xlsx، صيغة المؤسسة)"),
    # load table columns
    "lt_Post": ("Post", "المنصب"), "lt_Teacher": ("Teacher ID", "معرّف الأستاذ"),
    "lt_Name": ("Name (اللقب و الاسم)", "اللقب و الاسم"), "lt_Subject": ("Subject", "المادة"),
    "lt_Hours": ("Hours", "الساعات"), "lt_Remedial": ("Remedial", "الاستدراك"), "lt_Total": ("Total", "المجموع"),
    "lt_Max": ("Max", "الأقصى"), "lt_Status": ("Status", "الحالة"), "lt_Levels": ("Levels", "المستويات"),
    "lt_Classes": ("Classes", "الأفواج"),
    "over_max": ("⛔ over max", "⛔ فوق الأقصى"),
    # diff table
    "d_Class": ("Class", "الفوج"), "d_Subject": ("Subject", "المادة"), "d_Teacher": ("Teacher", "الأستاذ"),
    "d_Matrix hours": ("Matrix hours", "ساعات الجدول"), "d_Curriculum hours": ("Curriculum hours", "ساعات المنهاج"),
    # import / planner warnings
    "w_map_conflict": ("After grouping, class {c} has {s} with several teachers ({x}) – only the first is kept",
                       "بعد التجميع، الفوج {c} له مادة {s} مع عدة أساتذة ({x}) – يُحتفظ بالأول فقط"),
    "e_grid": ("breaks the standard grid of {c} (5 full mornings + 2 first afternoon slots on 4 days, 7th slot only for extra hours, never Thursday)",
               "يكسر الشبكة المعيارية للفوج {c} (5 صباحات كاملة + أول حصتين مساءً في 4 أيام، الحصة 7 للساعات الإضافية فقط)"),
    "max_time_help": ("With the standard grid the solver works in 2 phases: first a timetable that respects the grid, then "
                      "teacher comfort. 5–15 minutes recommended (faster on a computer with more CPU cores).",
                      "مع الشبكة المعيارية يعمل المحلّل على مرحلتين: أولًا جدول يحترم الشبكة، ثم راحة الأساتذة. "
                      "يُنصح بـ 5–15 دقيقة (أسرع على حاسوب بأنوية معالجة أكثر)."),
    "phase_caption": ("Phase 1 – timetable respecting the grid: {s1} in {t1}s · Phase 2 – teacher comfort: {s2} in {t2}s",
                      "المرحلة 1 – جدول يحترم الشبكة: {s1} في {t1} ثا · المرحلة 2 – راحة الأساتذة: {s2} في {t2} ثا"),
    "use_remedial": ("📚 Schedule remediation hours (الاستدراك)", "📚 برمجة ساعات الاستدراك"),
    "use_remedial_help": ("Placed AFTER the timetable is finished: each teacher gets ONE remediation session for ALL his classes "
                          "(he divides his students himself), at an hour free for him and all those classes – slot 6 first "
                          "(no extra hour), otherwise slot 7. Teachers of a group (e.g. ARABIC+MATH) share one session free for "
                          "both teachers and all their classes.",
                          "يُبرمج بعد انتهاء الجدول: لكل أستاذ حصة استدراك واحدة لكل أفواجه (وهو من يقسّم تلاميذه)، في ساعة "
                          "شاغرة له ولكل هذه الأفواج – الحصة السادسة أولا (دون ساعة إضافية)، وإلا الحصة السابعة. أساتذة المجموعة "
                          "(مثل ARABIC+MATH) يتقاسمون حصة واحدة شاغرة للأستاذين ولكل أفواجهما."),
    "src_manual": ("✏️ Create / edit in the app", "✏️ إنشاء / تعديل داخل التطبيق"),
    "src_manual_info": ("Data is being created in the page (✏️ data builder at the top).",
                        "البيانات تُنشأ في الصفحة (✏️ منشئ البيانات في الأعلى)."),
    "db_title": ("✏️ Data builder – create your school data without files", "✏️ منشئ البيانات – أنشئ بيانات مؤسستك دون ملفات"),
    "db_caption": ("Start from an empty template, the sample, or your uploaded files, then edit the tables (add rows with ➕ "
                   "at the bottom). Teachers can also be created in step 1 (assignment).",
                   "ابدأ من قالب فارغ أو من المثال أو من ملفاتك المرفوعة، ثم عدّل الجداول (أضف أسطرًا بـ ➕ في الأسفل). "
                   "يمكن أيضًا إنشاء الأساتذة في الخطوة 1 (الإسناد)."),
    "db_from_empty": ("🆕 Empty template", "🆕 قالب فارغ"), "db_from_sample": ("📦 Start from the sample", "📦 البدء من المثال"),
    "db_from_upload": ("📤 Start from my uploaded files", "📤 البدء من ملفاتي المرفوعة"),
    "db_gen_classes": ("Generate classes", "توليد الأفواج"),
    "db_gen_curr": ("➕ Add every subject for every level", "➕ إضافة كل المواد لكل المستويات"),
    "db_gen_curr_help": ("Adds missing (level, subject) rows with 0 hours – then fill in the hours.",
                         "يضيف الأسطر الناقصة (مستوى، مادة) بحجم 0 – ثم املأ الساعات."),
    "db_slots_help": ("Blocked slots separated by ';' – 0-3 morning, 4-6 afternoon (e.g. 0;1;2;3)",
                      "الحصص الممنوعة مفصولة بـ ';' – 0-3 صباحًا، 4-6 مساءً (مثال 0;1;2;3)"),
    "db_qual_help": ("Subjects separated by ';' (e.g. ARABIC;ISLAMIC)", "المواد مفصولة بـ ';' (مثال ARABIC;ISLAMIC)"),
    "db_help_classes": ("One row per class (فوج). Type the number of classes per level and click Generate, or edit rows.",
                        "سطر لكل فوج. اكتب عدد الأفواج لكل مستوى ثم اضغط توليد، أو عدّل الأسطر."),
    "db_help_subjects": ("Weekly hours per level and subject: course, TD, TP, practice + room type.",
                         "الحجم الساعي الأسبوعي لكل مستوى ومادة: درس، أعمال موجهة، أعمال تطبيقية، تطبيق + نوع القاعة."),
    "db_help_rooms": ("How many rooms of each type exist.", "عدد القاعات من كل نوع."),
    "db_help_inspections": ("Pedagogical windows: subject, day (0=Sunday … 4=Thursday) and blocked slots. Optional.",
                            "النوافذ البيداغوجية: المادة، اليوم (0=الأحد … 4=الخميس) والحصص الممنوعة. اختياري."),
    "db_help_rules": ("Split (فوج) rules – optional. Primary/secondary subject, TD or TP, hours, Frequency 1 = every week, 2 = alternate weeks.",
                      "قواعد التفويج – اختياري. المادة الأساسية/الثانوية، TD أو TP، الساعات، التكرار 1 = كل أسبوع، 2 = أسبوع بعد أسبوع."),
    "db_help_teachers": ("Teachers (optional here: you can also build the assignment in step 1 or upload اسناد.csv).",
                         "الأساتذة (اختياري هنا: يمكن أيضًا بناء الإسناد في الخطوة 1 أو رفع ملف الإسناد)."),
    "db_rows": ("{n} valid rows", "{n} سطر صالح"),
    "db_level_hours": ("Weekly hours per level:", "الحجم الساعي الأسبوعي لكل مستوى:"),
    "db_missing": ("Still needed: {x}", "ما زال مطلوبًا: {x}"),
    "db_ready": ("✅ Data ready – you can go to step 1 / step 2.", "✅ البيانات جاهزة – يمكنك الانتقال إلى الخطوة 1 / الخطوة 2."),
    "db_download": ("⬇️ Download the data (zip of CSV files)", "⬇️ تنزيل البيانات (ملف zip من ملفات CSV)"),
    "db_download_help": ("Keep a copy – you can upload these files next time.", "احتفظ بنسخة – يمكنك رفع هذه الملفات لاحقًا."),
    "rem_groups": ("Remediation groups (one shared session)", "تجميع الاستدراك (حصة مشتركة)"),
    "rem_groups_help": ("Subjects whose remediation is ONE shared session – students split into groups at the same hour. "
                        "Join subjects with '+', separate groups with ';' (e.g. ARABIC+MATH; FRENCH+ENGLISH). "
                        "Sessions of different groups are kept at different hours for the same class.",
                        "المواد التي يكون استدراكها حصة واحدة مشتركة – يُقسَّم التلاميذ إلى أفواج في نفس الساعة. "
                        "اربط المواد بـ '+' وافصل المجموعات بـ ';' (مثال ARABIC+MATH; FRENCH+ENGLISH). "
                        "حصص المجموعات المختلفة تُبرمج في ساعات مختلفة لنفس الفوج."),
    "export_title": ("⬇️ Export (PDF / Excel)", "⬇️ تصدير (PDF / Excel)"),
    "export_sections": ("Include", "المحتوى"),
    "exp_full_class": ("Full table – all classes", "الجدول الشامل – كل الأفواج"),
    "exp_full_teacher": ("Full table – all teachers", "الجدول الشامل – كل الأساتذة"),
    "exp_class": ("One timetable per class", "جدول لكل فوج"), "exp_teacher": ("One timetable per teacher", "جدول لكل أستاذ"),
    "export_xlsx": ("📊 Download Excel (.xlsx)", "📊 تنزيل Excel (.xlsx)"),
    "export_pdf": ("📄 Download PDF", "📄 تنزيل PDF"),
    "advanced": ("⚙️ Advanced settings (constraints & weights)", "⚙️ إعدادات متقدمة (القيود والأوزان)"),
    "adv_caption": ("Defaults are tuned for Algerian middle schools – change only if needed.",
                    "القيم الافتراضية مضبوطة للمتوسطات – غيّرها عند الحاجة فقط."),
    "adv_password": ("Password", "كلمة السر"), "adv_wrong": ("Wrong password", "كلمة سر خاطئة"),
    "workspace": ("🏫 School name (workspace)", "🏫 اسم المؤسسة (مساحة العمل)"),
    "workspace_help": ("The school name is also the workspace: versions and wizard projects are stored separately per "
                       "school, and it appears on the exported timetables (PDF / Excel).",
                       "اسم المؤسسة هو أيضًا مساحة العمل: تُحفظ النسخ ومشاريع المساعد منفصلة لكل مؤسسة، ويظهر في "
                       "الجداول المصدَّرة (PDF / Excel)."),
    "db_local": ("💾 Local SQLite database (data/app.db) – on Streamlit Cloud it is erased at each restart; configure an external MySQL in secrets to keep data.",
                 "💾 قاعدة بيانات محلية SQLite – على Streamlit Cloud تُمحى عند كل إعادة تشغيل؛ اضبط MySQL خارجية في الأسرار للاحتفاظ بالبيانات."),
    "manage_versions": ("🗃 Manage versions", "🗃 إدارة النسخ"),
    "new_name": ("New name", "الاسم الجديد"),
    "rename": ("✏️ Rename", "✏️ إعادة التسمية"),
    "rename_bad": ("Name empty or already used.", "الاسم فارغ أو مستعمل."),
    "delete": ("🗑 Delete", "🗑 حذف"),
    "delete_confirm": ("Confirm deleting {v}", "تأكيد حذف {v}"),
    "delete_all_confirm": ("Confirm deleting ALL {n} versions", "تأكيد حذف كل النسخ ({n})"),
    "pw_change": ("🔑 Change password", "🔑 تغيير كلمة السر"),
    "pw_new": ("New password", "كلمة السر الجديدة"),
    "pw_again": ("Repeat password", "أعد كتابة كلمة السر"),
    "pw_save": ("Save", "حفظ"),
    "pw_short": ("At least 6 characters.", "6 أحرف على الأقل."),
    "pw_mismatch": ("The two passwords differ.", "كلمتا السر مختلفتان."),
    "pw_saved": ("Password saved in the database.", "حُفظت كلمة السر في قاعدة البيانات."),
    "countdown": ("⏳ {p} – about {m}:{s} left ({c} CPU)", "⏳ {p} – بقي حوالي {m}:{s} ({c} معالج)"),
    "phase1_name": ("Phase 1: placing all lessons", "المرحلة 1: وضع كل الحصص"),
    "phase2_name": ("Phase 2: improving quality", "المرحلة 2: تحسين الجودة"),
    "cpu_hint": ("ℹ️ This server has {n} CPU(s). With 4 or more CPUs the solver finds better timetables in the same time.",
                 "ℹ️ هذا الخادم به {n} معالج(ات). مع 4 معالجات أو أكثر يجد المحلّل جداول أفضل في نفس الوقت."),
    "tt_mode": ("Mode", "الوضع"),
    "mode_view": ("👁 View", "👁 عرض"),
    "mode_quick": ("✏️ Quick edit", "✏️ تعديل سريع"),
    "mode_free": ("🔓 Free edit", "🔓 تعديل حر"),
    "mode_help": ("View: read only. Quick edit: only checked moves/swaps (green/yellow). Free edit: forced moves allowed "
                  "(📌 pinned), conflicts are shown and the solver adapts the rest. Improve: the solver re-optimises the saved version for your goals.",
                  "عرض: قراءة فقط. تعديل سريع: التنقلات/التبديلات المتحقَّق منها فقط (أخضر/أصفر). تعديل حر: يُسمح بالنقل القسري "
                  "(📌 مثبّتة)، تُعرض التعارضات ويكيّف المحلّل الباقي. تحسين: يعيد المحلّل تحسين النسخة المحفوظة حسب أهدافك."),
    "no_state_edit": ("This version was saved without its editing state, so it can only be viewed.",
                      "حُفظت هذه النسخة دون حالة التعديل، لذا يمكن عرضها فقط."),
    "unsaved_badge": ("⚠ Unsaved changes: {n} change(s) in the working copy are shown here but not saved yet.",
                      "⚠ تعديلات غير محفوظة: {n} تغيير في نسخة العمل معروضة هنا لكنها لم تُحفظ بعد."),
    "export_unsaved": ("Save the changes as a version first to export them (the export uses saved versions).",
                       "احفظ التعديلات كنسخة أولًا لتصديرها (التصدير يعتمد على النسخ المحفوظة)."),
    "pv_title": ("Check before confirming", "تحقّق قبل التأكيد"),
    "pv_state": ("Current state (before the change). Outlined lessons will move:", "الحالة الحالية (قبل التغيير). الحصص المؤطّرة ستتنقّل:"),
    "pv_show": ("Show the tables of", "عرض جداول"),
    "pv_show_teacher": ("👨‍🏫 Teachers", "👨‍🏫 الأساتذة"),
    "pv_show_class": ("🎒 Classes", "🎒 الأفواج"),
    "full_screen": ("⛶ Full screen", "⛶ ملء الشاشة"),
    "view_pick": ("Show", "عرض"),
    "rn_panel": ("✏️ Teacher names in this solution", "✏️ أسماء الأساتذة في هذا الحل"),
    "rn_help": ("Type the real name in the 'New name' column (leave it empty to keep the current one), then apply. "
                "Only this solution changes (undo works); save it as a version to keep it. To use the names in future "
                "solves, change them in the assignment file too.",
                "اكتب الاسم الحقيقي في عمود «الاسم الجديد» (اتركه فارغًا للإبقاء على الحالي) ثم طبّق. "
                "يتغيّر هذا الحل فقط (التراجع ممكن)؛ احفظه كنسخة للاحتفاظ به. لاستعمال الأسماء في الحلول القادمة "
                "غيّرها أيضًا في ملف الإسناد."),
    "rn_old": ("Current name", "الاسم الحالي"),
    "rn_new": ("New name", "الاسم الجديد"),
    "rn_apply": ("Apply the names", "تطبيق الأسماء"),
    "rn_nothing": ("No name changed.", "لم يتغيّر أي اسم."),
    "rn_dup": ("Two teachers would get the same name: {x}", "سيحمل أستاذان نفس الاسم: {x}"),
    "rn_done": ("{n} teacher name(s) changed.", "تم تغيير {n} اسم."),
    "pv_confirm": ("✅ Confirm", "✅ تأكيد"),
    "pv_cancel": ("✖ Cancel", "✖ إلغاء"),
    "pv_none": ("No other class or teacher is affected.", "لا يتأثر أي فوج أو أستاذ آخر."),
    "pv_moves_to": ("moves to {w}", "تنتقل إلى {w}"),
    "pv_incoming": ("arrives here", "تصل إلى هنا"),
    "pv_clash": ("will be in conflict", "ستكون في تعارض"),
    "pv_leg_move": ("dashed = will move", "متقطّع = ستتنقّل"),
    "pv_leg_in": ("green = the moved lesson arrives", "أخضر = وصول الحصة المنقولة"),
    "pv_leg_clash": ("red = conflict (free edit)", "أحمر = تعارض (تعديل حر)"),
    "aff_title": ("Affected by the last change:", "تأثّر بالتغيير الأخير:"),
    "aff_open": ("Open", "فتح"),
    "aff_clear": ("Hide", "إخفاء"),
    "exp_only": ("Only one table", "جدول واحد فقط"),
    "exp_all": ("— everything selected above —", "— كل ما سبق اختياره —"),
    "open_pdf_tab": ("🔗 Open PDF in a new tab", "🔗 فتح PDF في تبويب جديد"),
    "open_this_pdf": ("🔗 This table as PDF (new tab)", "🔗 هذا الجدول PDF (تبويب جديد)"),
    "pdf_ready": ("PDF ready: open it", "ملف PDF جاهز: افتحه"),
    "dnd_forced_s": ("Forced", "قسري"),
    "free_mode": ("📌 Free moves (the solver adapts the rest)", "📌 تنقلات حرة (المحلّل يكيّف الباقي)"),
    "free_mode_help": ("Drag lessons anywhere, even onto occupied or impossible hours (orange). Each moved lesson is pinned 📌. Then press «Adapt the timetable»: the solver keeps your pins and moves as few other lessons as possible.",
                       "اسحب الحصص إلى أي مكان حتى إلى ساعات مشغولة أو غير ممكنة (برتقالي). تُثبَّت كل حصة منقولة 📌. ثم اضغط «تكييف الجدول»: يحافظ المحلّل على التثبيتات ويغيّر أقل عدد ممكن من الحصص الأخرى."),
    "dnd_forced": ("Allowed – will be adapted", "مسموح – سيُكيَّف"),
    "pv_all_moves": ("**All moves executed together if you confirm: {n}**", "**كل التنقلات التي ستُنفَّذ معا عند التأكيد: {n}**"),
    "pv_left_conf": ("**⚠️ Conflicts that will remain: {n}** (shown in the live table, fix later or 🔧 adapt)", "**⚠️ تعارضات ستبقى: {n}** (تظهر في الجدول المباشر، عالجها لاحقا أو 🔧 كيّف)"),
    "live_kpi": ("**📊 Live indicators**", "**📊 المؤشرات المباشرة**"),
    "live_saved": ("Saved version", "النسخة المحفوظة"),
    "live_now": ("Now", "الآن"),
    "live_conf": ("**⚠️ Conflicts now: {n}**", "**⚠️ التعارضات الحالية: {n}**"),
    "live_conf_none": ("No conflict – this timetable is valid.", "لا تعارض – هذا الجدول سليم."),
    "live_conf_help": ("Fix them by more moves/switches, or let the solver adapt (🔧).", "عالجها بتنقلات/تبديلات أخرى، أو دع المحلّل يكيّف (🔧)."),
    "live_when": ("When", "التوقيت"),
    "live_why": ("Problem", "المشكلة"),
    "e_noswitch": ("no clean switch possible here (lessons of different lengths or a split group would overlap) – it would create a double lesson in the class",
                   "لا يمكن التبديل هنا بشكل سليم (حصص بأطوال مختلفة أو تفويج سيتداخل) – سينتج حصتان في نفس الوقت للقسم"),
    "e_forced": ("📌 switched/placed anyway – remaining conflicts are shown, the solver can adapt ({m})", "📌 بُدّلت/وُضعت رغم ذلك – التعارضات المتبقية معروضة، ويمكن للمحلّل التكييف ({m})"),
    "e_lunch": ("A 2-hour block cannot cross the lunch break", "لا يمكن لحصة ساعتين أن تتخطى فترة الغداء"),
    "e_outside": ("Outside the school week (off hours)", "خارج أوقات الدراسة"),
    "e_c_double": ("double booking: {w}", "تداخل: {w}"),
    "pins_n": ("📌 Pinned lessons", "📌 حصص مثبّتة"),
    "conflicts_n": ("⚠ Conflicts", "⚠ تعارضات"),
    "pin_toggle": ("📌 Pin / unpin selected", "📌 تثبيت / إلغاء المحددة"),
    "pin_toggle_help": ("Select a lesson in the table (click), then pin it to keep it exactly where it is.",
                        "حدّد حصة في الجدول (نقرة) ثم ثبّتها لتبقى في مكانها تمامًا."),
    "pins_clear": ("Remove all pins", "إزالة كل التثبيتات"),
    "adapt_time": ("Max. time (seconds)", "الوقت الأقصى (ثوانٍ)"),
    "mode_improve": ("✨ Improve", "✨ تحسين"),
    "imp_unsaved": ("Improve works on the SAVED version. Your unsaved edits are not included: save them as a version first.",
                    "التحسين يعمل على النسخة المحفوظة. تعديلاتك غير المحفوظة غير مشمولة: احفظها كنسخة أولا."),
    "imp_zero_opt": ("No improvement possible: the solver PROVED that with these protections this timetable is already the best for your goals. Allow a relaxation or choose other goals.",
                     "لا تحسين ممكن: أثبت المحلّل أنه مع هذه الحمايات هذا الجدول هو الأفضل لأهدافك. اسمح بتخفيف أو اختر أهدافا أخرى."),
    "imp_zero": ("No improvement found: the solver searched {s} s (of {T} s) without finding a better timetable that respects all protections. Try more time, Free re-arrangement, or a relaxation.",
                 "لم يُعثر على تحسين: بحث المحلّل {s} ث (من {T} ث) دون إيجاد جدول أفضل يحترم كل الحمايات. جرّب وقتا أطول أو إعادة ترتيب حرة أو تخفيفا."),
    "imp_outside": ("Some lessons of this version are outside the allowed slots of the current rules (data or settings changed since it was solved).",
                    "بعض حصص هذه النسخة خارج الحصص المسموحة في القواعد الحالية (تغيّرت البيانات أو الإعدادات منذ حلّها)."),
    "imp_diag": ("Solver status: {st} · search {s} s · total {T} s", "حالة المحلّل: {st} · بحث {s} ث · المجموع {T} ث"),
    "imp_back": ("↩️ New attempt / close", "↩️ محاولة جديدة / إغلاق"),
    "imp_title": ("✨ Auto-improve this timetable", "✨ تحسين تلقائي لهذا الجدول"),
    "imp_help": ("Choose what to reduce. Every other indicator is protected (never worse). Relaxing a rule unlocks it and its linked rules. Pinned lessons never move.",
                 "اختر ما تريد تقليصه. كل المؤشرات الأخرى محمية (لا تسوء). تخفيف قاعدة يحرّرها مع القواعد المرتبطة بها. الحصص المثبّتة لا تتحرك."),
    "imp_goals": ("Goals (reduce)", "الأهداف (تقليص)"),
    "imp_main": ("Main goal (counts ×3)", "الهدف الرئيسي (وزن ×3)"),
    "imp_relax": ("**Relaxations** (extra units allowed)", "**التخفيفات** (وحدات إضافية مسموحة)"),
    "imp_relax_help": ("0 = protected. Empty mornings: at most +1 per class.", "0 = محمي. الصبيحات غير المكتملة: +1 كحد أقصى لكل قسم."),
    "imp_guards": ("Protected:", "محمي:"),
    "imp_off": ("Unlocked by the relaxation:", "محرَّر بسبب التخفيف:"),
    "imp_mode": ("Changes", "التغييرات"),
    "imp_mode_few": ("Few changes", "تغييرات قليلة"),
    "imp_mode_free": ("Free re-arrangement", "إعادة ترتيب حرة"),
    "imp_cap": ("Max lessons moved", "أقصى عدد للحصص المنقولة"),
    "imp_btn": ("✨ Improve", "✨ تحسين"),
    "imp_running": ("✨ Improving… about {m}:{s} left", "✨ جارٍ التحسين… الوقت المتبقي تقريبا {m}:{s}"),
    "imp_none": ("No better timetable found ({s}). Try more time or a relaxation.", "لم يُعثر على جدول أفضل ({s}). جرّب وقتا أطول أو تخفيفا."),
    "imp_ok": ("✨ Improved proposal: {m} lessons moved ({s} s). Review, then accept as a new version.", "✨ اقتراح محسَّن: {m} حصة نُقلت ({s} ث). راجِع ثم اقبل كنسخة جديدة."),
    "kpi_t_single": ("Teacher 1-hour half-days", "أنصاف أيام بساعة واحدة (أساتذة)"),
    "kpi_t_gap1": ("Teacher 1-hour gaps", "فراغات ساعة (أساتذة)"),
    "kpi_t_gap2": ("Teacher 2-hour gaps", "فراغات ساعتين (أساتذة)"),
    "kpi_t_shifts": ("Teacher half-days worked", "أنصاف الأيام المشتغلة (أساتذة)"),
    "kpi_t_days": ("Teacher working days", "أيام العمل (أساتذة)"),
    "kpi_t_late": ("Teacher days ending at last hour", "أيام تنتهي بآخر ساعة (أساتذة)"),
    "kpi_c_empty_morning": ("Classes: incomplete mornings", "الأقسام: صبيحات غير مكتملة"),
    "kpi_c_aft": ("Classes: afternoon hours", "الأقسام: ساعات المساء"),
    "kpi_c_slot7": ("Classes: last-hour lessons", "الأقسام: حصص آخر ساعة"),
    "kpi_c_slot7_max": ("Classes: last-hour peak", "الأقسام: ذروة آخر ساعة"),
    "adapt_btn": ("🔧 Adapt the timetable", "🔧 تكييف الجدول"),
    "adapt_help": ("Keeps every 📌 lesson and re-arranges the others, moving as few lessons as possible.",
                   "يحافظ على كل حصة 📌 ويعيد ترتيب الباقي مع تغيير أقل عدد ممكن من الحصص."),
    "regen_pins": ("🔄 Regenerate all, keep 📌", "🔄 إعادة التوليد مع الإبقاء على 📌"),
    "regen_pins_help": ("New timetable from scratch that only keeps the pinned lessons (may change many lessons).",
                        "جدول جديد كليًا يحافظ فقط على الحصص المثبّتة (قد يغيّر حصصًا كثيرة)."),
    "conflicts_list": ("⚠ {n} lesson(s) in conflict – the solver will resolve them", "⚠ {n} حصة في تعارض – سيحلّها المحلّل"),
    "adapt_running": ("🔧 Adapting… step {l}/{n} – about {m}:{s} left", "🔧 جارٍ التكييف… المرحلة {l}/{n} – بقي حوالي {m}:{s}"),
    "adapt_mismatch": ("The data or the settings changed since this version was created: it cannot be adapted. Reload the same data / settings, or generate a new timetable.",
                       "تغيّرت المعطيات أو الإعدادات منذ إنشاء هذه النسخة: لا يمكن تكييفها. أعد تحميل نفس المعطيات/الإعدادات أو ولّد جدولًا جديدًا."),
    "adapt_outside": ("These pinned lessons are at a forbidden hour (blocked window, day off, remediation hour…). Move or unpin them:",
                      "هذه الحصص المثبّتة في ساعة ممنوعة (نافذة محجوزة، يوم عطلة، ساعة استدراك…). انقلها أو ألغِ تثبيتها:"),
    "adapt_clash": ("These pinned lessons cannot all stay where they are (same class or teacher at the same hour, or no possible arrangement). Move or unpin one of them:",
                    "لا يمكن إبقاء كل هذه الحصص المثبّتة في مكانها (نفس الفوج أو الأستاذ في نفس الساعة، أو لا يوجد ترتيب ممكن). انقل إحداها أو ألغِ تثبيتها:"),
    "adapt_none": ("No arrangement found in the time given ({s}). Give more time, or adapt after fewer moves (e.g. every 3–5 moves).",
                   "لم يُعثر على ترتيب في الوقت المحدد ({s}). امنح وقتًا أطول، أو كيّف بعد عدد أقل من النقلات (مثلًا كل 3–5 نقلات)."),
    "adapt_failed_at": ("The problem appeared at this move (the earlier ones were placed):",
                        "ظهرت المشكلة عند هذه النقلة (النقلات السابقة وُضعت):"),
    "adapt_many": ("ℹ️ Many lessons moved. For the smallest changes, adapt after every few moves or give more time.",
                   "ℹ️ نُقلت حصص كثيرة. للحصول على أقل تغيير، كيّف بعد كل بضع نقلات أو امنح وقتًا أطول."),
    "adapt_close": ("Close", "إغلاق"),
    "adapt_ok": ("✅ {p} pinned lesson(s) kept · {m} other lesson(s) moved (search circle {l}, {s} s). Check and accept:",
                 "✅ حوفظ على {p} حصة مثبّتة · نُقلت {m} حصة أخرى (دائرة البحث {l}، {s} ث). راجع ثم اقبل:"),
    "regen_ok": ("✅ New timetable: {p} pinned lesson(s) kept · {m} lesson(s) changed ({s} s).",
                 "✅ جدول جديد: حوفظ على {p} حصة مثبّتة · تغيّرت {m} حصة ({s} ث)."),
    "mv_title": ("**Lessons moved by the solver**", "**الحصص التي نقلها المحلّل**"),
    "mv_lesson": ("Lesson", "الحصة"), "mv_from": ("From", "من"), "mv_to": ("To", "إلى"),
    "before_col": ("Before", "قبل"), "after_col": ("After", "بعد"),
    "proposal_preview": ("👁 Preview of the solver's proposal: 📌 your pins · green frame = lessons moved by the solver. Accept or cancel below.",
                         "👁 معاينة اقتراح المحلّل: 📌 تثبيتاتك · إطار أخضر = حصص نقلها المحلّل. اقبل أو ألغِ في الأسفل."),
    "adapt_accept": ("✅ Accept (save as new version)", "✅ قبول (حفظ كنسخة جديدة)"),
    "adapt_cancel": ("✖ Cancel", "✖ إلغاء"),
    "rec_title": ("🤝 Reception", "🤝 استقبال"),
    "rec_tip": ("Reception hour for parents – {t} (drag to move)", "ساعة استقبال الأولياء – {t} (اسحب لنقلها)"),
    "rec_moved": ("Reception {t} → {d} {s}", "استقبال {t} ← {d} {s}"),
    "rec_free": ("Free hour for the teacher", "ساعة شاغرة للأستاذ"),
    "rec_off": ("Outside school hours", "خارج أوقات الدراسة"),
    "rec_busy": ("The teacher has a lesson at this hour", "للأستاذ حصة في هذه الساعة"),
    "rec_window": ("Pedagogical window of the teacher", "نافذة بيداغوجية للأستاذ"),
    "rec_panel": ("🤝 Reception hours ({n})", "🤝 ساعات الاستقبال ({n})"),
    "rec_panel_help": ("One hour per week per teacher to receive parents. Placed automatically in a teacher gap when possible, else next to his lessons. Drag the 🤝 card in the teacher tables to move it, or add / remove it here.",
                       "ساعة أسبوعية لكل أستاذ لاستقبال الأولياء. توضع تلقائيًا في فراغ الأستاذ إن أمكن وإلا بجوار حصصه. اسحب بطاقة 🤝 في جداول الأساتذة لنقلها، أو أضفها/احذفها هنا."),
    "rec_none": ("no reception", "بدون استقبال"),
    "rec_add": ("➕ Place automatically", "➕ وضع تلقائي"),
    "rec_add_help": ("Adds (or re-places) the reception hour of this teacher at the best free hour.", "يضيف (أو يعيد وضع) ساعة استقبال هذا الأستاذ في أفضل ساعة شاغرة."),
    "rec_remove": ("🗑 Remove", "🗑 حذف"),
    "rec_reset": ("🔄 All automatic", "🔄 الكل تلقائيًا"),
    "rec_reset_help": ("Re-places the reception hours of all teachers automatically (manual changes are lost).", "يعيد وضع ساعات استقبال كل الأساتذة تلقائيًا (تضيع التعديلات اليدوية)."),
    "rec_nowhere": ("No free hour found for this teacher.", "لا توجد ساعة شاغرة لهذا الأستاذ."),
    "tab_guide": ("📘 Guide", "📘 الدليل"),
    "small_screen": ("📱 Small screen detected: the timetables and drag & drop need at least 900 px. Use a computer or a tablet in landscape mode (see Guide → known limits).",
                     "📱 شاشة صغيرة: الجداول والسحب والإفلات تحتاج 900 بكسل على الأقل. استعمل حاسوبًا أو لوحة بالوضع الأفقي (انظر الدليل ← حدود معروفة)."),
    "exp_rooms": ("Room occupancy", "شغل القاعات"),
    "adv_locked": ("🔒 Locked – default values are used. Enter the admin password (default: beta2026, changeable once unlocked).", "🔒 مقفل – تُستعمل القيم الافتراضية. أدخل كلمة سر المشرف (الافتراضية: beta2026، يمكن تغييرها بعد الفتح)."),
    "adv_lock": ("🔒 Lock", "🔒 قفل"),
    "layout": ("Layout", "طريقة العرض"),
    "lay_single": ("One timetable", "جدول واحد"), "lay_full_class": ("🗂 All classes", "🗂 كل الأفواج"),
    "lay_full_teacher": ("🗂 All teachers", "🗂 كل الأساتذة"),
    "full_hint": ("Click a lesson to see where it can go (green = free, yellow = swap), then click or drag it to a cell of the same row.",
                  "انقر على حصة لرؤية أماكنها الممكنة (أخضر = شاغر، أصفر = تبديل)، ثم انقر أو اسحبها إلى خانة في نفس السطر."),
    "full_loading": ("Checking possible moves…", "جارٍ فحص التنقلات الممكنة…"),
    "full_other_row": ("A lesson can only move inside its own row (same class / teacher).",
                       "لا يمكن نقل الحصة إلا داخل سطرها (نفس الفوج / الأستاذ)."),
    "e_rem_swap": ("a remediation session can only be swapped with another remediation session",
                   "حصة الاستدراك لا تُبادَل إلا مع حصة استدراك أخرى"),
    "rem_summary": ("Remediation: {n} sessions placed – {a} in slot 6, {b} in slot 7 · not placed: {x}",
                    "الاستدراك: {n} حصة مبرمجة – {a} في الحصة السادسة، {b} في السابعة · غير مبرمجة: {x}"),
    "day": ("Day", "اليوم"), "slot": ("Slot", "الحصة"),
    "rem_table": ("📚 Remediation sessions", "📚 حصص الاستدراك"),
    "rem_split": ("No common free hour for {t} – sessions placed separately.", "لا توجد ساعة شاغرة مشتركة لـ {t} – بُرمجت الحصص منفصلة."),
    "rem_none": ("No free slot 6 / slot 7 for {t} and all his classes.", "لا توجد حصة سادسة / سابعة شاغرة لـ {t} ولكل أفواجه."),
    "k_prio": ("⭐ priority {v}", "⭐ الأولوية {v}"), "k_hours": ("⏱ {v} h", "⏱ {v} سا"),
    "k_rem": ("{v} h remediation", "{v} سا استدراك"), "k_days": ("📅 {v} days", "📅 {v} أيام عمل"),
    "k_gaps": ("⏳ gaps {v}", "⏳ فراغات {v}"), "k_single": ("🕐 single-hour half-days {v}", "🕐 أنصاف أيام بحصة واحدة {v}"),
    "k_aft": ("🌇 afternoon {v} h", "🌇 مساءً {v} سا"), "k_slot7": ("🔚 7th slot {v}", "🔚 الحصة السابعة {v}"),
    "k_finish": ("🏁 avg. end slot {v}", "🏁 متوسط نهاية اليوم {v}"), "k_win": ("🚫 in own window {v}", "🚫 في نافذته {v}"),
    "k_sgaps": ("⏳ student gaps {v}", "⏳ فراغات التلاميذ {v}"), "k_empty_m": ("🌅 empty morning slots {v}", "🌅 خانات صباحية فارغة {v}"),
    "ks_Teacher": ("Teacher", "الأستاذ"), "ks_Priority": ("Priority", "الأولوية"), "ks_Hours": ("Hours", "الساعات"),
    "ks_Remedial": ("Remediation", "الاستدراك"), "ks_Days": ("Days", "الأيام"), "ks_Gaps": ("Gaps", "الفراغات"),
    "ks_Single_hour": ("Single-hour half-days", "أنصاف أيام بحصة واحدة"), "ks_Afternoon_h": ("Afternoon h", "ساعات مسائية"),
    "ks_Slot7": ("7th slots", "الحصة السابعة"), "ks_Avg_finish": ("Avg. end", "متوسط النهاية"),
    "ks_In_window": ("In own window", "في نافذته"), "ks_Classes": ("Classes", "الأفواج"),
    "n_classes": ("{n} classes", "{n} فوج"),
    "tot_class": ("Class", "الفوج"), "tot_teacher": ("Teacher", "الأستاذ"), "tot_hours": ("Weekly hours", "الحجم الساعي الأسبوعي"),
    "tot_rem": ("Remediation", "الاستدراك"), "tot_days": ("Working days", "أيام العمل"),
    "tot_h": ("{h} h", "{h} سا"), "tot_rem_h": ("{h} h remediation", "{h} سا استدراك"),
    "tot_title_c": ("📊 Total hours – {n} classes ({h} h)", "📊 الحجم الساعي – {n} فوج ({h} سا)"),
    "tot_title_t": ("📊 Total hours – {n} teachers ({h} h)", "📊 الحجم الساعي – {n} أستاذ ({h} سا)"),
    "grid_ok": ("Standard grid respected by {n} / {m} classes", "الشبكة المعيارية محترمة في {n} / {m} فوج"),
    "gr_Class": ("Class", "الفوج"), "gr_Hours": ("Hours", "الساعات"), "gr_Holes": ("Empty grid cells", "خانات فارغة في الشبكة"),
    "gr_Slot7_days": ("Days with 7th slot", "أيام بحصة سابعة"), "gr_Slot7_bad_day": ("7th slot on Thursday", "حصة سابعة يوم الخميس"),
    "strict_grid": ("🧱 Standard class grid (top-priority soft rule)", "🧱 الشبكة المعيارية للفوج (قاعدة مرنة بأعلى أولوية)"),
    "strict_grid_help": ("Every class: 5 mornings × 4 slots (20h) + first 2 afternoon slots on the 4 afternoon days (8h). "
                         "Each hour above 28 = one day with a 7th slot (29h → one 7h day, 30h → two …), never on Thursday.",
                         "كل فوج: 5 صباحات × 4 حصص (20 سا) + أول حصتين مساءً في أيام المساء الأربعة (8 سا). "
                         "كل ساعة فوق 28 = يوم بحصة سابعة (29 سا ← يوم واحد من 7 ساعات، 30 سا ← يومان …)، وليس يوم الخميس أبدًا."),
    "sl_grid": ("Grid (morning + afternoon + 7th)", "الشبكة (صباح + مساء + سابعة)"),
    "windows_hard": ("🚫 Teachers unavailable in their pedagogical windows", "🚫 الأساتذة غير متاحين في نوافذهم البيداغوجية"),
    "windows_hard_help": ("A teacher gets NO lesson (any subject, split sessions included) during the windows of the subjects "
                          "they teach. These hours are never counted as gaps.",
                          "لا يُسند للأستاذ أي حصة (أي مادة، بما فيها حصص التفويج) أثناء نوافذ المواد التي يدرّسها. "
                          "ولا تُحسب هذه الساعات فراغات."),
    "fair_title": ("⚖️ Teacher fairness", "⚖️ الإنصاف بين الأساتذة"),
    "prio_strength": ("Priority for the most loaded teachers (×)", "أولوية الأساتذة الأكثر ساعات (×)"),
    "prio_help": ("Comfort weights (gaps, single-hour half-days, working days, afternoon hours, late finish) are multiplied "
                  "by 1 for the teacher with the fewest hours and by this value for the teacher with the most hours "
                  "(linear in between). 1 = everybody equal.",
                  "تُضرب أوزان الراحة (الفراغات، نصف يوم بساعة واحدة، أيام العمل، ساعات المساء، الخروج المتأخر) "
                  "في 1 للأستاذ الأقل ساعات وفي هذه القيمة للأستاذ الأكثر ساعات (خطيًا بينهما). 1 = الجميع سواسية."),
    "w_teacher_late_finish_weight": ("Teacher late finish (per slot, per day)", "خروج الأستاذ المتأخر (لكل حصة، لكل يوم)"),
    "fair_table": ("⚖️ Teacher fairness report (sorted by weekly hours)", "⚖️ تقرير الإنصاف بين الأساتذة (مرتب حسب الحجم الساعي)"),
    "fair_caption": ("Teachers at the top have the most hours and the highest priority factor: they should have the fewest gaps and "
                     "single-hour half-days and the earliest finish. Pedagogical-window hours are not counted as gaps.",
                     "الأساتذة في الأعلى لهم أكبر حجم ساعي وأعلى معامل أولوية: يجب أن تكون لهم أقل الفراغات وأنصاف الأيام "
                     "بساعة واحدة وأبكر خروج. ساعات النوافذ البيداغوجية لا تُحسب فراغات."),
    "fr_Teacher": ("Teacher", "الأستاذ"), "fr_Hours": ("Hours", "الساعات"), "fr_Days": ("Days", "الأيام"),
    "fr_Gaps": ("Gaps (h)", "الفراغات (سا)"), "fr_Single_hour": ("Single-hour half-days", "أنصاف أيام بساعة واحدة"),
    "fr_Afternoon_h": ("Afternoon hours", "ساعات المساء"), "fr_Avg_finish": ("Avg finish (slot)", "متوسط الخروج (الحصة)"),
    "fr_Late_days": ("Days ending slot 6–7", "أيام تنتهي بالحصة 6–7"), "fr_Factor": ("Priority ×", "الأولوية ×"),
    "sr_title": ("🔀 Split rules (تفويج) – how the solver reads them", "🔀 قواعد التفويج – كيف يفهمها المحلّل"),
    "sr_caption": ("One row per rule. Check the description: this is exactly what will be scheduled for every class of the listed levels.",
                   "سطر لكل قاعدة. راجع الوصف: هذا بالضبط ما سيُبرمج لكل أفواج المستويات المذكورة."),
    "sr_c_rule": ("Rule", "القاعدة"), "sr_c_levels": ("Applied to", "تُطبّق على"),
    "sr_c_desc": ("How the solver reads it", "كيف يفهمها المحلّل"),
    "sr_c_slots": ("Class slots / week", "حصص الفوج / أسبوع"),
    "sr_c_teach": ("Teacher hours / class / week", "ساعات الأساتذة / فوج / أسبوع"),
    "sr_c_ignored": ("Not applied to", "لا تُطبّق على"), "sr_c_check": ("Check", "التحقق"),
    "sr_h": ("h", "سا"),
    "sr_d_14": ("One {L}h session per week: group A {p} {L}h ‖ group B {s}. The groups swap the following week (each group every 14 days).",
                "حصة واحدة مدتها {L} سا أسبوعيًا: الفوج أ {p} {L} سا ‖ الفوج ب {s}. يتبادل الفوجان في الأسبوع الموالي (كل فوج مرة كل 14 يومًا)."),
    "sr_d_b2b": ("One 2h block per week: hour 1 group A {p} ‖ group B {s}; hour 2 the groups swap (each group every week).",
                 "كتلة ساعتين متتاليتين أسبوعيًا: الساعة 1 الفوج أ {p} ‖ الفوج ب {s}؛ الساعة 2 يتبادل الفوجان (كل فوج كل أسبوع)."),
    "sr_d_week2": ("Two {L}h sessions per week (placed separately): group A {p} ‖ group B {s}, then the groups swap in the second session (each group every week).",
                   "حصتان مدة كل منهما {L} سا أسبوعيًا (منفصلتان): الفوج أ {p} ‖ الفوج ب {s}، ثم يتبادل الفوجان في الحصة الثانية (كل فوج كل أسبوع)."),
    "sr_ign": ("{l} (no {s} in curriculum)", "{l} (لا توجد {s} في المنهاج)"),
    "sr_p_sum": ("⚠ Secondary hours do not add up to Primary_Hours", "⚠ مجموع ساعات المواد الثانوية لا يساوي Primary_Hours"),
    "sr_p_count": ("⚠ Secondary_Hours must give one value per secondary subject", "⚠ يجب أن يحتوي Secondary_Hours على قيمة لكل مادة ثانوية"),
    "sr_p_freq": ("⚠ Frequency must be 1 (weekly) or 2 (every 14 days) – 2 used", "⚠ يجب أن يكون Frequency إما 1 (أسبوعي) أو 2 (كل 14 يومًا) – استُعمل 2"),
    "sr_p_curr": ("⚠ {l}: curriculum gives {s} {c}h TD/TP, this rule creates {r}h", "⚠ {l}: المنهاج يعطي {s} {c} سا أ.م/أ.ت، هذه القاعدة تُنشئ {r} سا"),
    "sr_old_format": ("Your file uses the old format (Coupling_Mode 1H/2H). It is still accepted – download the explicit version below "
                      "(with Primary_Hours, Secondary_Hours and Frequency) to make every rule unambiguous.",
                      "ملفك بالصيغة القديمة (Coupling_Mode 1H/2H). ما زال مقبولًا – نزّل الصيغة الواضحة أدناه "
                      "(مع Primary_Hours و Secondary_Hours و Frequency) لتصبح كل قاعدة دون لبس."),
    "sr_download": ("📥 Download rules in explicit format (split_rules_v2.csv)", "📥 تنزيل القواعد بالصيغة الواضحة (split_rules_v2.csv)"),
    "sr_help_btn": ("ℹ️ File format", "ℹ️ صيغة الملف"),
    "sr_help": ("""**Columns** (one row per rule):

| Column | Meaning | Example |
|---|---|---|
| Rule_ID | any name | R_FOUJ_04 |
| Level | `1AM;2AM` or `ALL` | ALL |
| Primary_Subject / Primary_Type | group A's subject during the whole session | INFO / TP |
| **Primary_Hours** | length of one session (h) | 2 |
| Secondary_Subject / Secondary_Type | group B's subject(s), **in order** | FRENCH;ENGLISH / TD |
| **Secondary_Hours** | hours of each secondary subject, in order – must add up to Primary_Hours | 1;1 |
| **Frequency** | 1 = every week (groups swap in the same week) · 2 = every 14 days (groups swap next week) | 2 |

A 1h session with Frequency 1 is placed as one 2h back-to-back block (swap after the first hour).
The old format (Coupling_Mode = 1H / 2H) is still accepted.""",
                """**الأعمدة** (سطر لكل قاعدة):

| العمود | المعنى | مثال |
|---|---|---|
| القاعدة (Rule_ID) | أي اسم | R_FOUJ_04 |
| المستوى (Level) | ‎`1AM;2AM` أو `ALL` | ALL / الكل |
| المادة أ / النوع أ | مادة الفوج أ طوال الحصة | INFO / TP |
| **ساعات أ** | مدة الحصة الواحدة (سا) | 2 |
| المادة ب / النوع ب | مادة/مواد الفوج ب **بالترتيب** | FRENCH;ENGLISH / TD |
| **ساعات ب** | ساعات كل مادة ثانوية بالترتيب – مجموعها = ساعات أ | 1;1 |
| **الحصص في الأسبوع** (Frequency) | ‏1 = كل أسبوع (التبادل في نفس الأسبوع) · 2 = كل 14 يومًا (التبادل في الأسبوع الموالي) | 2 |

حصة مدتها 1 سا مع «الحصص في الأسبوع» = 1 تُبرمج ككتلة ساعتين متتاليتين (التبادل بعد الساعة الأولى).
يمكن كتابة القيم بالعربية (مثال: إعلام آلي، أعمال تطبيقية، 1م) أو بالرموز.
الصيغة القديمة (Coupling_Mode = 1H / 2H) ما زالت مقبولة."""),
    "map_title": ("🔗 Subject codes not in the curriculum: {n} – suggested mapping",
                  "🔗 رموز مواد غير موجودة في المنهاج: {n} – ربط مقترح"),
    "map_caption": ("These codes appear in your files but not in the curriculum, so they are ignored. "
                    "Check the suggestions (change the target if needed, empty = drop) and click Apply. "
                    "Several codes with the same target are grouped into one subject (e.g. HIST + GEO + CIVICS → HISTGEO).",
                    "هذه الرموز موجودة في ملفاتك لكنها غير موجودة في المنهاج، لذلك تُهمل. "
                    "راجع الاقتراحات (غيّر المادة الهدف عند الحاجة، فارغ = حذف) ثم اضغط تطبيق. "
                    "الرموز التي لها نفس الهدف تُجمَّع في مادة واحدة (مثال: HIST + GEO + CIVICS → HISTGEO)."),
    "map_grid": ("Assignment grid", "جدول توزيع الحصص"),
    "map_c_src": ("File", "الملف"), "map_c_code": ("Code in file", "الرمز في الملف"),
    "map_c_target": ("→ Curriculum subject", "→ مادة المنهاج"), "map_c_kind": ("Type", "النوع"),
    "map_c_reason": ("Why", "السبب"),
    "map_target_help": ("Empty = drop this code", "فارغ = حذف هذا الرمز"),
    "map_k_synonym": ("Same subject, other name", "نفس المادة باسم آخر"),
    "map_k_group": ("Grouping (part of)", "تجميع (جزء من)"),
    "map_k_part": ("Partial name match", "تطابق جزئي في الاسم"),
    "map_k_similar": ("Similar spelling", "كتابة مشابهة"),
    "map_k_none": ("No suggestion – choose", "لا اقتراح – اختر"),
    "map_k_same": ("Same", "مطابق"),
    "map_apply": ("✅ Apply mapping", "✅ تطبيق الربط"),
    "map_active": ("Active mapping:", "الربط المُطبّق:"),
    "map_reset": ("↺ Reset mapping", "↺ إلغاء الربط"),
    "w_not_in_curr": ("Post '{p}' → subject {s}, which is not in the curriculum file",
                      "المنصب '{p}' ← المادة {s} غير موجودة في ملف المنهاج"),
    "w_split": ("{c}: {s} is split between {n} teachers – the scheduler supports one teacher per class & subject; keeping {t}",
                "{c}: المادة {s} موزعة على {n} أساتذة – يدعم البرنامج أستاذًا واحدًا لكل فوج ومادة؛ تم الإبقاء على {t}"),
    "w_unknown_cls": ("Classes in the matrix but not in classes.csv: {x}", "أفواج في الجدول غير موجودة في ملف الأفواج: {x}"),
    "w_no_posts": ("Could not find the row of posts (المناصب) – expected cells like 'عربية1', 'رياضيات2'.",
                   "تعذّر إيجاد سطر المناصب – يُنتظر خانات مثل 'عربية1'، 'رياضيات2'."),
    "w_no_classes": ("No class rows found – expected class labels like '4م1' or '4AM1'.",
                     "لم يُعثر على أسطر الأفواج – يُنتظر تسميات مثل '4م1' أو '4AM1'."),
    "w_post_small": ("{s}: a class needs {h}h but a post only has {c}h – raise max hours",
                     "{s}: فوج يحتاج {h} سا لكن المنصب لا يتسع إلا لـ {c} سا – ارفع الحجم الأقصى"),
    "assign_failed": ("Teacher assignment failed – check qualified subjects and max hours in staff.csv",
                      "فشل إسناد الأساتذة – تحقق من المواد المؤهلة والحجم الأقصى في ملف الأساتذة"),
}


def tr_message(m):
    """Warnings are stored as (key, kwargs) tuples so they can be shown in the current language."""
    if isinstance(m, tuple):
        k, kw = m
        return t(k, **kw)
    return str(m)
