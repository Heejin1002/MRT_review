# 마이리얼트립 리뷰 답변 생성 대시보드

마이리얼트립 파트너 리뷰에 대한 GPT 답변을 자동 생성하는 Streamlit 앱입니다.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.28+-red.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--3.5--turbo-green.svg)

## 기능

- 마이리얼트립 파트너 계정 연동
- 4-5점 리뷰 자동 수집
- GPT를 활용한 개인화된 답변 생성
- 사용자 정의 프롬프트 지원
- 파트너별, 점수별 필터링
- 원클릭 답변 복사

## 배포 방법

### Streamlit Community Cloud

1. GitHub에 리포지토리 생성 및 코드 업로드
2. [Streamlit Community Cloud](https://share.streamlit.io/)에서 앱 배포
3. **Advanced settings**에서 환경변수 설정:
   - `OPENAI_API_KEY`: OpenAI API 키
   - `MYREALTRIP_EMAIL`: 마이리얼트립 파트너 계정 이메일
   - `MYREALTRIP_PASSWORD`: 마이리얼트립 파트너 계정 비밀번호

### 로컬 실행

```bash
pip install -r requirements.txt
streamlit run gpt_response_dashboard.py
```

## 사용법

1. **환경변수 설정** (배포 시): Streamlit Community Cloud의 Advanced settings에서 환경변수 설정
2. **계정 정보**: 환경변수에 없으면 사이드바에서 입력
3. **프롬프트 설정**: 기본 프롬프트 또는 사용자 정의 프롬프트 선택
4. **필터 설정**: 파트너 및 점수 필터 설정
5. **데이터 수집**: "데이터 가져오기" 버튼 클릭
6. **답변 복사**: "📋 답변 복사하기" 버튼 클릭 → 자동으로 클립보드에 복사 → Ctrl+V로 붙여넣기

## 보안

- 모든 민감한 정보는 환경변수로 관리됩니다.
- 계정 정보는 세션 중에만 메모리에 저장됩니다.
- GitHub에는 민감한 정보가 포함되지 않습니다.

## 환경변수 설정

### Streamlit Community Cloud
배포 시 **Advanced settings** → **Secrets**에서 설정:
```
OPENAI_API_KEY = "your-openai-api-key"
MYREALTRIP_EMAIL = "your-email@example.com"
MYREALTRIP_PASSWORD = "your-password"
```

### 로컬 개발
`.env` 파일 생성하거나 시스템 환경변수로 설정:
```bash
export OPENAI_API_KEY="your-openai-api-key"
export MYREALTRIP_EMAIL="your-email@example.com"
export MYREALTRIP_PASSWORD="your-password"
```

## 주요 특징

- ✅ **자동 리뷰 수집**: 마이리얼트립 API를 통한 실시간 리뷰 수집
- ✅ **GPT 답변 생성**: OpenAI gpt-4o-mini를 활용한 개인화된 답변
- ✅ **원클릭 복사**: JavaScript 기반 클립보드 자동 복사
- ✅ **사용자 정의 프롬프트**: 답변 스타일 커스터마이징 가능
- ✅ **필터링**: 파트너별, 점수별 리뷰 필터링
- ✅ **보안**: 환경변수를 통한 안전한 인증 정보 관리

## 스크린샷

### 메인 대시보드
- 리뷰 목록과 GPT 답변을 카드 형태로 표시
- 예약번호, 여행일, 작성일 등 상세 정보 포함

### 사이드바 설정
- 계정 정보 입력
- 프롬프트 유형 선택 (기본/사용자 정의)
- 파트너 및 점수 필터

## 기술 스택

- **Frontend**: Streamlit
- **Backend**: Python 3.8+
- **AI**: OpenAI GPT-3.5-turbo
- **API**: MyRealTrip Partner API
- **Deployment**: Streamlit Community Cloud

## 주의사항

- 마이리얼트립 파트너 계정이 필요합니다.
- OpenAI API 키가 필요합니다.
- API 사용량에 따라 요금이 부과될 수 있습니다.
- 브라우저에서 JavaScript가 활성화되어 있어야 복사 기능이 작동합니다.

## 라이선스

이 프로젝트는 개인 사용을 위한 것입니다.

