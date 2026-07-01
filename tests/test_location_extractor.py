from app.application.location_extractor import extract_location_candidates


def test_station_suffix():
    assert "강남역" in extract_location_candidates("강남역 가는데 뭐하지")


def test_before_movement():
    assert "판교" in extract_location_candidates("판교 가는데 갈만한 곳")
    assert "성수동" in extract_location_candidates("성수동 갈건데 카페 추천")


def test_no_location():
    # 지역 언급 없음 → 후보 없음
    assert extract_location_candidates("비 오는데 조용한 데 가고싶어") == []


def test_stopwords_filtered():
    assert extract_location_candidates("집에 가는데 심심해") == []
    assert "지역" not in extract_location_candidates("이 지역에서 뭐하지")


def test_no_false_positive_movement_word():
    # '운동'은 역 접미사 아님 → 지역으로 오인 안 함
    assert extract_location_candidates("운동하고 싶어") == []
