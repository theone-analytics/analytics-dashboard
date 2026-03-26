# Analytics Dashboard

## 아키텍처

- **Streamlit** 기반 멀티페이지 대시보드
- **BigQuery** (Firebase Analytics `events_*` 테이블) 데이터 소스
- **멀티 프로젝트 지원**: `st.secrets["projects"]`에서 프로젝트/환경 설정을 동적 로드
- 코드 변경 없이 Secrets 수정만으로 새 프로젝트 추가 가능

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `bigquery_client.py` | BigQuery 클라이언트, 프로젝트/환경 선택, config 로드, 카테고리 동적 추출 |
| `pages/1_사용자_현황.py` | DAU, OS, 앱 버전 |
| `pages/2_화면_분석.py` | 화면별 조회수, 체류시간 |
| `pages/3_이벤트_분석.py` | 이벤트별 발생 횟수, 카테고리 분포 |
| `app.py` | 메인 진입점 (페이지 목록만 표시) |

## Secrets 구조

```toml
github_token = "ghp_..."  # private 레포 config 접근용

[projects]
keys = ["baedalpan"]  # 프로젝트 키 목록

[projects.baedalpan]
display_name = "배달판"

[projects.baedalpan.Dev]
project_id = "gcp-project-id"
dataset = "analytics_데이터셋ID"
secret_key = "gcp_service_account_baedalpan_dev"  # 아래 서비스 계정 섹션명과 일치
config_url = "https://raw.githubusercontent.com/.../analytics_config.json"

[gcp_service_account_baedalpan_dev]
type = "service_account"
# ... GCP 서비스 계정 JSON 필드들
```

## 설정 흐름

1. `project_env_selector()` → `st.secrets["projects"]`에서 프로젝트 목록 로드
2. 프로젝트 1개면 이름만 표시, 2개 이상이면 드롭다운
3. 환경(Dev/Prod) 선택 → config dict 반환
4. `config["secret_key"]`로 BigQuery 서비스 계정 접근
5. `config["config_url"]`로 analytics_config.json 로드 (카테고리, 화면/이벤트 매핑)

## analytics_config.json 포맷

각 프로젝트 레포의 `assets/analytics_config.json`에 위치해야 함.

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

- 카테고리는 이 파일에서 동적으로 추출됨 (하드코딩 없음)
- 화면/이벤트 한글 매핑도 이 파일 기반

## 배포

- 레포: `theone-analytics/analytics-dashboard` (public)
- 플랫폼: Streamlit Community Cloud
- `main` push → 자동 배포
- Secrets 변경 시 Streamlit Cloud에서 Save → Reboot app 필요

## Custom Dashboard 자동 생성

### 구조
- `pages/custom/*.py` — AI가 생성한 대시보드 페이지
- `scripts/generate_dashboard.py` — 생성 스크립트 (GitHub Actions에서 실행)
- `scripts/prompts/system_prompt.md` — GPT-4o 시스템 프롬프트
- `.github/workflows/generate-dashboard.yml` — GitHub Actions 워크플로우

### 보호 페이지 (수정/삭제 금지)
- `pages/1_사용자_현황.py`
- `pages/2_화면_분석.py`
- `pages/3_이벤트_분석.py`

### 커스텀 페이지 규칙
- 파일명: `custom_{slug}.py` (한글 slug 허용)
- 위치: `pages/custom/` 디렉토리만
- Slack에서 생성/삭제 가능
- 생성 시 py_compile + 필수 패턴 검증

### 흐름
```
Slack → GitHub repository_dispatch → GitHub Actions
→ generate_dashboard.py → GitHub Models API (GPT-4o)
→ 코드 생성/검증 → push → Streamlit 자동 배포
```

## 주의사항

- `secrets.toml`은 `.gitignore`에 포함 — 실제 키는 Streamlit Cloud Secrets에만 존재
- `secret_key` 값은 반드시 Secrets의 서비스 계정 섹션명(`[gcp_service_account_xxx]`)과 일치해야 함
- Firebase Analytics 표준 스키마(`events_*`)를 사용하는 프로젝트만 지원
