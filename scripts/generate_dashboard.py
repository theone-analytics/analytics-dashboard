"""Slack → GitHub Actions에서 호출되는 대시보드 페이지 생성 스크립트."""

from __future__ import annotations

import argparse
import glob
import json
import os
import py_compile
import re
import tempfile

from openai import OpenAI

CUSTOM_DIR = os.path.join(os.path.dirname(__file__), "..", "pages", "custom")
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.md")

REQUIRED_PATTERNS = ["project_env_selector()", "@st.cache_data", "use_container_width=True"]
FORBIDDEN_PATTERNS = [
    "subprocess", "os.system", "shutil", "__import__", "eval(", "exec(",
    'config["project"]', "config['project']",
    "screen_name_map", "event_name_map",
    "set_page_config",
    "matplotlib", "plt.",
    "pd.read_gbq", "read_gbq",
    "INFORMATION_SCHEMA", "__TABLES__",
]

MAX_RETRIES = 2


def load_system_prompt() -> str:
    with open(PROMPT_PATH, "r") as f:
        return f.read()


def list_custom_pages() -> list[str]:
    pages = glob.glob(os.path.join(CUSTOM_DIR, "custom_*.py"))
    return [os.path.basename(p) for p in sorted(pages)]


def detect_intent(prompt: str) -> str:
    prompt_lower = prompt.lower()
    delete_keywords = ["삭제", "제거", "delete", "remove", "지워"]
    modify_keywords = ["수정", "변경", "업데이트", "update", "modify", "바꿔"]

    for kw in delete_keywords:
        if kw in prompt_lower:
            return "delete"

    for kw in modify_keywords:
        if kw in prompt_lower:
            return "modify"

    return "create"


def find_page_to_delete(prompt: str, pages: list[str]) -> str | None:
    prompt_lower = prompt.lower().replace(" ", "")

    # 1. 영문 slug 매칭 (custom_daily_new_users.py → "dailynewusers")
    for page in pages:
        name = page.replace("custom_", "").replace(".py", "").replace("_", "")
        if name in prompt_lower:
            return page

    # 2. 파일명 직접 매칭 (custom_daily_new_users)
    for page in pages:
        filename_no_ext = page.replace(".py", "")
        if filename_no_ext in prompt_lower.replace(" ", ""):
            return page

    # 3. 부분 매칭 (가장 많이 겹치는 페이지)
    best_match = None
    best_score = 0
    for page in pages:
        parts = page.replace("custom_", "").replace(".py", "").split("_")
        score = sum(1 for part in parts if part in prompt_lower)
        if score > best_score:
            best_score = score
            best_match = page

    if best_score >= 1:
        return best_match

    return None


def validate_code(code: str) -> tuple[bool, str]:
    for pattern in REQUIRED_PATTERNS:
        if pattern not in code:
            return False, f"필수 패턴 누락: {pattern}"

    for pattern in FORBIDDEN_PATTERNS:
        if pattern in code:
            return False, f"금지된 패턴: {pattern}"

    # from bigquery_client import 확인 (주석이 아닌 실제 import만 인정)
    if not re.search(r"^from bigquery_client import", code, re.MULTILINE):
        return False, "bigquery_client import 누락"

    # query() 함수가 cached 함수 안에서만 호출되는지는 구문 분석이 복잡하므로
    # 최소한 @st.cache_data가 있는지만 확인 (위에서 이미 체크)

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write(code)
        tmp_path = f.name
    try:
        py_compile.compile(tmp_path, doraise=True)
    except py_compile.PyCompileError as e:
        return False, f"구문 오류: {e}"
    finally:
        os.unlink(tmp_path)

    return True, ""


def parse_response(content: str) -> dict:
    """GPT 응답에서 JSON을 추출하고 파싱"""
    content = content.strip()

    # 코드 펜스 제거 (멀티라인 지원)
    content = re.sub(r"^```(?:json)?\s*\n?", "", content)
    content = re.sub(r"\n?\s*```\s*$", "", content)

    # JSON 객체 추출 (앞뒤 텍스트가 있을 경우)
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        content = match.group(0)

    result = json.loads(content)

    # 필수 키 확인
    for key in ["filename", "title", "code"]:
        if key not in result:
            raise KeyError(f"JSON에 '{key}' 키가 없습니다")

    return result


def generate_code(prompt: str) -> dict:
    from datetime import date

    system_prompt = load_system_prompt()
    existing_pages = list_custom_pages()
    today = date.today().isoformat()

    user_message = f"""오늘 날짜: {today}

사용자 요청: {prompt}

기존 커스텀 페이지: {json.dumps(existing_pages, ensure_ascii=False)}

위 요청에 맞는 Streamlit 대시보드 페이지를 생성해주세요.
기존 페이지와 파일명이 겹치지 않도록 해주세요.
날짜는 절대 하드코딩하지 말고 date.today() 기준으로 동적 계산하세요.
반드시 JSON 형식으로만 응답하세요."""

    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=os.environ["GITHUB_TOKEN"],
    )

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
            )

            content = response.choices[0].message.content
            return parse_response(content)
        except (json.JSONDecodeError, KeyError) as e:
            last_error = e
            print(f"시도 {attempt + 1}/{MAX_RETRIES} 실패: {e}")
            continue

    raise ValueError(f"JSON 파싱 {MAX_RETRIES}회 실패: {last_error}")


def handle_create(prompt: str) -> str:
    result = generate_code(prompt)

    filename = result["filename"]
    title = result["title"]
    code = result["code"]

    # app.py에서 page_config를 관리하므로 제거 (멀티라인 지원)
    code = re.sub(r'st\.set_page_config\([^)]*\)\n?', '', code, flags=re.DOTALL)

    if not filename.startswith("custom_") or not filename.endswith(".py"):
        raise ValueError(f"잘못된 파일명: {filename}")

    # 파일명 안전성 검사
    if ".." in filename or "/" in filename:
        raise ValueError(f"위험한 파일명: {filename}")

    is_valid, error = validate_code(code)
    if not is_valid:
        raise ValueError(f"코드 검증 실패: {error}")

    filepath = os.path.join(CUSTOM_DIR, filename)
    with open(filepath, "w") as f:
        f.write(code)

    print(f"생성 완료: {filename} ({title})")
    return filename


def handle_delete(prompt: str) -> str:
    pages = list_custom_pages()
    if not pages:
        raise ValueError("삭제할 커스텀 페이지가 없습니다.")

    # 전체 삭제
    all_keywords = ["전체", "모두", "모든", "all", "전부", "다"]
    if any(kw in prompt.lower() for kw in all_keywords):
        for page in pages:
            os.remove(os.path.join(CUSTOM_DIR, page))
        print(f"전체 삭제 완료: {pages}")
        return ", ".join(pages)

    target = find_page_to_delete(prompt, pages)
    if not target:
        page_list = "\n".join(f"  - {p}" for p in pages)
        raise ValueError(f"매칭되는 페이지를 찾을 수 없습니다.\n현재 페이지:\n{page_list}")

    filepath = os.path.join(CUSTOM_DIR, target)
    os.remove(filepath)

    print(f"삭제 완료: {target}")
    return target


def handle_modify(prompt: str) -> str:
    """수정 요청 → 삭제 후 재생성"""
    pages = list_custom_pages()
    if not pages:
        raise ValueError("수정할 커스텀 페이지가 없습니다. 먼저 생성해주세요.")

    target = find_page_to_delete(prompt, pages)
    if target:
        os.remove(os.path.join(CUSTOM_DIR, target))
        print(f"기존 페이지 삭제: {target}")

    # 삭제 키워드 제거 후 생성
    clean_prompt = prompt
    for kw in ["수정", "변경", "업데이트", "update", "modify", "바꿔"]:
        clean_prompt = clean_prompt.replace(kw, "")

    return handle_create(clean_prompt.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True, choices=["generate"])
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--requester", default="unknown")
    args = parser.parse_args()

    if not args.prompt.strip():
        raise ValueError("빈 요청입니다.")

    intent = detect_intent(args.prompt)

    if intent == "delete":
        result = handle_delete(args.prompt)
        print(f"결과: {result} 삭제됨")
    elif intent == "modify":
        result = handle_modify(args.prompt)
        print(f"결과: {result} 수정됨")
    else:
        result = handle_create(args.prompt)
        print(f"결과: {result} 생성됨")


if __name__ == "__main__":
    main()
