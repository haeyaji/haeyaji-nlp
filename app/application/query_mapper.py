"""기분·날씨·형용사·명시 카테고리 → 카카오 검색 키워드 매핑 (코드 규칙).

'무엇을 검색할지'는 LLM이 아니라 규칙으로 결정한다.
작은 모델에게 매번 결정시키면 불안정하므로 여기서 고정한다.

우선순위:
1) 사용자가 명시한 카테고리 (밥집→맛집, 카페, 전시 등) — 최우선. 있으면 그걸로 검색.
2) 형용사/기분 (조용→북카페/도서관 등)
3) 둘 다 없으면 날씨 기본값
비/눈이면 야외 카테고리는 최종 제거(날씨 모순 방지).
"""

_RAINY = ("비", "눈", "소나기", "장마")

# 야외 카테고리 — 비/눈일 때 최종 결과에서 제거
_OUTDOOR = {"공원", "산책로"}

# ① 사용자가 명시한 카테고리/의도 → 검색 키워드 (최우선)
_EXPLICIT: list[tuple[tuple[str, ...], str]] = [
    (("밥집", "맛집", "식당", "점심", "저녁", "브런치", "배고", "먹을", "먹고", "먹지", "맛있", "밥 먹"), "맛집"),
    (("카페", "커피", "디저트"), "카페"),
    (("술", "맥주", "펍", "호프", "포차", "와인바"), "술집"),
    (("전시", "미술관", "박물관", "갤러리"), "전시회"),
    (("영화", "영화관"), "영화관"),
    (("서점", "책방"), "서점"),
    (("도서관",), "도서관"),
    (("헬스", "운동하", "짐 가"), "헬스장"),
    (("노래방", "코인노래"), "노래방"),
    (("쇼핑", "아울렛"), "쇼핑몰"),
    (("공원", "산책"), "공원"),
]

# ② 형용사/분위기/기분 → 카테고리 선호
_VIBE_RULES: list[tuple[tuple[str, ...], list[str]]] = [
    (("조용", "차분", "한적", "힐링", "여유", "혼자", "고요"),
     ["북카페", "도서관", "서점", "전시회", "공원"]),
    (("활기", "신나", "신남", "활발", "에너지", "들뜸"),
     ["맛집", "전시회", "헬스장"]),
    (("감성", "분위기", "예쁜", "데이트", "뷰"),
     ["카페", "전시회", "공원"]),
    (("운동", "땀", "활동적", "움직"),
     ["헬스장", "공원", "산책로"]),
    (("무기력", "우울", "지침", "피곤", "처짐", "쉬고", "쉬"),
     ["카페", "산책로", "공원"]),
]


# 집/온라인 활동 표시어 — 이게 있으면 장소를 붙이지 않는다
_HOME_HINT = ("집에서", "집안", "온라인", "홈트", "홈 트", "재택", "방에서", "실내에서 혼자")

# 검색어 → 카카오 category_group_code 하드 필터.
# "맛집"(FD6=음식점) 검색에 카페(CE7)가 섞이는 것을 API 레벨에서 원천 차단한다.
_CATEGORY_GROUP: dict[str, str] = {
    # 음식점 (FD6)
    "맛집": "FD6", "한식": "FD6", "중식": "FD6", "일식": "FD6", "양식": "FD6",
    "분식": "FD6", "고기": "FD6", "치킨": "FD6", "피자": "FD6", "버거": "FD6",
    "국밥": "FD6", "라멘": "FD6", "브런치": "FD6", "술집": "FD6", "야식": "FD6",
    # 카페 (CE7)
    "카페": "CE7", "북카페": "CE7", "디저트": "CE7",
    # 문화시설 (CT1)
    "전시회": "CT1", "미술관": "CT1", "박물관": "CT1", "영화관": "CT1",
}


def category_code_for(query: str) -> str | None:
    """검색어에 해당하는 카카오 category_group_code (모르는 검색어는 None=필터 없음)."""
    return _CATEGORY_GROUP.get(query)


def keyword_from_text(text: str) -> str | None:
    """텍스트에 명시된 장소 종류 하나를 반환 (없으면 None).

    LLM이 search_query를 안 채웠을 때 할 일 제목에서 장소 키워드를 복구하는 용도.
    _EXPLICIT만 보고 날씨 기본값은 안 씀 → 집/온라인 활동은 None(장소 안 붙임).
    """
    if any(h in text for h in _HOME_HINT):
        return None
    for keywords, cat in _EXPLICIT:
        if any(k in text for k in keywords):
            return cat
    return None


def pick_search_queries(weather: str, mood: str, text: str = "") -> list[str]:
    """명시 카테고리 → 형용사 → (없으면) 날씨 기본값. 비/눈이면 야외 제거."""
    rainy = any(w in weather for w in _RAINY)
    blob = f"{mood} {text}"
    queries: set[str] = set()

    # ① 명시적으로 언급한 카테고리 (최우선)
    for keywords, cat in _EXPLICIT:
        if any(k in blob for k in keywords):
            queries.add(cat)

    # ② 형용사/기분 선호
    for keywords, cats in _VIBE_RULES:
        if any(k in blob for k in keywords):
            queries |= set(cats)

    # ③ 아무것도 안 잡히면 날씨 기본값
    if not queries:
        queries |= {"카페", "전시회", "서점", "영화관"} if rainy else {"공원", "산책로", "카페"}

    # ④ 비/눈이면 야외 제거 (다 빠지면 실내 기본으로)
    if rainy:
        queries -= _OUTDOOR
        if not queries:
            queries |= {"카페", "전시회"}

    return list(queries)
