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


def get_env():
    """사이드바 환경 선택 (페이지 간 공유)"""
    if "env" not in st.session_state:
        st.session_state.env = "Dev"
    env = st.sidebar.selectbox(
        "환경",
        list(ENV_CONFIG.keys()),
        index=list(ENV_CONFIG.keys()).index(st.session_state.env),
        key="env_selector",
    )
    st.session_state.env = env
    return env


def get_config():
    """현재 선택된 환경의 설정"""
    env = get_env()
    return ENV_CONFIG[env]


@st.cache_resource
def get_client(secret_key: str, project_id: str):
    """BigQuery 클라이언트 (환경별 캐싱)"""
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets[secret_key],
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(credentials=credentials, project=project_id)


def query(sql: str):
    """BigQuery SQL 실행 후 DataFrame 반환"""
    config = get_config()
    client = get_client(config["secret_key"], config["project_id"])
    return client.query(sql).to_dataframe()


def events_table():
    """이벤트 테이블 전체 경로"""
    config = get_config()
    return f"`{config['project_id']}.{config['dataset']}.events_*`"
