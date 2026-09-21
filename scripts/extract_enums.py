import pandas as pd
import json

# CSV 로드
df = pd.read_csv('data/직무코드_캠프명_매핑.csv')

# 컬럼에 공백이 있을 수 있으므로 처리
df.columns = [col.strip() for col in df.columns]

# 각 컬럼의 고유값 추출 (결측치 제외)
job_categories = sorted([str(x).strip() for x in df['직무중분류'].dropna().unique() if str(x).strip()])
job_details = sorted([str(x).strip() for x in df['상세분류'].dropna().unique() if str(x).strip()])
industries = sorted([str(x).strip() for x in df['산업'].dropna().unique() if str(x).strip()])

# N/A는 명시적으로 null이나 N/A로 다루지만, Enum 리스트에는 문자열로 포함
enums = {
    "job_category": job_categories,
    "job_detail": job_details,
    "industry": industries
}

# JSON 파일로 저장
with open('data/enums.json', 'w', encoding='utf-8') as f:
    json.dump(enums, f, ensure_ascii=False, indent=2)

print(f"job_category: {len(job_categories)}개")
print(f"job_detail: {len(job_details)}개")
print(f"industry: {len(industries)}개")
print("✅ data/enums.json 파일이 생성되었습니다.")
