"""대시보드 생성/삭제 통합 테스트 — 실제 파일 I/O + Streamlit 로드 검증.

GPT API 호출만 mock하고, 나머지는 실제 동작:
- pages/custom/ 디렉토리에 파일 생성/삭제
- validate_code로 코드 검증
- py_compile로 구문 검사
- glob으로 페이지 목록 조회
- app.py의 동적 로드 로직 검증
"""

import glob
import json
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from scripts.generate_dashboard import (
    CUSTOM_DIR,
    handle_create,
    handle_delete,
    handle_modify,
    list_custom_pages,
    validate_code,
)

# ──────────────────────────────────────────────
# 유효한 Streamlit 대시보드 코드 템플릿
# ──────────────────────────────────────────────
VALID_DASHBOARD_CODE = '''\
import streamlit as st
import plotly.express as px
from datetime import date, timedelta
from bigquery_client import project_env_selector, query, events_table

st.title("{title}")

config = project_env_selector()
table = events_table(config)

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("시작일", value=date.today() - timedelta(days=7))
with col2:
    end_date = st.date_input("종료일", value=date.today() - timedelta(days=1))

start_str = start_date.strftime("%Y%m%d")
end_str = end_date.strftime("%Y%m%d")


@st.cache_data(ttl=3600)
def get_data(start, end, _table, _config):
    sql = f"""
    SELECT
        PARSE_DATE('%Y%m%d', event_date) AS date,
        COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {{_table}}
    WHERE _TABLE_SUFFIX BETWEEN '{{start}}' AND '{{end}}'
    GROUP BY date ORDER BY date
    """
    return query(sql, _config)


df = get_data(start_str, end_str, table, config)
if not df.empty:
    fig = px.line(df, x="date", y="users", markers=True)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("데이터가 없습니다.")
'''


def make_code(title="테스트 대시보드"):
    return VALID_DASHBOARD_CODE.format(title=title)


def mock_generate_code(filename, title):
    """generate_code (GPT 호출)를 대체하는 mock"""
    def _mock(prompt):
        return {
            "filename": filename,
            "title": title,
            "code": make_code(title),
        }
    return _mock


# ──────────────────────────────────────────────
# Fixture: 임시 custom 디렉토리 사용
# ──────────────────────────────────────────────
@pytest.fixture(autouse=True)
def use_temp_custom_dir(monkeypatch, tmp_path):
    """실제 pages/custom/ 대신 임시 디렉토리 사용"""
    custom_dir = str(tmp_path / "custom")
    os.makedirs(custom_dir, exist_ok=True)

    import scripts.generate_dashboard as gd
    monkeypatch.setattr(gd, "CUSTOM_DIR", custom_dir)

    yield custom_dir


def _page_files(custom_dir):
    """custom 디렉토리의 .py 파일 목록"""
    return sorted(
        f for f in os.listdir(custom_dir)
        if f.startswith("custom_") and f.endswith(".py")
    )


def _write_page(custom_dir, filename, title="더미"):
    """헬퍼: 테스트용 페이지 파일 직접 생성"""
    path = os.path.join(custom_dir, filename)
    with open(path, "w") as f:
        f.write(make_code(title))
    return path


# ══════════════════════════════════════════════
# 생성 테스트 (CREATE)
# ══════════════════════════════════════════════

class TestCreate:
    # 1. 정상 생성 → 파일 존재 + 유효한 Python
    def test_create_writes_valid_file(self, use_temp_custom_dir):
        mock = mock_generate_code("custom_daily_users.py", "일별 사용자")
        with patch("scripts.generate_dashboard.generate_code", side_effect=mock):
            result = handle_create("일별 사용자 추이 보여줘")

        assert result == "custom_daily_users.py"

        filepath = os.path.join(use_temp_custom_dir, "custom_daily_users.py")
        assert os.path.exists(filepath)

        # 실제 Python으로 컴파일 가능한지
        import py_compile
        py_compile.compile(filepath, doraise=True)

    # 2. 생성 후 list_custom_pages()에 노출
    def test_created_page_appears_in_list(self, use_temp_custom_dir):
        mock = mock_generate_code("custom_retention.py", "리텐션")
        with patch("scripts.generate_dashboard.generate_code", side_effect=mock):
            handle_create("리텐션 분석")

        pages = list_custom_pages()
        assert "custom_retention.py" in pages

    # 3. 여러 개 생성 → 각각 독립 존재
    def test_multiple_creates_coexist(self, use_temp_custom_dir):
        for name, title in [
            ("custom_page_a.py", "A"),
            ("custom_page_b.py", "B"),
            ("custom_page_c.py", "C"),
        ]:
            mock = mock_generate_code(name, title)
            with patch("scripts.generate_dashboard.generate_code", side_effect=mock):
                handle_create(f"{title} 대시보드 만들어줘")

        files = _page_files(use_temp_custom_dir)
        assert files == ["custom_page_a.py", "custom_page_b.py", "custom_page_c.py"]

    # 4. set_page_config 포함 코드 → 자동 제거 후 저장
    def test_set_page_config_stripped(self, use_temp_custom_dir):
        code_with_config = 'st.set_page_config(page_title="test")\n' + make_code("Config Test")

        def mock(prompt):
            return {"filename": "custom_config_test.py", "title": "Config", "code": code_with_config}

        with patch("scripts.generate_dashboard.generate_code", side_effect=mock):
            handle_create("테스트")

        filepath = os.path.join(use_temp_custom_dir, "custom_config_test.py")
        content = open(filepath).read()
        assert "set_page_config" not in content

    # 5. 금지 패턴 포함 코드 → 거부
    def test_create_rejects_forbidden_code(self, use_temp_custom_dir):
        bad_code = make_code("Evil") + "\nimport subprocess\n"

        def mock(prompt):
            return {"filename": "custom_evil.py", "title": "Evil", "code": bad_code}

        with patch("scripts.generate_dashboard.generate_code", side_effect=mock):
            with pytest.raises(ValueError, match="금지된 패턴"):
                handle_create("악의적 대시보드")

        assert not os.path.exists(os.path.join(use_temp_custom_dir, "custom_evil.py"))

    # 6. 필수 패턴 누락 코드 → 거부
    def test_create_rejects_missing_required(self, use_temp_custom_dir):
        bad_code = "import streamlit as st\nst.title('hi')\n"

        def mock(prompt):
            return {"filename": "custom_bad.py", "title": "Bad", "code": bad_code}

        with patch("scripts.generate_dashboard.generate_code", side_effect=mock):
            with pytest.raises(ValueError, match="코드 검증 실패"):
                handle_create("불완전 대시보드")

    # 7. 잘못된 파일명 (접두사 없음) → 거부
    def test_create_rejects_bad_filename(self, use_temp_custom_dir):
        def mock(prompt):
            return {"filename": "evil_page.py", "title": "Evil", "code": make_code("Evil")}

        with patch("scripts.generate_dashboard.generate_code", side_effect=mock):
            with pytest.raises(ValueError, match="잘못된 파일명"):
                handle_create("나쁜 이름")

    # 8. 경로 탈출 파일명 → 거부
    def test_create_rejects_path_traversal(self, use_temp_custom_dir):
        def mock(prompt):
            return {"filename": "custom_../../etc/evil.py", "title": "X", "code": make_code("X")}

        with patch("scripts.generate_dashboard.generate_code", side_effect=mock):
            with pytest.raises(ValueError, match="위험한 파일명"):
                handle_create("경로 탈출")


# ══════════════════════════════════════════════
# 삭제 테스트 (DELETE)
# ══════════════════════════════════════════════

class TestDelete:
    # 9. 특정 페이지 삭제
    def test_delete_specific_page(self, use_temp_custom_dir):
        _write_page(use_temp_custom_dir, "custom_daily_users.py")
        _write_page(use_temp_custom_dir, "custom_retention.py")

        result = handle_delete("daily users 삭제해줘")
        assert result == "custom_daily_users.py"
        assert not os.path.exists(os.path.join(use_temp_custom_dir, "custom_daily_users.py"))
        # 다른 파일은 살아있어야 함
        assert os.path.exists(os.path.join(use_temp_custom_dir, "custom_retention.py"))

    # 10. 전체 삭제
    def test_delete_all(self, use_temp_custom_dir):
        _write_page(use_temp_custom_dir, "custom_a.py")
        _write_page(use_temp_custom_dir, "custom_b.py")
        _write_page(use_temp_custom_dir, "custom_c.py")

        result = handle_delete("전체 삭제해줘")
        assert "custom_a.py" in result
        assert "custom_b.py" in result
        assert "custom_c.py" in result
        assert _page_files(use_temp_custom_dir) == []

    # 11. 빈 디렉토리에서 삭제 시도 → 에러
    def test_delete_empty_raises(self, use_temp_custom_dir):
        with pytest.raises(ValueError, match="삭제할 커스텀 페이지가 없습니다"):
            handle_delete("아무거나 삭제")

    # 12. 매칭 불가 프롬프트 → 에러
    def test_delete_no_match_raises(self, use_temp_custom_dir):
        _write_page(use_temp_custom_dir, "custom_daily_users.py")

        with pytest.raises(ValueError, match="매칭되는 페이지를 찾을 수 없습니다"):
            handle_delete("xyzxyz 삭제")


# ══════════════════════════════════════════════
# 수정 테스트 (MODIFY)
# ══════════════════════════════════════════════

class TestModify:
    # 13. 기존 페이지 수정 → 삭제 후 재생성
    def test_modify_replaces_page(self, use_temp_custom_dir):
        _write_page(use_temp_custom_dir, "custom_daily_users.py", "원본")

        mock = mock_generate_code("custom_daily_users_v2.py", "수정된 버전")
        with patch("scripts.generate_dashboard.generate_code", side_effect=mock):
            result = handle_modify("daily users 수정해서 차트 추가해줘")

        assert result == "custom_daily_users_v2.py"
        # 원본은 삭제됨
        assert not os.path.exists(os.path.join(use_temp_custom_dir, "custom_daily_users.py"))
        # 새 파일 생성됨
        assert os.path.exists(os.path.join(use_temp_custom_dir, "custom_daily_users_v2.py"))

    # 14. 빈 디렉토리에서 수정 시도 → 에러
    def test_modify_empty_raises(self, use_temp_custom_dir):
        with pytest.raises(ValueError, match="수정할 커스텀 페이지가 없습니다"):
            handle_modify("뭔가 수정해줘")


# ══════════════════════════════════════════════
# app.py 동적 로드 로직 검증
# ══════════════════════════════════════════════

class TestAppDynamicLoad:
    # 15. app.py의 glob 패턴이 custom 페이지를 올바르게 발견하는지
    def test_app_glob_discovers_pages(self, use_temp_custom_dir):
        _write_page(use_temp_custom_dir, "custom_alpha.py", "Alpha")
        _write_page(use_temp_custom_dir, "custom_beta.py", "Beta")

        # app.py와 동일한 glob 패턴 사용
        pattern = os.path.join(use_temp_custom_dir, "custom_*.py")
        found = sorted(glob.glob(pattern))

        assert len(found) == 2
        assert found[0].endswith("custom_alpha.py")
        assert found[1].endswith("custom_beta.py")

        # app.py의 타이틀 추출 로직 검증
        for path in found:
            filename = path.split("/")[-1]
            title = filename.replace("custom_", "").replace(".py", "").replace("_", " ").title()
            assert title  # 빈 문자열이 아닌지
            assert "_" not in title  # 언더스코어가 공백으로 변환됐는지

    # 16 (bonus). .gitkeep은 glob에 안 잡히는지
    def test_gitkeep_not_matched(self, use_temp_custom_dir):
        open(os.path.join(use_temp_custom_dir, ".gitkeep"), "w").close()
        _write_page(use_temp_custom_dir, "custom_test.py")

        pattern = os.path.join(use_temp_custom_dir, "custom_*.py")
        found = glob.glob(pattern)
        filenames = [os.path.basename(f) for f in found]

        assert ".gitkeep" not in filenames
        assert "custom_test.py" in filenames
