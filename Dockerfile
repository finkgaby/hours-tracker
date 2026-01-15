# בחירת בסיס פייתון
FROM python:3.10-slim

# הגדרת תיקיית עבודה
WORKDIR /app

# העתקת קבצים
COPY . .

# התקנת ספריות
RUN pip install --no-cache-dir -r requirements.txt

# חשיפת הפורט של Streamlit
EXPOSE 8080

# הרצת האפליקציה
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]