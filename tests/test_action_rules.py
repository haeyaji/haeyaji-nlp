from app.application.action_rules import parse_action, parse_target_friend, parse_time_range


# ── 시간 파싱 ──
def test_time_range_start_end():
    tr = parse_time_range("1시부터 3시까지")
    assert tr is not None
    assert (tr.start_hour, tr.end_hour) == (1, 3)
    assert tr.start_minute == 0


def test_time_point_no_end():
    tr = parse_time_range("1시에 일정 잡아줘")
    assert tr.start_hour == 1 and tr.end_hour is None


def test_time_half_and_meridiem():
    tr = parse_time_range("오후 2시반에 보자")
    assert (tr.start_hour, tr.start_minute, tr.meridiem) == (2, 30, "pm")


def test_time_evening_meridiem():
    assert parse_time_range("저녁 7시").meridiem == "pm"


def test_no_time_returns_none():
    assert parse_time_range("놀러 가고싶어") is None


# ── 공유 대상 ──
def test_named_friend():
    assert parse_target_friend("철수랑 공유해줘") == "철수"
    assert parse_target_friend("영희한테 공유") == "영희"


def test_generic_friend_is_none():
    assert parse_target_friend("친구랑 공유해줘") is None


def test_no_share_no_friend():
    assert parse_target_friend("1시에 일정 잡아줘") is None


# ── parse_action 통합 ──
def test_compound_create_and_share():
    p = parse_action("1시부터 3시까지 뭐 할건데 일정 생성해줘. 친구랑 공유해줘")
    assert p is not None
    assert p.create and p.share
    assert (p.time_range.start_hour, p.time_range.end_hour) == (1, 3)
    assert p.target_friend is None  # '친구' = 일반 → be 피커


def test_share_only_with_name():
    p = parse_action("이 일정 철수랑 공유해줘")
    assert p is not None and p.share and not p.create
    assert p.target_friend == "철수"


def test_cancel_slot_is_not_action():
    # 요구 4: 취소+추천은 생성/공유 동사 없음 → None (recommend 경로)
    assert parse_action("1시 일정 취소됐는데 그 시간에 할거 추천해줘") is None


def test_plain_request_is_not_action():
    assert parse_action("오늘 뭐하지") is None
    assert parse_action("강남역 맛집 추천") is None
