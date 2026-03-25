import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import env_selector, query, events_table, get_event_name_map, get_event_category_map

st.set_page_config(page_title="이벤트 분석", page_icon="🎯", layout="wide")
st.title("🎯 이벤트 분석")

# --- 환경 선택 ---
config = env_selector()

# --- 이벤트 매핑 (analytics_config.json에서 자동 로드) ---
EVENT_NAME_MAP = get_event_name_map(config)
EVENT_CATEGORY_MAP = get_event_category_map(config)

CUSTOM_EVENTS = list(EVENT_NAME_MAP.keys())
if not CUSTOM_EVENTS:
    st.warning("이벤트 매핑을 불러올 수 없습니다. GitHub 토큰 설정을 확인하세요.")
    st.stop()
CUSTOM_EVENTS_SQL = ", ".join(f"'{e}'" for e in CUSTOM_EVENTS)

# --- 필터 ---
col1, col2, col3 = st.columns(3)
with col1:
    start_date = st.date_input(
        "시작일",
        value=date.today() - timedelta(days=7),
        max_value=date.today() - timedelta(days=1),
    )
with col2:
    end_date = st.date_input(
        "종료일",
        value=date.today() - timedelta(days=1),
        max_value=date.today() - timedelta(days=1),
    )

start_str = start_date.strftime("%Y%m%d")
end_str = end_date.strftime("%Y%m%d")
table = events_table(config)

categories = ["전체", "운행", "장부", "지갑", "커뮤니티", "바이크", "홈", "설정"]
with col3:
    category_filter = st.selectbox("카테고리", categories)


@st.cache_data(ttl=3600)
def get_event_data(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        event_name,
        COUNT(*) AS count,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND event_name IN ({CUSTOM_EVENTS_SQL})
    GROUP BY event_name
    ORDER BY count DESC
    """
    return query(sql, _config)


@st.cache_data(ttl=3600)
def get_event_daily(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        PARSE_DATE('%Y%m%d', event_date) AS date,
        COUNT(*) AS count
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND event_name IN ({CUSTOM_EVENTS_SQL})
    GROUP BY date
    ORDER BY date
    """
    return query(sql, _config)


# --- 데이터 조회 + 한글 매핑 ---
event_df = get_event_data(start_str, end_str, table, config)
daily_df = get_event_daily(start_str, end_str, table, config)

if not event_df.empty:
    event_df["event_name_kr"] = event_df["event_name"].map(EVENT_NAME_MAP).fillna(event_df["event_name"])
    event_df["category"] = event_df["event_name"].map(EVENT_CATEGORY_MAP).fillna("기타")

    if category_filter != "전체":
        event_df = event_df[event_df["category"] == category_filter]

# --- 스코어카드 ---
total_events = int(event_df["count"].sum()) if not event_df.empty else 0
total_users = int(event_df["users"].sum()) if not event_df.empty else 0
unique_events = len(event_df) if not event_df.empty else 0

col1, col2, col3 = st.columns(3)
col1.metric("총 이벤트 수", f"{total_events:,}")
col2.metric("이벤트 발생 사용자", f"{total_users:,}")
col3.metric("이벤트 종류", f"{unique_events}개")

st.divider()

# --- 일별 추이 ---
st.subheader("일별 이벤트 발생 추이")
if not daily_df.empty:
    fig = px.line(
        daily_df,
        x="date",
        y="count",
        markers=True,
        labels={"date": "날짜", "count": "이벤트 수"},
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# --- 차트 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("이벤트별 발생 횟수")
    if not event_df.empty:
        fig = px.bar(
            event_df,
            x="count",
            y="event_name_kr",
            orientation="h",
            color="category",
            labels={"count": "횟수", "event_name_kr": "이벤트", "category": "카테고리"},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("카테고리별 이벤트 분포")
    if not event_df.empty:
        category_df = event_df.groupby("category", as_index=False)["count"].sum()
        fig = px.pie(category_df, values="count", names="category", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

# --- 상세 테이블 ---
st.subheader("이벤트 상세")
if not event_df.empty:
    st.dataframe(
        event_df[["event_name_kr", "category", "count", "users"]].rename(columns={
            "event_name_kr": "이벤트",
            "category": "카테고리",
            "count": "발생 횟수",
            "users": "사용자 수",
        }),
        use_container_width=True,
        hide_index=True,
    )
