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
def get_job_candidates(extraction):
    """
    slots.interest_job을 후보 리스트로 정규화한다.
    interest_job은 배열(최대 3개, 0번째=primary)이 정상 형태이며,
    구버전 단일 dict 응답이 섞여 있어도 안전하게 리스트로 감싼다.
    """
    job_slots = extraction.get('slots', {}).get('interest_job')
    if isinstance(job_slots, dict):
        job_slots = [job_slots]
    elif not isinstance(job_slots, list):
        job_slots = []
    return [j for j in job_slots if isinstance(j, dict)]


def _match_single_job(job_slot, code_index, category_index):
    """
    직무 후보 1건에 대해 3단계 폴백 + 카테고리 폴백으로 캠프를 매칭한다.

    matched_level은 항상 고정된 의미를 가집니다 (AI가 생성한 camp_matching_keys는
    참고용으로만 남기고 매칭 자체에는 사용하지 않음 — 중복 제거로 검색 키 개수가
    바뀌면서 동일한 폴백 단계가 매번 다른 레벨 번호로 찍히는 문제를 방지하기 위함):
        1 = 정확매칭 (job_category-job_detail-industry)
        2 = 상세생략 (job_category-N/A-industry)
        3 = 산업확장 (job_category-job_detail-산업무관)
        4 = 카테고리 폴백 (job_category 전체)
        0 = 매칭 실패

    Returns:
        dict: {
            "matched_level": 0~4,
            "matched_key": 매칭된 직무코드,
            "camps": [캠프명 리스트],
            "all_attempted_keys": [시도한 키 목록]
        }
    """
    job_category = job_slot.get('job_category', '') or ''
    job_detail = job_slot.get('job_detail', '') or 'N/A'
    industry = job_slot.get('industry', '') or ''

    # None이나 "null" 문자열 처리
    if job_detail in (None, 'null', 'None', ''):
        job_detail = 'N/A'

    # 고정 3단계 캐노니컬 키 (레벨 번호는 이 순서에 고정)
    canonical_keys = [
        (1, f"{job_category}-{job_detail}-{industry}"),      # 1순위: 정확매칭
        (2, f"{job_category}-N/A-{industry}"),                # 2순위: 상세생략
        (3, f"{job_category}-{job_detail}-산업무관"),          # 3순위: 산업확장
    ]

    tried_keys = []
    seen_keys = set()
    for level, key in canonical_keys:
        tried_keys.append(key)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        camps = code_index.get(key, [])
        if camps:
            return {
                "matched_level": level,
                "matched_key": key,
                "camps": camps,
                "camp_count": len(camps),
                "all_attempted_keys": tried_keys
            }

    # 4순위 (고정, 최종 폴백): 직무중분류 전체
    if job_category and job_category in category_index:
        camps = category_index[job_category]
        return {
            "matched_level": 4,
            "matched_key": f"[카테고리 폴백] {job_category}",
            "camps": camps,
            "camp_count": len(camps),
            "all_attempted_keys": tried_keys + [f"(카테고리) {job_category}"]
        }

    # 매칭 실패
    return {
        "matched_level": 0,
        "matched_key": None,
        "camps": [],
        "camp_count": 0,
        "all_attempted_keys": tried_keys,
        "flag": "LOW_CONFIDENCE_MANUAL_REVIEW"
    }


def match_camps(extraction, code_index, category_index):
    """
    interest_job 후보 중 0번째(primary)만으로 매칭레벨/적합도 점수를 결정한다.
    (여러 직무가 동등하게 언급된 경우에도, 리뷰 여부 판단 로직은 기존과 동일하게
    primary 하나만 기준으로 유지 — secondary는 find_supplementary_camps()가
    보충 추천 캠프를 채우는 데만 쓰인다.)
    """
    candidates = get_job_candidates(extraction)
    primary = candidates[0] if candidates else {}
    return _match_single_job(primary, code_index, category_index)


def find_supplementary_camps(extraction, code_index, category_index, exclude_camps, max_camps):
    """
    interest_job의 2번째 이후 후보(secondary)로 캠프를 추가 매칭해,
    primary 매칭 결과에서 부족한 만큼(최대 max_camps개)만 보충한다.
    matched_level/적합도 점수/리뷰 여부에는 영향을 주지 않는다.
    """
    if max_camps <= 0:
        return []

    exclude = set(exclude_camps)
    supplementary = []
    for job_slot in get_job_candidates(extraction)[1:]:
        result = _match_single_job(job_slot, code_index, category_index)
        for camp in result['camps']:
            if camp in exclude or camp in supplementary:
                continue
            supplementary.append(camp)
            if len(supplementary) >= max_camps:
                return supplementary
    return supplementary


# =========================================================================
# 2-1. 적합도 점수 산출 (matched_level 50 + confidence 30 + 추출근거 20)
# =========================================================================
LEVEL_SCORE = {0: 0, 1: 50, 2: 30, 3: 15, 4: 0}
BASIS_WEIGHT = {'명시': 1.0, '추론': 0.5, '없음': 0.0}


def calculate_suitability_score(extraction, match_result):
    """
    matched_level(최대 50) + confidence(최대 30) + 추출근거(최대 20)를 합산한
    0~100점 적합도 점수를 계산합니다.

    matched_level 0(매칭 실패)/4(카테고리 폴백)는 0점 처리되어, confidence와
    추출근거가 아무리 높아도 최대 50점(confidence 30 + 근거 20)을 넘을 수 없습니다.
    즉 이 두 레벨은 다른 지표와 무관하게 항상 담당자 리뷰 대상이 됩니다.
    """
    intent = extraction.get('intent', {})
    confidence = intent.get('confidence', 0) or 0

    candidates = get_job_candidates(extraction)
    job_slot = candidates[0] if candidates else {}

    job_category_basis = job_slot.get('job_category_basis', '없음')
    industry_basis = job_slot.get('industry_basis', '없음')

    level_score = LEVEL_SCORE.get(match_result['matched_level'], 0)
    confidence_score = confidence * 30
    basis_score = (
        BASIS_WEIGHT.get(job_category_basis, 0.0) * 12 +
        BASIS_WEIGHT.get(industry_basis, 0.0) * 8
    )

    return {
        "total": round(level_score + confidence_score + basis_score, 1),
        "matched_level_score": level_score,
        "confidence_score": round(confidence_score, 1),
        "basis_score": round(basis_score, 1),
        "job_category_basis": job_category_basis,
        "industry_basis": industry_basis,
    }


# =========================================================================
# 3. 추천 팝업 데이터 생성
# =========================================================================
def generate_popup_data(question_id, extraction, match_result, code_index, category_index):
    """
    매칭 결과를 바탕으로 추천 팝업에 들어갈 데이터 구조를 생성합니다.

    담당자 수동매칭 트리거는 두 가지 (모두 primary 후보 기준, secondary는 관여 안 함):
      1) confidence <= 0.5 (AI 자체 확신도가 낮음)
      2) suitability_score <= 50 (matched_level+confidence+추출근거 종합 적합도가 낮음
         — camp_count==0, 카테고리 폴백 매칭도 이 조건에 자동으로 포함됨)

    추천 캠프는 primary 매칭 결과를 먼저 채우고, 5개 캡 안에 자리가 남으면
    secondary 후보(최대 2개)로 보충한다. 보충 캠프는 리뷰 여부 판단에 영향을 주지 않는다.
    """
    intent = extraction.get('intent', {})
    confidence = intent.get('confidence', 0) or 0
    score_info = calculate_suitability_score(extraction, match_result)

    needs_review = confidence <= 0.5 or score_info['total'] <= 50

    if match_result['camp_count'] == 0:
        review_reason = "NO_CAMP_MATCH"
    elif confidence <= 0.5:
        review_reason = "LOW_CONFIDENCE"
    elif score_info['total'] <= 50:
        review_reason = "LOW_SUITABILITY_SCORE"
    else:
        review_reason = None

    # 추천 캠프는 최대 5개까지만 노출: primary 우선 채우고, 남는 자리는 secondary로 보충
    primary_camps = match_result['camps'][:5]
    supplementary_camps = find_supplementary_camps(
        extraction, code_index, category_index,
        exclude_camps=primary_camps, max_camps=5 - len(primary_camps)
    )
    recommended_camps = primary_camps + supplementary_camps

    candidates = get_job_candidates(extraction)
    secondary_job_categories = [
        c.get('job_category') for c in candidates[1:] if c.get('job_category')
    ]

    return {
        "question_id": question_id,
        "intent_primary": intent.get('primary', 'UNKNOWN'),
        "confidence": confidence,
        "matched_key": match_result['matched_key'],
        "matched_level": match_result['matched_level'],
        "total_camp_candidates": match_result['camp_count'],
        "recommended_camps": recommended_camps,
        "supplementary_camp_count": len(supplementary_camps),
        "secondary_job_categories": secondary_job_categories,
        "suitability_score": score_info['total'],
        "score_breakdown": {
            "matched_level_score": score_info['matched_level_score'],
            "confidence_score": score_info['confidence_score'],
            "basis_score": score_info['basis_score'],
            "job_category_basis": score_info['job_category_basis'],
            "industry_basis": score_info['industry_basis'],
        },
        "needs_manual_review": needs_review,
        "review_reason": review_reason
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
        popup = generate_popup_data(q_id, extraction, match_result, code_index, category_index)
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
        label = {0: "실패", 1: "1순위(정확)", 2: "2순위(상세생략)", 3: "3순위(산업확장)", 4: "4순위(카테고리 폴백)"}.get(level, f"{level}순위")
        print(f"    Level {level} ({label}): {stats['by_level'][level]}건")
    
    print(f"\n🎉 결과 저장 완료: {output_path}")


if __name__ == "__main__":
    main()
