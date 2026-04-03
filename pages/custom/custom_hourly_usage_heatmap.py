import streamlit as st
import plotly.express as px
from datetime import date, timedelta
import pandas as pd

from bigquery_client import project_env_selector, query, events_table

st.title("📊 시간대별 사용 패턴 히트맵")

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
def get_hourly_usage(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        PARSE_DATE('%Y%m%d', event_date) AS date,
        EXTRACT(HOUR FROM TIMESTAMP_MICROS(event_timestamp)) AS hour,
        COUNT(*) AS events,
        COUNT(DISTINCT user_id) AS users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND user_id IS NOT NULL
    GROUP BY date, hour
    ORDER BY date, hour
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_hourly_usage(start_str, end_str, table, config)

if not df.empty:
    # 피벗 테이블 생성
    pivot_df = df.pivot(index="hour", columns="date", values="users").fillna(0)

    # 히트맵 생성
    fig = px.imshow(
        pivot_df,
        labels=dict(x="날짜", y="시간대", color="사용자 수"),
        x=pivot_df.columns,
        y=pivot_df.index,
        color_continuous_scale="Viridis",
    )
    fig.update_layout(
        xaxis=dict(tickformat="%m/%d"),
        yaxis=dict(title="시간대 (시)", dtick=1),
        coloraxis_colorbar=dict(title="사용자 수"),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")