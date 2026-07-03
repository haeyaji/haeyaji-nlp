from app.application.option_builder import pick_options


def test_sunny_day_includes_outdoor():
    options = pick_options("맑음, 22도", "오후 2시")
    assert "야외/산책" in options
    assert 5 <= len(options) <= 6


def test_rainy_excludes_outdoor():
    options = pick_options("비, 18도", "오후 2시")
    assert "야외/산책" not in options
    assert "영화" in options


def test_night_swaps_outdoor_for_bar():
    options = pick_options("맑음", "밤 10시")
    assert "야외/산책" not in options
    assert "술집/야식" in options


def test_deterministic():
    # 같은 상황이면 항상 같은 칩 (규칙 기반)
    assert pick_options("맑음", "오후") == pick_options("맑음", "오후")
