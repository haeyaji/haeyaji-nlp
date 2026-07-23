from app.application.category_map import ALL_CODES, OUTDOOR_CODES
from app.application.category_selector import (
    category_intro,
    rejected_codes,
    select_categories,
)
from app.domain.models import UserProfile


def _codes(opts):
    return [o.code for o in opts]


def test_returns_2_to_4_unique_valid_codes():
    opts = select_categories(weather="맑음", time_of_day="오후 2시")
    codes = _codes(opts)
    assert 2 <= len(codes) <= 4
    assert len(codes) == len(set(codes))
    assert all(c in ALL_CODES for c in codes)


def test_rainy_excludes_outdoor():
    opts = select_categories(weather="비, 18도")
    assert not (set(_codes(opts)) & OUTDOOR_CODES)


def test_night_excludes_outdoor():
    opts = select_categories(weather="맑음", time_of_day="밤 11시")
    assert not (set(_codes(opts)) & OUTDOOR_CODES)


def test_profile_preference_ranks_first_and_carries_keyword():
    opts = select_categories(profile=UserProfile(preferred_categories=["전시 좋아함"]))
    assert opts[0].code == "CULTURE_EXHIBIT"
    assert "전시 좋아함" in opts[0].keywords  # 매칭된 취향어를 키워드로 실어줌


def test_avoid_drops_category():
    opts = select_categories(
        weather="맑음", profile=UserProfile(avoid=["운동"])
    )
    assert "SPORTS_ACTIVITY" not in _codes(opts)


def test_deterministic():
    a = select_categories(weather="비", time_of_day="오후")
    b = select_categories(weather="비", time_of_day="오후")
    assert _codes(a) == _codes(b)


def test_each_option_has_label_and_keywords():
    for o in select_categories(weather="맑음"):
        assert o.label
        assert o.keywords


def test_rejected_codes_from_negation():
    assert rejected_codes("카페 말고 딴거") == {"CAFE_DESSERT"}
    assert rejected_codes("그냥 추천해줘") == set()  # 부정어 없음


def test_exclude_removes_from_candidates():
    opts = select_categories(weather="맑음", exclude={"CAFE_DESSERT"})
    assert "CAFE_DESSERT" not in _codes(opts)


def test_intro_frames_weather():
    assert "비" in category_intro(weather="비, 18도")
