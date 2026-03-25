import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import query, events_table

st.set_page_config(page_title="화면 분석", page_icon="📱", layout="wide")
st.title("📱 화면 분석")

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

# --- 화면 카테고리 매핑 ---
SCREEN_CATEGORY_SQL = """
    SELECT '홈' AS name, '홈' AS category UNION ALL
    SELECT '일별 상세', '홈' UNION ALL
    SELECT '운행 상세', '홈' UNION ALL
    SELECT 'GPS 추적', '홈' UNION ALL
    SELECT '월간 프로모션', '홈' UNION ALL
    SELECT '공지 목록', '홈' UNION ALL
    SELECT '공지 상세', '홈' UNION ALL
    SELECT '서비스 더보기', '홈' UNION ALL
    SELECT '홈 편집', '홈' UNION ALL
    SELECT '장부', '장부' UNION ALL
    SELECT '수입 상세', '장부' UNION ALL
    SELECT '월간 프로모션 상세', '장부' UNION ALL
    SELECT '장부 상세', '장부' UNION ALL
    SELECT '정산 입력', '장부' UNION ALL
    SELECT '지갑', '지갑' UNION ALL
    SELECT '플랫폼 연동', '지갑' UNION ALL
    SELECT '타플랫폼 연동', '지갑' UNION ALL
    SELECT '계좌 등록', '지갑' UNION ALL
    SELECT '출금', '지갑' UNION ALL
    SELECT '계좌 상세', '지갑' UNION ALL
    SELECT '공제 관리', '지갑' UNION ALL
    SELECT '공제 상세 (미처리)', '지갑' UNION ALL
    SELECT '공제 상세', '지갑' UNION ALL
    SELECT '순서 편집', '지갑' UNION ALL
    SELECT '바이크', '바이크' UNION ALL
    SELECT '바이크 등록', '바이크' UNION ALL
    SELECT '바이크 정보', '바이크' UNION ALL
    SELECT '바이크 관리', '바이크' UNION ALL
    SELECT '정비 기록', '바이크' UNION ALL
    SELECT '정비 기록 작성', '바이크' UNION ALL
    SELECT '바이크 검색', '바이크' UNION ALL
    SELECT '바이크 보험', '바이크' UNION ALL
    SELECT '커뮤니티', '커뮤니티' UNION ALL
    SELECT '게시글 상세', '커뮤니티' UNION ALL
    SELECT '인기글', '커뮤니티' UNION ALL
    SELECT '이벤트/뉴스', '커뮤니티' UNION ALL
    SELECT '커뮤니티 검색', '커뮤니티' UNION ALL
    SELECT '글쓰기 (자유)', '커뮤니티' UNION ALL
    SELECT '글쓰기 (동네)', '커뮤니티' UNION ALL
    SELECT '글쓰기 (수익인증)', '커뮤니티' UNION ALL
    SELECT '댓글/답글', '커뮤니티' UNION ALL
    SELECT '유저 프로필', '커뮤니티' UNION ALL
    SELECT '차단 계정', '커뮤니티' UNION ALL
    SELECT '구독 목록', '커뮤니티' UNION ALL
    SELECT '활동 등급', '커뮤니티' UNION ALL
    SELECT '신고', '커뮤니티' UNION ALL
    SELECT '유저 프로필 (딥링크)', '커뮤니티' UNION ALL
    SELECT '게시글 상세 (딥링크)', '커뮤니티' UNION ALL
    SELECT '마이페이지', '설정' UNION ALL
    SELECT '프로필 수정', '설정' UNION ALL
    SELECT '알림 목록', '설정' UNION ALL
    SELECT '알림 설정', '설정' UNION ALL
    SELECT '플랫폼 관리', '설정' UNION ALL
    SELECT '플랫폼 추가', '설정' UNION ALL
    SELECT '내 동네 설정', '설정' UNION ALL
    SELECT '동네 인증', '설정' UNION ALL
    SELECT '동네 인증 도움말', '설정' UNION ALL
    SELECT '본인 인증', '설정' UNION ALL
    SELECT '지출 항목 관리', '설정' UNION ALL
    SELECT '지출 항목 추가', '설정' UNION ALL
    SELECT '화면 테마', '설정' UNION ALL
    SELECT '지도 서비스', '설정' UNION ALL
    SELECT '회원 탈퇴', '설정' UNION ALL
    SELECT '스플래시', '온보딩' UNION ALL
    SELECT '온보딩', '온보딩' UNION ALL
    SELECT '로그인', '온보딩' UNION ALL
    SELECT '심사용 로그인', '온보딩' UNION ALL
    SELECT '권한 설정', '온보딩' UNION ALL
    SELECT '닉네임 설정', '온보딩' UNION ALL
    SELECT '플랫폼 설정', '온보딩' UNION ALL
    SELECT '지역 설정', '온보딩'
"""


@st.cache_data(ttl=3600)
def get_screen_data(start: str, end: str, category_filter: str):
    category_condition = ""
    if category_filter != "전체":
        category_condition = f"WHERE screen_category = '{category_filter}'"

    sql = f"""
    WITH screen_raw AS (
        SELECT
            PARSE_DATE('%Y%m%d', event_date) AS date,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'firebase_screen') AS screen_name,
            (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'engagement_time_msec') AS engagement_time_msec,
            COALESCE(user_id, user_pseudo_id) AS unique_user
        FROM {events_table()}
        WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
          AND event_name = 'screen_view'
    ),
    screen_with_category AS (
        SELECT
            s.date,
            s.screen_name,
            s.engagement_time_msec,
            s.unique_user,
            COALESCE(c.category, '기타') AS screen_category
        FROM screen_raw s
        LEFT JOIN ({SCREEN_CATEGORY_SQL}) c ON s.screen_name = c.name
    )
    SELECT
        screen_name,
        screen_category,
        COUNT(*) AS views,
        COUNT(DISTINCT unique_user) AS users,
        ROUND(AVG(engagement_time_msec / 1000), 2) AS avg_duration_sec
    FROM screen_with_category
    {category_condition}
    GROUP BY screen_name, screen_category
    ORDER BY views DESC
    """
    return query(sql)


@st.cache_data(ttl=3600)
def get_screen_daily(start: str, end: str):
    sql = f"""
    SELECT
        PARSE_DATE('%Y%m%d', event_date) AS date,
        COUNT(*) AS views,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {events_table()}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
      AND event_name = 'screen_view'
    GROUP BY date
    ORDER BY date
    """
    return query(sql)


# --- 카테고리 필터 ---
categories = ["전체", "홈", "장부", "지갑", "바이크", "커뮤니티", "설정", "온보딩", "기타"]
with col3:
    category_filter = st.selectbox("카테고리", categories)

# --- 데이터 조회 ---
screen_df = get_screen_data(start_str, end_str, category_filter)
daily_df = get_screen_daily(start_str, end_str)

# --- 스코어카드 ---
total_views = int(screen_df["views"].sum()) if not screen_df.empty else 0
total_users = int(screen_df["users"].sum()) if not screen_df.empty else 0
avg_duration = round(screen_df["avg_duration_sec"].mean(), 2) if not screen_df.empty else 0

col1, col2, col3 = st.columns(3)
col1.metric("총 화면 조회수", f"{total_views:,}")
col2.metric("순 사용자", f"{total_users:,}")
col3.metric("평균 체류시간", f"{avg_duration}초")

st.divider()

# --- 일별 추이 ---
st.subheader("일별 화면 조회 추이")
if not daily_df.empty:
    fig = px.line(
        daily_df,
        x="date",
        y=["views", "users"],
        markers=True,
        labels={"date": "날짜", "value": "수", "variable": "지표"},
    )
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# --- TOP 15 차트 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("화면별 조회수 TOP 15")
    if not screen_df.empty:
        top_views = screen_df.nlargest(15, "views")
        fig = px.bar(
            top_views,
            x="views",
            y="screen_name",
            orientation="h",
            labels={"views": "조회수", "screen_name": "화면"},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("화면별 체류시간 TOP 15")
    if not screen_df.empty:
        top_duration = screen_df.nlargest(15, "avg_duration_sec")
        fig = px.bar(
            top_duration,
            x="avg_duration_sec",
            y="screen_name",
            orientation="h",
            labels={"avg_duration_sec": "평균 체류시간(초)", "screen_name": "화면"},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

# --- 상세 테이블 ---
st.subheader("화면 상세")
if not screen_df.empty:
    st.dataframe(
        screen_df.rename(columns={
            "screen_name": "화면 이름",
            "screen_category": "카테고리",
            "views": "조회수",
            "users": "순 사용자",
            "avg_duration_sec": "평균 체류시간(초)",
        }),
        use_container_width=True,
        hide_index=True,
    )
