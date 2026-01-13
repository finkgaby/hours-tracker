import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import os

# --- הגדרות עמוד ותמיכה בעברית ---
st.set_page_config(page_title="מערכת דיווח שעות", layout="wide", page_icon="⏱️")

# הזרקת CSS ליישור לימין (RTL)
st.markdown("""
<style>
    .stApp {
        direction: rtl;
        text-align: right;
    }
    .stMarkdown, .stText, .stHeader, .stMetricLabel {
        text-align: right !important;
    }
    div[data-testid="stMetricValue"] {
        direction: ltr; /* המספרים יישארו משמאל לימין */
        text-align: right;
    }
    .css-10trblm {
        text-align: right;
    }
    /* התאמה לטבלה */
    div[data-testid="stDataFrame"] {
        direction: ltr; 
    }
</style>
""", unsafe_allow_html=True)

# --- ניהול קובץ הנתונים ---
DATA_FILE = "hours_data.csv"

def load_data():
    if not os.path.exists(DATA_FILE):
        # יצירת מבנה התחלתי אם הקובץ לא קיים
        return pd.DataFrame(columns=["Date", "Day", "Entry", "Exit", "Actual", "Standard", "Balance", "Notes"])
    
    df = pd.read_csv(DATA_FILE)
    # המרת עמודות לפורמט הנכון כדי למנוע בעיות חישוב
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    df['Actual'] = pd.to_numeric(df['Actual'], errors='coerce').fillna(0)
    df['Standard'] = pd.to_numeric(df['Standard'], errors='coerce').fillna(0)
    df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce').fillna(0)
    return df

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def get_hebrew_day(py_date):
    days = {6: "יום א'", 0: "יום ב'", 1: "יום ג'", 2: "יום ד'", 3: "יום ה'", 4: "יום ו'", 5: "שבת"}
    return days.get(py_date.weekday(), "-")

# --- טעינת הנתונים ---
df = load_data()

# --- כותרת ---
st.title("⏱️ מערכת דיווח שעות")

# --- אזור הזנת דיווח חדש ---
with st.expander("📝 דיווח חדש", expanded=True):
    with st.form("entry_form", clear_on_submit=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            date_input = st.date_input("תאריך", value=date.today())
        with col2:
            entry_time = st.time_input("כניסה", value=datetime.strptime("09:00", "%H:%M").time())
        with col3:
            exit_time = st.time_input("יציאה", value=datetime.strptime("18:00", "%H:%M").time())
        with col4:
            standard_hours = st.number_input("תקן שעות", value=9.0, step=0.5)
        with col5:
            notes = st.text_input("הערות")

        submitted = st.form_submit_button("שמור דיווח")

        if submitted:
            # חישוב שעות
            start_dt = datetime.combine(date_input, entry_time)
            end_dt = datetime.combine(date_input, exit_time)
            
            duration = end_dt - start_dt
            actual_hours = duration.total_seconds() / 3600
            balance = actual_hours - standard_hours
            
            day_name = get_hebrew_day(date_input)

            new_record = {
                "Date": date_input,
                "Day": day_name,
                "Entry": entry_time.strftime("%H:%M"),
                "Exit": exit_time.strftime("%H:%M"),
                "Actual": round(actual_hours, 2),
                "Standard": standard_hours,
                "Balance": round(balance, 2),
                "Notes": notes
            }
            
            # הוספה ל-DataFrame
            df = pd.concat([pd.DataFrame([new_record]), df], ignore_index=True)
            save_data(df)
            st.success("הדיווח נשמר בהצלחה!")
            st.rerun()

# --- חישוב סיכומים ---
# וידוא שתאריכים הם אובייקט date לצורך השוואה
df['Date'] = pd.to_datetime(df['Date']).dt.date
today = date.today()

# 1. סינון לחודש הנוכחי
current_month_df = df[
    (pd.to_datetime(df['Date']).dt.month == today.month) & 
    (pd.to_datetime(df['Date']).dt.year == today.year)
]

# 2. סינון לשבוע הנוכחי (יום ראשון עד היום)
# חישוב יום ראשון של השבוע הנוכחי (בהנחה שיום ראשון הוא תחילת שבוע)
# weekday(): 0=Mon, 6=Sun. בתיקון לישראל: אם היום יום א' (6), נחסיר 0. אם יום ב' (0), נחסיר 1.
idx = (today.weekday() + 1) % 7 
sunday_of_week = today - timedelta(days=idx)

current_week_df = df[df['Date'] >= sunday_of_week]

# --- תצוגת סיכומים ---
st.markdown("---")
st.header("📊 סיכום נתונים")

col_week, col_month = st.columns(2)

# --- כרטיסייה שבועית ---
with col_week:
    st.subheader("📅 סיכום שבועי")
    w_actual = current_week_df['Actual'].sum()
    w_standard = current_week_df['Standard'].sum()
    w_balance = current_week_df['Balance'].sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("סה\"כ שעות", f"{w_actual:.2f}")
    m2.metric("תקן מצטבר", f"{w_standard:.2f}")
    m3.metric("מאזן שבועי", f"{w_balance:.2f}", delta_color="normal")

# --- כרטיסייה חודשית ---
with col_month:
    st.subheader("📆 סיכום חודשי")
    m_actual = current_month_df['Actual'].sum()
    m_standard = current_month_df['Standard'].sum()
    m_balance = current_month_df['Balance'].sum()
    
    m4, m5, m6 = st.columns(3)
    m4.metric("סה\"כ שעות", f"{m_actual:.2f}")
    m5.metric("תקן מצטבר", f"{m_standard:.2f}")
    m6.metric("מאזן חודשי", f"{m_balance:.2f}", delta_color="normal")

st.markdown("---")

# --- היסטוריה ---
st.subheader("📜 היסטוריה")

# עיצוב הטבלה (צביעת המאזן)
def highlight_balance(val):
    color = '#d4edda' if val > 0 else '#f8d7da' if val < 0 else ''
    return f'background-color: {color}; color: black'

# הצגת הטבלה
if not df.empty:
    st.dataframe(
        df.style.applymap(highlight_balance, subset=['Balance'])
        .format({"Actual": "{:.2f}", "Standard": "{:.2f}", "Balance": "{:.2f}"}),
        use_container_width=True,
        height=400
    )
else:
    st.info("אין נתונים להצגה עדיין.")