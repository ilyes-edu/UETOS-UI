"""Step-by-step setup guide: builds a complete school (classes, curriculum, rooms, split rules,
pedagogical windows, teachers and the teacher assignment) from a few simple questions, starting
from the default curriculum.  Nothing has to be uploaded.

Pure logic (build_frames, needed_hours, suggest_counts, make_teachers, auto_assign, to_plan) is
kept separate from the Streamlit pages (render) so it can be tested on its own.
"""
import json
import math
import os

import pandas as pd

import i18n
import datai18n as dl
from i18n import t
import assignment_planner as ap

LEVELS = ["1AM", "2AM", "3AM", "4AM"]
DAYS_N = 5
SLOTS_N = 7
MORNING = [0, 1, 2, 3]

# default curriculum (weekly hours per level) – same as the school example
BASE_CURRICULUM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data", "curriculum.csv")
PROJECT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "projects", "wizard")

# default coordination windows (day index, morning) with the curriculum codes
DEFAULT_WINDOWS = {"ARABIC": 1, "ISLAMIC": 1, "FRENCH": 2, "ENGLISH": 2, "INFO": 2, "PHYS": 3, "SCIENCE": 3,
                   "MATH": 4, "MUSIC": 4, "ART": 4, "HISTGEO": 0, "SPORT": 0, "AMAZIGH": 2}

DEFAULTS = {
    "levels": {"1AM": 5, "2AM": 5, "3AM": 5, "4AM": 5},
    "amazigh": False, "amazigh_h": 3,
    "arts": "music",                 # none | music | art | both
    "music_h": 1, "art_h": 1,
    "labs": "dedicated", "n_labs": 6,
    "classrooms": 20,
    "info_levels": ["1AM", "2AM"], "it_rooms": 1, "it_mode": "half_lang",   # full | half_lang
    "sport_cap": 2,
    "g_armath": True, "g_physsci": True, "g_lang34": True, "rem_armath": True,
    "base_hours": 20, "mumayaz_less": 2, "rem_hours": 1,
    "windows": dict(DEFAULT_WINDOWS),
}
STEPS = ["levels", "subjects", "grouping", "teachers", "windows", "assign", "finish"]

# ------------------------------------------------------------------ strings (merged into i18n.S)
i18n.S.update({
    "src_wizard": ("🧭 Setup guide", "🧭 دليل الإعداد"),
    "wz_title": ("🧭 School setup guide", "🧭 دليل إعداد المؤسسة"),
    "wz_intro": ("Answer a few simple questions – the default curriculum does the rest. Every answer can be changed later.",
                 "أجب عن أسئلة بسيطة، والمنهاج الافتراضي يتكفّل بالباقي. يمكن تغيير كل إجابة لاحقًا."),
    "wz_step": ("Step {i} of {n}", "الخطوة {i} من {n}"),
    "wz_intro_files": ("Each step can be filled by answering its questions or by loading its file. A file can be loaded "
                       "in any step: it fills its own section.",
                       "يمكن ملء كل خطوة بالإجابة عن أسئلتها أو بتحميل ملفها. يمكن تحميل أي ملف في أي خطوة: يملأ القسم الخاص به."),
    "wz_sec_classes": ("Classes", "الأفواج"), "wz_sec_subjects": ("Curriculum", "المنهاج"),
    "wz_sec_rooms": ("Rooms", "القاعات"), "wz_sec_rules": ("Split rules", "قواعد التفويج"),
    "wz_sec_teachers": ("Teachers", "الأساتذة"), "wz_sec_inspections": ("Pedagogical windows", "النوافذ البيداغوجية"),
    "wz_sec_assign": ("Assignment", "الإسناد"),
    "wz_from_file": ("📄 **{s}** – from file «{f}» ({n} lines). The questions of this section are replaced by the file.",
                     "📄 **{s}** – من الملف «{f}» ({n} سطر). ملف هذا القسم يعوّض أسئلته."),
    "wz_manual_btn": ("✏️ Create manually instead", "✏️ الإنشاء يدويًا بدلًا منه"),
    "wz_step_upload": ("📎 Load a file (for this step or any other section – zip accepted)",
                       "📎 تحميل ملف (لهذه الخطوة أو لأي قسم آخر – يُقبل zip)"),
    "wz_filled_other": ("«{f}» filled the section {s} (step {i}).", "«{f}» ملأ قسم {s} (الخطوة {i})."),
    "wz_filled_here": ("«{f}» filled the section {s}.", "«{f}» ملأ قسم {s}."),
    "wz_not_recog": ("«{f}» was not recognised: {e}", "لم يُتعرّف على «{f}»: {e}"),
    "wz_confirm_over": ("⚠️ The section **{s}** is already filled ({o}). Replace it with «{f}»?",
                        "⚠️ قسم **{s}** مملوء مسبقًا ({o}). هل تريد استبداله بـ«{f}»؟"),
    "wz_by_file": ("file «{f}»", "الملف «{f}»"),
    "wz_by_manual": ("manual assignment", "إسناد يدوي"),
    "wz_replace": ("✅ Replace", "✅ استبدال"), "wz_keep": ("✖ Keep the current one", "✖ الإبقاء على الحالي"),
    "wz_bulk_title": ("📂 Load all your files at once", "📂 تحميل كل ملفاتك دفعة واحدة"),
    "wz_bulk_help": ("One zip with all the files (e.g. downloaded from the setup guide), or several CSV / Excel files. "
                     "Each file fills its step; the missing sections can be created manually in their step.",
                     "ملف zip واحد يضم كل الملفات (مثلًا المنزَّل من دليل الإعداد)، أو عدة ملفات CSV / Excel. "
                     "يملأ كل ملف خطوته، ويمكن إنشاء الأقسام الناقصة يدويًا في خطوتها."),
    "wz_bulk_state": ("From files: {a} · To create manually (questions): {b}", "من الملفات: {a} · للإنشاء يدويًا (أسئلة): {b}"),
    "wz_assign_extra": ("{n} line(s) of the assignment file do not exist in the curriculum and are ignored: {x}",
                        "{n} سطر من ملف الإسناد غير موجود في المنهاج وتم تجاهله: {x}"),
    "wz_s_levels": ("Levels & classes", "المستويات والأفواج"),
    "wz_s_subjects": ("Subjects & rooms", "المواد والقاعات"),
    "wz_s_grouping": ("Groups", "التفويج"),
    "wz_s_teachers": ("Teachers", "الأساتذة"),
    "wz_s_windows": ("Time grid & windows", "الشبكة الزمنية والنوافذ"),
    "wz_s_assign": ("Assignment", "الإسناد"),
    "wz_s_finish": ("Finish", "إنهاء"),
    "wz_prev": ("⬅️ Back", "➡️ السابق"),
    "wz_next": ("Next ➡️", "التالي ⬅️"),
    "wz_reopen": ("🧭 Open the setup guide", "🧭 فتح دليل الإعداد"),
    "wz_restart": ("♻️ Start again from defaults", "♻️ البدء من جديد بالقيم الافتراضية"),
    "wz_project_ok": ("Using the school built with the setup guide ({c} classes, {p} teachers).",
                      "يُستعمل إعداد المؤسسة المُنشأ بالدليل ({c} فوجًا، {p} أستاذًا)."),
    "wz_not_done": ("The setup guide is not finished yet.", "لم يكتمل دليل الإعداد بعد."),
    # step 1
    "wz_rules_from_preset": ("Group rules come from the school-type defaults; edit them later in the Data page (split rules).",
                             "قواعد التفويج من القيم الافتراضية لنوع المؤسسة؛ يمكن تعديلها لاحقًا في صفحة المعطيات (قواعد التفويج)."),
    "wz_tl_dl": ("⬇️ Download the teacher list", "⬇️ تنزيل قائمة الأساتذة"),
    "wz_tl_up": ("Load a teacher list (Name, Subject, Mumayaz, Remedial, Max)", "تحميل قائمة أساتذة (Name, Subject, Mumayaz, Remedial, Max)"),
    "wz_tl_cols": ("The file needs at least the columns Name and Subject.", "يجب أن يحتوي الملف على العمودين Name و Subject على الأقل."),
    "wz_tl_apply": ("✅ Replace the list by {n} teachers", "✅ استبدال القائمة بـ {n} أستاذًا"),
    "wz_g_title": ("TD / TP in groups", "الأعمال الموجهة / التطبيقية بالأفواج"),
    "wz_g_help": ("Every TD/TP is taught in 2 groups (A/B). Choose once per subject; it applies to all levels. "
                  "Partner options need a partner subject with the same hours in the level.",
                  "كل حصة أعمال موجهة/تطبيقية تُدرَّس بفوجين (أ/ب). اختر مرة واحدة لكل مادة، ويُطبَّق على كل المستويات. "
                  "خيارات المادة الشريكة تحتاج مادة بنفس الساعات في المستوى."),
    "wz_g_none": ("The curriculum has no TD/TP hours.", "لا توجد ساعات أعمال موجهة/تطبيقية في المنهاج."),
    "wz_g_level": ("Level", "المستوى"), "wz_g_all": ("All levels", "كل المستويات"),
    "wz_g_c_level": ("Level", "المستوى"), "wz_g_c_hours": ("h / student", "سا / تلميذ"),
    "wz_g_c_mode": ("Grouping", "التفويج"), "wz_g_c_partner": ("Partner (pair)", "المادة الشريكة (pair)"),
    "wz_g_m_alt": ("One session – groups A/B alternate weeks", "حصة واحدة – الفوجان أ/ب بالتناوب أسبوعيًا"),
    "wz_g_m_pair_alt": ("One session with a partner subject – swap next week", "حصة واحدة مع مادة شريكة – التبادل الأسبوع الموالي"),
    "wz_g_m_div": ("Each group every week (2 sessions, same teacher)", "كل فوج كل أسبوع (حصتان، نفس الأستاذ)"),
    "wz_g_m_pair": ("Double session with a partner – swap in the middle", "حصة مضاعفة مع مادة شريكة – التبادل في منتصفها"),
    "wz_g_m_whole": ("Whole class (not divided)", "القسم كاملًا (بدون تفويج)"),
    "wz_g_c_levels": ("Levels", "المستويات"),
    "wz_g_mixed": ("✱ = the levels have different choices (see 'per level')", "✱ = اختيارات مختلفة حسب المستوى (انظر 'حسب المستوى')"),
    "wz_g_per_level": ("Different choice for one level", "اختيار مختلف لمستوى معيّن"),
    "wz_g_sum2": ("{p} pairs with a partner · {a} alternate-week sessions · {d} weekly per group · {w} whole class.",
                  "{p} أزواج مع مادة شريكة · {a} حصص بالتناوب أسبوعيًا · {d} أسبوعية لكل فوج · {w} قسم كامل."),
    "wz_g_bad": ("{l} – {s} {ty}: the partner «{p}» is missing in this level, already used, or has different hours → alternate weeks.",
                 "{l} – {s} {ty}: المادة الشريكة «{p}» غير موجودة في هذا المستوى أو مستعملة أو بساعات مختلفة ← بالتناوب أسبوعيًا."),
    "wz_g_sum": ("{p} parallel pairs, {d} divided TD/TP.", "{p} أزواج متوازية، {d} حصص مقسَّمة."),
    "wz_sf_title": ("📎 School files", "📎 ملفات المؤسسة"),
    "wz_sf_help": ("Only two files are needed: the classes (streams and number of classes) and the staff (teachers per "
                   "subject, regular and distinguished). The curriculum is the default one (step 2, editable).",
                   "يكفي ملفان: الأفواج (الشعب وعدد الأفواج) والأساتذة (عدد الأساتذة لكل مادة، عاديون ومميزون). "
                   "المنهاج هو المنهاج الافتراضي (الخطوة 2، قابل للتعديل)."),
    "wz_sf_classes": ("Classes file", "ملف الأفواج"), "wz_sf_staff": ("Staff file", "ملف الأساتذة"),
    "wz_sf_unknown": ("Row {r}: «{x}» not recognised – enter its classes below.", "السطر {r}: «{x}» غير معروف – أدخل أفواجه أدناه."),
    "wz_sf_which": ("«{x}» ({n} classes): which option?", "«{x}» ({n} أفواج): أي اختيار؟"),
    "wz_sf_subj": ("Staff row «{x}»: which subject?", "سطر الأساتذة «{x}»: أي مادة؟"),
    "wz_sf_cls_ok": ("{f}: {n} classes detected – check them below.", "{f}: تم اكتشاف {n} فوجًا – تحقق منها أدناه."),
    "wz_sf_stf_ok": ("{f}: {n} teachers detected ({r} regular + {d} distinguished).",
                     "{f}: تم اكتشاف {n} أستاذًا ({r} عاديًا + {d} مميزًا)."),
    "wz_sf_noteacher": ("No teacher of {s} in the staff file, but these streams need it: {l}.",
                        "لا يوجد أستاذ {s} في ملف الأساتذة، لكن هذه الشعب تحتاجه: {l}."),
    "wz_classes_n": ("Classes", "عدد الأفواج"),
    "wz_struct": ("🌳 Years and tracks (school structure)", "🌳 السنوات والشعب (هيكل المؤسسة)"),
    "wz_struct_help": ("Years: free number and names. Tracks: optional; list the years where each track exists (IDs separated "
                       "by ';'). A year with tracks gives one level per track (e.g. 2AS-SCI); classes = level × number.",
                       "السنوات: عدد وأسماء حرة. الشعب: اختيارية؛ اذكر السنوات التي توجد فيها كل شعبة (رموز يفصل بينها ';'). "
                       "السنة ذات الشعب تعطي مستوى لكل شعبة (مثل 2AS-SCI)؛ الأفواج = المستوى × العدد."),
    "wz_years": ("Years", "السنوات"), "wz_tracks": ("Tracks", "الشعب"),
    "wz_track_years": ("Years (;)", "السنوات (;)"), "wz_struct_apply": ("✅ Apply the structure", "✅ تطبيق الهيكل"),
    "wz_cur_edit": ("✏️ Edit the curriculum (hours per level and subject)", "✏️ تعديل المنهاج (الساعات حسب المستوى والمادة)"),
    "wz_cur_use": ("✅ Use this curriculum", "✅ اعتماد هذا المنهاج"),
    "wz_cur_edited": ("edited curriculum", "منهاج معدَّل"),
    "wz_q_levels": ("How many classes do you have in each level?", "كم عدد الأفواج في كل مستوى؟"),
    "wz_level": ("Level {l}", "المستوى {l}"),
    "wz_total_classes": ("Total: {n} classes", "المجموع: {n} فوجًا"),
    # step 2
    "wz_q_optional": ("Optional subjects", "المواد الاختيارية"),
    "wz_amazigh": ("Amazigh is taught", "تُدرَّس اللغة الأمازيغية"),
    "wz_hours_week": ("Hours per week", "ساعات في الأسبوع"),
    "wz_arts": ("Arts education", "التربية الفنية"),
    "wz_arts_none": ("None", "لا شيء"), "wz_arts_music": ("Music only", "موسيقى فقط"),
    "wz_arts_art": ("Art (drawing) only", "تربية تشكيلية فقط"), "wz_arts_both": ("Both", "كلاهما"),
    "wz_q_rooms": ("Rooms", "القاعات"),
    "wz_classrooms": ("Normal classrooms", "عدد القاعات العادية"),
    "wz_labs": ("Physics / Science practical work", "الأعمال التطبيقية (فيزياء / علوم)"),
    "wz_labs_dedicated": ("Dedicated labs", "مخابر مخصّصة"),
    "wz_labs_class": ("In normal classrooms", "في القاعات العادية"),
    "wz_n_labs": ("Number of labs", "عدد المخابر"),
    "wz_q_it": ("Computer science (IT)", "الإعلام الآلي"),
    "wz_info_levels": ("Levels that have IT", "المستويات التي تدرس الإعلام الآلي"),
    "wz_it_rooms": ("IT rooms", "عدد قاعات الإعلام الآلي"),
    "wz_it_mode": ("IT room capacity", "سعة قاعة الإعلام الآلي"),
    "wz_it_full": ("Full class", "فوج كامل"),
    "wz_it_half": ("Half class – the other half has French then English", "نصف فوج – النصف الآخر يدرس الفرنسية ثم الإنجليزية"),
    "wz_sport": ("Sport field: how many classes at the same time?", "الملعب: كم فوجًا في نفس الوقت؟"),
    "wz_curr_preview": ("Resulting curriculum (hours per week)", "المنهاج الناتج (ساعات أسبوعية)"),
    # step 3
    "wz_q_grouping": ("How are classes split into groups?", "كيف تُقسَّم الأفواج إلى أفواج فرعية؟"),
    "wz_g_armath": ("Arabic / Math practice (TD): half class each, groups swap",
                    "أعمال موجهة عربية / رياضيات: نصف فوج لكل مادة ثم يتبادلان"),
    "wz_g_armath_h": ("1AM–3AM: 1h, alternating weeks · 4AM: 2h block every week",
                      "1م–3م: ساعة بالتناوب أسبوعيًا · 4م: حصة ساعتين كل أسبوع"),
    "wz_g_physsci": ("Physics / Science practical work (TP): 2h block, groups swap after 1h",
                     "أعمال تطبيقية فيزياء / علوم: حصة ساعتين، يتبادل الفوجان بعد ساعة"),
    "wz_g_lang34": ("French / English practice for levels without IT: half class each",
                    "أعمال موجهة فرنسية / إنجليزية للمستويات بدون إعلام آلي: نصف فوج لكل مادة"),
    "wz_rem_title": ("Remedial work (استدراك)", "حصص الاستدراك"),
    "wz_rem_armath": ("Arabic and Math teachers of the same classes share ONE remedial session",
                      "أستاذا العربية والرياضيات لنفس الأفواج يشتركان في حصة استدراك واحدة"),
    "wz_rules_preview": ("Generated group rules", "قواعد التفويج الناتجة"),
    # step 4
    "wz_q_teachers": ("How many teachers per subject?", "كم أستاذًا في كل مادة؟"),
    "wz_base_hours": ("Full weekly load of a teacher (h)", "النصاب الأسبوعي للأستاذ (سا)"),
    "wz_mumayaz_less": ("A أستاذ مميز teaches fewer hours (h)", "الأستاذ المميز يدرّس ساعات أقل بـ (سا)"),
    "wz_rem_hours": ("Remedial hours per teacher (inside the load)", "ساعات الاستدراك لكل أستاذ (ضمن النصاب)"),
    "wz_c_subject": ("Subject", "المادة"), "wz_c_needed": ("Hours needed", "الساعات المطلوبة"),
    "wz_c_n": ("Teachers", "عدد الأساتذة"), "wz_c_mum": ("of which مميز", "منهم مميز"),
    "wz_c_rem": ("Remedial", "استدراك"), "wz_c_cap": ("Capacity", "الطاقة"),
    "wz_c_balance": ("Balance", "الفارق"),
    "wz_teacher_list": ("Teacher list (edit names, مميز and remedial per teacher)",
                        "قائمة الأساتذة (عدّل الأسماء، المميز والاستدراك لكل أستاذ)"),
    "wz_c_name": ("Teacher", "الأستاذ"), "wz_c_hours": ("Class hours", "ساعات الأفواج"),
    "wz_c_total": ("Total", "المجموع"), "wz_c_classes": ("Classes", "الأفواج"), "wz_c_max": ("Load", "النصاب"),
    "wz_short": ("⚠️ {s}: {h}h are missing – add a teacher, or accept to drop hours in the assignment step.",
                 "⚠️ {s}: تنقص {h} سا – أضف أستاذًا، أو اقبل حذف ساعات في خطوة الإسناد."),
    "wz_regen": ("↻ Rebuild the list from the counts", "↻ إعادة بناء القائمة من الأعداد"),
    # step 5
    "wz_grid_info": ("School week: Sunday–Thursday · 4 morning hours + 3 afternoon hours · Tuesday afternoon off. "
                     "The student grid is filled in this order: mornings, then hours 5–6, then hour 7.",
                     "أسبوع الدراسة: الأحد–الخميس · 4 ساعات صباحًا + 3 مساءً · مساء الثلاثاء عطلة. "
                     "تُملأ شبكة التلاميذ بالترتيب: الصباح، ثم الساعتان 5–6، ثم الساعة 7."),
    "wz_q_windows": ("Coordination windows: which morning is kept free for each subject's teachers?",
                     "النوافذ البيداغوجية: أي صبيحة تبقى حرة لأساتذة كل مادة؟"),
    "wz_no_window": ("No window", "بدون نافذة"),
    # step 6
    "wz_q_assign": ("Drag classes between teachers of the same subject. Totals update live.",
                    "اسحب الأفواج بين أساتذة نفس المادة. المجاميع تتحدث مباشرة."),
    "wz_auto": ("✨ Suggest automatically", "✨ اقتراح تلقائي"),
    "wz_unassigned": ("{n} class/subject pairs have no teacher ({h}h).", "{n} حصة (فوج/مادة) بدون أستاذ ({h} سا)."),
    "wz_bypass": ("Accept: these hours are dropped from the timetable (curriculum bypass)",
                  "أقبل: تُحذف هذه الساعات من الجدول (تجاوز المنهاج)"),
    "wz_add_teacher": ("➕ Go back and add teachers", "➕ الرجوع لإضافة أساتذة"),
    "wz_over": ("⛔ {n} teacher(s) above their load: {x}", "⛔ {n} أستاذ فوق النصاب: {x}"),
    "wz_accept_over": ("Accept the overload (overtime)", "أقبل تجاوز النصاب (ساعات إضافية)"),
    "wz_all_ok": ("✅ Every class has a teacher for every subject, and no teacher is above the load.",
                  "✅ لكل فوج أستاذ في كل مادة، ولا أحد فوق النصاب."),
    "wz_fix_first": ("Resolve the points above to continue.", "عالج النقاط أعلاه للمتابعة."),
    # step 7
    "wz_summary": ("Summary", "الملخص"),
    "wz_sum_line": ("{c} classes · {s} subjects · {p} teachers · {r} group rules · {w} windows",
                    "{c} فوجًا · {s} مادة · {p} أستاذًا · {r} قاعدة تفويج · {w} نافذة"),
    "wz_apply": ("✅ Use this school", "✅ اعتماد هذه المؤسسة"),
    "wz_download": ("⬇️ Download the data files (zip)", "⬇️ تنزيل ملفات المعطيات (zip)"),
    "wz_applied": ("Done! Review the assignment, then continue to ⚙️ Generate.",
                   "تم! راجع الإسناد ثم تابع إلى ⚙️ التوليد."),
    "wz_dropped": ("Dropped hours (bypass): {x}", "ساعات محذوفة (تجاوز): {x}"),
    "a_pool": ("Without teacher", "بدون أستاذ"), "a_drop_hint": ("Drop classes here", "أفلت الأفواج هنا"),
    "a_all": ("All subjects", "كل المواد"),
    "a_clear_t": ("Empty this teacher", "إفراغ هذا الأستاذ"),
    "a_clear_s": ("🧹 Empty this subject", "🧹 إفراغ هذه المادة"),
    "a_clear_a": ("🧹 Empty everything", "🧹 إفراغ الكل"),
    "a_confirm_all": ("Remove every class from every teacher?", "سحب كل الأفواج من كل الأساتذة؟"),
    "a_mode_on": ("✋ Click classes to give them to {t} (click again to remove)", "✋ انقر على الأفواج لإسنادها إلى {t} (نقرة ثانية للسحب)"),
    "a_mode_off": ("Tip: click a teacher, then click classes to assign them – or drag and drop.",
                   "نصيحة: انقر على أستاذ ثم انقر على الأفواج لإسنادها إليه – أو اسحب وأفلت."),
    "a_mode_stop": ("Done", "إنهاء"),
    "a_select_tip": ("Click to select this teacher", "انقر لاختيار هذا الأستاذ"),
})


def _ans(ss):
    if "wz" not in ss:
        ss["wz"] = json.loads(json.dumps(DEFAULTS))
    a = ss["wz"]
    import presets as _pr
    if a.get("preset") not in (None, _pr.CURRENT_ID) and not a.get("files"):   # school type changed: its own defaults
        ss["wz"] = a = json.loads(json.dumps(DEFAULTS))
    if a.get("preset") is None or not a.get("years"):  # years / tracks / counts come from the server preset (free to edit)
        P = _pr.load()
        nm = lambda x: (x.get("name") or {})
        a["years"] = [{"id": str(y["id"]), "en": nm(y).get("en", y["id"]), "ar": nm(y).get("ar", y["id"])}
                      for y in sorted(P.get("years", []), key=lambda y: y.get("order", 0))]
        a["tracks"] = [{"id": tr["id"], "en": nm(tr).get("en", tr["id"]), "ar": nm(tr).get("ar", tr["id"]),
                        "years": list(tr.get("years", []))} for tr in P.get("tracks", [])]
        sc = P.get("wizard", {}).get("sample_counts")
        if sc:
            a["levels"] = dict(sc)
        a["msq"] = bool(P.get("wizard", {}).get("middle_school_questions", True))
        if P.get("teacher_defaults", {}).get("max_hours"):
            a["base_hours"] = int(P["teacher_defaults"]["max_hours"])
        if not a["msq"]:
            a["info_levels"] = []
            a["windows"] = {w["subject"]: int(w["day"]) for w in P.get("subject_unavailable", [])}
        a["preset"] = _pr.CURRENT_ID
    a.setdefault("tracks", [])
    return a


def levels_of(a):
    """[(level key, year id, track id or '')]: a year without track is one level; with tracks, one level per track."""
    out = []
    for y in a.get("years") or [{"id": l} for l in LEVELS]:
        trs = [tr for tr in a.get("tracks", []) if y["id"] in tr.get("years", [])]
        out += [(f"{y['id']}-{tr['id']}", y["id"], tr["id"]) for tr in trs] or [(y["id"], y["id"], "")]
    return out


def level_keys(a):
    return [k for k, _, _ in levels_of(a)]


def level_label(a, key):
    """Display name of a level key in the current language."""
    lang = "ar" if i18n.is_ar() else "en"
    for k, y, tr in levels_of(a):
        if k == key:
            yn = next((x.get(lang) or x["id"] for x in a.get("years", []) if x["id"] == y), y)
            tn = next((x.get(lang) or x["id"] for x in a.get("tracks", []) if x["id"] == tr), "")
            return f"{yn} {tn}".strip()
    return key


# ------------------------------------------------------------------ pure logic
STEP_OF = {"classes": "levels", "subjects": "levels", "rooms": "subjects", "rules": "grouping", "teachers": "teachers",
           "inspections": "windows", "assign": "assign"}


def file_of(a, k):
    """{'name', 'records'} when the section k comes from a loaded file, else None."""
    if k == "subjects":
        return {"name": a.get("curriculum_name", "?"), "records": a["curriculum"]} if a.get("curriculum") else None
    return (a.get("files") or {}).get(k)


def _file_df(a, k):
    f = file_of(a, k)
    return pd.DataFrame(f["records"]) if f and f.get("records") is not None else None


def build_frames(a):
    """answers (+ loaded files) -> dict of data frames in the application's formats (without teachers)."""
    LV = level_keys(a)
    classes = pd.DataFrame([{"Class_ID": f"{l}{i}", "Level": l}
                            for l in LV for i in range(1, int(a["levels"].get(l, 0)) + 1)], columns=["Class_ID", "Level"])
    if file_of(a, "classes"):
        classes = _file_df(a, "classes")[["Class_ID", "Level"]].astype(str)
    active = list(dict.fromkeys(classes["Level"])) if file_of(a, "classes") else \
        [l for l in LV if int(a["levels"].get(l, 0)) > 0]
    import presets as _pr
    base = _pr.curriculum_df()
    _add = []                                           # track levels start from their year's curriculum
    for k, y, tr in levels_of(a):
        if tr and k not in set(base["Level"]):
            _add.append(base[base["Level"] == y].assign(Level=k))
    if _add:
        base = pd.concat([base] + _add, ignore_index=True)
    msq = a.get("msq", True)
    if msq:
        base = base[~base["Subject_Code"].isin(["MUSIC", "ART", "AMAZIGH", "INFO"])]
    extra = []
    for l in (LV if msq else []):
        if a["arts"] in ("music", "both"):
            extra.append((l, "MUSIC", a["music_h"], 0, 0, 0, "classroom"))
        if a["arts"] in ("art", "both"):
            extra.append((l, "ART", a["art_h"], 0, 0, 0, "classroom"))
        if a["amazigh"]:
            extra.append((l, "AMAZIGH", a["amazigh_h"], 0, 0, 0, "classroom"))
        if l in a["info_levels"]:
            extra.append((l, "INFO", 0, 0, 2, 0, "computer_lab"))
    cur = pd.concat([base, pd.DataFrame(extra, columns=base.columns)], ignore_index=True)
    if a.get("curriculum"):                             # the school's own curriculum file, used as it is
        cur = _file_df(a, "subjects")
        for c in ["Hrs_Cours", "Hrs_TD", "Hrs_TP", "Hrs_Practice"]:
            cur[c] = pd.to_numeric(cur[c], errors="coerce").fillna(0) if c in cur else 0
        if "Required_Room_Type" not in cur:
            cur["Required_Room_Type"] = "classroom"
    cur = cur[cur["Level"].isin(active)]
    if msq and a["labs"] != "dedicated" and not a.get("curriculum"):
        cur.loc[cur["Subject_Code"].isin(["PHYS", "SCIENCE"]), "Required_Room_Type"] = "classroom"
    order = {s: i for i, s in enumerate(["ARABIC", "AMAZIGH", "ISLAMIC", "MATH", "FRENCH", "ENGLISH", "PHYS", "SCIENCE",
                                         "HISTGEO", "INFO", "MUSIC", "ART", "SPORT"])}
    cur = cur.assign(_o=cur["Subject_Code"].map(order).fillna(99), _l=cur["Level"]).sort_values(["_l", "_o"]) \
             .drop(columns=["_o", "_l"]).reset_index(drop=True)
    for c in ["Hrs_Cours", "Hrs_TD", "Hrs_TP", "Hrs_Practice"]:
        cur[c] = cur[c].astype(int)

    rooms = [("classroom", int(a["classrooms"])), ("gym", int(a["sport_cap"])), ("computer_lab", int(a["it_rooms"]))]
    if a["labs"] == "dedicated":
        rooms.append(("lab", int(a["n_labs"])))
    if not a.get("msq", True):                          # room types of the preset not covered by the questions
        have = {r for r, _ in rooms}
        rooms += [(r["id"], int(r.get("count", 0))) for r in _pr.load().get("room_types", []) if r["id"] not in have]
    rooms = pd.DataFrame(rooms, columns=["Room_Type", "Capacity"])

    rules = []
    lv = lambda ls: ";".join(l for l in ls if l in active)
    if a["g_armath"]:
        if lv(["1AM", "2AM", "3AM"]):
            rules.append(("R_FOUJ_01", lv(["1AM", "2AM", "3AM"]), "ARABIC", "TD", 1, "MATH", "TD", 1, 2,
                          "1h per week: group A Arabic / group B Math - groups swap next week"))
        if lv(["4AM"]):
            rules.append(("R_FOUJ_02", "4AM", "ARABIC", "TD", 1, "MATH", "TD", 1, 1,
                          "Every week: 2h block - groups swap after the first hour"))
    if a["g_physsci"]:
        rules.append(("R_FOUJ_03", "ALL", "PHYS", "TP", 1, "SCIENCE", "TP", 1, 1,
                      "Every week: 2h lab block - groups swap after the first hour"))
    info_lv = lv(a["info_levels"])
    if a["it_mode"] == "half_lang" and info_lv:
        rules.append(("R_FOUJ_04", info_lv, "INFO", "TP", 2, "FRENCH;ENGLISH", "TD", "1;1", 2,
                      "2h per week: group A Informatics 2h / group B French 1h then English 1h - groups swap next week"))
    no_info = lv([l for l in LV if l not in a["info_levels"]])
    if a["g_lang34"] and no_info:
        rules.append(("R_FOUJ_05", no_info, "FRENCH", "TD", 1, "ENGLISH", "TD", 1, 2,
                      "1h per week: group A French / group B English - groups swap next week"))
    if not msq:
        rules = []
    rules = pd.DataFrame(rules, columns=["Rule_ID", "Level", "Primary_Subject", "Primary_Type", "Primary_Hours",
                                         "Secondary_Subject", "Secondary_Type", "Secondary_Hours", "Frequency",
                                         "Description"])
    subjects = set(cur["Subject_Code"])
    win = [{"Subject_Code": s, "Day_Index": int(d), "Blocked_Slots": ";".join(map(str, MORNING)),
            "Description": f"{s} coordination"} for s, d in a["windows"].items()
           if s in subjects and d is not None and int(d) >= 0]
    windows = pd.DataFrame(win, columns=["Subject_Code", "Day_Index", "Blocked_Slots", "Description"])
    divided = pd.DataFrame(columns=["ID", "Levels", "Subject", "Type", "Groups", "Block", "Weeks"])
    if not msq:                                         # every TD/TP in 2 groups: pairs -> split rules, others divided
        g_rules, g_div, _ = grouping_tables(grouping_rows(a, cur, active))
        rules = pd.DataFrame(g_rules, columns=["Rule_ID", "Level", "Primary_Subject", "Primary_Type", "Primary_Hours",
                                               "Secondary_Subject", "Secondary_Type", "Secondary_Hours", "Frequency",
                                               "Description"])
        divided = pd.DataFrame(g_div, columns=["ID", "Levels", "Subject", "Type", "Groups", "Block", "Weeks"])
    out = {"classes": classes, "subjects": cur, "rooms": rooms, "rules": rules, "inspections": windows, "divided": divided}
    for k in ("rooms", "rules", "inspections"):
        if file_of(a, k):
            out[k] = _file_df(a, k)
    return out


# ------------------------------------------------------------------ TD/TP grouping (every TD/TP is taught in 2 groups)
GROUP_MODES = ["alt", "pair_alt", "div", "pair", "whole"]
#  alt      : one session per week, the 2 groups alternate weeks (teacher h)
#  pair_alt : one session, group A subject X / group B subject Y, swap the next week (each teacher h)
#  div      : each group every week, same teacher (teacher 2h; the other group may have another TD at that time)
#  pair     : one session twice as long, 2 subjects in parallel, the groups swap in the middle (each teacher 2h)
#  whole    : whole class, not divided


def td_tp_items(cur, active):
    out = []
    for r in cur.to_dict("records"):
        if str(r["Level"]) not in active:
            continue
        for ty in ("TD", "TP"):
            h = int(float(r.get("Hrs_" + ty, 0) or 0))
            if h > 0:
                out.append({"Level": str(r["Level"]), "Subject": r["Subject_Code"], "Type": ty, "Hours": h})
    return out


def grouping_rows(a, cur, active):
    """Current choice for every TD/TP of the curriculum (manager's choices kept, else preset defaults/suggestions)."""
    import presets as _pr
    W = _pr.load().get("wizard", {})
    dflt = W.get("grouping_default", "div")
    items = td_tp_items(cur, active)
    prev = {(g["Level"], g["Subject"], g["Type"]): g for g in a.get("grouping") or []}
    have = {(i["Level"], i["Subject"], i["Type"]): i for i in items}
    sugg = {}
    for s1, t1, s2, t2 in W.get("grouping_pairs", []):
        for lv in active:
            i1, i2 = have.get((lv, s1, t1)), have.get((lv, s2, t2))
            if i1 and i2 and i1["Hours"] == i2["Hours"] and (lv, s1, t1) not in sugg and (lv, s2, t2) not in sugg:
                sugg[(lv, s1, t1)] = f"{s2} {t2}"; sugg[(lv, s2, t2)] = f"{s1} {t1}"
    rows = []
    for k, i in have.items():
        p = prev.get(k)
        if p:
            rows.append({**i, "Mode": p.get("Mode", dflt), "Partner": p.get("Partner", "")})
        elif k in sugg:
            rows.append({**i, "Mode": "pair", "Partner": sugg[k]})
        else:
            rows.append({**i, "Mode": dflt, "Partner": ""})
    return rows


def grouping_tables(rows):
    """choices -> (split rules for pairs, divided-lesson rows, problems [(level, subject, type, partner)])."""
    by = {(r["Level"], r["Subject"], r["Type"]): r for r in rows}
    done, rules, div, probs = set(), [], [], []
    for r in rows:
        k = (r["Level"], r["Subject"], r["Type"])
        if k in done or r["Mode"] not in ("pair", "pair_alt"):
            continue
        ps = str(r.get("Partner") or "").split()
        pk = (r["Level"], ps[0], ps[1]) if len(ps) == 2 else None
        p = by.get(pk) if pk else None
        if not p or pk in done or p["Hours"] != r["Hours"] or pk == k:
            probs.append((r["Level"], r["Subject"], r["Type"], r.get("Partner", "")))
            r = {**r, "Mode": "alt"}                     # falls back to alternate weeks
            by[k] = r
            continue
        f = 1 if r["Mode"] == "pair" else 2
        rules.append((f"G_{r['Level']}_{r['Subject']}_{p['Subject']}", r["Level"], r["Subject"], r["Type"], r["Hours"],
                      p["Subject"], p["Type"], str(r["Hours"]), f,
                      f"2 groups in parallel: {r['Subject']} {r['Type']} / {p['Subject']} {p['Type']}, swap "
                      + ("in the session" if f == 1 else "next week")))
        done |= {k, pk}
    for k, r in by.items():
        if k in done or r["Mode"] == "whole":
            continue
        mode = r["Mode"] if r["Mode"] in ("alt", "div") else "alt"
        div.append({"ID": f"D_{r['Level']}_{r['Subject']}_{r['Type']}", "Levels": r["Level"], "Subject": r["Subject"],
                    "Type": r["Type"], "Groups": "2", "Block": str(r["Hours"]) if mode == "alt" else "1",
                    "Weeks": "2" if mode == "alt" else "1"})
    return rules, div, probs


def teacher_hours(rows):
    """Weekly teacher hours created by one class for each (subject, type) choice."""
    out = {}
    for r in rows:
        h = int(r["Hours"])
        out[(r["Level"], r["Subject"], r["Type"])] = h if r["Mode"] in ("alt", "pair_alt", "whole") else 2 * h
    return out


# ------------------------------------------------------------------ files -> sections
def _records(df):
    return json.loads(df.to_json(orient="records", force_ascii=False))


def teachers_from_staff(df):
    return [{"Name": str(r["Teacher_ID"]), "Subject": str(r["Qualified_Subjects"]).split(";")[0].strip(),
             "Mumayaz": False, "Remedial": False,
             "Max": int(r["Max_Weekly_Hours"]) if pd.notna(r.get("Max_Weekly_Hours")) else None}
            for _, r in df.iterrows()]


def teachers_from_assign(p):
    a_ = p["assignment"]
    mx = dict(zip(p["teachers"]["Teacher_ID"], p["teachers"]["Max_Weekly_Hours"])) if "teachers" in p else {}
    rem = p.get("remedial") or {}
    out = []
    for n, g in a_.groupby("Teacher", sort=False):
        subj = g.groupby("Subject")["Hours"].sum().idxmax()
        out.append({"Name": str(n), "Subject": str(subj), "Mumayaz": False, "Remedial": int(rem.get(n, 0) or 0) > 0,
                    "Max": int(mx[n]) if n in mx and pd.notna(mx[n]) else int(g["Hours"].sum() + int(rem.get(n, 0) or 0))})
    return out


def is_filled(ss, a, k):
    """Text describing what already fills section k (file / manual assignment), or None."""
    f = file_of(a, k)
    if f:
        return t("wz_by_file", f=f.get("name", "?"))
    if k == "teachers" and file_of(a, "assign"):
        return t("wz_by_file", f=file_of(a, "assign").get("name", "?"))
    if k == "assign" and ss.get("wz_assign_touched"):
        return t("wz_by_manual")
    return None


def apply_item(ss, a, it):
    k, name = it["kind"], it["name"]
    files = a.setdefault("files", {})
    if k == "subjects":
        a["curriculum"] = _records(it["df"]); a["curriculum_name"] = name
    elif k in ("classes", "rooms", "rules", "inspections"):
        files[k] = {"name": name, "records": _records(it["df"])}
    elif k == "teachers":
        files["teachers"] = {"name": name, "records": None}
        ss["wz_teachers"] = teachers_from_staff(it["df"]); ss.pop("wz_assign", None); ss.pop("wz_assign_touched", None)
    elif k == "assign":
        p = it["assign"]
        files["assign"] = {"name": name, "records": None,
                           "hours": {f"{r.Class}|{r.Subject}": int(r.Hours) for r in p["assignment"].itertuples()},
                           "remedial": {str(k_): int(v) for k_, v in (p.get("remedial") or {}).items() if int(v or 0) > 0}}
        files["teachers"] = {"name": name, "records": None}
        ss["wz_teachers"] = teachers_from_assign(p)
        ss["wz_assign"] = {(r.Class, r.Subject): str(r.Teacher) for r in p["assignment"].itertuples()}
        ss.pop("wz_assign_touched", None)
    ss.pop("wz_counts", None) if k in ("teachers", "assign") else None


def remove_file(ss, a, k):
    files = a.setdefault("files", {})
    if k == "subjects":
        a.pop("curriculum", None); a.pop("curriculum_name", None)
    else:
        files.pop(k, None)
    if k in ("teachers", "assign"):
        files.pop("teachers", None); files.pop("assign", None)
        for x in ("wz_teachers", "wz_assign", "wz_counts", "wz_assign_touched"):
            ss.pop(x, None)


def handle_uploads(st, ss, a, files, frames, here=None):
    """Loaded files -> sections (confirmation first when a section is already filled)."""
    import importer
    items = importer.read_uploads(files, set(frames["subjects"]["Subject_Code"]), set(frames["classes"]["Class_ID"]))
    ok, batch = [], set()
    order = {k: i for i, k in enumerate(importer.KINDS)}          # staff before assignment (it defines teachers)
    for it in sorted(items, key=lambda x: order.get(x["kind"], 99)):
        if it["kind"] is None:
            st.error(t("wz_not_recog", f=it["name"], e=it.get("error") or "?")); continue
        same_batch = it["kind"] in batch or (it["kind"] == "assign" and "teachers" in batch)
        batch.add(it["kind"])
        if is_filled(ss, a, it["kind"]) and not same_batch:
            ss.setdefault("wz_pending", []).append(it); continue
        apply_item(ss, a, it); ok.append(it)
    for it in ok:
        sec = t("wz_sec_" + it["kind"])
        step_i = STEPS.index(STEP_OF[it["kind"]]) + 1
        ss.setdefault("wz_msgs", []).append(t("wz_filled_here", f=it["name"], s=sec) if STEP_OF[it["kind"]] == here
                                            else t("wz_filled_other", f=it["name"], s=sec, i=step_i))
    ss["wz_val"] = [(it["name"], it["kind"], it["df"]) for it in ok if it.get("df") is not None]
    return items


def _uploader(st, ss, a, frames, key, label, here=None, help_=None):
    ups = st.file_uploader(label, type=["csv", "xlsx", "xls", "zip"], accept_multiple_files=True, key=key, help=help_)
    seen = ss.setdefault("wz_up_seen", {})
    new = [u for u in ups or [] if seen.get(f"{key}:{u.name}") != u.size]
    if new:
        for u in new:
            seen[f"{key}:{u.name}"] = u.size
        handle_uploads(st, ss, a, new, frames, here)
        st.rerun()


def _pending(st, ss, a):
    """Confirmation for files that would overwrite a filled section."""
    pend = ss.get("wz_pending") or []
    if not pend:
        return
    it = pend[0]
    with st.container(border=True):
        st.warning(t("wz_confirm_over", s=t("wz_sec_" + it["kind"]), o=is_filled(ss, a, it["kind"]) or "—", f=it["name"]))
        c1, c2, _ = st.columns([1, 1, 3])
        if c1.button(t("wz_replace"), key="wz_pend_yes", type="primary"):
            apply_item(ss, a, it); pend.pop(0)
            ss.setdefault("wz_msgs", []).append(t("wz_filled_here", f=it["name"], s=t("wz_sec_" + it["kind"])))
            st.rerun()
        if c2.button(t("wz_keep"), key="wz_pend_no"):
            pend.pop(0); st.rerun()


def _file_banner(st, ss, a, k):
    """'from file' banner of a section with the button back to manual creation.  True when file-backed."""
    f = file_of(a, k)
    if not f:
        return False
    n = len(f["records"]) if f.get("records") is not None else (len(ss.get("wz_teachers") or []) if k == "teachers"
                                                               else len(f.get("hours", {})))
    c1, c2 = st.columns([4, 1])
    c1.info(t("wz_from_file", s=t("wz_sec_" + k), f=f.get("name", "?"), n=n))
    if c2.button(t("wz_manual_btn"), key=f"wz_manual_{k}", width="stretch"):
        remove_file(ss, a, k); st.rerun()
    return True


def _bulk_panel(st, ss, a, frames):
    import curriculum as curr
    with st.container(border=True):
        st.markdown(f"#### {t('wz_bulk_title')}")
        _uploader(st, ss, a, frames, "wz_bulk", t("wz_bulk_help"))
        have = [k for k in ["classes", "subjects", "rooms", "rules", "teachers", "inspections", "assign"] if file_of(a, k)]
        miss = [k for k in ["classes", "rooms", "rules", "teachers", "inspections", "assign"] if k not in have]
        sep = "، " if i18n.is_ar() else ", "
        st.caption(t("wz_bulk_state", a=sep.join(t("wz_sec_" + k) for k in have) or "—",
                     b=sep.join(t("wz_sec_" + k) for k in miss) or "—")
                   + ("" if file_of(a, "subjects") else "  ·  📘 " + curr.label()))
        import os as _os
        sample = _os.path.join(_os.path.dirname(BASE_CURRICULUM))
        import presets as _pr
        tpl = {"classes": pd.read_csv(_os.path.join(sample, "classes.csv"))}
        tpl.update(_pr.default_frames())
        c1, c2, _ = st.columns([1, 1, 2])
        c1.download_button(t("tpl_csv"), dl.to_zip(tpl), f"{t('tpl_name')}_csv.zip", "application/zip", width="stretch",
                           key="wz_tpl_csv")
        c2.download_button(t("tpl_xlsx"), dl.to_zip(tpl, fmt="xlsx"), f"{t('tpl_name')}_xlsx.zip", "application/zip",
                           width="stretch", key="wz_tpl_xlsx")


_REQ_CACHE = {}


def needed_hours(frames):
    """Class × subject teacher hours (engine rules), one row per pair (memoised: it runs on every click)."""
    import presets as _pr
    key = _pr.CURRENT_ID + "|".join(frames[k].to_csv(index=False) for k in ("classes", "subjects", "rules", "divided")
                                    if frames.get(k) is not None)
    if key not in _REQ_CACHE:
        if len(_REQ_CACHE) > 20:
            _REQ_CACHE.clear()
        _REQ_CACHE[key] = _families(ap.required_hours(ap.make_loader(frames)))
    return _REQ_CACHE[key].copy()


def family_of():
    """{subject: teacher post subject} from the preset (one post teaches several subjects)."""
    import presets as _pr
    return {s: f for f, ss in (_pr.load().get("teacher_families") or {}).items() for s in ss}


def _families(req):
    fam = family_of()
    if not fam or req.empty:
        return req
    r = req.copy()
    r["Parts"] = [f"{s}:{h}" for s, h in zip(r["Subject"], r["Hours"])]
    r["Subject"] = r["Subject"].map(lambda s: fam.get(s, s))
    agg = r.groupby(["Class", "Subject"], sort=False).agg(Hours=("Hours", "sum"), Parts=("Parts", ";".join)).reset_index()
    extra = [c for c in req.columns if c not in ("Class", "Subject", "Hours")]
    for c in extra:                                    # keep the other columns (first value)
        agg[c] = r.groupby(["Class", "Subject"], sort=False)[c].first().values
    return agg


def suggest_counts(req, a, prev=None):
    """Per subject: hours needed, teachers suggested (keeps the manager's previous choices)."""
    prev = {r["Subject"]: r for r in (prev or [])}
    rows = []
    for s, h in req.groupby("Subject")["Hours"].sum().items():
        rem = a["rem_hours"] if s in ("ARABIC", "MATH", "FRENCH") else 0
        p = prev.get(s)
        if not p:
            import presets as _pr
            tc = (a.get("teacher_counts") or {}).get(s) or \
                (None if a.get("teacher_counts") else (_pr.load().get("wizard", {}).get("teacher_counts") or {}).get(s))
            if tc:
                p = {"n": tc[0], "mum": tc[1] if len(tc) > 1 else 0, "rem": False}
            elif a.get("teacher_counts"):               # staff file given: no teacher of this subject
                p = {"n": 0, "mum": 0, "rem": False}
        n = int(p["n"]) if p else _min_teachers(req[req["Subject"] == s], a["base_hours"] - rem)
        rows.append({"Subject": s, "Needed": int(h), "n": n, "mum": int(p["mum"]) if p else 0,
                     "rem": bool(p["rem"]) if p else bool(rem)})
    return rows


def _min_teachers(g, cap):
    """Smallest number of teachers (load `cap`) that can hold every class of the subject (classes are not split)."""
    hrs = sorted(g["Hours"].astype(int), reverse=True)
    n = max(1, math.ceil(sum(hrs) / cap))
    while n < len(hrs):
        bins = [0] * n                      # first-fit decreasing, then exact check if it fails
        if all(_place(bins, h, cap) for h in hrs):
            return n
        fake = [{"Name": str(k), "Subject": "X", "Mumayaz": False, "Remedial": False} for k in range(n)]
        gg = g.assign(Subject="X")
        if all(auto_assign(gg, fake, {"base_hours": cap, "mumayaz_less": 0, "rem_hours": 0}, 2).values()):
            return n
        n += 1
    return n


def _place(bins, h, cap):
    for k, b in enumerate(bins):
        if b + h <= cap:
            bins[k] += h
            return True
    return False


def make_teachers(counts, a):
    rows = []
    for r in counts:
        for k in range(1, int(r["n"]) + 1):
            rows.append({"Name": ap.post_label(r["Subject"], k), "Subject": r["Subject"],
                         "Mumayaz": k <= int(r["mum"]), "Remedial": bool(r["rem"])})
    return rows


def load_of(tr, a):
    """Teaching capacity (hours of classes) of one teacher row."""
    full = int(tr["Max"]) if tr.get("Max") else \
        int(a["base_hours"]) - (int(a["mumayaz_less"]) if tr["Mumayaz"] else 0)
    return full, full - (int(a["rem_hours"]) if tr["Remedial"] else 0)


def capacity_by_subject(teachers, a):
    cap = {}
    for tr in teachers:
        cap[tr["Subject"]] = cap.get(tr["Subject"], 0) + load_of(tr, a)[1]
    return cap


def auto_assign(req, teachers, a, time_limit=3):
    """Per subject, a small CP-SAT: assign as many hours as possible within each teacher's load, then keep
    each teacher on few levels, then balance.  Returns {(class, subject): teacher name or None}."""
    from ortools.sat.python import cp_model
    out = {}
    for s, g in req.groupby("Subject"):
        ts = [tr for tr in teachers if tr["Subject"] == s]
        items = sorted(g.itertuples(), key=lambda r: (r.Level, ap._class_key(r.Class)))
        if not ts:
            out.update({(r.Class, s): None for r in items}); continue
        m = cp_model.CpModel()
        x = {(i, p): m.NewBoolVar("") for i in range(len(items)) for p in range(len(ts))}
        for i in range(len(items)):
            m.Add(sum(x[i, p] for p in range(len(ts))) <= 1)
        levels = sorted({r.Level for r in items})
        y = {(p, l): m.NewBoolVar("") for p in range(len(ts)) for l in levels}
        for p, tr in enumerate(ts):
            m.Add(sum(x[i, p] * r.Hours for i, r in enumerate(items)) <= load_of(tr, a)[1])
            for i, r in enumerate(items):
                m.AddImplication(x[i, p], y[p, r.Level])
        done = sum(x[i, p] * r.Hours for i, r in enumerate(items) for p in range(len(ts)))
        m.Maximize(done * 1000 - sum(y.values()) * 10)
        sv = cp_model.CpSolver(); sv.parameters.max_time_in_seconds = time_limit; sv.parameters.num_workers = 2
        st_ = sv.Solve(m)
        for i, r in enumerate(items):
            who = None
            if st_ in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                who = next((ts[p]["Name"] for p in range(len(ts)) if sv.Value(x[i, p])), None)
            out[(r.Class, s)] = who
    return out


def status(req, assign, teachers, a):
    hours = {(r.Class, r.Subject): int(r.Hours) for r in req.itertuples()}
    un = [(k, h) for k, h in hours.items() if not assign.get(k)]
    tot = {}
    for k, n in assign.items():
        if n:
            tot[n] = tot.get(n, 0) + hours.get(k, 0)
    over = [(tr["Name"], tot.get(tr["Name"], 0), load_of(tr, a)[1]) for tr in teachers
            if tot.get(tr["Name"], 0) > load_of(tr, a)[1]]
    return un, over, tot


def to_plan(req, assign, teachers, a):
    hours = {(r.Class, r.Subject): int(r.Hours) for r in req.itertuples()}
    fa = file_of(a, "assign")
    if fa:                                   # hours of the school file (differences are corrected later)
        for k_, h_ in fa.get("hours", {}).items():
            c_, s_ = k_.split("|", 1)
            if (c_, s_) in hours:
                hours[(c_, s_)] = int(h_)
    parts = {(r.Class, r.Subject): r.Parts for r in req.itertuples()} if "Parts" in req.columns else {}
    rows = []
    for (c, s), n in assign.items():
        if not n or (c, s) not in hours:
            continue
        pr = parts.get((c, s))
        if isinstance(pr, str) and pr:                 # a teacher post covering several subjects -> real subjects
            for it in pr.split(";"):
                s_, h_ = it.rsplit(":", 1)
                rows.append({"Teacher": n, "Post": n, "Class": c, "Subject": s_, "Hours": int(h_)})
        else:
            rows.append({"Teacher": n, "Post": n, "Class": c, "Subject": s, "Hours": hours[(c, s)]})
    by = {tr["Name"]: tr for tr in teachers}
    used = {r["Teacher"] for r in rows}
    rem = {n: int(a["rem_hours"]) for n in used if by[n]["Remedial"] and int(a["rem_hours"]) > 0}
    if fa and fa.get("remedial"):
        rem = {n: int(h) for n, h in fa["remedial"].items() if n in used}
    mx = {n: load_of(by[n], a)[0] for n in used}
    plan = ap.finalize(pd.DataFrame(rows), remedial=rem, max_hours=mx)
    plan["mumayaz"] = [n for n in used if by[n]["Mumayaz"]]
    return plan


def save_project(frames, plan, a, teachers, db, ws):
    db.save_project(ws, {"frames": {k: frames[k].to_csv(index=False) for k in FRAME_KEYS},
                         "assignment": plan["assignment"].to_csv(index=False),
                         "answers": a, "teachers": teachers, "remedial": plan["remedial"],
                         "max_hours": plan["max_hours"]})


FRAME_KEYS = ["classes", "subjects", "rooms", "rules", "inspections"]


def load_project(db, ws):
    import io
    meta, stamp = db.load_project(ws)
    if not meta:
        return None
    frames = {k: pd.read_csv(io.StringIO(meta["frames"][k])) for k in FRAME_KEYS}
    plan = ap.finalize(pd.read_csv(io.StringIO(meta["assignment"])), remedial=meta["remedial"],
                       max_hours=meta["max_hours"])
    return {"frames": frames, "plan": plan, "answers": meta["answers"], "teachers": meta["teachers"], "stamp": stamp}


# ------------------------------------------------------------------ Streamlit pages
def render(st, dnd_assign, db=None, ws="demo", bulk=False):
    """Draw the guide in the main area.  Returns True when the manager applied the result.
    bulk=True (Upload mode): a panel on top loads all the files at once; the steps are filled from them."""
    ss = st.session_state
    a = _ans(ss)
    step = ss.setdefault("wz_step", 0)
    st.subheader(t("wz_title"))
    st.caption(t("wz_intro") + " " + t("wz_intro_files"))
    for m_ in ss.pop("wz_msgs", []):
        st.toast(m_, icon="📄")
    if bulk:
        _bulk_panel(st, ss, a, build_frames(a))
    _pending(st, ss, a)
    if ss.get("wz_val"):
        import validate
        viss = validate.check_all(ss["wz_val"], build_frames(a))
        nv = sum(len(v_) for v_ in viss.values())
        if nv:
            with st.expander(f"{validate.t('v_title')} ({nv})", expanded=True):
                for fn_, lst_ in viss.items():
                    for ln_, msg_ in lst_[:60]:
                        st.markdown(f"- **{fn_}** · {t('v_line', n=ln_)}: {msg_}")
    labels = [t("wz_s_" + s) for s in STEPS]
    st.progress((step + 1) / len(STEPS), text=t("wz_step", i=step + 1, n=len(STEPS)) + " · " + labels[step])
    cols = st.columns(len(STEPS))
    for i, (c, lab) in enumerate(zip(cols, labels)):
        from_file = any(file_of(a, k) for k, s_ in STEP_OF.items() if s_ == STEPS[i])
        if c.button(("● " if i == step else "") + f"{i + 1}. {lab}" + (" 📄" if from_file else ""), key=f"wz_nav{i}",
                    width="stretch",
                    type="primary" if i == step else "secondary"):
            ss["wz_step"] = i; st.rerun()
    st.divider()

    frames = build_frames(a)
    can_next = True
    name = STEPS[step]
    if name != "finish":
        with st.expander(t("wz_step_upload"), expanded=False):
            _uploader(st, ss, a, frames, f"wz_up_{name}", t("wz_step_upload"), here=name)
    if name == "levels":
        _step_levels(st, a)
    elif name == "subjects":
        _step_subjects(st, a, frames)
    elif name == "grouping":
        _step_grouping(st, a, frames)
    elif name == "teachers":
        can_next = _step_teachers(st, ss, a, frames)
    elif name == "windows":
        _step_windows(st, a, frames)
    elif name == "assign":
        can_next = _step_assign(st, ss, a, frames, dnd_assign)
    else:
        return _step_finish(st, ss, a, frames, db, ws)

    st.divider()
    b1, _, b2 = st.columns([1, 3, 1])
    if step > 0 and b1.button(t("wz_prev"), key="wz_prev", width="stretch"):
        ss["wz_step"] = step - 1; st.rerun()
    if b2.button(t("wz_next"), key="wz_next", type="primary", width="stretch", disabled=not can_next):
        ss["wz_step"] = step + 1; st.rerun()
    return False


def _zip_with_assignment(files, plan):
    """Data files + the assignment in the school format -> one zip that the Upload mode accepts as is."""
    import io, zipfile
    from assignment_matrix import build_matrix_xlsx
    buf = io.BytesIO(dl.to_zip(files))
    xl = build_matrix_xlsx(plan["assignment"], None, {}, remedial=plan.get("remedial", {}))
    with zipfile.ZipFile(buf, "a") as z:
        z.writestr("الإسناد.xlsx" if i18n.is_ar() else "assignment.xlsx", xl if isinstance(xl, bytes) else xl.getvalue())
    return buf.getvalue()


def _curriculum_box(st, a):
    """Approved curriculum by default; the school may replace it by its own file (or go back)."""
    import curriculum as curr
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        if a.get("curriculum"):
            c1.markdown(t("curr_using_custom", y=curr.YEAR) + f" («{a.get('curriculum_name', '?')}»)")
            if c2.button(t("curr_revert"), key="wz_curr_revert"):
                a.pop("curriculum", None); a.pop("curriculum_name", None); st.rerun()
        else:
            c1.markdown(t("curr_using_approved", y=curr.YEAR))
            c2.download_button(t("curr_download"), curr.approved_bytes(), f"{curr.label()}.csv".replace("/", "-"),
                               "text/csv", key="wz_curr_dl", width="stretch")


def _step_levels(st, a):
    ss = st.session_state
    _curriculum_box(st, a)
    if _file_banner(st, ss, a, "classes"):
        cl = build_frames(a)["classes"]
        st.caption(" · ".join(f"{l}: {n}" for l, n in cl.groupby("Level").size().items()))
        return
    with st.expander(t("wz_struct"), expanded=False):
        st.caption(t("wz_struct_help"))
        c1, c2 = st.columns(2)
        c1.markdown("**" + t("wz_years") + "**")
        yd = c1.data_editor(pd.DataFrame(a["years"], columns=["id", "en", "ar"]), num_rows="dynamic", width="stretch",
                            key="wz_years_ed", column_config={"id": "ID", "en": "English", "ar": "العربية"})
        c2.markdown("**" + t("wz_tracks") + "**")
        td = c2.data_editor(pd.DataFrame([{**x, "years": ";".join(x.get("years", []))} for x in a["tracks"]],
                                         columns=["id", "en", "ar", "years"]), num_rows="dynamic", width="stretch",
                            key="wz_tracks_ed", column_config={"id": "ID", "en": "English", "ar": "العربية",
                                                               "years": st.column_config.TextColumn(t("wz_track_years"))})
        if st.button(t("wz_struct_apply"), key="wz_struct_ok", type="primary"):
            a["years"] = [{"id": str(r["id"]).strip(), "en": str(r.get("en") or r["id"]), "ar": str(r.get("ar") or r["id"])}
                          for r in yd.fillna("").to_dict("records") if str(r["id"]).strip()]
            a["tracks"] = [{"id": str(r["id"]).strip(), "en": str(r.get("en") or r["id"]), "ar": str(r.get("ar") or r["id"]),
                            "years": [x.strip() for x in str(r.get("years", "")).replace(",", ";").split(";") if x.strip()]}
                           for r in td.fillna("").to_dict("records") if str(r["id"]).strip()]
            st.rerun()
    if not a.get("msq", True):
        _school_files(st, a)
    st.subheader(t("wz_q_levels"))
    keys = level_keys(a)
    lang = "ar" if i18n.is_ar() else "en"
    for y in a.get("years", []):                         # one block per level, its streams side by side
        ks = [(k, tr) for k, y_, tr in levels_of(a) if y_ == y["id"]]
        st.markdown(f"**{y.get(lang) or y['id']}**")
        cols = st.columns(min(4, max(1, len(ks))))
        for i, (k, tr) in enumerate(ks):
            lab = next((x.get(lang) or x["id"] for x in a.get("tracks", []) if x["id"] == tr), "") if tr else t("wz_classes_n")
            a["levels"][k] = int(cols[i % len(cols)].number_input(lab, 0, 30, int(a["levels"].get(k, 0)), key=f"wz_lv_{k}"))
    st.info(t("wz_total_classes", n=sum(int(a["levels"].get(l, 0)) for l in keys)))
    _staff_check(st, a)


def _school_files(st, a):
    """Classes file + staff file of the school: counts detected, unrecognised rows asked with a dropdown."""
    import presets as _pr
    import school_files as sf
    ss = st.session_state
    P = _pr.load()
    st.subheader(t("wz_sf_title"))
    st.caption(t("wz_sf_help"))
    c1, c2 = st.columns(2)
    fc = c1.file_uploader(t("wz_sf_classes"), type=["xlsx", "xls", "csv"], key="wz_sf_cls")
    fs = c2.file_uploader(t("wz_sf_staff"), type=["xlsx", "xls", "csv"], key="wz_sf_stf")
    if fc is not None and a.get("cls_file") != (fc.name, fc.size):
        counts, probs = sf.read_classes(fc, P)
        a["cls_file"], a["cls_counts"], a["cls_probs"] = (fc.name, fc.size), counts, probs
        a["cls_fix"] = {}
        _apply_class_counts(ss, a)
    if fs is not None and a.get("stf_file") != (fs.name, fs.size):
        cnt, probs = sf.read_staff(fs, P)
        a["stf_file"], a["stf_counts"], a["stf_probs"] = (fs.name, fs.size), cnt, probs
        a["stf_fix"] = {}
        _apply_staff_counts(ss, a)
    if a.get("cls_file"):
        lang = "ar" if i18n.is_ar() else "en"
        tr_name = {x["id"]: x.get(lang) or x["id"] for x in a.get("tracks", [])}
        for p_ in a.get("cls_probs") or []:
            ch = p_.get("choices") or [tr for k, y_, tr in levels_of(a) if y_ == p_.get("year") and tr]
            if not ch:
                st.warning(t("wz_sf_unknown", r=p_["row"], x=p_["text"]))
                continue
            k_ = str(p_["row"])
            cur = a["cls_fix"].get(k_, p_.get("guess") or ch[0])
            new = st.selectbox(t("wz_sf_which", x=p_["text"], n=p_["n"]), ch, index=ch.index(cur) if cur in ch else 0,
                               key=f"wz_sf_fix_{k_}", format_func=lambda x: tr_name.get(x, x))
            if new != a["cls_fix"].get(k_):
                a["cls_fix"][k_] = new
                _apply_class_counts(ss, a)
                st.rerun()
        st.success(t("wz_sf_cls_ok", f=a["cls_file"][0], n=sum(a["cls_counts"].values()) +
                     sum(p_["n"] for p_ in a.get("cls_probs") or [] if str(p_["row"]) in a["cls_fix"])))
    if a.get("stf_file"):
        codes = [x["id"] for x in P.get("subjects", [])]
        for p_ in a.get("stf_probs") or []:
            k_ = str(p_["row"])
            new = st.selectbox(t("wz_sf_subj", x=p_["text"]), ["—"] + codes, key=f"wz_sf_sfix_{k_}",
                               format_func=lambda x: x if x == "—" else i18n.subj(x))
            if new != "—" and new != a["stf_fix"].get(k_):
                a["stf_fix"][k_] = new
                _apply_staff_counts(ss, a)
                st.rerun()
        tc = a.get("teacher_counts") or {}
        R_, D_ = sum(v[0] - v[1] for v in tc.values()), sum(v[1] for v in tc.values())
        st.success(t("wz_sf_stf_ok", f=a["stf_file"][0], n=R_ + D_, r=R_, d=D_))


def _apply_class_counts(ss, a):
    lv = {k: 0 for k in level_keys(a)}
    for k, n in (a.get("cls_counts") or {}).items():
        lv[k] = lv.get(k, 0) + n
    for p_ in a.get("cls_probs") or []:
        ch = a.get("cls_fix", {}).get(str(p_["row"])) or p_.get("guess")
        if ch and p_.get("year"):
            lv[f"{p_['year']}-{ch}"] = lv.get(f"{p_['year']}-{ch}", 0) + p_["n"]
    a["levels"] = lv
    for k, n in lv.items():                              # prefill the number fields (set before they are drawn)
        ss[f"wz_lv_{k}"] = int(n)


def _apply_staff_counts(ss, a):
    tc = {k: [r + d, d] for k, (r, d) in (a.get("stf_counts") or {}).items()}     # [total, distinguished]
    for p_ in a.get("stf_probs") or []:
        code = a.get("stf_fix", {}).get(str(p_["row"]))
        if code:
            r, d = (p_["nums"] + [0, 0])[:2]
            o = tc.get(code, [0, 0]); tc[code] = [o[0] + r + d, o[1] + d]
    a["teacher_counts"] = tc
    ss.pop("wz_counts", None); ss.pop("wz_teachers", None); ss.pop("wz_assign", None)


def _staff_check(st, a):
    """Streams whose subjects have no teacher at all (e.g. a 3rd language or an engineering option)."""
    tc = a.get("teacher_counts")
    if not tc:
        return
    fam = family_of()
    import presets as _pr
    cur = _pr.curriculum_df()
    miss = {}
    for k in level_keys(a):
        if int(a["levels"].get(k, 0)) <= 0:
            continue
        for sj in cur[cur["Level"] == k]["Subject_Code"]:
            post = fam.get(sj, sj)
            if int((tc.get(post) or [0])[0]) <= 0:
                miss.setdefault(post, []).append(level_label(a, k))
    for post, lvs in miss.items():
        st.warning(t("wz_sf_noteacher", s=i18n.subj(post), l=", ".join(lvs)))


def _step_subjects(st, a, frames):
    ss = st.session_state
    cur_file = bool(a.get("curriculum"))
    if cur_file:
        st.info(t("wz_from_file", s=t("wz_sec_subjects"), f=a.get("curriculum_name", "?"), n=len(a["curriculum"])))
    elif a.get("msq", True):
        _optional_subjects(st, a)
    if not _file_banner(st, ss, a, "rooms"):
        _rooms_questions(st, a)
    if not (cur_file and file_of(a, "rules")) and a.get("msq", True):
        _it_questions(st, a)
    frames = build_frames(a)
    with st.expander(t("wz_curr_preview")):
        cur = frames["subjects"].copy()
        cur["Total"] = cur[["Hrs_Cours", "Hrs_TD", "Hrs_TP", "Hrs_Practice"]].sum(axis=1)
        piv = cur.pivot_table(index="Subject_Code", columns="Level", values="Total", aggfunc="sum").fillna(0).astype(int)
        piv.index = [i18n.subj(s) for s in piv.index]
        piv.columns = [level_label(a, c) for c in piv.columns]
        piv.loc["Σ"] = piv.sum()
        st.dataframe(piv, width="stretch")
    with st.expander(t("wz_cur_edit")):
        ce = st.data_editor(frames["subjects"], num_rows="dynamic", width="stretch", key="wz_cur_ed")
        if st.button(t("wz_cur_use"), key="wz_cur_use", type="primary"):
            a["curriculum"] = json.loads(ce.to_json(orient="records", force_ascii=False))
            a["curriculum_name"] = t("wz_cur_edited")
            st.rerun()


def _optional_subjects(st, a):
    st.subheader(t("wz_q_optional"))
    c1, c2 = st.columns(2)
    a["amazigh"] = c1.checkbox(t("wz_amazigh"), a["amazigh"], key="wz_amz")
    if a["amazigh"]:
        a["amazigh_h"] = int(c1.number_input(t("wz_hours_week"), 1, 5, int(a["amazigh_h"]), key="wz_amz_h"))
    opts = ["none", "music", "art", "both"]
    a["arts"] = c2.radio(t("wz_arts"), opts, opts.index(a["arts"]), key="wz_arts", horizontal=True,
                         format_func=lambda x: t("wz_arts_" + x))
    if a["arts"] in ("music", "both"):
        a["music_h"] = int(c2.number_input(i18n.subj("MUSIC") + " – " + t("wz_hours_week"), 1, 3, int(a["music_h"]), key="wz_mus_h"))
    if a["arts"] in ("art", "both"):
        a["art_h"] = int(c2.number_input(i18n.subj("ART") + " – " + t("wz_hours_week"), 1, 3, int(a["art_h"]), key="wz_art_h"))


def _rooms_questions(st, a):
    st.subheader(t("wz_q_rooms"))
    c1, c2, c3 = st.columns(3)
    a["classrooms"] = int(c1.number_input(t("wz_classrooms"), 1, 80, int(a["classrooms"]), key="wz_cr"))
    a["labs"] = c2.radio(t("wz_labs"), ["dedicated", "class"], ["dedicated", "class"].index(a["labs"]), key="wz_labs",
                         format_func=lambda x: t("wz_labs_" + x))
    if a["labs"] == "dedicated":
        a["n_labs"] = int(c2.number_input(t("wz_n_labs"), 1, 20, int(a["n_labs"]), key="wz_nlabs"))
    a["sport_cap"] = int(c3.number_input(t("wz_sport"), 1, 10, int(a["sport_cap"]), key="wz_sport"))


def _it_questions(st, a):
    st.subheader(t("wz_q_it"))
    c1, c2, c3 = st.columns(3)
    _K = level_keys(a)
    a["info_levels"] = c1.multiselect(t("wz_info_levels"), _K, [l for l in a["info_levels"] if l in _K], key="wz_infol",
                                      format_func=lambda k: level_label(a, k))
    if a["info_levels"]:
        a["it_rooms"] = int(c2.number_input(t("wz_it_rooms"), 1, 10, int(a["it_rooms"]), key="wz_itr"))
        a["it_mode"] = c3.radio(t("wz_it_mode"), ["full", "half_lang"], ["full", "half_lang"].index(a["it_mode"]),
                                key="wz_itm", format_func=lambda x: t("wz_it_full") if x == "full" else t("wz_it_half"))


def _step_grouping(st, a, frames):
    ss = st.session_state
    if _file_banner(st, ss, a, "rules"):
        st.subheader(t("wz_rem_title"))
        a["rem_armath"] = st.checkbox(t("wz_rem_armath"), a["rem_armath"], key="wz_rem")
        _rules_preview(st, build_frames(a))
        return
    if not a.get("msq", True):
        _grouping_ui(st, a)
        return
    st.subheader(t("wz_q_grouping"))
    a["g_armath"] = st.checkbox(t("wz_g_armath"), a["g_armath"], key="wz_gam", help=t("wz_g_armath_h"))
    a["g_physsci"] = st.checkbox(t("wz_g_physsci"), a["g_physsci"], key="wz_gps")
    no_info = [level_label(a, l) for l in level_keys(a) if l not in a["info_levels"] and a["levels"].get(l, 0)]
    if no_info:
        a["g_lang34"] = st.checkbox(t("wz_g_lang34") + f" ({', '.join(no_info)})", a["g_lang34"], key="wz_gl")
    if a["info_levels"] and a["it_mode"] == "half_lang":
        st.caption("✔ " + t("wz_it_half") + f" ({', '.join(a['info_levels'])})")
    st.subheader(t("wz_rem_title"))
    a["rem_armath"] = st.checkbox(t("wz_rem_armath"), a["rem_armath"], key="wz_rem")
    _rules_preview(st, build_frames(a))


def _grouping_ui(st, a):
    """Every TD/TP is taught in 2 groups; one choice per subject and type (all levels), per level only if needed."""
    st.subheader(t("wz_g_title"))
    st.caption(t("wz_g_help"))
    fr = build_frames(a)
    active = list(dict.fromkeys(fr["classes"]["Level"].astype(str)))
    rows = grouping_rows(a, fr["subjects"], active)
    if not rows:
        st.info(t("wz_g_none"))
        return
    mode_fmt = lambda m: t("wz_g_m_" + m)
    # ---- one row per (subject, type): the choice of the majority of its levels
    keys = list(dict.fromkeys((r["Subject"], r["Type"]) for r in rows))
    opts = [""] + [f"{s_} {t_}" for s_, t_ in keys]
    summ = []
    for s_, t_ in keys:
        rs = [r for r in rows if (r["Subject"], r["Type"]) == (s_, t_)]
        modes = [r["Mode"] for r in rs]
        m = max(set(modes), key=modes.count)
        parts = [r["Partner"] for r in rs if r["Mode"] == m and r["Partner"]]
        hs = sorted({int(r["Hours"]) for r in rs})
        summ.append({"Subject": s_, "Type": t_, "Name": i18n.subj(s_), "Hours": "/".join(map(str, hs)),
                     "Levels": len(rs), "Mode": mode_fmt(m), "Partner": max(set(parts), key=parts.count) if parts else "",
                     "Mixed": "✱" if len(set(modes)) > 1 else ""})
    df = pd.DataFrame(summ)
    labels = [mode_fmt(m) for m in GROUP_MODES]
    ed = st.data_editor(df[["Name", "Type", "Hours", "Levels", "Mode", "Partner", "Mixed"]], hide_index=True, width="stretch",
                        key="wz_g_ed_all", disabled=["Name", "Type", "Hours", "Levels", "Mixed"],
                        column_config={"Name": st.column_config.TextColumn(t("wz_c_subject")),
                                       "Hours": st.column_config.TextColumn(t("wz_g_c_hours")),
                                       "Levels": st.column_config.NumberColumn(t("wz_g_c_levels")),
                                       "Mode": st.column_config.SelectboxColumn(t("wz_g_c_mode"), options=labels, required=True),
                                       "Partner": st.column_config.SelectboxColumn(t("wz_g_c_partner"), options=opts),
                                       "Mixed": st.column_config.TextColumn("✱", help=t("wz_g_mixed"))})
    back = {mode_fmt(m): m for m in GROUP_MODES}
    for (o, (_, e)) in zip(summ, ed.iterrows()):
        nm, np_ = back.get(e["Mode"], "alt"), e["Partner"] or ""
        if nm != back.get(o["Mode"]) or np_ != o["Partner"]:      # changed here -> applies to every level
            for r in rows:
                if (r["Subject"], r["Type"]) == (o["Subject"], o["Type"]):
                    r["Mode"], r["Partner"] = nm, np_
    # ---- per level (only when needed)
    with st.expander(t("wz_g_per_level")):
        lv = st.selectbox(t("wz_g_level"), active, key="wz_g_lv", format_func=lambda x: level_label(a, x))
        shown = [r for r in rows if r["Level"] == lv]
        d2 = pd.DataFrame(shown)
        d2["Name"] = [i18n.subj(x) for x in d2["Subject"]]
        d2["Mode"] = [mode_fmt(m) for m in d2["Mode"]]
        e2 = st.data_editor(d2[["Name", "Type", "Hours", "Mode", "Partner"]], hide_index=True, width="stretch",
                            key=f"wz_g_ed_{lv}", disabled=["Name", "Type", "Hours"],
                            column_config={"Name": st.column_config.TextColumn(t("wz_c_subject")),
                                           "Hours": st.column_config.NumberColumn(t("wz_g_c_hours")),
                                           "Mode": st.column_config.SelectboxColumn(t("wz_g_c_mode"), options=labels, required=True),
                                           "Partner": st.column_config.SelectboxColumn(t("wz_g_c_partner"), options=opts)})
        for r, (_, e) in zip(shown, e2.iterrows()):
            r["Mode"], r["Partner"] = back.get(e["Mode"], r["Mode"]), e["Partner"] or ""
    a["grouping"] = rows
    rules, div, probs = grouping_tables(rows)
    for lv_, s_, t_, p_ in probs:
        st.warning(t("wz_g_bad", l=level_label(a, lv_), s=i18n.subj(s_), ty=t_, p=p_ or "—"))
    st.info(t("wz_g_sum2", p=len(rules), a=sum(1 for d in div if d["Weeks"] == "2"), d=sum(1 for d in div if d["Weeks"] == "1"),
              w=sum(1 for r in rows if r["Mode"] == "whole")))


def _rules_preview(st, frames):
    with st.expander(t("wz_rules_preview"), expanded=True):
        r = frames["rules"]
        if r.empty:
            st.caption("—")
        for _, x in r.iterrows():
            st.markdown(f"- **{x['Level'].replace(';', ', ')}** · {i18n.subj(x['Primary_Subject'])} ↔ "
                        f"{' / '.join(i18n.subj(s) for s in str(x['Secondary_Subject']).split(';'))} — {x.get('Description', '')}")


def _step_teachers(st, ss, a, frames):
    req = needed_hours(frames)
    if file_of(a, "teachers"):
        f = file_of(a, "teachers")
        c1, c2 = st.columns([4, 1])
        c1.info(t("wz_from_file", s=t("wz_sec_teachers"), f=f.get("name", "?"), n=len(ss.get("wz_teachers") or [])))
        if c2.button(t("wz_manual_btn"), key="wz_manual_teachers", width="stretch"):
            remove_file(ss, a, "teachers"); st.rerun()
        counts = suggest_counts(req, a)
        return _teacher_list(st, ss, a, counts, key="file")
    c1, c2, c3 = st.columns(3)
    a["base_hours"] = int(c1.number_input(t("wz_base_hours"), 10, 30, int(a["base_hours"]), key="wz_bh"))
    a["mumayaz_less"] = int(c2.number_input(t("wz_mumayaz_less"), 0, 6, int(a["mumayaz_less"]), key="wz_ml"))
    a["rem_hours"] = int(c3.number_input(t("wz_rem_hours"), 0, 3, int(a["rem_hours"]), key="wz_rh"))
    st.subheader(t("wz_q_teachers"))
    counts = suggest_counts(req, a, ss.get("wz_counts"))
    df = pd.DataFrame(counts)
    df["Name"] = [i18n.subj(s) for s in df["Subject"]]
    ed = st.data_editor(
        df[["Name", "Needed", "n", "mum", "rem"]], hide_index=True, width="stretch", key="wz_counts_ed",
        disabled=["Name", "Needed"],
        column_config={"Name": st.column_config.TextColumn(t("wz_c_subject")),
                       "Needed": st.column_config.NumberColumn(t("wz_c_needed")),
                       "n": st.column_config.NumberColumn(t("wz_c_n"), min_value=0, max_value=30, step=1),
                       "mum": st.column_config.NumberColumn(t("wz_c_mum"), min_value=0, max_value=30, step=1),
                       "rem": st.column_config.CheckboxColumn(t("wz_c_rem"))})
    counts = [{"Subject": s, "Needed": int(r["Needed"]), "n": int(r["n"] or 0), "mum": min(int(r["mum"] or 0), int(r["n"] or 0)),
               "rem": bool(r["rem"])} for s, (_, r) in zip(df["Subject"], ed.iterrows())]
    changed = [(c["Subject"], c["n"], c["mum"], c["rem"]) for c in counts] != \
              [(c["Subject"], c["n"], c["mum"], c["rem"]) for c in ss.get("wz_counts") or []]
    ss["wz_counts"] = counts
    if changed or "wz_teachers" not in ss:
        ss["wz_teachers"] = make_teachers(counts, a)
        ss.pop("wz_assign", None)
    return _teacher_list(st, ss, a, counts, key=hash(tuple((c['Subject'], c['n'], c['mum'], c['rem']) for c in counts)))


def _teacher_list(st, ss, a, counts, key):
    st.subheader(t("wz_teacher_list"))
    tl = pd.DataFrame(ss["wz_teachers"])
    tl["SubjName"] = [i18n.subj(s) for s in tl["Subject"]]
    tl["Max"] = [load_of(r, a)[0] for r in ss["wz_teachers"]]
    ed2 = st.data_editor(tl[["Name", "SubjName", "Mumayaz", "Remedial", "Max"]], hide_index=True, width="stretch",
                         key=f"wz_tl_{key}",
                         disabled=["SubjName", "Max"], height=min(600, 38 + 35 * len(tl)),
                         column_config={"Name": st.column_config.TextColumn(t("wz_c_name")),
                                        "SubjName": st.column_config.TextColumn(t("wz_c_subject")),
                                        "Mumayaz": st.column_config.CheckboxColumn("مميز"),
                                        "Remedial": st.column_config.CheckboxColumn(t("wz_c_rem")),
                                        "Max": st.column_config.NumberColumn(t("wz_c_max"))})
    new = [{"Name": str(r["Name"]).strip() or o["Name"], "Subject": o["Subject"], "Mumayaz": bool(r["Mumayaz"]),
            "Remedial": bool(r["Remedial"]), **({"Max": o["Max"]} if o.get("Max") else {})}
           for o, (_, r) in zip(ss["wz_teachers"], ed2.iterrows())]
    if [x["Name"] for x in new] != [x["Name"] for x in ss["wz_teachers"]] and "wz_assign" in ss:
        ren = {o["Name"]: n["Name"] for o, n in zip(ss["wz_teachers"], new)}
        ss["wz_assign"] = {k: ren.get(v, v) for k, v in ss["wz_assign"].items()}
    ss["wz_teachers"] = new
    _c1, _c2 = st.columns(2)                            # teacher list: download / load
    _c1.download_button(t("wz_tl_dl"), pd.DataFrame(new).to_csv(index=False).encode("utf-8-sig"), "teachers_list.csv",
                        "text/csv", key="wz_tl_dl", width="stretch")
    _up = _c2.file_uploader(t("wz_tl_up"), type=["csv", "xlsx"], key="wz_tl_up", label_visibility="collapsed")
    if _up is not None:
        _new = (pd.read_excel(_up, dtype=str) if _up.name.endswith("xlsx") else pd.read_csv(_up, dtype=str)).fillna("")
        if not {"Name", "Subject"} <= set(_new.columns):
            st.error(t("wz_tl_cols"))
        elif st.button(t("wz_tl_apply", n=len(_new)), key="wz_tl_ok"):
            yes = lambda v: str(v).strip().lower() in ("1", "true", "yes", "x", "نعم")
            ss["wz_teachers"] = [{"Name": r["Name"], "Subject": r["Subject"], "Mumayaz": yes(r.get("Mumayaz", "")),
                                  "Remedial": yes(r.get("Remedial", "")),
                                  **({"Max": int(float(r["Max"]))} if str(r.get("Max", "")).strip() not in ("", "nan") else {})}
                                 for r in _new.to_dict("records") if str(r["Name"]).strip()]
            ss.pop("wz_assign", None)
            st.rerun()
    names = [x["Name"] for x in new]
    if len(set(names)) != len(names):
        st.error("⛔ " + ", ".join(sorted({n for n in names if names.count(n) > 1})))
        return False
    cap = capacity_by_subject(new, a)
    for c in counts:
        miss = c["Needed"] - cap.get(c["Subject"], 0)
        if miss > 0:
            st.warning(t("wz_short", s=i18n.subj(c["Subject"]), h=miss))
    return True


def _step_windows(st, a, frames):
    st.info(t("wz_grid_info"))
    if _file_banner(st, st.session_state, a, "inspections"):
        w = frames["inspections"]
        st.dataframe(pd.DataFrame({t("wz_c_subject"): [i18n.subj(s) for s in w["Subject_Code"]],
                                   "📅": [i18n.day(int(d)) for d in w["Day_Index"]], "⏱": w["Blocked_Slots"].astype(str)}),
                     hide_index=True)
        return
    st.subheader(t("wz_q_windows"))
    subjects = list(dict.fromkeys(frames["subjects"]["Subject_Code"]))
    opts = [-1] + list(range(DAYS_N))
    cols = st.columns(3)
    for i, s in enumerate(subjects):
        cur = a["windows"].get(s, -1)
        cur = -1 if cur is None else int(cur)
        a["windows"][s] = cols[i % 3].selectbox(i18n.subj(s), opts, opts.index(cur), key=f"wz_win_{s}",
                                                format_func=lambda d: t("wz_no_window") if d < 0 else i18n.day(d))


def _payload(req, assign, teachers, a):
    items = [{"cls": r.Class, "label": i18n.cls(r.Class), "subject": r.Subject, "hours": int(r.Hours),
              "teacher": assign.get((r.Class, r.Subject))} for r in req.itertuples()]
    import colors
    subs = list(dict.fromkeys(req["Subject"]))
    return {"teachers": [{"name": tr["Name"], "subject": tr["Subject"], "cap": load_of(tr, a)[1],
                          "full": load_of(tr, a)[0], "mum": tr["Mumayaz"], "rem": tr["Remedial"]} for tr in teachers],
            "items": items,
            "subjects": [{"code": s, "name": i18n.subj(s), "color": colors.strong(s), "light": colors.light(s)} for s in subs],
            "rtl": i18n.is_ar(),
            "i18n": {"h": "سا" if i18n.is_ar() else "h", "pool": t("a_pool"), "clear_t": t("a_clear_t"),
                     "clear_s": t("a_clear_s"), "clear_a": t("a_clear_a"), "confirm_all": t("a_confirm_all"),
                     "mode_on": t("a_mode_on"), "mode_off": t("a_mode_off"), "mode_stop": t("a_mode_stop"),
                     "select_tip": t("a_select_tip"), "drop": t("a_drop_hint"), "all": t("a_all"), "rem": t("wz_c_rem")}}


def _step_assign(st, ss, a, frames, dnd_assign):
    req = needed_hours(frames)
    teachers = ss.get("wz_teachers") or make_teachers(suggest_counts(req, a), a)
    ss["wz_teachers"] = teachers
    names = {tr["Name"] for tr in teachers}
    keys = {(r.Class, r.Subject) for r in req.itertuples()}
    cur = ss.get("wz_assign")
    fa = file_of(a, "assign")
    if fa and cur is not None:
        _file_banner(st, ss, a, "assign")
        extra = [k_ for k_ in cur if k_ not in keys]
        if extra:
            st.warning(t("wz_assign_extra", n=len(extra), x=", ".join(f"{i18n.cls(c)}·{i18n.subj(s_)}" for c, s_ in extra[:12])))
        cur = {k_: (cur.get(k_) if cur.get(k_) in names else None) for k_ in keys}
    elif cur is None or set(cur) != keys or any(v and v not in names for v in cur.values()):
        cur = auto_assign(req, teachers, a)
    st.subheader(t("wz_q_assign"))
    if st.button(t("wz_auto"), key="wz_auto"):
        cur = auto_assign(req, teachers, a); ss["wz_nonce"] = None
    ss["wz_assign"] = cur
    ev = dnd_assign(data=_payload(req, cur, teachers, a), key="wz_dnd", default=None)
    if ev and ev.get("nonce") != ss.get("wz_nonce"):
        ss["wz_nonce"] = ev.get("nonce")
        for c_, s_, n_ in ev.get("assign", []):
            if (c_, s_) in cur:
                cur[(c_, s_)] = n_ or None
        for m in ev.get("moves", []):
            k = (m["cls"], m["subject"])
            if k in cur:
                cur[k] = m["teacher"] or None
        ss["wz_assign"] = cur
        ss["wz_assign_touched"] = True
        st.rerun()
    un, over, _ = status(req, cur, teachers, a)
    ok = True
    if un:
        st.warning(t("wz_unassigned", n=len(un), h=sum(h for _, h in un)) + " " +
                   ", ".join(f"{i18n.cls(c)}·{i18n.subj(s)}" for (c, s), _ in un[:12]) + (" …" if len(un) > 12 else ""))
        c1, c2 = st.columns([3, 1])
        a["bypass"] = c1.checkbox(t("wz_bypass"), a.get("bypass", False), key="wz_bypass")
        if c2.button(t("wz_add_teacher"), key="wz_addt"):
            ss["wz_step"] = STEPS.index("teachers"); st.rerun()
        ok &= bool(a["bypass"])
    if over:
        st.error(t("wz_over", n=len(over), x=", ".join(f"{n} ({h}/{c})" for n, h, c in over)))
        a["accept_over"] = st.checkbox(t("wz_accept_over"), a.get("accept_over", False), key="wz_aover")
        ok &= bool(a["accept_over"])
    if not un and not over:
        st.success(t("wz_all_ok"))
    elif not ok:
        st.caption(t("wz_fix_first"))
    return ok


def _step_finish(st, ss, a, frames, db=None, ws="demo"):
    import datai18n as dl
    req = needed_hours(frames)
    teachers = ss.get("wz_teachers") or []
    cur = ss.get("wz_assign") or {}
    if not teachers or not cur:
        st.warning(t("wz_not_done"))
        if st.button(t("wz_prev"), key="wz_prev_f"):
            ss["wz_step"] = STEPS.index("assign"); st.rerun()
        return False
    plan = to_plan(req, cur, teachers, a)
    un, _, _ = status(req, cur, teachers, a)
    st.subheader(t("wz_summary"))
    st.success(t("wz_sum_line", c=len(frames["classes"]), s=frames["subjects"]["Subject_Code"].nunique(),
                 p=len(plan["teachers"]), r=len(frames["rules"]), w=len(frames["inspections"])))
    if un:
        st.caption(t("wz_dropped", x=", ".join(f"{i18n.cls(c)}·{i18n.subj(s)} ({h})" for (c, s), h in un)))
    with st.expander(t("rm_check_title"), expanded=True):
        import rooms as rms
        from engine import SchoolDataLoader, SchedulerConfig, SchoolSchedulerEngine
        fr = dict(frames); fr["teachers"] = plan["teachers"]
        eng = SchoolSchedulerEngine(SchoolDataLoader(fr), SchedulerConfig(), fixed_assignment=plan["assignment"])
        eng._generate_lessons_and_assignments()
        rms.render_check(st, rms.capacity_check(eng.lessons, eng.room_caps()))
    lt = ap.load_table(plan)
    lt["Subject"] = [i18n.subj(s) for s in lt["Subject"]]
    lt["Classes"] = [" ".join(i18n.cls(c.strip()) for c in x.split(",")) for x in lt["Classes"]]
    st.dataframe(lt[["Teacher", "Subject", "Hours", "Remedial", "Total", "Max", "Classes"]].rename(columns={
        "Teacher": t("wz_c_name"), "Subject": t("wz_c_subject"), "Hours": t("wz_c_hours"), "Remedial": t("wz_c_rem"),
        "Total": t("wz_c_total"), "Max": t("wz_c_max"), "Classes": t("wz_c_classes")}), hide_index=True, width="stretch")
    c1, c2, c3 = st.columns(3)
    applied = False
    if c1.button(t("wz_apply"), type="primary", key="wz_apply", width="stretch"):
        save_project(frames, plan, a, teachers, db, ws)
        ss["wz_open"] = False
        applied = True
    files = dict(frames)
    files["teachers"] = plan["teachers"]
    c2.download_button(t("wz_download"), _zip_with_assignment(files, plan), f"{ws}_school_setup.zip",
                       "application/zip", key="wz_zip", width="stretch")
    if c3.button(t("wz_prev"), key="wz_prev_f2", width="stretch"):
        ss["wz_step"] = STEPS.index("assign"); st.rerun()
    return applied
