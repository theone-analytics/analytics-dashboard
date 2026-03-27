import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("📉 사용자 이탈 퍼널 분석")

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
def get_churn_funnel_data(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    WITH user_sessions AS (
        SELECT
            COALESCE(user_id, user_pseudo_id) AS uid,
            COUNTIF(event_name = 'session_start') AS sessions,
            SUM((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'engagement_time_msec')) / 1000 AS total_engagement_seconds
        FROM {_table}
        WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
        GROUP BY uid
    )
    SELECT
        CASE
            WHEN sessions = 1 THEN '1회 세션'
            WHEN sessions BETWEEN 2 AND 5 THEN '2-5회 세션'
            WHEN sessions > 5 THEN '5회 이상 세션'
            ELSE '세션 없음'
        END AS session_group,
        COUNT(*) AS users,
        AVG(total_engagement_seconds) AS avg_engagement_seconds
    FROM user_sessions
    GROUP BY session_group
    ORDER BY users DESC
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_churn_funnel_data(start_str, end_str, table, config)

# --- 데이터 확인 ---
if not df.empty:
    st.metric("총 사용자 수", f"{df['users'].sum():,}")
    st.metric("평균 체류 시간 (초)", f"{df['avg_engagement_seconds'].mean():.2f}")
else:
    st.metric("총 사용자 수", "0")
    st.metric("평균 체류 시간 (초)", "0")

st.divider()

# --- 차트 ---
if not df.empty:
    fig = px.bar(
        df,
        x="session_group",
        y="users",
        text="users",
        labels={"session_group": "세션 그룹", "users": "사용자 수"},
        title="사용자 이탈 퍼널"
    )
    fig.update_traces(texttemplate='%{text:,}', textposition='outside')
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")