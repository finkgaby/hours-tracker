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
    
    include_today = st.checkbox("כולל היום", value=True, key=f"inc_today_{suffix}")
    calc_limit_date = today_dt if include_today else (today_dt - timedelta(days=1))
    
    m_target = sum(get_target_hours(date(year, month, d)) for d in range(1, cal_lib.monthrange(year, month)[1] + 1))
    
    target_until_limit = 0.0
    if year < today_dt.year or (year == today_dt.year and month < today_dt.month):
        target_until_limit = m_target
    elif year == today_dt.year and month == today_dt.month:
        target_until_limit = sum(get_target_hours(date(year, month, d)) for d in range(1, calc_limit_date.day + 1)) if calc_limit_date.month == month else 0.0
    
    sun_curr = today_dt - timedelta(days=(today_dt.weekday() + 1) % 7)
    sat_curr = sun_curr + timedelta(days=6)
    w_target = sum(get_target_hours(sun_curr + timedelta(days=i)) for i in range(7))

    # חישוב מקדים של סך כל שעות העבודה היומיות עבור הלוח
    daily_work_hrs = {}
    for _, row in df.iterrows():
        if row.get('type', 'עבודה') == 'עבודה':
            dt_str = row['date']
            try:
                s_t = datetime.strptime(f"{dt_str} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e_t = datetime.strptime(f"{dt_str} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                daily_work_hrs[dt_str] = daily_work_hrs.get(dt_str, 0.0) + (e_t - s_t).total_seconds() / 3600
            except: pass

    done_m, done_w, done_until_limit = 0.0, 0.0, 0.0
    events = []
    processed_dates_for_events = set()
    processed_dates_for_targets = set()
    
    for _, row in df.iterrows():
        try:
            dt_str = row['date']
            dt_obj = datetime.strptime(dt_str, '%Y-%m-%d')
            curr_date = dt_obj.date()
            row_t = row.get('type', 'עבודה')
            hrs = 0.0
            
            # --- חישוב המדדים לכל שורה ---
            if row_t == 'עבודה':
                s_t = datetime.strptime(f"{dt_str} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e_t = datetime.strptime(f"{dt_str} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                hrs = (e_t - s_t).total_seconds() / 3600
            elif row_t == 'שבתון':
                hrs = 0.0
                if dt_str not in processed_dates_for_targets:
                    if curr_date.year == year and curr_date.month == month: 
                        m_target -= get_target_hours(dt_obj)
                        if curr_date <= calc_limit_date: target_until_limit -= get_target_hours(dt_obj)
                    if sun_curr <= curr_date <= sat_curr: w_target -= get_target_hours(dt_obj)
                    processed_dates_for_targets.add(dt_str)
            else:
                if dt_str not in processed_dates_for_targets:
                    hrs = get_target_hours(dt_obj)
                    processed_dates_for_targets.add(dt_str)
                else:
                    hrs = 0.0

            if curr_date.year == year and curr_date.month == month: 
                if curr_date <= calc_limit_date: done_m += hrs
                done_until_limit += hrs if curr_date <= calc_limit_date else 0
            if sun_curr <= curr_date <= sat_curr:
                if curr_date <= calc_limit_date: done_w += hrs
            
            # --- יצירת הבלוק בלוח השנה (פעם אחת בלבד לכל תאריך) ---
            if dt_str not in processed_dates_for_events:
                if row_t == 'עבודה':
                    total_day_hrs = daily_work_hrs.get(dt_str, hrs)
                    ev_color = "#28a745" if (total_day_hrs >= get_target_hours(dt_obj)) else "#dc3545"
                    ev_title = f"{int(total_day_hrs)}:{int((total_day_hrs%1)*60):02d}"
                elif row_t == 'שבתון':
                    ev_color, ev_title = "#6f42c1", "שבתון"
                else:
                    ev_color = "#007bff" if row_t == 'חופשה' else "#fd7e14"
                    ev_title = row_t
                
                events.append({"title": ev_title, "start": dt_str, "backgroundColor": ev_color, "borderColor": ev_color, "id": dt_str})
                processed_dates_for_events.add(dt_str)
        except: continue

    st.markdown(f"### 🗓️ סיכום עבור {month}/{year}")
    
    c_m1, c_m2, c_m3 = st.columns(3)
    with c_m1: st.markdown(get_status_card("מאזן חודשי", done_m - m_target), unsafe_allow_html=True)
    with c_m2: st.markdown(get_status_card("מאזן עד היום", done_until_limit - target_until_limit), unsafe_allow_html=True)
    with c_m3: st.markdown(get_status_card("מאזן שבועי", done_w - w_target), unsafe_allow_html=True)
    
    t1, t2, t3 = st.columns(3)
    t1.metric("תקן חודשי", float_to_time_str(m_target).replace('+', ''))
    t2.metric("תקן עד היום", float_to_time_str(target_until_limit).replace('+', ''))
    t3.metric("תקן שבועי", float_to_time_str(w_target).replace('+', ''))
    
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

# --- טאבים ---
tab_stats, tab_details, tab_report, tab_manage = st.tabs(["📊 סיכומים", "📋 פירוט", "📝 דיווח", "🛠️ ניהול"])

with tab_stats:
    evs = render_metrics_and_nav("stats")
    cal_res = calendar(events=evs, options={"initialView": "dayGridMonth", "locale": "he", "direction": "rtl", "initialDate": f"{st.session_state.view_year}-{st.session_state.view_month:02d}-01", "headerToolbar": {"left": "", "center": "title", "right": ""}}, key=f"cal_{st.session_state.view_year}_{st.session_state.view_month}")
    
    if "eventClick" in cal_res:
        clicked_date = cal_res["eventClick"]["event"]["start"]
        row_data = df[df['date'] == clicked_date]
        if not row_data.empty:
            dt_obj = datetime.strptime(clicked_date, '%Y-%m-%d')
            target = get_target_hours(dt_obj)
            
            shifts_html = ""
            total_work_hrs = 0.0
            has_work = False
            
            for _, r in row_data.iterrows():
                if r['type'] == 'עבודה':
                    s_t = datetime.strptime(f"{clicked_date} {r['start_time']}", "%Y-%m-%d %H:%M:%S")
                    e_t = datetime.strptime(f"{clicked_date} {r['end_time']}", "%Y-%m-%d %H:%M:%S")
                    hrs = (e_t - s_t).total_seconds() / 3600
                    total_work_hrs += hrs
                    has_work = True
                    shifts_html += f"🕒 <strong>כניסה:</strong> {format_time_display(r['start_time'])} | <strong>יציאה:</strong> {format_time_display(r['end_time'])} <br> <span style='font-size:0.9em; color:gray;'>💬 הערה: {r['notes'] if r['notes'] else 'אין הערות'}</span><hr style='margin: 5px 0;'/>"
                else:
                    shifts_html += f"📌 <strong>סוג:</strong> {r['type']} <br> <span style='font-size:0.9em; color:gray;'>💬 הערה: {r['notes'] if r['notes'] else 'אין הערות'}</span><hr style='margin: 5px 0;'/>"

            diff_text = ""
            if has_work:
                diff = total_work_hrs - target
                if abs(diff) > (1/60):
                    status = "🔴 חסר יומי" if diff < 0 else "🟢 עודף יומי"
                    diff_text = f"<strong>{status}:</strong> {float_to_time_str(diff).replace('-', '').replace('+', '')}"
                else:
                    diff_text = "✅ <strong>הושלם תקן יומי בדיוק</strong>"
            
            st.markdown(f"""
            <div class="selected-date-info">
                <strong>📅 תאריך: {dt_obj.strftime('%d/%m/%Y')}</strong><br><br>
                {shifts_html}
                <div style="margin-top: 10px;">{diff_text}</div>
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
    if r_t == "עבודה":
        c1, c2 = st.columns(2)
        st_t, en_t = c1.time_input("כניסה", time(6,30)), c2.time_input("יציאה", time(15,30))
    else:
        st_t, en_t = time(0,0), time(0,0)
    n_in = st.text_input("הערה", key="new_note")
    
    is_split = st.checkbox("פיצול (הוסף דיווח זה בנוסף לדיווחים קיימים באותו יום)")
    
    if st.button("שמור דיווח", type="primary", use_container_width=True):
        new_row = pd.DataFrame([{"date": str(d_in), "start_time": f"{st_t}", "end_time": f"{en_t}", "notes": n_in, "type": r_t}])
        if is_split:
            update_google_sheet(pd.concat([df, new_row], ignore_index=True))
        else:
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
        s_d = st.selectbox("תאריך", d_l, format_func=lambda x: datetime.strptime(x, '%Y-%m-%d').strftime('%d/%m/%Y'))
        sub = df[df['date'] == s_d].copy().reset_index()
        s_i = st.selectbox("רשומה", sub.index, format_func=lambda i: f"{sub.iloc[i]['type']} | {format_time_display(sub.iloc[i]['start_time'])}")
        curr_r = sub.iloc[s_i]
        nt = st.radio("סוג", ["עבודה", "חופשה", "מחלה", "שבתון"], index=["עבודה", "חופשה", "מחלה", "שבתון"].index(curr_r['type']), horizontal=True)
        sv, ev = curr_r['start_time'], curr_r['end_time']
        if nt == "עבודה":
            c1, c2 = st.columns(2)
            sv = c1.time_input("כניסה", value=datetime.strptime(str(curr_r['start_time'])[:8], "%H:%M:%S").time())
            ev = c2.time_input("יציאה", value=datetime.strptime(str(curr_r['end_time'])[:8], "%H:%M:%S").time())
        nn = st.text_input("הערה", value=curr_r['notes'])
        if st.button("💾 שמור", use_container_width=True):
            df.loc[curr_r['index'], ['type', 'start_time', 'end_time', 'notes']] = [nt, str(sv), str(ev), nn]
            update_google_sheet(df)
        if st.button("🗑️ מחק", use_container_width=True):
            update_google_sheet(df.drop(curr_r['index']))