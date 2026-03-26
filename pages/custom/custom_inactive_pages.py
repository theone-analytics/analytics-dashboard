import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table, get_screen_name_map

st.title("📊 2주간 진입하지 않은 페이지")

# --- 프로젝트/환경 선택 ---
config = project_env_selector()

# --- 날짜 필터 ---
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "시작일",
        value=date.today() - timedelta(days=14),
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
def get_inactive_pages(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    WITH active_pages AS (
        SELECT DISTINCT
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'firebase_screen') AS screen_name
        FROM {_table}
        WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
    )
    
    SELECT
        screen_name_map.screen_name AS page_name
    FROM `{_config['project']}.{_config['dataset']}.screen_name_map` AS screen_name_map
    WHERE screen_name_map.screen_name NOT IN (SELECT screen_name FROM active_pages)
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_inactive_pages(start_str, end_str, table, config)

# --- 스코어카드 ---
col1, col2, col3 = st.columns(3)
col1.metric("총 비활성 페이지 수", len(df))

st.divider()

# --- 차트 ---
if not df.empty:
    fig = px.bar(df, x="page_name", y=[1] * len(df), labels={"page_name": "페이지 이름", "y": "비활성 상태"})
    fig.update_layout(hovermode="x unified", xaxis_title="페이지 이름", yaxis_title="비활성 상태")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")