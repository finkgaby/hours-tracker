import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time, date, timedelta
import calendar as cal_lib
from streamlit_calendar import calendar
import time as time_lib

# --- הגדרות עמוד ---
st.set_page_config(page_title="מערכת דיווח שעות", page_icon="⏱️", layout="centered")

# ניהול זיכרון לצפייה בחודשים
if 'view_month' not in st.session_state:
    st.session_state.view_month = datetime.now().month
if 'view_year' not in st.session_state:
    st.session_state.view_year = datetime.now().year

# --- CSS מותאם ליישור לימין ועיצוב כללי ---
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
        background-color: #ff7675 !important;
        color: white !important;
        border: 1px solid #ff7675 !important;
        border-radius: 4px !important;
        font-weight: bold !important;
        height: 34px !important;
        min-width: 67px !important;
        font-size: 16px !important;
    }

    .status-card {
        padding: 12px;
        border-radius: 12px;
        text-align: center;
        color: white;
        font-weight: bold;
        direction: rtl;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .status-label { font-size: 0.85rem; margin-bottom: 4px; opacity: 0.95; }
    .status-value { font-size: 1.4rem; direction: ltr; letter-spacing: 1px; }
    
    th, td { text-align: right !important; padding: 8px !important; border-bottom: 1px solid #f0f2f6 !important; }
</style>
""", unsafe_allow_html=True)

st.title("⏱️ מערכת דיווח שעות")

# --- טעינת נתונים ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        existing_data = conn.read(worksheet="Sheet1", ttl=0)
        df = pd.DataFrame(existing_data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            df['type'] = df.get('type', 'עבודה').fillna('עבודה')
            df['start_time'] = df['start_time'].fillna("00:00:00").astype(str)
            df['end_time'] = df['end_time'].fillna("00:00:00").astype(str)
            df['notes'] = df.get('notes', '').fillna('')
        return df
    except:
        return pd.DataFrame(columns=["date", "start_time", "end_time", "notes", "type"])

df = load_data()

# --- פונקציות עזר ---
def format_time_display(val):
    try:
        t_parts = str(val).split(':')
        return f"{int(t_parts[0]):02d}:{int(t_parts[1]):02d}"
    except: return "00:00"

def float_to_time_str(hf):
    is_neg = hf < 0
    hf = abs(hf)
    h, m = int(hf), int(round((hf - int(hf)) * 60))
    if m == 60: h += 1; m = 0
    sign = "+" if not is_neg and hf > 0 else ("-" if is_neg else "")
    return f"{sign}{h}:{m:02d}"

def get_target_hours(dt):
    wd = dt.weekday()
    return 8.5 if wd == 3 else (0.0 if wd in [4, 5] else 9.0)

def get_status_card(label, diff_val):
    color = "#f39c12" if diff_val > 0 else ("#ff4b4b" if diff_val < 0 else "#28a745")
    return f"""<div class="status-card" style="background-color: {color};"><div class="status-label">{label}</div><div class="status-value">{float_to_time_str(diff_val)}</div></div>"""

def update_google_sheet(new_df, rerun=True):
    conn.update(worksheet="Sheet1", data=new_df)
    st.cache_data.clear()
    if rerun: st.rerun()

def render_metrics_and_nav(suffix):
    year, month = st.session_state.view_year, st.session_state.view_month
    m_target = sum(get_target_hours(date(year, month, d)) for d in range(1, cal_lib.monthrange(year, month)[1] + 1))
    
    today_dt = date.today()
    sun_curr = today_dt - timedelta(days=(today_dt.weekday() + 1) % 7)
    sat_curr = sun_curr + timedelta(days=6)
    w_target = sum(get_target_hours(sun_curr + timedelta(days=i)) for i in range(7))

    done_m, done_w = 0.0, 0.0
    events = []
    for _, row in df.iterrows():
        try:
            dt_obj = datetime.strptime(row['date'], '%Y-%m-%d')
            row_t = row.get('type', 'עבודה')
            hrs = 0.0
            if row_t == 'עבודה':
                s = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                hrs = (e - s).total_seconds() / 3600
                ev_color = "#28a745" if (hrs >= get_target_hours(dt_obj)) else "#dc3545"
                ev_title = format_time_display(row['start_time'])
            elif row_t == 'שבתון':
                hrs, ev_color, ev_title = 0.0, "#6f42c1", "שבתון"
                if dt_obj.year == year and dt_obj.month == month: m_target -= get_target_hours(dt_obj)
                if sun_curr <= dt_obj.date() <= sat_curr: w_target -= get_target_hours(dt_obj)
            else:
                hrs, ev_color, ev_title = get_target_hours(dt_obj), ("#007bff" if row_t == 'חופשה' else "#fd7e14"), row_t

            if dt_obj.year == year and dt_obj.month == month: done_m += hrs
            if sun_curr <= dt_obj.date() <= sat_curr: done_w += hrs
            events.append({"title": ev_title, "start": row['date'], "backgroundColor": ev_color, "borderColor": ev_color})
        except: continue

    st.markdown(f"### 🗓️ סיכום עבור {month}/{year}")
    c1, c2, c3 = st.columns(3)
    c1.metric("📋 תקן חודשי", f"{int(m_target)}:{int((m_target%1)*60):02d} ש'")
    c2.metric("✅ בוצע בחודש", f"{int(done_m)}:{int((done_m%1)*60):02d}")
    with c3: st.markdown(get_status_card("⚖️ מאזן חודשי", done_m - m_target), unsafe_allow_html=True)
    
    st.divider()
    st.markdown("#### 📅 מדדי שבוע נוכחי")
    w1, w2, w3 = st.columns(3)
    w1.metric("📊 תקן שבועי", f"{int(w_target)}:{int((w_target%1)*60):02d} ש'")
    w2.metric("⏱️ בוצע השבוע", f"{int(done_w)}:{int((done_w%1)*60):02d}")
    with w3: st.markdown(get_status_card("⚖️ מאזן שבועי", done_w - w_target), unsafe_allow_html=True)

    st.divider()
    col_nav, _ = st.columns([0.4, 0.6])
    with col_nav:
        sub_c1, sub_c2, sub_c3 = st.columns(3)
        if sub_c1.button("קודם", key=f"p_{suffix}"):
            st.session_state.view_month = 12 if st.session_state.view_month == 1 else st.session_state.view_month - 1
            if st.session_state.view_month == 12: st.session_state.view_year -= 1
            st.rerun()
        if sub_c3.button("היום", key=f"t_{suffix}"):
            st.session_state.view_month, st.session_state.view_year = datetime.now().month, datetime.now().year
            st.rerun()
        if sub_c2.button("הבא", key=f"n_{suffix}"):
            st.session_state.view_month = 1 if st.session_state.view_month == 12 else st.session_state.view_month + 1
            if st.session_state.view_month == 1: st.session_state.view_year += 1
            st.rerun()
    return events

# --- טאבים ---
tab_stats, tab_details, tab_report, tab_manage = st.tabs(["📊 סיכומים ולוח שנה", "📋 פירוט", "📝 דיווח חדש", "🛠️ ניהול ועריכה"])

with tab_stats:
    events = render_metrics_and_nav("stats")
    calendar(events=events, options={"initialView": "dayGridMonth", "locale": "he", "direction": "rtl", "initialDate": f"{st.session_state.view_year}-{st.session_state.view_month:02d}-01", "headerToolbar": {"left": "", "center": "title", "right": ""}}, key=f"cal_{st.session_state.view_year}_{st.session_state.view_month}")

with tab_details:
    render_metrics_and_nav("details")
    month_prefix = f"{st.session_state.view_year}-{st.session_state.view_month:02d}"
    m_data = df[df['date'].str.startswith(month_prefix)].copy().sort_values('date')
    if not m_data.empty:
        m_data['תאריך'] = pd.to_datetime(m_data['date']).dt.strftime('%d/%m/%Y')
        m_data['כניסה'] = m_data['start_time'].apply(format_time_display)
        m_data['יציאה'] = m_data['end_time'].apply(format_time_display)
        # הצגת טבלה ללא עמודת מספור
        st.markdown(m_data[['תאריך', 'type', 'כניסה', 'יציאה', 'notes']].rename(columns={'type': 'סוג', 'notes': 'הערה'}).to_html(index=False), unsafe_allow_html=True)
    else: st.info("אין נתונים לחודש זה")

with tab_report:
    st.subheader("📝 דיווח ידני")
    d_in = st.date_input("תאריך", date.today(), format="DD/MM/YYYY")
    r_t = st.radio("סוג", ["עבודה", "חופשה", "מחלה", "שבתון"], horizontal=True)
    st_t, en_t = time(0,0), time(0,0)
    if r_t == "עבודה":
        c1, c2 = st.columns(2)
        st_t = c1.time_input("כניסה", time(6,30))
        en_t = c2.time_input("יציאה", time(15,30))
    n_in = st.text_input("הערה", key="new_rep_note")
    if st.button("שמור דיווח", type="primary", use_container_width=True):
        new = pd.DataFrame([{"date": str(d_in), "start_time": f"{st_t}", "end_time": f"{en_t}", "notes": n_in, "type": r_t}])
        update_google_sheet(pd.concat([df[df['date'] != str(d_in)], new], ignore_index=True))

    st.divider()
    st.subheader("📂 טעינת קובץ אקסל")
    excel_file = st.file_uploader("בחר קובץ אקסל", type=["xlsx", "xls"])
    if excel_file:
        try:
            excel_df = pd.read_excel(excel_file)
            if st.button("🚀 טען ודרוס נתונים", use_container_width=True):
                pb = st.progress(0); st_txt = st.empty()
                new_entries = []; total_rows = len(excel_df)
                for i, row in excel_df.iterrows():
                    pb.progress((i+1)/total_rows); st_txt.text(f"מעבד שורה {i+1}...")
                    curr_d = pd.to_datetime(row['תאריך']).strftime('%Y-%m-%d')
                    def t_to_s(v):
                        if pd.isna(v): return "00:00:00"
                        if isinstance(v, time): return v.strftime('%H:%M:00')
                        return pd.to_datetime(v).strftime('%H:%M:00')
                    new_entries.append({"date": curr_d, "start_time": t_to_s(row['משעה']), "end_time": t_to_s(row.get('עד שעה', '00:00:00')), "notes": str(row.get('תיאור', '')), "type": "עבודה"})
                dates = [e['date'] for e in new_entries]
                update_google_sheet(pd.concat([df[~df['date'].isin(dates)], pd.DataFrame(new_entries)], ignore_index=True), rerun=False)
                st_txt.empty(); pb.empty(); st.balloons()
                st.success("✅ עדכון הסתיים!"); time_lib.sleep(3); st.rerun()
        except Exception as e: st.error(f"שגיאה: {e}")

with tab_manage:
    if not df.empty:
        st.subheader("🛠️ ניהול ועריכה")
        d_list = sorted(df['date'].unique())
        if 'last_manage_date' not in st.session_state: st.session_state.last_manage_date = d_list[-1]
        try: current_idx = d_list.index(st.session_state.last_manage_date)
        except: current_idx = len(d_list)-1
        s_date = st.selectbox("בחר תאריך", d_list, index=current_idx, format_func=lambda x: datetime.strptime(x, '%Y-%m-%d').strftime('%d/%m/%Y'))
        st.session_state.last_manage_date = s_date
        d_sub = df[df['date'] == s_date].copy().reset_index()
        def fmt(idx):
            r = d_sub.iloc[idx]
            return f"{r['type']} | {format_time_display(r['start_time'])}" if r['type'] == 'עבודה' else r['type']
        s_idx = st.selectbox("בחר רשומה", d_sub.index, format_func=fmt)
        curr = d_sub.iloc[s_idx]
        st.markdown("#### ✏️ עדכון")
        types = ["עבודה", "חופשה", "מחלה", "שבתון"]
        new_t = st.radio("סוג", types, index=types.index(curr['type']), horizontal=True, key=f"tr_{s_date}_{s_idx}")
        st_v, en_v = curr['start_time'], curr['end_time']
        if new_t == "עבודה":
            c1, c2 = st.columns(2)
            def t_obj(v): return datetime.strptime(str(v)[:8], "%H:%M:%S").time()
            st_v = c1.time_input("כניסה", value=t_obj(curr['start_time']), key=f"sin_{s_date}_{s_idx}")
            en_v = c2.time_input("יציאה", value=t_obj(curr['end_time']), key=f"eout_{s_date}_{s_idx}")
        new_n = st.text_input("הערה", value=curr['notes'], key=f"nedit_{s_date}_{s_idx}")
        if st.button("💾 שמור שינויים", type="primary", use_container_width=True, key=f"bsave_{s_date}_{s_idx}"):
            df.loc[curr['index'], ['type', 'start_time', 'end_time', 'notes']] = [new_t, str(st_v), str(en_v), new_n]
            update_google_sheet(df)
        if st.button("🗑️ מחק", use_container_width=True, key=f"bdel_{s_date}_{s_idx}"):
            update_google_sheet(df.drop(curr['index']))