from app.application.query_mapper import (
    category_code_for,
    is_outdoor,
    is_rainy,
    normalize_query,
    pick_search_queries,
)


def test_activity_word_normalized_to_category():
    # 소풍/피크닉은 장소명이 아니라 활동 → 공원으로 정규화 (literal '소풍' 검색 방지)
    assert normalize_query("소풍") == "공원"
    assert normalize_query("피크닉") == "공원"
    assert normalize_query("카페") == "카페"  # 일반 검색어는 그대로


def test_rainy_and_outdoor_helpers():
    assert is_rainy("비 18도") and is_rainy("눈 옴")
    assert not is_rainy("맑음")
    assert is_outdoor("공원") and is_outdoor("소풍")  # 소풍→공원→야외
    assert not is_outdoor("카페")


def test_category_code_food_vs_cafe():
    assert category_code_for("맛집") == "FD6"
    assert category_code_for("한식") == "FD6"
    assert category_code_for("카페") == "CE7"
    assert category_code_for("방탈출카페") is None  # 모르는 검색어 → 필터 없음


def test_food_request_maps_to_restaurant():
    # "밥집"을 명시하면 반드시 맛집을 검색해야 한다 (카페/공원으로 새면 안 됨)
    q = pick_search_queries("맑음", "", "점심 밥집 추천해줘")
    assert "맛집" in q
    assert "공원" not in q  # 명시 카테고리가 있으면 날씨 기본값으로 희석 안 함


def test_explicit_cafe():
    assert "카페" in pick_search_queries("맑음", "", "조용한 카페 가고싶어")


def test_rainy_removes_outdoor():
    q = pick_search_queries("비 18도", "무기력", "조용한 데")
    assert "카페" in q
    assert "공원" not in q  # 비 → 야외 제거
    assert "산책로" not in q


def test_sunny_default_allows_outdoor():
    # 명시/형용사 없으면 날씨 기본값 → 맑으면 야외 포함
    q = pick_search_queries("맑음", "", "")
    assert "공원" in q or "산책로" in q


def test_quiet_vibe_maps_to_quiet_categories():
    q = pick_search_queries("맑음", "", "조용한 데 가고싶어")
    assert "도서관" in q or "북카페" in q
