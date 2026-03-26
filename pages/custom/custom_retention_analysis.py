import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("📊 리텐션 분석")

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
def get_retention_data(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    WITH first_day AS (
        SELECT
            COALESCE(user_id, user_pseudo_id) AS uid,
            MIN(event_date) AS first_date
        FROM {_table}
        WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
        GROUP BY uid
    ),
    return_day AS (
        SELECT DISTINCT
            COALESCE(user_id, user_pseudo_id) AS uid,
            event_date
        FROM {_table}
        WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
    )
    SELECT
        PARSE_DATE('%Y%m%d', f.first_date) AS cohort_date,
        COUNT(DISTINCT f.uid) AS cohort_size,
        COUNT(DISTINCT CASE
            WHEN DATE_DIFF(PARSE_DATE('%Y%m%d', r.event_date), PARSE_DATE('%Y%m%d', f.first_date), DAY) = 1
            THEN f.uid END) AS day1_return,
        COUNT(DISTINCT CASE
            WHEN DATE_DIFF(PARSE_DATE('%Y%m%d', r.event_date), PARSE_DATE('%Y%m%d', f.first_date), DAY) = 7
            THEN f.uid END) AS day7_return,
        COUNT(DISTINCT CASE
            WHEN DATE_DIFF(PARSE_DATE('%Y%m%d', r.event_date), PARSE_DATE('%Y%m%d', f.first_date), DAY) = 30
            THEN f.uid END) AS day30_return
    FROM first_day f
    LEFT JOIN return_day r ON f.uid = r.uid
    GROUP BY cohort_date
    ORDER BY cohort_date
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_retention_data(start_str, end_str, table, config)

# --- 스코어카드 ---
col1, col2, col3 = st.columns(3)
if not df.empty:
    total_cohort_size = df['cohort_size'].sum()
    day1_total = df['day1_return'].sum()
    day7_total = df['day7_return'].sum()
    day30_total = df['day30_return'].sum()

    col1.metric("총 코호트 크기", f"{total_cohort_size:,}")
    col2.metric("Day 1 리텐션", f"{(day1_total / total_cohort_size * 100):.2f}%" if total_cohort_size > 0 else "0%")
    col3.metric("Day 7 리텐션", f"{(day7_total / total_cohort_size * 100):.2f}%" if total_cohort_size > 0 else "0%")
else:
    col1.metric("총 코호트 크기", "0")
    col2.metric("Day 1 리텐션", "0%")
    col3.metric("Day 7 리텐션", "0%")

st.divider()

# --- 차트 ---
if not df.empty:
    df['day1_rate'] = (df['day1_return'] / df['cohort_size']) * 100
    df['day7_rate'] = (df['day7_return'] / df['cohort_size']) * 100
    df['day30_rate'] = (df['day30_return'] / df['cohort_size']) * 100

    fig = px.line(
        df,
        x="cohort_date",
        y=["day1_rate", "day7_rate", "day30_rate"],
        markers=True,
        labels={"cohort_date": "코호트 날짜", "value": "리텐션율 (%)", "variable": "리텐션"},
        title="리텐션 분석"
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")