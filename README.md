# 마이리얼트립 리뷰 답변 생성 대시보드

마이리얼트립 파트너 리뷰에 대한 GPT 답변을 자동 생성하는 Streamlit 앱입니다.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.28+-red.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-green.svg)

## 기능

- 마이리얼트립 파트너 계정 연동
- 4-5점 리뷰 자동 수집
- GPT를 활용한 개인화된 답변 생성
- 사용자 정의 프롬프트 지원
- 파트너별, 점수별 필터링
- 원클릭 답변 복사

## 🚀 빠른 시작

### 1. 저장소 클론
```bash
git clone <your-repository-url>
cd MRT_review
```

### 2. 환경변수 설정
```bash
# .env 파일 생성
echo "MYREALTRIP_EMAIL=your_email@example.com" > .env
echo "MYREALTRIP_PASSWORD=your_password" >> .env
echo "OPENAI_API_KEY=your_openai_api_key" >> .env
```

### 3. 의존성 설치 및 실행
```bash
pip install -r requirements.txt
streamlit run gpt_response_dashboard.py
```

### 4. 브라우저에서 확인
- `http://localhost:8501`에서 앱 확인
- 사이드바에서 "📊 데이터 가져오기" 클릭
- 생성된 GPT 답변 확인 및 복사

## 배포 방법

### Streamlit Community Cloud

1. GitHub에 리포지토리 생성 및 코드 업로드
2. [Streamlit Community Cloud](https://share.streamlit.io/)에서 앱 배포
3. **Advanced settings**에서 환경변수 설정:
   - `OPENAI_API_KEY`: OpenAI API 키
   - `MYREALTRIP_EMAIL`: 마이리얼트립 파트너 계정 이메일
   - `MYREALTRIP_PASSWORD`: 마이리얼트립 파트너 계정 비밀번호

### 로컬 실행

1. **환경변수 설정**

   **방법 1: .env 파일 생성 (권장)**
   ```bash
   # 프로젝트 루트에 .env 파일 생성
   touch .env
   ```
   
   `.env` 파일에 다음 내용 추가:
   ```
   MYREALTRIP_EMAIL=your_actual_email@example.com
   MYREALTRIP_PASSWORD=your_actual_password
   OPENAI_API_KEY=your_actual_openai_api_key
   ```
   
   **방법 2: 시스템 환경변수 설정**
   ```bash
   # Windows (CMD)
   set OPENAI_API_KEY=your_actual_openai_api_key
   set MYREALTRIP_EMAIL=your_actual_email@example.com
   set MYREALTRIP_PASSWORD=your_actual_password
   
   # Windows (PowerShell)
   $env:OPENAI_API_KEY="your_actual_openai_api_key"
   $env:MYREALTRIP_EMAIL="your_actual_email@example.com"
   $env:MYREALTRIP_PASSWORD="your_actual_password"
   
   # macOS/Linux
   export OPENAI_API_KEY="your_actual_openai_api_key"
   export MYREALTRIP_EMAIL="your_actual_email@example.com"
   export MYREALTRIP_PASSWORD="your_actual_password"
   ```

2. **의존성 설치 및 실행**
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

### 필수 환경변수

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `OPENAI_API_KEY` | OpenAI API 키 | `sk-...` |
| `MYREALTRIP_EMAIL` | 마이리얼트립 파트너 계정 이메일 | `partner@example.com` |
| `MYREALTRIP_PASSWORD` | 마이리얼트립 파트너 계정 비밀번호 | `your_password` |

### Streamlit Community Cloud
배포 시 **Advanced settings** → **Secrets**에서 설정:
```
OPENAI_API_KEY = "your-openai-api-key"
MYREALTRIP_EMAIL = "your-email@example.com"
MYREALTRIP_PASSWORD = "your-password"
```

### 로컬 개발

**방법 1: .env 파일 생성 (권장)**
1. 프로젝트 루트에 `.env` 파일 생성
2. 다음 내용 추가:
```
MYREALTRIP_EMAIL=your_actual_email@example.com
MYREALTRIP_PASSWORD=your_actual_password
OPENAI_API_KEY=your_actual_openai_api_key
```

**방법 2: 시스템 환경변수 설정**
```bash
# Windows (CMD)
set OPENAI_API_KEY=your_actual_openai_api_key
set MYREALTRIP_EMAIL=your_actual_email@example.com
set MYREALTRIP_PASSWORD=your_actual_password

# Windows (PowerShell)
$env:OPENAI_API_KEY="your_actual_openai_api_key"
$env:MYREALTRIP_EMAIL="your_actual_email@example.com"
$env:MYREALTRIP_PASSWORD="your_actual_password"

# macOS/Linux
export OPENAI_API_KEY="your_actual_openai_api_key"
export MYREALTRIP_EMAIL="your_actual_email@example.com"
export MYREALTRIP_PASSWORD="your_actual_password"
```

### 보안 주의사항
- `.env` 파일은 `.gitignore`에 포함되어 Git에 업로드되지 않습니다
- 실제 API 키와 계정 정보는 절대 GitHub에 커밋하지 마세요
- 환경변수 설정 후 터미널을 재시작해야 할 수 있습니다

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
- **AI**: OpenAI GPT-4o-mini
- **API**: MyRealTrip Partner API
- **Deployment**: Streamlit Community Cloud

## 주의사항

- 마이리얼트립 파트너 계정이 필요합니다.
- OpenAI API 키가 필요합니다.
- API 사용량에 따라 요금이 부과될 수 있습니다.
- 브라우저에서 JavaScript가 활성화되어 있어야 복사 기능이 작동합니다.

## 🔧 문제 해결

### 환경변수가 인식되지 않는 경우
```bash
# 터미널 재시작 후 다시 시도
# 또는 환경변수 확인
echo $OPENAI_API_KEY  # macOS/Linux
echo %OPENAI_API_KEY% # Windows CMD
echo $env:OPENAI_API_KEY # Windows PowerShell
```

### OpenAI API 오류
- API 키가 올바른지 확인
- API 사용량 한도 확인
- 네트워크 연결 상태 확인

### 마이리얼트립 로그인 오류
- 계정 정보가 올바른지 확인
- 계정이 파트너 권한을 가지고 있는지 확인
- 계정이 활성화되어 있는지 확인

### Streamlit 실행 오류
```bash
# 의존성 재설치
pip uninstall -r requirements.txt
pip install -r requirements.txt

# Streamlit 캐시 클리어
streamlit cache clear
```

## 라이선스

이 프로젝트는 개인 사용을 위한 것입니다.


