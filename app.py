import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time, date, timedelta
import calendar as cal_lib
from streamlit_calendar import calendar
import time as time_lib

# --- הגדרות עמוד ---
st.set_page_config(page_title="מערכת דיווח שעות", page_icon="⏱️", layout="centered")

# --- ניהול זיכרון לצפייה בחודשים ---
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
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 16px !important;
    }

    /* עיצוב כרטיסי המאזן הצבעוניים */
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
        else:
            df = pd.DataFrame(columns=["date", "start_time", "end_time", "notes", "type"])
        return df
    except:
        return pd.DataFrame(columns=["date", "start_time", "end_time", "notes", "type"])

df = load_data()

# --- פונקציות עזר ---
def float_to_time_str(hf):
    is_neg = hf < 0
    hf = abs(hf)
    h, m = int(hf), int(round((hf - int(hf)) * 60))
    if m == 60: h += 1; m = 0
    # הצגת סימן ברור: פלוס לחריגה, מינוס לחוסר
    sign = "+" if not is_neg and hf > 0 else ("-" if is_neg else "")
    return f"{sign}{h}:{m:02d}"

def get_target_hours(dt):
    wd = dt.weekday()
    return 8.5 if wd == 3 else (0.0 if wd in [4, 5] else 9.0)

def get_adjusted_monthly_target(year, month, data_df):
    total = sum(get_target_hours(date(year, month, d)) for d in range(1, cal_lib.monthrange(year, month)[1] + 1))
    if not data_df.empty:
        month_prefix = f"{year}-{month:02d}"
        shab = data_df[(data_df['date'].str.startswith(month_prefix)) & (data_df['type'] == 'שבתון')]
        for _, row in shab.iterrows():
            total -= get_target_hours(datetime.strptime(row['date'], '%Y-%m-%d'))
    return max(0.0, total)

def get_adjusted_weekly_target(data_df):
    today_val = date.today()
    sun = today_val - timedelta(days=(today_val.weekday() + 1) % 7)
    total_w = sum(get_target_hours(sun + timedelta(days=i)) for i in range(7))
    if not data_df.empty:
        sat = sun + timedelta(days=6)
        week_data = data_df[(data_df['date'] >= str(sun)) & (data_df['date'] <= str(sat))]
        shab_week = week_data[week_data['type'] == 'שבתון']
        for _, row in shab_week.iterrows():
            total_w -= get_target_hours(datetime.strptime(row['date'], '%Y-%m-%d'))
    return max(0.0, total_w)

def update_google_sheet(new_df):
    conn.update(worksheet="Sheet1", data=new_df)
    st.cache_data.clear()
    st.rerun()

def get_status_card(label, diff_val):
    # לוגיקת צבעים למאזן שעות:
    if diff_val > 0: color = "#f39c12" # כתום (חריגה/שעות נוספות)
    elif diff_val < 0: color = "#ff4b4b" # אדום (חוסר שעות)
    else: color = "#28a745" # ירוק (עמידה מדויקת ביעד)
    
    return f"""
    <div class="status-card" style="background-color: {color};">
        <div class="status-label">{label}</div>
        <div class="status-value">{float_to_time_str(diff_val)}</div>
    </div>
    """

# --- הגדרת הטאבים ---
tab_stats, tab_report, tab_manage = st.tabs(["📊 סיכומים ולוח שנה", "📝 דיווח חדש", "🛠️ ניהול ועריכה"])

with tab_stats:
    m_target = get_adjusted_monthly_target(st.session_state.view_year, st.session_state.view_month, df)
    w_target = get_adjusted_weekly_target(df)
    
    st.markdown(f"### 📅 סיכום עבור {st.session_state.view_month}/{st.session_state.view_year}")
    
    today_dt = date.today()
    sun_curr = today_dt - timedelta(days=(today_dt.weekday() + 1) % 7)
    sat_curr = sun_curr + timedelta(days=6)

    events, done_m, done_w = [], 0.0, 0.0
    for _, row in df.iterrows():
        try:
            dt_obj = datetime.strptime(row['date'], '%Y-%m-%d')
            row_t = row.get('type', 'עבודה')
            
            def simple_time_str(hf):
                h, m = int(hf), int(round((hf - int(hf)) * 60))
                if m == 60: h += 1; m = 0
                return f"{h}:{m:02d}"

            if row_t == 'עבודה':
                s = datetime.strptime(f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M:%S")
                e = datetime.strptime(f"{row['date']} {row['end_time']}", "%Y-%m-%d %H:%M:%S")
                hrs = (e - s).total_seconds() / 3600
                ev_color = "#28a745" if (hrs - get_target_hours(dt_obj)) >= 0 else "#dc3545"
                ev_title = simple_time_str(hrs)
            elif row_t == 'שבתון':
                hrs, ev_color, ev_title = 0.0, "#6f42c1", "שבתון"
            else:
                hrs, ev_color, ev_title = get_target_hours(dt_obj), ("#007bff" if row_t == 'חופשה' else "#fd7e14"), row_t

            if dt_obj.year == st.session_state.view_year and dt_obj.month == st.session_state.view_month:
                done_m += hrs
            if str(sun_curr) <= row['date'] <= str(sat_curr):
                done_w += hrs
            events.append({"title": ev_title, "start": row['date'], "backgroundColor": ev_color, "borderColor": ev_color})
        except: continue

    st.markdown("#### 📈 מדדי חודש")
    c1, c2, c3 = st.columns(3)
    c1.metric("📋 תקן חודשי", f"{int(m_target)}:{int((m_target%1)*60):02d} ש'")
    c2.metric("✅ בוצע בחודש", f"{int(done_m)}:{int((done_m%1)*60):02d}")
    with c3:
        # כותרת מעודכנת שמתאימה לפלוס/מינוס
        st.markdown(get_status_card("⚖️ מאזן חודשי", done_m - m_target), unsafe_allow_html=True)
    
    st.divider()
    st.markdown("#### 📅 מדדי שבוע נוכחי")
    w1, w2, w3 = st.columns(3)
    w1.metric("📊 תקן שבועי", f"{int(w_target)}:{int((w_target%1)*60):02d} ש'")
    w2.metric("⏱️ בוצע השבוע", f"{int(done_w)}:{int((done_w%1)*60):02d}")
    with w3:
        # כותרת מעודכנת שמתאימה לפלוס/מינוס
        st.markdown(get_status_card("⚖️ מאזן שבועי", done_w - w_target), unsafe_allow_html=True)

    st.divider()
    col_nav, _ = st.columns([0.4, 0.6])
    with col_nav:
        sub_c1, sub_c2, sub_c3 = st.columns(3)
        if sub_c1.button("קודם", key="prev"):
            if st.session_state.view_month == 1:
                st.session_state.view_month = 12; st.session_state.view_year -= 1
            else: st.session_state.view_month -= 1
            st.rerun()
        if sub_c2.button("הבא", key="next"):
            if st.session_state.view_month == 12:
                st.session_state.view_month = 1; st.session_state.view_year += 1
            else: st.session_state.view_month += 1
            st.rerun()
        if sub_c3.button("היום", key="today_btn"):
            st.session_state.view_month = datetime.now().month
            st.session_state.view_year = datetime.now().year
            st.rerun()

    calendar(
        events=events,
        options={
            "initialView": "dayGridMonth", "locale": "he", "direction": "rtl",
            "headerToolbar": {"left": "", "center": "title", "right": ""},
            "initialDate": f"{st.session_state.view_year}-{st.session_state.view_month:02d}-01"
        },
        key=f"cal_{st.session_state.view_year}_{st.session_state.view_month}"
    )

# --- הטאבים האחרים נשארים ללא שינוי ---
# ... (דיווח וניהול) ...
with tab_report:
    st.subheader("📝 דיווח ידני")
    d_in = st.date_input("תאריך", date.today(), format="DD/MM/YYYY", key="rep_d")
    r_type = st.radio("סוג דיווח", ["עבודה", "חופשה", "מחלה", "שבתון"], horizontal=True, key="rep_t")
    st_t, en_t = "00:00:00", "00:00:00"
    if r_type == "עבודה":
        col1, col2 = st.columns(2)
        st_t, en_t = col1.time_input("כניסה", time(6,30)), col2.time_input("יציאה", time(15,30))
    
    notes_in = st.text_input("הערות", key="rep_notes")
    
    if st.button("שמור דיווח", type="primary", use_container_width=True):
        new_row = pd.DataFrame([{
            "date": str(d_in), "start_time": f"{st_t}", "end_time": f"{en_t}", 
            "notes": notes_in, "type": r_type
        }])
        df_filtered = df[df['date'] != str(d_in)]
        update_google_sheet(pd.concat([df_filtered, new_row], ignore_index=True))

    st.divider()

    st.subheader("📂 טעינת קובץ דיווחים (Excel)")
    excel_file = st.file_uploader("בחר קובץ אקסל (xls, xlsx)", type=["xlsx", "xls"])
    
    if excel_file:
        try:
            excel_df = pd.read_excel(excel_file)
            if 'תאריך' in excel_df.columns and 'משעה' in excel_df.columns:
                if st.button("🚀 טען ודרוס נתונים קיימים", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    new_entries = []
                    dates_to_delete = []
                    total_rows = len(excel_df)
                    
                    for i, row in excel_df.iterrows():
                        progress = (i + 1) / total_rows
                        progress_bar.progress(progress)
                        status_text.text(f"מעבד שורה {i+1} מתוך {total_rows}...")
                        
                        curr_date = pd.to_datetime(row['תאריך']).strftime('%Y-%m-%d')
                        def to_t(val):
                            if pd.isna(val): return "00:00:00"
                            if isinstance(val, time): return val.strftime('%H:%M:00')
                            return pd.to_datetime(val).strftime('%H:%M:00')
                        
                        new_entries.append({
                            "date": curr_date, "start_time": to_t(row['משעה']), "end_time": to_t(row['עד שעה']),
                            "notes": str(row['תיאור']) if 'תיאור' in excel_df.columns and pd.notna(row['תיאור']) else "",
                            "type": "עבודה"
                        })
                        dates_to_delete.append(curr_date)
                    
                    status_text.text("שומר נתונים בגיליון... אנא המתן")
                    df_cleaned = df[~df['date'].isin(dates_to_delete)]
                    final_df = pd.concat([df_cleaned, pd.DataFrame(new_entries)], ignore_index=True)
                    
                    conn.update(worksheet="Sheet1", data=final_df)
                    st.cache_data.clear()
                    
                    status_text.empty()
                    progress_bar.empty()
                    st.success(f"✅ הטעינה הסתיימה בהצלחה! {len(new_entries)} דיווחים עודכנו.")
                    st.balloons()
                    time_lib.sleep(2)
                    st.rerun()
            else:
                st.error("הקובץ חייב להכיל עמודות: 'תאריך' ו-'משעה'")
        except Exception as e:
            st.error(f"שגיאה בעיבוד הקובץ: {e}")

with tab_manage:
    if df.empty: 
        st.info("אין נתונים להצגה")
    else:
        st.subheader("🛠️ ניהול ועריכה")
        d_list = sorted(df['date'].unique(), reverse=True)
        s_date = st.selectbox("בחר תאריך לעריכה/מחיקה", d_list, 
                             format_func=lambda x: datetime.strptime(x, '%Y-%m-%d').strftime('%d/%m/%Y'),
                             key="manage_date_selector")
        
        d_sub = df[df['date'] == s_date].copy().reset_index()
        
        def fmt(idx):
            r = d_sub.iloc[idx]
            if r['type'] == 'עבודה':
                try:
                    t_val = str(r['start_time'])
                    clean_time = datetime.strptime(t_val, "%H:%M:%S").strftime("%H:%M")
                    return f"עבודה | {clean_time}"
                except:
                    return f"עבודה | {str(r['start_time'])[:5].rstrip(':')}"
            return r['type']
        
        s_idx = st.selectbox("בחר רשומה", d_sub.index, format_func=fmt, key="manage_record_selector")
        curr_row = d_sub.iloc[s_idx]
        
        st.markdown("#### ✏️ עדכון פרטים")
        
        types_options = ["עבודה", "חופשה", "מחלה", "שבתון"]
        try:
            current_idx = types_options.index(curr_row['type'])
        except:
            current_idx = 0

        new_type = st.radio("סוג מעודכן", types_options, 
                           index=current_idx, 
                           horizontal=True, 
                           key=f"manage_type_radio_{s_date}_{s_idx}")
        
        col1, col2 = st.columns(2)
        if new_type == "עבודה":
            def to_t_obj(val, default_time):
                try:
                    t = datetime.strptime(str(val), "%H:%M:%S").time()
                    if t.hour == 0 and t.minute == 0:
                        return default_time
                    return t
                except:
                    return default_time
            
            new_start = col1.time_input("כניסה", value=to_t_obj(curr_row['start_time'], time(6,30)), key=f"m_start_{s_date}_{s_idx}")
            new_end = col2.time_input("יציאה", value=to_t_obj(curr_row['end_time'], time(15,30)), key=f"m_end_{s_date}_{s_idx}")
            st_val, en_val = str(new_start), str(new_end)
        else:
            st_val, en_val = "00:00:00", "00:00:00"
            
        new_notes = st.text_input("הערות", value=str(curr_row['notes']) if pd.notna(curr_row['notes']) else "", key=f"m_notes_{s_date}_{s_idx}")
        
        c_upd, c_del = st.columns(2)
        if c_upd.button("💾 שמור שינויים", use_container_width=True, type="primary", key=f"m_upd_btn_{s_date}_{s_idx}"):
            df.loc[curr_row['index'], ['type', 'start_time', 'end_time', 'notes']] = [new_type, st_val, en_val, new_notes]
            update_google_sheet(df)
            st.success("עודכן בהצלחה!")

        if c_del.button("🗑️ מחק רשומה", use_container_width=True, key=f"m_del_btn_{s_date}_{s_idx}"):
            update_google_sheet(df.drop(curr_row['index']))