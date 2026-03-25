import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import env_selector, query, events_table

st.set_page_config(page_title="사용자 현황", page_icon="👥", layout="wide")
st.title("👥 사용자 현황")

# --- 환경 선택 ---
config = env_selector()

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


# --- 캐싱된 쿼리 함수 ---
@st.cache_data(ttl=3600)
def get_dau(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        PARSE_DATE('%Y%m%d', event_date) AS date,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
    GROUP BY date
    ORDER BY date
    """
    return query(sql, _config)


@st.cache_data(ttl=3600)
def get_os_distribution(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        device.operating_system AS os,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
    GROUP BY os
    ORDER BY users DESC
    """
    return query(sql, _config)


@st.cache_data(ttl=3600)
def get_app_version(start: str, end: str, _table: str, _config: dict):
    sql = f"""
    SELECT
        app_info.version AS version,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND app_info.version IS NOT NULL
    GROUP BY version
    ORDER BY users DESC
    LIMIT 10
    """
    return query(sql, _config)


# --- 데이터 조회 ---
dau_df = get_dau(start_str, end_str, table, config)
os_df = get_os_distribution(start_str, end_str, table, config)
version_df = get_app_version(start_str, end_str, table, config)

# --- 스코어카드 ---
yesterday_users = 0
week_users = 0

if not dau_df.empty:
    yesterday_row = dau_df[dau_df["date"] == (date.today() - timedelta(days=1))]
    if not yesterday_row.empty:
        yesterday_users = int(yesterday_row["users"].iloc[0])
    week_users = int(dau_df["users"].sum()) if len(dau_df) > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("어제 활성 사용자", f"{yesterday_users:,}명")
col2.metric("기간 내 총 활성 사용자", f"{week_users:,}명")
col3.metric("조회 기간", f"{(end_date - start_date).days + 1}일")

st.divider()

# --- 일별 활성 사용자 차트 ---
st.subheader("일별 활성 사용자")
if not dau_df.empty:
    fig = px.line(
        dau_df,
        x="date",
        y="users",
        markers=True,
        labels={"date": "날짜", "users": "사용자 수"},
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")

# --- OS / 앱 버전 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("OS 비율")
    if not os_df.empty:
        fig = px.pie(os_df, values="users", names="os", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("데이터가 없습니다.")

with col2:
    st.subheader("앱 버전 분포")
    if not version_df.empty:
        fig = px.pie(version_df, values="users", names="version", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("데이터가 없습니다.")
