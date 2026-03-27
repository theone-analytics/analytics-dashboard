"""GPT가 실수할 수 있는 20가지 대시보드 생성 시나리오 테스트.

각 테스트는 사용자의 요청 프롬프트 + GPT가 생성할 법한 잘못된 코드를 시뮬레이션하고,
validate_code 또는 handle_create가 이를 올바르게 차단하는지 검증합니다.
"""

import json
import os
import re
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from scripts.generate_dashboard import (
    validate_code,
    handle_create,
    detect_intent,
    find_page_to_delete,
)


# ──────────────────────────────────────────────
# 유효한 기본 코드 (이것을 기반으로 실수를 주입)
# ──────────────────────────────────────────────
BASE_CODE = '''\
import streamlit as st
import plotly.express as px
from datetime import date, timedelta

from bigquery_client import project_env_selector, query, events_table

st.title("테스트")

config = project_env_selector()
table = events_table(config)

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("시작일", value=date.today() - timedelta(days=7), max_value=date.today() - timedelta(days=1))
with col2:
    end_date = st.date_input("종료일", value=date.today() - timedelta(days=1), max_value=date.today() - timedelta(days=1))

start_str = start_date.strftime("%Y%m%d")
end_str = end_date.strftime("%Y%m%d")


@st.cache_data(ttl=3600)
def get_data(start, end, _table, _config):
    sql = f"""
    SELECT PARSE_DATE('%Y%m%d', event_date) AS date,
           COUNT(DISTINCT COALESCE(user_id, user_pseudo_id)) AS users
    FROM {_table}
    WHERE _TABLE_SUFFIX BETWEEN '{start}' AND '{end}'
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


@pytest.fixture(autouse=True)
def use_temp_custom_dir(monkeypatch, tmp_path):
    custom_dir = str(tmp_path / "custom")
    os.makedirs(custom_dir, exist_ok=True)
    import scripts.generate_dashboard as gd
    monkeypatch.setattr(gd, "CUSTOM_DIR", custom_dir)
    yield custom_dir


def mock_gpt(filename, code):
    def _mock(prompt):
        return {"filename": filename, "title": "테스트", "code": code}
    return _mock


def assert_rejected(code, expected_msg=None):
    """validate_code가 거부하는지 확인"""
    is_valid, error = validate_code(code)
    assert not is_valid, f"차단되어야 하는 코드가 통과됨: {error}"
    if expected_msg:
        assert expected_msg in error, f"에러 메시지 불일치: {error}"


def assert_accepted(code):
    """validate_code가 통과하는지 확인"""
    is_valid, error = validate_code(code)
    assert is_valid, f"통과해야 하는 코드가 거부됨: {error}"


# ══════════════════════════════════════════════
# 1. 매출/결제 데이터 요청 → matplotlib 사용
# 프롬프트: "월별 매출 추이 보여줘"
# GPT 실수: matplotlib으로 차트 생성
# ══════════════════════════════════════════════
class TestGptMistakes:

    def test_01_matplotlib_instead_of_plotly(self):
        """프롬프트: '월별 매출 추이' → GPT가 matplotlib 사용"""
        code = BASE_CODE.replace(
            "import plotly.express as px",
            "import matplotlib.pyplot as plt"
        ).replace(
            "fig = px.line(df, x=\"date\", y=\"users\", markers=True)\n    st.plotly_chart(fig, use_container_width=True)",
            "fig, ax = plt.subplots()\n    ax.plot(df['date'], df['users'])\n    st.pyplot(fig, use_container_width=True)"
        )
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 2. pd.read_gbq 사용
    # 프롬프트: "DAU 추이 보여줘"
    # GPT 실수: query() 대신 pd.read_gbq() 사용
    # ══════════════════════════════════════════
    def test_02_read_gbq_instead_of_query(self):
        """프롬프트: 'DAU 추이' → GPT가 pd.read_gbq() 사용"""
        code = BASE_CODE.replace(
            "return query(sql, _config)",
            "return pd.read_gbq(sql)"
        )
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 3. set_page_config 포함
    # 프롬프트: "화면 분석 대시보드"
    # GPT 실수: st.set_page_config() 추가
    # ══════════════════════════════════════════
    def test_03_set_page_config(self):
        """프롬프트: '화면 분석' → GPT가 set_page_config 추가"""
        code = 'st.set_page_config(page_title="화면 분석")\n' + BASE_CODE
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 4. subprocess import
    # 프롬프트: "시스템 정보 대시보드"
    # GPT 실수: subprocess 사용
    # ══════════════════════════════════════════
    def test_04_subprocess_import(self):
        """프롬프트: '시스템 정보' → GPT가 subprocess 사용"""
        code = "import subprocess\n" + BASE_CODE
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 5. os.system 사용
    # 프롬프트: "서버 상태 대시보드"
    # GPT 실수: os.system 호출
    # ══════════════════════════════════════════
    def test_05_os_system(self):
        """프롬프트: '서버 상태' → GPT가 os.system 사용"""
        code = BASE_CODE + "\nos.system('ls -la')\n"
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 6. eval/exec 사용
    # 프롬프트: "동적 쿼리 대시보드"
    # GPT 실수: eval()로 동적 코드 실행
    # ══════════════════════════════════════════
    def test_06_eval_usage(self):
        """프롬프트: '동적 쿼리' → GPT가 eval() 사용"""
        code = BASE_CODE + "\nresult = eval('1+1')\n"
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 7. config["project"] 사용 (올바른 키는 config["project_id"])
    # 프롬프트: "프로젝트별 통계"
    # GPT 실수: 잘못된 config 키 사용
    # ══════════════════════════════════════════
    def test_07_wrong_config_key(self):
        """프롬프트: '프로젝트별 통계' → GPT가 config['project'] 사용"""
        code = BASE_CODE + '\nproject = config["project"]\n'
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 8. screen_name_map을 SQL 테이블로 참조
    # 프롬프트: "화면 이름별 통계"
    # GPT 실수: screen_name_map 테이블 JOIN
    # ══════════════════════════════════════════
    def test_08_screen_name_map_reference(self):
        """프롬프트: '화면 이름별 통계' → GPT가 screen_name_map 참조"""
        code = BASE_CODE.replace(
            "FROM {_table}",
            "FROM {_table} JOIN screen_name_map"
        )
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 9. INFORMATION_SCHEMA 사용
    # 프롬프트: "테이블 목록 보여줘"
    # GPT 실수: 메타데이터 테이블 조회
    # ══════════════════════════════════════════
    def test_09_information_schema(self):
        """프롬프트: '테이블 목록' → GPT가 INFORMATION_SCHEMA 조회"""
        code = BASE_CODE.replace(
            "FROM {_table}",
            "FROM INFORMATION_SCHEMA.TABLES"
        )
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 10. __TABLES__ 메타테이블 사용
    # 프롬프트: "데이터셋 크기 확인"
    # GPT 실수: __TABLES__ 조회
    # ══════════════════════════════════════════
    def test_10_tables_meta(self):
        """프롬프트: '데이터셋 크기' → GPT가 __TABLES__ 조회"""
        code = BASE_CODE.replace(
            "FROM {_table}",
            "FROM `project.dataset.__TABLES__`"
        )
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 11. @st.cache_data 누락
    # 프롬프트: "간단한 이벤트 카운트"
    # GPT 실수: 캐싱 데코레이터 빼먹음
    # ══════════════════════════════════════════
    def test_11_missing_cache_decorator(self):
        """프롬프트: '이벤트 카운트' → GPT가 @st.cache_data 누락"""
        code = BASE_CODE.replace("@st.cache_data(ttl=3600)", "# no cache")
        assert_rejected(code, "필수 패턴 누락")

    # ══════════════════════════════════════════
    # 12. use_container_width 누락
    # 프롬프트: "OS 비율 파이차트"
    # GPT 실수: use_container_width=True 빼먹음
    # ══════════════════════════════════════════
    def test_12_missing_container_width(self):
        """프롬프트: 'OS 비율' → GPT가 use_container_width 누락"""
        code = BASE_CODE.replace("use_container_width=True", "")
        assert_rejected(code, "필수 패턴 누락")

    # ══════════════════════════════════════════
    # 13. project_env_selector() 누락
    # 프롬프트: "앱 버전 분포"
    # GPT 실수: 환경 선택 위젯 빼먹음
    # ══════════════════════════════════════════
    def test_13_missing_env_selector(self):
        """프롬프트: '앱 버전 분포' → GPT가 project_env_selector 누락"""
        code = BASE_CODE.replace("config = project_env_selector()", "config = {}")
        assert_rejected(code, "필수 패턴 누락")

    # ══════════════════════════════════════════
    # 14. bigquery_client import 누락
    # 프롬프트: "세션 분석"
    # GPT 실수: import문 빼먹음
    # ══════════════════════════════════════════
    def test_14_missing_bigquery_import(self):
        """프롬프트: '세션 분석' → GPT가 bigquery_client import 누락"""
        code = BASE_CODE.replace(
            "from bigquery_client import project_env_selector, query, events_table",
            "# import removed"
        )
        assert_rejected(code, "bigquery_client import 누락")

    # ══════════════════════════════════════════
    # 15. bigquery_client import를 주석 처리
    # 프롬프트: "사용자 세그먼트"
    # GPT 실수: import를 주석으로 남김
    # ══════════════════════════════════════════
    def test_15_commented_import(self):
        """프롬프트: '사용자 세그먼트' → GPT가 import를 주석 처리"""
        code = BASE_CODE.replace(
            "from bigquery_client import",
            "# from bigquery_client import"
        )
        assert_rejected(code, "bigquery_client import 누락")

    # ══════════════════════════════════════════
    # 16. shutil 사용
    # 프롬프트: "데이터 백업 대시보드"
    # GPT 실수: shutil로 파일 조작
    # ══════════════════════════════════════════
    def test_16_shutil_usage(self):
        """프롬프트: '데이터 백업' → GPT가 shutil 사용"""
        code = "import shutil\n" + BASE_CODE
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 17. __import__ 사용
    # 프롬프트: "커스텀 모듈 로드"
    # GPT 실수: 동적 import
    # ══════════════════════════════════════════
    def test_17_dynamic_import(self):
        """프롬프트: '커스텀 모듈' → GPT가 __import__ 사용"""
        code = BASE_CODE + "\nmod = __import__('os')\n"
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 18. exec() 사용
    # 프롬프트: "사용자 정의 쿼리 실행기"
    # GPT 실수: exec()로 코드 실행
    # ══════════════════════════════════════════
    def test_18_exec_usage(self):
        """프롬프트: '사용자 정의 쿼리' → GPT가 exec() 사용"""
        code = BASE_CODE + "\nexec('print(1)')\n"
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 19. plt. 사용 (matplotlib.pyplot alias)
    # 프롬프트: "히트맵 대시보드"
    # GPT 실수: plt.figure() 사용
    # ══════════════════════════════════════════
    def test_19_plt_alias(self):
        """프롬프트: '히트맵' → GPT가 plt. 사용"""
        code = BASE_CODE + "\nimport matplotlib.pyplot as plt\nplt.figure()\n"
        assert_rejected(code, "금지된 패턴")

    # ══════════════════════════════════════════
    # 20. 구문 오류 (닫히지 않은 괄호)
    # 프롬프트: "복잡한 CTE 쿼리"
    # GPT 실수: 코드에 구문 오류
    # ══════════════════════════════════════════
    def test_20_syntax_error(self):
        """프롬프트: '복잡한 CTE' → GPT가 구문 오류 생성"""
        code = BASE_CODE + "\ndef broken(\n"
        assert_rejected(code, "구문 오류")


# ══════════════════════════════════════════════
# handle_create 통합 테스트: GPT 실수 코드가 파일로 저장되지 않는지
# ══════════════════════════════════════════════
class TestGptMistakesBlocked:

    def test_forbidden_code_not_saved(self, use_temp_custom_dir):
        """금지 패턴 코드 → 파일 생성 안 됨"""
        bad_code = "import subprocess\n" + BASE_CODE
        with patch("scripts.generate_dashboard.generate_code",
                   side_effect=mock_gpt("custom_evil.py", bad_code)):
            with pytest.raises(ValueError, match="코드 검증 실패"):
                handle_create("시스템 정보 보여줘")
        assert not os.path.exists(os.path.join(use_temp_custom_dir, "custom_evil.py"))

    def test_missing_required_not_saved(self, use_temp_custom_dir):
        """필수 패턴 누락 코드 → 파일 생성 안 됨"""
        bad_code = "import streamlit as st\nst.title('bad')\n"
        with patch("scripts.generate_dashboard.generate_code",
                   side_effect=mock_gpt("custom_bad.py", bad_code)):
            with pytest.raises(ValueError, match="코드 검증 실패"):
                handle_create("아무거나 만들어줘")
        assert not os.path.exists(os.path.join(use_temp_custom_dir, "custom_bad.py"))

    def test_syntax_error_not_saved(self, use_temp_custom_dir):
        """구문 오류 코드 → 파일 생성 안 됨"""
        bad_code = BASE_CODE + "\ndef oops(\n"
        with patch("scripts.generate_dashboard.generate_code",
                   side_effect=mock_gpt("custom_oops.py", bad_code)):
            with pytest.raises(ValueError, match="코드 검증 실패"):
                handle_create("대시보드 만들어줘")
        assert not os.path.exists(os.path.join(use_temp_custom_dir, "custom_oops.py"))

    def test_valid_code_saved(self, use_temp_custom_dir):
        """정상 코드 → 파일 생성됨 (대조군)"""
        with patch("scripts.generate_dashboard.generate_code",
                   side_effect=mock_gpt("custom_good.py", BASE_CODE)):
            result = handle_create("DAU 보여줘")
        assert result == "custom_good.py"
        assert os.path.exists(os.path.join(use_temp_custom_dir, "custom_good.py"))
