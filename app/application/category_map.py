"""10종 카테고리 code ↔ 라벨·검색어 매핑 (be/fe 공용 계약).

- label: fe 표시용 한국어 라벨
- queries: 2단계에서 그 카테고리 장소를 찾을 카카오 검색어들 (핸들러가 검색)
- default_keywords: 1단계 후보에 실을 기본 세부 키워드 (be 키워드축 학습용)

카카오 category_group_code 하드필터는 query_mapper.category_code_for가 검색어별로 붙인다.
"""

# 계약 순서(고정) — 후보 선정 시 동점이면 이 순서로 안정 정렬.
ALL_CODES: list[str] = [
    "CAFE_DESSERT",
    "RESTAURANT",
    "NATURE_WALK",
    "SPORTS_ACTIVITY",
    "CULTURE_EXHIBIT",
    "INDOOR_PLAY",
    "REST_HEALING",
    "STUDY_WORK",
    "SOCIAL",
    "SHOPPING",
]

_META: dict[str, dict] = {
    "CAFE_DESSERT":    {"label": "카페·디저트",   "queries": ["카페", "디저트"],
                        "keywords": ["감성카페"]},
    "RESTAURANT":      {"label": "맛집",          "queries": ["맛집"],
                        "keywords": ["맛집"]},
    "NATURE_WALK":     {"label": "산책·자연",     "queries": ["공원", "산책로"],
                        "keywords": ["공원산책"]},
    "SPORTS_ACTIVITY": {"label": "운동·액티비티", "queries": ["헬스장", "클라이밍장", "볼링장"],
                        "keywords": ["클라이밍"]},
    "CULTURE_EXHIBIT": {"label": "문화·전시",     "queries": ["전시회", "영화관", "박물관"],
                        "keywords": ["전시회"]},
    "INDOOR_PLAY":     {"label": "실내놀이",      "queries": ["방탈출카페", "보드게임카페", "PC방"],
                        "keywords": ["방탈출"]},
    "REST_HEALING":    {"label": "휴식·힐링",     "queries": ["북카페", "스파", "찜질방"],
                        "keywords": ["북카페"]},
    "STUDY_WORK":      {"label": "공부·작업",     "queries": ["스터디카페", "도서관"],
                        "keywords": ["스터디카페"]},
    "SOCIAL":          {"label": "사람만남",      "queries": ["술집", "맛집"],
                        "keywords": ["술집"]},
    "SHOPPING":        {"label": "쇼핑",          "queries": ["쇼핑몰", "아울렛"],
                        "keywords": ["쇼핑몰"]},
}

# 비/눈·밤이면 후보에서 제외할 야외 카테고리
OUTDOOR_CODES: set[str] = {"NATURE_WALK"}


def label_for(code: str) -> str:
    return _META[code]["label"]


def queries_for(code: str) -> list[str]:
    """2단계 장소검색용 카카오 검색어들. 모르는 code면 []."""
    meta = _META.get(code)
    return list(meta["queries"]) if meta else []


def default_keywords_for(code: str) -> list[str]:
    meta = _META.get(code)
    return list(meta["keywords"]) if meta else []
