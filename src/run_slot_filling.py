import pandas as pd
import json
import time
import requests
import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# =========================================================================
# 1. 포텐스닷 API 연동 설정 (이 부분을 복사하신 코드로 교체해주세요)
# =========================================================================
API_KEY = os.environ.get("POTENS_API_KEY", "")

def call_potens_api(system_prompt, user_content):
    """
    이 함수 안에 포텐스닷 API 가이드의 'Python으로 호출하기' 코드를 붙여넣어 수정해주세요.
    입력: system_prompt(문자열), user_content(문자열)
    출력: AI가 생성한 JSON 형태의 텍스트 반환
    """
    
    # 포텐스닷 API 요청 형식에 맞게 프롬프트 구성
    combined_prompt = f"System Instructions:\n{system_prompt}\n\nUser Question:\n{user_content}"

    try:
        resp = requests.post(
            "https://ai.potens.ai/api/chat",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "prompt": combined_prompt,
                "model": "claude-4-6-sonnet"
            },
        )
        data = resp.json()
        
        # 포텐스닷 응답 구조에 맞춰 반환 (data["message"])
        if "message" in data:
            return data["message"]
        else:
            print(f"API Error (No message): {data}")
            return "{}"
            
    except Exception as e:
        print(f"API Request Failed: {e}")
        return "{}"

# =========================================================================
# 1-1. Enum 검증 안전망
# 프롬프트를 강화해도 AI가 다른 필드(enum 리스트) 소속 값을 잘못된 필드에
# 채우는 교차 오염을 완전히 막을 수는 없어서, 응답 파싱 후 data/enums.json과
# 대조해 위반 필드는 null로 되돌리는 후처리를 추가한다.
# =========================================================================
with open('data/enums.json', 'r', encoding='utf-8') as f:
    ENUMS = json.load(f)

VALID_INTENTS = {
    'CAREER_DIRECTION', 'SKILL_GAP', 'EXPERIENCE_GAP',
    'APPLICATION_PREP', 'CAREER_TRANSITION', 'COMPOUND'
}


def validate_and_clean(extraction):
    """
    enums.json / 6개 intent 코드 대비 값을 검증한다.
    위반된 필드는 null로 되돌리고(교차 오염된 값을 그대로 매칭에 흘려보내지 않기 위함),
    위반 이력은 extraction['_enum_violations']에 남겨 추후 검수에 활용한다.
    """
    violations = []

    intent = extraction.get('intent', {}) or {}
    for field in ('primary', 'secondary'):
        value = intent.get(field)
        if value and value not in VALID_INTENTS:
            violations.append(f"intent.{field}={value!r} (허용되지 않은 intent 코드)")
            intent[field] = None

    job_slot = extraction.get('slots', {}).get('interest_job')
    if isinstance(job_slot, list):
        job_slot = job_slot[0] if job_slot else None
    if isinstance(job_slot, dict):
        for field, enum_key, basis_field in (
            ('job_category', 'job_category', 'job_category_basis'),
            ('job_detail', 'job_detail', None),
            ('industry', 'industry', 'industry_basis'),
        ):
            value = job_slot.get(field)
            if value and value not in ENUMS[enum_key]:
                violations.append(f"interest_job.{field}={value!r} (다른 필드의 enum 값이거나 존재하지 않는 값)")
                job_slot[field] = None
                if basis_field:
                    job_slot[basis_field] = '없음'

    if violations:
        extraction['_enum_violations'] = violations
    return extraction


# =========================================================================
# 2. 메인 슬롯필링 파이프라인
# =========================================================================
def main():
    # 데이터 및 프롬프트 로드
    print("데이터 로딩 중...")
    df = pd.read_excel('data/community_qna_samples_20260910.xlsx')

    # 취업 고민 카테고리 그룹만 대상으로 유형화 진행 (이직 고민, 대학생 고민, 랜선 사수 등 제외)
    before_count = len(df)
    df = df[df['question_category_group'] == '취업 고민'].reset_index(drop=True)
    print(f"카테고리 그룹 필터링: {before_count}건 → {len(df)}건 (취업 고민만)")

    # 테스트용 50건만 추출
    test_df = df.head(50).copy()
    
    with open('prompts/system_prompt.md', 'r', encoding='utf-8') as f:
        system_prompt = f.read()

    results = []
    
    print(f"\n🚀 총 {len(test_df)}건의 데이터에 대해 AI 슬롯필링을 시작합니다...")
    
    for idx, row in test_df.iterrows():
        print(f"[{idx+1}/50] ID: {row['question_id']} 처리 중...")
        
        # 유저 메시지 구성 (원문 + 메타데이터)
        user_content = f"""
        [title] {row['question_title']}
        [content] {row['question_content']}
        [metadata_category] {row.get('question_category', 'N/A')}
        [metadata_target_job] {row.get('question_target_job', 'N/A')}
        [metadata_target_company] {row.get('question_target_company', 'N/A')}
        """
        
        # API 호출
        try:
            ai_response_text = call_potens_api(system_prompt, user_content)
            
            # 마크다운 코드블록(```json)이 섞여 나올 경우를 대비한 전처리
            if "```json" in ai_response_text:
                ai_response_text = ai_response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in ai_response_text:
                ai_response_text = ai_response_text.split("```")[1].strip()
                
            parsed_json = json.loads(ai_response_text) # JSON 문법 검증
            parsed_json = validate_and_clean(parsed_json)  # enum 교차 오염 검증 및 정리

            results.append({
                "question_id": row['question_id'],
                "ai_extraction": parsed_json
            })
            if parsed_json.get('_enum_violations'):
                print(f"  ⚠️  성공했지만 enum 위반 감지 → null 처리: {parsed_json['_enum_violations']}")
            else:
                print(f"  ✅ 성공 (Intent: {parsed_json.get('intent', {}).get('primary', 'N/A')})")
            
        except json.JSONDecodeError:
            print(f"  ❌ JSON 파싱 에러 (반환값 형식이 잘못됨)")
            results.append({
                "question_id": row['question_id'],
                "error": "JSON 파싱 에러",
                "raw_response": ai_response_text
            })
        except Exception as e:
            print(f"  ❌ 에러 발생: {e}")
            results.append({
                "question_id": row['question_id'],
                "error": str(e)
            })
            
        time.sleep(1) # API Rate limit 방지용 대기

    # 결과 JSON으로 저장
    output_path = 'results/slot_filling_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"\n🎉 테스트 완료! 결과가 {output_path} 에 저장되었습니다.")

if __name__ == "__main__":
    main()
