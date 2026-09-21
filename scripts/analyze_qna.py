"""
코멘토 커뮤니티 QnA 데이터 → 고민 유형 분류 분석 스크립트 (v2)
================================================================
업무요청서 1번 결과물: 유저 고민 유형/특징 분석표

개선사항 (v1 → v2):
  1. 대표 키워드를 "고민 패턴 키워드" + "주요 관심 분야"로 분리
  2. "캠프 추천 시 활용 가능한 정보" 열 추가
  3. 유형별 특징 서술 강화 (유저 프로파일링)
  4. 추가 분석: 타겟 직무 미정 비율, 타겟 기업 미정 비율, 답변 보유율
"""

import pandas as pd
import json
import re
from collections import Counter

# ═════════════════════════════════════════════════
# 1. 데이터 로드
# ═════════════════════════════════════════════════
df = pd.read_excel("community_qna_samples_20260910.xlsx")
df["text"] = df["question_title"].fillna("") + " " + df["question_content"].fillna("")

print(f"총 데이터: {len(df)}건")
print()

# ═════════════════════════════════════════════════
# 2. 기존 카테고리 → 5대 고민 유형 1차 매핑
# ═════════════════════════════════════════════════
CATEGORY_MAP = {
    # ① 직무 미결정 (진로 방향 고민)
    "진로": "직무 미결정",
    "전공": "직무 미결정",
    # ② 스펙 부족
    "스펙": "스펙 부족",
    "인적성": "스펙 부족",
    "자기계발": "스펙 부족",
    "대외활동": "스펙 부족",
    # ③ 인턴 경험 없음 (실무 경험 부족)
    "인턴": "인턴 경험 없음",
    "포트폴리오": "인턴 경험 없음",
    # ④ 자소서/면접 (취업 전략/방법)
    "자소서": "자소서/면접",
    "면접": "자소서/면접",
    # ⑤ 이직 고민
    "이직": "이직 고민",
    "퇴사": "이직 고민",
    "직장생활": "이직 고민",
    "커리어": "이직 고민",
}

df["worry_type"] = df["question_category"].map(CATEGORY_MAP)

# ═════════════════════════════════════════════════
# 3. 키워드 기반 2차 분류 (미분류 건)
# ═════════════════════════════════════════════════
KEYWORD_RULES = [
    {
        "type": "직무 미결정",
        "keywords": [
            "어떤 직무", "무슨 직무", "직무를 못", "직무를 정하지", "직무 선택",
            "진로", "방향", "갈피", "갈 길", "뭘 해야", "무엇을 해야",
            "어떤 분야", "어느 산업", "산업을 선택", "어디로 가야",
            "전공과 다른", "전공 살려", "전공 무관", "비전공",
            "맞는 직무", "적성", "어떤 일", "뭘 하고 싶", "모르겠",
            "직무를 끌고", "직무가 맞을", "직무 추천", "직무를 잡",
        ],
    },
    {
        "type": "스펙 부족",
        "keywords": [
            "자격증", "어학", "토익", "학점", "스펙", "역량",
            "부족", "낮은데", "없는데", "가능할까", "가능한가",
            "자격요건", "지원 자격", "시그마", "기사", "학벌",
            "스펙으로", "준비", "ncs", "필기", "인적성",
            "공부", "수학", "과목", "강의",
        ],
    },
    {
        "type": "인턴 경험 없음",
        "keywords": [
            "인턴", "현장실습", "경험이 없", "경험 없",
            "프로젝트", "포트폴리오", "포폴", "실무 경험",
            "관련 경험", "경력 없", "경험 부족", "아르바이트",
            "실습", "체험",
        ],
    },
    {
        "type": "자소서/면접",
        "keywords": [
            "자소서", "자기소개서", "면접", "지원동기", "지원 동기",
            "작성", "첨삭", "자유 형식", "면접 준비", "ai면접",
            "답변", "어필", "입사 후", "채용", "서류", "합격",
            "지원", "넣어야", "응시",
        ],
    },
    {
        "type": "이직 고민",
        "keywords": [
            "이직", "퇴사", "퇴직", "연봉", "처우", "연차",
            "직장", "재직", "현직", "옮기고", "현재 회사",
            "커리어", "경력직", "이직 준비", "전직", "전환",
        ],
    },
]


def classify_by_keywords(text):
    """키워드 매칭 점수 기반으로 고민 유형 분류"""
    scores = {}
    for rule in KEYWORD_RULES:
        score = sum(1 for kw in rule["keywords"] if kw in text)
        scores[rule["type"]] = score
    max_score = max(scores.values())
    if max_score == 0:
        return None
    return max(scores, key=scores.get)


mask = df["worry_type"].isna()
df.loc[mask, "worry_type"] = df.loc[mask, "text"].apply(classify_by_keywords)

# 3차: 나머지 폴백 매핑
FALLBACK_MAP = {
    "직무": "직무 미결정",
    "회사/산업": "자소서/면접",
    "공기업": "자소서/면접",
    "대학생활": "직무 미결정",
    "중고신입": "스펙 부족",
    "취업": "자소서/면접",
}
still_unmapped = df["worry_type"].isna()
df.loc[still_unmapped, "worry_type"] = df.loc[still_unmapped, "question_category"].map(FALLBACK_MAP)

print(f"최종 미분류: {df['worry_type'].isna().sum()}건")
print()

# ═════════════════════════════════════════════════
# 4. 키워드 사전 정의 (고민 패턴 vs 관심 분야 분리)
# ═════════════════════════════════════════════════

# ① 고민 패턴 키워드: "어떤 고민인가"를 나타내는 표현
WORRY_PATTERN_KEYWORDS = {
    "직무 미결정": [
        "방향", "모르겠", "고민", "선택", "갈피", "적성",
        "어떤 직무", "맞는 직무", "직무를 정하", "직무를 끌고",
        "뭘 해야", "무엇을 해야", "어디로 가야", "못 정했",
        "전공과 다른", "비전공", "전공 무관", "전공 살려",
    ],
    "스펙 부족": [
        "자격증", "학점", "스펙", "부족", "가능할까",
        "토익", "어학", "기사", "기능사", "인적성",
        "없는데", "낮은데", "학벌", "준비", "역량",
    ],
    "인턴 경험 없음": [
        "인턴", "경험 없", "경험이 없", "실무 경험",
        "포트폴리오", "포폴", "프로젝트", "현장실습",
        "실습", "경험 부족", "경력 없",
    ],
    "자소서/면접": [
        "자소서", "면접", "지원동기", "지원 동기", "작성",
        "첨삭", "합격", "채용", "서류", "준비",
        "어필", "입사 후", "답변",
    ],
    "이직 고민": [
        "이직", "퇴사", "퇴직", "연봉", "처우",
        "옮기", "재직", "커리어", "전환", "경력직",
    ],
}

# ② 관심 분야 키워드: "어떤 분야/직무에 관심이 있는가"
INTEREST_FIELD_KEYWORDS = [
    # 전공/산업 분야
    "기계", "화공", "전기", "전자", "전기전자", "토목", "건축", "환경",
    "바이오", "화학", "재료", "소재", "신소재",
    # 산업군
    "반도체", "자동차", "제조", "건설", "플랜트", "에너지", "IT",
    "금융", "은행", "항공", "물류", "유통", "제약", "식품", "게임",
    # 직무 분야
    "설계", "공정", "품질", "생산", "연구", "개발", "영업",
    "마케팅", "기획", "회계", "재무", "인사", "총무", "SCM",
    "데이터", "SW", "프로그래밍",
]


def extract_pattern_keywords(texts, worry_type, n=5):
    """고민 패턴 키워드만 빈도순 추출"""
    kw_list = WORRY_PATTERN_KEYWORDS.get(worry_type, [])
    kw_counts = {}
    for kw in kw_list:
        count = sum(1 for t in texts if kw in t)
        if count > 0:
            kw_counts[kw] = count
    return sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:n]


def extract_interest_fields(texts, n=5):
    """주요 관심 분야 키워드 빈도순 추출"""
    kw_counts = {}
    for kw in INTEREST_FIELD_KEYWORDS:
        count = sum(1 for t in texts if kw in t)
        if count > 0:
            kw_counts[kw] = count
    return sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:n]


# ═════════════════════════════════════════════════
# 5. 유형별 특징 & 캠프 추천 활용 정보 정의
# ═════════════════════════════════════════════════

TYPE_ORDER = ["직무 미결정", "스펙 부족", "인턴 경험 없음", "자소서/면접", "이직 고민"]

CAMP_LINK = {
    "직무 미결정": "✅ 직무탐색 캠프",
    "스펙 부족": "✅ 실무 부트캠프",
    "인턴 경험 없음": "✅ 직무 체험 캠프",
    "자소서/면접": "△ 간접 연결",
    "이직 고민": "✅ 직무전환 캠프",
}

# 유형별 특징 서술 (유저 프로파일링)
TYPE_FEATURES = {
    "직무 미결정": (
        "주로 3~4학년 또는 졸업예정자. "
        "전공과 다른 직무를 고려하거나, 전공 내 세부 직무를 못 정한 상태. "
        "'어떤 직무가 맞을지', '뭘 해야 할지' 등 방향성 자체를 묻는 질문이 주류. "
        "타겟 직무가 '모든 직무'인 비율이 높음."
    ),
    "스펙 부족": (
        "재학생~졸업예정자 비율이 높고, 전체 유형 중 최다(41%). "
        "'자격증이 없는데 가능할까', '학점이 낮아도 되나' 등 자신의 스펙에 대한 불안이 핵심. "
        "구체적 타겟 직무/기업이 있는 경우가 많아, 지원 자격 충족 여부를 확인하려는 의도."
    ),
    "인턴 경험 없음": (
        "실무 경험이 전무한 상태의 취준생. "
        "인턴 경험이 없거나, 있어도 희망 직무와 결이 달라 고민하는 유저. "
        "포트폴리오·프로젝트 경험 부재로 자소서에 쓸 소재가 없다는 불안이 동반됨."
    ),
    "자소서/면접": (
        "자소서 작성법, 면접 답변 방향, 지원 전략 등 취업 실행 단계의 고민. "
        "구체적 타겟 기업/직무가 있는 경우가 많음. "
        "회사/산업 정보 탐색(공고 해석, 기업 분위기 파악)도 이 유형에 포함."
    ),
    "이직 고민": (
        "현직 경력 1~5년차의 커리어 전환 고민이 주류. "
        "건설→제조, 중소→대기업 등 산업/규모 전환 방향을 묻는 질문이 많음. "
        "연봉/처우 불만, 성장 정체에 따른 퇴사 고민도 포함."
    ),
}

# 캠프 추천 시 활용 가능한 정보
CAMP_RECOMMEND_INFO = {
    "직무 미결정": "전공, 관심 직무 후보, 고민 키워드(방향/선택/모르겠)",
    "스펙 부족": "보유 자격증, 타겟 기업/직무, 학점, 부족 역량",
    "인턴 경험 없음": "학년, 전공, 희망 직무, 경험 유무(인턴/프로젝트)",
    "자소서/면접": "지원 기업명, 지원 직무, 준비 단계(서류/면접)",
    "이직 고민": "현재 직무/업종, 경력 연차, 희망 전환 방향",
}

# ═════════════════════════════════════════════════
# 6. 분석 실행 & 산출물 생성
# ═════════════════════════════════════════════════
print("=" * 110)
print("  유저 고민 유형/특징 분석표")
print("=" * 110)
print()

results = []

for wtype in TYPE_ORDER:
    subset = df[df["worry_type"] == wtype]
    count = len(subset)
    pct = count / len(df) * 100

    # ── 고민 패턴 키워드 추출 ──
    pattern_kw = extract_pattern_keywords(subset["text"].tolist(), wtype, n=5)
    pattern_kw_str = ", ".join([w for w, c in pattern_kw])
    pattern_kw_detail = ", ".join([f"{w}({c}건)" for w, c in pattern_kw])

    # ── 주요 관심 분야 추출 ──
    interest_kw = extract_interest_fields(subset["text"].tolist(), n=5)
    interest_kw_str = ", ".join([w for w, c in interest_kw])
    interest_kw_detail = ", ".join([f"{w}({c}건)" for w, c in interest_kw])

    # ── 유저 프로파일 지표 ──
    all_job_pct = round((subset["question_target_job"] == "모든 직무").sum() / count * 100, 1)
    all_company_pct = round((subset["question_target_company"] == "모든 회사").sum() / count * 100, 1)

    # 답변 보유율
    has_answer = subset["answers"].apply(
        lambda x: len(json.loads(x)) > 0 if isinstance(x, str) and x.strip().startswith("[") else False
    ).sum()
    answer_pct = round(has_answer / count * 100, 1)

    # 원 카테고리 분포
    orig_cats = subset["question_category"].value_counts().head(5)
    orig_cat_str = ", ".join([f"{k}({v})" for k, v in orig_cats.items()])

    # 상위 타겟 직무 (모든 직무 제외)
    target_jobs = subset[subset["question_target_job"] != "모든 직무"]["question_target_job"].value_counts().head(5)
    target_job_str = ", ".join([f"{k}({v})" for k, v in target_jobs.items()]) if len(target_jobs) > 0 else "-"

    results.append({
        "고민 유형": wtype,
        "빈도(건)": count,
        "비율(%)": round(pct, 1),
        "고민 패턴 키워드": pattern_kw_str,
        "주요 관심 분야": interest_kw_str,
        "유형별 특징": TYPE_FEATURES[wtype],
        "캠프 추천 시 활용 가능 정보": CAMP_RECOMMEND_INFO[wtype],
        "캠프 연결": CAMP_LINK[wtype],
        # 상세 데이터
        "고민 패턴 키워드 상세": pattern_kw_detail,
        "주요 관심 분야 상세": interest_kw_detail,
        "원 카테고리 분포": orig_cat_str,
        "타겟직무 미정 비율": f"{all_job_pct}%",
        "타겟기업 미정 비율": f"{all_company_pct}%",
        "답변 보유율": f"{answer_pct}%",
        "상위 타겟 직무": target_job_str,
    })

# ── 요약 테이블 출력 ──
print("┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐")
print("│                                    5단계 | 유형화 산출물 요약                                          │")
print("├──────────┬───────┬───────┬──────────────────────┬──────────────────────┬──────────────────┤")
print("│ 고민 유형  │빈도(건)│ 비율  │ 고민 패턴 키워드       │ 주요 관심 분야         │ 캠프 연결         │")
print("├──────────┼───────┼───────┼──────────────────────┼──────────────────────┼──────────────────┤")
for r in results:
    print(f"│ {r['고민 유형']:<8} │ {r['빈도(건)']:>4}  │{r['비율(%)']:>5.1f}% │ {r['고민 패턴 키워드']:<20} │ {r['주요 관심 분야']:<20} │ {r['캠프 연결']:<16} │")
print("└──────────┴───────┴───────┴──────────────────────┴──────────────────────┴──────────────────┘")

# ── 유형별 상세 분석 ──
print()
print("=" * 110)
print("  유형별 상세 분석")
print("=" * 110)

for r in results:
    print()
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  {r['고민 유형']}  |  {r['빈도(건)']}건 ({r['비율(%)']}%)")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print(f"  ■ 고민 패턴 키워드: {r['고민 패턴 키워드 상세']}")
    print(f"  ■ 주요 관심 분야  : {r['주요 관심 분야 상세']}")
    print()
    print(f"  ■ 유형별 특징:")
    # 특징을 50자 단위로 줄바꿈
    feature = r["유형별 특징"]
    for i in range(0, len(feature), 55):
        prefix = "    " if i > 0 else "    "
        print(f"{prefix}{feature[i:i+55]}")
    print()
    print(f"  ■ 캠프 추천 시 활용 가능 정보:")
    print(f"    → {r['캠프 추천 시 활용 가능 정보']}")
    print(f"  ■ 캠프 연결: {r['캠프 연결']}")
    print()
    print(f"  ■ 유저 프로파일 지표:")
    print(f"    - 타겟 직무 미정('모든 직무') 비율: {r['타겟직무 미정 비율']}")
    print(f"    - 타겟 기업 미정('모든 회사') 비율: {r['타겟기업 미정 비율']}")
    print(f"    - 답변 보유율: {r['답변 보유율']}")
    print(f"    - 상위 타겟 직무: {r['상위 타겟 직무']}")
    print(f"    - 원 카테고리 구성: {r['원 카테고리 분포']}")

# ── 유형별 대표 질문 예시 ──
print()
print("=" * 110)
print("  유형별 대표 질문 예시 (각 5건)")
print("=" * 110)

for wtype in TYPE_ORDER:
    subset = df[df["worry_type"] == wtype]
    print(f"\n  ━━━ {wtype} ━━━")
    for _, row in subset.head(5).iterrows():
        print(f"    [{row['question_category']}] {row['question_title']}")

# ═════════════════════════════════════════════════
# 7. 엑셀 산출물 저장
# ═════════════════════════════════════════════════
print()
print("=" * 110)
print("  엑셀 산출물 저장 중...")

# 시트1: 유형화 요약 (핵심 산출물)
summary_cols = [
    "고민 유형", "빈도(건)", "비율(%)",
    "고민 패턴 키워드", "주요 관심 분야", "유형별 특징",
    "캠프 추천 시 활용 가능 정보", "캠프 연결",
]
summary_df = pd.DataFrame(results)[summary_cols]

# 시트2: 유형별 상세 지표
detail_cols = [
    "고민 유형", "빈도(건)", "비율(%)",
    "고민 패턴 키워드 상세", "주요 관심 분야 상세",
    "타겟직무 미정 비율", "타겟기업 미정 비율", "답변 보유율",
    "상위 타겟 직무", "원 카테고리 분포",
]
detail_df = pd.DataFrame(results)[detail_cols]

# 시트3: 전체 분류 결과 (499건)
output_df = df[[
    "question_id", "question_title", "question_content",
    "question_category", "question_category_group",
    "question_target_job", "question_target_company",
    "worry_type",
]].copy()
output_df.rename(columns={"worry_type": "고민_유형_분류"}, inplace=True)

# 시트4: 고민 패턴 키워드 상세
pattern_kw_rows = []
for wtype in TYPE_ORDER:
    subset = df[df["worry_type"] == wtype]
    kws = extract_pattern_keywords(subset["text"].tolist(), wtype, n=15)
    for rank, (word, freq) in enumerate(kws, 1):
        pattern_kw_rows.append({
            "고민 유형": wtype, "순위": rank,
            "키워드 종류": "고민 패턴", "키워드": word, "빈도(건)": freq,
        })
    fields = extract_interest_fields(subset["text"].tolist(), n=15)
    for rank, (word, freq) in enumerate(fields, 1):
        pattern_kw_rows.append({
            "고민 유형": wtype, "순위": rank,
            "키워드 종류": "관심 분야", "키워드": word, "빈도(건)": freq,
        })
kw_detail_df = pd.DataFrame(pattern_kw_rows)

# 저장
output_path = "comento_worry_type_analysis.xlsx"
with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
    summary_df.to_excel(writer, sheet_name="유형화_요약", index=False)
    detail_df.to_excel(writer, sheet_name="유형별_상세지표", index=False)
    output_df.to_excel(writer, sheet_name="전체_분류결과", index=False)
    kw_detail_df.to_excel(writer, sheet_name="키워드_상세", index=False)

print(f"✅ 저장 완료: {output_path}")
print(f"  - 시트1: 유형화_요약 (핵심 산출물 표)")
print(f"  - 시트2: 유형별_상세지표 (프로파일 지표)")
print(f"  - 시트3: 전체_분류결과 (499건 개별 분류)")
print(f"  - 시트4: 키워드_상세 (고민 패턴 + 관심 분야 분리)")
