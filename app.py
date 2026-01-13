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
    existing_data = conn.read(worksheet="Sheet1", ttl=0)
    df = pd.DataFrame(existing_data)
    if df.empty:
        df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes"])
    else:
        df['date'] = df['date'].astype(str)
except Exception as e:
    st.error(f"שגיאה בחיבור לגוגל שיטס: {e}")
    df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes"])

# --- פונקציות עזר ---
def get_hebrew_day(date_obj):
    """המרת יום בשבוע לעברית"""
    days = {6: "א'", 0: "ב'", 1: "ג'", 2: "ד'", 3: "ה'", 4: "ו'", 5: "ש'"}
    return f"יום {days[date_obj.weekday()]}"

def calculate_target_hours(date_obj):
    """חישוב תקן שעות יומי"""
    wd = date_obj.weekday() 
    if wd == 6 or wd in [0, 1, 2]: # א, ב, ג, ד
        return 9.0
    elif wd == 3: # יום ה
        return 8.5
    return 0.0

def parse_time_input(time_str):
    """המרה חכמה של הקלדה ידנית לשעה"""
    try:
        clean_str = str(time_str).replace(":", "").replace(".", "").strip()
        if len(clean_str) <= 2: clean_str += "00"
        if len(clean_str) == 3: clean_str = "0" + clean_str
        if len(clean_str) == 4:
            return datetime.strptime(clean_str, "%H%M").time()
    except:
        return None
    return None

def update_google_sheet(new_df):
    try:
        conn.update(worksheet="Sheet1", data=new_df)
        st.cache_data.clear()
        st.success("הנתונים עודכנו בהצלחה! ✅")
        st.rerun()
    except Exception as e:
        st.error(f"שגיאה בשמירה: {e}")

# --- לוגיקה ראשית ---
tab_report, tab_manage, tab_stats = st.tabs(["📝 דיווח חדש", "🛠️ ניהול ועריכה", "📊 סיכומים ודוחות"])

# --- לשונית 1: דיווח חדש ---
with tab_report:
    st.caption("הזנת דיווח יומי")
    col_d1, col_d2 = st.columns([2, 1])
    with col_d1:
        input_date = st.date_input("תאריך", datetime.now())
        # הצגת היום הנבחר בצורה ויזואלית
        st.caption(f"📅 {get_hebrew_day(input_date)}")
    
    date_exists = False
    if not df.empty and str(input_date) in df['date'].values:
        date_exists = True
        st.warning(f"⚠️ קיים כבר דיווח לתאריך {input_date} ({get_hebrew_day(input_date)})")

    t_clock, t_type = st.tabs(["⏰ שעון", "⌨️ הקלדה"])
    with t_clock:
        c_start = st.time_input("כניסה", time(9, 0), step=60, key="c_s")
        c_end = st.time_input("יציאה", time(18, 0), step=60, key="c_e")
    with t_type:
        m_start = st.text_input("כניסה (0900)", value="09:00", key="m_s")
        m_end = st.text_input("יציאה (1800)", value="18:00", key="m_e")
    
    notes = st.text_input("הערות")

    if st.button("שמור דיווח", type="primary", use_container_width=True, disabled=date_exists):
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
    st.caption("עריכה או מחיקה")
    if df.empty:
        st.info("אין נתונים.")
    else:
        # יצירת רשימה יפה לבחירה עם ימים בעברית
        df_temp = df.copy()
        df_temp['date_obj'] = pd.to_datetime(df_temp['date'])
        # יצירת עמודת תצוגה: "2024-01-01 (יום ב')"
        df_temp['display'] = df_temp.apply(
            lambda x: f"{x['date']} ({get_hebrew_day(x['date_obj'])})", axis=1
        )
        # מיון לפי תאריך
        df_temp = df_temp.sort_values('date_obj', ascending=False)
        
        # בחירה מתוך הרשימה המעוצבת
        selected_display = st.selectbox("בחר תאריך לעריכה:", df_temp['display'].unique())
        
        # חילוץ התאריך המקורי מתוך התצוגה (החלק לפני הרווח הראשון)
        selected_date_str = selected_display.split(" ")[0]
        
        current_row = df[df['date'] == selected_date_str].iloc[0]
        
        with st.expander("✏️ ערוך נתונים", expanded=True):
            edit_col1, edit_col2 = st.columns(2)
            try:
                t_s = datetime.strptime(current_row['start_time'], "%H:%M:%S").time()
                t_e = datetime.strptime(current_row['end_time'], "%H:%M:%S").time()
            except:
                t_s, t_e = time(9,0), time(18,0)

            new_start = edit_col1.time_input("שינוי כניסה", t_s, step=60)
            new_end = edit_col2.time_input("שינוי יציאה", t_e, step=60)
            new_notes = st.text_input("שינוי הערות", current_row['notes'])
            
            col_save, col_del = st.columns([3, 1])
            
            if col_save.button("עדכן", use_container_width=True):
                updated_row = pd.DataFrame([{
                    "date": selected_date_str,
                    "start_time": str(new_start),
                    "end_time": str(new_end),
                    "notes": new_notes
                }])
                # הסרת הישן והוספת החדש
                final_df = df[df['date'] != selected_date_str]
                final_df = pd.concat([final_df, updated_row], ignore_index=True)
                update_google_sheet(final_df)

            if col_del.button("🗑️ מחק", type="primary", use_container_width=True):
                final_df = df[df['date'] != selected_date_str]
                update_google_sheet(final_df)

# --- לשונית 3: סיכומים ---
with tab_stats:
    if not df.empty:
        calc_df = df.copy()
        calc_df['date_obj'] = pd.to_datetime(calc_df['date'])
        
        # הוספת עמודת יום בשבוע לחישובים ולתצוגה
        calc_df['day_name'] = calc_df['date_obj'].apply(get_hebrew_day)

        def get_hours(row):
            try:
                s = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                return (e - s).total_seconds() / 3600
            except: return 0

        calc_df['hours_worked'] = calc_df.apply(get_hours, axis=1)
        calc_df['target'] = calc_df['date_obj'].apply(calculate_target_hours)
        calc_df['delta'] = calc_df['hours_worked'] - calc_df['target']
        
        # סיכום שבועי
        st.subheader("📅 סיכום שבועי")
        current_iso_week = datetime.now().isocalendar()[1]
        weekly_df = calc_df[calc_df['date_obj'].dt.isocalendar().week == current_iso_week]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("סה\"כ שעות", f"{weekly_df['hours_worked'].sum():.2f}")
        c2.metric("תקן", f"{weekly_df['target'].sum():.2f}")
        c3.metric("מאזן", f"{weekly_df['delta'].sum():.2f}", delta_color="normal")

        st.divider()

        # טבלה היסטורית
        st.subheader("היסטוריה")
        display_df = calc_df.sort_values('date_obj', ascending=False)
        
        # סידור העמודות לתצוגה יפה
        final_view = display_df[[
            'date', 'day_name', 'start_time', 'end_time', 
            'hours_worked', 'target', 'delta', 'notes'
        ]].rename(columns={
            'date': 'תאריך', 
            'day_name': 'יום', 
            'start_time': 'כניסה', 
            'end_time': 'יציאה', 
            'hours_worked': 'בפועל', 
            'target': 'תקן', 
            'delta': 'הפרש', 
            'notes': 'הערות'
        })
        
        def color_delta(val):
            color = '#d4edda' if val >= 0 else '#f8d7da'
            return f'background-color: {color}'

        st.dataframe(
            final_view.style.map(color_delta, subset=['הפרש']).format("{:.2f}", subset=['בפועל', 'תקן', 'הפרש']),
            use_container_width=True,
            hide_index=True  # הסתרת המספור בצד שמאל
        )
    else:
        st.info("אין נתונים להצגה")