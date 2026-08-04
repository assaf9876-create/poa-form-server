# שרת מילוי טפסי ייפוי כוח — הדרכת הקמה

## שלב 0 — קבצים שחסרים ואתה צריך להוסיף בעצמך לתיקיית `assets/`

הקבצים האלה קיימים אצלי בפרויקט קלוד אבל לא ניתן להוריד אותם אוטומטית לכאן.
לך לפרויקט הקלוד שלך → קבצי הפרויקט, והורד את הארבעה האלה, שים אותם בתוך `assets/`:

1. `ראשי_ידני_לקלאוד.pdf`
2. `נוסף_ידני_לקלאוד.pdf`
3. `קשקוש.png` (חתימה)
4. `סמי_ביטון.png` (חותמת)

בנוסף, הורד את הפונט DejaVu Sans (חינמי, קובץ יחיד) מכאן:
https://dejavu-fonts.github.io/  → קובץ `DejaVuSans.ttf`
ושים גם אותו בתוך `assets/`.

בסוף, `assets/` אמורה להכיל 5 קבצים:
```
assets/
  ראשי_ידני_לקלאוד.pdf
  נוסף_ידני_לקלאוד.pdf
  קשקוש.png
  סמי_ביטון.png
  DejaVuSans.ttf
```

## שלב 1 — יצירת ריפו ב-GitHub

1. היכנס ל-github.com, צור חשבון אם אין לך.
2. לחץ "New repository", תן שם (למשל `poa-form-server`), Public או Private — לא משנה.
3. העלה את כל 4 הקבצים מהתיקייה הזו (`app.py`, `requirements.txt`, `render.yaml`, `README.md`)
   ואת תיקיית `assets/` עם 5 הקבצים בתוכה — דרך "Add file" → "Upload files" בממשק של GitHub (לא צריך Git בשורת פקודה).

## שלב 2 — הקמה ב-Render

1. היכנס ל-render.com, הירשם (אפשר עם GitHub — הכי מהיר).
2. לחץ "New" → "Web Service".
3. חבר את הריפו שיצרת ב-GitHub.
4. Render יזהה את `render.yaml` אוטומטית ויציע את ההגדרות הנכונות (Build: `pip install -r requirements.txt`, Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`).
5. ודא ש-Plan מוגדר "Free".
6. לחץ "Create Web Service" — Render יתחיל לבנות (כמה דקות).
7. בסיום, תקבל כתובת URL כמו: `https://poa-form-server.onrender.com`

## שלב 3 — בדיקה

פתח בדפדפן: `https://poa-form-server.onrender.com/`
אמור להחזיר: `{"status":"ok"}`

בדיקה מלאה (למשל דרך Postman או curl):
```
POST https://poa-form-server.onrender.com/fill-poa
Content-Type: application/json

{
  "company_name": "שם החברה בע\"מ",
  "company_number": "123456789",
  "company_addr": "רחוב הדוגמה 1, תל אביב"
}
```
תקבל חזרה JSON עם שני שדות base64 של ה-PDF-ים.

## שלב 4 — חיבור ב-Make

ב-Make, מודול HTTP → "Make a request":
- URL: `https://poa-form-server.onrender.com/fill-poa`
- Method: POST
- Body type: JSON
- Body:
```json
{
  "company_name": "{{שם חברה מ-Zoho}}",
  "company_number": "{{ח\"פ מ-Zoho}}",
  "company_addr": "{{כתובת מ-Zoho}}"
}
```

לאחר מכן, מודול "Base64 to file" (מובנה ב-Make) על השדות `primary_pdf_base64` ו-`additional_pdf_base64`,
ואז מודול Dropbox "Upload a File" עבור כל אחד מהם.

**הערה חשובה:** בטייר החינמי של Render, השרת "נרדם" אחרי כ-15 דקות חוסר פעילות.
הקריאה הראשונה אחרי שינה עלולה לקחת כ-30-50 שניות. ב-Make, אפשר להגדיר Timeout גבוה יותר במודול ה-HTTP כדי למנוע כשל.
