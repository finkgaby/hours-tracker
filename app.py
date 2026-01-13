import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time, date
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
        else:
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
    # הצגת תאריך בפורמט dd/mm/yyyy בדיאלוג
    fmt_d = datetime.strptime(d_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    s_clean = ":".join(str(s_s).split(":")[:2]) if pd.notna(s_s) else "00:00"
    e_clean = ":".join(str(e_s).split(":")[:2]) if pd.notna(e_s) else "00:00"
    st.markdown(f"**תאריך** {fmt_d}"); st.markdown(f"**שעת כניסה** {s_clean}"); st.markdown(f"**שעת יציאה** {e_clean}")
    st.write("---"); st.write("**האם את בטוחה?**")
    c1, c2 = st.columns(2)
    if c1.button("✅ כן, מחק", type="primary", use_container_width=True, key="dlg_confirm_del"):
        update_google_sheet(df.drop(idx))
    if c2.button("❌ לא, בטל", use_container_width=True, key="dlg_cancel_del"): st.rerun()

# --- טאבים ---
tab_stats, tab_report, tab_manage = st.tabs(["📊 סיכומים ולוח שנה", "📝 דיווח חדש", "🛠️ ניהול ועריכה"])

with tab_stats:
    if df.empty: st.info("אין נתונים להצגה")
    else:
        events, tw, tm = [], 0.0, 0.0
        now = datetime.now()
        for _, row in df.iterrows():
            try:
                dt = datetime.strptime(row['date'], '%Y-%m-%d')
                target = 8.5 if dt.weekday() == 3 else (0 if dt.weekday() in [4,5] else 9.0)
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
                else:
                    hrs, bal = target, 0
                    color = "#007bff" if row_type == 'חופשה' else "#fd7e14"
                    title = row_type

                if dt.year == now.year and dt.month == now.month: tm += bal
                if dt.year == now.year and dt.isocalendar()[1] == now.isocalendar()[1]: tw += bal
                events.append({"title": title, "start": row['date'], "end": row['date'], "backgroundColor": color, "borderColor": color})
            except: continue
        cr, cl = st.columns(2)
        cr.metric("📅 מאזן שבועי", float_to_time_str(tw))
        cl.metric("📆 מאזן חודשי", float_to_time_str(tm))
        st.divider()
        calendar(events=events, options={"headerToolbar": {"left": "today prev,next", "center": "title", "right": ""}, "initialView": "dayGridMonth", "locale": "he", "direction": "rtl", "height": 650}, key="main_cal_comp")

with tab_report:
    # שינוי פורמט התצוגה בדיווח חדש
    d = st.date_input("תאריך", date.today(), format="DD/MM/YYYY", key="rep_date_input")
    report_type = st.radio("סוג דיווח", ["עבודה", "חופשה", "מחלה"], horizontal=True, key="rep_type_radio")
    
    if report_type == "עבודה":
        c1, c2 = st.columns(2)
        ci = c1.time_input("כניסה", time(6,30), key="rep_time_in")
        co = c2.time_input("יציאה", time(15,30), key="rep_time_out")
        st.caption(f"תקן ליום זה: {8.5 if d.weekday() == 3 else (0 if d.weekday() in [4,5] else 9.0)}")
    else:
        st.info(f"דיווח {report_type} יחשב כיום עבודה מלא לפי התקן.")
        ci, co = "00:00:00", "00:00:00"

    notes = st.text_input("הערות", key="rep_notes_input")
    
    if st.button("שמור דיווח", type="primary", use_container_width=True, key="rep_save_btn"):
        new_row = pd.DataFrame([{"date": str(d), "start_time": str(ci), "end_time": str(co), "notes": notes, "type": report_type}])
        update_google_sheet(pd.concat([df, new_row], ignore_index=True))

with tab_manage:
    if df.empty: st.info("אין נתונים")
    else:
        # שינוי פורמט התצוגה בבחירת תאריך לעריכה (Selectbox)
        dates_list = sorted(df['date'].unique(), reverse=True)
        # פונקציה להצגת התאריך בפורמט dd/mm/yyyy ברשימה
        def format_date_selectbox(d_str):
            return datetime.strptime(d_str, '%Y-%m-%d').strftime('%d/%m/%Y')

        sel_d = st.selectbox("בחר תאריך לעריכה", dates_list, format_func=format_date_selectbox, key="man_date_sel")
        
        d_rows = df[df['date'] == sel_d].reset_index()
        
        def format_row_option(x):
            row = d_rows.iloc[x]
            t_type = row.get('type', 'עבודה')
            if t_type == 'עבודה':
                start_clean = ":".join(str(row['start_time']).split(":")[:2])
                return f"עבודה | {start_clean}"
            return t_type

        sel_idx = st.selectbox("בחר רשומה", d_rows.index, format_func=format_row_option, key="man_row_sel")
        curr = d_rows.iloc[sel_idx]
        
        with st.expander("עריכה / מחיקה", expanded=True):
            # שינוי פורמט בתוך האקספנדר (אם תבחר לשים שם date_input נוסף בעתיד)
            options = ["עבודה", "חופשה", "מחלה"]
            curr_type = curr.get('type', 'עבודה')
            if curr_type not in options: curr_type = "עבודה"
            
            new_type = st.radio("סוג יום", options, index=options.index(curr_type), key="man_edit_type")
            new_n = st.text_input("הערות", "" if pd.isna(curr['notes']) else curr['notes'], key="man_edit_notes")
            
            b1, b2 = st.columns(2)
            if b1.button("💾 עדכן", use_container_width=True, key="man_update_btn"):
                df.loc[curr['index'], 'type'] = new_type
                df.loc[curr['index'], 'notes'] = new_n
                update_google_sheet(df)
            
            if b2.button("🗑️ מחק רשומה", type="secondary", use_container_width=True, key="man_delete_btn"):
                delete_confirmation_dialog(curr['index'], sel_d, curr['start_time'], curr['end_time'])