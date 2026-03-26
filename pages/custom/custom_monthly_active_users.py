import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("📊 월별 활성 사용자 추이")

# --- 프로젝트/환경 선택 ---
config = project_env_selector()

# --- 날짜 필터 ---
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "시작일",
        value=date.today() - timedelta(days=365),
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
def get_monthly_active_users(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        FORMAT_TIMESTAMP('%Y-%m', PARSE_TIMESTAMP('%Y%m%d', event_date)) AS month,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS active_users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
    GROUP BY month
    ORDER BY month
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_monthly_active_users(start_str, end_str, table, config)

# --- 스코어카드 ---
if not df.empty:
    total_users = df['active_users'].sum()
    avg_users = round(df['active_users'].mean(), 2)
    col1, col2 = st.columns(2)
    col1.metric("총 활성 사용자", f"{total_users:,}")
    col2.metric("월 평균 활성 사용자", f"{avg_users:,}")
else:
    st.info("데이터가 없습니다.")

st.divider()

# --- 차트 ---
if not df.empty:
    fig = px.line(df, x="month", y="active_users", markers=True, title="월별 활성 사용자 추이")
    fig.update_layout(hovermode="x unified", xaxis_title="월", yaxis_title="활성 사용자 수")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")