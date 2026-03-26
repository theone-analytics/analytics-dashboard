import json

import requests
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

def _load_projects() -> dict:
    """secrets.toml에서 프로젝트 목록 로드"""
    projects_config = st.secrets["projects"]
    keys = list(projects_config["keys"])
    result = {}
    for key in keys:
        proj = projects_config[key]
        display_name = proj["display_name"]
        envs = {k: dict(v) for k, v in proj.items() if k != "display_name"}
        result[key] = {"display_name": display_name, "envs": envs}
    return result


def project_env_selector():
    """사이드바 프로젝트 + 환경 선택 — 각 페이지 상단에서 1회 호출"""
    projects = _load_projects()

    project_keys = list(projects.keys())
    display_names = [projects[k]["display_name"] for k in project_keys]

    if len(project_keys) == 1:
        selected_idx = 0
        st.sidebar.markdown(f"**프로젝트:** {display_names[0]}")
    else:
        selected_display = st.sidebar.selectbox("프로젝트", display_names)
        selected_idx = display_names.index(selected_display)

    selected_key = project_keys[selected_idx]
    envs = projects[selected_key]["envs"]

    env = st.sidebar.selectbox("환경", list(envs.keys()))
    return envs[env]


@st.cache_resource
def _get_client(secret_key: str, project_id: str):
    """BigQuery 클라이언트 (환경별 캐싱)"""
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets[secret_key],
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(credentials=credentials, project=project_id)


def get_client(config: dict):
    """config에서 클라이언트 반환"""
    return _get_client(config["secret_key"], config["project_id"])


def query(sql: str, config: dict):
    """BigQuery SQL 실행 후 DataFrame 반환"""
    client = get_client(config)
    return client.query(sql).to_dataframe()


def events_table(config: dict):
    """이벤트 테이블 전체 경로"""
    return f"`{config['project_id']}.{config['dataset']}.events_*`"


@st.cache_data(ttl=3600)
def load_analytics_config(config_url: str):
    """GitHub에서 analytics_config.json 로드 (1시간 캐싱)"""
    try:
        # private 레포인 경우 GitHub 토큰 필요
        headers = {}
        if "github_token" in st.secrets:
            headers["Authorization"] = f"token {st.secrets['github_token']}"

        response = requests.get(config_url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.sidebar.error(f"Config 로드 실패: {e}")
        return {"screens": {}, "events": {}}


def get_screen_name_map(config: dict) -> dict:
    """화면 이름 매핑 (route name → 한글)"""
    data = load_analytics_config(config["config_url"])
    return {k: v["name"] for k, v in data.get("screens", {}).items()}


def get_screen_category_map(config: dict) -> dict:
    """화면 카테고리 매핑 (route name → 카테고리)"""
    data = load_analytics_config(config["config_url"])
    return {k: v["category"] for k, v in data.get("screens", {}).items()}


def get_event_name_map(config: dict) -> dict:
    """이벤트 이름 매핑 (event name → 한글)"""
    data = load_analytics_config(config["config_url"])
    return {k: v["name"] for k, v in data.get("events", {}).items()}


def get_event_category_map(config: dict) -> dict:
    """이벤트 카테고리 매핑 (event name → 카테고리)"""
    data = load_analytics_config(config["config_url"])
    return {k: v["category"] for k, v in data.get("events", {}).items()}


def get_screen_categories(config: dict) -> list[str]:
    """analytics_config.json에서 화면 카테고리 목록 동적 로드"""
    data = load_analytics_config(config["config_url"])
    categories = sorted(set(v["category"] for v in data.get("screens", {}).values()))
    return ["전체"] + categories + ["기타"]


def get_event_categories(config: dict) -> list[str]:
    """analytics_config.json에서 이벤트 카테고리 목록 동적 로드"""
    data = load_analytics_config(config["config_url"])
    categories = sorted(set(v["category"] for v in data.get("events", {}).values()))
    return ["전체"] + categories


def build_screen_category_sql(config: dict) -> str:
    """화면 카테고리 LEFT JOIN용 SQL 생성"""
    data = load_analytics_config(config["config_url"])
    screens = data.get("screens", {})
    if not screens:
        return "SELECT '' AS name, '' AS category WHERE FALSE"

    parts = []
    for key, val in screens.items():
        parts.append(f"SELECT '{val['name']}' AS name, '{val['category']}' AS category")
    return " UNION ALL\n    ".join(parts)
