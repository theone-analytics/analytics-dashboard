import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

# 환경별 설정
ENV_CONFIG = {
    "Dev": {
        "project_id": "baedalpartner-dev",
        "dataset": "analytics_527323568",
        "secret_key": "gcp_service_account_dev",
    },
    "Prod": {
        "project_id": "baedalpartner",
        "dataset": "",  # TODO: prod 데이터셋 ID 확인 후 입력
        "secret_key": "gcp_service_account_prod",
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
