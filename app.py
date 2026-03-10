# app.py
import os
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

SAVE_FILE = "weekly_progress.csv"

TIMETABLE = {
    "월": [("1교시", "2-10"), ("2교시", "3-3"), ("4교시", "2-8"), ("5교시", "2-7")],
    "화": [("2교시", "2-9"), ("3교시", "3-4"), ("5교시", "2-11"), ("6교시", "2-8")],
    "수": [("2교시", "2-7"), ("3교시", "2-9"), ("5교시", "2-10"), ("6교시", "3-3")],
    "목": [("1교시", "2-11"), ("2교시", "3-4"), ("4교시", "2-7"), ("5교시", "2-9")],
    "금": [("1교시", "2-10"), ("3교시", "2-8"), ("4교시", "2-11")],
}

DAYS = ["월", "화", "수", "목", "금"]


# -----------------------------
# 데이터 처리 함수
# -----------------------------
def create_default_df():
    rows = []
    for day, classes in TIMETABLE.items():
        for period, class_name in classes:
            rows.append(
                {
                    "요일": day,
                    "교시": period,
                    "반": class_name,
                    "진도": ""
                }
            )
    return pd.DataFrame(rows)


def load_data():
    """저장 파일이 있으면 불러오고, 없으면 기본 데이터 생성"""
    if os.path.exists(SAVE_FILE):
        try:
            df = pd.read_csv(SAVE_FILE, dtype=str).fillna("")
            # 혹시 구조가 달라졌을 때 최소 보정
            required_cols = {"요일", "교시", "반", "진도"}
            if not required_cols.issubset(df.columns):
                df = create_default_df()
                save_data(df)
        except Exception:
            df = create_default_df()
            save_data(df)
    else:
        df = create_default_df()
        save_data(df)
    return df


def save_data(df):
    df.to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")


def sync_session_from_df(df):
    """DataFrame 값을 session_state 입력창에 반영"""
    for _, row in df.iterrows():
        key = make_input_key(row["요일"], row["교시"], row["반"])
        if key not in st.session_state:
            st.session_state[key] = row["진도"]


def make_input_key(day, period, class_name):
    return f"progress_{day}_{period}_{class_name}"


def update_df_from_session(df, day):
    """선택한 요일의 입력값을 session_state에서 읽어 df에 반영"""
    for idx, row in df[df["요일"] == day].iterrows():
        key = make_input_key(row["요일"], row["교시"], row["반"])
        df.at[idx, "진도"] = st.session_state.get(key, "")
    return df


# -----------------------------
# 초기 로드
# -----------------------------
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = True
    st.session_state.df = load_data()
    sync_session_from_df(st.session_state.df)

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
    .day-card {
        padding: 0.6rem 0.8rem;
        border-radius: 12px;
        background-color: #f8f9fb;
        border: 1px solid #e9edf3;
        margin-bottom: 0.6rem;
    }
    .small-note {
        font-size: 0.9rem;
        color: #666666;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">📚 주간 수업 진도 체크</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-text">요일별 시간표를 확인하고, 오늘 나간 진도를 기록하세요.</div>',
    unsafe_allow_html=True
)

# -----------------------------
# 탭 UI
# -----------------------------
tabs = st.tabs(DAYS)

for i, day in enumerate(DAYS):
    with tabs[i]:
        st.markdown(f"### {day}요일")

        day_df = st.session_state.df[st.session_state.df["요일"] == day].copy()

        with st.form(f"form_{day}"):
            header_cols = st.columns([1.1, 1.2, 4])
            header_cols[0].markdown("**교시**")
            header_cols[1].markdown("**반**")
            header_cols[2].markdown("**오늘 나간 진도**")

            st.markdown("---")

            for _, row in day_df.iterrows():
                period = row["교시"]
                class_name = row["반"]
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
                st.session_state.df = update_df_from_session(st.session_state.df, day)
                save_data(st.session_state.df)
                st.success(f"{day}요일 진도가 저장되었습니다.")

        with st.expander("현재 저장된 내용 보기", expanded=False):
            preview_df = st.session_state.df[st.session_state.df["요일"] == day][["교시", "반", "진도"]].copy()
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

# -----------------------------
# 전체 주간 데이터 보기 / 백업
# -----------------------------
st.markdown("---")
st.markdown("### 전체 주간 기록")

weekly_view = st.session_state.df[["요일", "교시", "반", "진도"]].copy()
st.dataframe(weekly_view, use_container_width=True, hide_index=True)

csv_data = weekly_view.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    label="CSV 백업 다운로드",
    data=csv_data,
    file_name="weekly_progress_backup.csv",
    mime="text/csv",
    use_container_width=True,
)

st.caption("저장 위치: 앱 실행 폴더의 weekly_progress.csv")