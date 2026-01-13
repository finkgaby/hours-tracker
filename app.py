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
    .stApp { text-align: right; }
    h1, h2, h3, h4, h5, h6, p, span, div, .stMarkdown, .stText, .stCaption, .stAlert, .stInfo, .stWarning, .stError, .stSuccess {
        text-align: right;
        direction: rtl;
    }
    div[data-testid="stMetric"] { direction: rtl; text-align: right; align-items: flex-end; }
    div[data-testid="stMetricLabel"] { text-align: right !important; width: 100%; direction: rtl; }
    div[data-testid="stMetricValue"] { text-align: right !important; direction: ltr; width: 100%; }
    .stTextInput input, .stNumberInput input, .stTimeInput input, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        direction: rtl;
        text-align: right;
    }
    div[data-testid="stWidgetLabel"] { direction: rtl; text-align: right; width: 100%; display: flex; justify-content: flex-end; }
    .stTabs [data-baseweb="tab-list"] { flex-direction: row-reverse; justify-content: flex-end; }
    .fc-toolbar-title { font-family: sans-serif; text-align: center; }
    div[data-testid="stDataFrame"] { direction: rtl; }
    div[data-testid="stButton"] button[kind="secondary"] { border-color: #ff4b4b; color: #ff4b4b; }
    div[data-testid="stButton"] button[kind="secondary"]:hover { border-color: #ff4b4b; background-color: #ff4b4b; color: white; }
    div[data-testid="stDialog"] button { width: 100%; }
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
    if not time_str: return None
    try:
        clean_str = str(time_str).replace(":", "").replace(".", "").strip()
        if len(clean_str) <= 2: clean_str += "00"
        if len(clean_str) == 3: clean_str = "0" + clean_str
        if len(clean_str) == 4:
            h, m = int(clean_str[:2]), int(clean_str[2:])
            if h > 23 or m > 59: return None
            return datetime.strptime(clean_str, "%H%M").time()
    except: return None
    return None

def float_to_time_str(hours_float):
    is_neg = hours_float < 0
    hf = abs(hours_float)
    h, m = int(hf), int(round((hf - int(hf)) * 60))
    if m == 60: h += 1; m = 0
    res = f"{h}:{m:02d}"
    return f"-{res}" if is_neg else res

def check_overlap(df, check_date, start_t, end_t):
    if df.empty: return False
    day_records = df[df['date'] == str(check_date)]
    new_s, new_e = datetime.combine(date.min, start_t), datetime.combine(date.min, end_t)
    for _, row in day_records.iterrows():
        try:
            curr_s = datetime.combine(date.min, datetime.strptime(row['start_time'], "%H:%M:%S").time())
            curr_e = datetime.combine(date.min, datetime.strptime(row['end_time'], "%H:%M:%S").time())
            if new_s < curr_e and new_e > curr_s: return True
        except: continue
    return False

def update_google_sheet(new_df):
    try:
        conn.update(worksheet="Sheet1", data=new_df)
        st.cache_data.clear()
        st.success("השינויים נשמרו! ✅")
        st.rerun()
    except Exception as e: st.error(f"שגיאה: {e}")

@st.dialog("⚠️ אישור מחיקה")
def delete_confirmation_dialog(idx, d_str, s_s, e_s):
    st.write("### שימי לב!")
    st.write("את עומדת למחוק את הרשומה:")
    fmt_d = datetime.strptime(d_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    s_clean, e_clean = ":".join(str(s_s).split(":")[:2]), ":".join(str(e_s).split(":")[:2])
    st.markdown(f"**תאריך** {fmt_d}"); st.markdown(f"**כניסה** {s_clean}"); st.markdown(f"**יציאה** {e_clean}")
    st.write("---"); st.write("**האם את בטוחה?**")
    c1, c2 = st.columns(2)
    if c1.button("✅ כן, מחק", type="primary", use_container_width=True):
        update_google_sheet(df.drop(idx))
    if c2.button("❌ לא, בטל", use_container_width=True): st.rerun()

# --- טאבים ---
tab_stats, tab_report, tab_manage = st.tabs(["📊 סיכומים ולוח שנה", "📝 דיווח חדש", "🛠️ ניהול ועריכה"])

with tab_stats:
    if df.empty: st.info("אין נתונים")
    else:
        events, tw, tm = [], 0.0, 0.0
        now = datetime.now()
        for _, row in df.iterrows():
            try:
                s = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                hrs = (e - s).total_seconds() / 3600
                dt = datetime.strptime(row['date'], '%Y-%m-%d')
                target = 8.5 if dt.weekday() == 3 else (0 if dt.weekday() in [4,5] else 9.0)
                bal = hrs - target
                if dt.year == now.year and dt.month == now.month: tm += bal
                if dt.year == now.year and dt.isocalendar()[1] == now.isocalendar()[1]: tw += bal
                bg = "#28a745" if bal >= 0 else "#dc3545"
                events.append({"title": float_to_time_str(hrs), "start": row['date'], "end": row['date'], "backgroundColor": bg, "borderColor": bg})
            except: continue
        c_r, c_l = st.columns(2)
        c_r.metric("📅 מאזן שבועי", float_to_time_str(tw))
        c_l.metric("📆 מאזן חודשי", float_to_time_str(tm))
        st.divider()
        st.subheader("🗓️ לוח שנה")
        calendar(events=events, options={"headerToolbar": {"left": "today prev,next", "center": "title", "right": ""}, "initialView": "dayGridMonth", "locale": "he", "direction": "rtl", "height": 650}, key="cal")
        # הטבלה הוסרה מכאן בהתאם לבקשתך

with tab_report:
    c_d, c_i = st.columns([2, 1])
    d = c_d.date_input("תאריך", date.today())
    wd = d.weekday()
    if wd in [4,5]: c_i.warning("סופ\"ש")
    else: c_i.info(f"תקן: {8.5 if wd == 3 else 9.0}")
    t1, t2 = st.tabs(["שעון", "הקלדה"])
    with t1:
        cr, cl = st.columns(2)
        ci, co = cr.time_input("כניסה", time(6,30)), cl.time_input("יציאה", time(15,30))
    with t2:
        tr, tl = st.columns(2)
        si, so = tr.text_input("כניסה (0630)", ""), tl.text_input("יציאה (1530)", "")
    n = st.text_input("הערות")
    if st.button("שמור דיווח", type="primary", use_container_width=True):
        fs = parse_time_input(si) if si.strip() else ci
        fe = parse_time_input(so) if so.strip() else co
        if fs >= fe: st.error("כניסה חייבת להיות לפני יציאה"); st.stop()
        if check_overlap(df, d, fs, fe): st.error("קיימת חפיפה!"); st.stop()
        update_google_sheet(pd.concat([df, pd.DataFrame([{"date": str(d), "start_time": str(fs), "end_time": str(fe), "notes": n}])], ignore_index=True))

with tab_manage:
    if df.empty: st.info("אין נתונים")
    else:
        sel_d = st.selectbox("בחר תאריך", sorted(df['date'].unique(), reverse=True))
        d_rows = df[df['date'] == sel_d].reset_index()
        sel_idx = st.selectbox("בחר רשומה", d_rows.index, format_func=lambda x: f"{d_rows.iloc[x]['start_time'][:5]}-{d_rows.iloc[x]['end_time'][:5]}")
        curr = d_rows.iloc[sel_idx]
        with st.expander("עריכה / מחיקה", expanded=True):
            er, el = st.columns(2)
            ni, no = er.time_input("כניסה", datetime.strptime(str(curr['start_time']), "%H:%M:%S").time()), el.time_input("יציאה", datetime.strptime(str(curr['end_time']), "%H:%M:%S").time())
            nn = st.text_input("הערות", "" if pd.isna(curr['notes']) else curr['notes'])
            b1, b2 = st.columns(2)
            if b1.button("💾 עדכן", use_container_width=True):
                if ni >= no: st.error("זמן לא תקין")
                elif check_overlap(df.drop(curr['index']), sel_d, ni, no): st.error("חפיפה!")
                else:
                    df.loc[curr['index']] = [sel_d, str(ni), str(no), nn]
                    update_google_sheet(df)
            if b2.button("🗑️ מחק", type="secondary", use_container_width=True):
                delete_confirmation_dialog(curr['index'], sel_d, curr['start_time'], curr['end_time'])