# Comento QnA AI 자동화 파이프라인

유저의 고민(QnA) 데이터를 AI를 통해 정형화(Slot-filling)하고, 적절한 부트캠프를 자동으로 추천 매칭해주는 파이프라인 프로젝트입니다.

## 📂 폴더 구조

- **`data/`**: 원본 데이터 (QnA 샘플, 직무코드 매핑, 생성된 Enums)
- **`prompts/`**: AI 시스템 프롬프트 저장소 (`system_prompt.md`)
- **`src/`**: 파이프라인 핵심 코드 (`run_slot_filling.py`, `camp_matcher.py`)
- **`scripts/`**: 데이터 추출 및 유틸리티 스크립트 (`extract_enums.py`, `generate_comparison.py` 등)
- **`results/`**: 파이프라인 실행 결과 (JSON 및 엑셀 리포트)
- **`docs/`**: 기획 문서 및 업무 보고 자료

---

## 🚀 시작하기 (가상환경 세팅 및 실행 방법)

프로젝트를 클론한 후 로컬에서 실행하기 위한 초기 환경 설정 방법입니다.

### 1. 가상환경 생성 및 활성화
```bash
# 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화 (Mac/Linux 기준)
source .venv/bin/activate

# (참고) Windows의 경우:
# .venv\Scripts\activate
```

### 2. 필수 패키지 설치
가상환경이 활성화된 상태에서 아래 명령어들을 입력하여 필요한 라이브러리를 설치합니다.
```bash
pip install pandas openpyxl requests python-dotenv
```

### 3. 환경 변수(API 키) 설정
프로젝트 최상단에 `.env` 파일을 생성하고 발급받은 포텐스닷 API 키를 입력합니다.
```env
POTENS_API_KEY=발급받은_API_키를_여기에_입력하세요
```

### 4. 전체 파이프라인 실행
```bash
# 1단계: 유저 고민 슬롯필링 실행 (AI API 호출)
python src/run_slot_filling.py

# 2단계: 슬롯 결과를 바탕으로 캠프 매칭
python src/camp_matcher.py

# 3단계: 확인을 위한 통합 엑셀 리포트 생성
python scripts/generate_comparison.py
```
