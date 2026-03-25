import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import query, events_table

st.set_page_config(page_title="이벤트 분석", page_icon="🎯", layout="wide")
st.title("🎯 이벤트 분석")

# --- 이벤트 매핑 ---
EVENT_NAME_MAP = {
    "drive_start": "운행 시작",
    "drive_stop": "운행 종료",
    "drive_break_start": "휴식 시작",
    "drive_resume": "운행 재개",
    "ledger_tab_switch": "장부 탭 전환",
    "ledger_period_change": "장부 기간 변경",
    "wallet_platform_link": "플랫폼 연동",
    "wallet_account_register": "계좌 등록",
    "wallet_withdraw": "출금",
    "wallet_account_delete": "계좌 삭제",
    "wallet_platform_unlink": "플랫폼 연동 해제",
    "community_post_write": "게시글 작성",
    "community_post_like": "게시글 좋아요",
    "community_comment_write": "댓글 작성",
    "community_comment_like": "댓글 좋아요",
    "community_share": "공유",
    "community_search": "커뮤니티 검색",
    "community_follow": "구독",
    "community_block": "차단",
    "community_report": "신고",
    "bike_register": "바이크 등록",
    "bike_delete": "바이크 삭제",
    "bike_maintenance_write": "정비 기록 작성",
    "bike_find_repair_shop": "정비소 찾기",
    "bike_check_insurance": "보험 확인",
    "goal_set": "목표 설정",
    "ad_banner_tap": "배너 클릭",
    "notification_setting_change": "알림 설정 변경",
    "logout": "로그아웃",
    "account_delete": "회원 탈퇴",
    "map_service_tab_switch": "지도 서비스 탭 전환",
}

EVENT_CATEGORY_MAP = {
    "drive_start": "운행", "drive_stop": "운행", "drive_break_start": "운행", "drive_resume": "운행",
    "ledger_tab_switch": "장부", "ledger_period_change": "장부",
    "wallet_platform_link": "지갑", "wallet_account_register": "지갑", "wallet_withdraw": "지갑",
    "wallet_account_delete": "지갑", "wallet_platform_unlink": "지갑",
    "community_post_write": "커뮤니티", "community_post_like": "커뮤니티",
    "community_comment_write": "커뮤니티", "community_comment_like": "커뮤니티",
    "community_share": "커뮤니티", "community_search": "커뮤니티",
    "community_follow": "커뮤니티", "community_block": "커뮤니티", "community_report": "커뮤니티",
    "bike_register": "바이크", "bike_delete": "바이크", "bike_maintenance_write": "바이크",
    "bike_find_repair_shop": "바이크", "bike_check_insurance": "바이크",
    "goal_set": "홈", "ad_banner_tap": "홈",
    "notification_setting_change": "설정", "logout": "설정", "account_delete": "설정",
    "map_service_tab_switch": "설정",
}

CUSTOM_EVENTS = list(EVENT_NAME_MAP.keys())
CUSTOM_EVENTS_SQL = ", ".join(f"'{e}'" for e in CUSTOM_EVENTS)

# --- 필터 ---
col1, col2, col3 = st.columns(3)
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

categories = ["전체", "운행", "장부", "지갑", "커뮤니티", "바이크", "홈", "설정"]
with col3:
    category_filter = st.selectbox("카테고리", categories)


@st.cache_data(ttl=3600)
def get_event_data(start: str, end: str):
    sql = f"""
    SELECT
        event_name,
        COUNT(*) AS count,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {events_table()}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND event_name IN ({CUSTOM_EVENTS_SQL})
    GROUP BY event_name
    ORDER BY count DESC
    """
    return query(sql)


@st.cache_data(ttl=3600)
def get_event_daily(start: str, end: str):
    sql = f"""
    SELECT
        PARSE_DATE('%Y%m%d', event_date) AS date,
        COUNT(*) AS count
    FROM {events_table()}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND event_name IN ({CUSTOM_EVENTS_SQL})
    GROUP BY date
    ORDER BY date
    """
    return query(sql)


# --- 데이터 조회 + 한글 매핑 ---
event_df = get_event_data(start_str, end_str)
daily_df = get_event_daily(start_str, end_str)

if not event_df.empty:
    event_df["event_name_kr"] = event_df["event_name"].map(EVENT_NAME_MAP).fillna(event_df["event_name"])
    event_df["category"] = event_df["event_name"].map(EVENT_CATEGORY_MAP).fillna("기타")

    if category_filter != "전체":
        event_df = event_df[event_df["category"] == category_filter]

# --- 스코어카드 ---
total_events = int(event_df["count"].sum()) if not event_df.empty else 0
total_users = int(event_df["users"].sum()) if not event_df.empty else 0
unique_events = len(event_df) if not event_df.empty else 0

col1, col2, col3 = st.columns(3)
col1.metric("총 이벤트 수", f"{total_events:,}")
col2.metric("이벤트 발생 사용자", f"{total_users:,}")
col3.metric("이벤트 종류", f"{unique_events}개")

st.divider()

# --- 일별 추이 ---
st.subheader("일별 이벤트 발생 추이")
if not daily_df.empty:
    fig = px.line(
        daily_df,
        x="date",
        y="count",
        markers=True,
        labels={"date": "날짜", "count": "이벤트 수"},
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# --- 차트 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("이벤트별 발생 횟수")
    if not event_df.empty:
        fig = px.bar(
            event_df,
            x="count",
            y="event_name_kr",
            orientation="h",
            color="category",
            labels={"count": "횟수", "event_name_kr": "이벤트", "category": "카테고리"},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("카테고리별 이벤트 분포")
    if not event_df.empty:
        category_df = event_df.groupby("category", as_index=False)["count"].sum()
        fig = px.pie(category_df, values="count", names="category", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

# --- 상세 테이블 ---
st.subheader("이벤트 상세")
if not event_df.empty:
    st.dataframe(
        event_df[["event_name_kr", "category", "count", "users"]].rename(columns={
            "event_name_kr": "이벤트",
            "category": "카테고리",
            "count": "발생 횟수",
            "users": "사용자 수",
        }),
        use_container_width=True,
        hide_index=True,
    )
