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
    }
</style>
""", unsafe_allow_html=True)

st.title("⏱️ מערכת דיווח שעות")

# --- טעינת נתונים (Cache מבוקר למניעת שגיאת 429) ---
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
    # ראשון-רביעי (0-3): 9 שעות, חמישי (4): 8.5 שעות
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
                s_t = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e_t = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                hrs = (e_t - s_t).total_seconds() / 3600
                ev_color = "#28a745" if (hrs >= get_target_hours(dt_obj)) else "#dc3545"
                ev_title = f"{int(hrs)}:{int((hrs%1)*60):02d}"
            elif row_t == 'שבתון':
                hrs, ev_color, ev_title = 0.0, "#6f42c1", "שבתון"
                if dt_obj.year == year and dt_obj.month == month: m_target -= get_target_hours(dt_obj)
                if str(sun_curr) <= row['date'] <= str(sat_curr): w_target -= get_target_hours(dt_obj)
            else:
                hrs, ev_color, ev_title = get_target_hours(dt_obj), ("#007bff" if row_t == 'חופשה' else "#fd7e14"), row_t

            if dt_obj.year == year and dt_obj.month == month: done_m += hrs
            if str(sun_curr) <= row['date'] <= str(sat_curr): done_w += hrs
            events.append({"title": ev_title, "start": row['date'], "backgroundColor": ev_color, "borderColor": ev_color, "id": row['date']})
        except: continue

    st.markdown(f"### 🗓️ סיכום עבור {month}/{year}")
    c1, c2, c3 = st.columns(3)
    c1.metric("📋 תקן חודשי", f"{int(m_target)}:{int((m_target%1)*60):02d}")
    c2.metric("✅ בוצע חודש", f"{int(done_m)}:{int((done_m%1)*60):02d}")
    with c3: st.markdown(get_status_card("⚖️ מאזן חודשי", done_m - m_target), unsafe_allow_html=True)
    
    st.divider()
    w1, w2, w3 = st.columns(3)
    w1.metric("📊 תקן שבועי", f"{int(w_target)}:{int((w_target%1)*60):02d}")
    w2.metric("⏱️ בוצע שבוע", f"{int(done_w)}:{int((done_w%1)*60):02d}")
    with w3: st.markdown(get_status_card("⚖️ מאזן שבועי", done_w - w_target), unsafe_allow_html=True)

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
            st.session_state.view_month, st.session_state.view_year = datetime.now().month, datetime.now().year
            st.rerun()
        if sub3.button("הבא", key=f"n_{suffix}"):
            if st.session_state.view_month == 12:
                st.session_state.view_month = 1; st.session_state.view_year += 1
            else: st.session_state.view_month += 1
            st.rerun()
    return events

# --- טאבים ---
tab_stats, tab_details, tab_report, tab_manage = st.tabs(["📊 סיכומים", "📋 פירוט", "📝 דיווח", "🛠️ ניהול"])

with tab_stats:
    evs = render_metrics_and_nav("stats")
    cal_res = calendar(events=evs, options={"initialView": "dayGridMonth", "locale": "he", "direction": "rtl", "initialDate": f"{st.session_state.view_year}-{st.session_state.view_month:02d}-01", "headerToolbar": {"left": "", "center": "title", "right": ""}}, key=f"cal_{st.session_state.view_year}_{st.session_state.view_month}")
    
    if "eventClick" in cal_res:
        clicked_date = cal_res["eventClick"]["event"]["start"]
        row_data = df[df['date'] == clicked_date]
        if not row_data.empty:
            r = row_data.iloc[0]
            dt_obj = datetime.strptime(clicked_date, '%Y-%m-%d')
            target = get_target_hours(dt_obj)
            
            # חישוב חסר/עודף
            diff_text = ""
            if r['type'] == 'עבודה':
                s_t = datetime.strptime(f"{clicked_date} {r['start_time']}", "%Y-%m-%d %H:%M:%S")
                e_t = datetime.strptime(f"{clicked_date} {r['end_time']}", "%Y-%m-%d %H:%M:%S")
                actual_hrs = (e_t - s_t).total_seconds() / 3600
                diff = actual_hrs - target # כאן התיקון: מחשבים הפרש יחסי לתקן
                
                # הצגה רק אם יש הפרש משמעותי (מעל דקה)
                if abs(diff) > (1/60): 
                    if diff < 0:
                        diff_text = f" | 🔴 **חסר:** {float_to_time_str(diff).replace('-', '')}"
                    elif diff > 0:
                        diff_text = f" | 🟢 **עודף:** {float_to_time_str(diff).replace('+', '')}"
            
            st.markdown(f"""
            <div class="selected-date-info">
                <strong>📅 תאריך: {dt_obj.strftime('%d/%m/%Y')}</strong>{diff_text}<br>
                🕒 כניסה: {format_time_display(r['start_time'])} | 🕒 יציאה: {format_time_display(r['end_time'])}<br>
                💬 הערה: {r['notes'] if r['notes'] else 'אין הערות'}
            </div>
            """, unsafe_allow_html=True)

with tab_details:
    render_metrics_and_nav("details")
    m_data = df[df['date'].str.startswith(f"{st.session_state.view_year}-{st.session_state.view_month:02d}")].copy().sort_values('date')
    if not m_data.empty:
        m_data['תאריך'] = pd.to_datetime(m_data['date']).dt.strftime('%d/%m/%Y')
        m_data['כניסה'] = m_data['start_time'].apply(format_time_display)
        m_data['יציאה'] = m_data['end_time'].apply(format_time_display)
        st.markdown(m_data[['תאריך', 'type', 'כניסה', 'יציאה', 'notes']].rename(columns={'type': 'סוג', 'notes': 'הערה'}).to_html(index=False), unsafe_allow_html=True)
    else: st.info("אין נתונים")

with tab_report:
    st.subheader("📝 דיווח ידני")
    d_in = st.date_input("תאריך", date.today(), format="DD/MM/YYYY")
    r_t = st.radio("סוג", ["עבודה", "חופשה", "מחלה", "שבתון"], horizontal=True)
    st_t, en_t = time(6,30), time(15,30)
    if r_t == "עבודה":
        c1, c2 = st.columns(2)
        st_t, en_t = c1.time_input("כניסה", st_t), c2.time_input("יציאה", en_t)
    n_in = st.text_input("הערה", key="new_note")
    if st.button("שמור דיווח", type="primary", use_container_width=True):
        new_row = pd.DataFrame([{"date": str(d_in), "start_time": f"{st_t}", "end_time": f"{en_t}", "notes": n_in, "type": r_t}])
        update_google_sheet(pd.concat([df[df['date'] != str(d_in)], new_row], ignore_index=True))

    st.divider()
    f = st.file_uploader("📂 טעינת אקסל", type=["xlsx", "xls"])
    if f:
        edf = pd.read_excel(f)
        if st.button("🚀 טען ודרוס נתונים", use_container_width=True):
            pb = st.progress(0); stxt = st.empty(); total = len(edf); entries = []
            for i, row in edf.iterrows():
                pb.progress((i+1)/total); stxt.text(f"מעבד שורה {i+1}...")
                curr_d = pd.to_datetime(row['תאריך']).strftime('%Y-%m-%d')
                def t_to_s(v):
                    if pd.isna(v): return "00:00:00"
                    return v.strftime('%H:%M:00') if isinstance(v, time) else pd.to_datetime(v).strftime('%H:%M:00')
                entries.append({"date": curr_d, "start_time": t_to_s(row['משעה']), "end_time": t_to_s(row.get('עד שעה', '00:00:00')), "notes": str(row.get('תיאור', '')), "type": "עבודה"})
            update_google_sheet(pd.concat([df[~df['date'].isin([e['date'] for e in entries])], pd.DataFrame(entries)], ignore_index=True), rerun=False)
            stxt.empty(); pb.empty(); st.balloons(); st.success("✅ בוצע!"); time_lib.sleep(3); st.rerun()

with tab_manage:
    if not df.empty:
        st.subheader("🛠️ ניהול")
        d_l = sorted(df['date'].unique())
        if 'last_d' not in st.session_state: st.session_state.last_d = d_l[-1]
        try: idx = d_l.index(st.session_state.last_d)
        except: idx = len(d_l)-1
        s_d = st.selectbox("תאריך", d_l, index=idx, format_func=lambda x: datetime.strptime(x, '%Y-%m-%d').strftime('%d/%m/%Y'))
        st.session_state.last_d = s_d
        sub = df[df['date'] == s_d].copy().reset_index()
        s_i = st.selectbox("רשומה", sub.index, format_func=lambda i: f"{sub.iloc[i]['type']} | {format_time_display(sub.iloc[i]['start_time'])}")
        curr_r = sub.iloc[s_i]
        st.markdown("#### עדכון")
        types = ["עבודה", "חופשה", "מחלה", "שבתון"]
        nt = st.radio("סוג", types, index=types.index(curr_r['type']), horizontal=True, key=f"nt_{s_d}")
        sv, ev = curr_r['start_time'], curr_r['end_time']
        if nt == "עבודה":
            c1, c2 = st.columns(2)
            sv = c1.time_input("כניסה", value=datetime.strptime(str(curr_r['start_time'])[:8], "%H:%M:%S").time(), key=f"sv_{s_d}")
            ev = c2.time_input("יציאה", value=datetime.strptime(str(curr_r['end_time'])[:8], "%H:%M:%S").time(), key=f"ev_{s_d}")
        nn = st.text_input("הערה", value=curr_r['notes'], key=f"nn_{s_d}")
        if st.button("💾 שמור", use_container_width=True, key=f"bs_{s_d}"):
            df.loc[curr_r['index'], ['type', 'start_time', 'end_time', 'notes']] = [nt, str(sv), str(ev), nn]
            update_google_sheet(df)
        if st.button("🗑️ מחק", use_container_width=True, key=f"bd_{s_d}"):
            update_google_sheet(df.drop(curr_r['index']))