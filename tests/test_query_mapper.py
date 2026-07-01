from app.application.query_mapper import pick_search_queries


def test_rainy_removes_outdoor():
    q = pick_search_queries("비 18도", "무기력", "조용한 데")
    assert "카페" in q
    assert "공원" not in q  # 비 → 야외 제거
    assert "산책로" not in q


def test_sunny_allows_outdoor():
    q = pick_search_queries("맑음", "활기참", "")
    assert "공원" in q or "산책로" in q


def test_quiet_vibe_maps_to_quiet_categories():
    q = pick_search_queries("맑음", "", "조용한 데 가고싶어")
    assert "도서관" in q or "북카페" in q
