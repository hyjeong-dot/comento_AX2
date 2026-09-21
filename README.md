# Comento QnA AI 자동화 파이프라인

유저의 고민(QnA) 데이터를 AI를 통해 정형화(Slot-filling)하고, 적절한 부트캠프를 자동으로 추천 매칭해주는 파이프라인 프로젝트입니다.

## 폴더 구조

- **`data/`**: 원본 데이터 (QnA 샘플, 직무코드 매핑, 생성된 Enums)
- **`prompts/`**: AI 시스템 프롬프트 저장소 (`system_prompt.md`)
- **`src/`**: 파이프라인 핵심 코드 (`run_slot_filling.py`, `camp_matcher.py`)
- **`scripts/`**: 데이터 추출 및 유틸리티 스크립트 (`extract_enums.py`, `generate_comparison.py` 등)
- **`results/`**: 파이프라인 실행 결과 (JSON 및 엑셀 리포트)
- **`docs/`**: 기획 문서 및 업무 보고 자료
