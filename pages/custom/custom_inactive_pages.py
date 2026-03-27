import streamlit as st
import pandas as pd
from datetime import date, timedelta
from bigquery_client import project_env_selector, query, events_table

st.title("📊 최근 2주간 방문하지 않은 페이지")

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
all_start = (date.today() - timedelta(days=90)).strftime("%Y%m%d")
all_end = end_str
table = events_table(config)

@st.cache_data(ttl=3600)
def get_inactive_pages(start, end, all_start, all_end, _table, _config):
    sql = f"""
    WITH all_screens AS (
        SELECT DISTINCT
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'firebase_screen') AS screen_name
        FROM {_table}
        WHERE _TABLE_SUFFIX BETWEEN '{all_start}' AND '{all_end}'
          AND event_name = 'screen_view'
    ),
    recent_screens AS (
        SELECT DISTINCT
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'firebase_screen') AS screen_name
        FROM {_table}
        WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
          AND event_name = 'screen_view'
    )
    SELECT a.screen_name
    FROM all_screens a
    LEFT JOIN recent_screens r ON a.screen_name = r.screen_name
    WHERE r.screen_name IS NULL
      AND a.screen_name IS NOT NULL
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_inactive_pages(start_str, end_str, all_start, all_end, table, config)

# --- 결과 표시 ---
if not df.empty:
    st.dataframe(
        df.rename(columns={"screen_name": "페이지 이름"}),
        use_container_width=True
    )
else:
    st.info("데이터가 없습니다.")