import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time, timedelta

# --- הגדרות עמוד ---
st.set_page_config(page_title="דיווח שעות - גבי", page_icon="⏱️", layout="centered")
st.title("⏱️ מערכת דיווח שעות")

# --- חיבור לגוגל שיטס ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # קריאה ללא מטמון (ttl=0) כדי לראות שינויים מיד
    existing_data = conn.read(worksheet="Sheet1", ttl=0)
    df = pd.DataFrame(existing_data)
    # ווידוא שיש עמודות גם אם הקובץ ריק
    if df.empty:
        df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes"])
    else:
        # המרת עמודת התאריך לטקסט אחיד כדי למנוע בעיות
        df['date'] = df['date'].astype(str)
        
except Exception as e:
    st.error(f"שגיאה בחיבור לגוגל שיטס: {e}")
    df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes"])

# --- פונקציות עזר ---
def calculate_target_hours(date_obj):
    """חישוב תקן שעות יומי"""
    wd = date_obj.weekday() # 0=Mon, 6=Sun
    if wd == 6 or wd in [0, 1, 2]: # א, ב, ג, ד
        return 9.0
    elif wd == 3: # יום ה
        return 8.5
    return 0.0

def parse_time_input(time_str):
    """המרה חכמה של הקלדה ידנית לשעה"""
    try:
        clean_str = str(time_str).replace(":", "").replace(".", "").strip()
        if len(clean_str) <= 2: clean_str += "00" # 9 -> 900
        if len(clean_str) == 3: clean_str = "0" + clean_str # 930 -> 0930
        if len(clean_str) == 4:
            return datetime.strptime(clean_str, "%H%M").time()
    except:
        return None
    return None

def update_google_sheet(new_df):
    """פונקציה מרכזית לעדכון הגליון"""
    try:
        conn.update(worksheet="Sheet1", data=new_df)
        st.cache_data.clear() # ניקוי זיכרון כדי לראות את השינוי
        st.success("הנתונים עודכנו בהצלחה! ✅")
        st.rerun()
    except Exception as e:
        st.error(f"שגיאה בשמירה: {e}")

# --- לוגיקה ראשית ---
# יצירת לשוניות ראשיות
tab_report, tab_manage, tab_stats = st.tabs(["📝 דיווח חדש", "🛠️ ניהול ועריכה", "📊 סיכומים ודוחות"])

# --- לשונית 1: דיווח חדש ---
with tab_report:
    st.caption("הזנת דיווח יומי")
    
    col_d1, col_d2 = st.columns([2, 1])
    with col_d1:
        input_date = st.date_input("תאריך", datetime.now())
    
    # בדיקה האם התאריך כבר קיים
    date_exists = False
    if not df.empty and str(input_date) in df['date'].values:
        date_exists = True
        st.warning("⚠️ שים לב: כבר קיים דיווח לתאריך זה. עבור ללשונית 'ניהול' לעריכה.")

    # כלי בחירת שעות (טאבים פנימיים)
    t_clock, t_type = st.tabs(["⏰ שעון", "⌨️ הקלדה"])
    with t_clock:
        c_start = st.time_input("כניסה", time(9, 0), step=60, key="c_s")
        c_end = st.time_input("יציאה", time(18, 0), step=60, key="c_e")
    with t_type:
        m_start = st.text_input("כניסה (לדוגמה 0900)", value="09:00", key="m_s")
        m_end = st.text_input("יציאה (לדוגמה 1800)", value="18:00", key="m_e")
    
    notes = st.text_input("הערות")

    if st.button("שמור דיווח", type="primary", use_container_width=True, disabled=date_exists):
        # בחירת השעה (ידני או שעון)
        final_start = parse_time_input(m_start) if parse_time_input(m_start) else c_start
        final_end = parse_time_input(m_end) if parse_time_input(m_end) else c_end
        
        new_row = pd.DataFrame([{
            "date": str(input_date),
            "start_time": str(final_start),
            "end_time": str(final_end),
            "notes": notes
        }])
        
        updated_df = pd.concat([df, new_row], ignore_index=True)
        update_google_sheet(updated_df)

# --- לשונית 2: ניהול ועריכה ---
with tab_manage:
    st.caption("עריכה או מחיקה של דיווחים קיימים")
    
    if df.empty:
        st.info("אין עדיין נתונים לניהול.")
    else:
        # מיון תאריכים מהחדש לישן לבחירה נוחה
        sorted_dates = sorted(df['date'].unique(), reverse=True)
        selected_date_str = st.selectbox("בחר תאריך לעריכה:", sorted_dates)
        
        # שליפת הנתונים של התאריך הנבחר
        current_row = df[df['date'] == selected_date_str].iloc[0]
        
        with st.expander("✏️ ערוך נתונים", expanded=True):
            edit_col1, edit_col2 = st.columns(2)
            
            # המרת מחרוזות חזרה לאובייקטים של זמן
            try:
                t_s = datetime.strptime(current_row['start_time'], "%H:%M:%S").time()
                t_e = datetime.strptime(current_row['end_time'], "%H:%M:%S").time()
            except:
                t_s, t_e = time(9,0), time(18,0)

            new_start = edit_col1.time_input("שינוי כניסה", t_s, step=60)
            new_end = edit_col2.time_input("שינוי יציאה", t_e, step=60)
            new_notes = st.text_input("שינוי הערות", current_row['notes'])
            
            col_save, col_del = st.columns([3, 1])
            
            if col_save.button("עדכן רשומה", use_container_width=True):
                # מחיקת השורה הישנה והוספת החדשה
                df_temp = df[df['date'] != selected_date_str].copy()
                updated_row = pd.DataFrame([{
                    "date": selected_date_str,
                    "start_time": str(new_start),
                    "end_time": str(new_end),
                    "notes": new_notes
                }])
                final_df = pd.concat([df_temp, updated_row], ignore_index=True)
                update_google_sheet(final_df)

            if col_del.button("🗑️ מחק", type="primary", use_container_width=True):
                # מחיקת השורה ושמירה
                final_df = df[df['date'] != selected_date_str]
                update_google_sheet(final_df)

# --- לשונית 3: סיכומים ודוחות ---
with tab_stats:
    if not df.empty:
        # חישובים
        calc_df = df.copy()
        calc_df['date_obj'] = pd.to_datetime(calc_df['date'])
        
        def get_hours(row):
            try:
                s = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                return (e - s).total_seconds() / 3600
            except: return 0

        calc_df['hours_worked'] = calc_df.apply(get_hours, axis=1)
        calc_df['target'] = calc_df['date_obj'].apply(calculate_target_hours)
        calc_df['delta'] = calc_df['hours_worked'] - calc_df['target']
        
        # --- סיכום שבועי (הפיצ'ר החדש!) ---
        st.subheader("📅 סיכום שבועי (נוכחי)")
        current_iso_week = datetime.now().isocalendar()[1]
        current_year = datetime.now().year
        
        # סינון לשבוע הנוכחי
        weekly_df = calc_df[
            (calc_df['date_obj'].dt.isocalendar().week == current_iso_week) & 
            (calc_df['date_obj'].dt.year == current_year)
        ]
        
        w_col1, w_col2, w_col3 = st.columns(3)
        w_col1.metric("שעות השבוע", f"{weekly_df['hours_worked'].sum():.2f}")
        w_col2.metric("תקן שבועי", f"{weekly_df['target'].sum():.2f}")
        w_col3.metric("מאזן שבועי", f"{weekly_df['delta'].sum():.2f}", 
                     delta_color="normal")

        st.divider()

        # --- סיכום חודשי ---
        st.subheader(f"📆 סיכום חודש {datetime.now().month}")
        current_month = datetime.now().month
        monthly_df = calc_df[calc_df['date_obj'].dt.month == current_month]
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("שעות החודש", f"{monthly_df['hours_worked'].sum():.2f}")
        m_col2.metric("תקן חודשי", f"{monthly_df['target'].sum():.2f}")
        m_col3.metric("מאזן חודשי", f"{monthly_df['delta'].sum():.2f}", 
                     delta_color="normal")

        # --- טבלה מפורטת ---
        st.divider()
        st.subheader("היסטוריה")
        
        display_df = calc_df.sort_values('date_obj', ascending=False)
        final_view = display_df[['date', 'start_time', 'end_time', 'hours_worked', 'target', 'delta', 'notes']].rename(columns={
            'date': 'תאריך', 'start_time': 'כניסה', 'end_time': 'יציאה', 
            'hours_worked': 'בפועל', 'target': 'תקן', 'delta': 'הפרש', 'notes': 'הערות'
        })
        
        def color_delta(val):
            color = '#d4edda' if val >= 0 else '#f8d7da'
            return f'background-color: {color}'

        st.dataframe(
            final_view.style.map(color_delta, subset=['הפרש']).format("{:.2f}", subset=['בפועל', 'תקן', 'הפרש']),
            use_container_width=True
        )
    else:
        st.info("אין נתונים להצגה בדוחות")