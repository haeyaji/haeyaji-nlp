from app.application.query_mapper import pick_search_queries


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
