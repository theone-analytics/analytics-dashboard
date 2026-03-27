import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("📊 3월 통계")

st.info("참고: Firebase Analytics에서 제공하는 데이터 범위 내에서 생성되었습니다.")

# --- 프로젝트/환경 선택 ---
config = project_env_selector()

# --- 날짜 필터 ---
start_date = date(2023, 3, 1)
end_date = date(2023, 3, 31)

start_str = start_date.strftime("%Y%m%d")
end_str = end_date.strftime("%Y%m%d")
table = events_table(config)

@st.cache_data(ttl=3600)
def get_data(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        event_name,
        COUNT(*) AS count,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
    GROUP BY event_name
    ORDER BY count DESC
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_data(start_str, end_str, table, config)

# --- 스코어카드 ---
col1, col2 = st.columns(2)
if not df.empty:
    total_events = df['count'].sum()
    unique_users = df['users'].sum()
    col1.metric("총 이벤트 수", f"{total_events:,}")
    col2.metric("고유 사용자 수", f"{unique_users:,}")
else:
    col1.metric("총 이벤트 수", "0")
    col2.metric("고유 사용자 수", "0")

st.divider()

# --- 차트 ---
if not df.empty:
    fig = px.bar(df, x="event_name", y="count", text="count",
                 labels={"event_name": "이벤트 이름", "count": "이벤트 수"})
    fig.update_layout(xaxis_title="이벤트 이름", yaxis_title="이벤트 수", xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")