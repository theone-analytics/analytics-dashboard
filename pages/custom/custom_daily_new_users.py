import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.set_page_config(page_title="일별 신규 사용자 수", page_icon="📊", layout="wide")
st.title("📊 일별 신규 사용자 수")

# --- 프로젝트/환경 선택 ---
config = project_env_selector()

# --- 날짜 필터 ---
col1, col2 = st.columns(2)
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

@st.cache_data(ttl=3600)
def get_data(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT 
        PARSE_DATE('%Y%m%d', event_date) AS date,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS new_users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND event_name = 'first_open'
    GROUP BY date
    ORDER BY date
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_data(start_str, end_str, table, config)

# --- 스코어카드 ---
col1, col2, col3 = st.columns(3)
if not df.empty:
    total_new_users = df['new_users'].sum()
    col1.metric("총 신규 사용자 수", f"{total_new_users:,}")
    col2.metric("평균 일별 신규 사용자 수", f"{total_new_users / len(df):,.2f}")
else:
    col1.metric("총 신규 사용자 수", "0")
    col2.metric("평균 일별 신규 사용자 수", "0")

st.divider()

# --- 차트 ---
if not df.empty:
    fig = px.line(df, x="date", y="new_users", markers=True, title="일별 신규 사용자 수 추이")
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")