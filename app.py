# app.py
import os
from datetime import date, datetime, timedelta
import pandas as pd
import streamlit as st

# -------------------------------------------------
# 기본 설정
# -------------------------------------------------
st.set_page_config(
    page_title="교사 일과 플래너",
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
ROW_ORDER = PERIODS + ["종례"]

CLASS_MAP = {}
for day, items in TIMETABLE.items():
    for period, class_name in items:
        CLASS_MAP[(day, period)] = class_name

# -------------------------------------------------
# 키 생성
# -------------------------------------------------
def make_input_key(day: str, row_name: str, version: int) -> str:
    return f"content_{day}_{row_name}_v{version}"

def make_date_key(day: str, version: int) -> str:
    return f"lesson_date_{day}_v{version}"

def make_goal_key(day: str, version: int) -> str:
    return f"goal_{day}_v{version}"

# -------------------------------------------------
# 데이터 처리
# -------------------------------------------------
CORE_COLS = ["수업날짜", "기록일시", "요일", "구분", "교시", "반", "유형", "내용", "목표"]

def create_empty_log_df() -> pd.DataFrame:
    return pd.DataFrame(columns=CORE_COLS)

def save_log_data(df: pd.DataFrame) -> None:
    df.to_csv(SAVE_FILE, index=False, encoding="utf-8-sig")

def migrate_old_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    기존 파일 호환:
    - 예전 컬럼(진도, 메모 등)을 새 구조로 변환
    - 기존 CSV 내용은 유지
    """
    if df.empty:
        return create_empty_log_df()

    old = df.copy()
    for col in ["수업날짜", "기록일시", "요일", "교시", "반", "진도", "메모"]:
        if col not in old.columns:
            old[col] = ""

    rows = []

    for _, row in old.iterrows():
        lesson_date = str(row.get("수업날짜", "")).strip()
        record_time = str(row.get("기록일시", "")).strip()
        day = str(row.get("요일", "")).strip()
        period = str(row.get("교시", "")).strip()
        class_name = str(row.get("반", "")).strip()
        progress = str(row.get("진도", "")).strip()
        memo = str(row.get("메모", "")).strip()

        if progress:
            rows.append(
                {
                    "수업날짜": lesson_date,
                    "기록일시": record_time,
                    "요일": day,
                    "구분": "교시",
                    "교시": period,
                    "반": class_name,
                    "유형": "수업" if class_name else "할일",
                    "내용": progress,
                    "목표": "",
                }
            )

        if memo:
            rows.append(
                {
                    "수업날짜": lesson_date,
                    "기록일시": record_time,
                    "요일": day,
                    "구분": "종례",
                    "교시": "종례",
                    "반": "",
                    "유형": "종례",
                    "내용": memo,
                    "목표": "",
                }
            )

    if not rows:
        return create_empty_log_df()

    migrated = pd.DataFrame(rows, columns=CORE_COLS).fillna("")
    migrated = migrated.drop_duplicates()
    return migrated

def load_log_data() -> pd.DataFrame:
    if not os.path.exists(SAVE_FILE):
        df = create_empty_log_df()
        save_log_data(df)
        return df

    try:
        raw = pd.read_csv(SAVE_FILE, dtype=str).fillna("")
    except Exception:
        df = create_empty_log_df()
        save_log_data(df)
        return df

    # 이미 새 구조면 그대로 사용
    if set(CORE_COLS).issubset(raw.columns):
        df = raw[CORE_COLS].copy().fillna("")
        save_log_data(df)
        return df

    # 예전 구조면 마이그레이션
    df = migrate_old_df(raw)
    save_log_data(df)
    return df

def prepare_log_df(df: pd.DataFrame) -> pd.DataFrame:
    temp = df.copy()
    temp["수업날짜_dt"] = pd.to_datetime(temp["수업날짜"], errors="coerce")
    temp["기록일시_dt"] = pd.to_datetime(temp["기록일시"], errors="coerce")
    temp["주차시작"] = temp["수업날짜_dt"].dt.date.apply(
        lambda x: get_monday(x) if pd.notna(x) else pd.NaT
    )
    return temp

# -------------------------------------------------
# 날짜/주차 유틸
# -------------------------------------------------
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

def get_available_week_starts(df: pd.DataFrame) -> list[date]:
    week_starts = []

    if not df.empty and "주차시작" in df.columns:
        for v in df["주차시작"].dropna().tolist():
            if isinstance(v, date):
                week_starts.append(v)

    current_week = get_monday(date.today())
    if current_week not in week_starts:
        week_starts.append(current_week)

    return sorted(set(week_starts), reverse=True)

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

# -------------------------------------------------
# 표시용 데이터
# -------------------------------------------------
def get_cell_default_label(day: str, period: str) -> str:
    return CLASS_MAP.get((day, period), "")

def get_weekly_list_df(week_df: pd.DataFrame) -> pd.DataFrame:
    if week_df.empty:
        return pd.DataFrame(
            columns=["수업날짜", "요일", "구분", "교시", "학급", "유형", "목표", "내용"]
        )

    temp = week_df.sort_values(
        by=["수업날짜_dt", "기록일시_dt"],
        ascending=[False, False]
    ).copy()

    display_df = temp[["수업날짜", "요일", "구분", "교시", "반", "유형", "목표", "내용"]].rename(
        columns={"반": "학급"}
    )
    return display_df.reset_index(drop=True)

def truncate_text(text: str, max_len: int = 26) -> str:
    text = str(text).strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"

def build_goal_summary(week_df: pd.DataFrame) -> dict:
    """
    각 요일별 가장 최근 목표
    """
    summary = {day: "" for day in DAYS}
    if week_df.empty:
        return summary

    temp = week_df[week_df["목표"].fillna("").astype(str).str.strip() != ""].copy()
    if temp.empty:
        return summary

    temp = temp.sort_values(
        by=["수업날짜_dt", "기록일시_dt"],
        ascending=[False, False]
    )
    latest = temp.groupby("요일", as_index=False).first()

    for _, row in latest.iterrows():
        day = str(row["요일"]).strip()
        goal = str(row["목표"]).strip()
        if day in DAYS:
            summary[day] = goal
    return summary

def build_timetable_grid(week_df: pd.DataFrame) -> pd.DataFrame:
    """
    8x5 표:
    - 1~7교시 + 종례
    - 수업 있는 칸: 학급명 + 진도
    - 공강 칸: 할 일
    - 종례 행: 종례 내용
    - 같은 주차, 같은 요일/행 여러 기록이면 가장 최근 기록 사용
    """
    grid = pd.DataFrame("", index=ROW_ORDER, columns=DAYS)

    # 기본 시간표 학급명 표시
    for day in DAYS:
        for period in PERIODS:
            class_name = get_cell_default_label(day, period)
            grid.at[period, day] = class_name if class_name else ""

    if week_df.empty:
        return grid

    temp = week_df.sort_values(
        by=["수업날짜_dt", "기록일시_dt"],
        ascending=[False, False]
    ).copy()

    latest = temp.groupby(["요일", "교시"], as_index=False).first()

    for _, row in latest.iterrows():
        day = str(row["요일"]).strip()
        row_name = str(row["교시"]).strip()
        content = str(row["내용"]).strip()
        entry_type = str(row["유형"]).strip()
        class_name = str(row["반"]).strip()

        if day not in DAYS or row_name not in ROW_ORDER:
            continue

        if row_name == "종례":
            grid.at[row_name, day] = f"<div class='memo-text'>{content}</div>"
            continue

        if entry_type == "수업":
            class_html = f"<div class='class-name'>{class_name}</div>" if class_name else ""
            content_html = f"<div class='progress-text'>{content}</div>" if content else ""
            grid.at[row_name, day] = class_html + content_html
        elif entry_type == "할일":
            if content:
                grid.at[row_name, day] = f"<div class='todo-text'>할 일: {content}</div>"
        else:
            # 혹시 예외 데이터가 있어도 내용은 보이게
            if class_name:
                grid.at[row_name, day] = (
                    f"<div class='class-name'>{class_name}</div>"
                    f"<div class='progress-text'>{content}</div>"
                )
            else:
                grid.at[row_name, day] = f"<div class='todo-text'>{content}</div>"

    return grid

def render_goal_summary_html(goal_summary: dict) -> str:
    html = """
    <style>
    .goal-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        margin-bottom: 1rem;
    }
    .goal-table th, .goal-table td {
        border: 1px solid #d0d6de;
        padding: 8px 10px;
        text-align: center;
        vertical-align: middle;
    }
    .goal-table th {
        background: #eef3f8;
        font-weight: 700;
    }
    .goal-title-cell {
        width: 120px;
        background: #eef3f8;
        font-weight: 700;
    }
    .goal-cell {
        background: #fafcff;
        font-size: 0.95rem;
        line-height: 1.4;
        min-height: 52px;
    }
    </style>
    <table class="goal-table">
        <tr>
            <th class="goal-title-cell">주요 목표</th>
    """
    for day in DAYS:
        html += f"<th>{day}</th>"
    html += "</tr><tr><td class='goal-title-cell'>내용</td>"
    for day in DAYS:
        value = str(goal_summary.get(day, "")).strip()
        html += f"<td class='goal-cell'>{value if value else ''}</td>"
    html += "</tr></table>"
    return html

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
        border: 1px solid #8f8f8f;
        background: white;
    }
    .tt th, .tt td {
        border: 1px solid #8f8f8f;
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
        font-size: 1.4rem;
        font-weight: 600;
        height: 92px;
    }
    .tt .homeroom {
        font-size: 1rem;
    }
    .tt .cell {
        background: #eeeeee;
        height: 92px;
        padding: 6px 8px;
        word-break: keep-all;
        white-space: normal;
        line-height: 1.25;
    }
    .tt .class-name {
        font-size: 1.15rem;
        font-weight: 600;
        color: #222;
    }
    .tt .progress-text {
        margin-top: 4px;
        font-size: 0.9rem;
        color: #303030;
    }
    .tt .todo-text {
        font-size: 0.92rem;
        color: #2d4b67;
        font-weight: 500;
    }
    .tt .memo-text {
        font-size: 0.9rem;
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

    row_label_map = {
        "1교시": "1",
        "2교시": "2",
        "3교시": "3",
        "4교시": "4",
        "5교시": "5",
        "6교시": "6",
        "7교시": "7",
        "종례": "종례",
    }

    for row_name in ROW_ORDER:
        left_class = "period homeroom" if row_name == "종례" else "period"
        html += f"<tr><td class='{left_class}'>{row_label_map[row_name]}</td>"

        for day in DAYS:
            value = str(grid.at[row_name, day]).strip()
            html += f"<td class='cell'>{value if value else ''}</td>"

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
def save_day_planner(day: str) -> None:
    current_version = st.session_state["input_versions"][day]

    date_key = make_date_key(day, current_version)
    goal_key = make_goal_key(day, current_version)

    selected_lesson_date = to_date_safe(st.session_state.get(date_key, date.today()))
    goal_text = str(st.session_state.get(goal_key, "")).strip()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    lesson_date_str = selected_lesson_date.strftime("%Y-%m-%d")

    rows_to_add = []
    used_keys = [date_key, goal_key]

    for row_name in ROW_ORDER:
        input_key = make_input_key(day, row_name, current_version)
        used_keys.append(input_key)
        content_text = str(st.session_state.get(input_key, "")).strip()

        if not content_text:
            continue

        if row_name == "종례":
            rows_to_add.append(
                {
                    "수업날짜": lesson_date_str,
                    "기록일시": current_time,
                    "요일": day,
                    "구분": "종례",
                    "교시": "종례",
                    "반": "",
                    "유형": "종례",
                    "내용": content_text,
                    "목표": goal_text,
                }
            )
        else:
            class_name = get_cell_default_label(day, row_name)
            entry_type = "수업" if class_name else "할일"

            rows_to_add.append(
                {
                    "수업날짜": lesson_date_str,
                    "기록일시": current_time,
                    "요일": day,
                    "구분": "교시",
                    "교시": row_name,
                    "반": class_name,
                    "유형": entry_type,
                    "내용": content_text,
                    "목표": goal_text,
                }
            )

    # 목표만 입력한 경우도 저장
    if not rows_to_add and goal_text:
        rows_to_add.append(
            {
                "수업날짜": lesson_date_str,
                "기록일시": current_time,
                "요일": day,
                "구분": "목표",
                "교시": "목표",
                "반": "",
                "유형": "목표",
                "내용": "",
                "목표": goal_text,
            }
        )

    if not rows_to_add:
        st.session_state["save_message"] = f"{day}요일은 저장할 내용이 없습니다."
        st.session_state["save_message_type"] = "warning"
        st.rerun()

    existing_df = load_log_data()
    new_df = pd.DataFrame(rows_to_add, columns=CORE_COLS)
    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
    save_log_data(updated_df)

    st.session_state["selected_week_start"] = get_monday(selected_lesson_date)

    for key in used_keys:
        if key in st.session_state:
            del st.session_state[key]

    st.session_state["input_versions"][day] += 1
    st.session_state["save_message"] = (
        f"{day}요일 내용 {len(rows_to_add)}건이 저장되었습니다. "
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
    .muted {
        color: #777;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# 제목
# -------------------------------------------------
st.markdown('<div class="main-title">📚 교사 일과 플래너</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-text">수업 진도, 공강 할 일, 오늘의 목표, 종례 내용을 주차별로 정리하세요.</div>',
    unsafe_allow_html=True,
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
        goal_key = make_goal_key(day, current_version)

        if date_key not in st.session_state:
            weekday_idx = DAYS.index(day)
            st.session_state[date_key] = selected_week_start + timedelta(days=weekday_idx)

        if goal_key not in st.session_state:
            st.session_state[goal_key] = ""

        st.date_input(
            "수업 날짜 선택",
            key=date_key,
            value=st.session_state[date_key],
        )

        st.text_input(
            "오늘의 주요 목표",
            key=goal_key,
            placeholder="예: 2-10 개념 이해 완료, 생활지도 점검, 공문 처리 마무리",
        )

        st.markdown("")
        header_cols = st.columns([1.0, 1.4, 4.8])
        header_cols[0].markdown('<div class="table-header">교시</div>', unsafe_allow_html=True)
        header_cols[1].markdown('<div class="table-header">학급/구분</div>', unsafe_allow_html=True)
        header_cols[2].markdown('<div class="table-header">진도 또는 할 일</div>', unsafe_allow_html=True)

        st.markdown("---")

        for period in PERIODS:
            class_name = get_cell_default_label(day, period)
            input_key = make_input_key(day, period, current_version)

            if input_key not in st.session_state:
                st.session_state[input_key] = ""

            cols = st.columns([1.0, 1.4, 4.8])
            cols[0].write(period.replace("교시", ""))

            if class_name:
                cols[1].write(class_name)
                placeholder = "예: 프랑스 혁명 서론"
            else:
                cols[1].markdown('<span class="muted">공강</span>', unsafe_allow_html=True)
                placeholder = "예: 생활기록부 정리, 학부모 연락, 수행평가 채점"

            cols[2].text_input(
                label=f"{day} {period}",
                key=input_key,
                label_visibility="collapsed",
                placeholder=placeholder,
            )

        homeroom_key = make_input_key(day, "종례", current_version)
        if homeroom_key not in st.session_state:
            st.session_state[homeroom_key] = ""

        st.markdown("#### 종례")
        st.text_area(
            "종례",
            key=homeroom_key,
            label_visibility="collapsed",
            height=110,
            placeholder="예: 숙제 공지, 준비물 안내, 생활지도 사항, 전달사항 등을 기록하세요.",
        )

        st.button(
            f"{day}요일 저장하기",
            key=f"save_button_{day}",
            use_container_width=True,
            on_click=save_day_planner,
            args=(day,),
        )

        st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# 주간 대시보드
# -------------------------------------------------
st.markdown("---")
st.markdown("## 주간 시간표 플래너")
st.caption(f"현재 조회 주차: {format_week_label(selected_week_start)}")

goal_summary = build_goal_summary(selected_week_df)
st.markdown(render_goal_summary_html(goal_summary), unsafe_allow_html=True)

grid_df = build_timetable_grid(selected_week_df)
st.markdown(render_timetable_html(grid_df), unsafe_allow_html=True)

# -------------------------------------------------
# 선택 주차 리스트
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
