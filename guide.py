"""Short bilingual user guide + "what's new / known limits" panel."""
import i18n

GUIDE = {
"en": """
### 📘 Quick guide
**1. Choose your data** (page *📂 Data* → *Source*)
- **Example** – the school sample files, ready to try.
- **Upload** – your own CSV/XLSX files (download the templates first; column names can be English or Arabic). Each file is checked line by line; problems are listed as *file · line N*.
- **Wizard** – build a school from scratch in guided steps (levels → subjects/rooms → teachers → assignment).

**2. Assignment** (page *👥 Assignment*) – check the teacher ↔ class plan, the totals and the remedial sessions.

**3. Generate** (page *⚙️ Generate*) – first check **🧩 Before solving**: remediation units (joint subjects, singles/pairs, optional fixed hour – confirmation required) and **external teachers** (fix their lessons; allowed even in their subject's pedagogical window). Then press *Solve*. A countdown shows the remaining time. The result is saved as a new version in **your workspace** (sidebar, your name).

**4. Check & edit** – *Timetables* shows colored tables for classes, teachers and room occupancy; *Edit* lets you drag & drop lessons (only valid moves are proposed).

**5. Export & compare** – *Compare* shows the KPIs of all versions, lets you rename/delete them and export PDF/XLSX (full tables, one per class/teacher, room occupancy).

**Advanced constraints** are locked by the admin password (default `beta2026`, change it once unlocked).
""",
"ar": """
### 📘 دليل سريع
**1. اختر البيانات** (صفحة *📂 المعطيات* ← *المصدر*)
- **المثال** – ملفات المؤسسة الجاهزة للتجربة.
- **تحميل** – ملفاتك CSV/XLSX (حمّل النماذج أولًا؛ أسماء الأعمدة بالعربية أو الإنجليزية). يُفحص كل ملف سطرًا بسطر وتُعرض المشاكل بصيغة *الملف · السطر N*.
- **المساعد** – إنشاء مؤسسة من الصفر بخطوات موجهة (المستويات ← المواد/القاعات ← الأساتذة ← الإسناد).

**2. الإسناد** (صفحة *👥 الإسناد*) – راجع إسناد الأساتذة على الأفواج والمجاميع وحصص الاستدراك.

**3. التوليد** (صفحة *⚙️ التوليد*) – راجع أولًا **🧩 قبل التوليد**: وحدات الاستدراك (المواد المشتركة، فردي/ثنائي، ساعة مثبّتة اختيارية – التأكيد إلزامي) و**الأساتذة الخارجيين** (ثبّت حصصهم؛ مسموح حتى في النافذة البيداغوجية لمادتهم). ثم اضغط *حل*. يظهر عدّ تنازلي للوقت المتبقي. تُحفظ النتيجة كنسخة جديدة في **مساحة عملك** (الشريط الجانبي، اسمك).

**4. المراجعة والتعديل** – *الجداول* تعرض جداول ملونة للأفواج والأساتذة وشغل القاعات؛ *التعديل* يسمح بسحب وإفلات الحصص (تُقترح التنقلات الصحيحة فقط).

**5. التصدير والمقارنة** – *المقارنة* تعرض مؤشرات كل النسخ وتسمح بإعادة تسميتها أو حذفها وتصديرها PDF/XLSX (الجداول الشاملة، جدول لكل فوج/أستاذ، شغل القاعات).

**القيود المتقدمة** مقفلة بكلمة سر المشرف (الافتراضية `beta2026`، غيّرها بعد الفتح).
""",
}

NEWS = {
"en": """
#### 🆕 What's new in this beta
- Database storage, one **workspace** per tester (versions + wizard projects).
- Rename / delete versions; admin password stored (hashed) in the database.
- Remediation: Arabic/Math teachers linked through shared classes share ONE weekly hour, alternating weekly (one week Arabic, the next Math): each teacher has one session, each class exactly one, always with its own teachers; a slot-6 remediation ends the day (no slot 7 for those classes).
- Reception hour (parents): created automatically after each solve (in a teacher gap when possible, else next to his lessons); shown as 🤝 in the teacher tables and exports; drag it, add or remove it in Edit → 🤝 Reception hours.
- Live countdown while solving; room occupancy in PDF/XLSX export.
- Line-by-line checking of uploaded files; this guide.
- **📌 Free moves + Adapt** (Edit → full tables): drag lessons anywhere, even onto occupied hours; the solver keeps your pins and moves as few other lessons as possible. Pins are saved with the version.

#### ⚠️ Known limits
- A teacher who teaches **two different subjects** is not supported yet (one subject per teacher).
- **Small screens / phones**: the drag & drop tables need a wide screen (≥ 900 px); use a computer or tablet in landscape.
- On **Streamlit Cloud** the local SQLite database is erased at each restart – configure an external MySQL database (secrets) to keep versions.
- Some free-text descriptions inside the sample files are still in English.
- The solver is faster and better with 4 or more CPUs.
""",
"ar": """
#### 🆕 الجديد في هذه النسخة التجريبية
- حفظ في قاعدة بيانات، **مساحة عمل** لكل مختبِر (النسخ ومشاريع المساعد).
- إعادة تسمية النسخ وحذفها؛ كلمة سر المشرف محفوظة (مشفّرة) في قاعدة البيانات.
- الاستدراك: أساتذة العربية/الرياضيات المرتبطون بأفواج مشتركة يتقاسمون ساعة أسبوعية واحدة بالتناوب (أسبوع عربية والموالي رياضيات): حصة واحدة لكل أستاذ ولكل فوج، دائمًا مع أساتذته؛ الاستدراك في الحصة 6 ينهي اليوم (لا حصة 7 لتلك الأفواج).
- ساعة استقبال الأولياء: تُنشأ تلقائيًا بعد كل توليد (في فراغ الأستاذ إن أمكن وإلا بجوار حصصه)؛ تظهر 🤝 في جداول الأساتذة والتصدير؛ اسحبها أو أضفها/احذفها في التعديل ← 🤝 ساعات الاستقبال.
- عدّ تنازلي أثناء الحل؛ شغل القاعات في تصدير PDF/XLSX.
- فحص الملفات المحمّلة سطرًا بسطر؛ هذا الدليل.
- **📌 تنقلات حرة + تكييف** (التعديل ← الجداول الشاملة): اسحب الحصص إلى أي مكان حتى الساعات المشغولة؛ يحافظ المحلّل على تثبيتاتك ويغيّر أقل عدد ممكن من الحصص. تُحفظ التثبيتات مع النسخة.

#### ⚠️ حدود معروفة
- الأستاذ الذي يدرّس **مادتين مختلفتين** غير مدعوم بعد (مادة واحدة لكل أستاذ).
- **الشاشات الصغيرة / الهواتف**: جداول السحب والإفلات تحتاج شاشة عريضة (≥ 900 بكسل)؛ استعمل حاسوبًا أو لوحة أفقيًا.
- على **Streamlit Cloud** تُمحى قاعدة SQLite المحلية عند كل إعادة تشغيل – اضبط قاعدة MySQL خارجية (الأسرار) للاحتفاظ بالنسخ.
- بعض الأوصاف النصية داخل ملفات المثال ما زالت بالإنجليزية.
- المحلّل أسرع وأفضل مع 4 معالجات أو أكثر.
""",
}


def render(st):
    lang = "ar" if i18n.is_ar() else "en"
    c1, c2 = st.columns([3, 2])
    c1.markdown(GUIDE[lang])
    with c2.container(border=True):
        st.markdown(NEWS[lang])
