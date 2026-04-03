import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("📊 2월 통계")

# --- 프로젝트/환경 선택 ---
config = project_env_selector()

# --- 날짜 필터 ---
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "시작일",
        value=date(date.today().year, 2, 1),
        max_value=date.today() - timedelta(days=1),
    )
with col2:
    end_date = st.date_input(
        "종료일",
        value=min(date(date.today().year, 2, 28), date.today() - timedelta(days=1)),
        max_value=date.today() - timedelta(days=1),
    )

start_str = start_date.strftime("%Y%m%d")
end_str = end_date.strftime("%Y%m%d")
table = events_table(config)

@st.cache_data(ttl=3600)
def get_february_data(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        PARSE_DATE('%Y%m%d', event_date) AS date,
        COUNT(DISTINCT user_id) AS users,
        COUNT(*) AS events
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND user_id IS NOT NULL
    GROUP BY date
    ORDER BY date
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_february_data(start_str, end_str, table, config)

# --- 스코어카드 ---
col1, col2, col3 = st.columns(3)
if not df.empty:
    col1.metric("총 사용자 수", f"{int(df['users'].sum()):,}")
    col2.metric("총 이벤트 수", f"{int(df['events'].sum()):,}")
    col3.metric("일 평균 사용자 수", f"{int(df['users'].mean()):,}")
else:
    col1.metric("총 사용자 수", "0")
    col2.metric("총 이벤트 수", "0")
    col3.metric("일 평균 사용자 수", "0")

st.divider()

# --- 차트 ---
if not df.empty:
    fig = px.line(df, x="date", y="users", markers=True,
                  labels={"date": "날짜", "users": "사용자 수"},
                  title="일별 활성 사용자 추이")
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%m/%d")
    st.plotly_chart(fig, use_container_width=True)

    fig_events = px.bar(df, x="date", y="events",
                        labels={"date": "날짜", "events": "이벤트 수"},
                        title="일별 이벤트 발생 수")
    fig_events.update_layout(hovermode="x unified")
    fig_events.update_xaxes(tickformat="%m/%d")
    st.plotly_chart(fig_events, use_container_width=True)
else:
    st.info("데이터가 없습니다.")