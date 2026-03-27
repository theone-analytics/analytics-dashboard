import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("📊 푸시 알림 클릭률 분석")

st.info("참고: Firebase Analytics에서 제공하는 데이터 범위 내에서 생성되었습니다.")

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
def get_push_click_data(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        PARSE_DATE('%Y%m%d', event_date) AS date,
        COUNT(*) AS total_push_events,
        COUNT(CASE WHEN event_name = 'push_notification_click' THEN 1 END) AS push_clicks
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND event_name IN ('push_notification_sent', 'push_notification_click')
    GROUP BY date
    ORDER BY date
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_push_click_data(start_str, end_str, table, config)

# --- 스코어카드 ---
col1, col2, col3 = st.columns(3)
if not df.empty:
    total_push_events = int(df['total_push_events'].sum())
    total_push_clicks = int(df['push_clicks'].sum())
    click_rate = (total_push_clicks / total_push_events * 100) if total_push_events > 0 else 0

    col1.metric("총 푸시 이벤트", f"{total_push_events:,}")
    col2.metric("총 클릭 수", f"{total_push_clicks:,}")
    col3.metric("클릭률 (%)", f"{click_rate:.2f}%")
else:
    col1.metric("총 푸시 이벤트", "0")
    col2.metric("총 클릭 수", "0")
    col3.metric("클릭률 (%)", "0.00%")

st.divider()

# --- 차트 ---
if not df.empty:
    df['click_rate'] = (df['push_clicks'] / df['total_push_events'] * 100).fillna(0)
    fig = px.line(df, x="date", y="click_rate", markers=True,
                  labels={"date": "날짜", "click_rate": "클릭률 (%)"})
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%m/%d")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")