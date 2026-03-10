# app.py
import os
from datetime import datetime, date

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
# 유틸 함수
# -----------------------------
def make_input_key(day: str, period: str, class_name: str, version: int) -> str:
    return f"progress_{day}_{period}_{class_name}_v{version}"


def make_date_key(day: str, version: int) -> str:
    return f"lesson_date_{day}_v{version}"


def create_empty_log_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["수업날짜", "기록일시", "요일", "교시", "반", "진도"])


def load_log_data() -> pd.DataFrame:
    if not os.path.exists(SAVE_FILE):
        df = create_empty_log_df()
        df.to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")
        return df

    try:
        df = pd.read_csv(SAVE_FILE, dtype=str).fillna("")
        required_cols = {"수업날짜", "기록일시", "요일", "교시", "반", "진도"}

        # 예전 파일 호환
        if "수업날짜" not in df.columns and {"기록일시", "요일", "교시", "반", "진도"}.issubset(df.columns):
            df["수업날짜"] = ""
            df = df[["수업날짜", "기록일시", "요일", "교시", "반", "진도"]]
            save_log_data(df)

        if not required_cols.issubset(df.columns):
            df = create_empty_log_df()
            df.to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")

        return df

    except Exception:
        df = create_empty_log_df()
        df.to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")
        return df


def save_log_data(df: pd.DataFrame) -> None:
    df.to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")


def get_sorted_log_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    temp_df = df.copy()
    temp_df["__sort_lesson_date"] = pd.to_datetime(temp_df["수업날짜"], errors="coerce")
    temp_df["__sort_record_dt"] = pd.to_datetime(temp_df["기록일시"], errors="coerce")

    temp_df = temp_df.sort_values(
        by=["__sort_lesson_date", "__sort_record_dt"],
        ascending=[False, False]
    ).drop(columns=["__sort_lesson_date", "__sort_record_dt"])

    return temp_df


def get_latest_day_view(df: pd.DataFrame, day: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["교시", "학급", "최근 저장 진도", "수업날짜"])

    day_df = df[df["요일"] == day].copy()
    if day_df.empty:
        return pd.DataFrame(columns=["교시", "학급", "최근 저장 진도", "수업날짜"])

    day_df["__sort_lesson_date"] = pd.to_datetime(day_df["수업날짜"], errors="coerce")
    day_df["__sort_record_dt"] = pd.to_datetime(day_df["기록일시"], errors="coerce")
    day_df = day_df.sort_values(
        by=["__sort_lesson_date", "__sort_record_dt"],
        ascending=[False, False]
    )

    latest_df = (
        day_df.groupby(["교시", "반"], as_index=False)
        .first()[["교시", "반", "진도", "수업날짜"]]
        .rename(columns={"반": "학급", "진도": "최근 저장 진도"})
    )

    period_order = {
        "1교시": 1, "2교시": 2, "3교시": 3,
        "4교시": 4, "5교시": 5, "6교시": 6, "7교시": 7
    }
    latest_df["__period_order"] = latest_df["교시"].map(period_order)
    latest_df = latest_df.sort_values(by="__period_order").drop(columns="__period_order")

    return latest_df


def get_display_log_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    화면 표시용 데이터프레임.
    기록일시는 숨기고, 사용자가 보기 쉬운 컬럼명으로 변경
    """
    if df.empty:
        return pd.DataFrame(columns=["수업날짜", "요일", "교시", "학급", "진도내용"])

    display_df = df[["수업날짜", "요일", "교시", "반", "진도"]].copy()
    display_df = display_df.rename(columns={"반": "학급", "진도": "진도내용"})
    return display_df


# -----------------------------
# 세션 상태 초기화
# -----------------------------
if "input_versions" not in st.session_state:
    st.session_state["input_versions"] = {day: 0 for day in DAYS}

if "save_message" not in st.session_state:
    st.session_state["save_message"] = ""

if "save_message_type" not in st.session_state:
    st.session_state["save_message_type"] = "success"


# -----------------------------
# 저장 콜백 함수
# -----------------------------
def save_day_progress(day: str) -> None:
    current_version = st.session_state["input_versions"][day]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    date_key = make_date_key(day, current_version)
    selected_lesson_date = st.session_state.get(date_key, date.today())

    if isinstance(selected_lesson_date, datetime):
        lesson_date_str = selected_lesson_date.strftime("%Y-%m-%d")
    elif isinstance(selected_lesson_date, date):
        lesson_date_str = selected_lesson_date.strftime("%Y-%m-%d")
    else:
        lesson_date_str = str(selected_lesson_date)

    rows_to_add = []
    used_keys = [date_key]

    for period, class_name in TIMETABLE[day]:
        key = make_input_key(day, period, class_name, current_version)
        used_keys.append(key)
        progress_text = str(st.session_state.get(key, "")).strip()

        if progress_text:
            rows_to_add.append(
                {
                    "수업날짜": lesson_date_str,
                    "기록일시": current_time,
                    "요일": day,
                    "교시": period,
                    "반": class_name,
                    "진도": progress_text,
                }
            )

    if not rows_to_add:
        st.session_state["save_message"] = f"{day}요일은 저장할 진도 내용이 없습니다."
        st.session_state["save_message_type"] = "warning"
        st.rerun()

    existing_df = load_log_data()
    new_df = pd.DataFrame(rows_to_add)
    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
    save_log_data(updated_df)

    for key in used_keys:
        if key in st.session_state:
            del st.session_state[key]

    st.session_state["input_versions"][day] += 1
    st.session_state["save_message"] = (
        f"{day}요일 진도 {len(rows_to_add)}건이 저장되었습니다. "
        f"(수업날짜: {lesson_date_str})"
    )
    st.session_state["save_message_type"] = "success"

    st.rerun()


# -----------------------------
# 스타일
# -----------------------------
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-text {
        color: #666666;
        margin-bottom: 1rem;
    }
    .block-wrap {
        padding: 1rem;
        border: 1px solid #e9ecef;
        border-radius: 12px;
        background-color: #fafafa;
        margin-bottom: 1rem;
    }
    .table-header {
        font-weight: 700;
        padding-bottom: 0.35rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# 제목
# -----------------------------
st.markdown('<div class="main-title">📚 주간 수업 진도 체크</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-text">요일별 시간표를 확인하고 오늘 나간 진도를 기록하세요.</div>',
    unsafe_allow_html=True,
)

if st.session_state["save_message"]:
    if st.session_state["save_message_type"] == "success":
        st.success(st.session_state["save_message"])
    else:
        st.warning(st.session_state["save_message"])

    st.session_state["save_message"] = ""
    st.session_state["save_message_type"] = "success"

# -----------------------------
# 요일 탭
# -----------------------------
tabs = st.tabs(DAYS)

for idx, day in enumerate(DAYS):
    with tabs[idx]:
        st.markdown(f"### {day}요일")

        st.markdown('<div class="block-wrap">', unsafe_allow_html=True)

        current_version = st.session_state["input_versions"][day]
        date_key = make_date_key(day, current_version)

        if date_key not in st.session_state:
            st.session_state[date_key] = date.today()

        st.date_input(
            "수업 날짜 선택",
            key=date_key,
            value=st.session_state[date_key],
        )

        st.markdown("")

        header_cols = st.columns([1.2, 1.3, 4.8])
        header_cols[0].markdown('<div class="table-header">교시</div>', unsafe_allow_html=True)
        header_cols[1].markdown('<div class="table-header">반</div>', unsafe_allow_html=True)
        header_cols[2].markdown('<div class="table-header">오늘 나간 진도</div>', unsafe_allow_html=True)

        st.markdown("---")

        for period, class_name in TIMETABLE[day]:
            key = make_input_key(day, period, class_name, current_version)

            cols = st.columns([1.2, 1.3, 4.8])
            cols[0].write(period)
            cols[1].write(class_name)
            cols[2].text_input(
                label=f"{day} {period} {class_name}",
                key=key,
                label_visibility="collapsed",
                placeholder="예: 프랑스 혁명 서론",
            )

        st.button(
            f"{day}요일 저장하기",
            key=f"save_button_{day}",
            use_container_width=True,
            on_click=save_day_progress,
            args=(day,),
        )

        st.markdown("</div>", unsafe_allow_html=True)

        day_log_df = load_log_data()
        with st.expander("최근 저장된 내용 보기", expanded=False):
            latest_day_df = get_latest_day_view(day_log_df, day)
            if latest_day_df.empty:
                st.info("아직 저장된 기록이 없습니다.")
            else:
                st.dataframe(latest_day_df, use_container_width=True, hide_index=True)

# -----------------------------
# 전체 주간 기록
# -----------------------------
st.markdown("---")
st.markdown("### 전체 주간 기록")

log_df = load_log_data()
sorted_log_df = get_sorted_log_df(log_df)
display_log_df = get_display_log_df(sorted_log_df)

if display_log_df.empty:
    st.info("아직 저장된 기록이 없습니다.")
else:
    st.dataframe(
        display_log_df,
        use_container_width=True,
        hide_index=True,
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
