# School Timetable Scheduler (مولّد جداول التوقيت)

OR-Tools CP-SAT timetable engine + Streamlit UI (Arabic / English).

## Run
```bash
pip install ortools streamlit pandas openpyxl
streamlit run app.py
```

## Features
- Upload CSV data, or create/edit it directly in the app
- Assignment step (جدول توزيع الحصص) import/export, split (تفويج) rules
- Standard student grid (soft, top priority), pedagogical windows, teacher fairness
- Remediation (الاستدراك) in the last hour, when all the teacher's classes are free
- Subject colours, weekly totals, drag & drop editor with move validation
