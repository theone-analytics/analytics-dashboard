import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_ID = "baedalpartner-dev"
DATASET = "analytics_527323568"


@st.cache_resource
def get_client():
    """BigQuery 클라이언트 (앱 실행 중 1회만 생성)"""
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(credentials=credentials, project=PROJECT_ID)


def query(sql: str):
    """BigQuery SQL 실행 후 DataFrame 반환 (1시간 캐싱)"""
    client = get_client()
    return client.query(sql).to_dataframe()


def events_table():
    """이벤트 테이블 전체 경로"""
    return f"`{PROJECT_ID}.{DATASET}.events_*`"
