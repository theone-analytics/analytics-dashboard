import glob
import streamlit as st

# 커스텀 페이지 동적 로드
custom_pages = sorted(glob.glob("pages/custom/custom_*.py"))
custom_nav = []
for path in custom_pages:
    filename = path.split("/")[-1].replace("custom_", "").replace(".py", "").replace("_", " ").title()
    custom_nav.append(st.Page(path, title=filename))

# 기본 페이지
default_pages = [
    st.Page("pages/1_사용자_현황.py", title="사용자 현황"),
    st.Page("pages/2_화면_분석.py", title="화면 분석"),
    st.Page("pages/3_이벤트_분석.py", title="이벤트 분석"),
]

# 네비게이션 구성
nav = {"기본": default_pages}
if custom_nav:
    nav["커스텀"] = custom_nav

pg = st.navigation(nav)
pg.run()
