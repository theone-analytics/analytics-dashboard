import glob
import re

import streamlit as st


def _extract_title(path: str) -> str:
    """파일에서 st.title("...") 한글 제목 추출, 없으면 파일명 사용"""
    with open(path, "r") as f:
        for line in f:
            match = re.search(r'st\.title\(["\'](.+?)["\']\)', line)
            if match:
                # 이모지 제거 후 strip
                return re.sub(r'[^\w가-힣a-zA-Z0-9 ]', '', match.group(1)).strip()
    return path.split("/")[-1].replace("custom_", "").replace(".py", "").replace("_", " ").title()


# 커스텀 페이지 동적 로드
custom_pages = sorted(glob.glob("pages/custom/custom_*.py"))
custom_nav = []
for path in custom_pages:
    title = _extract_title(path)
    custom_nav.append(st.Page(path, title=title))

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
