import streamlit as st

st.set_page_config(
    page_title="Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Analytics Dashboard")
st.markdown("사이드바에서 페이지를 선택하세요.")

st.markdown("""
### 페이지 목록
- **사용자 현황** — DAU, OS 비율, 앱 버전 분포
- **화면 분석** — 화면별 조회수, 체류시간
- **이벤트 분석** — 이벤트별 발생 횟수, 카테고리 분포
""")
