import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time, date, timedelta
import calendar as cal_lib
from streamlit_calendar import calendar

# --- הגדרות עמוד ---
st.set_page_config(page_title="מערכת דיווח שעות", page_icon="⏱️", layout="centered")

# --- CSS מותאם ליישור לימין ---
st.markdown("""
<style>
    .stApp { text-align: right; }
    h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown, .stText, .stCaption, .stAlert, .stInfo, .stWarning, .stError, .stSuccess {
        text-align: right; direction: rtl;
    }
    div[data-testid="stMetric"] { direction: rtl; text-align: right; align-items: flex-end; }
    div[data-testid="stMetricLabel"] { text-align: right !important; width: 100%; direction: rtl; }
    div[data-testid="stMetricValue"] { text-align: right !important; direction: ltr; width: 100%; }
    .stTextInput input, .stTimeInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        direction: rtl; text-align: right;
    }
    div[data-testid="stWidgetLabel"] { direction: rtl; text-align: right; width: 100%; display: flex; justify-content: flex-end; }
    .stTabs [data-baseweb="tab-list"] { flex-direction: row-reverse; justify-content: flex-end; }
    .fc-toolbar-title { font-family: sans-serif; text-align: center; }
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
        if 'type' not in df.columns:
            df['type'] = 'עבודה'
        df['type'] = df['type'].fillna('עבודה')
    else:
        df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes", "type"])
except Exception as e:
    st.error("שגיאה בטעינת הנתונים")
    df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes", "type"])

# --- פונקציות עזר ---
def float_to_time_str(hours_float):
    is_neg = hours_float < 0
    hf = abs(hours_float)
    h, m = int(hf), int(round((hf - int(hf)) * 60))
    if m == 60: h += 1; m = 0
    res = f"{h}:{m:02d}"
    return f"-{res}" if is_neg else res

def get_target_hours(dt):
    """מחזיר תקן שעות ליום נתון (dt יכול להיות אובייקט date או datetime)"""
    wd = dt.weekday()
    # ב-Python: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    if wd == 3: return 8.5   # חמישי
    if wd in [4, 5]: return 0.0 # שישי שבת
    return 9.0               # ראשון עד רביעי

def get_monthly_target_total(year, month):
    total = 0.0
    num_days = cal_lib.monthrange(year, month)[1]
    for day in range(1, num_days + 1):
        total += get_target_hours(date(year, month, day))
    return total

def get_weekly_target_total():
    """מחשב תקן שבועי לשבוע הנוכחי (ראשון עד שבת)"""
    today = date.today()
    # מציאת יום ראשון הקרוב ביותר בעבר (או היום אם היום ראשון)
    # ב-weekday() של Python יום ראשון הוא 6. 
    # כדי להגיע לראשון: (today.weekday() + 1) % 7
    days_since_sunday = (today.weekday() + 1) % 7
    start_of_week = today - timedelta(days=days_since_sunday)
    
    total_weekly = 0.0
    for i in range(7):
        current_day = start_of_week + timedelta(days=i)
        total_weekly += get_target_hours(current_day)
    return total_weekly

def update_google_sheet(new_df):
    try:
        conn.update(worksheet="Sheet1", data=new_df)
        st.cache_data.clear()
        st.success("נשמר בהצלחה! ✅")
        st.rerun()
    except Exception as e: st.error(f"שגיאה בשמירה: {e}")

# --- הגדרת הטאבים ---
tab_stats, tab_report, tab_manage = st.tabs(["📊 סיכומים ולוח שנה", "📝 דיווח חדש", "🛠️ ניהול ועריכה"])

# --- טאב סטטיסטיקה ---
with tab_stats:
    events, total_done_month = [], 0.0
    now = datetime.now()
    monthly_target_total = get_monthly_target_total(now.year, now.month)
    weekly_target_total = get_weekly_target_total()
    
    for _, row in df.iterrows():
        try:
            dt = datetime.strptime(row['date'], '%Y-%m-%d')
            target = get_target_hours(dt)
            row_type = row.get('type', 'עבודה')
            if pd.isna(row_type): row_type = 'עבודה'

            if row_type == 'עבודה':
                if pd.isna(row['start_time']) or pd.isna(row['end_time']): continue
                s = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                hrs = (e - s).total_seconds() / 3600
                bal = hrs - target
                color = "#28a745" if bal >= 0 else "#dc3545"
                title = float_to_time_str(hrs)
            elif row_type == 'שבתון':
                hrs = 0.0
                color = "#6f42c1"
                title = "שבתון"
            else:
                hrs = target
                color = "#007bff" if row_type == 'חופשה' else "#fd7e14"
                title = row_type

            if dt.year == now.year and dt.month == now.month:
                total_done_month += hrs
            
            events.append({"title": title, "start": row['date'], "end": row['date'], "backgroundColor": color, "borderColor": color})
        except: continue
    
    # הצגת המטריקות בראש העמוד
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📋 תקן חודשי", f"{int(monthly_target_total)} ש'")
    m2.metric("📅 תקן שבועי", f"{weekly_target_total} ש'")
    m3.metric("✅ בוצע החודש", float_to_time_str(total_done_month))
    m4.metric("⏳ נותר לחודש", float_to_time_str(max(0, monthly_target_total - total_done_month)))
    
    st.divider()
    calendar(events=events, options={"headerToolbar": {"left": "today prev,next", "center": "title", "right": ""}, "initialView": "dayGridMonth", "locale": "he", "direction": "rtl", "height": 650}, key="main_cal")

# --- טאב דיווח ---
with tab_report:
    d = st.date_input("תאריך", date.today(), format="DD/MM/YYYY", key="rep_date")
    rtype = st.radio("סוג דיווח", ["עבודה", "חופשה", "מחלה", "שבתון"], horizontal=True, key="rep_type")
    
    ci, co = "00:00:00", "00:00:00"
    if rtype == "עבודה":
        c1, c2 = st.columns(2)
        ci = c1.time_input("כניסה", time(6,30), key="rep_in")
        co = c2.time_input("יציאה", time(15,30), key="rep_out")
    
    notes = st.text_input("הערות", key="rep_notes")
    if st.button("שמור דיווח", type="primary", use_container_width=True):
        new_row = pd.DataFrame([{"date": str(d), "start_time": str(ci), "end_time": str(co), "notes": notes, "type": rtype}])
        update_google_sheet(pd.concat([df, new_row], ignore_index=True))

# --- טאב ניהול ---
with tab_manage:
    if df.empty: st.info("אין נתונים")
    else:
        dates_list = sorted(df['date'].unique(), reverse=True)
        sel_d = st.selectbox(
            "בחר תאריך לעריכה", 
            dates_list, 
            format_func=lambda x: datetime.strptime(x, '%Y-%m-%d').strftime('%d/%m/%Y'), 
            key="man_date"
        )
        
        d_rows = df[df['date'] == sel_d].reset_index()
        
        def format_row(x):
            r = d_rows.iloc[x]
            if r['type'] == 'עבודה':
                clean_time = ":".join(str(r['start_time']).split(":")[:2])
                return f"עבודה | {clean_time}"
            return str(r['type'])
            
        sel_idx = st.selectbox("בחר רשומה לעריכה", d_rows.index, format_func=format_row, key="man_row")
        curr = d_rows.iloc[sel_idx]
        
        with st.expander("שינוי פרטים / מחיקה", expanded=True):
            options = ["עבודה", "חופשה", "מחלה", "שבתון"]
            curr_t = curr['type'] if curr['type'] in options else "עבודה"
            
            new_type = st.radio(
                "סוג דיווח:", 
                options, 
                index=options.index(curr_t), 
                key=f"edit_type_{sel_d}_{sel_idx}"
            )
            
            edit_ci, edit_co = str(curr['start_time']), str(curr['end_time'])
            
            if new_type == "עבודה":
                c1, c2 = st.columns(2)
                try:
                    ti = datetime.strptime(str(curr['start_time']), "%H:%M:%S").time()
                    to = datetime.strptime(str(curr['end_time']), "%H:%M:%S").time()
                except: ti, to = time(6,30), time(15,30)
                
                edit_ci = c1.time_input("כניסה מעודכנת", ti, key=f"edit_in_{sel_d}_{sel_idx}")
                edit_co = c2.time_input("יציאה מעודכנת", to, key=f"edit_out_{sel_d}_{sel_idx}")
            else:
                edit_ci, edit_co = "00:00:00", "00:00:00"
            
            new_n = st.text_input("הערות", "" if pd.isna(curr['notes']) else curr['notes'], key=f"edit_notes_{sel_d}_{sel_idx}")
            
            st.divider()
            b1, b2 = st.columns(2)
            if b1.button("💾 עדכן שינויים", use_container_width=True, key=f"btn_upd_{sel_d}_{sel_idx}"):
                df.loc[curr['index'], ['type', 'start_time', 'end_time', 'notes']] = [new_type, str(edit_ci), str(edit_co), new_n]
                update_google_sheet(df)
            
            if b2.button("🗑️ מחק רשומה", type="secondary", use_container_width=True, key=f"btn_del_{sel_d}_{sel_idx}"):
                update_google_sheet(df.drop(curr['index']))