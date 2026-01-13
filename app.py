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
    else:
        df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes"])
except Exception as e:
    st.error("שגיאה בטעינת הנתונים")
    df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes"])

# --- פונקציות עזר ---
def float_to_time_str(hours_float):
    is_neg = hours_float < 0
    hf = abs(hours_float)
    h, m = int(hf), int(round((hf - int(hf)) * 60))
    if m == 60: h += 1; m = 0
    res = f"{h}:{m:02d}"
    return f"-{res}" if is_neg else res

def update_google_sheet(new_df):
    try:
        conn.update(worksheet="Sheet1", data=new_df)
        st.cache_data.clear()
        st.success("נשמר בהצלחה! ✅")
        st.rerun()
    except Exception as e: st.error(f"שגיאה בשמירה: {e}")

@st.dialog("⚠️ אישור מחיקה")
def delete_confirmation_dialog(idx, d_str, s_s, e_s):
    st.write("### שימי לב!")
    st.write("את עומדת למחוק את הרשומה:")
    fmt_d = datetime.strptime(d_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    # ניקוי השעות לתצוגה בדיאלוג
    s_clean = ":".join(str(s_s).split(":")[:2])
    e_clean = ":".join(str(e_s).split(":")[:2])
    st.markdown(f"**תאריך** {fmt_d}")
    st.markdown(f"**כניסה** {s_clean}")
    st.markdown(f"**יציאה** {e_clean}")
    st.write("---")
    st.write("**האם את בטוחה?**")
    c1, c2 = st.columns(2)
    if c1.button("✅ כן, מחק", type="primary", use_container_width=True, key="confirm_del_btn"):
        update_google_sheet(df.drop(idx))
    if c2.button("❌ לא, בטל", use_container_width=True, key="cancel_del_btn"): 
        st.rerun()

# --- טאבים ---
tab_stats, tab_report, tab_manage = st.tabs(["📊 סיכומים ולוח שנה", "📝 דיווח חדש", "🛠️ ניהול ועריכה"])

with tab_stats:
    if df.empty:
        st.info("אין נתונים להצגה")
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
        cr, cl = st.columns(2)
        cr.metric("📅 מאזן שבועי", float_to_time_str(tw))
        cl.metric("📆 מאזן חודשי", float_to_time_str(tm))
        st.divider()
        calendar(events=events, options={"headerToolbar": {"left": "today prev,next", "center": "title", "right": ""}, "initialView": "dayGridMonth", "locale": "he", "direction": "rtl", "height": 650}, key="main_cal")

with tab_report:
    d = st.date_input("תאריך", date.today(), key="report_date")
    wd = d.weekday()
    if wd in [4,5]: st.warning("סופ\"ש")
    else: st.info(f"תקן ליום זה: {8.5 if wd == 3 else 9.0}")
    
    c1, c2 = st.columns(2)
    ci = c1.time_input("כניסה", time(6,30), key="report_in")
    co = c2.time_input("יציאה", time(15,30), key="report_out")
    
    notes = st.text_input("הערות", key="report_notes")
    
    if st.button("שמור דיווח", type="primary", use_container_width=True, key="save_report_btn"):
        if ci >= co:
            st.error("שעת כניסה חייבת להיות לפני שעת יציאה")
        else:
            new_row = pd.DataFrame([{"date": str(d), "start_time": str(ci), "end_time": str(co), "notes": notes}])
            update_google_sheet(pd.concat([df, new_row], ignore_index=True))

with tab_manage:
    if df.empty:
        st.info("אין נתונים לעריכה")
    else:
        sel_d = st.selectbox("בחר תאריך לעריכה", sorted(df['date'].unique(), reverse=True), key="manage_date_sel")
        d_rows = df[df['date'] == sel_d].reset_index()
        
        # בניית רשימת אופציות לעריכה במקרה של פיצול יום
        opt_list = {i: f"{r['start_time'][:5]} - {r['end_time'][:5]}" for i, r in d_rows.iterrows()}
        sel_idx = st.selectbox("בחר רשומה ספציפית", opt_list.keys(), format_func=lambda x: opt_list[x], key="manage_row_sel")
        
        curr = d_rows.iloc[sel_idx]
        
        with st.expander("עריכה / מחיקה", expanded=True):
            er, el = st.columns(2)
            # המרת השעה הקיימת לאובייקט time עבור ה-input
            t_in = datetime.strptime(str(curr['start_time']), "%H:%M:%S").time()
            t_out = datetime.strptime(str(curr['end_time']), "%H:%M:%S").time()
            
            ni = er.time_input("כניסה", t_in, key="edit_in")
            no = el.time_input("יציאה", t_out, key="edit_out")
            
            # כאן התיקון הקריטי - הוספת key ייחודי לשדה ההערות בעריכה
            nn = st.text_input("הערות", "" if pd.isna(curr['notes']) else curr['notes'], key="edit_notes_input")
            
            b_upd, b_del = st.columns(2)
            if b_upd.button("💾 עדכן רשומה", use_container_width=True, key="update_btn"):
                if ni >= no:
                    st.error("זמן לא תקין")
                else:
                    df.loc[curr['index']] = [sel_d, str(ni), str(no), nn]
                    update_google_sheet(df)
            
            if b_del.button("🗑️ מחק רשומה", type="secondary", use_container_width=True, key="delete_btn"):
                delete_confirmation_dialog(curr['index'], sel_d, curr['start_time'], curr['end_time'])