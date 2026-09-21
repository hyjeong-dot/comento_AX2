"""
캠프 CSV 커버리지 갭 분석
직무코드_캠프명_매핑.csv의 캠프 커버리지를 실제 유저 수요(question_target_job)와
대조하여, ① 캠프가 아예 없는 직무 ② 캠프는 있지만 풀이 얇은 직무를 추출합니다.
결과는 캠프 기획팀 공유용 엑셀(docs/camp_coverage_gap_analysis.xlsx)로 저장합니다.
"""
import pandas as pd

THIN_POOL_THRESHOLD = 5  # 이 개수 이하면 "얇은 커버리지"로 간주

# ── 1. 데이터 로드 ──
csv = pd.read_csv('data/직무코드_캠프명_매핑.csv')
csv.columns = [c.strip() for c in csv.columns]

qna = pd.read_excel('data/community_qna_samples_20260910.xlsx')
qna = qna[qna['question_category_group'] == '취업 고민']

valid_categories = set(csv['직무중분류'].unique())
valid_details = set(csv['상세분류'].dropna().unique())
cat_pool = csv.groupby('직무중분류').size()
code_pool = csv.groupby('직무코드').size()

target_counts = qna[qna['question_target_job'] != '모든 직무']['question_target_job'].value_counts()

# ── 2. 완전 커버리지 공백: target_job이 직무중분류(job_category) 리스트에 아예 없음 ──
missing = target_counts[~target_counts.index.isin(valid_categories)]
missing_df = pd.DataFrame({
    '유저입력_target_job': missing.index,
    '수요건수': missing.values,
})
missing_df['job_detail_리스트에는_존재'] = missing_df['유저입력_target_job'].isin(valid_details)
missing_df['비고'] = missing_df['job_detail_리스트에는_존재'].map(
    lambda x: '⚠️ job_detail 필드로는 존재 — AI가 job_category로 잘못 매핑할 위험' if x else '완전 미매핑 (신규 직무중분류 추가 검토 필요)'
)
missing_df = missing_df.drop(columns=['job_detail_리스트에는_존재']).sort_values('수요건수', ascending=False)

# ── 3. 얇은 커버리지: target_job이 존재하지만 캠프 풀이 THIN_POOL_THRESHOLD 이하 ──
existing = target_counts[target_counts.index.isin(valid_categories)]
thin_df = pd.DataFrame({
    '직무중분류': existing.index,
    '수요건수': existing.values,
})
thin_df['캠프풀크기'] = thin_df['직무중분류'].map(cat_pool)
thin_df = thin_df[thin_df['캠프풀크기'] <= THIN_POOL_THRESHOLD]
thin_df = thin_df.sort_values(['수요건수', '캠프풀크기'], ascending=[False, True])

# ── 4. 참고용 전체 현황: 직무중분류별 캠프 수 (145개 전체, 오름차순) ──
all_cat_df = cat_pool.reset_index()
all_cat_df.columns = ['직무중분류', '캠프풀크기(전체)']
all_cat_df['수요건수(target_job 기준)'] = all_cat_df['직무중분류'].map(target_counts).fillna(0).astype(int)
all_cat_df = all_cat_df.sort_values('캠프풀크기(전체)')

# ── 5. 참고용 전체 현황: 직무코드(정확 키)별 캠프 수 (451개 전체, 오름차순) ──
all_code_df = code_pool.reset_index()
all_code_df.columns = ['직무코드', '캠프수']
all_code_df = all_code_df.sort_values('캠프수')

# ── 6. 요약 시트 ──
summary_df = pd.DataFrame([
    {'항목': '전체 직무중분류 수', '값': len(cat_pool)},
    {'항목': '전체 직무코드(정확 키) 수', '값': len(code_pool)},
    {'항목': '캠프 1개뿐인 직무중분류 수', '값': int((cat_pool == 1).sum())},
    {'항목': f'캠프 {THIN_POOL_THRESHOLD}개 이하인 직무중분류 수', '값': int((cat_pool <= THIN_POOL_THRESHOLD).sum())},
    {'항목': '캠프 1개뿐인 직무코드 수', '값': int((code_pool == 1).sum())},
    {'항목': 'target_job 기준 완전 미매핑 직무 종류 수', '값': len(missing_df)},
    {'항목': 'target_job 기준 완전 미매핑 총 건수', '값': int(missing_df['수요건수'].sum())},
    {'항목': f'수요 있고 캠프풀 {THIN_POOL_THRESHOLD}개 이하인 직무중분류 종류 수', '값': len(thin_df)},
])

# ── 7. 엑셀 저장 ──
output_path = 'docs/camp_coverage_gap_analysis.xlsx'
with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    summary_df.to_excel(writer, sheet_name='요약', index=False)
    missing_df.to_excel(writer, sheet_name='1_완전공백_직무', index=False)
    thin_df.to_excel(writer, sheet_name='2_얇은커버리지_직무', index=False)
    all_cat_df.to_excel(writer, sheet_name='참고_직무중분류별_캠프수', index=False)
    all_code_df.to_excel(writer, sheet_name='참고_직무코드별_캠프수', index=False)

print(f"✅ 저장 완료: {output_path}")
print(f"  - 완전공백 직무: {len(missing_df)}종 (총 {missing_df['수요건수'].sum()}건)")
print(f"  - 얇은커버리지 직무: {len(thin_df)}종")
