import asyncio

from app.api.schemas import MessageRequest, MessageResponse
from app.application.handler.action_handler import ActionHandler
from app.application.message_service import MessageService
from app.domain.models import Analysis, TodoItem, UserProfile


class _FakeClassifier:
    def __init__(self, analysis: Analysis):
        self._analysis = analysis

    async def classify(self, text, history=None):
        return self._analysis


class _FakeGeocoder:
    async def geocode(self, query):
        return None  # 지역 없음 → 현재 위치 유지


class _AnywhereGeocoder:
    """뭘 물어도 좌표를 주는 지오코더 — 잘못된 후보가 넘어오면 중심이 튄다."""

    async def geocode(self, query):
        return (35.0, 129.0)


class _CaptureHandler:
    """핸들러로 들어온 req를 캡처해 슬롯 매핑을 검증한다."""

    def __init__(self, todos=None):
        self.seen: MessageRequest | None = None
        self._todos = todos or []

    async def handle(self, req: MessageRequest) -> MessageResponse:
        self.seen = req
        return MessageResponse(intent="recommend", reply="분석.", todos=self._todos)


def _service(analysis: Analysis, handler=None):
    handler = handler or _CaptureHandler()
    svc = MessageService(
        classifier=_FakeClassifier(analysis),
        geocoder=_FakeGeocoder(),
        recommend_handler=handler,
        info_handler=handler,
        chat_handler=handler,
        action_handler=ActionHandler(recommend_handler=handler),
    )
    return svc, handler


def _req(**kwargs):
    base = dict(text="아무거나", lat=37.5, lng=127.0)
    base.update(kwargs)
    return MessageRequest(**base)


# ── 명시 종류 → 1단계 건너뛰고 바로 장소 추천 ──────────────────────────

def test_prefer_near_maps_to_distance_sort():
    svc, handler = _service(Analysis(intent="recommend", keywords=["맛집"], prefer="near"))
    asyncio.run(svc.handle(_req(text="가까운 밥집", mood="배고픔")))
    assert handler.seen.search_sort == "distance"
    assert handler.seen.search_keywords == ["맛집"]


def test_default_sort_is_accuracy():
    svc, handler = _service(Analysis(intent="recommend", keywords=["맛집"]))
    asyncio.run(svc.handle(_req(text="유명한 밥집", mood="배고픔")))
    assert handler.seen.search_sort == "accuracy"


def test_geo_keyword_filtered():
    # 분류기가 지역명을 keywords에 섞어도 검색어에서 제외된다
    svc, handler = _service(Analysis(intent="recommend", keywords=["강남역", "방탈출"]))
    asyncio.run(svc.handle(_req(text="강남역 방탈출", mood="심심")))
    assert handler.seen.search_keywords == ["방탈출"]


def test_explicit_keyword_skips_category_step():
    # 구체 종류가 있으면 카테고리 후보 없이 바로 장소 추천
    svc, handler = _service(Analysis(intent="recommend", keywords=["맛집"]))
    resp = asyncio.run(svc.handle(_req(text="밥집 추천", mood="배고픔")))
    assert handler.seen is not None
    assert resp.categories == []


def test_place_type_word_never_moves_center():
    handler = _CaptureHandler()
    svc = MessageService(
        classifier=_FakeClassifier(Analysis(intent="recommend", keywords=["PC방"])),
        geocoder=_AnywhereGeocoder(),
        recommend_handler=handler, info_handler=handler, chat_handler=handler,
        action_handler=ActionHandler(recommend_handler=handler),
    )
    asyncio.run(svc.handle(_req(text="PC방 가고싶어", mood="심심")))
    assert (handler.seen.lat, handler.seen.lng) == (37.5, 127.0)


def test_food_word_never_moves_center():
    handler = _CaptureHandler()
    svc = MessageService(
        classifier=_FakeClassifier(Analysis(intent="recommend", keywords=["맛집"])),
        geocoder=_AnywhereGeocoder(),
        recommend_handler=handler, info_handler=handler, chat_handler=handler,
        action_handler=ActionHandler(recommend_handler=handler),
    )
    asyncio.run(svc.handle(_req(text="밥집 가고싶어", mood="배고픔")))
    assert (handler.seen.lat, handler.seen.lng) == (37.5, 127.0)


def test_picnic_goes_direct_not_narrow():
    # 소풍/나들이는 '어디로(위치)' 축 → 카테고리 안 묻고 공원 직접 추천
    svc, handler = _service(Analysis(intent="recommend", keywords=["공원"]))
    asyncio.run(svc.handle(_req(text="소풍 갈래", weather="맑음")))
    assert handler.seen is not None


def test_broad_activity_with_category_recommends_directly():
    svc, handler = _service(Analysis(intent="recommend", keywords=["카페"]))
    asyncio.run(svc.handle(_req(text="데이트할 카페", mood="설렘")))
    assert handler.seen is not None
    assert handler.seen.search_keywords == ["카페"]


def test_geo_keyword_does_not_block_center_move():
    # keywords에 지역명(강남역)이 섞여도 위치 해석은 살고, 지역명은 검색어에서 빠진다
    handler = _CaptureHandler()
    svc = MessageService(
        classifier=_FakeClassifier(Analysis(intent="recommend", keywords=["강남역", "맛집"])),
        geocoder=_AnywhereGeocoder(),
        recommend_handler=handler, info_handler=handler, chat_handler=handler,
        action_handler=ActionHandler(recommend_handler=handler),
    )
    asyncio.run(svc.handle(_req(text="강남역 맛집 추천", mood="배고픔")))
    assert (handler.seen.lat, handler.seen.lng) == (35.0, 129.0)  # 중심 이동됨
    assert handler.seen.search_keywords == ["맛집"]               # 지역명 제외


# ── 1단계: 막연하면 카테고리 후보 제시 ─────────────────────────────────

def test_vague_returns_category_candidates():
    svc, handler = _service(Analysis(intent="recommend", keywords=[]))
    resp = asyncio.run(svc.handle(_req(text="오늘 뭐하지")))
    assert handler.seen is None                    # 장소 핸들러 미호출
    assert resp.intent == "recommend_category"
    assert 2 <= len(resp.categories) <= 4
    assert resp.todos == []


def test_category_candidates_are_valid_codes():
    from app.application.category_map import ALL_CODES
    svc, _ = _service(Analysis(intent="recommend", keywords=[]))
    resp = asyncio.run(svc.handle(_req(text="추천해줘", weather="맑음")))
    codes = [c.code for c in resp.categories]
    assert len(codes) == len(set(codes))           # 중복 없음
    assert all(c in ALL_CODES for c in codes)
    assert all(c.label and c.keywords for c in resp.categories)


def test_step1_rainy_excludes_nature():
    svc, _ = _service(Analysis(intent="recommend", keywords=[]))
    resp = asyncio.run(svc.handle(_req(text="뭐하지", weather="비, 18도")))
    assert resp.intent == "recommend_category"
    assert "NATURE_WALK" not in [c.code for c in resp.categories]


def test_step1_profile_boosts_preferred():
    svc, _ = _service(Analysis(intent="recommend", keywords=[]))
    resp = asyncio.run(
        svc.handle(_req(text="추천", user_profile=UserProfile(preferred_categories=["맛집"])))
    )
    assert resp.categories[0].code == "RESTAURANT"  # 명시 취향 최우선


def test_negation_returns_step1_excluding_category():
    # "카페 말고" → 다시 카테고리 후보 제시하되 카페는 제외
    svc, handler = _service(Analysis(intent="recommend", keywords=["카페"]))
    resp = asyncio.run(svc.handle(_req(text="카페 말고 딴거", weather="맑음")))
    assert handler.seen is None
    assert resp.intent == "recommend_category"
    assert "CAFE_DESSERT" not in [c.code for c in resp.categories]


# ── 2단계: 선택 카테고리 → 그 안에서 장소 ──────────────────────────────

def test_selected_category_goes_to_places():
    svc, handler = _service(Analysis(intent="recommend", keywords=[]))
    asyncio.run(svc.handle(_req(text="이걸로", selected_category="CAFE_DESSERT")))
    assert handler.seen is not None                          # 장소 핸들러 호출
    assert handler.seen.search_keywords == ["카페", "디저트"]  # 카테고리 검색어로 치환


def test_selected_category_tags_todos():
    todo = TodoItem(title="x", reason="r", category="RESTAURANT", estimated_minutes=30)
    handler = _CaptureHandler(todos=[todo])
    svc = MessageService(
        classifier=_FakeClassifier(Analysis(intent="recommend", keywords=[])),
        geocoder=_FakeGeocoder(),
        recommend_handler=handler, info_handler=handler, chat_handler=handler,
        action_handler=ActionHandler(recommend_handler=handler),
    )
    resp = asyncio.run(svc.handle(_req(text="이걸로", selected_category="CAFE_DESSERT")))
    assert resp.todos[0].category == "CAFE_DESSERT"          # 선택 카테고리로 태깅 통일


# ── 액션/도메인 (기존 유지) ────────────────────────────────────────────

def test_cancelled_slot_attaches_fill_action():
    svc, handler = _service(Analysis(intent="recommend", keywords=["맛집"]))
    resp = asyncio.run(
        svc.handle(_req(text="1시 일정 취소됐는데 그 시간에 할거 추천해줘", weather="맑음"))
    )
    assert handler.seen is not None
    assert [a.type for a in resp.actions] == ["schedule.fill"]
    assert resp.actions[0].time_range.start_hour == 1


def test_cancelled_slot_with_category_step_keeps_fill():
    # 막연+시간 → 1단계 카테고리라도 be가 슬롯 유지하도록 fill 부착
    svc, _ = _service(Analysis(intent="recommend", keywords=[]))
    resp = asyncio.run(svc.handle(_req(text="1시 취소됐는데 그때 뭐하지", weather="맑음")))
    assert resp.intent == "recommend_category"
    assert [a.type for a in resp.actions] == ["schedule.fill"]


def test_recommend_without_time_has_no_fill():
    svc, _ = _service(Analysis(intent="recommend", keywords=["맛집"]))
    resp = asyncio.run(svc.handle(_req(text="맛집 추천", mood="배고픔")))
    assert resp.actions == []


def test_mixed_domain_salvages_place():
    svc, handler = _service(Analysis(intent="recommend"))
    resp = asyncio.run(svc.handle(_req(text="소풍가서 김치찌개 레시피 추천해줘")))
    assert handler.seen is not None
    assert handler.seen.search_keywords == ["공원"]
    assert resp.reply.startswith("그건 도와드리긴 어렵지만")


def test_pure_domain_still_declines():
    svc, handler = _service(Analysis(intent="recommend"))
    resp = asyncio.run(svc.handle(_req(text="김치찌개 레시피 추천해줘")))
    assert handler.seen is None
    assert resp.intent == "chat"
    assert "도와드리기 어려워요" in resp.reply
