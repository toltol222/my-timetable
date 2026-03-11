# app.py
import os
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st

# -------------------------------------------------
# 기본 설정
# -------------------------------------------------
st.set_page_config(
    page_title="주간 수업 진도 체크",
    page_icon="📚",
    layout="wide",
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
PERIODS = ["1교시", "2교시", "3교시", "4교시", "5교시", "6교시", "7교시"]


# -------------------------------------------------
# 유틸
# -------------------------------------------------
def make_input_key(day: str, period: str, class_name: str, version: int) -> str:
    return f"progress_{day}_{period}_{class_name}_v{version}"


def make_date_key(day: str, version: int) -> str:
    return f"lesson_date_{day}_v{version}"


def make_memo_key(day: str, version: int) -> str:
    return f"memo_{day}_v{version}"


def create_empty_log_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["수업날짜", "기록일시", "요일", "교시", "반", "진도", "메모"])


def save_log_data(df: pd.DataFrame) -> None:
    df.to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")


def load_log_data() -> pd.DataFrame:
    if not os.path.exists(SAVE_FILE):
        df = create_empty_log_df()
        save_log_data(df)
        return df

    try:
        df = pd.read_csv(SAVE_FILE, dtype=str).fillna("")
    except Exception:
        df = create_empty_log_df()
        save_log_data(df)
        return df

    required_cols = ["수업날짜", "기록일시", "요일", "교시", "반", "진도", "메모"]

    # 예전 파일 호환
    if "수업날짜" not in df.columns and {"기록일시", "요일", "교시", "반", "진도"}.issubset(df.columns):
        df["수업날짜"] = ""

    if "메모" not in df.columns:
        df["메모"] = ""

    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    df = df[required_cols]
    save_log_data(df)
    return df


def to_date_safe(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return date.today()


def get_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def get_friday(d: date) -> date:
    monday = get_monday(d)
    return monday + timedelta(days=4)


def get_week_of_month(d: date) -> int:
    first_day = d.replace(day=1)
    first_monday_offset = (7 - first_day.weekday()) % 7
    first_monday = first_day + timedelta(days=first_monday_offset)

    monday = get_monday(d)
    if monday < first_monday:
        return 1
    return ((monday - first_monday).days // 7) + 2


def format_week_label(week_start: date) -> str:
    week_end = week_start + timedelta(days=4)
    month_week = get_week_of_month(week_start)
    return f"{week_start.year}년 {week_start.month}월 {month_week}주차 ({week_start:%m.%d}~{week_end:%m.%d})"


def prepare_log_df(df: pd.DataFrame) -> pd.DataFrame:
    temp = df.copy()
    temp["수업날짜_dt"] = pd.to_datetime(temp["수업날짜"], errors="coerce")
    temp["기록일시_dt"] = pd.to_datetime(temp["기록일시"], errors="coerce")
    temp["주차시작"] = temp["수업날짜_dt"].dt.date.apply(
        lambda x: get_monday(x) if pd.notna(x) else pd.NaT
    )
    return temp


def get_available_week_starts(df: pd.DataFrame) -> list[date]:
    week_starts = []

    if not df.empty and "주차시작" in df.columns:
        for v in df["주차시작"].dropna().tolist():
            if isinstance(v, date):
                week_starts.append(v)

    current_week = get_monday(date.today())
    if current_week not in week_starts:
        week_starts.append(current_week)

    week_starts = sorted(set(week_starts), reverse=True)
    return week_starts


def filter_df_by_week(df: pd.DataFrame, week_start: date) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    week_end = week_start + timedelta(days=4)
    mask = (
        df["수업날짜_dt"].notna()
        & (df["수업날짜_dt"].dt.date >= week_start)
        & (df["수업날짜_dt"].dt.date <= week_end)
    )
    return df.loc[mask].copy()


def get_weekly_list_df(week_df: pd.DataFrame) -> pd.DataFrame:
    if week_df.empty:
        return pd.DataFrame(columns=["수업날짜", "요일", "교시", "학급", "진도내용", "메모"])

    temp = week_df.sort_values(
        by=["수업날짜_dt", "기록일시_dt"],
        ascending=[False, False]
    ).copy()

    display_df = temp[["수업날짜", "요일", "교시", "반", "진도", "메모"]].rename(
        columns={"반": "학급", "진도": "진도내용"}
    )
    return display_df.reset_index(drop=True)


def truncate_text(text: str, max_len: int = 22) -> str:
    text = str(text).strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def build_timetable_grid(week_df: pd.DataFrame) -> pd.DataFrame:
    """
    이미지와 같은 7x5 시간표 생성.
    기본 시간표 학급명을 채워두고,
    선택 주차에 기록된 진도/메모가 있으면 가장 최근 기록을 반영.
    """
    grid = pd.DataFrame("", index=PERIODS, columns=DAYS)

    for day, lessons in TIMETABLE.items():
        for period, class_name in lessons:
            grid.at[period, day] = class_name

    if week_df.empty:
        return grid

    temp = week_df.sort_values(
        by=["수업날짜_dt", "기록일시_dt"],
        ascending=[False, False]
    ).copy()

    latest = temp.groupby(["요일", "교시"], as_index=False).first()

    for _, row in latest.iterrows():
        day = str(row["요일"]).strip()
        period = str(row["교시"]).strip()
        class_name = str(row["반"]).strip()
        progress = str(row["진도"]).strip()
        memo = str(row["메모"]).strip()

        if day in DAYS and period in PERIODS:
            parts = [f"<div class='class-name'>{class_name}</div>"]

            if progress:
                parts.append(f"<div class='progress-text'>{progress}</div>")

            if memo:
                parts.append(f"<div class='memo-text'>메모: {truncate_text(memo, 18)}</div>")

            grid.at[period, day] = "".join(parts)

    return grid


def render_timetable_html(grid: pd.DataFrame) -> str:
    html = """
    <style>
    .tt-wrap {
        margin-top: 0.5rem;
        margin-bottom: 1.2rem;
    }
    .tt {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        border: 1px solid #9a9a9a;
        background: white;
    }
    .tt th, .tt td {
        border: 1px solid #9a9a9a;
        text-align: center;
        vertical-align: middle;
        padding: 0;
    }
    .tt thead th {
        background: #d9d9d9;
        height: 54px;
        font-size: 1.05rem;
        font-weight: 700;
    }
    .tt .left-top {
        width: 95px;
        background: #d9d9d9;
    }
    .tt .period {
        width: 95px;
        background: #d9d9d9;
        font-size: 1.8rem;
        font-weight: 500;
        height: 90px;
    }
    .tt .cell {
        background: #eeeeee;
        height: 90px;
        padding: 6px 8px;
        font-size: 1rem;
        line-height: 1.25;
        word-break: keep-all;
        white-space: normal;
    }
    .tt .empty-cell {
        color: transparent;
    }
    .tt .class-name {
        font-size: 1.15rem;
        font-weight: 600;
        color: #222;
    }
    .tt .progress-text {
        margin-top: 4px;
        font-size: 0.9rem;
        font-weight: 400;
        color: #303030;
    }
    .tt .memo-text {
        margin-top: 4px;
        font-size: 0.82rem;
        color: #5a5a5a;
    }
    </style>
    <div class="tt-wrap">
    <table class="tt">
        <thead>
            <tr>
                <th class="left-top"></th>
                <th>월</th>
                <th>화</th>
                <th>수</th>
                <th>목</th>
                <th>금</th>
            </tr>
        </thead>
        <tbody>
    """

    period_num_map = {
        "1교시": "1", "2교시": "2", "3교시": "3", "4교시": "4",
        "5교시": "5", "6교시": "6", "7교시": "7"
    }

    for period in PERIODS:
        html += f"<tr><td class='period'>{period_num_map[period]}</td>"
        for day in DAYS:
            value = str(grid.at[period, day]).strip()
            if value == "":
                html += "<td class='cell empty-cell'>.</td>"
            else:
                html += f"<td class='cell'>{value}</td>"
        html += "</tr>"

    html += "</tbody></table></div>"
    return html


# -------------------------------------------------
# 세션 상태
# -------------------------------------------------
if "input_versions" not in st.session_state:
    st.session_state["input_versions"] = {day: 0 for day in DAYS}

if "save_message" not in st.session_state:
    st.session_state["save_message"] = ""

if "save_message_type" not in st.session_state:
    st.session_state["save_message_type"] = "success"

if "selected_week_start" not in st.session_state:
    st.session_state["selected_week_start"] = get_monday(date.today())


# -------------------------------------------------
# 저장 콜백
# -------------------------------------------------
def save_day_progress(day: str) -> None:
    current_version = st.session_state["input_versions"][day]
    date_key = make_date_key(day, current_version)
    memo_key = make_memo_key(day, current_version)

    selected_lesson_date = to_date_safe(st.session_state.get(date_key, date.today()))
    memo_text = str(st.session_state.get(memo_key, "")).strip()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    lesson_date_str = selected_lesson_date.strftime("%Y-%m-%d")

    rows_to_add = []
    used_keys = [date_key, memo_key]

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
                    "메모": memo_text,
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

    st.session_state["selected_week_start"] = get_monday(selected_lesson_date)

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


# -------------------------------------------------
# 스타일
# -------------------------------------------------
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

# -------------------------------------------------
# 제목
# -------------------------------------------------
st.markdown('<div class="main-title">📚 주간 수업 진도 체크</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-text">요일별 시간표를 확인하고 오늘 나간 진도와 종례 메모를 기록하세요.</div>',
    unsafe_allow_html=True
)

if st.session_state["save_message"]:
    if st.session_state["save_message_type"] == "success":
        st.success(st.session_state["save_message"])
    else:
        st.warning(st.session_state["save_message"])

    st.session_state["save_message"] = ""
    st.session_state["save_message_type"] = "success"

# -------------------------------------------------
# 상단: 주차 선택
# -------------------------------------------------
raw_df = load_log_data()
prepared_df = prepare_log_df(raw_df)
available_week_starts = get_available_week_starts(prepared_df)

if st.session_state["selected_week_start"] not in available_week_starts:
    available_week_starts = [st.session_state["selected_week_start"]] + available_week_starts
    available_week_starts = sorted(set(available_week_starts), reverse=True)

week_label_map = {wk: format_week_label(wk) for wk in available_week_starts}

st.markdown("### 조회 주차 선택")
selected_week_start = st.selectbox(
    "조회할 주차를 선택하세요",
    options=available_week_starts,
    index=available_week_starts.index(st.session_state["selected_week_start"]),
    format_func=lambda x: week_label_map[x],
)

st.session_state["selected_week_start"] = selected_week_start
selected_week_df = filter_df_by_week(prepared_df, selected_week_start)

# -------------------------------------------------
# 입력 탭
# -------------------------------------------------
tabs = st.tabs(DAYS)

for idx, day in enumerate(DAYS):
    with tabs[idx]:
        st.markdown(f"### {day}요일 입력")

        st.markdown('<div class="block-wrap">', unsafe_allow_html=True)

        current_version = st.session_state["input_versions"][day]
        date_key = make_date_key(day, current_version)
        memo_key = make_memo_key(day, current_version)

        if date_key not in st.session_state:
            weekday_idx = DAYS.index(day)
            st.session_state[date_key] = selected_week_start + timedelta(days=weekday_idx)

        if memo_key not in st.session_state:
            st.session_state[memo_key] = ""

        st.date_input(
            "수업 날짜 선택",
            key=date_key,
            value=st.session_state[date_key],
        )

        st.markdown("")

        header_cols = st.columns([1.1, 1.2, 4.7])
        header_cols[0].markdown('<div class="table-header">교시</div>', unsafe_allow_html=True)
        header_cols[1].markdown('<div class="table-header">학급</div>', unsafe_allow_html=True)
        header_cols[2].markdown('<div class="table-header">오늘 나간 진도</div>', unsafe_allow_html=True)

        st.markdown("---")

        for period, class_name in TIMETABLE[day]:
            key = make_input_key(day, period, class_name, current_version)
            cols = st.columns([1.1, 1.2, 4.7])

            cols[0].write(period.replace("교시", ""))
            cols[1].write(class_name)
            cols[2].text_input(
                label=f"{day} {period} {class_name}",
                key=key,
                label_visibility="collapsed",
                placeholder="예: 프랑스 혁명 서론",
            )

        st.markdown("#### 종례 및 기타 메모")
        st.text_area(
            "종례 및 기타 메모",
            key=memo_key,
            label_visibility="collapsed",
            height=120,
            placeholder="예: 숙제 공지, 준비물 안내, 생활지도 사항, 특이사항 등을 기록하세요.",
        )

        st.button(
            f"{day}요일 저장하기",
            key=f"save_button_{day}",
            use_container_width=True,
            on_click=save_day_progress,
            args=(day,),
        )

        st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# 시간표형 대시보드
# -------------------------------------------------
st.markdown("---")
st.markdown("## 주간 시간표 진도표")
st.caption(f"현재 조회 주차: {format_week_label(selected_week_start)}")

grid_df = build_timetable_grid(selected_week_df)
st.markdown(render_timetable_html(grid_df), unsafe_allow_html=True)

# -------------------------------------------------
# 선택 주차 기록 리스트
# -------------------------------------------------
st.markdown("---")
st.markdown("## 선택 주차 전체 기록")

weekly_list_df = get_weekly_list_df(selected_week_df)

if weekly_list_df.empty:
    st.info("선택한 주차에 저장된 기록이 없습니다.")
else:
    st.dataframe(
        weekly_list_df,
        use_container_width=True,
        hide_index=True,
    )

# -------------------------------------------------
# CSV 다운로드
# -------------------------------------------------
csv_data = raw_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    label="CSV 백업 다운로드",
    data=csv_data,
    file_name="weekly_progress_backup.csv",
    mime="text/csv",
    use_container_width=True,
)

st.caption(f"저장 파일: {SAVE_FILE}")
