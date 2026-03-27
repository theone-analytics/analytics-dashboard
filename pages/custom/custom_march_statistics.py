import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("📊 3월 통계")

# --- 프로젝트/환경 선택 ---
config = project_env_selector()

# --- 날짜 필터 ---
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "시작일",
        value=date(date.today().year, 3, 1),
        max_value=date.today()
    )
with col2:
    end_date = st.date_input(
        "종료일",
        value=date(date.today().year, 3, 31),
        max_value=date.today()
    )

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
      AND event_name NOT IN ('screen_view', 'session_start', 'user_engagement', 'first_visit', 'first_open')
    GROUP BY event_name
    ORDER BY count DESC
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_data(start_str, end_str, table, config)

# --- 스코어카드 ---
col1, col2, col3 = st.columns(3)
if not df.empty:
    col1.metric("총 이벤트 수", f"{int(df['count'].sum()):,}")
    col2.metric("고유 사용자 수", f"{int(df['users'].sum()):,}")
    col3.metric("이벤트 종류", f"{df['event_name'].nunique():,}")
else:
    col1.metric("총 이벤트 수", "0")
    col2.metric("고유 사용자 수", "0")
    col3.metric("이벤트 종류", "0")

st.divider()

# --- 차트 ---
if not df.empty:
    fig = px.bar(df, x="event_name", y="count", text="count",
                 labels={"event_name": "이벤트 이름", "count": "횟수"})
    fig.update_layout(hovermode="x unified")
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")

st.info("참고: Firebase Analytics에서 제공하는 데이터 범위 내에서 생성되었습니다.")