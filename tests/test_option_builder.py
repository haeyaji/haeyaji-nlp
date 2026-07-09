from app.application.option_builder import narrow_prompt, pick_options


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


def test_narrow_prompt_rainy_frames_indoor():
    q, opts = narrow_prompt("비, 18도", "오후 2시")
    assert "실내" in q                 # 비 → 실내 프레이밍
    assert "야외/산책" not in opts       # 칩도 야외 제외


def test_narrow_prompt_sunny_allows_outdoor():
    q, opts = narrow_prompt("맑음, 22도", "오후 2시")
    assert "야외/산책" in opts
    assert "실내" not in q              # 맑으면 실내 프레이밍 안 함
