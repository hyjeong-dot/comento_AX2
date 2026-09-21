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
# 2. 메인 슬롯필링 파이프라인 (수정 불필요)
# =========================================================================
def main():
    # 데이터 및 프롬프트 로드
    print("데이터 로딩 중...")
    df = pd.read_excel('data/community_qna_samples_20260910.xlsx')
    
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
            
            results.append({
                "question_id": row['question_id'],
                "ai_extraction": parsed_json
            })
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
