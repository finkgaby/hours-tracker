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
    wd = dt.weekday()
    if wd == 3: return 8.5   # חמישי
    if wd in [4, 5]: return 0.0 # שישי שבת
    return 9.0               # ראשון-רביעי

def get_adjusted_monthly_target(year, month, data_df):
    total = 0.0
    num_days = cal_lib.monthrange(year, month)[1]
    for d_val in range(1, num_days + 1):
        total += get_target_hours(date(year, month, d_val))
    
    if not data_df.empty:
        month_prefix = f"{year}-{month:02d}"
        shabbatons = data_df[(data_df['date'].str.startswith(month_prefix)) & (data_df['type'] == 'שבתון')]
        for _, row in shabbatons.iterrows():
            total -= get_target_hours(datetime.strptime(row['date'], '%Y-%m-%d'))
    return max(0, total)

def get_adjusted_weekly_target(data_df):
    today_val = date.today()
    days_since_sun = (today_val.weekday() + 1) % 7
    sun = today_val - timedelta(days=days_since_sun)
    sat = sun + timedelta(days=6)
    
    total_w = sum(get_target_hours(sun + timedelta(days=i)) for i in range(7))
    
    if not data_df.empty:
        week_data = data_df[(data_df['date'] >= str(sun)) & (data_df['date'] <= str(sat))]
        shab_week = week_data[week_data['type'] == 'שבתון']
        for _, row in shab_week.iterrows():
            total_w -= get_target_hours(datetime.strptime(row['date'], '%Y-%m-%d'))
    return max(0, total_w)

def update_google_sheet(new_df):
    try:
        conn.update(worksheet="Sheet1", data=new_df)
        st.cache_data.clear()
        st.success("נשמר בהצלחה! ✅")
        st.rerun()
    except Exception as e: st.error(f"שגיאה בשמירה: {e}")

# --- הגדרת הטאבים ---
tab_stats, tab_report, tab_manage = st.tabs(["📊 סיכומים ולוח שנה", "📝 דיווח חדש", "🛠️ ניהול ועריכה"])

# --- 1. טאב סיכומים ---
with tab_stats:
    events, done_m, done_w = [], 0.0, 0.0
    now = datetime.now()
    today_val = date.today()
    days_since_sun = (today_val.weekday() + 1) % 7
    sun_date = today_val - timedelta(days=days_since_sun)
    sat_date = sun_date + timedelta(days=6)

    m_target = get_adjusted_monthly_target(now.year, now.month, df)
    w_target = get_adjusted_weekly_target(df)
    
    for _, row in df.iterrows():
        try:
            dt_obj = datetime.strptime(row['date'], '%Y-%m-%d')
            row_t = row.get('type', 'עבודה')
            if pd.isna(row_t): row_t = 'עבודה'
            
            # חישוב שעות לביצוע
            if row_t == 'עבודה':
                if pd.isna(row['start_time']) or pd.isna(row['end_time']): hrs = 0.0
                else:
                    s_t = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                    e_t = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                    hrs = (e_t - s_t).total_seconds() / 3600
                bal = hrs - get_target_hours(dt_obj)
                ev_color = "#28a745" if bal >= 0 else "#dc3545"
                ev_title = float_to_time_str(hrs)
            elif row_t == 'שבתון':
                hrs, ev_color, ev_title = 0.0, "#6f42c1", "שבתון"
            else: # חופשה או מחלה
                hrs, ev_color, ev_title = get_target_hours(dt_obj), ("#007bff" if row_t == 'חופשה' else "#fd7e14"), row_t

            # צבירת שעות חודשיות
            if dt_obj.year == now.year and dt_obj.month == now.month: 
                done_m += hrs
            
            # צבירת שעות שבועיות
            if str(sun_date) <= row['date'] <= str(sat_date):
                done_w += hrs

            events.append({"title": ev_title, "start": row['date'], "backgroundColor": ev_color, "borderColor": ev_color})
        except: continue
    
    # שורה 1: תקנים (חודשי ושבועי)
    st.markdown("### 📋 תקנים מותאמים")
    c1, c2 = st.columns(2)
    c1.metric("תקן חודשי", f"{m_target} ש'")
    c2.metric("תקן שבועי", f"{w_target} ש'")
    
    st.divider()

    # שורה 2: ביצוע ונותר (חודשי ושבועי)
    st.markdown("### ✅ סיכום שעות שבוצעו")
    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
    r1_c1.metric("בוצע החודש", float_to_time_str(done_m))
    r1_c2.metric("נותר לחודש", float_to_time_str(max(0, m_target - done_m)))
    r1_c3.metric("בוצע השבוע", float_to_time_str(done_w))
    r1_c4.metric("נותר לשבוע", float_to_time_str(max(0, w_target - done_w)))
    
    st.divider()
    calendar(events=events, options={"initialView": "dayGridMonth", "locale": "he", "direction": "rtl"}, key="main_cal")

# טאב דיווח וניהול נשארו כפי שהיו...
with tab_report:
    d_in = st.date_input("תאריך", date.today(), format="DD/MM/YYYY", key="rep_d")
    r_type = st.radio("סוג דיווח", ["עבודה", "חופשה", "מחלה", "שבתון"], horizontal=True, key="rep_t")
    st_t, en_t = "00:00:00", "00:00:00"
    if r_type == "עבודה":
        col1, col2 = st.columns(2)
        st_t = col1.time_input("כניסה", time(6,30), key="rep_i")
        en_t = col2.time_input("יציאה", time(15,30), key="rep_o")
    notes_in = st.text_input("הערות", key="rep_n")
    if st.button("שמור דיווח", type="primary", use_container_width=True):
        new_entry = pd.DataFrame([{"date": str(d_in), "start_time": str(st_t), "end_time": str(en_t), "notes": notes_in, "type": r_type}])
        update_google_sheet(pd.concat([df, new_entry], ignore_index=True))

with tab_manage:
    if df.empty: st.info("אין נתונים")
    else:
        d_list = sorted(df['date'].unique(), reverse=True)
        s_date = st.selectbox("בחר תאריך", d_list, format_func=lambda x: datetime.strptime(x, '%Y-%m-%d').strftime('%d/%m/%Y'), key="m_d")
        d_sub = df[df['date'] == s_date].reset_index()
        def fmt_row(idx):
            r = d_sub.iloc[idx]
            if r['type'] == 'עבודה':
                t_clean = ":".join(str(r['start_time']).split(":")[:2])
                return f"עבודה | {t_clean}"
            return str(r['type'])
        s_idx = st.selectbox("בחר רשומה", d_sub.index, format_func=fmt_row, key="m_r")
        curr_row = d_sub.iloc[s_idx]
        with st.expander("שינוי פרטים / מחיקה", expanded=True):
            opts = ["עבודה", "חופשה", "מחלה", "שבתון"]
            curr_val = curr_row['type'] if curr_row['type'] in opts else "עבודה"
            new_t = st.radio("סוג דיווח:", opts, index=opts.index(curr_val), key=f"ed_t_{s_date}_{s_idx}")
            e_st, e_en = str(curr_row['start_time']), str(curr_row['end_time'])
            if new_t == "עבודה":
                ec1, ec2 = st.columns(2)
                try:
                    v_i = datetime.strptime(str(curr_row['start_time']), "%H:%M:%S").time()
                    v_o = datetime.strptime(str(curr_row['end_time']), "%H:%M:%S").time()
                except: v_i, v_o = time(6,30), time(15,30)
                e_st = ec1.time_input("כניסה", v_i, key=f"ed_i_{s_date}_{s_idx}")
                e_en = ec2.time_input("יציאה", v_o, key=f"ed_o_{s_date}_{s_idx}")
            e_notes = st.text_input("הערות", "" if pd.isna(curr_row['notes']) else curr_row['notes'], key=f"ed_n_{s_date}_{s_idx}")
            st.divider()
            bu1, bu2 = st.columns(2)
            if bu1.button("💾 עדכן שינויים", use_container_width=True, key=f"btn_u_{s_date}_{s_idx}"):
                df.loc[curr_row['index'], ['type', 'start_time', 'end_time', 'notes']] = [new_t, str(e_st), str(e_en), e_notes]
                update_google_sheet(df)
            if bu2.button("🗑️ מחק רשומה", type="secondary", use_container_width=True, key=f"btn_d_{s_date}_{s_idx}"):
                update_google_sheet(df.drop(curr_row['index']))