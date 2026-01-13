import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time, date
from streamlit_calendar import calendar

# --- הגדרות עמוד ---
st.set_page_config(page_title="מערכת דיווח שעות", page_icon="⏱️", layout="centered")

# --- CSS מתקדם ליישור מלא לימין ---
st.markdown("""
<style>
    /* 1. הגדרת כיוון כללית */
    .stApp {
        text-align: right;
    }

    /* 2. יישור כל הכותרות והטקסטים לימין */
    h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown, .stText, .stCaption, .stAlert, .stInfo, .stWarning, .stError, .stSuccess {
        text-align: right;
        direction: rtl;
    }
    
    /* 3. יישור תוכן של מדדים (Metrics) */
    div[data-testid="stMetric"] {
        direction: rtl;
        text-align: right;
        align-items: flex-end;
    }
    div[data-testid="stMetricLabel"] {
        text-align: right !important;
        width: 100%;
        direction: rtl;
    }
    div[data-testid="stMetricValue"] {
        text-align: right !important;
        direction: ltr;
        width: 100%;
    }

    /* 4. יישור שדות קלט */
    .stTextInput input, .stNumberInput input, .stTimeInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        direction: rtl;
        text-align: right;
    }
    
    /* 5. יישור תוויות */
    div[data-testid="stWidgetLabel"] {
        direction: rtl;
        text-align: right;
        width: 100%;
        display: flex;
        justify-content: flex-end;
    }

    /* 6. יישור טאבים */
    .stTabs [data-baseweb="tab-list"] {
        flex-direction: row-reverse;
        justify-content: flex-end;
    }
    
    /* 7. כותרת הלוח שנה */
    .fc-toolbar-title {
        font-family: sans-serif;
        text-align: center;
    }
    
    /* 8. טבלה */
    div[data-testid="stDataFrame"] {
        direction: rtl;
    }
    
    /* כפתורים בחלון דיאלוג */
    div[data-testid="stDialog"] button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

st.title("⏱️ מערכת דיווח שעות")

# --- טעינת נתונים ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    existing_data = conn.read(worksheet="Sheet1", ttl=0)
    df = pd.DataFrame(existing_data)
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    else:
        df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes"])

except Exception as e:
    st.error("שגיאה בטעינת הנתונים מהגוגל שיטס")
    df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes"])

# --- פונקציות עזר ---

def get_hebrew_day(py_date):
    days = {6: "א'", 0: "ב'", 1: "ג'", 2: "ד'", 3: "ה'", 4: "ו'", 5: "ש'"}
    return f"יום {days[py_date.weekday()]}"

def parse_time_input(time_str):
    if not time_str:
        return None
    try:
        clean_str = str(time_str).replace(":", "").replace(".", "").strip()
        if len(clean_str) <= 2: clean_str += "00"
        if len(clean_str) == 3: clean_str = "0" + clean_str
        if len(clean_str) == 4:
            h = int(clean_str[:2])
            m = int(clean_str[2:])
            if h > 23 or m > 59:
                return None
            return datetime.strptime(clean_str, "%H%M").time()
    except:
        return None
    return None

def float_to_time_str(hours_float):
    is_negative = hours_float < 0
    hours_float = abs(hours_float)
    hours = int(hours_float)
    minutes = int(round((hours_float - hours) * 60))
    if minutes == 60:
        hours += 1
        minutes = 0
    time_str = f"{hours}:{minutes:02d}"
    if is_negative:
        return f"-{time_str}"
    return time_str

def check_overlap(df, check_date, start_t, end_t):
    if df.empty:
        return False
        
    day_records = df[df['date'] == str(check_date)]
    if day_records.empty:
        return False

    new_start = datetime.combine(date.min, start_t)
    new_end = datetime.combine(date.min, end_t)

    for _, row in day_records.iterrows():
        try:
            exist_s = datetime.strptime(row['start_time'], "%H:%M:%S").time()
            exist_e = datetime.strptime(row['end_time'], "%H:%M:%S").time()
            
            curr_start = datetime.combine(date.min, exist_s)
            curr_end = datetime.combine(date.min, exist_e)

            if new_start < curr_end and new_end > curr_start:
                return True
        except:
            continue
    return False

def update_google_sheet(new_df):
    try:
        conn.update(worksheet="Sheet1", data=new_df)
        st.cache_data.clear()
        st.success("השינויים נשמרו בהצלחה! ✅")
        st.rerun()
    except Exception as e:
        st.error(f"שגיאה בשמירה: {e}")

# --- פונקציית דיאלוג למחיקה ---
@st.dialog("⚠️ אישור מחיקה")
def delete_confirmation_dialog(index_to_delete, date_str, start_s, end_s):
    st.write("### שימי לב!")
    st.write("את עומדת למחוק את הרשומה שבחרת:")
    
    # המרת תאריך לפורמט ישראלי להצגה
    fmt_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    
    st.markdown(f"**תאריך:** {fmt_date}")
    st.markdown(f"**שעת כניסה:** {start_s[:5]}")
    st.markdown(f"**שעת יציאה:** {end_s[:5]}")
    
    st.write("---")
    st.write("**האם את בטוחה שאת רוצה להמשיך?**")
    
    col_yes, col_no = st.columns(2)
    
    with col_yes:
        if st.button("✅ כן, מחק", type="primary", use_container_width=True):
            new_df = df.drop(index_to_delete)
            update_google_sheet(new_df)
            st.rerun()
            
    with col_no:
        if st.button("❌ לא, בטל", use_container_width=True):
            st.rerun()

# --- הגדרת הטאבים ---
tab_stats, tab_report, tab_manage = st.tabs(["📊 סיכומים ולוח שנה", "📝 דיווח חדש", "🛠️ ניהול ועריכה"])

# --- טאב 1: סיכומים ולוח שנה ---
with tab_stats:
    if df.empty:
        st.info("אין נתונים להצגה")
    else:
        events = []
        total_balance_week = 0.0
        total_balance_month = 0.0
        
        now = datetime.now()
        current_iso_week = now.isocalendar()[1]
        
        for _, row in df.iterrows():
            try:
                s = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                hours = (e - s).total_seconds() / 3600
                
                dt_obj = datetime.strptime(row['date'], '%Y-%m-%d')
                wd = dt_obj.weekday()
                target = 8.5 if wd == 3 else 9.0
                if wd in [4,5]: target = 0 
                
                balance = hours - target
                
                if dt_obj.year == now.year and dt_obj.month == now.month:
                    total_balance_month += balance
                
                if dt_obj.year == now.year and dt_obj.isocalendar()[1] == current_iso_week:
                    total_balance_week += balance

                bg_color = "#28a745" if balance >= 0 else "#dc3545"
                
                events.append({
                    "title": float_to_time_str(hours),
                    "start": row['date'],
                    "end": row['date'],
                    "backgroundColor": bg_color,
                    "borderColor": bg_color
                })
            except:
                continue

        col_right_stats, col_left_stats = st.columns(2)
        with col_right_stats: 
            st.metric("📅 מאזן שבועי (נוכחי)", float_to_time_str(total_balance_week))
        with col_left_stats: 
            st.metric("📆 מאזן חודשי (נוכחי)", float_to_time_str(total_balance_month))
            
        st.divider()

        cal_options = {
            "editable": False,
            "headerToolbar": {
                "left": "today prev,next",
                "center": "title",
                "right": "" 
            },
            "buttonText": {
                "today": "היום"
            },
            "initialView": "dayGridMonth",
            "locale": "he",
            "direction": "rtl",
            "height": 650
        }
        
        st.subheader("🗓️ לוח שנה")
        calendar(events=events, options=cal_options, key="main_calendar")
        
        st.divider()
        st.caption("פירוט רשומות:")
        
        display_df = df.copy()
        display_df = display_df.rename(columns={
            "date": "תאריך", "start_time": "כניסה", "end_time": "יציאה", "notes": "הערות"
        })
        st.dataframe(display_df.sort_values('תאריך', ascending=False), use_container_width=True, hide_index=True)

# --- טאב 2: דיווח חדש ---
with tab_report:
    col_date_right, col_info_left = st.columns([2, 1])
    
    with col_date_right:
        d = st.date_input("תאריך", date.today())
        st.caption(f"📅 {get_hebrew_day(d)}")
        
    with col_info_left:
        wd = d.weekday()
        if wd in [4, 5]:
            st.warning("סופ\"ש")
        else:
            target = 8.5 if wd == 3 else 9.0
            st.info(f"תקן: {target}")
            
    if not df.empty and str(d) in df['date'].values:
        st.info(f"💡 שים לב: כבר קיימים דיווחים לתאריך זה.")

    t1, t2 = st.tabs(["שעון", "הקלדה"])
    with t1:
        col_in_right, col_out_left = st.columns(2)
        with col_in_right: 
            c_in = st.time_input("כניסה", time(6,30), key="clock_in")
        with col_out_left: 
            c_out = st.time_input("יציאה", time(15,30), key="clock_out")
            
    with t2:
        col_in_txt, col_out_txt = st.columns(2)
        with col_in_txt: 
            s_in = st.text_input("כניסה (0630)", value="", placeholder="לדוגמה: 0630", key="txt_in")
        with col_out_txt: 
            s_out = st.text_input("יציאה (1530)", value="", placeholder="לדוגמה: 1530", key="txt_out")
    
    notes = st.text_input("הערות")
    
    if st.button("שמור דיווח", type="primary", use_container_width=True):
        final_start = None
        final_end = None
        
        is_manual_entry = (s_in.strip() != "") or (s_out.strip() != "")
        
        if is_manual_entry:
            if not s_in.strip() or not s_out.strip():
                st.error("⚠️ שגיאה: בהקלדה ידנית חובה למלא גם שעת כניסה וגם שעת יציאה.")
                st.stop()
            
            parsed_start = parse_time_input(s_in)
            parsed_end = parse_time_input(s_out)
            
            if parsed_start is None or parsed_end is None:
                st.error("⚠️ שגיאה: השעות שהוקלדו אינן תקינות.")
                st.stop()
                
            final_start = parsed_start
            final_end = parsed_end
        else:
            final_start = c_in
            final_end = c_out

        if final_start >= final_end:
            st.error("⚠️ שגיאה: שעת הכניסה חייבת להיות מוקדמת משעת היציאה.")
            st.stop()

        if check_overlap(df, d, final_start, final_end):
            st.error(f"⚠️ שגיאה: חפיפת שעות עם רשומה קיימת.")
            st.stop()

        new_row = pd.DataFrame([{
            "date": str(d),
            "start_time": str(final_start),
            "end_time": str(final_end),
            "notes": notes
        }])
        new_df = pd.concat([df, new_row], ignore_index=True)
        update_google_sheet(new_df)

# --- טאב 3: ניהול ועריכה ---
with tab_manage:
    if df.empty:
        st.info("אין נתונים לעריכה")
    else:
        dates_list = sorted(df['date'].unique(), reverse=True)
        sel_date = st.selectbox("בחר תאריך לעריכה", dates_list)
        
        daily_rows = df[df['date'] == sel_date].reset_index()
        
        if len(daily_rows) > 0:
            options = {i: f"{r['start_time'][:5]} - {r['end_time'][:5]} ({r['notes']})" for i, r in daily_rows.iterrows()}
            selected_idx = st.selectbox("בחר רשומה:", options.keys(), format_func=lambda x: options[x])
            
            curr_row = daily_rows.iloc[selected_idx]
            original_index = curr_row['index']
            
            try:
                t_s = datetime.strptime(str(curr_row['start_time']), "%H:%M:%S").time()
                t_e = datetime.strptime(str(curr_row['end_time']), "%H:%M:%S").time()
            except:
                t_s, t_e = time(6,30), time(15,30)
                
            with st.expander("עריכת פרטים / מחיקה", expanded=True):
                ec_in, ec_out = st.columns(2)
                with ec_in:
                    new_in = st.time_input("כניסה", t_s, key="edit_in")
                with ec_out:
                    new_out = st.time_input("יציאה", t_e, key="edit_out")
                    
                new_n = st.text_input("הערות", curr_row['notes'], key="edit_note")
                
                st.write("---") # קו מפריד
                
                # כפתורי פעולה: עדכון ומחיקה
                col_btn_update, col_btn_delete = st.columns([1, 1])
                
                with col_btn_update:
                    if st.button("💾 עדכן רשומה", use_container_width=True):
                        if new_in >= new_out:
                            st.error("שגיאה: כניסה אחרי יציאה")
                        else:
                            df_temp = df.drop(original_index)
                            if check_overlap(df_temp, sel_date, new_in, new_out):
                                st.error("שגיאה: העדכון יוצר חפיפה")
                            else:
                                upd_row = pd.DataFrame([{
                                    "date": sel_date,
                                    "start_time": str(new_in),
                                    "end_time": str(new_out),
                                    "notes": new_n
                                }])
                                new_df = pd.concat([df_temp, upd_row], ignore_index=True)
                                update_google_sheet(new_df)
                
                with col_btn_delete:
                    # שינוי: במקום צ'ק בוקס, קריאה לדיאלוג
                    if st.button("🗑️ מחק רשומה", type="secondary", use_container_width=True):
                        delete_confirmation_dialog(original_index, sel_date, str(curr_row['start_time']), str(curr_row['end_time']))