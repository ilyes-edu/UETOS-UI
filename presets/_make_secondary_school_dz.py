import json, copy
M = json.load(open("/home/user/timetable/presets/middle_school_dz.json"))
N = lambda en, ar: {"en": en, "ar": ar}
P = {"preset_id": "dz_secondary_school", "version": 1,
     "name": N("Algerian secondary school (lycée) – sample values", "ثانوية جزائرية – قيم نموذجية"),
     "notes": "SAMPLE defaults. Weekly totals follow the 2026/2027 decree as reported in the press (1AS Letters 31 h, "
              "1AS Sciences & Technology 32 h; Maths track 3AS maths 10 h; Experimental sciences SVT 6 h, maths 5 h, physics 4 h). "
              "All other hours are estimates: check them against the official decree and edit the curriculum table.",
     "wizard": {"middle_school_questions": False, "sample_counts": {"1AS-ST": 4, "1AS-LET": 3, "2AS-SE": 2, "2AS-M": 1,
                "2AS-GE": 1, "2AS-LP": 2, "3AS-SE": 2, "3AS-M": 1, "3AS-GE": 1, "3AS-LP": 2}}}
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
    {"id": "TM", "name": N("Technical maths", "تقني رياضي"), "years": ["2AS", "3AS"]},
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
    ("TECH", "Technology", "تكنولوجيا", "TECH", "تكنولوجيا"), ("ACCOUNT", "Accounting & finance", "تسيير محاسبي ومالي", "ACC", "محاسبة"),
    ("ECON", "Economics & management", "اقتصاد ومناجمنت", "ECO", "اقتصاد"), ("LAW", "Law", "قانون", "LAW", "قانون"),
    ("LANG3", "Third language (German/Spanish/Italian)", "لغة أجنبية ثالثة", "L3", "لغة 3"),
    ("ARTS", "Arts", "فنون", "ART", "فنون"), ("SPORT", "Physical education", "تربية بدنية", "PE", "رياضة")]]
P["room_types"] = [
    {"id": "classroom", "name": N("Classroom", "قاعة دراسة"), "count": 22, "capacity_students": 40, "fallback": None},
    {"id": "lab", "name": N("Laboratory", "مخبر"), "count": 4, "capacity_students": 40, "fallback": "classroom"},
    {"id": "computer_lab", "name": N("Computer room", "قاعة إعلام آلي"), "count": 2, "capacity_students": 20, "fallback": None},
    {"id": "workshop", "name": N("Technology workshop", "ورشة تكنولوجيا"), "count": 1, "capacity_students": 20, "fallback": "classroom"},
    {"id": "gym", "name": N("Sports field", "ملعب"), "count": 3, "capacity_students": 40, "fallback": None}]
ROOM = {"PHYS": "lab", "SCIENCE": "lab", "INFO": "computer_lab", "SPORT": "gym"}
# (course, td, tp) per subject; tp in labs
C = {
 ("1AS", "ST"): {"ARABIC": (3,), "ISLAMIC": (2,), "MATH": (5,), "FRENCH": (3,), "ENGLISH": (3,), "PHYS": (3, 0, 1), "SCIENCE": (3, 0, 1),
                 "HISTGEO": (2,), "TECH": (2,), "INFO": (0, 0, 2), "SPORT": (2,)},
 ("1AS", "LET"): {"ARABIC": (6,), "ISLAMIC": (2,), "MATH": (3,), "FRENCH": (4,), "ENGLISH": (3,), "HISTGEO": (4,), "SCIENCE": (2,),
                  "PHYS": (2,), "INFO": (0, 0, 2), "ARTS": (1,), "SPORT": (2,)},
 ("3AS", "SE"): {"SCIENCE": (5, 0, 1), "MATH": (5,), "PHYS": (3, 0, 1), "ARABIC": (3,), "ISLAMIC": (2,), "FRENCH": (3,), "ENGLISH": (3,),
                 "HISTGEO": (2,), "PHILO": (2,), "SPORT": (2,)},
 ("3AS", "M"): {"MATH": (10,), "PHYS": (5, 0, 1), "SCIENCE": (2,), "ARABIC": (3,), "ISLAMIC": (2,), "FRENCH": (3,), "ENGLISH": (2,),
                "HISTGEO": (2,), "PHILO": (2,), "SPORT": (2,)},
 ("3AS", "TM"): {"MATH": (6,), "PHYS": (5, 0, 1), "TECH": (4, 0, 3), "ARABIC": (2,), "ISLAMIC": (2,), "FRENCH": (3,), "ENGLISH": (2,),
                 "HISTGEO": (2,), "PHILO": (2,), "SPORT": (2,)},
 ("3AS", "GE"): {"ACCOUNT": (5,), "ECON": (4,), "LAW": (2,), "MATH": (5,), "ARABIC": (3,), "ISLAMIC": (2,), "FRENCH": (3,),
                 "ENGLISH": (3,), "HISTGEO": (4,), "PHILO": (2,), "SPORT": (2,)},
 ("3AS", "LP"): {"PHILO": (7,), "ARABIC": (6,), "HISTGEO": (4,), "MATH": (2,), "ISLAMIC": (2,), "FRENCH": (3,), "ENGLISH": (3,), "SPORT": (2,)},
 ("3AS", "LE"): {"FRENCH": (5,), "ENGLISH": (5,), "LANG3": (4,), "ARABIC": (5,), "PHILO": (2,), "HISTGEO": (3,), "MATH": (2,),
                 "ISLAMIC": (2,), "SPORT": (2,)},
}
for tr in ("SE", "M", "TM", "GE", "LP", "LE"):        # 2AS = 3AS of the same track (estimates), maths track 7 h
    C[("2AS", tr)] = dict(C[("3AS", tr)])
C[("2AS", "M")]["MATH"] = (7,)
C[("2AS", "M")]["SCIENCE"] = (3,)
cur = []
for (y, tr), subs in C.items():
    for s, h in subs.items():
        h = tuple(h) + (0,) * (3 - len(h))
        cur.append({"year": y, "track": tr, "subject": s, "hours": {"course": h[0], "td": h[1], "tp": h[2], "practice": 0},
                    "room_type": "gym" if s == "SPORT" else ("workshop" if s == "TECH" and h[2] else (ROOM.get(s, "classroom") if h[2] else "classroom")),
                    "blocks_allowed": [1, 2], "max_per_day": 1, "frequency": "weekly"})
P["curriculum"] = cur
P["subject_unavailable"] = []
P["teacher_defaults"] = copy.deepcopy(M["teacher_defaults"]); P["teacher_defaults"]["max_hours"] = 18
lab_lv = ["1AS-ST", "2AS-SE", "3AS-SE"]
P["session_templates"] = [
    {"id": "R_LAB_01", "kind": "split_class", "years": lab_lv,
     "groups": [{"group": "A", "parts": [{"subject": "PHYS", "type": "TP", "hours": 1}]},
                {"group": "B", "parts": [{"subject": "SCIENCE", "type": "TP", "hours": 1}]}],
     "frequency": "weekly", "swap": "after_first_hour", "description": "Every week: 2h lab block - groups swap after the first hour"}]
pol = copy.deepcopy(M["policies"][0]); pol["id"] = "lycee_policy"
pol["rules"]["class_grid"]["base_hours"] = 32
pol["rules"]["same_day_exempt"] = ["INFO"]
P["policies"] = [pol]
P["solver"] = dict(M["solver"])
json.dump(P, open("/home/user/timetable/presets/secondary_school_dz.json", "w"), ensure_ascii=False, indent=1)
for (y, tr), subs in sorted(C.items()):
    print(y, tr, sum(sum(h) for h in subs.values()))
