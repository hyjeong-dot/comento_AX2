"""
Phase 3: 캠프 매칭 파이프라인
슬롯필링 결과(slot_filling_results.json)를 읽어
직무코드_캠프명_매핑.csv와 3단계 폴백 매칭을 수행하고,
각 유저 고민에 대한 캠프 추천 후보를 생성합니다.
"""
import pandas as pd
import json
from collections import defaultdict

# =========================================================================
# 1. 캠프 데이터 인덱스 구축
# =========================================================================
def build_camp_index(csv_path='data/직무코드_캠프명_매핑.csv'):
    """
    CSV를 로드하여 직무코드 → 캠프 리스트 딕셔너리를 구축합니다.
    또한 직무중분류 → 캠프 리스트(대분류 폴백용)도 함께 구축합니다.
    """
    df = pd.read_csv(csv_path)
    df.columns = [col.strip() for col in df.columns]
    
    # 직무코드 → 캠프명 리스트 (정확 매칭용)
    code_index = defaultdict(list)
    # 직무중분류 → 캠프명 리스트 (최종 폴백용)
    category_index = defaultdict(list)
    
    for _, row in df.iterrows():
        code = str(row['직무코드']).strip()
        camp = str(row['캠프명']).strip()
        category = str(row['직무중분류']).strip()
        
        code_index[code].append(camp)
        category_index[category].append(camp)
    
    print(f"📊 캠프 인덱스 구축 완료: 직무코드 {len(code_index)}개, 직무중분류 {len(category_index)}개")
    return code_index, category_index


# =========================================================================
# 2. 3단계 폴백 매칭 로직
# =========================================================================
def match_camps(extraction, code_index, category_index):
    """
    AI 추출 결과 1건에 대해 3단계 폴백으로 캠프를 매칭합니다.
    
    Returns:
        dict: {
            "matched_level": 1~4 또는 0(실패),
            "matched_key": 매칭된 직무코드,
            "camps": [캠프명 리스트],
            "all_attempted_keys": [시도한 키 목록]
        }
    """
    slots = extraction.get('slots', {})
    job_slot = slots.get('interest_job', {})
    
    # interest_job이 리스트인 경우 처리
    if isinstance(job_slot, list):
        job_slot = job_slot[0] if len(job_slot) > 0 else {}
    elif job_slot is None:
        job_slot = {}
    
    job_category = job_slot.get('job_category', '') or ''
    job_detail = job_slot.get('job_detail', '') or 'N/A'
    industry = job_slot.get('industry', '') or ''
    
    # None이나 "null" 문자열 처리
    if job_detail in (None, 'null', 'None', ''):
        job_detail = 'N/A'
    
    # AI가 이미 생성한 camp_matching_keys 활용
    ai_keys = extraction.get('camp_matching_keys', {})
    prefix = ai_keys.get('job_code_prefix', '')
    fallbacks = ai_keys.get('fallback_codes', [])
    
    # 3단계 폴백 키 구성 (AI가 생성한 키 + 직접 생성한 키 병합, 중복 제거)
    search_keys = []
    
    # 1순위: 정확매칭 {job_category}-{job_detail}-{industry}
    key1 = f"{job_category}-{job_detail}-{industry}"
    search_keys.append(key1)
    
    # 2순위: 상세생략 {job_category}-N/A-{industry}
    key2 = f"{job_category}-N/A-{industry}"
    if key2 != key1:
        search_keys.append(key2)
    
    # 3순위: 산업확장 {job_category}-{job_detail}-산업무관
    key3 = f"{job_category}-{job_detail}-산업무관"
    if key3 not in search_keys:
        search_keys.append(key3)
    
    # AI가 만든 키 중 누락된 것 추가
    if prefix and prefix not in search_keys:
        search_keys.insert(0, prefix)
    for fb in fallbacks:
        if fb not in search_keys:
            search_keys.append(fb)
    
    # 순차적으로 매칭 시도
    for level, key in enumerate(search_keys, 1):
        camps = code_index.get(key, [])
        if camps:
            return {
                "matched_level": level,
                "matched_key": key,
                "camps": camps,
                "camp_count": len(camps),
                "all_attempted_keys": search_keys
            }
    
    # 4순위 (최종 폴백): 직무중분류 전체
    if job_category and job_category in category_index:
        camps = category_index[job_category]
        return {
            "matched_level": len(search_keys) + 1,
            "matched_key": f"[카테고리 폴백] {job_category}",
            "camps": camps,
            "camp_count": len(camps),
            "all_attempted_keys": search_keys + [f"(카테고리) {job_category}"]
        }
    
    # 매칭 실패
    return {
        "matched_level": 0,
        "matched_key": None,
        "camps": [],
        "camp_count": 0,
        "all_attempted_keys": search_keys,
        "flag": "LOW_CONFIDENCE_MANUAL_REVIEW"
    }


# =========================================================================
# 3. 추천 팝업 데이터 생성
# =========================================================================
def generate_popup_data(question_id, extraction, match_result):
    """
    매칭 결과를 바탕으로 추천 팝업에 들어갈 데이터 구조를 생성합니다.
    """
    intent = extraction.get('intent', {})
    confidence = intent.get('confidence', 0)
    
    # 담당자 리뷰 필요 여부 판단
    needs_review = (
        confidence < 0.5 or 
        match_result['camp_count'] == 0 or
        match_result.get('flag') == 'LOW_CONFIDENCE_MANUAL_REVIEW'
    )
    
    # 추천 캠프는 최대 5개까지만 노출
    recommended_camps = match_result['camps'][:5]
    
    return {
        "question_id": question_id,
        "intent_primary": intent.get('primary', 'UNKNOWN'),
        "confidence": confidence,
        "matched_key": match_result['matched_key'],
        "matched_level": match_result['matched_level'],
        "total_camp_candidates": match_result['camp_count'],
        "recommended_camps": recommended_camps,
        "needs_manual_review": needs_review,
        "review_reason": (
            "LOW_CONFIDENCE" if confidence < 0.5 
            else "NO_CAMP_MATCH" if match_result['camp_count'] == 0 
            else None
        )
    }


# =========================================================================
# 4. 메인 파이프라인
# =========================================================================
def main():
    print("=" * 60)
    print("Phase 3: 캠프 매칭 파이프라인")
    print("=" * 60)
    
    # 캠프 인덱스 구축
    code_index, category_index = build_camp_index()
    
    # 슬롯필링 결과 로드
    with open('results/slot_filling_results.json', 'r', encoding='utf-8') as f:
        slot_results = json.load(f)
    
    print(f"\n🔍 {len(slot_results)}건의 슬롯필링 결과에 대해 캠프 매칭을 시작합니다...\n")
    
    # 통계 변수
    stats = {
        "total": len(slot_results),
        "matched": 0,
        "unmatched": 0,
        "needs_review": 0,
        "by_level": defaultdict(int),
        "errors": 0
    }
    
    popup_results = []
    
    for result in slot_results:
        q_id = result.get('question_id', 'UNKNOWN')
        extraction = result.get('ai_extraction', {})
        
        # 에러가 있는 건은 스킵
        if 'error' in result:
            stats['errors'] += 1
            popup_results.append({
                "question_id": q_id,
                "error": result['error'],
                "needs_manual_review": True,
                "review_reason": "AI_EXTRACTION_ERROR"
            })
            continue
        
        # 캠프 매칭 실행
        match_result = match_camps(extraction, code_index, category_index)
        
        # 팝업 데이터 생성
        popup = generate_popup_data(q_id, extraction, match_result)
        popup_results.append(popup)
        
        # 통계 업데이트
        if match_result['camp_count'] > 0:
            stats['matched'] += 1
        else:
            stats['unmatched'] += 1
        
        if popup['needs_manual_review']:
            stats['needs_review'] += 1
        
        stats['by_level'][match_result['matched_level']] += 1
        
        # 진행 로그
        status = "✅" if match_result['camp_count'] > 0 else "⚠️"
        print(f"  {status} {q_id}: Level {match_result['matched_level']} 매칭 "
              f"→ {match_result['camp_count']}개 캠프 (키: {match_result['matched_key']})")
    
    # 결과 저장
    output_path = 'results/camp_matching_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(popup_results, f, ensure_ascii=False, indent=2)
    
    # 통계 출력
    print("\n" + "=" * 60)
    print("📊 매칭 결과 요약")
    print("=" * 60)
    print(f"  전체: {stats['total']}건")
    print(f"  매칭 성공: {stats['matched']}건")
    print(f"  매칭 실패: {stats['unmatched']}건")
    print(f"  담당자 리뷰 필요: {stats['needs_review']}건")
    print(f"  AI 추출 에러: {stats['errors']}건")
    print(f"\n  매칭 레벨별 분포:")
    for level in sorted(stats['by_level'].keys()):
        label = {0: "실패", 1: "1순위(정확)", 2: "2순위(상세생략)", 3: "3순위(산업확장)", }.get(level, f"{level}순위(폴백)")
        print(f"    Level {level} ({label}): {stats['by_level'][level]}건")
    
    print(f"\n🎉 결과 저장 완료: {output_path}")


if __name__ == "__main__":
    main()
