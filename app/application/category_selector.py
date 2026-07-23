"""추천 1단계 — 카테고리 후보(2~4개) 생성 (코드 규칙, LLM 아님).

날씨·시간대·사용자 프로필로 10종 중 상황에 맞는 카테고리를 점수화해 고른다.
매번 같은 상황이면 같은 후보가 나오도록 결정론적으로(칩 철학과 동일).

- reason: 상황별 템플릿 문구
- keywords: 카테고리 기본 세부어 + 프로필에서 매칭된 취향어 (be 키워드 학습용)
"""

from app.application.category_map import (
    ALL_CODES,
    OUTDOOR_CODES,
    default_keywords_for,
    label_for,
)
from app.domain.models import CategoryOption, UserProfile

_RAINY = ("비", "눈", "소나기", "장마")
_NIGHT = ("밤", "저녁", "새벽")

# 상황별 가점 (기본 점수 0에서 시작, 계약 순서로 동점 정렬)
_RAINY_BOOST = {"CAFE_DESSERT", "INDOOR_PLAY", "CULTURE_EXHIBIT", "REST_HEALING"}
_NIGHT_BOOST = {"RESTAURANT", "SOCIAL", "CAFE_DESSERT"}
_SUNNY_BOOST = {"NATURE_WALK", "SPORTS_ACTIVITY", "CAFE_DESSERT"}

# 프로필 자유어(라벨+세부키워드 혼합) → code 매칭. 부분 문자열 포함이면 매칭.
_PROFILE_HINT: list[tuple[tuple[str, ...], str]] = [
    (("카페", "디저트", "커피", "감성"), "CAFE_DESSERT"),
    (("맛집", "먹", "밥", "food"), "RESTAURANT"),
    (("산책", "자연", "공원", "야외", "나들이"), "NATURE_WALK"),
    (("운동", "액티비티", "클라이밍", "볼링", "스포츠"), "SPORTS_ACTIVITY"),
    (("전시", "문화", "박물관", "미술", "영화"), "CULTURE_EXHIBIT"),
    (("방탈출", "실내놀이", "보드게임", "오락", "pc방", "PC방"), "INDOOR_PLAY"),
    (("휴식", "힐링", "스파", "찜질", "쉬"), "REST_HEALING"),
    (("공부", "작업", "스터디", "카공", "개발", "코딩"), "STUDY_WORK"),
    (("사람", "모임", "친구", "술"), "SOCIAL"),
    (("쇼핑", "아울렛", "백화점"), "SHOPPING"),
]
# 그룹 힌트 — 특정 code가 아니라 계열 전체를 가점
_GROUP_HINT: list[tuple[str, set[str]]] = [
    ("실내", _RAINY_BOOST | {"STUDY_WORK", "SHOPPING", "SOCIAL"}),
    ("야외", {"NATURE_WALK", "SPORTS_ACTIVITY"}),
]

# reason 템플릿 — (조건, code) 우선, 없으면 code 기본
_REASON_DEFAULT = {
    "CAFE_DESSERT": "커피 한 잔 여유",
    "RESTAURANT": "맛있는 한 끼",
    "NATURE_WALK": "바람 쐬며 산책",
    "SPORTS_ACTIVITY": "몸 움직이며 활력",
    "CULTURE_EXHIBIT": "전시로 기분 환기",
    "INDOOR_PLAY": "실내에서 신나게",
    "REST_HEALING": "푹 쉬며 재충전",
    "STUDY_WORK": "집중해서 작업",
    "SOCIAL": "사람들과 어울리기",
    "SHOPPING": "구경하며 쇼핑",
}
_REASON_RAINY = {
    "CAFE_DESSERT": "비 오는 날 감성",
    "INDOOR_PLAY": "비 안 맞고 놀기",
    "CULTURE_EXHIBIT": "실내에서 문화생활",
    "REST_HEALING": "비 오는 날 푹 쉬기",
}


def _matched_codes(profile: UserProfile | None) -> tuple[dict[str, list[str]], set[str]]:
    """프로필 → {code: 매칭된 취향어들}, 그룹가점 code 집합."""
    hits: dict[str, list[str]] = {}
    group: set[str] = set()
    if profile is None:
        return hits, group
    for pref in profile.preferred_categories:
        low = pref.strip()
        for keys, code in _PROFILE_HINT:
            if any(k in low for k in keys):
                hits.setdefault(code, []).append(low)
        for token, codes in _GROUP_HINT:
            if token in low:
                group |= codes
    return hits, group


def select_categories(
    weather: str = "",
    time_of_day: str = "",
    profile: UserProfile | None = None,
    exclude: set[str] | None = None,
    limit: int = 3,
) -> list[CategoryOption]:
    """상황에 맞는 카테고리 후보 2~4개(기본 3)를 점수순으로 반환 (중복 없음)."""
    rainy = any(w in weather for w in _RAINY)
    night = any(t in time_of_day for t in _NIGHT)
    excluded = set(exclude or set())
    if rainy or night:
        excluded |= OUTDOOR_CODES  # 비/눈·밤이면 야외 제외

    prof_hits, prof_group = _matched_codes(profile)
    avoid = set()
    if profile and profile.avoid:
        for a in profile.avoid:
            for keys, code in _PROFILE_HINT:
                if any(k in a for k in keys):
                    avoid.add(code)
    excluded |= avoid

    scores: dict[str, int] = {}
    for i, code in enumerate(ALL_CODES):
        if code in excluded:
            continue
        s = -i  # 계약 순서 tie-break (앞쪽 우선)
        if rainy and code in _RAINY_BOOST:
            s += 100
        if night and code in _NIGHT_BOOST:
            s += 100
        if not rainy and not night and code in _SUNNY_BOOST:
            s += 60
        if code in prof_group:
            s += 80
        if code in prof_hits:
            s += 200  # 명시 취향 최우선
        scores[code] = s

    ranked = sorted(scores, key=lambda c: (-scores[c],))
    picked = ranked[: max(2, min(limit, 4))]

    out: list[CategoryOption] = []
    for code in picked:
        reason = ""
        if rainy:
            reason = _REASON_RAINY.get(code, "")
        reason = reason or _REASON_DEFAULT.get(code, "")
        keywords = list(prof_hits.get(code, [])) or default_keywords_for(code)
        out.append(
            CategoryOption(code=code, label=label_for(code), reason=reason, keywords=keywords)
        )
    return out


_NEGATION = ("말고", "말구", "빼고", "싫", "별로")


def rejected_codes(text: str) -> set[str]:
    """"카페 말고" 같은 부정 → 제외할 카테고리 code 집합 (부정어 없으면 빈 집합)."""
    if not any(n in text for n in _NEGATION):
        return set()
    codes: set[str] = set()
    for keys, code in _PROFILE_HINT:
        if any(k in text for k in keys):
            codes.add(code)
    return codes


def category_intro(weather: str = "", time_of_day: str = "") -> str:
    """1단계 후보 제시 문구 — 상황 프레이밍."""
    if any(w in weather for w in _RAINY):
        return "비가 오네요, 이런 건 어때요?"
    if any(t in time_of_day for t in _NIGHT):
        return "이 시간엔 뭐가 끌려요?"
    return "오늘 뭐가 끌려요?"
