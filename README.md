# Analytics Dashboard

Firebase Analytics 데이터를 시각화하는 Streamlit 대시보드입니다. 멀티 프로젝트를 지원하며, 코드 변경 없이 Secrets 설정만으로 새 프로젝트를 추가할 수 있습니다.

## 페이지 구성

| 페이지 | 설명 |
|--------|------|
| 사용자 현황 | DAU, OS 비율, 앱 버전 분포 |
| 화면 분석 | 화면별 조회수, 체류시간, 카테고리 필터 |
| 이벤트 분석 | 이벤트별 발생 횟수, 카테고리 분포 |

## 배포

- **레포**: `theone-analytics/analytics-dashboard` (public)
- **플랫폼**: Streamlit Community Cloud
- **자동 배포**: `main` 브랜치에 push 시 자동 반영

## 새 프로젝트 추가 방법

코드 변경 없이 아래 2가지만 준비하면 됩니다.

### 1. analytics_config.json 준비

해당 프로젝트 레포에 `assets/analytics_config.json`을 생성합니다.

```json
{
  "screens": {
    "route_name": { "name": "한글 이름", "category": "카테고리" }
  },
  "events": {
    "event_name": { "name": "한글 이름", "category": "카테고리" }
  }
}
```

### 2. Streamlit Secrets 수정

Streamlit Cloud Settings > Secrets에서 아래 항목을 추가합니다.

```toml
# 1) projects.keys에 새 키 추가
[projects]
keys = ["baedalpan", "새프로젝트키"]

# 2) 프로젝트 설정 추가
[projects.새프로젝트키]
display_name = "프로젝트 표시 이름"

[projects.새프로젝트키.Dev]
project_id = "gcp-project-id"
dataset = "analytics_데이터셋ID"
secret_key = "gcp_service_account_새프로젝트키_dev"
config_url = "https://raw.githubusercontent.com/조직/레포/브랜치/assets/analytics_config.json"

# 3) GCP 서비스 계정 키 추가
[gcp_service_account_새프로젝트키_dev]
type = "service_account"
project_id = "gcp-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
# ... 나머지 필드
```

Save 후 Reboot app하면 사이드바에 프로젝트 선택 드롭다운이 자동으로 나타납니다.

## 로컬 실행

```bash
# 가상환경 설정
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# .streamlit/secrets.toml에 Secrets 설정 후
streamlit run app.py
```

## 필수 요건

- 각 프로젝트는 Firebase Analytics 표준 스키마(`events_*`)를 사용해야 합니다
- `analytics_config.json`이 없으면 화면/이벤트 매핑이 동작하지 않습니다
- private 레포의 config에 접근하려면 Secrets에 `github_token` 설정이 필요합니다
