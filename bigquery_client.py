import json

import requests
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

# 환경별 설정
ENV_CONFIG = {
    "Dev": {
        "project_id": "baedalpartner-dev",
        "dataset": "analytics_527323568",
        "secret_key": "gcp_service_account_dev",
        "config_url": "https://raw.githubusercontent.com/TheoneInternationalDeveloper/baedalpan/staging/assets/analytics_config.json",
    },
    "Prod": {
        "project_id": "baedalpartner",
        "dataset": "",  # TODO: prod 데이터셋 ID 확인 후 입력
        "secret_key": "gcp_service_account_prod",
        "config_url": "https://raw.githubusercontent.com/TheoneInternationalDeveloper/baedalpan/main/assets/analytics_config.json",
    },
}


def env_selector():
    """사이드바 환경 선택 — 각 페이지 상단에서 1회 호출"""
    env = st.sidebar.selectbox("환경", list(ENV_CONFIG.keys()))
    return ENV_CONFIG[env]


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
