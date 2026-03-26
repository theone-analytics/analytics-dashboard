import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table, build_screen_category_sql, get_screen_categories

st.title("📱 화면 분석")

# --- 환경 선택 ---
config = project_env_selector()

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

# --- 화면 카테고리 매핑 (analytics_config.json에서 자동 생성) ---
SCREEN_CATEGORY_SQL = build_screen_category_sql(config)
if not SCREEN_CATEGORY_SQL or "WHERE FALSE" in SCREEN_CATEGORY_SQL:
    st.warning("화면 매핑을 불러올 수 없습니다. GitHub 토큰 설정을 확인하세요.")
    st.stop()


@st.cache_data(ttl=3600)
def get_screen_data(start: str, end: str, category_filter: str, _table: str, _config: dict):
    category_condition = ""
    if category_filter != "전체":
        category_condition = f"WHERE screen_category = '{category_filter}'"

    sql = f"""
    WITH screen_raw AS (
        SELECT
            PARSE_DATE('%Y%m%d', event_date) AS date,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'firebase_screen') AS screen_name,
            (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'engagement_time_msec') AS engagement_time_msec,
            COALESCE(user_id, user_pseudo_id) AS unique_user
        FROM {_table}
        WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
          AND event_name = 'screen_view'
    ),
    screen_with_category AS (
        SELECT
            s.date,
            s.screen_name,
            s.engagement_time_msec,
            s.unique_user,
            COALESCE(c.category, '기타') AS screen_category
        FROM screen_raw s
        LEFT JOIN ({SCREEN_CATEGORY_SQL}) c ON s.screen_name = c.name
    )
    SELECT
        screen_name,
        screen_category,
        COUNT(*) AS views,
        COUNT(DISTINCT unique_user) AS users,
        ROUND(AVG(engagement_time_msec / 1000), 2) AS avg_duration_sec
    FROM screen_with_category
    {category_condition}
    GROUP BY screen_name, screen_category
    ORDER BY views DESC
    """
    return query(sql, _config)


@st.cache_data(ttl=3600)
def get_screen_daily(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        PARSE_DATE('%Y%m%d', event_date) AS date,
        COUNT(*) AS views,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND event_name = 'screen_view'
    GROUP BY date
    ORDER BY date
    """
    return query(sql, _config)


# --- 카테고리 필터 ---
categories = get_screen_categories(config)
with col3:
    category_filter = st.selectbox("카테고리", categories)

# --- 데이터 조회 ---
screen_df = get_screen_data(start_str, end_str, category_filter, table, config)
daily_df = get_screen_daily(start_str, end_str, table, config)

# --- 스코어카드 ---
total_views = int(screen_df["views"].sum()) if not screen_df.empty else 0
total_users = int(screen_df["users"].sum()) if not screen_df.empty else 0
avg_duration = round(screen_df["avg_duration_sec"].mean(), 2) if not screen_df.empty else 0

col1, col2, col3 = st.columns(3)
col1.metric("총 화면 조회수", f"{total_views:,}")
col2.metric("순 사용자", f"{total_users:,}")
col3.metric("평균 체류시간", f"{avg_duration}초")

st.divider()

# --- 일별 추이 ---
st.subheader("일별 화면 조회 추이")
if not daily_df.empty:
    fig = px.line(
        daily_df,
        x="date",
        y=["views", "users"],
        markers=True,
        labels={"date": "날짜", "value": "수", "variable": "지표"},
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# --- TOP 15 차트 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("화면별 조회수 TOP 15")
    if not screen_df.empty:
        top_views = screen_df.nlargest(15, "views")
        fig = px.bar(
            top_views,
            x="views",
            y="screen_name",
            orientation="h",
            labels={"views": "조회수", "screen_name": "화면"},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("화면별 체류시간 TOP 15")
    if not screen_df.empty:
        top_duration = screen_df.nlargest(15, "avg_duration_sec")
        fig = px.bar(
            top_duration,
            x="avg_duration_sec",
            y="screen_name",
            orientation="h",
            labels={"avg_duration_sec": "평균 체류시간(초)", "screen_name": "화면"},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

# --- 상세 테이블 ---
st.subheader("화면 상세")
if not screen_df.empty:
    st.dataframe(
        screen_df.rename(columns={
            "screen_name": "화면 이름",
            "screen_category": "카테고리",
            "views": "조회수",
            "users": "순 사용자",
            "avg_duration_sec": "평균 체류시간(초)",
        }),
        use_container_width=True,
        hide_index=True,
    )
