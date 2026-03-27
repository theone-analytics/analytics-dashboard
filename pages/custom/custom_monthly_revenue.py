import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("📊 월별 매출 추이")

st.info("참고: Firebase Analytics에서 제공하는 데이터 범위 내에서 생성되었습니다.")

# --- 프로젝트/환경 선택 ---
config = project_env_selector()

# --- 날짜 필터 ---
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "시작일",
        value=date.today().replace(day=1) - timedelta(days=365),
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
        DATE_TRUNC(PARSE_DATE('%Y%m%d', event_date), MONTH) AS month,
        COUNT(*) AS revenue_events
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND event_name = 'purchase'
    GROUP BY month
    ORDER BY month
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_data(start_str, end_str, table, config)

# --- 스코어카드 ---
col1, col2 = st.columns(2)
if not df.empty:
    col1.metric("총 매출 이벤트 수", f"{int(df['revenue_events'].sum()):,}")
else:
    col1.metric("총 매출 이벤트 수", "0")

st.divider()

# --- 차트 ---
if not df.empty:
    fig = px.bar(df, x="month", y="revenue_events",
                 labels={"month": "월", "revenue_events": "매출 이벤트 수"},
                 title="월별 매출 이벤트 추이")
    fig.update_xaxes(tickformat="%Y-%m")
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")