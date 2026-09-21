import pandas as pd
import json

# 1. 원본 데이터 로드 (50건)
df_origin = pd.read_excel('data/community_qna_samples_20260910.xlsx').head(50)

# 2. AI 추출 결과 JSON 로드
with open('results/slot_filling_results.json', 'r', encoding='utf-8') as f:
    ai_results = json.load(f)

# 3. 캠프 매칭 결과 JSON 로드
with open('results/camp_matching_results.json', 'r', encoding='utf-8') as f:
    camp_results = json.load(f)

# 캠프 매칭 결과를 question_id 기준 딕셔너리로 변환
camp_map = {r['question_id']: r for r in camp_results}

# 4. 결과 파싱하여 리스트로 정리
comparison_data = []
for result in ai_results:
    q_id = result['question_id']
    ai_ext = result.get('ai_extraction', {})
    
    intent = ai_ext.get('intent', {})
    intent_primary = intent.get('primary', 'ERROR')
    intent_secondary = intent.get('secondary', '')
    confidence = intent.get('confidence', 0)
    
    job_slot = ai_ext.get('slots', {}).get('interest_job', {})
    if isinstance(job_slot, list):
        job_slot = job_slot[0] if len(job_slot) > 0 else {}
    elif job_slot is None:
        job_slot = {}
        
    job_cat = job_slot.get('job_category', '')
    job_det = job_slot.get('job_detail', '')
    ind = job_slot.get('industry', '')
    job_raw = job_slot.get('raw_mention', '')
    
    # 캠프 매칭 결과 병합
    camp = camp_map.get(q_id, {})
    matched_key = camp.get('matched_key', '')
    matched_level = camp.get('matched_level', '')
    camp_count = camp.get('total_camp_candidates', 0)
    recommended = camp.get('recommended_camps', [])
    needs_review = camp.get('needs_manual_review', False)
    review_reason = camp.get('review_reason', '')
    
    comparison_data.append({
        'question_id': q_id,
        # AI 슬롯필링 결과
        'AI_Intent(주)': intent_primary,
        'AI_Intent(부)': intent_secondary,
        'AI_Confidence': confidence,
        'AI_JobCategory': job_cat,
        'AI_JobDetail': job_det,
        'AI_Industry': ind,
        'AI_직무근거(발췌)': job_raw,
        # 캠프 매칭 결과
        '매칭키': matched_key,
        '매칭레벨': matched_level,
        '후보캠프수': camp_count,
        '추천캠프1': recommended[0] if len(recommended) > 0 else '',
        '추천캠프2': recommended[1] if len(recommended) > 1 else '',
        '추천캠프3': recommended[2] if len(recommended) > 2 else '',
        '담당자리뷰필요': '⚠️ YES' if needs_review else '',
        '리뷰사유': review_reason or ''
    })

df_ai = pd.DataFrame(comparison_data)

# 5. 원본과 병합
df_merged = pd.merge(
    df_origin[['question_id', 'question_title', 'question_content', 'question_target_job']],
    df_ai, on='question_id', how='left'
)

# 6. 엑셀로 저장
output_path = 'results/pilot_test_comparison.xlsx'
df_merged.to_excel(output_path, index=False)
print(f"✅ 통합 비교 리포트 생성 완료: {output_path}")
print(f"   컬럼: {list(df_merged.columns)}")
