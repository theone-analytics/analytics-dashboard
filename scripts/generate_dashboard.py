"""Slack → GitHub Actions에서 호출되는 대시보드 페이지 생성 스크립트."""

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
    'config["project"]', "config['project']",  # 올바른 키: config["project_id"]
    "screen_name_map", "event_name_map",  # 존재하지 않는 테이블
    "set_page_config",  # app.py에서 관리
    "matplotlib", "plt.",  # plotly만 사용
    "pd.read_gbq", "read_gbq",  # query() 함수만 사용
    "INFORMATION_SCHEMA", "__TABLES__",  # 접근 불가
]

MAX_RETRIES = 2


def load_system_prompt() -> str:
    with open(PROMPT_PATH, "r") as f:
        return f.read()


def list_custom_pages() -> list[str]:
    pages = glob.glob(os.path.join(CUSTOM_DIR, "custom_*.py"))
    return [os.path.basename(p) for p in pages]


def detect_intent(prompt: str) -> str:
    delete_keywords = ["삭제", "제거", "delete", "remove", "지워"]
    for kw in delete_keywords:
        if kw in prompt.lower():
            return "delete"
    return "create"


def find_page_to_delete(prompt: str, pages: list[str]) -> str | None:
    prompt_lower = prompt.lower().replace(" ", "")
    for page in pages:
        name = page.replace("custom_", "").replace(".py", "").replace("_", "")
        if name in prompt_lower:
            return page
    return None


def validate_code(code: str) -> tuple[bool, str]:
    for pattern in REQUIRED_PATTERNS:
        if pattern not in code:
            return False, f"필수 패턴 누락: {pattern}"

    for pattern in FORBIDDEN_PATTERNS:
        if pattern in code:
            return False, f"금지된 패턴: {pattern}"

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

    return json.loads(content)


def generate_code(prompt: str) -> dict:
    system_prompt = load_system_prompt()
    existing_pages = list_custom_pages()

    user_message = f"""사용자 요청: {prompt}

기존 커스텀 페이지: {json.dumps(existing_pages, ensure_ascii=False)}

위 요청에 맞는 Streamlit 대시보드 페이지를 생성해주세요.
기존 페이지와 파일명이 겹치지 않도록 해주세요.
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
    all_keywords = ["전체", "모두", "모든", "all", "전부"]
    if any(kw in prompt.lower() for kw in all_keywords):
        for page in pages:
            os.remove(os.path.join(CUSTOM_DIR, page))
        print(f"전체 삭제 완료: {pages}")
        return ", ".join(pages)

    target = find_page_to_delete(prompt, pages)
    if not target:
        raise ValueError(f"매칭되는 페이지를 찾을 수 없습니다. 현재 페이지: {pages}")

    filepath = os.path.join(CUSTOM_DIR, target)
    os.remove(filepath)

    print(f"삭제 완료: {target}")
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True, choices=["generate"])
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--requester", default="unknown")
    args = parser.parse_args()

    intent = detect_intent(args.prompt)

    if intent == "delete":
        result = handle_delete(args.prompt)
        print(f"결과: {result} 삭제됨")
    else:
        result = handle_create(args.prompt)
        print(f"결과: {result} 생성됨")


if __name__ == "__main__":
    main()
