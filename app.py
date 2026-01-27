import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time, date, timedelta
import calendar as cal_lib
from streamlit_calendar import calendar
import time as time_lib

# --- הגדרות עמוד ---
st.set_page_config(page_title="מערכת דיווח שעות", page_icon="⏱️", layout="centered")

# ניהול Session State לניווט
if 'view_month' not in st.session_state:
    st.session_state.view_month = datetime.now().month
if 'view_year' not in st.session_state:
    st.session_state.view_year = datetime.now().year

# --- CSS מותאם ליישור לימין ועיצוב ---
st.markdown("""
<style>
    .stApp { text-align: right; }
    h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown, .stText, .stCaption, .stAlert, .stInfo, .stWarning, .stError, .stSuccess {
        text-align: right; direction: rtl;
    }
    div[data-testid="stMetric"] { direction: rtl; text-align: right; align-items: flex-end; }
    div[data-testid="stMetricLabel"] { text-align: right !important; width: 100%; direction: rtl; }
    div[data-testid="stMetricValue"] { text-align: right !important; direction: ltr; width: 100%; }
    .stTabs [data-baseweb="tab-list"] { flex-direction: row-reverse; justify-content: flex-end; }
    .fc-toolbar-title { font-family: sans-serif; text-align: center; }
    .stButton > button {
        background-color: #ff7675 !important; color: white !important; border: 1px solid #ff7675 !important;
        border-radius: 4px !important; font-weight: bold !important; height: 34px !important;
    }
    .status-card {
        padding: 12px; border-radius: 12px; text-align: center; color: white; font-weight: bold; direction: rtl; margin-bottom: 10px;
    }
    th, td { text-align: right !important; padding: 8px !important; border-bottom: 1px solid #f0f2f6 !important; }
    
    .selected-date-info {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-right: 5px solid #ff7675;
        margin-top: 10px;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)

st.title("⏱️ מערכת דיווח שעות")

# --- טעינת נתונים ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        existing_data = conn.read(worksheet="Sheet1", ttl=600)
        df = pd.DataFrame(existing_data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            df['type'] = df.get('type', 'עבודה').fillna('עבודה')
            df['start_time'] = df['start_time'].fillna("00:00:00").astype(str)
            df['end_time'] = df['end_time'].fillna("00:00:00").astype(str)
            df['notes'] = df.get('notes', '').fillna('')
        return df
    except Exception as e:
        if "429" in str(e):
            st.error("⚠️ חריגה ממכסת הבקשות לגוגל. המתן 2-3 דקות.")
        return pd.DataFrame(columns=["date", "start_time", "end_time", "notes", "type"])

df = load_data()

# --- פונקציות עזר ---
def format_time_display(val):
    try:
        parts = str(val).split(':')
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    except: return "00:00"

def float_to_time_str(hf):
    is_neg = hf < 0
    hf = abs(hf)
    h, m = int(hf), int(round((hf - int(hf)) * 60))
    if m == 60: h += 1; m = 0
    sign = "-" if is_neg else "+"
    if h == 0 and m == 0: sign = ""
    return f"{sign}{h}:{m:02d}"

def get_target_hours(dt):
    wd = dt.weekday()
    return 9.0 if wd in [6, 0, 1, 2] else (8.5 if wd == 3 else 0.0)

def get_status_card(label, diff_val):
    color = "#f39c12" if diff_val > 0 else ("#ff4b4b" if diff_val < 0 else "#28a745")
    return f"""
    <div class="status-card" style="background-color: {color};">
        <div style="font-size:0.85rem;">{label}</div>
        <div style="direction: ltr; unicode-bidi: bidi-override;">{float_to_time_str(diff_val)}</div>
    </div>"""

def update_google_sheet(new_df, rerun=True):
    conn.update(worksheet="Sheet1", data=new_df)
    st.cache_data.clear()
    if rerun:
        st.rerun()

def render_metrics_and_nav(suffix):
    year, month = st.session_state.view_year, st.session_state.view_month
    today_dt = date.today()
    
    # הצגת תיבת הסימון
    include_today = st.checkbox("כולל היום", value=True, key=f"inc_today_{suffix}")
    calc_limit_date = today_dt if include_today else (today_dt - timedelta(days=1))
    
    # 1. חישוב תקן חודשי מלא (תמיד כל החודש)
    m_target = sum(get_target_hours(date(year, month, d)) for d in range(1, cal_lib.monthrange(year, month)[1] + 1))
    
    # 2. חישוב תקן עד היום/אתמול (MTD)
    target_until_limit = 0.0
    if year < today_dt.year or (year == today_dt.year and month < today_dt.month):
        target_until_limit = m_target
    elif year == today_dt.year and month == today_dt.month:
        target_until_limit = sum(get_target_hours(date(year, month, d)) for d in range(1, calc_limit_date.day + 1)) if calc_limit_date.month == month else 0.0
    
    # 3. חישוב תקן שבועי (תמיד כל השבוע הנוכחי, ללא קשר לצ'קבוקס)
    sun_curr = today_dt - timedelta(days=(today_dt.weekday() + 1) % 7)
    sat_curr = sun_curr + timedelta(days=6)
    w_target = sum(get_target_hours(sun_curr + timedelta(days=i)) for i in range(7))

    done_m, done_w, done_until_limit = 0.0, 0.0, 0.0
    events = []
    
    for _, row in df.iterrows():
        try:
            dt_obj = datetime.strptime(row['date'], '%Y-%m-%d')
            curr_date = dt_obj.date()
            row_t = row.get('type', 'עבודה')
            hrs = 0.0
            
            # חישוב שעות ליום בודד
            if row_t == 'עבודה':
                s_t = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e_t = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                hrs = (e_t - s_t).total_seconds() / 3600
                ev_color = "#28a745" if (hrs >= get_target_hours(dt_obj)) else "#dc3545"
                ev_title = f"{int(hrs)}:{int((hrs%1)*60):02d}"
            elif row_t == 'שבתון':
                hrs = 0.0
                ev_color, ev_title = "#6f42c1", "שבתון"
                if curr_date.year == year and curr_date.month == month: 
                    m_target -= get_target_hours(dt_obj)
                    if curr_date <= calc_limit_date: target_until_limit -= get_target_hours(dt_obj)
                if sun_curr <= curr_date <= sat_curr: w_target -= get_target_hours(dt_obj)
            else:
                hrs, ev_color, ev_title = get_target_hours(dt_obj), ("#007bff" if row_t == 'חופשה' else "#fd7e14"), row_t

            # צבירה למדדים
            if curr_date.year == year and curr_date.month == month: 
                # בוצע חודש מושפע כעת מהצ'קבוקס (עד היום או עד אתמול)
                if curr_date <= calc_limit_date:
                    done_m += hrs
                    done_until_limit += hrs
            
            # בוצע שבוע מושפע מהצ'קבוקס (עד היום או עד אתמול בתוך השבוע)
            if sun_curr <= curr_date <= sat_curr:
                if curr_date <= calc_limit_date:
                    done_w += hrs
            
            events.append({"title": ev_title, "start": row['date'], "backgroundColor": ev_color, "borderColor": ev_color, "id": row['date']})
        except: continue

    st.markdown(f"### 🗓️ סיכום עבור {month}/{year}")
    
    # שורה ראשונה: מאזנים
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1: st.markdown(get_status_card("מאזן חודשי", done_m - m_target), unsafe_allow_html=True)
    with m_col2: st.markdown(get_status_card("מאזן עד היום", done_until_limit - target_until_limit), unsafe_allow_html=True)
    with m_col3: st.markdown(get_status_card("מאזן שבועי", done_w - w_target), unsafe_allow_html=True)
    
    # שורה שנייה: תקנים
    t1, t2, t3 = st.columns(3)
    t1.metric("תקן חודשי", float_to_time_str(m_target).replace('+', ''))
    t2.metric("תקן עד היום", float_to_time_str(target_until_limit).replace('+', ''))
    t3.metric("תקן שבועי", float_to_time_str(w_target).replace('+', ''))
    
    # שורה שלישית: ביצוע
    b1, b2 = st.columns(2)
    b1.metric("בוצע החודש", float_to_time_str(done_m).replace('+', ''))
    b2.metric("בוצע השבוע", float_to_time_str(done_w).replace('+', ''))

    st.divider()
    col_nav, _ = st.columns([0.4, 0.6])
    with col_nav:
        sub1, sub2, sub3 = st.columns(3)
        if sub1.button("קודם", key=f"p_{suffix}"):
            if st.session_state.view_month == 1:
                st.session_state.view_month = 12; st.session_state.view_year -= 1
            else: st.session_state.view_month -= 1
            st.rerun()
        if sub2.button("היום", key=f"t_{suffix}"):
            st.session_state.view_month, st.session_state.view_year = today_dt.month, today_dt.year
            st.rerun()
        if sub3.button("הבא", key=f"n_{suffix}"):
            if st.session_state.view_month == 12:
                st.session_state.view_month = 1; st.session_state.view_year += 1
            else: st.session_state.view_month += 1
            st.rerun()
    return events

# --- שאר הטאבים נותרים ללא שינוי מקוד הבסיס ---
tab_stats, tab_details, tab_report, tab_manage = st.tabs(["📊 סיכומים", "📋 פירוט", "📝 דיווח", "🛠️ ניהול"])

with tab_stats:
    evs = render_metrics_and_nav("stats")
    calendar(events=evs, options={"initialView": "dayGridMonth", "locale": "he", "direction": "rtl", "initialDate": f"{st.session_state.view_year}-{st.session_state.view_month:02d}-01", "headerToolbar": {"left": "", "center": "title", "right": ""}}, key=f"cal_main")

# ... (יתר הקוד של הטאבים מהגרסה היציבה שלך)