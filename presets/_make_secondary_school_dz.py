import json, copy
M = json.load(open("/home/user/timetable/presets/middle_school_dz.json"))
N = lambda en, ar: {"en": en, "ar": ar}
P = {"preset_id": "dz_secondary_school", "version": 1,
     "name": N("Algerian secondary school (lycée) – default values", "ثانوية جزائرية – القيم الافتراضية"),
     "notes": "SAMPLE defaults. Weekly totals follow the 2026/2027 decree as reported in the press (1AS Letters 31 h, "
              "1AS Sciences & Technology 32 h; Maths track 3AS maths 10 h; Experimental sciences SVT 6 h, maths 5 h, physics 4 h). "
              "Hours per year/track = course + TD + TP from the school administration tables (2026/2027).",
     "wizard": {
        "middle_school_questions": False,
        # default school (administration tables): classes per level
        "sample_counts": {"1AS-ST": 4, "1AS-LET": 3, "2AS-TME": 1, "2AS-SE": 2, "2AS-GE": 1, "2AS-LP": 1, "2AS-LE": 1,
                          "3AS-TME": 1, "3AS-TMP": 1, "3AS-SE": 3, "3AS-GE": 1, "3AS-LP": 2, "3AS-LE": 1},
        # teachers per subject: [total, of which distinguished (مميز)]
        "teacher_counts": {"MATH": [6, 0], "PHYS": [6, 0], "SCIENCE": [5, 1], "ISLAMIC": [3, 1], "ARABIC": [6, 1],
                           "PHILO": [2, 1], "HISTGEO": [4, 2], "FRENCH": [5, 3], "ENGLISH": [5, 3], "LANG3": [1, 1],
                           "ARTS": [1, 1], "INFO": [2, 0], "SPORT": [3, 1], "ELEC": [2, 0], "PROC": [2, 2], "ECOGEST": [2, 1]},
        # TD/TP: every TD/TP is taught in 2 groups; suggested pairs (2h session, groups swap after 1h) when hours match
        "grouping_pairs": [["PHYS", "TP", "SCIENCE", "TP"]],
        # default grouping of every TD/TP: alt = one session, the 2 groups alternate weeks
        "grouping_default": "alt"},
     # a stream with options: the option decides the engineering subject (teacher + workshop)
     "track_options": {"TM": {"name": N("Technical maths", "تقني رياضي"), "subject": "TECH",
                              "options": {"TME": "ELEC", "TMP": "PROC", "TMM": "MECH", "TMC": "CIVIL"}}},
     # spellings found in school files (Arabic / English variants) -> codes; matching ignores dots, spaces, hamza forms
     "aliases": {
        "tracks": {"ST": ["ج م ع ت", "جذع مشترك علوم وتكنولوجيا", "علوم وتكنولوجيا", "Science & Technology"],
                   "LET": ["ج م آ", "ج م ا", "جذع مشترك آداب", "Letters / Arts", "Letters"],
                   "SE": ["ع ت", "علوم تجريبية", "Experimental Sciences"], "M": ["رياضيات", "Mathematics"],
                   "TM": ["تقني رياضي", "Technical Math", "Technical Maths"],
                   "TME": ["هندسة كهربائية", "تقني رياضي هندسة كهربائية"],
                   "TMP": ["هندسة الطرائق", "هندسة الطرق"], "TMM": ["هندسة ميكانيكية"], "TMC": ["هندسة مدنية"],
                   "GE": ["تسيير واقتصاد", "Management & Econ"], "LP": ["آداب وفلسفة", "Letters & Philo"],
                   "LE": ["لغات", "لغات أجنبية", "Foreign Languages"]},
        "subjects": {"ARABIC": ["أدب عربي", "لغة عربية", "Arabic Language", "Arabic"], "MATH": ["رياضيات", "Mathematics"],
                     "PHYS": ["علوم فيزيائية", "Physics & Chemistry", "Physics & Chem."],
                     "SCIENCE": ["علوم طبيعية", "علوم الطبيعة والحياة", "Natural / Life Sciences", "Natural Sciences"],
                     "ISLAMIC": ["علوم إسلامية", "Islamic Sciences"], "PHILO": ["فلسفة", "Philosophy"],
                     "HISTGEO": ["اجتماعيات", "تاريخ وجغرافيا", "History & Geography", "History & Geog."],
                     "FRENCH": ["فرنسية", "French"], "ENGLISH": ["انجليزية", "English"],
                     "LANG3": ["إيطالية", "إسبانية", "ألمانية", "3rd Foreign Lang.", "Italian", "Spanish", "German"],
                     "ARTS": ["تربية فنية", "Art / Music"], "INFO": ["المعلوماتية", "إعلام آلي", "Computer Science"],
                     "SPORT": ["تربية بدنية", "Physical Education"], "TECH": ["تكنولوجيا", "Technology", "Technology / Eng."],
                     "ELEC": ["ه كهرباء", "هندسة كهربائية"], "PROC": ["ه الطرائق", "ه الطرقان", "هندسة الطرائق"],
                     "MECH": ["ه ميكانيك", "هندسة ميكانيكية"], "CIVIL": ["ه مدنية", "هندسة مدنية"],
                     "ECOGEST": ["ت/ اقتصادي", "ت/اقتصادي", "تسيير واقتصاد"],
                     "ACCOUNT": ["Management & Acc.", "تسيير محاسبي ومالي"], "ECON": ["Economics & Stat.", "اقتصاد ومناجمنت"],
                     "LAW": ["Law", "قانون"]}},
     # one teacher post teaches several subjects
     "teacher_families": {"ECOGEST": ["ACCOUNT", "ECON", "LAW"], "PROC": ["PROC", "TECH"]}}
per = [("08:00", "09:00", "morning"), ("09:00", "10:00", "morning"), ("10:00", "11:00", "morning"), ("11:00", "12:00", "morning"),
       ("13:00", "14:00", "afternoon"), ("14:00", "15:00", "afternoon"), ("15:00", "16:00", "afternoon"), ("16:00", "17:00", "afternoon")]
tp = copy.deepcopy(M["time_profiles"][0]); tp["id"] = "lycee_week"; tp["name"] = N("Secondary school week", "أسبوع الثانوية")
tp["periods"] = [{"id": i, "label": str(i + 1), "start": a, "end": b, "half": h} for i, (a, b, h) in enumerate(per)]
P["time_profiles"] = [tp]
P["stages"] = [{"id": "secondary", "name": N("Secondary school", "التعليم الثانوي"), "policy": "lycee_policy"}]
P["years"] = [{"id": f"{i}AS", "name": N(f"{i}AS", f"{i} ثانوي"), "stage": "secondary", "time_profile": "lycee_week", "order": i} for i in (1, 2, 3)]
P["tracks"] = [
    {"id": "ST", "name": N("Sciences & Technology", "جذع مشترك علوم وتكنولوجيا"), "years": ["1AS"]},
    {"id": "LET", "name": N("Letters", "جذع مشترك آداب"), "years": ["1AS"]},
    {"id": "SE", "name": N("Experimental sciences", "علوم تجريبية"), "years": ["2AS", "3AS"]},
    {"id": "M", "name": N("Mathematics", "رياضيات"), "years": ["2AS", "3AS"]},
    {"id": "TME", "name": N("Technical maths – electrical eng.", "تقني رياضي – هندسة كهربائية"), "years": ["2AS", "3AS"]},
    {"id": "TMP", "name": N("Technical maths – process eng.", "تقني رياضي – هندسة الطرائق"), "years": ["2AS", "3AS"]},
    {"id": "TMM", "name": N("Technical maths – mechanical eng.", "تقني رياضي – هندسة ميكانيكية"), "years": ["2AS", "3AS"]},
    {"id": "TMC", "name": N("Technical maths – civil eng.", "تقني رياضي – هندسة مدنية"), "years": ["2AS", "3AS"]},
    {"id": "GE", "name": N("Management & economics", "تسيير واقتصاد"), "years": ["2AS", "3AS"]},
    {"id": "LP", "name": N("Letters & philosophy", "آداب وفلسفة"), "years": ["2AS", "3AS"]},
    {"id": "LE", "name": N("Foreign languages", "لغات أجنبية"), "years": ["2AS", "3AS"]}]
P["class_template"] = {"pattern": "{year}-{track}{n}", "default_students": 40, "note": "classes = year x track x number"}
P["subjects"] = [{"id": k, "name": N(en, ar), "short": N(se, sa), "color": None} for k, en, ar, se, sa in [
    ("ARABIC", "Arabic", "لغة عربية", "ARA", "عربية"), ("ISLAMIC", "Islamic sciences", "علوم إسلامية", "ISL", "إسلامية"),
    ("MATH", "Mathematics", "رياضيات", "MATH", "رياضيات"), ("FRENCH", "French", "لغة فرنسية", "FR", "فرنسية"),
    ("ENGLISH", "English", "لغة إنجليزية", "ENG", "إنجليزية"), ("PHYS", "Physics", "علوم فيزيائية", "PHY", "فيزياء"),
    ("SCIENCE", "Natural & life sciences", "علوم الطبيعة والحياة", "SVT", "علوم"), ("HISTGEO", "History & geography", "تاريخ وجغرافيا", "H-G", "تاريخ/جغ"),
    ("PHILO", "Philosophy", "فلسفة", "PHILO", "فلسفة"), ("INFO", "Computer science", "إعلام آلي", "INFO", "إعلام"),
    ("TECH", "Technology", "تكنولوجيا", "TECH", "تكنولوجيا"),
    ("ELEC", "Electrical engineering", "هندسة كهربائية", "ELEC", "ه.كهرباء"),
    ("PROC", "Process engineering", "هندسة الطرائق", "PROC", "ه.طرائق"),
    ("MECH", "Mechanical engineering", "هندسة ميكانيكية", "MECH", "ه.ميكانيك"),
    ("CIVIL", "Civil engineering", "هندسة مدنية", "CIVIL", "ه.مدنية"),
    ("ECOGEST", "Management & economics (teacher)", "تسيير واقتصاد", "ECO", "ت/اقتصاد"), ("ACCOUNT", "Accounting & finance", "تسيير محاسبي ومالي", "ACC", "محاسبة"),
    ("ECON", "Economics & management", "اقتصاد ومناجمنت", "ECO", "اقتصاد"), ("LAW", "Law", "قانون", "LAW", "قانون"),
    ("LANG3", "Third foreign language", "لغة أجنبية ثالثة", "L3", "لغة 3"),
    ("ARTS", "Arts", "فنون", "ART", "فنون"), ("SPORT", "Physical education", "تربية بدنية", "PE", "رياضة")]]
P["room_types"] = [
    {"id": "classroom", "name": N("Classroom", "قاعة دراسة"), "count": 22, "capacity_students": 40, "fallback": None},
    {"id": "lab", "name": N("Laboratory", "مخبر"), "count": 4, "capacity_students": 40, "fallback": "classroom"},
    {"id": "computer_lab", "name": N("Computer room", "قاعة إعلام آلي"), "count": 2, "capacity_students": 20, "fallback": None},
    {"id": "workshop", "name": N("Technology workshop", "ورشة تكنولوجيا"), "count": 1, "capacity_students": 20, "fallback": "classroom"},
    {"id": "gym", "name": N("Sports field", "ملعب"), "count": 3, "capacity_students": 40, "fallback": None}]
ROOM = {"PHYS": "lab", "SCIENCE": "lab", "INFO": "computer_lab", "SPORT": "gym"}
# (course, td, tp) per subject; tp in labs
def T(txt):
    out = {}
    for part in txt.split(","):
        k, v = part.split("=")
        out[k.strip()] = tuple(int(x) for x in v.strip().split("+"))
    return out
COMMON2 = "ISLAMIC=2+0+0,SPORT=2+0+0"
C = {
 ("1AS", "ST"): T("ARABIC=3+1+0,MATH=3+2+0,PHYS=2+0+2,SCIENCE=2+0+2,HISTGEO=2+0+0,FRENCH=2+1+0,ENGLISH=2+1+0,ISLAMIC=2+0+0,"
                  "INFO=0+0+2,TECH=1+0+1,SPORT=2+0+0,ARTS=1+0+0"),
 ("1AS", "LET"): T("ARABIC=4+1+0,MATH=2+0+0,HISTGEO=3+0+0,FRENCH=3+1+0,ENGLISH=3+1+0,ISLAMIC=2+0+0,INFO=0+0+2,SPORT=2+0+0,ARTS=1+0+0"),
 ("2AS", "SE"): T("ARABIC=2+1+0,MATH=3+2+0,PHYS=3+0+2,SCIENCE=2+0+2,HISTGEO=2+0+0,PHILO=2+0+0,FRENCH=2+1+0,ENGLISH=2+1+0,INFO=0+0+2," + COMMON2),
 ("2AS", "M"): T("ARABIC=2+1+0,MATH=5+2+0,PHYS=4+2+0,SCIENCE=2+0+0,HISTGEO=2+0+0,PHILO=2+0+0,FRENCH=2+1+0,ENGLISH=2+1+0,INFO=0+0+2," + COMMON2),
 ("2AS", "TM"): T("ARABIC=2+1+0,MATH=4+2+0,PHYS=3+0+2,TECH=2+0+4,HISTGEO=2+0+0,PHILO=2+0+0,FRENCH=2+1+0,ENGLISH=2+1+0,INFO=0+0+2," + COMMON2),
 ("2AS", "LP"): T("ARABIC=4+1+0,MATH=2+0+0,HISTGEO=4+0+0,PHILO=3+1+0,FRENCH=3+1+0,ENGLISH=2+1+0," + COMMON2),
 ("2AS", "LE"): T("ARABIC=3+1+0,MATH=2+0+0,HISTGEO=4+0+0,PHILO=3+0+0,FRENCH=3+1+0,ENGLISH=3+1+0,LANG3=4+1+0," + COMMON2),
 ("2AS", "GE"): T("ARABIC=2+1+0,MATH=3+2+0,ACCOUNT=3+2+0,ECON=3+0+0,LAW=2+0+0,HISTGEO=3+0+0,PHILO=2+0+0,FRENCH=2+1+0,ENGLISH=2+1+0,"
                  "INFO=0+0+2," + COMMON2),
 ("3AS", "SE"): T("ARABIC=2+1+0,MATH=3+2+0,PHYS=3+0+2,SCIENCE=4+0+2,PHILO=2+0+0,HISTGEO=2+0+0,FRENCH=2+1+0,ENGLISH=2+0+0," + COMMON2),
 ("3AS", "M"): T("ARABIC=2+1+0,MATH=5+2+0,PHYS=4+2+0,SCIENCE=2+0+0,PHILO=2+0+0,HISTGEO=2+0+0,FRENCH=2+0+0,ENGLISH=2+0+0," + COMMON2),
 ("3AS", "TM"): T("ARABIC=2+1+0,MATH=4+2+0,PHYS=3+0+2,TECH=2+0+4,PHILO=2+0+0,HISTGEO=2+0+0,FRENCH=2+0+0,ENGLISH=2+0+0," + COMMON2),
 ("3AS", "LP"): T("ARABIC=5+1+0,MATH=2+0+0,PHILO=6+2+0,HISTGEO=4+0+0,FRENCH=4+1+0,ENGLISH=3+1+0," + COMMON2),
 ("3AS", "LE"): T("ARABIC=4+1+0,MATH=2+0+0,PHILO=3+1+0,HISTGEO=4+0+0,FRENCH=4+1+0,ENGLISH=4+1+0,LANG3=3+1+0," + COMMON2),
 ("3AS", "GE"): T("ARABIC=2+1+0,MATH=3+2+0,ACCOUNT=4+2+0,ECON=4+0+0,LAW=2+0+0,PHILO=2+0+0,HISTGEO=4+0+0,FRENCH=2+1+0,ENGLISH=2+0+0," + COMMON2),
}
for y in ("2AS", "3AS"):
    tm = C.pop((y, "TM"))
    C[(y, "TME")] = {("ELEC" if k == "TECH" else k): v for k, v in tm.items()}
    C[(y, "TMP")] = {("PROC" if k == "TECH" else k): v for k, v in tm.items()}
    C[(y, "TMM")] = {("MECH" if k == "TECH" else k): v for k, v in tm.items()}
    C[(y, "TMC")] = {("CIVIL" if k == "TECH" else k): v for k, v in tm.items()}
cur = []
for (y, tr), subs in C.items():
    for s, h in subs.items():
        h = tuple(h) + (0,) * (3 - len(h))
        cur.append({"year": y, "track": tr, "subject": s, "hours": {"course": h[0], "td": h[1], "tp": h[2], "practice": 0},
                    "room_type": "gym" if s == "SPORT" else ("workshop" if s in ("TECH", "ELEC", "PROC", "MECH", "CIVIL") and h[2] else (ROOM.get(s, "classroom") if h[2] else "classroom")),
                    "blocks_allowed": [1, 2], "max_per_day": 1, "frequency": "weekly"})
P["curriculum"] = cur
P["subject_unavailable"] = []
P["teacher_defaults"] = copy.deepcopy(M["teacher_defaults"]); P["teacher_defaults"]["max_hours"] = 18
lab_lv = ["1AS-ST", "2AS-SE", "3AS-SE"]
P["session_templates_unused"] = [
    {"id": "R_LAB_01", "kind": "split_class", "years": lab_lv,
     "groups": [{"group": "A", "parts": [{"subject": "PHYS", "type": "TP", "hours": 2}]},
                {"group": "B", "parts": [{"subject": "SCIENCE", "type": "TP", "hours": 2}]}],
     "frequency": "weekly", "swap": "after_first_hour", "description": "Every week: half class Physics TP 2h / half class Natural sciences TP 2h, then the groups swap"}]
P["session_templates"] = []
pol = copy.deepcopy(M["policies"][0]); pol["id"] = "lycee_policy"
pol["rules"]["class_grid"]["base_hours"] = 32
pol["rules"]["same_day_exempt"] = ["INFO"]
P["policies"] = [pol]
P["solver"] = dict(M["solver"])
json.dump(P, open("/home/user/timetable/presets/secondary_school_dz.json", "w"), ensure_ascii=False, indent=1)
for (y, tr), subs in sorted(C.items()):
    print(y, tr, sum(sum(h) for h in subs.values()))
