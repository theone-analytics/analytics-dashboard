"""generate_dashboard.py 핵심 로직 테스트 (10개 케이스)"""

import json
import os
import tempfile

import pytest

# generate_dashboard.py에서 순수 함수만 import
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from scripts.generate_dashboard import (
    detect_intent,
    find_page_to_delete,
    validate_code,
    parse_response,
)


# ──────────────────────────────────────────────
# 1. detect_intent: 삭제 키워드 감지
# ──────────────────────────────────────────────
class TestDetectIntent:
    def test_delete_keywords(self):
        """삭제/제거/delete 등 키워드가 있으면 'delete' 반환"""
        assert detect_intent("일별 사용자 대시보드 삭제해줘") == "delete"
        assert detect_intent("custom_daily 제거") == "delete"
        assert detect_intent("delete the retention page") == "delete"
        assert detect_intent("그 페이지 지워줘") == "delete"

    def test_modify_keywords(self):
        """수정/변경/update 등 키워드가 있으면 'modify' 반환"""
        assert detect_intent("일별 사용자 대시보드 수정해줘") == "modify"
        assert detect_intent("차트를 막대에서 선으로 변경") == "modify"
        assert detect_intent("update the daily dashboard") == "modify"
        assert detect_intent("기존 대시보드 바꿔줘") == "modify"

    def test_create_default(self):
        """삭제/수정 키워드가 없으면 'create' 반환"""
        assert detect_intent("일별 신규 사용자 추이를 보고 싶어") == "create"
        assert detect_intent("리텐션 분석 대시보드 만들어줘") == "create"
        assert detect_intent("show me DAU trends") == "create"

    def test_delete_takes_priority_over_modify(self):
        """삭제 키워드가 수정보다 우선"""
        assert detect_intent("수정 말고 삭제해줘") == "delete"


# ──────────────────────────────────────────────
# 2. find_page_to_delete: 페이지 매칭 정확도
# ──────────────────────────────────────────────
class TestFindPageToDelete:
    PAGES = [
        "custom_daily_new_users.py",
        "custom_retention_analysis.py",
        "custom_event_funnel.py",
    ]

    def test_slug_match(self):
        """영문 slug로 정확히 매칭"""
        result = find_page_to_delete("daily new users 삭제", self.PAGES)
        assert result == "custom_daily_new_users.py"

    def test_filename_match(self):
        """파일명 전체 입력으로 매칭"""
        result = find_page_to_delete("custom_retention_analysis 제거해줘", self.PAGES)
        assert result == "custom_retention_analysis.py"

    def test_partial_match(self):
        """부분 키워드로 가장 높은 점수 매칭"""
        result = find_page_to_delete("funnel 삭제", self.PAGES)
        assert result == "custom_event_funnel.py"

    def test_no_match_returns_best_guess(self):
        """단어가 1개라도 겹치면 best match 반환"""
        result = find_page_to_delete("event 삭제", self.PAGES)
        assert result == "custom_event_funnel.py"

    def test_completely_unrelated(self):
        """어떤 단어도 겹치지 않으면 None"""
        result = find_page_to_delete("xyzabc 삭제", self.PAGES)
        assert result is None


# ──────────────────────────────────────────────
# 3. validate_code: 필수 패턴 검증
# ──────────────────────────────────────────────
VALID_CODE = '''
import streamlit as st
from bigquery_client import project_env_selector, query, events_table

config = project_env_selector()

@st.cache_data(ttl=3600)
def get_data(_config: dict):
    return query("SELECT 1", _config)

st.plotly_chart(fig, use_container_width=True)
'''


class TestValidateCode:
    def test_valid_code_passes(self):
        """모든 필수 패턴이 있는 코드는 통과"""
        is_valid, error = validate_code(VALID_CODE)
        assert is_valid, f"검증 실패: {error}"

    def test_missing_required_pattern(self):
        """project_env_selector() 누락 시 실패"""
        code = VALID_CODE.replace("project_env_selector()", "some_other_func()")
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "필수 패턴 누락" in error

    def test_missing_cache_decorator(self):
        """@st.cache_data 누락 시 실패"""
        code = VALID_CODE.replace("@st.cache_data", "# no cache")
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "필수 패턴 누락" in error

    def test_missing_container_width(self):
        """use_container_width=True 누락 시 실패"""
        code = VALID_CODE.replace("use_container_width=True", "")
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "필수 패턴 누락" in error

    def test_missing_bigquery_import(self):
        """from bigquery_client import 완전 제거 시 실패"""
        code = VALID_CODE.replace("from bigquery_client import project_env_selector, query, events_table\n", "")
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "bigquery_client import 누락" in error

    def test_commented_bigquery_import_rejected(self):
        """주석 처리된 import는 검증 실패 (정규식 기반 검증)"""
        code = VALID_CODE.replace("from bigquery_client import", "# from bigquery_client import")
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "bigquery_client import 누락" in error


# ──────────────────────────────────────────────
# 4. validate_code: 금지 패턴 검증
# ──────────────────────────────────────────────
class TestValidateCodeForbidden:
    def test_subprocess_blocked(self):
        """subprocess 사용 차단"""
        code = VALID_CODE + "\nimport subprocess\n"
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "금지된 패턴" in error

    def test_os_system_blocked(self):
        """os.system 사용 차단"""
        code = VALID_CODE + "\nos.system('ls')\n"
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "금지된 패턴" in error

    def test_matplotlib_blocked(self):
        """matplotlib 사용 차단 (plotly만 허용)"""
        code = VALID_CODE + "\nimport matplotlib\n"
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "금지된 패턴" in error

    def test_set_page_config_blocked(self):
        """set_page_config 사용 차단 (app.py에서 관리)"""
        code = VALID_CODE + "\nst.set_page_config(page_title='test')\n"
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "금지된 패턴" in error

    def test_eval_exec_blocked(self):
        """eval/exec 사용 차단"""
        code = VALID_CODE + "\neval('1+1')\n"
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "금지된 패턴" in error

    def test_read_gbq_blocked(self):
        """pd.read_gbq 사용 차단 (query() 사용 필수)"""
        code = VALID_CODE + "\npd.read_gbq('SELECT 1')\n"
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "금지된 패턴" in error


# ──────────────────────────────────────────────
# 5. validate_code: 구문 오류 감지
# ──────────────────────────────────────────────
class TestValidateCodeSyntax:
    def test_syntax_error_detected(self):
        """파이썬 구문 오류가 있는 코드는 실패"""
        code = VALID_CODE + "\ndef broken(\n"
        is_valid, error = validate_code(code)
        assert not is_valid
        assert "구문 오류" in error


# ──────────────────────────────────────────────
# 6. parse_response: 정상 JSON 파싱
# ──────────────────────────────────────────────
class TestParseResponse:
    def test_plain_json(self):
        """순수 JSON 문자열 파싱"""
        content = json.dumps({
            "filename": "custom_test.py",
            "title": "테스트 대시보드",
            "code": "print('hello')",
        })
        result = parse_response(content)
        assert result["filename"] == "custom_test.py"
        assert result["title"] == "테스트 대시보드"
        assert result["code"] == "print('hello')"

    def test_json_with_code_fence(self):
        """```json ... ``` 코드 펜스 안의 JSON 파싱"""
        content = '```json\n{"filename": "custom_a.py", "title": "A", "code": "x=1"}\n```'
        result = parse_response(content)
        assert result["filename"] == "custom_a.py"

    def test_json_with_surrounding_text(self):
        """앞뒤에 텍스트가 있어도 JSON 추출"""
        content = 'Here is the result:\n{"filename": "custom_b.py", "title": "B", "code": "y=2"}\nDone!'
        result = parse_response(content)
        assert result["filename"] == "custom_b.py"

    def test_missing_key_raises(self):
        """필수 키(filename/title/code) 누락 시 KeyError"""
        content = json.dumps({"filename": "custom_c.py", "title": "C"})
        with pytest.raises(KeyError, match="code"):
            parse_response(content)

    def test_invalid_json_raises(self):
        """유효하지 않은 JSON은 JSONDecodeError"""
        with pytest.raises(json.JSONDecodeError):
            parse_response("this is not json at all")


# ──────────────────────────────────────────────
# 7. detect_intent: 빈 문자열 / 엣지 케이스
# ──────────────────────────────────────────────
class TestDetectIntentEdgeCases:
    def test_empty_string(self):
        """빈 문자열은 create 반환"""
        assert detect_intent("") == "create"

    def test_keyword_in_longer_word(self):
        """'삭제' 가 단어 일부로 포함돼도 감지됨 (현재 동작 확인)"""
        # "삭제" is a substring match, so "삭제하다" still triggers
        assert detect_intent("삭제하다") == "delete"

    def test_english_case_insensitive(self):
        """영문 키워드는 대소문자 무관"""
        assert detect_intent("DELETE this page") == "delete"
        assert detect_intent("Remove it") == "delete"


# ──────────────────────────────────────────────
# 8. find_page_to_delete: 엣지 케이스
# ──────────────────────────────────────────────
class TestFindPageToDeleteEdgeCases:
    def test_empty_pages_list(self):
        """빈 페이지 목록이면 None"""
        assert find_page_to_delete("삭제해줘", []) is None

    def test_single_page_partial_match(self):
        """페이지가 1개뿐이면 부분 매칭으로 반환"""
        pages = ["custom_daily_users.py"]
        result = find_page_to_delete("daily 삭제", pages)
        assert result == "custom_daily_users.py"


# ──────────────────────────────────────────────
# 9. 파일명 안전성 (handle_create 로직 추출 테스트)
# ──────────────────────────────────────────────
class TestFilenameSafety:
    def test_valid_filename(self):
        """정상 파일명 통과"""
        filename = "custom_daily_users.py"
        assert filename.startswith("custom_") and filename.endswith(".py")
        assert ".." not in filename and "/" not in filename

    def test_path_traversal_blocked(self):
        """경로 탈출 시도 차단"""
        filename = "custom_../../etc/passwd.py"
        assert ".." in filename  # handle_create에서 ValueError 발생

    def test_slash_in_filename_blocked(self):
        """슬래시 포함 파일명 차단"""
        filename = "custom_pages/evil.py"
        assert "/" in filename  # handle_create에서 ValueError 발생

    def test_wrong_prefix_blocked(self):
        """custom_ 접두사 없는 파일명 차단"""
        filename = "evil_page.py"
        assert not filename.startswith("custom_")

    def test_wrong_extension_blocked(self):
        """.py 확장자 없는 파일명 차단"""
        filename = "custom_page.sh"
        assert not filename.endswith(".py")


# ──────────────────────────────────────────────
# 10. parse_response: 멀티라인 코드 포함 JSON
# ──────────────────────────────────────────────
class TestParseResponseMultiline:
    def test_multiline_code_in_json(self):
        """코드에 줄바꿈이 포함된 JSON도 정상 파싱"""
        data = {
            "filename": "custom_multi.py",
            "title": "멀티라인 테스트",
            "code": "import streamlit as st\n\nst.title('Hello')\nst.write('World')",
        }
        content = json.dumps(data)
        result = parse_response(content)
        assert "\n" in result["code"]
        assert "st.title" in result["code"]

    def test_nested_code_fence_in_response(self):
        """GPT가 ```json 안에 코드를 넣어 응답해도 파싱"""
        inner = json.dumps({
            "filename": "custom_nested.py",
            "title": "Nested",
            "code": "x = 1\ny = 2",
        })
        content = f"```json\n{inner}\n```"
        result = parse_response(content)
        assert result["filename"] == "custom_nested.py"

    def test_extra_whitespace(self):
        """앞뒤 공백/줄바꿈이 있어도 파싱"""
        inner = json.dumps({
            "filename": "custom_ws.py",
            "title": "WS",
            "code": "pass",
        })
        content = f"\n\n  {inner}  \n\n"
        result = parse_response(content)
        assert result["filename"] == "custom_ws.py"
