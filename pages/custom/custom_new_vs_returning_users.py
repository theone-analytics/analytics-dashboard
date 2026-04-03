import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("📊 최근 30일 신규 vs 재방문 사용자 비교")

# --- 프로젝트/환경 선택 ---
config = project_env_selector()

# --- 날짜 필터 ---
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "시작일",
        value=date.today() - timedelta(days=30),
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

@st.cache_data(ttl=3600)
def get_new_vs_returning_users(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    WITH first_time_users AS (
        SELECT
            user_id AS uid,
            MIN(event_date) AS first_date
        FROM {_table}
        WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
          AND user_id IS NOT NULL
        GROUP BY uid
    ),
    daily_users AS (
        SELECT
            PARSE_DATE('%Y%m%d', event_date) AS date,
            user_id AS uid
        FROM {_table}
        WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
          AND user_id IS NOT NULL
    )
    SELECT
        u.date,
        COUNT(DISTINCT CASE WHEN u.date = PARSE_DATE('%Y%m%d', f.first_date) THEN u.uid END) AS new_users,
        COUNT(DISTINCT CASE WHEN u.date > PARSE_DATE('%Y%m%d', f.first_date) THEN u.uid END) AS returning_users
    FROM daily_users u
    LEFT JOIN first_time_users f ON u.uid = f.uid
    GROUP BY u.date
    ORDER BY u.date
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_new_vs_returning_users(start_str, end_str, table, config)

# --- 스코어카드 ---
col1, col2 = st.columns(2)
if not df.empty:
    col1.metric("신규 사용자 수", f"{int(df['new_users'].sum()):,}")
    col2.metric("재방문 사용자 수", f"{int(df['returning_users'].sum()):,}")
else:
    col1.metric("신규 사용자 수", "0")
    col2.metric("재방문 사용자 수", "0")

st.divider()

# --- 차트 ---
if not df.empty:
    fig = px.bar(
        df,
        x="date",
        y=["new_users", "returning_users"],
        labels={"date": "날짜", "value": "사용자 수", "variable": "유형"},
        title="일별 신규 vs 재방문 사용자 추이",
    )
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%m/%d")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")