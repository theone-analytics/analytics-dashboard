import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("📊 A/B 테스트 결과 분석")

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

st.info("참고: Firebase Analytics에서 제공하는 데이터 범위 내에서 생성되었습니다.")

@st.cache_data(ttl=3600)
def get_ab_test_data(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'experiment_id') AS experiment_id,
        (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'variant_id') AS variant_id,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users,
        COUNT(*) AS events
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'experiment_id') IS NOT NULL
      AND (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'variant_id') IS NOT NULL
    GROUP BY experiment_id, variant_id
    ORDER BY experiment_id, variant_id
    """
    return query(sql, _config)

# --- 데이터 조회 ---
df = get_ab_test_data(start_str, end_str, table, config)

# --- 데이터 표시 ---
if not df.empty:
    st.subheader("A/B 테스트 결과")
    st.dataframe(
        df.rename(columns={
            "experiment_id": "실험 ID",
            "variant_id": "변수 ID",
            "users": "사용자 수",
            "events": "이벤트 수"
        })
    )

    st.divider()

    # --- 차트 ---
    fig = px.bar(
        df,
        x="variant_id",
        y="users",
        color="experiment_id",
        barmode="group",
        labels={"variant_id": "변수 ID", "users": "사용자 수", "experiment_id": "실험 ID"},
        title="A/B 테스트 사용자 수 비교"
    )
    st.plotly_chart(fig, use_container_width=True)

    fig_events = px.bar(
        df,
        x="variant_id",
        y="events",
        color="experiment_id",
        barmode="group",
        labels={"variant_id": "변수 ID", "events": "이벤트 수", "experiment_id": "실험 ID"},
        title="A/B 테스트 이벤트 수 비교"
    )
    st.plotly_chart(fig_events, use_container_width=True)
else:
    st.info("데이터가 없습니다.")