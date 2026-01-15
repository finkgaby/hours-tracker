import streamlit as st
from streamlit_calendar import calendar

st.title("בדיקת לוח שנה")

# אירוע דמה פשוט
events = [
    {
        "title": "בדיקה",
        "start": "2026-01-13",
        "end": "2026-01-13",
    }
]

# אופציות בסיסיות ביותר
calendar_options = {
    "initialView": "dayGridMonth",
}

st.write("הלוח אמור להופיע למטה:")
calendar(events=events, options=calendar_options)
st.write("הלוח אמור להופיע למעלה.")