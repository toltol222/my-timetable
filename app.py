# app.py
import os
from datetime import datetime
import pandas as pd
import streamlit as st

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="주간 수업 진도 체크",
    page_icon="📚",
    layout="centered",
)

SAVE_FILE = "weekly_progress_log.csv"

TIMETABLE = {
    "월": [("1교시", "2-10"), ("2교시", "3-3"), ("4교시", "2-8"), ("5교시", "2-7")],
    "화": [("2교시", "2-9"), ("3교시", "3-4"), ("5교시", "2-11"), ("6교시", "2-8")],
    "수": [("2교시", "2-7"), ("3교시", "2-9"), ("5교시", "2-10"), ("6교시", "3-3")],
    "목": [("1교시", "2-11"), ("2교시", "3-4"), ("4교시", "2-7"), ("5교시", "2-9")],
    "금": [("1교시", "2-10"), ("3교시", "2-8"), ("4교시", "2-11")],
}

DAYS = ["월", "화", "수", "목", "금"]


# -----------------------------
# 데이터 함수
# -----------------------------
def create_empty_log_df():
    return pd.DataFrame(columns=["기록일시", "요일", "교시", "반", "진도"])


def load_log_data():
    if os.path.exists(SAVE_FILE):
        try:
            df = pd.read_csv(SAVE_FILE, dtype=str).fillna("")
            required_cols = {"기록일시", "요일", "교시", "반", "진도"}
            if not required_cols.issubset(df.columns):
                df = create_empty_log_df()
                save_log_data(df)
        except Exception:
            df = create_empty_log_df()
            save_log_data(df)
    else:
        df = create_empty_log_df()
        save_log_data(df)
    return df


def save_log_data(df):
    df.to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")


def make_input_key(day, period, class_name):
    return f"progress_{day}_{period}_{class_name}"


def init_input_states():
    for day, classes in TIMETABLE.items():
        for period, class_name in classes:
            key = make_input_key(day, period, class_name)
            if key not in st.session_state:
                st.session_state[key] = ""


def clear_day_inputs(day):
    for period, class_name in TIMETABLE[day]:
        key = make_input_key(day, period, class_name)
        st.session_state[key] = ""


def get_day_entries(day):
    rows = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    for period, class_name in TIMETABLE[day]:
        key = make_input_key(day, period, class_name)
        progress_text = st.session_state.get(key, "").strip()

        if progress_text:
            rows.append(
                {
                    "기록일시": current_time,
                    "요일": day,
                    "교시": period,
                    "반": class_name,
                    "진도": progress_text,
                }
            )
    return rows


def get_sorted_log_df(df):
    if df.empty:
        return df.copy()

    temp_df = df.copy()
    temp_df["정렬용일시"] = pd.to_datetime(temp_df["기록일시"], errors="coerce")
    temp_df = temp_df.sort_values(by="정렬용일시", ascending=False)
    temp_df = temp_df.drop(columns=["정렬용일시"])
    return temp_df


def get_latest_saved_for_day(df, day):
    if df.empty:
        return pd.DataFrame(columns=["교시", "반", "최근 저장 진도", "기록일시"])

    day_df = df[df["요일"] == day].copy()
    if day_df.empty:
        return pd.DataFrame(columns=["교시", "반", "최근 저장 진도", "기록일시"])

    day_df["정렬용일시"] = pd.to_datetime(day_df["기록일시"], errors="coerce")
    day_df = day_df.sort_values(by="정렬용일시", ascending=False)

    latest_rows = (
        day_df.groupby(["교시", "반"], as_index=False)
        .first()[["교시", "반", "진도", "기록일시"]]
        .rename(columns={"진도": "최근 저장 진도"})
    )

    period_order = {
        "1교시": 1, "2교시": 2, "3교시": 3,
        "4교시": 4, "5교시": 5, "6교시": 6, "7교시": 7
    }
    latest_rows["교시순서"] = latest_rows["교시"].map(period_order)
    latest_rows = latest_rows.sort_values(by="교시순서").drop(columns=["교시순서"])

    return latest_rows


# -----------------------------
# 초기화
# -----------------------------
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.log_df = load_log_data()

init_input_states()

# -----------------------------
# 스타일
# -----------------------------
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    .sub-text {
        color: #666666;
        margin-bottom: 1rem;
    }
    .small-note {
        font-size: 0.9rem;
        color: #666666;
    }
    div[data-testid="stForm"] {
        padding: 1rem;
        border: 1px solid #ececec;
        border-radius: 12px;
        background-color: #fafafa;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# 상단 제목
# -----------------------------
st.markdown('<div class="main-title">📚 주간 수업 진도 체크</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-text">요일별 시간표를 확인하고, 수업 진도를 기록한 뒤 저장하세요.</div>',
    unsafe_allow_html=True
)

# -----------------------------
# 탭
# -----------------------------
tabs = st.tabs(DAYS)

for i, day in enumerate(DAYS):
    with tabs[i]:
        st.markdown(f"### {day}요일 시간표")

        with st.form(f"form_{day}", clear_on_submit=False):
            header_cols = st.columns([1.1, 1.2, 4])
            header_cols[0].markdown("**교시**")
            header_cols[1].markdown("**반**")
            header_cols[2].markdown("**오늘 나간 진도**")

            st.markdown("---")

            for period, class_name in TIMETABLE[day]:
                key = make_input_key(day, period, class_name)
                cols = st.columns([1.1, 1.2, 4])
                cols[0].write(period)
                cols[1].write(class_name)
                cols[2].text_input(
                    label=f"{day} {period} {class_name}",
                    key=key,
                    label_visibility="collapsed",
                    placeholder="예: 프랑스 혁명 서론"
                )

            submitted = st.form_submit_button("저장하기", use_container_width=True)

            if submitted:
                new_rows = get_day_entries(day)

                if new_rows:
                    new_df = pd.DataFrame(new_rows)
                    st.session_state.log_df = pd.concat(
                        [st.session_state.log_df, new_df],
                        ignore_index=True
                    )
                    save_log_data(st.session_state.log_df)

                    # 저장 후 입력창 초기화
                    clear_day_inputs(day)

                    st.success(f"{day}요일 진도가 저장되었습니다. 입력창도 초기화되었습니다.")
                else:
                    st.warning("저장할 진도 내용이 없습니다.")

        with st.expander("최근 저장된 내용 보기", expanded=False):
            latest_day_df = get_latest_saved_for_day(st.session_state.log_df, day)
            if latest_day_df.empty:
                st.info("아직 저장된 기록이 없습니다.")
            else:
                st.dataframe(latest_day_df, use_container_width=True, hide_index=True)

# -----------------------------
# 전체 기록
# -----------------------------
st.markdown("---")
st.markdown("### 전체 주간 기록")

sorted_log_df = get_sorted_log_df(st.session_state.log_df)

if sorted_log_df.empty:
    st.info("아직 저장된 전체 기록이 없습니다.")
else:
    st.dataframe(
        sorted_log_df[["기록일시", "요일", "교시", "반", "진도"]],
        use_container_width=True,
        hide_index=True
    )

# -----------------------------
# CSV 다운로드
# -----------------------------
csv_data = sorted_log_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    label="CSV 백업 다운로드",
    data=csv_data,
    file_name="weekly_progress_backup.csv",
    mime="text/csv",
    use_container_width=True,
)

st.caption(f"저장 파일: {SAVE_FILE}")
