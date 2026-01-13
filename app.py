import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time, timedelta

# --- הגדרות עמוד (Page Config) ---
st.set_page_config(page_title="דיווח שעות - גבי", page_icon="⏱️", layout="centered")

# --- כותרת ---
st.title("⏱️ מערכת דיווח שעות")

# --- חיבור לגוגל שיטס ---
# אנחנו עוטפים את זה ב-try כדי שהאפליקציה לא תקרוס אם החיבור עדיין לא הוגדר
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # קריאת נתונים קיימים
    existing_data = conn.read(worksheet="Sheet1", ttl=0) # ttl=0 מונע caching
    df = pd.DataFrame(existing_data)
except Exception as e:
    st.warning("⚠️ טרם הוגדר חיבור לגוגל שיטס. האפליקציה במצב 'הדגמה' בלבד.")
    df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes"])

# --- פונקציות עזר ולוגיקה ---
def calculate_target_hours(date_obj):
    """
    מחזיר את תקן השעות ליום ספציפי:
    א-ד (0,1,2,6 ב-python weekday של יום ראשון הוא 6): 9 שעות
    ה (3): 8.5 שעות
    ו-ש: 0 שעות
    """
    # המרת תאריך לפורמט datetime אם הוא לא כזה
    if isinstance(date_obj, str):
        date_obj = datetime.strptime(date_obj, "%Y-%m-%d")
        
    wd = date_obj.weekday() # Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    
    if wd == 6 or wd in [0, 1, 2]: # ימים א, ב, ג, ד
        return 9.0
    elif wd == 3: # יום ה
        return 8.5
    else: # שישי שבת
        return 0.0

def save_entry(date_val, start_val, end_val, notes_val):
    try:
        # יצירת שורה חדשה
        new_row = pd.DataFrame([{
            "date": str(date_val),
            "start_time": str(start_val),
            "end_time": str(end_val),
            "notes": notes_val
        }])
        
        # איחוד עם המידע הקיים
        updated_df = pd.concat([df, new_row], ignore_index=True)
        
        # שמירה לגוגל
        conn.update(worksheet="Sheet1", data=updated_df)
        st.success("הדיווח נשמר בהצלחה! ✅")
        st.rerun() # רענון הדף כדי לראות את הנתונים החדשים
    except Exception as e:
        st.error(f"שגיאה בשמירה: {e}")

# --- סרגל צד להזנת נתונים ---
with st.sidebar:
    st.header("📝 דיווח חדש")
    input_date = st.date_input("תאריך", datetime.now())
    
    # יצירת לשוניות לבחירה נוחה
    tab_clock, tab_manual = st.tabs(["⏰ שעון", "⌨️ הקלדה"])
    
    # משתנים לשמירת השעות הסופיות
    final_start = None
    final_end = None
    
    with tab_clock:
        # אופציה 1: בחירה עם השעון הרגיל (כמו קודם)
        clock_start = st.time_input("כניסה (שעון)", time(9, 0), step=60, key="clk_s")
        clock_end = st.time_input("יציאה (שעון)", time(18, 0), step=60, key="clk_e")
        
    with tab_manual:
        # אופציה 2: הקלדה ידנית של מספרים
        st.caption("לדוגמה: 0930, 9:30, 1800")
        man_start = st.text_input("כניסה (הקלדה)", value="09:00", key="man_s")
        man_end = st.text_input("יציאה (הקלדה)", value="18:00", key="man_e")

    input_notes = st.text_input("הערות (אופציונלי)")
    
    # פונקציית עזר להמרת טקסט לשעה
    def parse_time_input(time_str):
        try:
            # מנקה רווחים ונקודות
            clean_str = time_str.replace(":", "").replace(".", "").strip()
            # משלים אפסים אם צריך (למשל 930 -> 0930)
            if len(clean_str) == 3:
                clean_str = "0" + clean_str
            if len(clean_str) == 4:
                return datetime.strptime(clean_str, "%H%M").time()
            return None
        except:
            return None

    if st.button("שמור דיווח", use_container_width=True):
        # החלטה באיזה קלט להשתמש לפי הטאב הפעיל? 
        # בסטרים-ליט קשה לדעת איזה טאב פתוח, אז נבדוק אם ההקלדה תקינה - נשתמש בה.
        # אחרת נשתמש בשעון.
        
        # ננסה קודם את ההקלדה הידנית
        parsed_s = parse_time_input(man_start)
        parsed_e = parse_time_input(man_end)
        
        # לוגיקה חכמה: אם המשתמש שינה את הטקסט מהדיפולט, נתייחס לטקסט. אחרת לשעון.
        # לצורך הפשטות בפרויקט הזה: אם הטקסט תקין ושונה מברירת המחדל, נלך עליו.
        # אבל הכי בטוח: בוא נשתמש במה שמופיע בטאב ה"הקלדה" רק אם המשתמש באמת הקליד משהו הגיוני
        
        # גישה פשוטה יותר שעובדת מעולה:
        # נשתמש בערכים של ה-Clock כברירת מחדל, אלא אם כן הפונקציה של הטקסט מצליחה
        # אבל זה מבלבל.
        
        # הפתרון הכי נקי ל-UX:
        # אני אוסיף Radio Button נסתר או פשוט אבקש מהמשתמש למחוק את הטקסט אם הוא רוצה שעון?
        # לא. בוא נעשה משהו פשוט:
        # אם יש ערך חוקי בטקסט - הוא הקובע. (כי הוא דורש אקטיביות).
        
        start_val = parsed_s if parsed_s else clock_start
        end_val = parsed_e if parsed_e else clock_end
        
        # בדיקה שהתאריך לא קיים
        if not df.empty and str(input_date) in df['date'].astype(str).values:
            st.error("יום זה כבר דווח במערכת!")
        else:
            save_entry(input_date, start_val, end_val, input_notes)

# --- תצוגת נתונים וחישובים ---
st.divider()

if not df.empty:
    # 1. עיבוד נתונים
    calc_df = df.copy()
    
    # המרת עמודות לטיפוסים נכונים
    calc_df['date_obj'] = pd.to_datetime(calc_df['date'])
    
    # פונקציה לחישוב שעות עבודה
    def get_hours(row):
        s = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
        e = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
        return (e - s).total_seconds() / 3600

    calc_df['hours_worked'] = calc_df.apply(get_hours, axis=1)
    calc_df['target'] = calc_df['date_obj'].apply(calculate_target_hours)
    calc_df['delta'] = calc_df['hours_worked'] - calc_df['target']

    # 2. כרטיסי סיכום (Metrics) לחודש הנוכחי
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    monthly_df = calc_df[
        (calc_df['date_obj'].dt.month == current_month) & 
        (calc_df['date_obj'].dt.year == current_year)
    ]
    
    total_delta = monthly_df['delta'].sum()
    
    st.subheader(f"📊 סיכום חודש {current_month}/{current_year}")
    
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("סה״כ שעות בפועל", f"{monthly_df['hours_worked'].sum():.2f}")
    col_m2.metric("תקן חודשי (עד כה)", f"{monthly_df['target'].sum():.2f}")
    col_m3.metric("מאזן שעות (בנק)", f"{total_delta:.2f}", delta_color="normal")

    # 3. טבלה מפורטת
    st.subheader("היסטוריית דיווחים")
    
    # סידור לפי תאריך יורד
    display_df = calc_df.sort_values('date_obj', ascending=False)
    
    # בחירת עמודות לתצוגה ושינוי שמות לעברית
    final_view = display_df[['date', 'start_time', 'end_time', 'hours_worked', 'target', 'delta', 'notes']].rename(columns={
        'date': 'תאריך',
        'start_time': 'כניסה',
        'end_time': 'יציאה',
        'hours_worked': 'בפועל',
        'target': 'תקן',
        'delta': 'הפרש',
        'notes': 'הערות'
    })

    # צביעת הטבלה (אדום לחוסר, ירוק ליתר)
    def color_delta(val):
        color = '#d4edda' if val >= 0 else '#f8d7da' # ירוק בהיר / אדום בהיר
        return f'background-color: {color}'

    st.dataframe(
        final_view.style.map(color_delta, subset=['הפרש']).format({"בפועל": "{:.2f}", "תקן": "{:.2f}", "הפרש": "{:.2f}"}),
        use_container_width=True
    )

else:
    st.info("עדיין אין נתונים. התחל לדווח בצד ימין! 👉")