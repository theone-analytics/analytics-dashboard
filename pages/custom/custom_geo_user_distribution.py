import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("🌍 지역별 사용자 분포")

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
def get_geo_data(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        geo.country AS country,
        geo.city AS city,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
    GROUP BY country, city
    HAVING country IS NOT NULL AND city IS NOT NULL
    ORDER BY users DESC
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_geo_data(start_str, end_str, table, config)

# --- 지도 시각화 ---
if not df.empty:
    fig = px.scatter_geo(
        df,
        locations="country",
        locationmode="country names",
        size="users",
        hover_name="city",
        title="지역별 사용자 분포",
        labels={"users": "사용자 수"},
    )
    fig.update_layout(geo=dict(showland=True, landcolor="lightgray"))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")